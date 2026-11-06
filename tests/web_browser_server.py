"""Servidor E2E para la interfaz vanilla: bundle temporal y ninguna búsqueda externa."""
from contextlib import asynccontextmanager
from pathlib import Path
import shutil
import tempfile

from api import create_app

BASE = Path(__file__).resolve().parents[1]
if not (BASE / "web/index.html").is_file():
    raise RuntimeError("Falta web/index.html.")

temporary = tempfile.TemporaryDirectory(prefix="orbitlens-web-browser-")
root = Path(temporary.name)
shutil.copytree(BASE / "demo/cache", root / "cache")


def forbidden(*args, **kwargs):
    raise RuntimeError("E2E sin red: no se permiten resoluciones ni construcciones nuevas.")


# La cuota elevada solo pertenece al servidor E2E, no al despliegue normal.
app = create_app(raw_root=root / "raw", cache_root=root / "cache",
                 frontend_root=BASE / "web", builder=forbidden,
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
