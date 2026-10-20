# Tkinter Android Native POC — engineering starter

This is an isolated investigation package for the existing Jupyter Android app.
It does **not** claim that Tkinter is already working.

## Confirmed from the uploaded APK and live diagnostic
- Runtime: Chaquopy / CPython 3.10.22, Android arm64-v8a.
- `tkinter` and `_tkinter` are missing at runtime.
- The APK contains Chaquopy's `libpython3.10.so`, but no packaged Tcl/Tk libraries or `_tkinter` extension were found in the APK archive.
- Existing app uses a Flask + Waitress Python backend and a WebView/CodeMirror notebook UI.

## Chosen native research direction
Investigate the AndroWish Tcl/Tk Android port. It supplies a Tcl/Tk 8.6 port using an SDL2-based rendering backend. This is a promising native runtime source, but it is **not** itself a Python `_tkinter` extension. The next engineering step is to build/package compatible Tcl/Tk libraries and then build `_tkinter` against the exact Chaquopy CPython 3.10 ABI. Only after symbol/ABI checks pass should we connect Tk's event loop to Android lifecycle/touch/keyboard handling.

## Important boundaries
- Keep the current Jupyter app and its working features unchanged.
- Keep native Tk work isolated until a real `Tk()`, `Label`, `Entry`, `Button`, and `mainloop()` test passes on-device.
- Do not use `pip install tkinter`: it cannot provide the native Android Tk/Tcl stack.
- Do not treat an HTML/JavaScript widget imitation as native Tkinter compatibility.

## Files
- `apk_audit.py`: inspects an APK archive for Python/Tcl/Tk native payload names.
- `runtime_probe.py`: run inside the app to print runtime ABI, Python version, import results, and likely Tcl/Tk locations.
- `NATIVE_BUILD_STAGES.md`: staged native integration checklist and pass criteria.

## Current status
This package is an engineering starter/audit, not a compiled APK and not a claim of a successful native build. A working APK requires a successful native build and a real-device GUI test.
