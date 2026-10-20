"""Run this code in the Android Jupyter notebook to capture the live Tkinter error.
This is a diagnostic test, not a Tkinter implementation.
"""
import sys, platform, traceback, importlib.util
print("=== ANDROID PYTHON DIAGNOSTIC ===")
print("Python:", sys.version)
print("Platform:", platform.platform())
print("Executable:", sys.executable)
print("tkinter spec:", importlib.util.find_spec("tkinter"))
try:
    import tkinter as tk
    print("tkinter imported:", getattr(tk, "TkVersion", "version unknown"))
    root = tk.Tk()
    root.title("Tkinter live test")
    tk.Label(root, text="Tkinter window started").pack(padx=20, pady=10)
    tk.Button(root, text="Close", command=root.destroy).pack(pady=10)
    root.mainloop()
    print("Tkinter mainloop finished")
except BaseException as exc:
    print("TKINTER_TEST_FAILED:", type(exc).__name__, str(exc))
    traceback.print_exc()
