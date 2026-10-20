\
#!/usr/bin/env python3
"""Inspect APK ZIP entries for likely Python/Tcl/Tk/SDL native components."""
import sys
import zipfile
from pathlib import Path

if len(sys.argv) != 2:
    raise SystemExit("Usage: python apk_audit.py path/to/app.apk")

apk = Path(sys.argv[1])
needles = (
    "_tkinter", "libtcl", "libtk", "tcl8.6", "tk8.6",
    "libSDL2", "libpython3.10", "libpython3.13", "chaquopy",
)
with zipfile.ZipFile(apk) as zf:
    names = zf.namelist()
    print("APK:", apk)
    print("Entries:", len(names))
    for needle in needles:
        matches = [n for n in names if needle.lower() in n.lower()]
        print(f"\n[{needle}] {len(matches)} match(es)")
        for item in matches[:30]:
            print(" ", item)
print("\nNote: ZIP entry inspection cannot prove a shared library is loadable.")
