# NiceCoding — Integrated Notebook + Web Coding APK

This update keeps the **Jupyter-style notebook as the main screen** and integrates SQLite3 SQL cells and a separate HTML/CSS/JavaScript workspace into the same NiceCoding APK.

## Main interface

- **Jupyter Notebook (default screen):** Python and SQL/SQLite3 cells can be mixed in the same notebook. Choose `Python` or `SQL / SQLite3` from each cell's language selector and press that cell's Run button.
- **Python Editor:** A standalone Python editor with Run, Open `.py`, and Save `.py` controls.
- **HTML / CSS / JavaScript:** Three connected CodeMirror editors. `Run All` combines them into one offline preview. HTML, CSS, and JS files can be opened and saved separately.
- **Jupyter-like controls preserved:** File menu, theme toggle, add/move/delete cell, output visibility, output PNG download, keyboard symbol toolbar, notebook Open/Save, and output area.
- **Notebook formats:** Saves standard `.ipynb` files with NiceCoding cell-language metadata, and can also save/open NiceCoding `.json` notebooks. Older JSON arrays of cell strings remain supported.

## SQLite3 integration

- The SQL cell calls the local `/run_sql` endpoint in the same Flask application; there is no separate SQLite notebook screen.
- The default database is created automatically at `~/NiceCoding/data/databases/nicecoding.sqlite3` (inside the app's writable home directory on Android).
- Supported SQLite statements include `CREATE TABLE`, `INSERT`, `UPDATE`, `DELETE`, `SELECT`, `PRAGMA`, and other single statements supported by SQLite.
- Convenience commands `SHOW TABLES`, `SHOW DATABASES`, and `USE database_name` are also supported.
- Use **File → Import SQLite Database** to import an existing `.db`, `.sqlite`, or `.sqlite3` file from the device file picker. NiceCoding checks the SQLite header and integrity before accepting it, avoids overwriting an existing database, and selects the imported database for SQL cells and `connect_sqlite()`.
- Python cells can connect to the currently selected database with `connect_sqlite()` or use the `SQLITE_DB_PATH` variable. The `sqlite3` module is included in Python's standard library.
- SQL results are displayed as tables inside the same notebook cell output.

## Android app entry point

The Android `MainActivity.java` starts the bundled Chaquopy Python server (`android_server.py`) and loads `http://127.0.0.1:8000/` in a WebView. Flask templates and static assets are copied under `android/app/src/main/python/` so they are bundled with the APK. The native JavaScript bridge saves notebook/code/output downloads into `Downloads/NiceCoding` on Android 10+; on older Android versions it saves to the app-specific Downloads directory.

The `INTERNET` Android permission is retained only because the app's local WebView needs to connect to the loopback Flask server. The code is designed to run locally and does not configure a remote backend. Web preview scripts should use local resources for offline use.

## Build with GitHub Actions

1. Extract this ZIP and upload the **contents** of the folder to the repository root (do not add an extra nested project folder).
2. Keep `.github/workflows/build-apk.yml` and the `android/` directory at repository root.
3. In GitHub, open **Actions** and run **Build NiceCoding APK**, or push to `main`/`master`.
4. Download the `nicecoding-v1.0.2-debug-apk` artifact and extract `app-debug.apk`.

The first GitHub Actions build requires internet to download Gradle, Android SDK components, and Chaquopy package wheels. The installed app's notebook and bundled Python environment run locally. Package compatibility and on-device behavior must still be confirmed by a successful build and testing on the target phone.

## Validation performed for this source update

- Python files pass `py_compile`.
- The notebook's inline JavaScript and the local web-editor syntax-mode JavaScript pass Node.js syntax checks.
- This environment does not have the project's Python dependencies or Android SDK/Gradle build dependencies installed, so a complete APK build was not run here. Use the GitHub Actions workflow to confirm the Android build.
