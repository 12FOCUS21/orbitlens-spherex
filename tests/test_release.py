"""El smoke de entrega comprueba la distribución sin modificar datos originales."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from verify_release import BASE, verify_release


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.bundle = BASE / "demo/cache"
        # Frontend mínimo controlado: la suite no depende de un build previo.
        self.frontend = self.root / "frontend"
        self.frontend.mkdir()
        (self.frontend / "index.html").write_text('<html><link href="/app.css" rel="stylesheet"><script src="/app.js"></script></html>')
        (self.frontend / "app.js").write_text('console.log("fixture")')
        (self.frontend / "app.css").write_text('body{margin:0}')
        (self.frontend / "catalogos.html").write_text('<html>fixture</html>')

    def test_smoke_checks_bundle_concurrency_repeated_cache_and_local_quota(self):
        originals = {path: (path.read_bytes(), path.stat().st_mtime_ns)
                     for path in self.bundle.rglob("*") if path.is_file()}
        report = verify_release(self.bundle, self.frontend)
        self.assertEqual(report["status"], "ok")
        self.assertEqual((report["png"], report["fits"], report["gif"], report["targets"]), (60, 60, 5, 5))
        self.assertEqual(report["concurrent_visitors"], 10)
        self.assertEqual(report["repeated_searches"], 4)
        for path, (content, stamp) in originals.items():
            self.assertEqual(path.read_bytes(), content)
            self.assertEqual(path.stat().st_mtime_ns, stamp)

    def test_missing_bundle_fails_with_clear_message(self):
        with self.assertRaisesRegex(ValueError, "informe del bundle"):
            verify_release(self.root / "absent", self.frontend)

    def test_missing_frontend_fails_with_actionable_message(self):
        with self.assertRaisesRegex(ValueError, "web/index.html"):
            verify_release(self.bundle, self.root / "absent")

    def test_missing_auxiliary_artifact_cannot_pass_smoke(self):
        bundle = self.root / "bundle"
        shutil.copytree(self.bundle, bundle)
        entry = json.loads((bundle / "preset_verification.json").read_text())["results"][0]
        ((bundle / entry["manifest"]).parent / "preview.gif").unlink()
        with self.assertRaises((ValueError, KeyError)):
            verify_release(bundle, self.frontend)
