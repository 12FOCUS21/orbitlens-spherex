"""Prueba manual de la Etapa 1: consulta IRSA, inspecciona un FITS y genera una PNG.

Ejecutar: python test_data.py --help
Documentación: https://irsa.ipac.caltech.edu/data/SPHEREx/docs/cutout_tool.html
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from xml.etree import ElementTree

import httpx
import numpy as np
from astropy.io import fits
from astropy.io.votable import parse_single_table
from astropy.time import Time
from astropy.wcs import WCS
from PIL import Image


from archive_config import COLLECTIONS
SIA_URL = "https://irsa.ipac.caltech.edu/SIA"
MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ra", type=float, default=269.452, help="RA ICRS en grados")
    parser.add_argument("--dec", type=float, default=4.693, help="Dec ICRS en grados")
    parser.add_argument("--fov", type=float, default=5, help="Lado del recorte en arcmin (1–30)")
    parser.add_argument("--maxrec", type=int, default=100, help="Límite de filas por colección")
    parser.add_argument("--detector", choices=[f"SPHEREx-D{i}" for i in range(1, 7)])
    parser.add_argument("--output", type=Path, default=Path("data/raw/day1"))
    args = parser.parse_args()
    if not (math.isfinite(args.ra) and 0 <= args.ra < 360):
        parser.error("RA debe estar en [0, 360) grados.")
    if not (math.isfinite(args.dec) and -90 <= args.dec <= 90):
        parser.error("Dec debe estar en [-90, 90] grados.")
    if not 1 <= args.fov <= 30 or not 1 <= args.maxrec <= 10000:
        parser.error("FOV debe estar entre 1 y 30; MAXREC entre 1 y 10000.")
    return args


def parse_sia_votable(content: bytes, collection: str) -> list[dict]:
    # IRSA puede devolver cloud_access como JSON sin escapar en CSV.
    # VOTable conserva los límites de cada campo, incluidas las comas del JSON.
    try:
        root = ElementTree.fromstring(content)
    except ElementTree.ParseError as exc:
        raise ValueError("Respuesta SIA no es XML VOTable válido.") from exc
    for info in root.iter():
        if info.tag.rsplit("}", 1)[-1] == "INFO" and info.get("name") == "QUERY_STATUS":
            status = info.get("value", "").upper()
            if status == "ERROR":
                raise ValueError(f"SIA {collection}: {''.join(info.itertext()).strip()}")
            if status == "OVERFLOW":
                print(f"AVISO: {collection}: IRSA indica resultados truncados.", file=sys.stderr)
    table = parse_single_table(io.BytesIO(content)).to_table(use_names_over_ids=True)
    if "access_url" not in table.colnames:
        raise ValueError("VOTable SIA sin columna access_url.")

    def text_value(value) -> str:
        if np.ma.is_masked(value):
            return ""
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return str(value)

    # Mantener el contrato de cadenas del CSV local y del informe JSON.
    return [dict({name: text_value(row[name]) for name in table.colnames},
                 collection=collection) for row in table]


def query_collection(client: httpx.Client, collection: str, args: argparse.Namespace) -> list[dict]:
    # Un radio pequeño prioriza imágenes que contienen el centro solicitado.
    params = {"COLLECTION": collection, "POS": f"circle {args.ra} {args.dec} 0.001",
              "RESPONSEFORMAT": "VOTABLE", "MAXREC": args.maxrec}
    for attempt in range(3):
        try:
            response = client.get(SIA_URL, params=params)
            response.raise_for_status()
            # Conservar la respuesta exacta para diagnosticar cambios de formato.
            (args.output / f"query_{collection}.vot").write_bytes(response.content)
            rows = parse_sia_votable(response.content, collection)
            print(f"{collection}: {len(rows)} filas" +
                  (" (MAXREC alcanzado; lista posiblemente truncada)" if len(rows) >= args.maxrec else ""))
            return rows
        except (httpx.HTTPError, ValueError, csv.Error) as exc:
            if attempt == 2 or not retryable(exc):
                raise
            time.sleep(2 ** attempt)
    return []


def retryable(exc):
    """Reintentar transporte y fallos temporales, nunca 4xx permanentes."""
    return isinstance(exc, httpx.TransportError) or (
        isinstance(exc, httpx.HTTPStatusError) and
        exc.response.status_code in {408, 429, 500, 502, 503, 504})


def mjd_key(row: dict) -> float:
    try:
        value = float(row.get("t_min", ""))
        return value if math.isfinite(value) else math.inf
    except (TypeError, ValueError):
        return math.inf


def cutout_url(access_url: str, args: argparse.Namespace) -> str:
    parts = urlsplit(access_url)
    if parts.scheme != "https" or parts.hostname != "irsa.ipac.caltech.edu" or "/ibe/data/" not in parts.path:
        raise ValueError("access_url no es una URL HTTPS de imágenes on-premises de IRSA.")
    params = dict(parse_qsl(parts.query))
    params.update(center=f"{args.ra},{args.dec}", size=str(args.fov / 60))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(params), ""))


def download(client: httpx.Client, url: str, target: Path) -> None:
    # No se descarga nunca la URL original sin center/size; se limita el flujo.
    temporary = target.with_suffix(".part")
    try:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            size = 0
            with temporary.open("wb") as output:
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > MAX_DOWNLOAD_BYTES:
                        raise ValueError("El recorte excedió el límite de seguridad de 100 MiB.")
                    output.write(chunk)
        temporary.replace(target)
        print(f"Recorte descargado: {size:,} bytes")
    finally:
        temporary.unlink(missing_ok=True)


def inspect_and_export(path: Path, output: Path, args: argparse.Namespace) -> dict:
    with fits.open(path, memmap=False) as hdul:
        hdul.info()
        extensions = []
        for index, hdu in enumerate(hdul):
            data = hdu.data
            extensions.append({"index": index, "name": hdu.name,
                               "type": type(hdu).__name__,
                               "shape": list(data.shape) if data is not None else None,
                               "dtype": str(data.dtype) if data is not None else None,
                               "unit": hdu.header.get("BUNIT")})
        if "IMAGE" not in hdul:
            raise ValueError("No existe la extensión IMAGE; revisar la estructura impresa.")
        science = hdul["IMAGE"]
        image = np.asarray(science.data, dtype=np.float64)
        print(f"IMAGE: {image.ndim} dimensiones; shape={image.shape}")
        if image.ndim != 2:
            raise ValueError("IMAGE no es 2D. Revisar sus ejes antes de seleccionar una banda.")
        # Evitar mostrar un recorte desplazado si el servicio cambió el centro.
        wcs = WCS(science.header, hdul).celestial
        x, y = (float(value) for value in wcs.world_to_pixel_values(args.ra, args.dec))
        if not (math.isfinite(x) and math.isfinite(y) and
                -0.5 <= x < image.shape[1] - 0.5 and -0.5 <= y < image.shape[0] - 0.5):
            raise ValueError("El centro solicitado no está dentro de IMAGE según su WCS.")
        finite = np.isfinite(image)
        if not finite.any():
            raise ValueError("IMAGE no tiene píxeles finitos.")
        low, high = (float(value) for value in np.percentile(image[finite], [1, 99]))
        if high <= low:
            raise ValueError("IMAGE sin rango visual entre percentiles 1 y 99.")
        normalized = np.zeros(image.shape, dtype=np.float64)
        normalized[finite] = np.clip((image[finite] - low) / (high - low), 0, 1)
        pixels = np.rint(np.arcsinh(10 * normalized) / np.arcsinh(10) * 255).astype(np.uint8)
        # FITS tiene origen abajo; PNG arriba. No se reproyecta ni gira al norte.
        Image.fromarray(np.flipud(pixels)).save(output / "preview.png")
        flags = None
        if "FLAGS" in hdul and hdul["FLAGS"].data is not None:
            values = hdul["FLAGS"].data
            flags = {"shape": list(values.shape),
                     "nonzero_fraction": float(np.count_nonzero(values) / values.size) if values.size else None}
        return {"extensions": extensions, "image_ndim": image.ndim,
                "target_pixel_xy": [x, y], "unit": science.header.get("BUNIT"),
                "finite_fraction": float(finite.mean()), "flags": flags,
                "preview": {"percentiles": [1, 99], "limits": [low, high],
                            "stretch": "asinh", "asinh_factor": 10,
                            "vertical_flip": True, "reprojected": False,
                            "flags_mask_applied": False}}


def main() -> int:
    args = arguments()
    args.output.mkdir(parents=True, exist_ok=True)
    rows, errors = [], {}
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        for collection in COLLECTIONS:
            try:
                rows.extend(query_collection(client, collection, args))
            except (httpx.HTTPError, ValueError, csv.Error) as exc:
                errors[collection] = str(exc)
                print(f"AVISO: {collection}: {exc}", file=sys.stderr)
        rows.sort(key=mjd_key)
        fields = sorted({key for row in rows for key in row}) or ["collection", "access_url"]
        with (args.output / "query_results.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        report = {"queried_at_utc": datetime.now(timezone.utc).isoformat(),
                  "target": {"ra_deg": args.ra, "dec_deg": args.dec,
                             "frame": "ICRS", "fov_arcmin": args.fov},
                  "collections": list(COLLECTIONS), "maxrec_per_collection": args.maxrec,
                  "query_errors": errors, "row_count": len(rows),
                  "credit": "NASA/JPL-Caltech; SPHEREx data hosted by IRSA"}
        report_path = args.output / "inspection.json"
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        for row in rows:
            mjd = mjd_key(row)
            date = Time(mjd, format="mjd").isot if math.isfinite(mjd) else "fecha desconocida"
            print(f"{date} | MJD={row.get('t_min')} | {row['collection']} | "
                  f"{row.get('energy_bandpassname', '?')} | {row['access_url']}")
        candidates = [row for row in rows if row.get("access_url") and
                      (not args.detector or row.get("energy_bandpassname") == args.detector)]
        if not candidates:
            print("Sin imágenes candidatas. Consultar query_errors en inspection.json.", file=sys.stderr)
            return 1
        # Preferir QR3, luego las alternativas; ordenar por fecha dentro de cada una.
        selected = min(candidates, key=lambda row: (COLLECTIONS.index(row["collection"]), mjd_key(row)))
        url = cutout_url(selected["access_url"], args)
        report.update(selected_row=selected, cutout_url=url)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        path = args.output / "cutout.fits"
        download(client, url, path)
        report.update(inspect_and_export(path, args.output, args))
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Listo: {args.output.resolve()} (FITS, PNG, CSV e informe JSON).")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (httpx.HTTPError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
