"""Servidor exclusivo E2E: bundle temporal y ninguna búsqueda externa permitida."""
from contextlib import asynccontextmanager
from pathlib import Path
import shutil
import tempfile

from api import create_app

BASE = Path(__file__).resolve().parents[1]
if not (BASE / "frontend/dist/index.html").is_file():
    raise RuntimeError("Compila primero el frontend: npm --prefix frontend run build")

temporary = tempfile.TemporaryDirectory(prefix="orbitlens-browser-")
root = Path(temporary.name)
shutil.copytree(BASE / "demo/cache", root / "cache")


def forbidden(*args, **kwargs):
    raise RuntimeError("E2E sin red: no se permiten resoluciones ni construcciones nuevas.")


# Cuota elevada solo en este servidor de pruebas: los límites de producción se
# comprueban aparte con verify_release.py y las pruebas unitarias/de proxy.
app = create_app(raw_root=root / "raw", cache_root=root / "cache",
                 frontend_root=BASE / "frontend/dist", builder=forbidden,
                 resolver=forbidden, per_minute=500)
original_lifespan = app.router.lifespan_context


@asynccontextmanager
async def lifespan(application):
    try:
        async with original_lifespan(application):
            yield
    finally:
        temporary.cleanup()


app.router.lifespan_context = lifespan
