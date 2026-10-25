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

if __name__ == "__main__":
    print("\nhttp://127.0.0.1:8000\n")
    serve(app, host="127.0.0.1", port=8000, threads=8)



# HTML/CSS/JavaScript editor workspace: saved files share one folder.
from pathlib import Path as _Path
_WEB_WORKSPACE = _Path(__file__).resolve().parent / "web_workspace"
_WEB_WORKSPACE.mkdir(parents=True, exist_ok=True)
_WEB_DEFAULTS = {
 "index.html": "<!doctype html>\\n<html>\\n<head><meta charset=\\\"utf-8\\\"><title>My page</title></head>\\n<body><h1>Hello, world!</h1><button id=\\\"helloBtn\\\">Click me</button></body>\\n</html>\\n",
 "style.css": "body { font-family: Arial, sans-serif; padding: 24px; }\\nh1 { color: #2878d0; }\\n",
 "script.js": "document.getElementById('helloBtn')?.addEventListener('click', () => alert('HTML, CSS and JavaScript are connected!'));\\n"
}
@app.route("/web-editor")
def web_editor_page():
 return render_template("web_editor.html")
@app.route("/api/web-files", methods=["GET","POST"])
def web_files_api():
 if request.method == "GET":
  values={}
  for key,fn in (("html","index.html"),("css","style.css"),("js","script.js")):
   p=_WEB_WORKSPACE/fn
   if not p.exists(): p.write_text(_WEB_DEFAULTS[fn],encoding="utf-8")
   values[key]=p.read_text(encoding="utf-8")
  return jsonify({"ok":True,**values})
 try:
  data=request.get_json(silent=True) or {}
  for key,fn in (("html","index.html"),("css","style.css"),("js","script.js")):
   val=data.get(key,"")
   if not isinstance(val,str): return jsonify({"ok":False,"error":"Invalid content"}),400
   (_WEB_WORKSPACE/fn).write_text(val,encoding="utf-8")
  return jsonify({"ok":True})
 except Exception as exc: return jsonify({"ok":False,"error":str(exc)}),500
