from flask import Flask, render_template, request, jsonify
import io
import contextlib
import pandas as pd
from waitress import serve
import ast
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams['axes.unicode_minus'] = False
matplotlib.rcParams['font.family'] = 'sans-serif'
matplotlib.rcParams['font.sans-serif'] = ['DejaVu Sans']


import matplotlib.pyplot as plt
import seaborn as sns
import base64
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


# Persistent SQLite SQL workspace. Multiple statements are supported per cell.
import sqlite3 as _sqlite3
import html as _html_escape
_SQLITE_DB_LOCK = threading.RLock() if "threading" in globals() else __import__("threading").RLock()

def _nicecoding_sqlite_db_path():
    private_files = Path("/data/data/com.meraj.jupyternotebook/files")
    candidates = []
    # Use Android app-private storage only when it is already present; desktop runs
    # should keep their database alongside the project instead of creating /data paths.
    if private_files.is_dir():
        candidates.append(private_files / "NiceCoding" / "sqlite")
    candidates.append(Path(__file__).resolve().parent / "NiceCodingSQLite")
    for folder in candidates:
        try:
            folder.mkdir(parents=True, exist_ok=True)
            probe = folder / ".write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            return folder / "nicecoding.sqlite3"
        except Exception:
            continue
    raise OSError("Cannot create a writable SQLite database folder")

def _split_sql_statements(script):
    """Split SQL at semicolons outside strings, quoted identifiers and comments."""
    statements, start, i = [], 0, 0
    quote = None
    line_comment = False
    block_comment = False
    n = len(script)
    while i < n:
        ch = script[i]
        nxt = script[i + 1] if i + 1 < n else ""
        if line_comment:
            if ch in "\r\n": line_comment = False
            i += 1; continue
        if block_comment:
            if ch == "*" and nxt == "/": block_comment = False; i += 2; continue
            i += 1; continue
        if quote:
            if quote == "]":
                if ch == "]": quote = None
            elif ch == quote:
                # SQL escapes quote characters by doubling them ('' or "").
                if nxt == quote: i += 2; continue
                quote = None
            i += 1; continue
        if ch == "-" and nxt == "-": line_comment = True; i += 2; continue
        if ch == "/" and nxt == "*": block_comment = True; i += 2; continue
        if ch in ("'", '"', "`", "["):
            quote = "]" if ch == "[" else ch
            i += 1; continue
        if ch == ";":
            part = script[start:i + 1].strip()
            if part and part != ";": statements.append(part)
            start = i + 1
        i += 1
    tail = script[start:].strip()
    if tail and tail != ";": statements.append(tail)
    return statements

def _sql_result_table(columns, rows):
    parts = ['<div style="overflow:auto;max-width:100%"><table class="dataframe" border="0"><thead><tr>']
    parts.extend('<th>' + _html_escape.escape(str(col)) + '</th>' for col in columns)
    parts.append('</tr></thead><tbody>')
    for row in rows:
        parts.append('<tr>')
        parts.extend('<td>' + _html_escape.escape("NULL" if value is None else str(value)) + '</td>' for value in row)
        parts.append('</tr>')
    parts.append('</tbody></table></div>')
    return ''.join(parts)

@app.route("/run-sql", methods=["POST"])
def run_sql_query():
    payload = request.get_json(silent=True) or {}
    sql = str(payload.get("code", "")).strip()
    if not sql:
        return jsonify({"ok": True, "output": "", "html": "", "final_val": ""})
    statements = _split_sql_statements(sql)
    if not statements:
        return jsonify({"ok": True, "output": "No SQL statement to execute.", "html": "", "final_val": ""})
    db_path = _nicecoding_sqlite_db_path()
    try:
        messages, html_parts = [], []
        with _SQLITE_DB_LOCK:
            with _sqlite3.connect(str(db_path), timeout=15) as connection:
                connection.row_factory = _sqlite3.Row
                for index, statement in enumerate(statements, start=1):
                    cursor = connection.execute(statement)
                    if cursor.description:
                        columns = [item[0] for item in cursor.description]
                        rows = cursor.fetchall()
                        messages.append(f"Statement {index}: {len(rows)} row(s) returned")
                        html_parts.append(f'<div style="margin:8px 0"><div style="font-weight:600;margin-bottom:5px">Result {index}</div>{_sql_result_table(columns, rows)}</div>')
                    else:
                        affected = max(cursor.rowcount, 0)
                        kind = statement.lstrip().split(None, 1)[0].upper().rstrip(";") if statement.strip() else "SQL"
                        if kind in ("INSERT", "UPDATE", "DELETE", "REPLACE"):
                            msg = f"Statement {index}: Query OK · {affected} row(s) affected"
                            if cursor.lastrowid: msg += f" · last inserted row ID: {cursor.lastrowid}"
                        else:
                            msg = f"Statement {index}: Query OK · statement executed"
                        messages.append(msg)
        messages.append(f"Executed {len(statements)} SQL statement(s) · SQLite database: {db_path.name}")
        return jsonify({"ok": True, "output": "\n".join(messages), "html": "".join(html_parts), "final_val": ""})
    except Exception as exc:
        return jsonify({"ok": False, "output": "SQLite error: " + str(exc), "html": "", "final_val": ""})

if __name__ == "__main__":
    print("\nhttp://127.0.0.1:8000\n")
    serve(app, host="127.0.0.1", port=8000, threads=8)

