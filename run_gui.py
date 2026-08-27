"""Entry point for Amazon Product Idea Generator AI GUI."""

import os
import subprocess
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).parent
VENV_PYTHON = PROJECT_DIR / "venv" / "Scripts" / "python.exe"


def _has_reportlab():
    try:
        import reportlab  # noqa: F401
        return True
    except ImportError:
        return False


def main():
    sys.path.insert(0, str(PROJECT_DIR))

    if not _has_reportlab() and VENV_PYTHON.exists():
        print(f"reportlab not found in {sys.executable}")
        print(f"Re-launching with venv Python: {VENV_PYTHON}")
        subprocess.call([str(VENV_PYTHON), str(PROJECT_DIR / "run_gui.py")])
        return

    from gui.app import main as app_main
    app_main()


if __name__ == "__main__":
    main()
