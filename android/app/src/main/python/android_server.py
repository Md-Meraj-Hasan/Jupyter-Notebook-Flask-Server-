"""Start the existing Flask notebook locally inside the Android app."""
import os
from pathlib import Path
from waitress import serve
from jupyter import app

# Keep relative dataset reads and Flask's templates/static paths rooted in this project.
PROJECT_DIR = Path(__file__).resolve().parent
try:
    os.chdir(str(PROJECT_DIR))
except Exception:
    pass


def start_server():
    # Blocking function; Android invokes it on a dedicated background thread.
    serve(app, host="127.0.0.1", port=8000, threads=4, _quiet=True)
