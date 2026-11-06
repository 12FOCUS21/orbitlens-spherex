"""Etapa 2: construir una secuencia real o verificar los cinco objetos del reto."""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

from spherex_pipeline import PipelineConfig, build_sequence, fingerprint, write_json
from targets import PRESETS, resolve_target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--preset", choices=list(PRESETS))
    target.add_argument("--name", help="Identificador SIMBAD")
    target.add_argument("--ra", type=float, help="RA ICRS en grados, sin propagación de movimiento")
    target.add_argument("--verify-presets", action="store_true", help="Procesa los cinco objetos; puede tardar varios minutos")
    parser.add_argument("--dec", type=float)
    parser.add_argument("--epoch", type=float, default=2026.5, help="Época juliana del centro resuelto en SIMBAD")
    parser.add_argument("--fov", type=float, default=5)
    parser.add_argument("--frames", type=int, default=12)
    parser.add_argument("--maxrec", type=int, default=1000)
    parser.add_argument("--detector", choices=[f"SPHEREx-D{i}" for i in range(1, 7)])
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw"))
    parser.add_argument("--cache-root", type=Path, default=Path("data/cache"))
    parser.add_argument("--refresh", action="store_true", help="Reconsulta y descarga de nuevo; conserva las secuencias previas")
    args = parser.parse_args()
    if (args.ra is None) != (args.dec is None):
        parser.error("--ra y --dec deben usarse juntos.")
    targets = list(PRESETS.items()) if args.verify_presets else [
        (args.preset or ("custom" if args.name or args.ra is not None else "barnard"),
         args.name or PRESETS.get(args.preset or "barnard"))]
    results = []
    args.cache_root.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=60, follow_redirects=True) as client:
        for slug, name in targets:
            print(f"\nProcesando: {slug}", flush=True)
            try:
                if args.ra is not None:
                    target_info = {"name": "Coordenadas del usuario", "ra_deg": args.ra,
                                   "dec_deg": args.dec, "proper_motion_applied": False,
                                   "coordinate_epoch_jyear": None}
                else:
                    resolution_dir = args.raw_root / "targets"
                    resolution_dir.mkdir(parents=True, exist_ok=True)
                    resolution_path = resolution_dir / f"{fingerprint({'name': name, 'epoch': args.epoch})}.json"
                    if resolution_path.exists() and not args.refresh:
                        target_info = json.loads(resolution_path.read_text(encoding="utf-8"))
                    else:
                        target_info = resolve_target(client, name, args.epoch)
                        target_info["retrieved_at_utc"] = datetime.now(timezone.utc).isoformat()
                        write_json(resolution_path, target_info)
                config = PipelineConfig(ra=target_info["ra_deg"], dec=target_info["dec_deg"],
                                        fov=args.fov, frames=args.frames, detector=args.detector,
                                        maxrec=args.maxrec)
                path = build_sequence(config, raw_root=args.raw_root, cache_root=args.cache_root,
                                      refresh=args.refresh, client=client)
                manifest = json.loads(path.read_text(encoding="utf-8"))
                # Identidad y época quedan junto a la secuencia sin cambiar el centro WCS.
                write_json(path.parent / "target.json", target_info)
                collections = sorted({frame["collection"] for frame in manifest["frames"]})
                result = {"preset": slug, "target": target_info, "status": manifest["status"],
                          "manifest": str(path.resolve()), "detector": manifest["detector"],
                          "collections": collections, "frame_count": len(manifest["frames"]),
                          "queries": manifest["queries"], "failures": manifest["failures"]}
                print(f"{manifest['status']}: {len(manifest['frames'])} frames. Manifiesto: {path.resolve()}")
                for warning in manifest.get("warnings", []):
                    print(f"AVISO: {warning}")
                if manifest["frames"]:
                    print(f"Vista previa: {(path.parent / 'preview.gif').resolve()}")
            except (httpx.HTTPError, OSError, ValueError, KeyError) as exc:
                result = {"preset": slug, "status": "error", "error": str(exc)}
                print(f"ERROR: {exc}", file=sys.stderr)
            results.append(result)
    if args.verify_presets:
        report_path = args.cache_root / "preset_verification.json"
        write_json(report_path, {"created_at_utc": datetime.now(timezone.utc).isoformat(), "results": results,
                                 "scope": "Cobertura y pipeline; no confirma identificación ni movimiento del objeto."})
        print(f"Informe de presets: {report_path.resolve()}")
    return 0 if all(item["status"] == "ready" for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
