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

## Candidate native runtime — research findings

AndroWish is a real Android port of Tcl/Tk 8.6.10, using SDL 2.0.6 plus AGG/Freetype. Its 2024 release provides prebuilt APKs for `armeabi-v7a`, `arm64-v8a`, and `x86_64`. The upstream project describes its architecture as a Java Activity + JNI + native Tcl/Tk/SDL libraries, and documents that its runtime assets and modified Java glue can be reused by other apps.

Important integration risks discovered:

- AndroWish is a Tcl/Tk application runtime, not a CPython `_tkinter` extension. Reusing its APK assets alone will not make `import tkinter` work in Chaquopy.
- The AndroWish port uses SDL/AGG/Freetype and its own Android Activity/event dispatch. It must be hosted or embedded deliberately; simply copying `.so` files into `jniLibs` is insufficient.
- Upstream warns that some builds use a modified Tcl Unicode representation (`TCL_UTF_MAX=6`) which is not binary-compatible with standard Tcl/Tk (`TCL_UTF_MAX=3`). The exact 2024 build configuration must be checked before compiling `_tkinter`.
- NiceCoding currently targets Android API 35 and uses Chaquopy 17.1.0 / CPython 3.10. The upstream AndroWish source/build system is older and must be adapted and validated against the current NDK/Gradle toolchain.
- The official Python Android platform guidance lists `tkinter` as unsupported by default because Android does not officially provide Tk; a custom port is required.

**Decision:** AndroWish is the strongest concrete Tcl/Tk Android foundation found so far, but a Python bridge has not yet been proven. Do not add its prebuilt APK or native libraries to NiceCoding until a minimal in-process Tcl/Tk + CPython 3.10 bridge is demonstrated.

## Next technical spike

1. Obtain and inspect the exact 2024 AndroWish source release and its license files.
2. Identify whether the bundled Tcl/Tk build uses standard or modified Unicode ABI and locate the Tcl/Tk C headers and exported symbols.
3. Build a tiny Android NDK test library for the existing `arm64-v8a` ABI first, exposing Tcl interpreter create/eval/destroy through JNI.
4. Separately compile a CPython 3.10 `_tkinter` extension against that exact Tcl/Tk build; do not mix a stock Tcl/Tk extension with an incompatible AndroWish Tcl ABI.
5. Prove `import tkinter`, `Tk()`, widget creation, event-loop pumping, callbacks, and clean shutdown in a throwaway test Activity before touching NiceCoding's MainActivity or Flask route.
6. Only after arm64 succeeds, repeat for `armeabi-v7a` and add the integration as an optional GUI runner.

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

## Licensing and packaging note

Tcl/Tk itself uses a permissive BSD-style license, but AndroWish is a bundle of multiple upstream components. Before redistributing any copied SDK assets or native binaries, inventory every bundled component and preserve its own license and copyright notices (including SDL, AGG, Freetype, Tcl/Tk, and bundled extensions). Do not assume the Tcl/Tk license covers the entire AndroWish bundle.

The upstream AndroWish documentation explicitly describes reusing its runtime assets and modified Java glue in another Android app. This gives us a plausible packaging route for the Tcl/Tk side, but it does not solve the CPython bridge or guarantee that its Java Activity can be merged directly into NiceCoding's existing Activity.

## Repository files inspected

- `android/app/build.gradle`: Chaquopy 17.1.0, Python 3.10, ABI filters `arm64-v8a` and `armeabi-v7a`.
- `android/app/src/main/java/com/meraj/jupyternotebook/MainActivity.java`: existing WebView, local Python startup, storage/file bridges, and Android Back handling.
- `jupyter.py`: existing Flask `/run` and `/run-sql` routes.
- `.github/workflows/build-apk.yml`: Java 17, Python 3.10, Gradle 8.13, debug APK workflow.

No production source files or build configuration have been changed on this branch. Only this implementation/research document is being updated until the native feasibility proof works.

## Verified official documentation (2026-11-13)

- Chaquopy's current standard-library support list explicitly marks `tkinter` and `turtle` unsupported because the runtime does not include the required libraries. This confirms that adding a PyPI package is not the fix.
- Python's Android platform documentation / PEP 738 explains that Tkinter would require an Android build of Tk itself; it is not part of the officially supported Android standard-library set.
- AndroWish's official release page identifies the 2024 release (2024-03-06) as Tcl/Tk 8.6.10 + patched SDL 2.0.6. Its documentation describes its Java Activity/JNI/native-library architecture and says its assets and modified Java glue can be reused by other apps; it also points to the `hellotcltk` demo.
- These sources support a Tcl/Tk Android port as a candidate, but do not establish binary compatibility with Chaquopy CPython 3.10.

References:
- Chaquopy Android docs: https://chaquo.com/chaquopy/doc/current/android.html
- Python Android platform / PEP 738: https://peps.python.org/pep-0738/
- AndroWish releases: https://androwish.org/home/wiki?name=Releases
- AndroWish architecture and reuse notes: https://androwish.org/home/raw/8999948f92969d6b3621412a8d617c5e47139ad4
- AndroWish source tree and architecture: https://androwish.org/home/dir

## Build decision for this iteration

Do not add `tkinter` to the Gradle pip list, do not change the Chaquopy Python version, and do not modify `MainActivity.java` yet. The missing deliverable is a tested Android CPython 3.10 `_tkinter` extension plus a compatible Tcl/Tk runtime and a viable Android event-loop/window integration. The next code change should follow only after the exact upstream source and build toolchain are pinned and an isolated arm64 proof-of-concept compiles.
