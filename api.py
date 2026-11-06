"""Etapa 3: un proceso, cola en memoria y resultados científicos en disco.

Ejecutar con un solo worker de Uvicorn: los límites y trabajos son por proceso.
El cómputo síncrono queda fuera del event loop mediante asyncio.to_thread.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import threading
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, model_validator
from astropy.io.fits.verify import VerifyError

from coordinates import parse_coordinates
from archive_config import COLLECTIONS
from disk_cache import trim
from analysis_modes import AnalysisInput, analyze
from spherex_pipeline import PIPELINE_VERSION, PipelineConfig, build_sequence, fingerprint, write_json, sequence_key
import spherex_pipeline as pipeline
from manifest_schema import Manifest
from targets import PRESETS, resolve_target

BASE = Path(__file__).resolve().parent
RESULT_ID = re.compile(r"[a-f0-9]{24}(?:-[a-f0-9]{8})?")
TERMINAL = {"ready", "partial", "empty", "error"}
logger = logging.getLogger("orbitlens")


class SearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    preset: str | None = Field(default=None, max_length=40)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    ra: str | float | None = None
    dec: str | float | None = None
    fov: float = Field(default=5, ge=1, le=30)
    frames: int = Field(default=12, ge=1, le=16, strict=True)
    detector: str | None = Field(default=None, pattern=r"^SPHEREx-D[1-6]$")

    @model_validator(mode="before")
    @classmethod
    def reject_booleans(cls, value):
        if isinstance(value, dict) and any(isinstance(value.get(key), bool) for key in ("ra", "dec", "fov")):
            raise ValueError("RA, Dec y FOV no admiten booleanos.")
        return value

    @model_validator(mode="after")
    def target_choice(self):
        if self.name is not None:
            self.name = self.name.strip()
            if not self.name:
                raise ValueError("Introduce un nombre SIMBAD.")
        coordinates = self.ra is not None or self.dec is not None
        if sum((self.preset is not None, self.name is not None, coordinates)) != 1:
            raise ValueError("Elige un preset, un nombre o un par RA/Dec.")
        if coordinates and (self.ra is None or self.dec is None):
            raise ValueError("RA y Dec deben usarse juntos.")
        if self.preset is not None and self.preset not in PRESETS:
            raise ValueError("Preset desconocido.")
        if coordinates:
            self.ra, self.dec = parse_coordinates(self.ra, self.dec)
        return self


def config_key(config: PipelineConfig) -> str:
    return sequence_key(config)


@dataclass
class Job:
    id: str
    key: str
    body: SearchInput
    state: str = "queued"
    message: str = "Esperando turno."
    result_id: str | None = None
    target: dict | None = None
    cached: bool = False
    owners: set[str] = field(default_factory=set)
    finished: float | None = None


class JobManager:
    def __init__(self, raw_root: Path, cache_root: Path, builder=build_sequence,
                 resolver=resolve_target, max_heavy=3, per_ip=2, per_minute=10):
        self.raw_root, self.cache_root = raw_root, cache_root
        self.builder, self.resolver = builder, resolver
        self.max_heavy, self.per_ip, self.per_minute = max_heavy, per_ip, per_minute
        self.semaphore = asyncio.Semaphore(max_heavy)
        self.jobs: dict[str, Job] = {}
        self.active: dict[str, Job] = {}
        self.pending: deque[str] = deque()
        self.requests: dict[str, deque[float]] = defaultdict(deque)
        self.results: dict[str, tuple[Path, dict]] = {}
        self.cache: dict[str, str] = {}
        self.presets: dict[str, dict] = {}
        self.tasks: set[asyncio.Task] = set()
        # Evitar escrituras simultáneas de consultas/recortes compartidos entre
        # variantes de una búsqueda. Estas cerraduras solo se usan en los threads.
        self.locks: dict[str, threading.Lock] = {}
        self.lock_guard = threading.Lock()
        self.maintenance = False
        self.analysis_count = 0
        self.analysis_owners: dict[str, int] = defaultdict(int)
        self.disk_bytes = 0
        self.disk_budget = int(os.environ.get("ORBITLENS_CACHE_BYTES", str(2 * 1024**3)))
        if self.disk_budget <= 0:
            raise ValueError("ORBITLENS_CACHE_BYTES debe ser positivo.")

    async def clean_disk(self):
        if self.active or self.maintenance or self.analysis_count:
            return
        self.maintenance = True
        try:
            self.prune()
            protected = {entry["result_id"] for entry in self.presets.values()}
            protected.update(job.result_id for job in self.jobs.values() if job.result_id)
            removed, self.disk_bytes = await asyncio.to_thread(
                trim, self.raw_root, self.cache_root, protected, self.disk_budget)
            for result_id in removed:
                self.results.pop(result_id, None)
            self.cache = {key: value for key, value in self.cache.items() if value not in removed}
            # No hay resolutores ni constructores activos durante esta limpieza.
            with self.lock_guard:
                self.locks.clear()
        except OSError:
            logger.exception("No se pudo completar la limpieza de caché.")
        finally:
            # También reconciliar después de una eliminación parcial interrumpida.
            missing = {key for key, (path, _) in self.results.items() if not path.is_file()}
            self.results = {key: value for key, value in self.results.items() if key not in missing}
            self.cache = {key: value for key, value in self.cache.items() if value not in missing}
            self.presets = {key: value for key, value in self.presets.items() if value["result_id"] not in missing}
            self.maintenance = False

    def touch(self, result_id):
        try:
            directory = self.results[result_id][0].parent
            if not directory.is_dir():
                raise FileNotFoundError(directory)
            os.utime(directory, None)  # No crea nada si desaparece entre comprobaciones.
        except (FileNotFoundError, NotADirectoryError):
            self.results.pop(result_id, None)
            self.cache = {key: value for key, value in self.cache.items() if value != result_id}
            self.presets = {key: value for key, value in self.presets.items() if value["result_id"] != result_id}
            raise HTTPException(404, "Resultado expirado. Repite la búsqueda.")

    def disk_lock(self, key):
        with self.lock_guard:
            return self.locks.setdefault(key, threading.Lock())

    def cached_result(self, key):
        result_id = self.cache.get(key)
        if result_id:
            path, manifest = self.results[result_id]
            if not path.is_file() or (manifest["status"] != "ready" and time.time() - path.stat().st_mtime >= 60):
                self.cache.pop(key, None)
                return None
        return result_id

    def register(self, path: Path):
        path = path.resolve()
        if path.parent.parent != self.cache_root.resolve() or not RESULT_ID.fullmatch(path.parent.name):
            raise ValueError("Ruta de resultado inválida.")
        manifest = json.loads(path.read_text(encoding="utf-8"))
        Manifest.model_validate(manifest)
        if (manifest["schema_version"] != 1 or manifest["pipeline_version"] != PIPELINE_VERSION
                or manifest["status"] not in TERMINAL
                or manifest["quality_policy"]["mask_bits"] != list(pipeline.MASK_BITS)):
            raise ValueError("Manifiesto incompatible.")
        config = PipelineConfig(**manifest["parameters"])
        cache_key = config_key(config)
        if manifest["status"] == "ready" and len(manifest["frames"]) < min(3, config.frames):
            raise ValueError("Secuencia ready sin suficientes frames.")
        for frame in manifest["frames"]:
            for key in ("image", "aligned_fits"):
                asset = (path.parent / frame[key]).resolve()
                if not asset.is_relative_to(path.parent) or not asset.is_file():
                    raise ValueError("Artefacto ausente o fuera del resultado.")
        result_id = path.parent.name
        self.results[result_id] = (path, manifest)
        if tuple(manifest["collections"]) == COLLECTIONS:
            self.cache[cache_key] = result_id
        return result_id

    def load_cache(self):
        """Calentar el índice local sin consultas a SIMBAD ni a IRSA."""
        self.cache_root.mkdir(parents=True, exist_ok=True)
        for path in sorted(self.cache_root.glob("*/manifest.json"), key=lambda p: p.stat().st_mtime):
            try:
                self.register(path)
            except (OSError, ValueError, KeyError, TypeError):
                logger.warning("Resultado incompatible o incompleto omitido: %s", path.parent.name)
        report = self.cache_root / "preset_verification.json"
        if report.exists():
            try:
                for entry in json.loads(report.read_text(encoding="utf-8"))["results"]:
                    # El informe del CLI puede proceder de Windows y desplegarse en Linux.
                    result_id = PureWindowsPath(entry.get("manifest", "")).parent.name
                    if entry.get("preset") in PRESETS and result_id in self.results:
                        manifest = self.results[result_id][1]
                        if manifest["status"] == "ready" and tuple(manifest.get("collections", COLLECTIONS)) == COLLECTIONS:
                            self.presets[entry["preset"]] = {"result_id": result_id, "target": entry["target"]}
            except (OSError, ValueError, KeyError, TypeError):
                logger.warning("No se pudo leer el informe de presets.")

    def config(self, body, target=None):
        return PipelineConfig(ra=target["ra_deg"] if target else float(body.ra),
                              dec=target["dec_deg"] if target else float(body.dec),
                              fov=body.fov, frames=body.frames, detector=body.detector)

    def known_target(self, body):
        if body.preset in self.presets:
            return self.presets[body.preset]["target"]
        if body.name:
            for entry in self.presets.values():
                if body.name.casefold() == entry["target"]["name"].casefold():
                    return entry["target"]
        return None

    def prune(self):
        now = time.monotonic()
        for job_id, job in list(self.jobs.items()):
            if job.finished is not None and now - job.finished > 3600:
                del self.jobs[job_id]
        for ip, timestamps in list(self.requests.items()):
            while timestamps and now - timestamps[0] >= 60:
                timestamps.popleft()
            if not timestamps:
                del self.requests[ip]
        # Límite de memoria de trabajos terminados; los resultados siguen en disco.
        done = [job for job in self.jobs.values() if job.finished is not None]
        for job in sorted(done, key=lambda j: j.finished)[:max(0, len(self.jobs) - 256)]:
            del self.jobs[job.id]

    def submit(self, body: SearchInput, ip: str):
        self.prune()
        timestamps = self.requests[ip]
        if len(timestamps) >= self.per_minute:
            raise HTTPException(429, "Demasiadas búsquedas. Espera un minuto e inténtalo de nuevo.",
                                headers={"Retry-After": "60"})
        timestamps.append(time.monotonic())
        target = self.known_target(body)
        config = self.config(body, target) if target or body.ra is not None else None
        key = config_key(config) if config else fingerprint(body.model_dump())
        result_id = self.cached_result(key) if config else None
        if self.maintenance and result_id not in {p["result_id"] for p in self.presets.values()}:
            raise HTTPException(429, "Caché en mantenimiento. Espera unos segundos o abre un campo precargado.",
                                headers={"Retry-After": "5"})
        if result_id:
            self.touch(result_id)
            job = Job(uuid.uuid4().hex, key, body, state=self.results[result_id][1]["status"], message="Resultado recuperado de caché.",
                      result_id=result_id, target=target, cached=True, finished=time.monotonic())
            self.jobs[job.id] = job
            return self.status(job)
        if self.maintenance or self.disk_bytes >= self.disk_budget:
            raise HTTPException(429, "La caché está en mantenimiento o llena. Prueba un campo precargado o espera unos minutos.",
                                headers={"Retry-After": "60"})
        existing = self.active.get(key)
        if existing and ip in existing.owners:
            return self.status(existing)
        if self.analysis_owners.get(ip, 0) + sum(ip in job.owners for job in self.active.values()) >= self.per_ip:
            raise HTTPException(429, "Ya tienes dos búsquedas en curso. Espera a que terminen.",
                                headers={"Retry-After": "5"})
        if existing:
            existing.owners.add(ip)
            return self.status(existing)
        if len(self.active) >= 32:
            raise HTTPException(429, "La cola está llena. Prueba un preset o vuelve en un minuto.",
                                headers={"Retry-After": "60"})
        job = Job(uuid.uuid4().hex, key, body, owners={ip}, target=target)
        self.jobs[job.id] = self.active[key] = job
        self.pending.append(job.id)
        task = asyncio.create_task(self.run(job), name=job.id)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return self.status(job)

    def resolve(self, body):
        name = PRESETS[body.preset] if body.preset else body.name
        resolution = self.raw_root / "targets" / f"{fingerprint({'name': name, 'epoch': 2026.5})}.json"
        with self.disk_lock(f"name:{name}"):
            if resolution.exists():
                return json.loads(resolution.read_text(encoding="utf-8"))
            with httpx.Client(timeout=60, follow_redirects=True) as client:
                target = self.resolver(client, name, 2026.5)
            target["retrieved_at_utc"] = datetime.now(timezone.utc).isoformat()
            resolution.parent.mkdir(parents=True, exist_ok=True)
            write_json(resolution, target)
            return target

    def compute(self, config):
        with self.disk_lock(f"sky:{config.ra}:{config.dec}"):
            return self.builder(config, raw_root=self.raw_root, cache_root=self.cache_root)

    async def run(self, job):
        try:
            async with self.semaphore:
                self.pending.remove(job.id)
                if job.body.ra is None and job.target is None:
                    job.state, job.message = "resolving", "Resolviendo el nombre con SIMBAD…"
                    job.target = await asyncio.to_thread(self.resolve, job.body)
                job.state, job.message = "searching", "Consultando y alineando observaciones; puede tardar varios minutos…"
                config = self.config(job.body, job.target)
                # Una resolución de nombre puede conducir a una secuencia ya indexada.
                result_id = self.cached_result(config_key(config))
                if result_id:
                    job.cached = True
                else:
                    path = await asyncio.to_thread(self.compute, config)
                    result_id = self.register(path)
                job.result_id = result_id
                job.state = self.results[result_id][1]["status"]
                job.message = {"ready": "Secuencia procesada; no confirma una detección.",
                               "partial": "Solo hay uno o dos frames utilizables.",
                               "empty": "No hay observaciones para este campo y detector. Prueba otro detector o un preset.",
                               "error": "No se pudo completar la secuencia. Revisa el informe de consultas y recortes."}[job.state]
        except Exception:
            logger.exception("Error en el trabajo %s", job.id)
            job.state, job.message = "error", "La búsqueda falló. Comprueba el nombre o las coordenadas y vuelve a intentarlo; SIMBAD o IRSA pueden estar temporalmente inaccesibles."
        finally:
            if job.id in self.pending:
                self.pending.remove(job.id)
            self.active.pop(job.key, None)
            job.finished = time.monotonic()

    def status(self, job):
        position = list(self.pending).index(job.id) + 1 if job.id in self.pending else 0
        return {"job_id": job.id, "status": job.state, "message": job.message,
                "queue_position": position, "cached": job.cached, "target": job.target,
                "result_id": job.result_id,
                "manifest_url": f"/api/results/{job.result_id}/manifest" if job.result_id else None}

    def preset_list(self):
        return [{"id": slug, "name": name, "cached": slug in self.presets,
                 "frame_count": len(self.results[self.presets[slug]["result_id"]][1]["frames"]) if slug in self.presets else 0}
                for slug, name in PRESETS.items()]


def create_app(*, raw_root=BASE / "data/raw", cache_root=BASE / "data/cache",
               frontend_root=BASE / "frontend/dist", builder=build_sequence,
               resolver=resolve_target, max_heavy=3, per_ip=2, per_minute=10):
    manager = JobManager(Path(raw_root), Path(cache_root), builder, resolver, max_heavy, per_ip, per_minute)

    @asynccontextmanager
    async def lifespan(app):
        await asyncio.to_thread(manager.load_cache)
        if os.environ.get("ORBITLENS_REQUIRE_PRESETS") == "1" and len(manager.presets) != len(PRESETS):
            raise RuntimeError("Despliegue incompleto: faltan presets compatibles. Ejecutar prepare_deploy.py antes de publicar.")
        await manager.clean_disk()
        async def maintain():
            while True:
                await asyncio.sleep(60)
                await manager.clean_disk()
        maintenance_task = asyncio.create_task(maintain())
        yield
        maintenance_task.cancel()
        await asyncio.gather(maintenance_task, return_exceptions=True)
        # No iniciar búsquedas pendientes durante el apagado del servidor.
        for task in list(manager.tasks):
            if task.get_name() in manager.pending:
                task.cancel()
        # Esperar los threads en curso: cancelar to_thread no interrumpe una descarga.
        if manager.tasks:
            await asyncio.gather(*list(manager.tasks), return_exceptions=True)

    app = FastAPI(title="OrbitLens API", version="0.3.0", lifespan=lifespan)
    app.state.manager = manager

    @app.get("/api/health")
    async def health():
        return {"status": "ok", "pipeline_version": PIPELINE_VERSION, "cached_presets": len(manager.presets)}

    @app.get("/api/presets")
    async def presets():
        return manager.preset_list()

    @app.post("/api/search", status_code=202)
    async def search(body: SearchInput, request: Request):
        # Uvicorn debe confiar X-Forwarded-For solo desde proxies conocidos.
        ip = request.client.host if request.client else "unknown"
        return manager.submit(body, ip)

    @app.get("/api/status/{job_id}")
    async def status(job_id: str):
        job = manager.jobs.get(job_id)
        if job is None:
            raise HTTPException(404, "Trabajo desconocido o expirado. Repite la búsqueda.")
        return manager.status(job)

    def result(result_id):
        if not RESULT_ID.fullmatch(result_id) or result_id not in manager.results:
            raise HTTPException(404, "Resultado desconocido.")
        if manager.maintenance and result_id not in {p["result_id"] for p in manager.presets.values()}:
            raise HTTPException(503, "Caché en mantenimiento; vuelve a intentarlo en unos segundos.", headers={"Retry-After": "5"})
        manager.touch(result_id)
        return manager.results[result_id]

    @app.get("/api/results/{result_id}/manifest")
    async def manifest(result_id: str):
        path, source = result(result_id)
        # Enlaces por índice: nunca se sirve el directorio completo de datos.
        value = {**source, "queries": {name: {**query, **({"error": "No se pudo consultar la colección."} if "error" in query else {})}
                                       for name, query in source["queries"].items()},
                 "failures": [{**failure, "error": "No se pudo procesar el recorte."} for failure in source["failures"]],
                 "frames": [{**frame,
                 "wavelength_at_target": {**frame["wavelength_at_target"], **({"error": "Información espectral no disponible."} if "error" in frame["wavelength_at_target"] else {})},
                 "image_url": f"/api/results/{result_id}/frames/{i}.png",
                 "fits_url": f"/api/results/{result_id}/aligned/{i}.fits"}
                 for i, frame in enumerate(source["frames"])]}
        if source.get("preview", {}).get("image") == "preview.gif" and (path.parent / "preview.gif").is_file():
            value["preview"] = {**source["preview"], "image_url": f"/api/results/{result_id}/preview.gif"}
        else:
            value.pop("preview", None)
        return JSONResponse(value)

    @app.post("/api/results/{result_id}/analysis")
    async def analysis(result_id: str, body: AnalysisInput, request: Request):
        path, source = result(result_id)
        if manager.maintenance or manager.semaphore.locked():
            raise HTTPException(429, "Servidor ocupado. Inténtalo en unos segundos.", headers={"Retry-After": "5"})
        manager.prune()
        ip = request.client.host if request.client else "unknown"
        timestamps = manager.requests[ip]
        if manager.analysis_owners.get(ip, 0) + sum(ip in job.owners for job in manager.active.values()) >= manager.per_ip:
            raise HTTPException(429, "Ya tienes dos operaciones en curso.", headers={"Retry-After": "5"})
        if len(timestamps) >= manager.per_minute:
            raise HTTPException(429, "Demasiadas solicitudes; espera un minuto.", headers={"Retry-After": "60"})
        timestamps.append(time.monotonic())
        manager.analysis_count += 1
        manager.analysis_owners[ip] += 1
        try:
            async with manager.semaphore:
                task = asyncio.create_task(asyncio.to_thread(analyze, path.parent, source, body))
                try:
                    return await asyncio.shield(task)
                except asyncio.CancelledError:
                    # La desconexión del cliente no detiene el thread de lectura.
                    await task
                    raise
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except (OSError, KeyError, TypeError, VerifyError):
            logger.exception("No se pudo analizar el resultado %s", result_id)
            raise HTTPException(422, "No se pudo leer la secuencia alineada. Repite la búsqueda.")
        finally:
            manager.analysis_count -= 1
            manager.analysis_owners[ip] -= 1
            if not manager.analysis_owners[ip]:
                del manager.analysis_owners[ip]

    @app.get("/api/results/{result_id}/frames/{index}.png")
    async def frame(result_id: str, index: int):
        path, source = result(result_id)
        if not 0 <= index < len(source["frames"]):
            raise HTTPException(404, "Frame desconocido.")
        return FileResponse(path.parent / source["frames"][index]["image"], media_type="image/png")

    @app.get("/api/results/{result_id}/preview.gif")
    async def preview(result_id: str):
        path, source = result(result_id)
        if source.get("preview", {}).get("image") != "preview.gif" or not (path.parent / "preview.gif").is_file():
            raise HTTPException(404, "Vista previa no disponible.")
        return FileResponse(path.parent / "preview.gif", media_type="image/gif")

    @app.get("/api/results/{result_id}/target.json")
    async def target(result_id: str):
        path, _ = result(result_id)
        if not (path.parent / "target.json").is_file():
            raise HTTPException(404, "Metadatos de objetivo no disponibles.")
        return FileResponse(path.parent / "target.json", media_type="application/json")

    @app.get("/api/results/{result_id}/aligned/{index}.fits")
    async def aligned(result_id: str, index: int):
        path, source = result(result_id)
        if not 0 <= index < len(source["frames"]):
            raise HTTPException(404, "Frame desconocido.")
        return FileResponse(path.parent / source["frames"][index]["aligned_fits"],
                            media_type="application/fits", filename=f"orbitlens-{result_id}-{index}.fits")

    # Evitar que una ruta API desconocida acabe devolviendo index.html.
    @app.api_route("/api/{unknown:path}", methods=["GET", "POST"])
    async def unknown_api(unknown: str):
        raise HTTPException(404, "Ruta API desconocida.")

    frontend_root = Path(frontend_root)
    if frontend_root.is_dir():
        app.mount("/", StaticFiles(directory=frontend_root, html=True), name="web")
    else:
        @app.get("/")
        async def no_build():
            return JSONResponse({"message": "Compila la web: cd frontend; npm install; npm run build. API disponible en /docs."}, status_code=503)
    return app


app = create_app()
