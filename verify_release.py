"""Smoke HTTP local del bundle y frontend compilado, sin consultar servicios remotos."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient

from api import create_app
from targets import PRESETS

BASE = Path(__file__).resolve().parent


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify_release(bundle=BASE / "demo/cache", frontend=BASE / "frontend/dist"):
    """Trabaja sobre una copia temporal: no modifica la caché ni sus mtimes originales."""
    bundle, frontend = Path(bundle).resolve(), Path(frontend).resolve()
    require((bundle / "preset_verification.json").is_file(), "Falta el informe del bundle.")
    require((frontend / "index.html").is_file(), "Falta frontend/dist; ejecuta npm --prefix frontend run build.")
    require((frontend / "catalogos.html").is_file(), "Falta la vista de catálogos en el frontend compilado.")

    def forbidden(*args, **kwargs):
        raise RuntimeError("El smoke debe usar la caché, nunca resolver nombres ni construir secuencias.")

    def get(client, url):
        require(url.startswith("/") and not url.startswith("//"), "URL de artefacto no local.")
        response = client.get(url)
        require(response.status_code == 200, f"GET {url}: HTTP {response.status_code}.")
        return response

    def search(client, body):
        response = client.post("/api/search", json=body)
        require(response.status_code == 202, f"Búsqueda cacheada: HTTP {response.status_code}.")
        job = response.json()
        require(job.get("status") == "ready" and job.get("cached"), "La búsqueda no recuperó una secuencia ready de caché.")
        return job

    with tempfile.TemporaryDirectory(prefix="orbitlens-smoke-") as folder:
        root = Path(folder)
        shutil.copytree(bundle, root / "cache")
        app = create_app(raw_root=root / "raw", cache_root=root / "cache", frontend_root=frontend,
                         builder=forbidden, resolver=forbidden)
        with TestClient(app) as client:
            health = get(client, "/api/health").json()
            require(health.get("cached_presets") == len(PRESETS), "No están indexados los cinco presets.")
            presets = get(client, "/api/presets").json()
            require({entry["id"] for entry in presets} == set(PRESETS), "Inventario de presets incompatible.")
            require(all(entry["cached"] for entry in presets), "Hay presets sin precargar.")

            # Misma aplicación/event loop y diez clientes HTTP concurrentes.
            # No equivale a ejecutar diez navegadores ni mide rendimiento de Render.
            start = threading.Barrier(10)
            def visitor(_):
                start.wait(timeout=30)
                page = get(client, "/")
                require("text/html" in page.headers.get("content-type", ""), "La portada no devuelve HTML.")
                get(client, "/api/health")
                get(client, "/api/presets")
                return page.text

            with ThreadPoolExecutor(max_workers=10) as pool:
                pages = list(pool.map(visitor, range(10)))
            assets = re.findall(r'(?:src|href)=["\'](/[^"\']+\.(?:js|css))["\']', pages[0])
            require(any(url.endswith(".js") for url in assets), "La portada no referencia un bundle JavaScript.")
            require(any(url.endswith(".css") for url in assets), "La portada no referencia estilos compilados.")
            for url in assets:
                response = get(client, url)
                expected = "javascript" if url.endswith(".js") else "text/css"
                require(expected in response.headers.get("content-type", ""), f"Tipo de recurso incorrecto: {url}.")
            get(client, "/catalogos.html?ra=0&dec=0&fov=5")

            results = []
            png_count = fits_count = 0
            for preset in presets:
                job = search(client, {"preset": preset["id"]})
                manifest = get(client, job["manifest_url"]).json()
                frames = manifest["frames"]
                require(len(frames) == 12, f"{preset['id']}: se esperaban 12 frames.")
                for frame in frames:
                    require(get(client, frame["image_url"]).content.startswith(b"\x89PNG\r\n\x1a\n"), "Artefacto PNG ilegible.")
                    require(get(client, frame["fits_url"]).content.startswith(b"SIMPLE  ="), "Artefacto FITS ilegible.")
                    png_count += 1
                    fits_count += 1
                preview_url = manifest.get("preview", {}).get("image_url")
                require(isinstance(preview_url, str), f"{preset['id']}: falta la referencia a preview.gif.")
                preview = get(client, preview_url)
                require(preview.content.startswith((b"GIF87a", b"GIF89a")), "Artefacto GIF ilegible.")
                target = get(client, f"/api/results/{job['result_id']}/target.json").json()
                require(all(target[key] == manifest["parameters"][axis]
                            for key, axis in (("ra_deg", "ra"), ("dec_deg", "dec"))), "Centro de target.json incompatible.")
                results.append({"preset": preset["id"], "result_id": job["result_id"],
                                "parameters": manifest["parameters"]})

            # Dos campos repetidos dos veces: 5 + 4 búsquedas, todas desde la misma IP.
            for result in results[:2]:
                body = {key: result["parameters"][key] for key in ("ra", "dec", "fov", "frames", "detector")}
                for _ in range(2):
                    require(search(client, body)["result_id"] == result["result_id"], "Un campo repetido no conserva el resultado.")
            search(client, {"preset": presets[0]["id"]})  # Décima petición permitida.
            limited = client.post("/api/search", json={"preset": presets[0]["id"]})
            require(limited.status_code == 429 and "Retry-After" in limited.headers, "El límite local de diez solicitudes no se aplica.")
            require(not app.state.manager.active, "El smoke inició trabajos pesados.")
            require(not (root / "raw").exists(), "El smoke generó datos raw inesperadamente.")

    return {"status": "ok", "scope": "local HTTP, sin navegador ni red externa",
            "concurrent_visitors": 10, "presets": len(results), "png": png_count, "fits": fits_count,
            "gif": len(results), "targets": len(results), "repeated_searches": 4, "local_rate_limit": "ok"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, default=BASE / "demo/cache")
    parser.add_argument("--frontend", type=Path, default=BASE / "frontend/dist")
    args = parser.parse_args()
    try:
        report = verify_release(args.bundle, args.frontend)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        parser.exit(1, f"Smoke fallido: {exc}\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
