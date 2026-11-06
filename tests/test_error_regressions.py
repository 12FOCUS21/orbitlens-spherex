"""Fallos del informe de auditoría: regresiones locales, sin servicios externos."""
import argparse
import io
import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
from astropy.io import fits
from astropy.io.fits.verify import VerifyError
from fastapi import HTTPException
from fastapi.testclient import TestClient
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from api import JobManager, SearchInput, config_key, create_app
from coordinates import parse_coordinates
from disk_cache import trim
from prepare_deploy import prepare
from spherex_pipeline import (COLLECTIONS, PipelineConfig, align_cutout, build_sequence,
                              cached_cutout, common_grid, fingerprint, query_observations, sequence_key)
from test_api import fixture
from test_data import query_collection
from test_pipeline import observation, synthetic_fits, votable


class ErrorRegressions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.raw, self.cache = self.root / "raw", self.root / "cache"

    def app(self):
        return create_app(raw_root=self.raw, cache_root=self.cache, frontend_root=self.root / "absent")

    def test_invalid_vot_never_published_and_next_request_recovers(self):
        args = argparse.Namespace(ra=10, dec=20, maxrec=10, output=self.root)
        bodies = iter([b"<html>error</html>", b"<VOTABLE>", votable([], ["access_url"])])
        with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=next(bodies)))) as client:
            for _ in range(2):
                with self.assertRaises(ValueError):
                    query_collection(client, COLLECTIONS[0], args)
                self.assertFalse(list(self.root.glob("*.vot")))
                self.assertFalse(list(self.root.glob("*.part")))
            self.assertEqual(query_collection(client, COLLECTIONS[0], args), [])
        self.assertEqual(len(list(self.root.glob("*.vot"))), 1)

    def test_poisoned_query_cache_refetches_all_collections(self):
        config = PipelineConfig(10, 20)
        directory = self.raw / "queries" / fingerprint({"ra": 10, "dec": 20, "maxrec": 1000})
        directory.mkdir(parents=True)
        for collection in COLLECTIONS:
            (directory / f"query_{collection}.vot").write_bytes(b"<html>unavailable</html>")
        calls = []
        def handler(request):
            calls.append(request)
            return httpx.Response(200, content=votable([], ["access_url"]))
        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            rows, metadata = query_observations(client, config, self.raw)
            self.assertEqual(rows, [])
            self.assertTrue(all("error" not in value for value in metadata.values()))
            query_observations(client, config, self.raw)
        self.assertEqual(len(calls), len(COLLECTIONS))

    def test_empty_flags_rejected_as_value_error(self):
        path = self.root / "bad.fits"
        with fits.open(io.BytesIO(synthetic_fits())) as hdul:
            hdul["FLAGS"].data = None
            hdul.writeto(path)
        config = PipelineConfig(10, 20, fov=1)
        with self.assertRaisesRegex(ValueError, "FLAGS"):
            align_cutout(path, config, *common_grid(config))

    def test_defective_cutout_cache_is_replaced(self):
        url = "https://irsa.ipac.caltech.edu/mock"
        self.raw.mkdir()
        path = self.raw / f"{fingerprint(url)}.fits"
        for defect in ("flags", "dimensions", "unit", "wcs"):
            with self.subTest(defect=defect), fits.open(io.BytesIO(synthetic_fits())) as hdul:
                if defect == "flags":
                    hdul["FLAGS"].data = None
                elif defect == "dimensions":
                    hdul["IMAGE"].data = hdul["IMAGE"].data[0]
                elif defect == "unit":
                    hdul["IMAGE"].header["BUNIT"] = "Jy"
                else:
                    del hdul["IMAGE"].header["CTYPE1"]
                    del hdul["IMAGE"].header["CTYPE2"]
                hdul.writeto(path, overwrite=True)
                with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, content=synthetic_fits()))) as client:
                    self.assertEqual(cached_cutout(client, url, self.raw, False), path)
                self.assertEqual(path.read_bytes(), synthetic_fits())

    def test_bad_frame_does_not_abort_accepted_frames(self):
        rows = [observation(i) for i in range(4)]
        config = PipelineConfig(10, 20, fov=1, frames=3)
        good = self.root / "good.fits"
        good.write_bytes(synthetic_fits())
        bad = self.root / "bad.fits"
        with fits.open(io.BytesIO(synthetic_fits())) as hdul:
            hdul["FLAGS"].data = None
            hdul.writeto(bad)
        with (httpx.Client() as client,
              patch("spherex_pipeline.query_observations", return_value=(rows, {})),
              patch("spherex_pipeline.cached_cutout", side_effect=[good, bad, good, good])):
            path = build_sequence(config, raw_root=self.raw, cache_root=self.cache, client=client)
        manifest = json.loads(path.read_text())
        self.assertEqual(manifest["status"], "ready")
        self.assertEqual(len(manifest["frames"]), 3)
        self.assertEqual(len(manifest["failures"]), 1)

    def test_verify_error_returns_422_and_releases_limits(self):
        path = fixture(self.cache)
        app = self.app()
        with TestClient(app) as client, patch("analysis_modes.fits.open", side_effect=VerifyError("C:/private/file.fits")):
            response = client.post(f"/api/results/{path.parent.name}/analysis", json={"mode": "lightcurve", "indices": [0]})
            self.assertEqual(response.status_code, 422)
            self.assertNotIn("private", response.text)
            self.assertEqual(app.state.manager.analysis_count, 0)
            self.assertFalse(app.state.manager.analysis_owners)

    def test_boolean_search_fields_rejected(self):
        with TestClient(self.app()) as client:
            for field in ("ra", "dec", "fov", "frames"):
                for value in (True, False):
                    with self.subTest(field=field, value=value):
                        body = {"ra": 10, "dec": 20, field: value}
                        self.assertEqual(client.post("/api/search", json=body).status_code, 422)

    def test_shared_cache_key_includes_mask_policy(self):
        config = PipelineConfig(10, 20)
        old = config_key(config)
        self.assertEqual(old, sequence_key(config))
        with patch("spherex_pipeline.MASK_BITS", (0,)):
            self.assertNotEqual(config_key(config), old)
            path = fixture(self.cache)
            with self.assertRaises(ValueError):
                JobManager(self.raw, self.cache).register(path)

    def test_incomplete_manifests_never_mutate_indexes(self):
        path = fixture(self.cache)
        original = json.loads(path.read_text())
        for field in ("schema_version", "parameters", "queries", "caveats", "failures", "quality", "wavelength_at_target"):
            value = json.loads(json.dumps(original))
            del (value["frames"][0] if field in ("quality", "wavelength_at_target") else value)[field]
            path.write_text(json.dumps(value))
            manager = JobManager(self.raw, self.cache)
            with self.subTest(field=field), self.assertRaises(ValueError):
                manager.register(path)
            self.assertFalse(manager.results)
            self.assertFalse(manager.cache)

    def test_manifest_hides_private_error_details(self):
        path = fixture(self.cache)
        value = json.loads(path.read_text())
        value["queries"] = {"test": {"error": "C:\\secret\\queries\\bad.vot"}}
        value["failures"] = [{"error": "/private/cutouts/file.fits"}]
        value["frames"][0]["wavelength_at_target"]["error"] = "C:/secret/wcs"
        path.write_text(json.dumps(value))
        with TestClient(self.app()) as client:
            response = client.get(f"/api/results/{path.parent.name}/manifest")
            self.assertEqual(response.status_code, 200)
            self.assertNotIn("secret", response.text)
            self.assertNotIn("private", response.text)

    def test_missing_result_directory_not_recreated(self):
        path = fixture(self.cache)
        manager = JobManager(self.raw, self.cache)
        manager.register(path)
        shutil.rmtree(path.parent)
        with self.assertRaises(HTTPException) as caught:
            manager.touch(path.parent.name)
        self.assertEqual(caught.exception.status_code, 404)
        self.assertFalse(path.parent.exists())
        self.assertFalse(manager.results)
        self.assertFalse(manager.cache)

    def test_cleanup_includes_targets_day1_and_parts(self):
        for name in ("targets/a.json", "day1/frame.fits", "cutouts/download.part", "queries/loose.part"):
            path = self.raw / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"old")
            os.utime(path, (time.time() - 7200,) * 2)
        _, size = trim(self.raw, self.cache, set(), 0)
        self.assertEqual(size, 0)

    def test_sexagesimal_overflow_rejected(self):
        for ra, dec in (("12:60:00", 0), ("12:00:60", 0), (0, "10:60:00"), (0, "10:00:60")):
            with self.subTest(ra=ra, dec=dec), self.assertRaises(ValueError):
                parse_coordinates(ra, dec)

    def test_even_grid_request_has_exact_center_pixel(self):
        wcs, shape = common_grid(PipelineConfig(10, 20, fov=4))
        self.assertEqual(shape, (41, 41))
        ra, dec = wcs.pixel_to_world_values(shape[1] // 2, shape[0] // 2)
        self.assertAlmostEqual(float(ra), 10)
        self.assertAlmostEqual(float(dec), 20)

    def test_negative_cache_expires_without_touch_extending_ttl(self):
        path = fixture(self.cache, status="empty", count=0)
        manager = JobManager(self.raw, self.cache)
        manager.register(path)
        job = manager.submit(SearchInput(ra=10, dec=20), "ip")
        self.assertTrue(job["cached"])
        self.assertEqual(job["status"], "empty")
        os.utime(path, (time.time() - 61,) * 2)
        self.assertIsNone(manager.cached_result(config_key(PipelineConfig(10, 20))))

    def test_small_complete_sequences_ready_and_reused(self):
        for count in (1, 2):
            config = PipelineConfig(10, 20, fov=1, frames=count)
            rows = [observation(i) for i in range(count)]
            good = self.root / "good.fits"
            good.write_bytes(synthetic_fits())
            with (httpx.Client() as client,
                  patch("spherex_pipeline.query_observations", return_value=(rows, {})),
                  patch("spherex_pipeline.cached_cutout", return_value=good)):
                path = build_sequence(config, raw_root=self.raw, cache_root=self.cache, client=client)
                self.assertEqual(json.loads(path.read_text())["status"], "ready")
                self.assertEqual(build_sequence(config, raw_root=self.raw, cache_root=self.cache, client=client), path)
                self.assertTrue((path.parent / "target.json").exists())

    def test_negative_pipeline_cache_reuses_latest_retry(self):
        config = PipelineConfig(10, 20)
        with httpx.Client() as client, patch("spherex_pipeline.query_observations", return_value=([], {})) as query:
            first = build_sequence(config, raw_root=self.raw, cache_root=self.cache, client=client)
            os.utime(first, (time.time() - 61,) * 2)
            second = build_sequence(config, raw_root=self.raw, cache_root=self.cache, client=client)
            self.assertNotEqual(first, second)
            self.assertEqual(build_sequence(config, raw_root=self.raw, cache_root=self.cache, client=client), second)
            self.assertEqual(query.call_count, 2)

    def test_trusted_proxy_separates_clients_and_ignores_untrusted_headers(self):
        path = fixture(self.cache)
        for trusted in ("10.0.0.1", "127.0.0.1"):
            app = create_app(raw_root=self.raw, cache_root=self.cache, frontend_root=self.root / "absent", per_minute=1)
            proxy = ProxyHeadersMiddleware(app, trusted_hosts=trusted)
            with TestClient(proxy, client=("10.0.0.1", 1234)) as client:
                body = {"ra": 10, "dec": 20}
                self.assertEqual(client.post("/api/search", json=body, headers={"x-forwarded-for": "203.0.113.1"}).status_code, 202)
                response = client.post("/api/search", json=body, headers={"x-forwarded-for": "203.0.113.2"})
                self.assertEqual(response.status_code, 202 if trusted == "10.0.0.1" else 429)

    def test_bundle_preparation_is_repeatable_and_has_all_referenced_artifacts(self):
        source = Path(__file__).resolve().parents[1] / "demo/cache"
        output = self.root / "bundle"
        prepare(source, output)
        prepare(source, output)
        report = json.loads((output / "preset_verification.json").read_text())
        for entry in report["results"]:
            directory = (output / entry["manifest"]).parent
            self.assertTrue((directory / "preview.gif").is_file())
            self.assertTrue((directory / "target.json").is_file())
        marker = output / report["results"][0]["manifest"]
        marker.write_text("user work")
        with self.assertRaises(ValueError):
            prepare(source, output)
        self.assertEqual(marker.read_text(), "user work")
        prepare(source, output, force=True)

    def test_preview_and_target_routes(self):
        path = fixture(self.cache)
        value = json.loads(path.read_text())
        value["preview"] = {"image": "preview.gif"}
        path.write_text(json.dumps(value))
        (path.parent / "preview.gif").write_bytes(b"GIF89a")
        (path.parent / "target.json").write_text('{"ra_deg":10,"dec_deg":20}')
        with TestClient(self.app()) as client:
            base = f"/api/results/{path.parent.name}"
            self.assertEqual(client.get(base + "/preview.gif").content, b"GIF89a")
            self.assertEqual(client.get(base + "/target.json").json()["ra_deg"], 10)
