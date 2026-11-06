"""Verificar los tres modos con los cinco presets distribuidos (sin red)."""
import base64
import io
import json
from pathlib import Path

import numpy as np
from PIL import Image
from analysis_modes import AnalysisInput, analyze

bundle = Path(__file__).resolve().parent / "demo/cache"
expected = {"barnard": 0, "rw-aur": 0, "r-dra": 0, "epsilon-indi-b": 10, "wise0855": 12}
entries = json.loads((bundle / "preset_verification.json").read_text())["results"]
assert sorted(entry["preset"] for entry in entries) == sorted(expected)
for entry in entries:
    preset = entry["preset"]
    path = bundle / entry["manifest"]
    manifest = json.loads(path.read_text())
    def run(mode, indices):
        return analyze(path.parent, manifest, AnalysisInput(mode=mode, indices=indices))
    curve = run("lightcurve", list(range(len(manifest["frames"]))))
    valid = sum(point["value"] is not None for point in curve["points"])
    assert valid == expected[preset], (preset, valid)
    print(preset, "centros válidos:", valid, "/", len(curve["points"]))
    if preset == "barnard":
        def pixels(indices):
            data = run("difference", indices)["image"].split(",", 1)[1]
            return np.asarray(Image.open(io.BytesIO(base64.b64decode(data))))
        a, b = pixels([0, 6]), pixels([6, 0])
        assert np.array_equal(a[:, :, [2, 1, 0, 3]], b)
        assert np.any(a[:, :, 3] == 0) and np.any(a[:, :, 3] == 255)
        print("Diferencia 1 y 7: inversión de signo y transparencia verificadas")
    if preset == "rw-aur":
        stack = run("stack", [0, 1])
        assert stack["contributors_min"] == stack["contributors_max"] == 2
        print("Pila 1 y 2: cobertura", round(stack["valid_fraction"] * 100, 2), "%")
