"""Launch MarketLens Web Application."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    reload = os.environ.get("MLENS_RELOAD", "false").lower() == "true"
    workers = int(os.environ.get("MLENS_WORKERS", "1"))
    print(f"MarketLens Web starting on http://localhost:{port}")
    uvicorn.run("web.app:app", host="0.0.0.0", port=port, reload=reload, workers=workers)
