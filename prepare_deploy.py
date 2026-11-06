"""Preparar presets portables sin red; ejecutar antes de publicar el código."""
import argparse
import json
import shutil
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

from api import JobManager
from targets import PRESETS


def prepare(source: Path, destination: Path, force=False):
    """Preparación repetible: completar archivos ausentes, nunca pisar diferencias sin --force."""
    with tempfile.TemporaryDirectory(prefix="orbitlens-bundle-") as temporary:
        staged = Path(temporary) / "cache"
        _prepare(source, staged)
        files = [path for path in staged.rglob("*") if path.is_file()]
        for path in files:
            output = destination / path.relative_to(staged)
            if output.exists() and (not output.is_file() or output.read_bytes() != path.read_bytes()) and not force:
                raise ValueError("El destino contiene archivos diferentes; usa otro --output o --force para actualizarlos.")
        for path in files:
            output = destination / path.relative_to(staged)
            output.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, output)
    print(f"Cinco presets preparados en {destination.resolve()}")


def _prepare(source: Path, destination: Path):
    manager = JobManager(source.parent / "raw", source)
    manager.load_cache()
    if set(manager.presets) != set(PRESETS):
        raise ValueError("Se necesitan los cinco presets completos y compatibles.")
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
        (target / "target.json").write_text(
            json.dumps(preset["target"], ensure_ascii=False, indent=2), encoding="utf-8")
        if "preview" in manifest:
            if manifest["preview"]["image"] != "preview.gif":
                raise ValueError("Ruta de vista previa inválida.")
            if (path.parent / "preview.gif").is_file():
                shutil.copyfile(path.parent / "preview.gif", target / "preview.gif")
            else:
                # Cachés antiguas: reconstruir el auxiliar QA sin consultar IRSA.
                panels = []
                for frame in manifest["frames"]:
                    with Image.open(target / frame["image"]) as image:
                        size = max(256, image.width)
                        panel = Image.new("RGB", (size, size + 40), "#181818")
                        rgba = image.convert("RGBA").resize((size, size), Image.Resampling.NEAREST)
                        panel.paste(rgba, (0, 0), rgba.getchannel("A"))
                        draw = ImageDraw.Draw(panel)
                        draw.text((4, size + 5), f"{frame['date_utc'][:10]}  {frame['detector']}", fill="white")
                        if not frame["quality"]["center_pixel_valid"]:
                            draw.text((4, size + 22), "CENTER MASKED", fill="#ffbc7b")
                        panels.append(panel)
                panels[0].save(target / "preview.gif", save_all=True, append_images=panels[1:],
                               duration=manifest["preview"].get("frame_duration_ms", 500), loop=0, disposal=2)
        entries.append({"preset": slug, "target": preset["target"],
                        "manifest": f"{target.name}/manifest.json"})
    (destination / "preset_verification.json").write_text(
        json.dumps({"results": entries}, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("data/cache"))
    parser.add_argument("--output", type=Path, default=Path("demo/cache"))
    parser.add_argument("--force", action="store_true", help="Actualizar artefactos diferentes; no borra archivos ajenos al bundle.")
    args = parser.parse_args()
    prepare(args.source, args.output, args.force)
