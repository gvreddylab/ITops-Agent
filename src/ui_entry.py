"""Entry point for `rag-ui` CLI command."""
import subprocess
import sys
from pathlib import Path

def main():
    ui_file = Path(__file__).resolve().parents[1] / "ui_streamlit.py"
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", str(ui_file),
         "--server.address", "127.0.0.1",
         "--server.port", "8501",
         "--browser.gatherUsageStats", "false"],
        check=True,
    )
