"""Debug wrapper - captures all output to file."""
import os
import sys
import traceback

# Redirect all output to file
log_path = os.path.join(os.path.dirname(__file__), "data", "debug.log")
os.makedirs(os.path.dirname(log_path), exist_ok=True)

class TeeWriter:
    def __init__(self, log_file, original):
        self.log_file = log_file
        self.original = original
    def write(self, text):
        self.log_file.write(text)
        self.log_file.flush()
        self.original.write(text)
    def flush(self):
        self.log_file.flush()

with open(log_path, "w", encoding="utf-8") as f:
    sys.stdout = TeeWriter(f, sys.stdout)
    sys.stderr = TeeWriter(f, sys.stderr)

    try:
        sys.path.insert(0, os.path.dirname(__file__))
        from gui.app import AmazonProductAIApp
        app = AmazonProductAIApp()
        app.mainloop()
    except Exception:
        f.write("\n\n=== FATAL ERROR ===\n")
        traceback.print_exc(file=f)
