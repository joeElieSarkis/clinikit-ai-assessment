"""Serve the built website and API together on the hosting provider's port."""
import os
from pathlib import Path

import uvicorn


def main():
    root = Path(__file__).resolve().parent
    if not (root / "frontend" / "dist" / "index.html").is_file():
        raise SystemExit("Build the interface first: npm --prefix frontend run build")
    try:
        port = int(os.getenv("PORT", "10000"))
    except ValueError:
        raise SystemExit("PORT must be a number between 1 and 65535") from None
    if not 1 <= port <= 65535:
        raise SystemExit("PORT must be a number between 1 and 65535")
    # Ephemeral sessions are process-local, so this demonstration uses one worker.
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=port, workers=1)


if __name__ == "__main__":
    main()
