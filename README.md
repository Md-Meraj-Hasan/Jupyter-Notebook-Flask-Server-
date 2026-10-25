# NiceCoding for Android

This project packages the existing Flask + CodeMirror notebook UI into an Android WebView and runs the Python backend locally using Chaquopy. It is designed to work without an external server or internet connection after installation.

## What is preserved
- Existing `templates/index.html` and `static/` assets (CodeMirror, themes, notebook controls).
- Existing `/run` Python execution logic in `jupyter.py`.
- Pandas DataFrame output and Matplotlib/Seaborn plotting (Agg backend).
- Bundled CSV datasets.
- Offline bundled numerical and data-science packages: NumPy, Pandas, SciPy, Matplotlib, Seaborn, Pillow.
- Offline bundled ML packages: scikit-learn, joblib, threadpoolctl, statsmodels 0.14.5 (plus its dependency `patsy`).
- Additional packages: SymPy, NetworkX, OpenPyXL, XlsxWriter, xlrd, Requests, BeautifulSoup4, python-dateutil, pytz, packaging, tqdm.
- Python 3.10 is selected to use current Android-compatible Chaquopy wheels, including scikit-learn.

## Build APK with GitHub Actions
1. Extract this ZIP.
2. Upload the contents to a GitHub repository (the `.github/workflows/build-apk.yml` file must be at the repository root).
3. Open **Actions** in GitHub.
4. Select **Build NiceCoding APK** and click **Run workflow** (or push to `main`/`master`).
5. Open the completed run, scroll to **Artifacts**, and download `offline-jupyter-notebook-debug-apk`.
6. Extract the artifact ZIP and install `app-debug.apk` on Android.

## Important notes
- The first GitHub Actions build downloads Android/Gradle/Python package dependencies, so the build runner needs internet. The installed app itself runs its Python engine and notebook UI locally.
- This is a debug APK for testing. A release APK should be signed before distribution.
- The APK bundles the packages listed in `android/app/build.gradle`; it cannot contain literally every Python package. Libraries which need unsupported native binaries (for example, standard desktop TensorFlow/PyTorch or some boosting packages) are not included in this build.
- The larger scientific packages can make the APK large and the first GitHub Actions build slower. The build runner needs internet to download dependencies, but the installed package set is intended to run offline.
- Chaquopy package compatibility and Android device behavior must be confirmed by a successful GitHub Actions build and on-device test. The original UI and Python endpoint are reused, but Android file-picker/download behavior can differ from a desktop browser.
- The app WebView only allows navigation to its own `127.0.0.1`/`localhost` notebook server. No remote backend is configured.


## ML/Data Science package compatibility note

This build uses Chaquopy Python 3.10 because its Android wheel repository includes SciPy and scikit-learn wheels for this Python version. The build pins a compatible set of NumPy, Pandas, SciPy, Matplotlib, Seaborn, scikit-learn, and statsmodels versions. `statsmodels==0.14.5` has an Android CPython 3.10 wheel in the Chaquopy package index.

Important: some older native Android wheels may not work on devices using 16 KB memory pages. This package set is aimed at broad compatibility with standard Android devices (including Android 12 and earlier); test on the target phone before relying on it.


### Important build note

The Android project is configured for Chaquopy Python 3.10. In GitHub Actions, `actions/setup-python@v5` installs Python 3.10 without pip caching (there is no requirements.txt or pyproject.toml). Gradle uses `buildPython("python")` so it does not depend on a `python3.10` executable alias. Upload the *contents* of this folder to the repository root, preserving `.github/workflows/` and `android/` paths. Do not upload this outer folder as an extra nested directory.

## Android file actions
- File → Open is wired to the Android system file picker through `WebChromeClient.onShowFileChooser`.
- Output PNG download and notebook JSON save use Android's native Create Document dialog through the `AndroidDownloads` JavaScript bridge.
- After building, test both actions on the target phone.


## HTML/CSS preview update (v1.0.4)
Notebook cells now have a language selector: Python, HTML, or CSS. Run on an HTML cell opens a sandboxed in-cell WebView-style iframe preview; CSS cells apply their styles to the latest non-empty HTML cell. Python cells continue using the existing Flask `/run` endpoint. Notebook `.ipynb` saving stores `custom_language` metadata for this app, and opening preserves it.


## v1.0.7 scrolling update
- Enabled vertical page scrolling for the Notebook and Coding workspace.
- Python and HTML/CSS CodeMirror editors expand with their content instead of being locked to a viewport-height box.
- Python output remains vertically scrollable in its output console.
- HTML/CSS preview iframe and its document allow vertical scrolling for long rendered pages.
- Preserved the existing workspace/menu and file extension logic from v1.0.6.

## Python execution network behavior

- The Android app retains the `INTERNET` permission so explicit network calls can work.
- During a Python run, outbound socket connections are blocked by default unless the code explicitly references a recognized network API such as `requests`, `socket`, `urllib`, `httpx`, or `aiohttp`.
- Loopback connections (`localhost`, `127.0.0.1`, `::1`) remain available for the app's local server.
- This is a convenience guard, not a security sandbox. Python code can bypass it, and libraries not recognized by the detector may need to be added to the network API list. Only run code you trust.


## v1.2.5 — Python Run and Output Toolbar Fix
- Python workspace hides HTML/CSS tabs and explicitly returns to Python editor mode.
- Run routing keeps HTML/CSS preview separate from Python execution.
- Output screen uses compact text labels (Back, Clear, Stop).
- Keyboard symbol toolbar is hidden while output/preview is open.


## NiceCoding shared storage (v1.3.8)
Open File → Setup Downloads/NiceCoding and choose the **Downloads** folder in Android system picker. The app creates `NiceCoding/Notebook`, `NiceCoding/Python`, and `NiceCoding/HTML_CSS` inside it. The app uses scoped Storage Access Framework access; it does not request broad storage permission. Notebook relative data files should be kept in `NiceCoding/Notebook`.


## NiceCoding first-run storage
On the first launch, Android opens its system folder picker so the user can grant persistent access to the Downloads folder. Select **Downloads** (not a child folder); the app creates `NiceCoding/Notebook`, `NiceCoding/Python`, and `NiceCoding/HTML_CSS` automatically. The persisted Storage Access Framework grant is reused on later launches. Notebook code execution refreshes files from `NiceCoding/Notebook` into the app's Python working directory before running, so relative paths such as `pd.read_csv("housing.csv")` work when the CSV is in that folder. Android requires this one-time system folder selection; an app cannot silently grant itself broad Downloads access.


## v1.4.3 — ML library and NumPy pickle compatibility
- Added `mlxtend==0.23.4` to the Chaquopy Python package list for the Android build.
- Added a startup compatibility alias for `numpy._core` pickle paths when loading joblib/pickle artifacts created under NumPy 2.x while this app uses NumPy 1.23.x.
- The `joblib` warning about `sem_open` means joblib uses serial execution on Android; it is a warning, not the cause of `ModuleNotFoundError`.
- This source update has not been validated by a GitHub Actions APK build or on-device model loading.
