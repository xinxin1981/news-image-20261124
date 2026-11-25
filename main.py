"""Draw a one-image summary of the world's news of Tuesday 24 November 2026.

Pure standard library only (no PIL, no network, no clock, no external files).
Writes entry.png (1024x1024) to $MAKEFUN_OUTPUT_DIR (default /output).
Deterministic: running it twice produces byte-identical output.
"""

import os
import struct
import zlib

W, H = 1024, 1024

# ---------------------------------------------------------------------------
# 5x7 bitmap font. Each glyph is 7 rows of 5 characters, '#' = pixel on.
# Covers A-Z, 0-9, space and .,:'-()/&%!?
# ---------------------------------------------------------------------------
FONT = {
    'A': (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    'B': ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
    'C': (".###.", "#...#", "#....", "#....", "#....", "#...#", ".###."),
    'D': ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
    'E': ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    'F': ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
    'G': (".###.", "#...#", "#....", "#.###", "#...#", "#...#", ".###."),
    'H': ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    'I': (".###.", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."),
    'J': ("..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."),
    'K': ("#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"),
    'L': ("#....", "#....", "#....", "#....", "#....", "#....", "#####"),
    'M': ("#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"),
    'N': ("#...#", "##..#", "##..#", "#.#.#", "#..##", "#..##", "#...#"),
    'O': (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    'P': ("####.", "#...#", "#...#", "####.", "#....", "#....", "#...."),
    'Q': (".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"),
    'R': ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
    'S': (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    'T': ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    'U': ("#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    'V': ("#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."),
    'W': ("#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"),
    'X': ("#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"),
    'Y': ("#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."),
    'Z': ("#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"),
    '0': (".###.", "#..##", "#.#.#", "##..#", "#...#", "#...#", ".###."),
    '1': ("..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."),
    '2': (".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"),
    '3': ("####.", "....#", "....#", ".###.", "....#", "....#", "####."),
    '4': ("...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."),
    '5': ("#####", "#....", "####.", "....#", "....#", "#...#", ".###."),
    '6': (".###.", "#....", "#....", "####.", "#...#", "#...#", ".###."),
    '7': ("#####", "....#", "...#.", "..#..", "..#..", "..#..", "..#.."),
    '8': (".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."),
    '9': (".###.", "#...#", "#...#", ".####", "....#", "....#", ".###."),
    ' ': (".....", ".....", ".....", ".....", ".....", ".....", "....."),
    '.': (".....", ".....", ".....", ".....", ".....", ".##..", ".##.."),
    ',': (".....", ".....", ".....", ".....", ".##..", ".##..", ".#..."),
    ':': (".....", ".##..", ".##..", ".....", ".##..", ".##..", "....."),
    ';': (".....", ".##..", ".##..", ".....", ".##..", ".##..", ".#..."),
    "'": ("..#..", "..#..", ".#...", ".....", ".....", ".....", "....."),
    '-': (".....", ".....", ".....", ".###.", ".....", ".....", "....."),
    '(': ("...#.", "..#..", ".#...", ".#...", ".#...", "..#..", "...#."),
    ')': (".#...", "..#..", "...#.", "...#.", "...#.", "..#..", ".#..."),
    '/': ("....#", "....#", "...#.", "..#..", ".#...", "#....", "#...."),
    '&': (".##..", "#..#.", "#..#.", ".#...", "#.#.#", "#..#.", ".##.#"),
    '%': ("##..#", "##.#.", "...#.", "..#..", ".#...", "#.##.", "#..##"),
    '!': ("..#..", "..#..", "..#..", "..#..", "..#..", ".....", "..#.."),
    '?': (".###.", "#...#", "....#", "...#.", "..#..", ".....", "..#.."),
}


def text_width(s, scale):
    """Pixel width of string s rendered at the given scale."""
    if not s:
        return 0
    return len(s) * 6 * scale - scale


def wrap_text(s, max_width, scale):
    """Greedy word wrap; returns a list of lines fitting max_width pixels."""
    words = s.split(" ")
    lines = []
    cur = ""
    for word in words:
        trial = word if not cur else cur + " " + word
        if text_width(trial, scale) <= max_width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


class Canvas:
    """An RGB image buffer with tiny drawing primitives."""

    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.px = bytearray(bytes(bg) * (w * h))

    def _set(self, x, y, color):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i] = color[0]
            self.px[i + 1] = color[1]
            self.px[i + 2] = color[2]

    def rect(self, x, y, w, h, color):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(self.w, x + w)
        y1 = min(self.h, y + h)
        for yy in range(y0, y1):
            base = (yy * self.w + x0) * 3
            for xx in range(x0, x1):
                i = base + (xx - x0) * 3
                self.px[i] = color[0]
                self.px[i + 1] = color[1]
                self.px[i + 2] = color[2]

    def hline(self, x0, x1, y, color):
        if x0 > x1:
            x0, x1 = x1, x0
        self.rect(x0, y, x1 - x0 + 1, 1, color)

    def vline(self, x, y0, y1, color):
        if y0 > y1:
            y0, y1 = y1, y0
        self.rect(x, y0, 1, y1 - y0 + 1, color)

    def line(self, x0, y0, x1, y1, color):
        """Bresenham line."""
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self._set(x0, y0, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def circle(self, cx, cy, r, color, fill=True):
        if fill:
            for dy in range(-r, r + 1):
                dx = int((r * r - dy * dy) ** 0.5)
                self.hline(cx - dx, cx + dx, cy + dy, color)
        else:
            for angle in range(360):
                import math
                x = cx + int(r * math.cos(math.radians(angle)))
                y = cy + int(r * math.sin(math.radians(angle)))
                self._set(x, y, color)

    def triangle(self, p1, p2, p3, color):
        """Filled triangle via bounding-box point-in-triangle test."""
        xs = [p1[0], p2[0], p3[0]]
        ys = [p1[1], p2[1], p3[1]]
        x0, x1 = max(0, min(xs)), min(self.w - 1, max(xs))
        y0, y1 = max(0, min(ys)), min(self.h - 1, max(ys))

        def sign(ax, ay, bx, by, cx, cy):
            return (ax - cx) * (by - cy) - (bx - cx) * (ay - cy)

        for yy in range(y0, y1 + 1):
            for xx in range(x0, x1 + 1):
                d1 = sign(xx, yy, p1[0], p1[1], p2[0], p2[1])
                d2 = sign(xx, yy, p2[0], p2[1], p3[0], p3[1])
                d3 = sign(xx, yy, p3[0], p3[1], p1[0], p1[1])
                neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
                pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
                if not (neg and pos):
                    self._set(xx, yy, color)

    def text(self, x, y, s, color, scale=1):
        """Draw string s with its top-left at (x, y). Returns width drawn."""
        s = s.upper()
        cx = x
        for ch in s:
            glyph = FONT.get(ch, FONT["?"])
            for row in range(7):
                bits = glyph[row]
                for col in range(5):
                    if bits[col] == "#":
                        self.rect(cx + col * scale, y + row * scale,
                                  scale, scale, color)
            cx += 6 * scale
        return cx - x - scale if s else 0

    def text_centered(self, cx, y, s, color, scale=1):
        w = text_width(s.upper(), scale)
        self.text(cx - w // 2, y, s, color, scale)
        return w


def _chunk(typ, data):
    out = struct.pack(">I", len(data)) + typ + data
    out += struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
    return out


def write_png(path, canvas):
    """Write the canvas as a PNG. Deterministic for identical pixels."""
    ihdr = struct.pack(">IIBBBBB", canvas.w, canvas.h, 8, 2, 0, 0, 0)
    raw = bytearray()
    stride = canvas.w * 3
    for y in range(canvas.h):
        raw.append(0)
        raw += canvas.px[y * stride:(y + 1) * stride]
    idat = zlib.compress(bytes(raw), 6)
    data = (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr)
            + _chunk(b"IDAT", idat) + _chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(data)
    return len(data)


# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------
PAPER = (247, 242, 231)
WHITE = (255, 255, 255)
INK = (20, 32, 48)
NAVY = (18, 38, 74)
GOLD = (198, 148, 52)
BORDER = (210, 205, 192)
BODY = (70, 74, 84)

CARD_W, CARD_H = 476, 262

# (section label, headline, one-line summary, theme colour)
STORIES = [
    ("WORLD COURT - MYANMAR",
     "ICJ: MYANMAR GENOCIDE",
     "Court rules Myanmar committed genocide against Rohingya.",
     (110, 68, 160)),
    ("TECH - NVIDIA",
     "HUANG BACK AS NVIDIA CEO",
     "Reinstated as chief executive days after resigning.",
     (14, 130, 130)),
    ("SPACE - NATO",
     "NATO VOWS TO DEFEND SPACE",
     "After reports Russia may orbit a nuclear weapon.",
     (36, 98, 178)),
    ("GAZA",
     "ISRAELI STRIKE KILLS HAMAS CHIEF",
     "Security director Naeem Abu Nahel among 7 dead.",
     (178, 44, 44)),
    ("UKRAINE - ZAPORIZHZHIA",
     "RUSSIAN STRIKE HITS FLATS",
     "Two killed, 40 hurt, including four children.",
     (196, 110, 24)),
    ("HEALTH - USA",
     "US LOSES MEASLES-FREE STATUS",
     "Elimination status lost after more than 25 years.",
     (34, 139, 92)),
]


def _tint(color):
    return tuple((c + 255 * 6) // 7 for c in color)


# ---------------------------------------------------------------------------
# Small geometric pictograms, drawn in a 64x64 box at (ox, oy).
# ---------------------------------------------------------------------------
def icon_sun(cv, ox, oy, theme):
    cx, cy = ox + 32, oy + 30
    cv.circle(cx, cy, 14, theme, fill=True)
    for dx, dy in ((1, 0), (1, 1), (0, 1), (-1, 1),
                   (-1, 0), (-1, -1), (0, -1), (1, -1)):
        cv.line(cx + dx * 19, cy + dy * 19, cx + dx * 25, cy + dy * 25, theme)


def icon_rocket(cv, ox, oy, theme):
    cv.triangle((ox + 32, oy + 6), (ox + 22, oy + 28), (ox + 42, oy + 28), theme)
    cv.rect(ox + 24, oy + 28, 16, 22, theme)
    cv.triangle((ox + 24, oy + 44), (ox + 15, oy + 56), (ox + 24, oy + 50), theme)
    cv.triangle((ox + 40, oy + 44), (ox + 49, oy + 56), (ox + 40, oy + 50), theme)
    cv.triangle((ox + 28, oy + 50), (ox + 36, oy + 50), (ox + 32, oy + 60), GOLD)


def icon_ship(cv, ox, oy, theme):
    cv.rect(ox + 10, oy + 38, 44, 12, theme)
    cv.vline(ox + 32, oy + 14, oy + 38, theme)
    cv.triangle((ox + 34, oy + 16), (ox + 34, oy + 36), (ox + 50, oy + 36), theme)
    cv.hline(ox + 8, ox + 56, oy + 56, theme)
    cv.hline(ox + 14, ox + 50, oy + 60, theme)


def icon_truck(cv, ox, oy, theme):
    cv.rect(ox + 8, oy + 22, 32, 20, theme)
    cv.rect(ox + 40, oy + 28, 16, 14, theme)
    cv.rect(ox + 43, oy + 31, 7, 7, WHITE)
    cv.circle(ox + 18, oy + 46, 5, INK, fill=True)
    cv.circle(ox + 46, oy + 46, 5, INK, fill=True)


def icon_warning(cv, ox, oy, theme):
    cv.line(ox + 32, oy + 8, ox + 10, oy + 54, theme)
    cv.line(ox + 10, oy + 54, ox + 54, oy + 54, theme)
    cv.line(ox + 54, oy + 54, ox + 32, oy + 8, theme)
    cv.text(ox + 26, oy + 28, "!", theme, 2)


def icon_chart(cv, ox, oy, theme):
    cv.rect(ox + 12, oy + 14, 10, 38, theme)
    cv.rect(ox + 27, oy + 26, 10, 26, theme)
    cv.rect(ox + 42, oy + 38, 10, 14, theme)
    cv.line(ox + 8, oy + 10, ox + 56, oy + 48, INK)
    cv.triangle((ox + 56, oy + 48), (ox + 46, oy + 46), (ox + 54, oy + 56), INK)


ICONS = [icon_warning, icon_chart, icon_rocket, icon_truck, icon_rocket, icon_sun]


def draw_card(cv, x0, y0, story, icon_fn):
    section, title, summary, theme = story
    cv.rect(x0, y0, CARD_W, CARD_H, WHITE)
    cv.rect(x0, y0, CARD_W, 1, BORDER)
    cv.rect(x0, y0 + CARD_H - 1, CARD_W, 1, BORDER)
    cv.rect(x0, y0, 1, CARD_H, BORDER)
    cv.rect(x0 + CARD_W - 1, y0, 1, CARD_H, BORDER)
    cv.rect(x0, y0, CARD_W, 10, theme)
    cv.rect(x0, y0 + CARD_H - 6, CARD_W, 6, theme)
    # Icon box.
    cv.rect(x0 + 18, y0 + 26, 64, 64, _tint(theme))
    icon_fn(cv, x0 + 18, y0 + 26, theme)
    # Section label beside the icon.
    cv.text(x0 + 96, y0 + 48, section, theme, 2)
    # Headline, up to two lines.
    ty = y0 + 116
    for line in wrap_text(title, CARD_W - 36, 3)[:2]:
        cv.text(x0 + 18, ty, line, INK, 3)
        ty += 30
    # Summary, up to two lines.
    sy = y0 + 190
    for line in wrap_text(summary, CARD_W - 36, 2)[:2]:
        cv.text(x0 + 18, sy, line, BODY, 2)
        sy += 22


def draw():
    cv = Canvas(W, H, PAPER)
    # Top banner.
    cv.rect(0, 0, W, 118, NAVY)
    cv.text_centered(W // 2, 20, "WORLD NEWS", WHITE, 6)
    cv.text_centered(W // 2, 74, "TUESDAY, NOVEMBER 24, 2026", GOLD, 3)
    cv.rect(0, 118, W, 4, GOLD)
    # Story cards: 2 columns x 3 rows.
    positions = [(24, 136), (520, 136), (24, 416),
                 (520, 416), (24, 696), (520, 696)]
    for (x0, y0), story, icon_fn in zip(positions, STORIES, ICONS):
        draw_card(cv, x0, y0, story, icon_fn)
    # Footer.
    cv.rect(24, 972, W - 48, 2, NAVY)
    cv.text_centered(
        W // 2, 984,
        "All six stories happened or were first reported on Tuesday, November 24, 2026.",
        INK, 2)
    return cv


def main():
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    cv = draw()
    os.makedirs(out_dir, exist_ok=True)
    write_png(os.path.join(out_dir, "entry.png"), cv)


if __name__ == "__main__":
    main()
