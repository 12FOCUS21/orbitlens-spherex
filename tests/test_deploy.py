"""Comprobar empaquetado portable sin consultar servicios externos."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from prepare_deploy import prepare
from targets import PRESETS


class DeployTests(unittest.TestCase):
    def test_missing_presets_do_not_create_bundle(self):
        with tempfile.TemporaryDirectory() as folder, patch("prepare_deploy.JobManager") as factory:
            factory.return_value.presets = {}
            output = Path(folder) / "bundle"
            with self.assertRaises(ValueError):
                prepare(Path(folder), output)
            self.assertFalse(output.exists())

    def test_bundle_contains_only_registered_assets_and_portable_report(self):
        with tempfile.TemporaryDirectory() as folder, patch("prepare_deploy.JobManager") as factory:
            root = Path(folder)
            source = root / "source" / ("a" * 24)
            source.mkdir(parents=True)
            for name in ("manifest.json", "frame.png", "aligned.fits", "private.txt"):
                (source / name).write_text("fixture", encoding="utf-8")
            manager = factory.return_value
            manager.presets = {slug: {"result_id": slug, "target": {"name": slug}} for slug in PRESETS}
            manager.results = {slug: (source / "manifest.json", {"frames": [
                {"image": "frame.png", "aligned_fits": "aligned.fits"}]}) for slug in PRESETS}
            # Each preset normally has its own directory.
            for i, slug in enumerate(PRESETS):
                directory = root / "source" / f"{i:024x}"
                directory.mkdir()
                for name in ("manifest.json", "frame.png", "aligned.fits"):
                    (directory / name).write_text("fixture", encoding="utf-8")
                manager.results[slug] = (directory / "manifest.json", manager.results[slug][1])
            output = root / "bundle"
            prepare(root / "source", output)
            report = json.loads((output / "preset_verification.json").read_text(encoding="utf-8"))
            self.assertEqual(len(report["results"]), 5)
            self.assertFalse(list(output.rglob("private.txt")))
            for entry in report["results"]:
                self.assertFalse(Path(entry["manifest"]).is_absolute())
                self.assertTrue((output / entry["manifest"]).is_file())


if __name__ == "__main__":
    unittest.main()
