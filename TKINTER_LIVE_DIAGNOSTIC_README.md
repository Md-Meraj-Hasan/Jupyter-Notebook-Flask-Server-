# Tkinter live diagnostic build (v1.0.2)

This ZIP is based on the existing Jupyter Notebook Android app. It preserves the existing Chaquopy/Flask/WebView app and adds a repeatable live diagnostic for the actual `tkinter` import/runtime error.

## Build and install
1. Upload the contents of this folder to the repository root (keep `.github/` and `android/` at root).
2. GitHub → Actions → **Build Jupyter Notebook Tkinter Live Diagnostic APK** → Run workflow.
3. Download artifact **jupyter-tkinter-live-diagnostic-v1.0.2-debug-apk**, extract `app-debug.apk`, install it.
4. Open the notebook and run the code from `TKINTER_LIVE_DIAGNOSTIC.py` (copy/paste it into a Python cell).
5. Send a screenshot of the full output/error, or copy the traceback text.

## Important
This is a **diagnostic build**, not a claim that Tkinter has been implemented. The current Chaquopy Python runtime does not bundle Android-compatible `_tkinter`/Tcl/Tk. The test intentionally attempts the real `import tkinter` and prints the exact exception and runtime details. Do not expect a Tkinter window to work until native Tcl/Tk, `_tkinter`, and Android window/event integration are built and verified.

The diagnostic file is also available at `TKINTER_LIVE_DIAGNOSTIC.py`. It does not change or remove existing notebook functionality.
