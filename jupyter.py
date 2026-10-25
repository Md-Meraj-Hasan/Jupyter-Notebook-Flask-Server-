from flask import Flask, render_template, request, jsonify
import io
import contextlib
import pandas as pd
from waitress import serve
import ast
import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams['axes.unicode_minus'] = False
matplotlib.rcParams['font.family'] = 'sans-serif'
matplotlib.rcParams['font.sans-serif'] = ['DejaVu Sans']


import matplotlib.pyplot as plt
import seaborn as sns
import base64
import sqlite3
import threading
from pathlib import Path
from flask import send_from_directory
plt.show = lambda *args, **kwargs: None

app = Flask(__name__)

cells_globals = {
    "pd": pd,
    "plt": plt,
    "sns": sns,
    'show': lambda *args, **kwargs: None

}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/suggest", methods=["POST"])
@app.route("/suggest", methods=["POST"])

@app.route("/run", methods=["POST"])
def run_code():
    code = request.json.get("code","").strip()
    output_capture = io.StringIO()
    html_output = ""
    final_val = ""

    if not code:
        return jsonify({"output":"","html":"","final_val":""})

    try:
        with contextlib.redirect_stdout(output_capture), contextlib.redirect_stderr(output_capture):
            tree = ast.parse(code)
            last_node = tree.body[-1] if tree.body else None

            if isinstance(last_node, ast.Expr):
                if len(tree.body) > 1:
                    exec(compile(ast.Module(body=tree.body[:-1], type_ignores=[]), "<ast>", "exec"), cells_globals)
                
                result = eval(compile(ast.Expression(body=last_node.value), "<ast>", "eval"), cells_globals)

                if isinstance(result, (pd.DataFrame, pd.Series)):
                    df = result.to_frame() if isinstance(result, pd.Series) else result
                    # FIXED: Set index=True to show column names for Series/Index labels
                    html_output = df.to_html(
                        classes="dataframe",
                        border=0,
                        justify="left",
                        index=True 
                    )
                elif result is not None:
                    final_val = str(result)
            else:
                exec(code, cells_globals)

        if plt.get_fignums():
            img = io.BytesIO()
            plt.savefig(img, format="png", bbox_inches="tight",dpi=400)
            img.seek(0)
            img_base64 = base64.b64encode(img.getvalue()).decode()
            html_output += f'<img src="data:image/png;base64,{img_base64}" style="max-width:100%;">'
            plt.close("all")

        output = output_capture.getvalue()
    except Exception as e:
        output = str(e)

    return jsonify({"output": output, "html": html_output, "final_val": final_val})


# --- Additional independent workspaces (kept separate from the original notebook) ---
PROJECT_ROOT = Path(__file__).resolve().parent
SQLITE_DIR = PROJECT_ROOT / "sqlite3_page"
SQLITE_DB_DIR = SQLITE_DIR / "databases"
SQLITE_DB_DIR.mkdir(parents=True, exist_ok=True)
SQLITE_DEFAULT_DB = SQLITE_DB_DIR / "nicecoding.sqlite3"
SQLITE_LOCK = threading.RLock()
if not SQLITE_DEFAULT_DB.exists():
    with sqlite3.connect(str(SQLITE_DEFAULT_DB)) as _conn:
        _conn.execute("PRAGMA user_version=1")

@app.route("/sqlite3")
def sqlite3_notebook_page():
    return render_template("sqlite3/index.html")

@app.route("/sqlite3/assets/<path:asset>")
def sqlite3_assets(asset):
    return send_from_directory(str(SQLITE_DIR / "static"), asset)

@app.route("/webdev")
def webdev_page():
    return render_template("webdev/index.html")

@app.route("/sqlite3/run", methods=["POST"])
def sqlite3_run():
    payload = request.get_json(silent=True) or {}
    query = str(payload.get("code", "")).strip()
    if not query:
        return jsonify({"output": "Empty query", "columns": [], "rows": []})
    # Each SQL workspace has its own database folder and current-db marker.
    selected_file = SQLITE_DB_DIR / "_current_database.txt"
    try:
        selected = selected_file.read_text(encoding="utf-8").strip() if selected_file.exists() else SQLITE_DEFAULT_DB.name
    except Exception:
        selected = SQLITE_DEFAULT_DB.name
    if not selected or Path(selected).name != selected or not selected.lower().endswith((".db", ".sqlite", ".sqlite3")):
        selected = SQLITE_DEFAULT_DB.name
    db_path = SQLITE_DB_DIR / selected
    lower = query.lower().strip().rstrip(";")
    with SQLITE_LOCK:
        try:
            if lower == "show databases":
                files = sorted(f.name for f in SQLITE_DB_DIR.iterdir() if f.is_file() and f.suffix.lower() in (".db", ".sqlite", ".sqlite3"))
                return jsonify({"output": f"{len(files)} database(s) found", "columns": ["Database Name"], "rows": [{"Database Name": x} for x in files]})
            if lower.startswith("use "):
                name = query.split(None, 1)[1].strip().strip("`\"'")
                if not name.lower().endswith((".db", ".sqlite", ".sqlite3")):
                    name += ".db"
                if Path(name).name != name or name in (".", ".."):
                    return jsonify({"output": "Invalid database filename", "columns": [], "rows": []})
                target = SQLITE_DB_DIR / name
                with sqlite3.connect(str(target)) as _c:
                    _c.execute("PRAGMA user_version=1")
                selected_file.write_text(name, encoding="utf-8")
                return jsonify({"output": f"Switched to {name}", "columns": [], "rows": []})
            conn = sqlite3.connect(str(db_path), timeout=10)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA busy_timeout=5000")
            cur = conn.cursor()
            if lower == "show tables":
                cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
                rows = [dict(r) for r in cur.fetchall()]
                conn.close()
                return jsonify({"output": f"{len(rows)} table(s) found" if rows else "No Tables Found", "columns": ["name"], "rows": rows})
            if lower.startswith("describe ") or lower.startswith("desc "):
                table = query.split(None, 1)[1].strip().strip('`"')
                if not table.replace("_", "").isalnum():
                    conn.close(); return jsonify({"output": "Invalid table name", "columns": [], "rows": []})
                cur.execute(f"PRAGMA table_info('{table}')")
                rows = [dict(r) for r in cur.fetchall()]
                conn.close()
                return jsonify({"output": f"{len(rows)} column(s)", "columns": list(rows[0].keys()) if rows else [], "rows": rows})
            cur.execute(query)
            if cur.description:
                columns = [d[0] for d in cur.description]
                rows = [dict(r) for r in cur.fetchall()]
                conn.commit()
                conn.close()
                return jsonify({"output": f"{len(rows)} row(s) returned", "columns": columns, "rows": rows})
            affected = cur.rowcount
            conn.commit()
            conn.close()
            return jsonify({"output": f"Query executed successfully. Rows affected: {affected}", "columns": [], "rows": []})
        except Exception as exc:
            try: conn.close()
            except Exception: pass
            return jsonify({"output": f"SQLite error: {exc}", "columns": [], "rows": []}), 400

if __name__ == "__main__":
    print("\nhttp://127.0.0.1:8000\n")
    serve(app, host="127.0.0.1", port=8000, threads=8)

