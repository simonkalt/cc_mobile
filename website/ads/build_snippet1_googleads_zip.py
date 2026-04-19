#!/usr/bin/env python3
"""Build snippet1_googleads.zip for Google Ads HTML5 (paths in snippet1.html are ./images/…, ./music/…)."""
from __future__ import annotations

import zipfile
from pathlib import Path

BASE = Path(__file__).resolve().parent
OUT = BASE / "snippet1_googleads.zip"
FILES = [
    BASE / "snippet1.html",
    BASE / "images" / "3.png",
    BASE / "images" / "6.png",
    BASE / "images" / "9.png",
    BASE / "images" / "100.png",
    BASE / "images" / "logo.png",
    BASE / "images" / "footer-app-store.png",
    BASE / "images" / "footer-google-play.avif",
    BASE / "music" / "Niceage_loop.mp3",
]


def main() -> None:
    missing = [p for p in FILES if not p.is_file()]
    if missing:
        raise SystemExit("Missing files:\n" + "\n".join(str(p) for p in missing))
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in FILES:
            arc = path.relative_to(BASE).as_posix()
            zf.write(path, arcname=arc)
    print("Wrote", OUT)
    for name in FILES:
        print(" ", name.relative_to(BASE).as_posix())


if __name__ == "__main__":
    main()
