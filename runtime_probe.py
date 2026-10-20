\
"""Run this inside the current Chaquopy app to collect native Tk evidence."""
import importlib
import importlib.util
import os
import platform
import sys
import traceback

print("=== TKINTER NATIVE POC PROBE ===")
print("python:", sys.version)
print("executable:", sys.executable)
print("machine:", platform.machine())
print("prefix:", sys.prefix)
print("pythonpath:", os.environ.get("PYTHONPATH", "<unset>"))

for module in ("tkinter", "_tkinter"):
    try:
        spec = importlib.util.find_spec(module)
        print(f"SPEC {module}: {None if spec is None else spec.origin}")
    except BaseException as exc:
        print(f"SPEC ERROR {module}: {type(exc).__name__}: {exc}")

for module in ("tkinter", "_tkinter"):
    try:
        loaded = importlib.import_module(module)
        print(f"IMPORT PASS {module}: {getattr(loaded, '__file__', '<built-in>')}")
    except BaseException:
        print(f"IMPORT FAIL {module}")
        traceback.print_exc()

# Look only in app-accessible locations; this does not scan the whole phone.
roots = [
    "/data/data/com.meraj.jupyternotebook/files",
    "/data/user/0/com.meraj.jupyternotebook/files",
    "/usr/local",
]
needles = ("libtcl", "libtk", "_tkinter", "tcl8.6", "tk8.6")
for root in roots:
    print(f"SEARCH ROOT: {root}")
    if not os.path.exists(root):
        print("  unavailable")
        continue
    found = 0
    for current, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules")]
        for filename in files:
            low = filename.lower()
            if any(n in low for n in needles):
                print("  MATCH:", os.path.join(current, filename))
                found += 1
                if found >= 100:
                    print("  stopped after 100 matches")
                    break
        if found >= 100:
            break
    if found == 0:
        print("  no matching filenames")
print("=== END PROBE ===")
