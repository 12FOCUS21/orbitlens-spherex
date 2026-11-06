"""Preparar presets portables sin red; ejecutar antes de publicar el código."""
import argparse
import json
import shutil
from pathlib import Path

from api import JobManager
from targets import PRESETS


def prepare(source: Path, destination: Path):
    manager = JobManager(source.parent / "raw", source)
    manager.load_cache()
    if set(manager.presets) != set(PRESETS):
        raise ValueError("Se necesitan los cinco presets completos y compatibles.")
    if destination.exists():
        raise ValueError("El destino ya existe; elige otro directorio para no sobrescribirlo.")
    entries = []
    destination.mkdir(parents=True)
    for slug, preset in manager.presets.items():
        path, manifest = manager.results[preset["result_id"]]
        target = destination / path.parent.name
        target.mkdir()
        for name in {"manifest.json"} | {frame[key] for frame in manifest["frames"]
                                       for key in ("image", "aligned_fits")}:
            relative = Path(name)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("Ruta de artefacto inválida.")
            output = target / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path.parent / relative, output)
        entries.append({"preset": slug, "target": preset["target"],
                        "manifest": f"{target.name}/manifest.json"})
    (destination / "preset_verification.json").write_text(
        json.dumps({"results": entries}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Cinco presets preparados en {destination.resolve()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("data/cache"))
    parser.add_argument("--output", type=Path, default=Path("demo/cache"))
    args = parser.parse_args()
    prepare(args.source, args.output)
