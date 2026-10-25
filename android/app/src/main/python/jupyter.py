import sys
from flask import Flask, render_template, request, jsonify
import io
import os
from pathlib import Path
import contextlib
import pandas as pd

# Compatibility for joblib/pickle files created with NumPy 2.x.
# This app pins NumPy 1.23.x for compatibility with the Chaquopy/Pandas stack,
# where the internal package is named numpy.core rather than numpy._core.
# Alias the old/new module paths before user code calls joblib.load().
import sys as _sys
import importlib as _importlib
import numpy as _np
if not hasattr(_np, "_core"):
    _np._core = _np.core
    _sys.modules.setdefault("numpy._core", _np.core)
    # Pickles commonly refer to these NumPy 2.x module paths.
    for _submodule in (
        "multiarray", "numeric", "_multiarray_umath", "overrides",
        "umath", "numerictypes", "_dtype", "_type_aliases",
    ):
        try:
            _legacy_module = _importlib.import_module("numpy.core." + _submodule)
            _sys.modules.setdefault("numpy._core." + _submodule, _legacy_module)
        except Exception:
            # Not every internal module exists on every NumPy build.
            pass
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
import threading
import uuid
import builtins
import time
import traceback
import socket
import re
from contextlib import contextmanager
plt.show = lambda *args, **kwargs: None

# Network is opt-in per execution: ordinary local/data-science code cannot open
# outbound sockets. Code that explicitly uses a network-capable API (requests,
# socket, urllib, httpx, etc.) is allowed to connect. Loopback remains available
# for local services. This is an execution guard, not a sandbox for hostile code.
_NETWORK_API_RE = re.compile(
    r"\b(requests|socket|urllib|httpx|aiohttp|http\.client|ftplib|smtplib|"
    r"websocket|websockets|paramiko|yfinance|praw|openai|boto3|firebase_admin|"
    r"urllib3|curl_cffi|feedparser|discord|telegram|wikipedia|yahooquery|"
    r"googleapiclient|selenium|playwright)\b"
)
_network_guard_lock = threading.RLock()

@contextmanager
def _network_policy(code):
    # Serialize code execution while the process-wide socket hook is installed.
    with _network_guard_lock:
        if _NETWORK_API_RE.search(code or ""):
            yield True
            return
        original_connect = socket.socket.connect
        def guarded_connect(sock, address):
            host = address[0] if isinstance(address, tuple) and address else address
            host_text = str(host).lower().strip("[]")
            is_loopback = host_text in ("localhost", "127.0.0.1", "::1")
            if not is_loopback:
                raise PermissionError(
                    "Internet access is blocked for this run. Use a network library "
                    "such as requests/socket/urllib explicitly in your code to allow it."
                )
            return original_connect(sock, address)
        socket.socket.connect = guarded_connect
        try:
            yield False
        finally:
            socket.socket.connect = original_connect

app = Flask(__name__)

# Automatic local-module discovery for the NiceCoding Python editor.
# Import resolution order: active working directory first, then the NiceCoding
# project directories (Python, Notebook, HTML_CSS, and nested subfolders).
# This is configured by the APK itself, so users do not need to edit sys.path
# or add import boilerplate to every script.
_IMPORT_PATH_LOCK = threading.RLock()

def _configure_local_import_paths():
    try:
        cwd = Path.cwd().resolve()
    except Exception:
        cwd = Path(__file__).resolve().parent

    roots = []
    # Find a NiceCoding project root from the active folder or this server file.
    for start in (cwd, Path(__file__).resolve().parent):
        for parent in (start, *start.parents):
            if parent.name.lower() == "nicecoding" and parent.is_dir():
                roots.append(parent)
                break

    # App-private project folder used by the NiceCoding Android app.
    private_root = Path("/data/data/com.meraj.jupyternotebook/files/NiceCoding")
    if private_root.is_dir():
        roots.append(private_root)

    # Shared-storage project folder, when the user keeps scripts in Downloads.
    for shared_root in (
        Path("/storage/emulated/0/Download/NiceCoding"),
        Path("/storage/emulated/0/Downloads/NiceCoding"),
    ):
        if shared_root.is_dir():
            roots.append(shared_root)

    # Deduplicate roots while preserving their discovery order.
    unique_roots = []
    seen_roots = set()
    for root in roots:
        try:
            root = root.resolve()
            key = str(root)
            if key not in seen_roots:
                seen_roots.add(key)
                unique_roots.append(root)
        except Exception:
            pass

    # Current directory must win over every other local project directory.
    ordered_dirs = [cwd]
    for root in unique_roots:
        ordered_dirs.append(root)
        try:
            for dirpath, dirnames, filenames in os.walk(str(root)):
                # Avoid walking cache/version-control/build directories.
                dirnames[:] = [d for d in dirnames if d not in {
                    ".git", "__pycache__", ".venv", "venv", "build", ".gradle"
                }]
                ordered_dirs.append(Path(dirpath))
        except Exception:
            continue

    unique_dirs = []
    seen_dirs = set()
    for directory in ordered_dirs:
        try:
            directory = directory.resolve()
            key = str(directory)
            if directory.is_dir() and key not in seen_dirs:
                seen_dirs.add(key)
                unique_dirs.append(key)
        except Exception:
            pass

    # Keep current directory first, then project folders; preserve system paths.
    with _IMPORT_PATH_LOCK:
        current_paths = [p for p in sys.path if isinstance(p, str)]
        non_project_paths = [p for p in current_paths if p not in seen_dirs]
        sys.path[:] = unique_dirs + non_project_paths

    return str(cwd)

# Install the common import paths at server startup as well as before each run.
try:
    _configure_local_import_paths()
except Exception:
    pass

# The user may import a local data folder from Android's Storage Access Framework.
# Relative reads such as pd.read_csv("housing.csv") then resolve in that folder.
_workspace_dir = Path(__file__).resolve().parent
_workspace_lock = threading.RLock()

def set_workspace_dir(path):
    global _workspace_dir
    candidate = Path(str(path)).resolve()
    if not candidate.exists() or not candidate.is_dir():
        raise ValueError("Workspace folder does not exist")
    with _workspace_lock:
        _workspace_dir = candidate
        os.chdir(str(candidate))
    return str(candidate)

cells_globals = {
    "pd": pd,
    "plt": plt,
    "sns": sns,
    'show': lambda *args, **kwargs: None

}


# Standalone coding-page execution jobs. Each job runs on a background thread so
# input() can pause safely while the WebView displays a prompt and submits a reply.
_code_jobs = {}
_code_jobs_lock = threading.Lock()
_code_globals = {"pd": pd, "plt": plt, "sns": sns, "__name__": "__main__"}

class _JobOutput:
    """Captured output stream compatible with print() and Uvicorn loggers."""
    encoding = "utf-8"
    errors = "replace"

    def __init__(self, job): self.job = job
    def write(self, value):
        if value:
            with self.job["condition"]:
                self.job["output"] += str(value)
                self.job["condition"].notify_all()
        return len(value) if value else 0
    def flush(self): pass
    def isatty(self): return False
    def writable(self): return True

class _JobInput:
    def __init__(self, job): self.job = job
    def __call__(self, prompt=""):
        with self.job["condition"]:
            self.job["input_prompt"] = str(prompt)
            self.job["input_value"] = None
            self.job["input_ready"] = False
            self.job["condition"].notify_all()
            while not self.job["input_ready"] and not self.job["cancelled"]:
                self.job["condition"].wait(timeout=0.5)
            if self.job["cancelled"]:
                raise KeyboardInterrupt("Execution cancelled")
            value = self.job["input_value"]
            self.job["input_prompt"] = None
            self.job["input_ready"] = False
            return value

def _run_code_job(job, code):
    out = _JobOutput(job)
    local_builtins = dict(vars(builtins))
    local_builtins["input"] = _JobInput(job)
    # Keep variables across runs, as in an interactive Python console.
    _code_globals["__builtins__"] = local_builtins
    try:
        _configure_local_import_paths()
        with _network_policy(code), contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            exec(compile(code, "<coding-page>", "exec"), _code_globals, _code_globals)
    except KeyboardInterrupt:
        out.write("\nExecution cancelled.\n")
    except BaseException:
        out.write(traceback.format_exc())
    finally:
        with job["condition"]:
            job["running"] = False
            job["done"] = True
            job["input_prompt"] = None
            job["condition"].notify_all()

@app.route("/code/start", methods=["POST"])
def code_start():
    payload = request.get_json(silent=True) or {}
    code = str(payload.get("code", ""))
    if not code.strip(): return jsonify({"error": "Enter Python code first."}), 400
    job_id = uuid.uuid4().hex
    job = {"condition": threading.Condition(), "output": "", "input_prompt": None,
           "input_value": None, "input_ready": False, "running": True,
           "done": False, "cancelled": False, "created": time.time()}
    with _code_jobs_lock:
        # Avoid unbounded memory use in long-lived sessions.
        for old_id in list(_code_jobs):
            if _code_jobs[old_id].get("done") and time.time() - _code_jobs[old_id].get("created", 0) > 1800:
                _code_jobs.pop(old_id, None)
        _code_jobs[job_id] = job
    threading.Thread(target=_run_code_job, args=(job, code), daemon=True, name="python-console-" + job_id[:8]).start()
    return jsonify({"job_id": job_id})

@app.route("/code/status/<job_id>", methods=["GET"])
def code_status(job_id):
    with _code_jobs_lock: job = _code_jobs.get(job_id)
    if not job: return jsonify({"error": "Execution session not found."}), 404
    with job["condition"]:
        return jsonify({"output": job["output"], "input_prompt": job["input_prompt"],
                        "running": job["running"], "done": job["done"]})

@app.route("/code/input/<job_id>", methods=["POST"])
def code_input(job_id):
    with _code_jobs_lock: job = _code_jobs.get(job_id)
    if not job: return jsonify({"error": "Execution session not found."}), 404
    payload = request.get_json(silent=True) or {}
    with job["condition"]:
        if job["input_prompt"] is None: return jsonify({"error": "No input is currently requested."}), 409
        job["input_value"] = str(payload.get("value", ""))
        job["input_ready"] = True
        job["output"] += str(payload.get("value", "")) + "\n"
        job["condition"].notify_all()
    return jsonify({"ok": True})

@app.route("/code/cancel/<job_id>", methods=["POST"])
def code_cancel(job_id):
    with _code_jobs_lock: job = _code_jobs.get(job_id)
    if not job: return jsonify({"ok": False}), 404
    with job["condition"]:
        job["cancelled"] = True
        job["condition"].notify_all()
    return jsonify({"ok": True})

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
        # The working directory is process-global in Python. Re-apply the selected
        # notebook workspace immediately before each cell and hold the workspace
        # lock during execution so relative paths such as pd.read_csv("data.csv")
        # resolve against the synchronized NiceCoding/Notebook directory.
        with _workspace_lock:
            os.chdir(str(_workspace_dir))
            _configure_local_import_paths()
            with _network_policy(code), contextlib.redirect_stdout(output_capture), contextlib.redirect_stderr(output_capture):
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
                        html_parts.append(_sql_result_table(columns, rows))
                    else:
                        # Successful non-SELECT statements intentionally produce no explanatory text.
                        pass
        return jsonify({"ok": True, "output": "", "html": "".join(html_parts), "final_val": ""})
    except Exception as exc:
        return jsonify({"ok": False, "output": "SQLite error: " + str(exc), "html": "", "final_val": ""})

if __name__ == "__main__":
    print("\nhttp://127.0.0.1:8000\n")
    serve(app, host="127.0.0.1", port=8000, threads=8)

