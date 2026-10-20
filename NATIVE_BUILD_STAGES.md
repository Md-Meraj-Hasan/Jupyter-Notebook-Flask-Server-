# Native Tkinter integration stages

## Stage 0 — baseline (completed from supplied diagnostic and APK archive)
- [x] Confirm Chaquopy CPython 3.10.22 on Android arm64.
- [x] Confirm `tkinter` import fails.
- [x] Confirm `_tkinter` import fails.
- [x] Inspect APK ZIP entries: no Tcl/Tk runtime or `_tkinter` payload was found.
- [x] Preserve existing Flask/WebView notebook as the baseline.

## Stage 1 — acquire and validate Tcl/Tk Android port
- [ ] Pin a specific AndroWish source/SDK revision.
- [ ] Build or obtain the Android arm64 Tcl/Tk/SDL2 artifacts and Tcl library scripts.
- [ ] Verify license notices and redistribution requirements.
- [ ] Verify exported symbols and dependent shared libraries using `readelf -d` / `nm -D`.
- [ ] Confirm ABI/API level compatibility with the app.

## Stage 2 — build `_tkinter` for the exact Chaquopy interpreter
- [ ] Use Chaquopy-compatible CPython 3.10 headers/configuration, not host CPython headers.
- [ ] Compile `_tkinter` against the selected Tcl/Tk libraries for arm64-v8a.
- [ ] Resolve library names/SONAMEs and package all required shared libraries.
- [ ] Verify extension import in the app process before testing a GUI.

## Stage 3 — GUI/event-loop proof
- [ ] `import tkinter` succeeds.
- [ ] `tkinter.Tcl()` succeeds and reports a Tcl patchlevel.
- [ ] `tkinter.Tk()` creates a real visible window.
- [ ] Label renders, Entry accepts keyboard input, Button callback fires.
- [ ] `mainloop()` does not freeze the notebook/server.
- [ ] Android Back, rotation/lifecycle, touch, soft keyboard, and cleanup work.

## Stage 4 — integrate with notebook
- [ ] Launch GUI in a controlled native host, without blocking Flask/Waitress.
- [ ] Route output/errors to notebook console.
- [ ] Preserve current editor, run/stop, file picker, notebook, and theme functions.
- [ ] Only merge after repeatable device tests.

## Current blocker
Stage 1 and Stage 2 are not complete. A source-only Tk/Tcl download or a pure Python package is not enough: the Android native rendering backend, matching Tcl/Tk shared libraries, and a matching `_tkinter` extension are all required.
