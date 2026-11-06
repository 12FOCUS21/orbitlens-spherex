"""Restaurar la demo local y arrancar un único proceso de servidor."""
import os
import shutil
from pathlib import Path

import uvicorn


if __name__ == "__main__":
    base = Path(__file__).resolve().parent
    bundle = base / "demo/cache"
    if bundle.is_dir():
        shutil.copytree(bundle, base / "data/cache", dirs_exist_ok=True)
    uvicorn.run("api:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")), workers=1)
