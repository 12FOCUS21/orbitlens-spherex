"""Pipeline exploratorio: un detector, WCS común y estiramiento global.

Las imágenes alineadas conservan brillo superficial; no son fotometría validada.
Fuentes y decisiones científicas: SCIENCE.md.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import astropy.units as u
import httpx
import numpy as np
from astropy.io import fits
from astropy.time import Time
from astropy.wcs import WCS
from PIL import Image, ImageDraw
from reproject import reproject_interp

from test_data import COLLECTIONS, cutout_url, download, mjd_key, parse_sia_votable, query_collection, retryable


PIPELINE_VERSION = "0.2.2"
PIXEL_SCALE_ARCSEC = 6.15
FLAGS_SOURCE = "https://irsa.ipac.caltech.edu/onlinehelp/spherex/spherex/sp.html"
FLAG_NAMES = {
    0: "TRANSIENT", 1: "OVERFLOW", 2: "SUR_ERROR", 6: "NONFUNC",
    7: "DICHROIC", 9: "MISSING_DATA", 10: "HOT", 11: "COLD",
    12: "FULLSAMPLE", 14: "PHANMISS", 15: "NONLINEAR", 17: "PERSIST",
    19: "OUTLIER", 20: "CROSSTALK", 21: "SOURCE", 22: "GHOST",
    23: "GHOST_FPA", 24: "GHOST_EXT", 25: "STREAK", 26: "BLOOM",
    27: "SNOWBALL", 28: "HALO", 29: "SATELLITE_HALO",
}
# Política conservadora para visualización; SOURCE y FULLSAMPLE son informativos.
MASK_BITS = tuple(bit for bit in FLAG_NAMES if bit not in (12, 21))
BAD_MASK = sum(1 << bit for bit in MASK_BITS)


@dataclass(frozen=True)
class PipelineConfig:
    ra: float
    dec: float
    fov: float = 5.0
    frames: int = 12
    detector: str | None = None
    maxrec: int = 1000
    min_coverage: float = 0.5

    def __post_init__(self):
        if not math.isfinite(self.ra) or not 0 <= self.ra < 360:
            raise ValueError("RA debe estar en [0, 360).")
        if not math.isfinite(self.dec) or not -90 <= self.dec <= 90:
            raise ValueError("Dec debe estar en [-90, 90].")
        if not 1 <= self.fov <= 30 or not 1 <= self.frames <= 16:
            raise ValueError("FOV debe estar en [1, 30] arcmin y frames en [1, 16].")
        if not 1 <= self.maxrec <= 10000 or not 0 < self.min_coverage <= 1:
            raise ValueError("MAXREC o cobertura mínima fuera de rango.")
        if self.detector is not None and self.detector not in {f"SPHEREx-D{i}" for i in range(1, 7)}:
            raise ValueError("Detector debe ser SPHEREx-D1…SPHEREx-D6.")


def fingerprint(value: dict | str) -> str:
    encoded = json.dumps(value, sort_keys=True, allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:24]


def write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".json.part")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def query_observations(client: httpx.Client, config: PipelineConfig, root: Path,
                       refresh: bool = False) -> tuple[list[dict], dict]:
    query_dir = root / "queries" / fingerprint({"ra": config.ra, "dec": config.dec, "maxrec": config.maxrec})
    query_dir.mkdir(parents=True, exist_ok=True)
    args = argparse.Namespace(ra=config.ra, dec=config.dec, maxrec=config.maxrec, output=query_dir)
    rows, metadata = [], {}
    for collection in COLLECTIONS:
        path = query_dir / f"query_{collection}.vot"
        try:
            if path.exists() and not refresh and time.time() - path.stat().st_mtime < 7 * 86400:
                found = parse_sia_votable(path.read_bytes(), collection)
            else:
                found = query_collection(client, collection, args)
            rows.extend(found)
            query_dir.touch()
            metadata[collection] = {
                "rows": len(found), "possibly_truncated": len(found) >= config.maxrec,
                "retrieved_at_utc": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
            }
        except (httpx.HTTPError, OSError, ValueError) as exc:
            metadata[collection] = {"error": str(exc)}
    return rows, metadata


def group_observations(rows: list[dict]) -> dict[str, list[dict]]:
    groups, seen = {}, set()
    # Preferir la versión más reciente de una misma exposición, sin duplicarla.
    for row in sorted(rows, key=lambda r: COLLECTIONS.index(r["collection"])):
        detector = row.get("energy_bandpassname", "")
        if detector not in {f"SPHEREx-D{i}" for i in range(1, 7)} or not math.isfinite(mjd_key(row)):
            continue
        identity = (row.get("obs_id") or row.get("access_url"), detector)
        if not row.get("access_url") or identity in seen:
            continue
        seen.add(identity)
        groups.setdefault(detector, []).append(row)
    return {name: sorted(group, key=mjd_key) for name, group in groups.items()}


def select_detector(groups: dict[str, list[dict]], requested: str | None = None) -> str | None:
    if requested:
        return requested if requested in groups else None
    if not groups:
        return None
    # Priorizar diversidad de fechas, después intervalo temporal y cantidad.
    def score(name):
        dates = [mjd_key(row) for row in groups[name]]
        return len({math.floor(date) for date in dates}), max(dates) - min(dates), len(dates), -int(name[-1])
    return max(groups, key=score)


def select_times(rows: list[dict], count: int) -> list[dict]:
    """Muestreo determinista: extremos y puntos más alejados de los elegidos."""
    ordered = sorted(rows, key=mjd_key)
    if len(ordered) <= count:
        return ordered
    if count == 1:
        return [ordered[len(ordered) // 2]]
    indices = {0, len(ordered) - 1}
    while len(indices) < count:
        next_index = max((i for i in range(len(ordered)) if i not in indices),
                         key=lambda i: min(abs(mjd_key(ordered[i]) - mjd_key(ordered[j])) for j in indices))
        indices.add(next_index)
    return [ordered[i] for i in sorted(indices)]


def common_grid(config: PipelineConfig) -> tuple[WCS, tuple[int, int]]:
    size = math.ceil(config.fov * 60 / PIXEL_SCALE_ARCSEC)
    wcs = WCS(naxis=2)
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    wcs.wcs.cunit = ["deg", "deg"]
    wcs.wcs.crval = [config.ra, config.dec]
    wcs.wcs.crpix = [(size + 1) / 2, (size + 1) / 2]
    wcs.wcs.cdelt = [-PIXEL_SCALE_ARCSEC / 3600, PIXEL_SCALE_ARCSEC / 3600]
    wcs.wcs.radesys = "ICRS"
    return wcs, (size, size)


def flag_statistics(flags: np.ndarray) -> tuple[np.ndarray, dict]:
    flags = flags.astype(np.uint32)
    rejected = (flags & BAD_MASK) != 0
    bits = [{"bit": bit, "name": FLAG_NAMES.get(bit, "UNDOCUMENTED"),
             "fraction": float(np.mean((flags & (1 << bit)) != 0)),
             "masked": bit in MASK_BITS} for bit in range(32) if np.any(flags & (1 << bit))]
    return rejected, {"nonzero_fraction": float(np.mean(flags != 0)),
                      "masked_fraction": float(np.mean(rejected)), "bits": bits}


def wavelength_at_target(hdul, header, x: float, y: float) -> dict:
    try:
        # IRSA: WCS W mapea píxeles del detector a longitud de onda sin SIP.
        # Copiar el header para conservar intacta la distorsión del WCS celestial.
        # Retirar SIP antes de construir W evita además el aviso de Astropy.
        spectral_header = header.copy()
        for keyword in list(spectral_header):
            if re.fullmatch(r"(?:A|B|AP|BP)_(?:ORDER|DMAX|\d+_\d+)", keyword):
                del spectral_header[keyword]
        spectral = WCS(spectral_header, hdul, key="W")
        spectral.sip = None
        values = spectral.all_pix2world([[x, y]], 0)[0]
        wave, width = [(float(value) * u.Unit(unit)).to_value(u.um)
                       for value, unit in zip(values, spectral.world_axis_units)]
        if not (math.isfinite(wave) and math.isfinite(width) and wave > 0 and width > 0):
            raise ValueError("Longitud de onda o ancho no válido.")
        return {"central_um": wave, "width_um": width,
                "method": "WCS-WAVE visualization lookup, without SIP"}
    except (ValueError, KeyError, TypeError, u.UnitConversionError) as exc:
        return {"central_um": None, "width_um": None, "error": str(exc)}


def align_cutout(path: Path, config: PipelineConfig, output_wcs: WCS,
                 shape: tuple[int, int]) -> tuple[np.ndarray, np.ndarray, dict]:
    with fits.open(path, memmap=False) as hdul:
        science = hdul["IMAGE"]
        image = np.asarray(science.data, dtype=np.float64)
        if image.ndim != 2:
            raise ValueError("IMAGE no es 2D.")
        if u.Unit(science.header.get("BUNIT", "")) != u.MJy / u.sr:
            raise ValueError("Unidad IMAGE inesperada; se espera MJy/sr.")
        wcs = WCS(science.header, hdul).celestial
        x, y = (float(v) for v in wcs.world_to_pixel_values(config.ra, config.dec))
        if not (-0.5 <= x < image.shape[1] - 0.5 and -0.5 <= y < image.shape[0] - 0.5):
            raise ValueError("El centro solicitado queda fuera del recorte.")
        if "FLAGS" not in hdul or hdul["FLAGS"].data.shape != image.shape:
            raise ValueError("FLAGS ausente o con dimensiones diferentes a IMAGE.")
        flags = np.asarray(hdul["FLAGS"].data, dtype=np.uint32)
        rejected, quality = flag_statistics(flags)
        image[rejected | ~np.isfinite(image)] = np.nan
        aligned, footprint = reproject_interp((image, wcs), output_wcs, shape_out=shape, order="bilinear")
        valid = np.isfinite(aligned) & (footprint > 0)
        aligned[~valid] = np.nan
        projected_flags, _ = reproject_interp((flags.astype(np.float64), wcs), output_wcs,
                                             shape_out=shape, order="nearest-neighbor")
        aligned_flags = np.where(np.isfinite(projected_flags), projected_flags, 0).astype(np.uint32)
        center = (shape[0] // 2, shape[1] // 2)
        coverage = float(valid.mean())
        if coverage < config.min_coverage:
            raise ValueError(f"Cobertura válida insuficiente ({coverage:.1%}; mínimo {config.min_coverage:.1%}).")
        # La máscara local no invalida todo el campo. Nunca se rellenan sus huecos.
        center_flags = int(aligned_flags[center])
        quality.update(valid_coverage=coverage, input_shape=list(image.shape),
                       center_pixel_valid=bool(valid[center]), center_pixel_flags=center_flags,
                       center_pixel_flag_names=[FLAG_NAMES.get(bit, f"UNDOCUMENTED_{bit}")
                                                for bit in range(32) if center_flags & (1 << bit)])
        return aligned, aligned_flags, {"quality": quality,
                                       "wavelength_at_target": wavelength_at_target(hdul, science.header, x, y)}


def global_limits(images: list[np.ndarray]) -> tuple[float, float]:
    values = np.concatenate([image[np.isfinite(image)] for image in images])
    if not values.size:
        raise ValueError("Secuencia sin píxeles finitos.")
    low, high = (float(v) for v in np.percentile(values, [1, 99]))
    if high <= low:
        raise ValueError("Secuencia sin rango visual entre percentiles 1 y 99.")
    return low, high


def render_frame(image: np.ndarray, limits: tuple[float, float]) -> Image.Image:
    low, high = limits
    valid = np.isfinite(image)
    normalized = np.zeros(image.shape)
    normalized[valid] = np.clip((image[valid] - low) / (high - low), 0, 1)
    gray = np.rint(np.arcsinh(10 * normalized) / np.arcsinh(10) * 255).astype(np.uint8)
    rgba = np.dstack((gray, gray, gray, valid.astype(np.uint8) * 255))
    return Image.fromarray(np.flipud(rgba))


def cached_cutout(client: httpx.Client, url: str, root: Path, refresh: bool) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{fingerprint(url)}.fits"
    if path.exists() and not refresh:
        try:
            with fits.open(path, memmap=False) as hdul:
                if "IMAGE" not in hdul:
                    raise ValueError("Caché FITS sin IMAGE.")
            path.touch()
            return path
        except (OSError, ValueError):
            path.unlink(missing_ok=True)
    for attempt in range(3):
        try:
            download(client, url, path)
            # Verificar que el servicio no haya devuelto HTML con estado 200.
            with fits.open(path, memmap=False) as hdul:
                if "IMAGE" not in hdul:
                    raise ValueError("El recorte no contiene IMAGE.")
            return path
        except (httpx.HTTPError, OSError, ValueError) as exc:
            path.unlink(missing_ok=True)
            if attempt == 2 or (isinstance(exc, httpx.HTTPError) and not retryable(exc)):
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("Descarga sin resultado.")


def build_sequence(config: PipelineConfig, *, raw_root: Path = Path("data/raw"),
                   cache_root: Path = Path("data/cache"), refresh: bool = False,
                   client: httpx.Client | None = None) -> Path:
    """Crea un manifiesto listo para consumir desde la API de la siguiente etapa."""
    if client is None:
        with httpx.Client(timeout=httpx.Timeout(30, connect=10), follow_redirects=True) as owned:
            return build_sequence(config, raw_root=raw_root, cache_root=cache_root,
                                  refresh=refresh, client=owned)
    key = fingerprint({"config": asdict(config), "version": PIPELINE_VERSION,
                       "collections": COLLECTIONS, "mask_bits": MASK_BITS})
    destination = cache_root / key
    existing = destination / "manifest.json"
    if existing.exists() and not refresh:
        manifest = json.loads(existing.read_text(encoding="utf-8"))
        if manifest["status"] == "ready" and all(
                (destination / frame[name]).exists() for frame in manifest["frames"] for name in ("image", "aligned_fits")):
            print(f"Caché lista: {existing}")
            return existing
    # Cada intento nuevo usa una carpeta propia; no sobrescribe una secuencia válida.
    if destination.exists():
        destination = cache_root / f"{key}-{uuid.uuid4().hex[:8]}"
    destination.mkdir(parents=True)
    rows, queries = query_observations(client, config, raw_root, refresh)
    groups = group_observations(rows)
    detector = select_detector(groups, config.detector)
    manifest = {"schema_version": 1, "pipeline_version": PIPELINE_VERSION,
                "cache_key": key, "created_at_utc": datetime.now(timezone.utc).isoformat(),
                "parameters": asdict(config), "collections": list(COLLECTIONS),
                "queries": queries, "detector": detector, "frames": [], "failures": [],
                "credit": "NASA/JPL-Caltech; SPHEREx data hosted by IRSA",
                "quality_policy": {"mask_bits": list(MASK_BITS), "source": FLAGS_SOURCE,
                                   "informational_bits": [12, 21], "unknown_bits_masked": False},
                "caveats": ["Exploración visual; no confirma movimiento ni descubrimientos.",
                            "Mismo detector no garantiza la misma longitud de onda.",
                            "Sin sustracción de ZODI ni ajuste de PSF ni fotometría.",
                            "Rejilla ICRS fija; los frames no siguen el movimiento del objeto."]}
    manifest_path = destination / "manifest.json"
    if detector is None:
        manifest["status"] = "error" if any("error" in q for q in queries.values()) else "empty"
        write_json(manifest_path, manifest)
        return manifest_path
    candidates = select_times(groups[detector], config.frames)
    chosen_urls = {row["access_url"] for row in candidates}
    backups = select_times([row for row in groups[detector] if row["access_url"] not in chosen_urls], 4)
    output_wcs, shape = common_grid(config)
    # Margen para las esquinas al rotar el detector a norte arriba.
    download_fov = config.fov * math.sqrt(2) + 2 * PIXEL_SCALE_ARCSEC / 60
    cutout_args = argparse.Namespace(ra=config.ra, dec=config.dec, fov=download_fov)
    accepted = []
    for row in candidates + backups:
        try:
            url = cutout_url(row["access_url"], cutout_args)
            path = cached_cutout(client, url, raw_root / "cutouts", refresh)
            image, flags, details = align_cutout(path, config, output_wcs, shape)
            accepted.append((row, image, flags, details, url))
            print(f"Frame aceptado {len(accepted)}/{config.frames}: {row['collection']} {detector} MJD {row['t_min']}")
            if not details["quality"]["center_pixel_valid"]:
                print("AVISO: píxel central sin valor válido; se conserva la máscara y el resto del campo.")
            if len(accepted) == config.frames:
                break
        except (httpx.HTTPError, OSError, ValueError, KeyError) as exc:
            manifest["failures"].append({"access_url": row["access_url"], "error": str(exc)})
            print(f"AVISO: frame omitido: {exc}")
    accepted.sort(key=lambda item: mjd_key(item[0]))
    if not accepted:
        manifest["status"] = "error"
        write_json(manifest_path, manifest)
        return manifest_path
    limits = global_limits([item[1] for item in accepted])
    manifest.update(status="ready" if len(accepted) >= 3 else "partial",
                    requested_frames=config.frames, frame_count=len(accepted),
                    requested_count_reached=len(accepted) == config.frames,
                    available_observations=len(groups[detector]),
                    download_fov_arcmin=download_fov,
                    display={"percentiles": [1, 99], "limits_MJy_sr": list(limits),
                             "stretch": "asinh", "asinh_factor": 10, "vertical_flip": True},
                    grid={"shape": list(shape), "pixel_scale_arcsec": PIXEL_SCALE_ARCSEC,
                          "orientation": "north-up, east-left", "fits_header": output_wcs.to_header().tostring(),
                          "reprojection": "bilinear; flags nearest-neighbor"})
    masked_centers = sum(not item[3]["quality"]["center_pixel_valid"] for item in accepted)
    manifest["center_masked_frame_count"] = masked_centers
    manifest["warnings"] = ([f"El píxel central carece de valor válido en {masked_centers} de "
                              f"{len(accepted)} frames; no evaluar la fuente central con esos píxeles."]
                            if masked_centers else [])
    (destination / "frames").mkdir()
    (destination / "aligned").mkdir()
    previews = []
    for index, (row, image, flags, details, url) in enumerate(accepted):
        name = f"{index:03d}"
        png_path = f"frames/{name}.png"
        fits_path = f"aligned/{name}.fits"
        rendered = render_frame(image, limits)
        rendered.save(destination / png_path)
        header = output_wcs.to_header()
        header["BUNIT"] = "MJy / sr"
        header["MJD-OBS"] = mjd_key(row)
        fits.HDUList([fits.PrimaryHDU(image.astype(np.float32), header),
                      fits.ImageHDU(flags, output_wcs.to_header(), name="FLAGS"),
                      fits.ImageHDU(np.isfinite(image).astype(np.uint8), output_wcs.to_header(), name="VALID")
                      ]).writeto(destination / fits_path)
        date = Time(mjd_key(row), format="mjd", scale="utc").isot
        manifest["frames"].append({"index": index, "image": png_path, "aligned_fits": fits_path,
                                   "mjd": mjd_key(row), "date_utc": date, "detector": detector,
                                   "collection": row["collection"], "obs_id": row.get("obs_id"),
                                   "access_url": row["access_url"], "cutout_url": url,
                                   "exposure_seconds": row.get("t_exptime"), **details})
        # GIF auxiliar para QA; cadencia visual uniforme, no representa tiempo físico.
        size = max(256, shape[0])
        panel = Image.new("RGB", (size, size + 40), "#181818")
        resized = rendered.resize((size, size), Image.Resampling.NEAREST)
        panel.paste(resized, (0, 0), resized.getchannel("A"))
        ImageDraw.Draw(panel).text((4, size + 5), f"{date[:10]}  {detector}", fill="white")
        if not details["quality"]["center_pixel_valid"]:
            ImageDraw.Draw(panel).text((4, size + 22), "CENTER MASKED", fill="#ffbc7b")
        previews.append(panel)
    previews[0].save(destination / "preview.gif", save_all=True, append_images=previews[1:],
                     duration=500, loop=0, disposal=2)
    manifest["preview"] = {"image": "preview.gif", "frame_duration_ms": 500, "physical_time_scale": False}
    write_json(manifest_path, manifest)
    return manifest_path
