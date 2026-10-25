from flask import Flask, render_template, request, jsonify
import io
import contextlib
import ast
import base64
import os
import sqlite3
import threading
from pathlib import Path

import pandas as pd
import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams['axes.unicode_minus'] = False
matplotlib.rcParams['font.family'] = 'sans-serif'
matplotlib.rcParams['font.sans-serif'] = ['DejaVu Sans']
import matplotlib.pyplot as plt
import seaborn as sns
from waitress import serve

plt.show = lambda *args, **kwargs: None
app = Flask(__name__)

# Keep the SQL database in a writable, persistent app/user data directory.
DATA_DIR = Path(os.environ.get("NICECODING_DATA_DIR", Path.home() / "NiceCoding" / "data"))
DB_DIR = DATA_DIR / "databases"
DB_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_DB = DB_DIR / "nicecoding.sqlite3"
# Create the default database file on first launch so it appears in SHOW DATABASES.
DEFAULT_DB.touch(exist_ok=True)
CURRENT_DB = DEFAULT_DB
SQL_LOCK = threading.RLock()


def connect_sqlite():
    """Connect Python cells to the currently selected notebook database."""
    with SQL_LOCK:
        path = CURRENT_DB
    conn = sqlite3.connect(str(path), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


cells_globals = {
    "pd": pd,
    "plt": plt,
    "sns": sns,
    "show": lambda *args, **kwargs: None,
    "sqlite3": sqlite3,
    "SQLITE_DB_PATH": str(DEFAULT_DB),
    "connect_sqlite": connect_sqlite,
}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/run", methods=["POST"])
def run_code():
    payload = request.get_json(silent=True) or {}
    code = str(payload.get("code", "")).strip()
    output_capture = io.StringIO()
    html_output = ""
    final_val = ""
    if not code:
        return jsonify({"output": "", "html": "", "final_val": ""})

    try:
        with contextlib.redirect_stdout(output_capture), contextlib.redirect_stderr(output_capture):
            tree = ast.parse(code)
            last_node = tree.body[-1] if tree.body else None
            if isinstance(last_node, ast.Expr):
                if len(tree.body) > 1:
                    exec(compile(ast.Module(body=tree.body[:-1], type_ignores=[]), "<notebook-cell>", "exec"), cells_globals)
                result = eval(compile(ast.Expression(body=last_node.value), "<notebook-cell>", "eval"), cells_globals)
                if isinstance(result, (pd.DataFrame, pd.Series)):
                    df = result.to_frame() if isinstance(result, pd.Series) else result
                    html_output = df.to_html(classes="dataframe", border=0, justify="left", index=True)
                elif result is not None:
                    final_val = str(result)
            else:
                exec(code, cells_globals)

        if plt.get_fignums():
            img = io.BytesIO()
            plt.savefig(img, format="png", bbox_inches="tight", dpi=180)
            img.seek(0)
            img_base64 = base64.b64encode(img.getvalue()).decode("ascii")
            html_output += f'<img src="data:image/png;base64,{img_base64}" style="max-width:100%;height:auto;">'
            plt.close("all")
        output = output_capture.getvalue()
    except Exception as exc:
        output = f"{type(exc).__name__}: {exc}"
        plt.close("all")
    return jsonify({"output": output, "html": html_output, "final_val": final_val})


def _safe_database_path(name):
    name = str(name or "").strip().strip('"\'')
    if not name:
        raise ValueError("Database name is missing")
    # Only allow a filename, never a path supplied by a SQL cell.
    name = Path(name).name
    if not name.endswith((".db", ".sqlite", ".sqlite3")):
        name += ".sqlite3"
    return DB_DIR / name


def run_sql(code):
    """Execute one SQLite statement, with a few familiar notebook shortcuts."""
    global CURRENT_DB
    original = str(code or "").strip()
    if not original:
        return {"output": "", "columns": [], "rows": []}

    lowered = original.lower().rstrip(";").strip()
    with SQL_LOCK:
        try:
            if lowered == "show databases":
                files = sorted(p.name for p in DB_DIR.iterdir() if p.is_file() and p.suffix.lower() in {".db", ".sqlite", ".sqlite3"})
                return {"output": f"{len(files)} database(s) found", "columns": ["Database Name"], "rows": [{"Database Name": name} for name in files]}

            if lowered == "show tables":
                conn = sqlite3.connect(str(CURRENT_DB), timeout=10)
                try:
                    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
                finally:
                    conn.close()
                return {"output": f"{len(rows)} table(s) found", "columns": ["Table Name"], "rows": [{"Table Name": row[0]} for row in rows]}

            if lowered.startswith("use "):
                requested = original[4:].strip().rstrip(";").strip()
                path = _safe_database_path(requested)
                path.parent.mkdir(parents=True, exist_ok=True)
                # Opening a SQLite database creates it if it does not exist.
                conn = sqlite3.connect(str(path), timeout=10)
                conn.close()
                CURRENT_DB = path
                cells_globals["SQLITE_DB_PATH"] = str(path)
                return {"output": f"Switched to database: {path.name}", "columns": [], "rows": []}

            conn = sqlite3.connect(str(CURRENT_DB), timeout=10)
            try:
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA busy_timeout=5000")
                cur = conn.cursor()
                cur.execute(original)
                if cur.description:
                    rows = [dict(row) for row in cur.fetchall()]
                    columns = [item[0] for item in cur.description]
                    return {"output": f"{len(rows)} row(s) returned", "columns": columns, "rows": rows}
                conn.commit()
                return {"output": f"Query executed successfully. Rows affected: {cur.rowcount if cur.rowcount >= 0 else 0}", "columns": [], "rows": []}
            finally:
                conn.close()
        except Exception as exc:
            return {"output": f"{type(exc).__name__}: {exc}", "columns": [], "rows": [], "error": True}


@app.route("/run_sql", methods=["POST"])
def run_sql_route():
    payload = request.get_json(silent=True) or {}
    return jsonify(run_sql(payload.get("code", "")))


@app.route("/import_sqlite", methods=["POST"])
def import_sqlite_database():
    """Import a real SQLite database file into NiceCoding's app database folder."""
    global CURRENT_DB
    upload = request.files.get("database")
    if upload is None or not upload.filename:
        return jsonify({"ok": False, "error": "Choose a .db, .sqlite, or .sqlite3 file first."}), 400

    filename = Path(upload.filename).name
    suffix = Path(filename).suffix.lower()
    if suffix not in {".db", ".sqlite", ".sqlite3"}:
        return jsonify({"ok": False, "error": "Unsupported file type. Select a .db, .sqlite, or .sqlite3 file."}), 400

    # Normalize the filename and avoid silently overwriting an existing database.
    safe_stem = Path(filename).stem.strip() or "imported_database"
    safe_stem = "".join(ch for ch in safe_stem if ch.isalnum() or ch in " _-").strip(" .") or "imported_database"
    target = DB_DIR / f"{safe_stem}{suffix}"
    with SQL_LOCK:
        if target.exists():
            counter = 1
            while (DB_DIR / f"{safe_stem}_imported_{counter}{suffix}").exists():
                counter += 1
            target = DB_DIR / f"{safe_stem}_imported_{counter}{suffix}"

        temp_path = None
        try:
            import tempfile
            with tempfile.NamedTemporaryFile(prefix="nicecoding_import_", suffix=suffix, dir=str(DB_DIR), delete=False) as temp:
                temp_path = Path(temp.name)
                upload.save(temp)

            with temp_path.open("rb") as stream:
                header = stream.read(16)
            if header != b"SQLite format 3\x00":
                raise ValueError("This file is not a valid SQLite database (SQLite header is missing).")

            # quick_check catches corrupt/incomplete database files before importing.
            check = sqlite3.connect(str(temp_path), timeout=10)
            try:
                result = check.execute("PRAGMA quick_check").fetchone()
                if not result or result[0] != "ok":
                    raise ValueError("SQLite integrity check failed; the database was not imported.")
            finally:
                check.close()

            temp_path.replace(target)
            CURRENT_DB = target
            cells_globals["SQLITE_DB_PATH"] = str(target)
            return jsonify({"ok": True, "database": target.name, "directory": str(DB_DIR), "message": f"Imported and selected {target.name}"})
        except Exception as exc:
            if temp_path is not None:
                try:
                    temp_path.unlink(missing_ok=True)
                except Exception:
                    pass
            return jsonify({"ok": False, "error": str(exc)}), 400


@app.route("/databases", methods=["GET"])
def list_databases():
    with SQL_LOCK:
        names = sorted(p.name for p in DB_DIR.iterdir() if p.is_file() and p.suffix.lower() in {".db", ".sqlite", ".sqlite3"})
        return jsonify({"current": CURRENT_DB.name, "databases": names, "directory": str(DB_DIR)})


def start_server():
    """Start the local Flask/Waitress server (also called by the Android host)."""
    serve(app, host="127.0.0.1", port=8000, threads=8)


if __name__ == "__main__":
    print("\nNiceCoding local server: http://127.0.0.1:8000\n")
    start_server()
