"""Copy this repository's entry.png to the output directory.

The entry image is the file entry.png beside this program. The program
copies it to <MAKEFUN_OUTPUT_DIR>/entry.png (default /output/entry.png).
Standard library only; the copy is byte for byte, so repeated runs write
identical bytes.
"""

import os
import shutil
from pathlib import Path


def main() -> None:
    here = Path(__file__).resolve().parent
    source = here / "entry.png"
    if not source.is_file():
        raise FileNotFoundError(f"entry image not found: {source}")
    out_dir = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / "entry.png"
    # Copy to a temporary file in the same directory, then rename it into
    # place, so a run can never leave a half-written entry.png behind.
    tmp = out_dir / ".entry.png.tmp"
    shutil.copyfile(source, tmp)
    if tmp.stat().st_size != source.stat().st_size:
        tmp.unlink(missing_ok=True)
        raise IOError("copied entry.png has the wrong size")
    os.replace(tmp, target)


if __name__ == "__main__":
    main()
