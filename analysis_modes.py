"""Análisis exploratorio de FITS alineados; nunca opera sobre grises PNG."""
import base64
import io
import itertools
import math
from pathlib import Path
from typing import Literal

import astropy.units as u
import numpy as np
from astropy.io import fits
from astropy.wcs import WCS
from PIL import Image
from pydantic import BaseModel, Field, StrictInt


class AnalysisInput(BaseModel):
    mode: Literal["difference", "stack", "lightcurve"]
    indices: list[StrictInt] = Field(min_length=1, max_length=16)


def compatible(a, b):
    """Heurística explícita en el centro, no equivalencia de filtros calibrada."""
    if a.get("detector") != b.get("detector"):
        return False
    try:
        wa, wb = a["wavelength_at_target"], b["wavelength_at_target"]
        x, y, dx, dy = (float(wa["central_um"]), float(wb["central_um"]),
                        float(wa["width_um"]), float(wb["width_um"]))
        return all(math.isfinite(v) and v > 0 for v in (x, y, dx, dy)) and abs(x-y) <= min(dx, dy) / 2
    except (KeyError, TypeError, ValueError):
        return False


def read_frame(root, frame):
    root = Path(root).resolve()
    path = (root / frame["aligned_fits"]).resolve()
    if not path.is_relative_to(root):
        raise ValueError("FITS fuera del resultado.")
    with fits.open(path, memmap=False) as hdul:
        data = np.array(hdul[0].data, dtype=float)
        header = hdul[0].header.copy()
        if data.ndim != 2 or data.size > 1024**2 or "VALID" not in hdul:
            raise ValueError("FITS alineado inválido o demasiado grande.")
        if u.Unit(header.get("BUNIT", "")) != u.MJy / u.sr:
            raise ValueError("Se requiere brillo superficial en MJy/sr.")
        valid = np.asarray(hdul["VALID"].data) > 0
        if valid.shape != data.shape:
            raise ValueError("Máscara de dimensiones incompatibles.")
        data[~valid | ~np.isfinite(data)] = np.nan
    return data, WCS(header).celestial.to_header().tostring()


def combine(arrays, mode):
    cube = np.stack(arrays)
    if mode == "difference":
        data = cube[0] - cube[1]
        count = np.isfinite(cube).sum(axis=0)
    else:
        count = np.isfinite(cube).sum(axis=0)
        data = np.full(count.shape, np.nan)
        # Exigir dos muestras: los bordes de una sola exposición no son apilado.
        np.divide(np.nansum(cube, axis=0), count, out=data, where=count >= 2)
    return data, count


def preview(data, signed=False):
    valid = np.isfinite(data)
    if not valid.any():
        raise ValueError("No quedan píxeles válidos comunes para este modo.")
    rgba = np.zeros((*data.shape, 4), dtype=np.uint8)
    if signed:
        limit = float(np.percentile(np.abs(data[valid]), 99)) or 1.0
        value = np.zeros(data.shape)
        value[valid] = np.arcsinh(10 * np.clip(data[valid] / limit, -1, 1)) / np.arcsinh(10)
        # Cero blanco, positivo rojo y negativo azul, simétrico alrededor de cero.
        rgba[..., 0] = np.rint(255 * (1 + np.minimum(value, 0))).astype(np.uint8)
        rgba[..., 1] = np.rint(255 * (1 - np.abs(value))).astype(np.uint8)
        rgba[..., 2] = np.rint(255 * (1 - np.maximum(value, 0))).astype(np.uint8)
        limits = [-limit, limit]
    else:
        low, high = (float(v) for v in np.percentile(data[valid], [1, 99]))
        value = np.zeros(data.shape)
        value[valid] = .5 if high <= low else np.arcsinh(10 * np.clip((data[valid]-low)/(high-low), 0, 1)) / np.arcsinh(10)
        rgba[..., :3] = np.rint(value[..., None] * 255).astype(np.uint8)
        limits = [low, high]
    rgba[..., 3] = valid.astype(np.uint8) * 255
    output = io.BytesIO()
    Image.fromarray(np.flipud(rgba)).save(output, format="PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode(), limits


def analyze(root, manifest, request):
    indices = request.indices
    if len(set(indices)) != len(indices) or any(i < 0 or i >= len(manifest["frames"]) for i in indices):
        raise ValueError("Selecciona índices distintos dentro de la secuencia.")
    frames = [manifest["frames"][i] for i in indices]
    if request.mode == "difference" and len(indices) != 2:
        raise ValueError("La diferencia requiere exactamente dos imágenes: A − B.")
    if request.mode == "stack" and len(indices) < 2:
        raise ValueError("Selecciona al menos dos imágenes para apilar.")
    if request.mode != "lightcurve" and not all(compatible(a, b) for a, b in itertools.combinations(frames, 2)):
        raise ValueError("Las imágenes no tienen bandas compatibles en el centro, o falta información espectral. Selecciona otras.")
    if request.mode == "stack" and max(f["mjd"] for f in frames) - min(f["mjd"] for f in frames) > 7:
        raise ValueError("El apilado requiere una misma época exploratoria: intervalo máximo de siete días.")
    loaded = [read_frame(root, frame) for frame in frames]
    arrays = [item[0] for item in loaded]
    if any(a.shape != arrays[0].shape or wcs != loaded[0][1] for a, wcs in loaded):
        raise ValueError("Las rejillas WCS no coinciden.")
    warnings = ["Exploratorio: sin igualación de PSF, sustracción de fondo ni incertidumbres propagadas. No confirma variabilidad ni movimiento.",
                "Compatibilidad espectral aproximada solo en el centro: separación ≤ mitad del menor ancho. No garantiza equivalencia en todo el campo."]
    points = []
    for index, frame, data in zip(indices, frames, arrays):
        value = data[data.shape[0] // 2, data.shape[1] // 2]
        valid = bool(np.isfinite(value)) and frame.get("quality", {}).get("center_pixel_valid", True)
        points.append({"index": index, "mjd": frame["mjd"], "date_utc": frame["date_utc"],
                       "value": float(value) if valid else None,
                       "wavelength_um": frame.get("wavelength_at_target", {}).get("central_um"),
                       "reason": None if valid else "Píxel central enmascarado o sin cobertura"})
    result = {"mode": request.mode, "indices": indices, "unit": "MJy/sr", "warnings": warnings,
              "points": sorted(points, key=lambda p: p["mjd"])}
    if request.mode == "lightcurve":
        result["warnings"].append("Muestra un píxel fijo del cielo; no sigue al objeto ni mide flujo integrado. Las bandas pueden cambiar entre puntos; no se conectan con líneas.")
    else:
        data, count = combine(arrays, request.mode)
        image, limits = preview(data, request.mode == "difference")
        result.update(image=image, limits=limits, valid_fraction=float(np.isfinite(data).mean()),
                      contributors_min=int(count[np.isfinite(data)].min()), contributors_max=int(count.max()))
        if request.mode == "stack":
            result["warnings"].append("Media aritmética por píxel válido, con al menos dos contribuciones y un intervalo máximo de siete días. Puede difuminar movimiento o variaciones dentro de la época; la mejora de señal/ruido no está cuantificada.")
    return result
