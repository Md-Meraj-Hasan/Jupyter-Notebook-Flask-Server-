# Offline Jupyter Notebook for Android

This project packages the existing Flask + CodeMirror notebook UI into an Android WebView and runs the Python backend locally using Chaquopy. It is designed to work without an external server or internet connection after installation.

## What is preserved
- Existing `templates/index.html` and `static/` assets (CodeMirror, themes, notebook controls).
- Existing `/run` Python execution logic in `jupyter.py`.
- Pandas DataFrame output and Matplotlib/Seaborn plotting (Agg backend).
- Bundled CSV datasets.
- Offline bundled numerical and data-science packages: NumPy, Pandas, SciPy, Matplotlib, Seaborn, Pillow.
- Offline bundled ML packages: scikit-learn, joblib, threadpoolctl.
- Additional packages: SymPy, NetworkX, OpenPyXL, XlsxWriter, xlrd, Requests, BeautifulSoup4, python-dateutil, pytz, packaging, tqdm.
- Python 3.10 is selected to use current Android-compatible Chaquopy wheels, including scikit-learn.

## Build APK with GitHub Actions
1. Extract this ZIP.
2. Upload the contents to a GitHub repository (the `.github/workflows/build-apk.yml` file must be at the repository root).
3. Open **Actions** in GitHub.
4. Select **Build Offline Jupyter Notebook APK** and click **Run workflow** (or push to `main`/`master`).
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

This build uses Chaquopy Python 3.10 because its Android wheel repository includes SciPy and scikit-learn wheels for this Python version. The build pins a compatible set of NumPy, Pandas, SciPy, Matplotlib, Seaborn, scikit-learn, and statsmodels versions.

Important: some older native Android wheels may not work on devices using 16 KB memory pages. This package set is aimed at broad compatibility with standard Android devices (including Android 12 and earlier); test on the target phone before relying on it.
