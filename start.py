"""
Master Launcher for AI Equity Research Generator (FastAPI Backend + React Frontend)
===================================================================================

Run:
    python start.py
"""

import os
import subprocess
import sys
import webbrowser
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
FRONTEND_DIR = HERE / "frontend"
FRONTEND_DIST = FRONTEND_DIR / "dist"

def main():
    env = os.environ.copy()
    
    # Auto-activate venv by restarting the script using the venv's python executable
    if sys.prefix == sys.base_prefix:
        venv_python = HERE / "venv" / "Scripts" / "python.exe" if sys.platform == "win32" else HERE / "venv" / "bin" / "python"
        if venv_python.exists():
            print(f"🔄 Automatically activating virtual environment...")
            sys.exit(subprocess.run([str(venv_python)] + sys.argv, env=env).returncode)
        else:
            print("⚠️ Virtual environment not found. Please create one with 'python -m venv venv'.")



    # Build React frontend if dist does not exist
    if not FRONTEND_DIST.exists():
        print("🔨 Building React frontend production bundle...")
        subprocess.run(["npm", "run", "build"], cwd=str(FRONTEND_DIR), shell=True, check=True)

    # Free port 8000 if previously occupied
    try:
        if sys.platform == "win32":
            cmd = "Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"
            subprocess.run(["powershell", "-Command", cmd], capture_output=True)
    except Exception:
        pass

    print("🚀 Starting FastAPI server hosting React Frontend at http://localhost:8000...")
    
    # Auto open browser after a brief delay
    time.sleep(1.0)
    webbrowser.open("http://localhost:8000")

    # Run uvicorn server
    subprocess.run(
        [sys.executable, "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"],
        cwd=str(HERE),
        env=env
    )


if __name__ == "__main__":
    main()
