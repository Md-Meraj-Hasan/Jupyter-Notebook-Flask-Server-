# Android Tkinter Runtime — Implementation Plan

## Current project baseline

- Android app module: `android/app`
- Python runtime: Chaquopy 17.1.0 with CPython 3.10
- ABIs: `arm64-v8a`, `armeabi-v7a`
- Python execution: existing Flask `/run` endpoint in `jupyter.py`
- Android shell: `MainActivity.java` with a local WebView and existing Android file/storage bridge
- The existing notebook, Flask server, scientific packages, and WebView must remain unchanged unless a separately tested integration requires a small additive hook.

## Confirmed blocker

Chaquopy documents `tkinter` as unsupported because its Android runtime does not include the required Tcl/Tk libraries. Adding `pip install tkinter` is not a solution: Tkinter is a Python standard-library wrapper around the native Tcl/Tk runtime, not a normal pure-Python pip package.

## Candidate native runtime

Investigate AndroWish / SDLTk as the Tcl/Tk-on-Android foundation. It provides an Android port of Tcl/Tk and an SDL-based window/rendering backend. Before embedding any binaries or source, verify its current source availability, ABI coverage, license obligations, Android SDK/NDK compatibility, and whether its Tcl/Tk interpreter and Tk window/event loop can be embedded in this Activity rather than launched as a separate app.

## Proposed implementation stages

1. **Runtime feasibility spike (no existing app behavior changes)**
   - Build or obtain reproducible Android native artifacts for Tcl, Tk, SDL2, and required dependencies for both currently supported ABIs.
   - Verify that the runtime can create and display a Tk window inside NiceCoding's Activity.
   - Verify Android lifecycle, touch input, soft keyboard, orientation, and Back behavior.
2. **Python bridge spike**
   - Build a CPython 3.10-compatible `_tkinter` extension against the selected Tcl/Tk build, or implement a compatible in-process bridge.
   - Confirm Tcl interpreter ownership, thread affinity, event-loop pumping, callback routing, and cleanup.
   - Do not claim Python `tkinter` compatibility until `import tkinter`, `Tk()`, `mainloop()`, widgets, and callbacks pass on a physical device.
3. **Isolated demo**
   - Support a small test set: Tk, Label, Entry, Button, Text, Checkbutton, Radiobutton, ttk.Combobox, messagebox, and Toplevel.
   - Add fullscreen/window sizing and mobile-friendly scaling.
4. **Integration**
   - Add a separate GUI execution route while preserving the current Flask `/run` route for ordinary notebook cells.
   - Keep the Tk event loop off the UI-blocking thread and provide explicit stop/cleanup behavior.
5. **Regression and release**
   - Test both ABIs, app restart, multiple Tk windows, keyboard/touch, Android Back, memory cleanup, and all existing notebook/SQL/file workflows.
   - Publish an APK only after a successful CI build and on-device test.

## Acceptance tests

- `import tkinter as tk` succeeds in the bundled NiceCoding Python 3.10 runtime.
- `tk.Tk()` opens a visible native Tk window in NiceCoding.
- Button callbacks, Entry/Text input, ttk.Combobox, Checkbutton, Radiobutton, messagebox, and Toplevel work.
- Fullscreen Toplevel/window behavior works without clipping on phone-sized displays.
- Closing a Tk window returns control to the notebook without killing Flask or the Python runtime.
- Existing Python notebook, SQL, file picker, save/export, and plotting regression tests pass.

## Safety boundary

This branch is intentionally isolated. Do not add a fake `tkinter.py` shim or silently map Tk widgets to HTML: that would make imports appear to work while breaking real Tkinter semantics. Do not change the existing Python version, Chaquopy package set, Flask endpoint, or MainActivity startup path until the native runtime spike is proven.
