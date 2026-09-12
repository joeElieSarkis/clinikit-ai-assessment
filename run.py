"""Start both local development services with one command: python run.py."""
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    node = shutil.which("node")
    vite = ROOT / "frontend" / "node_modules" / "vite" / "bin" / "vite.js"
    if not node or not vite.exists():
        raise SystemExit("Install Node.js, then run npm ci in frontend/ first. See README.md.")
    processes = []
    try:
        processes.append(subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1", "--port", "8000"], cwd=ROOT))
        processes.append(subprocess.Popen([node, str(vite), "--host", "127.0.0.1", "--port", "5173", "--strictPort"], cwd=ROOT / "frontend"))
        print("\nReception: http://127.0.0.1:5173\nAPI docs: http://127.0.0.1:8000/docs\nPress Ctrl+C to stop both services.\n", flush=True)
        while all(process.poll() is None for process in processes):
            time.sleep(.5)
    except KeyboardInterrupt:
        pass
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
    if any(process.returncode not in (0, None, -15, 1) for process in processes):
        raise SystemExit("A service stopped. Check the messages above for the cause.")


if __name__ == "__main__":
    main()
