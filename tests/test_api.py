"""Pruebas de API sin SIMBAD/IRSA: datos pequeños y constructor controlado."""

import asyncio
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from api import JobManager, SearchInput, config_key, create_app
from coordinates import parse_coordinates
from spherex_pipeline import PIPELINE_VERSION, PipelineConfig, MASK_BITS, COLLECTIONS


def fixture(root, config=None, status="ready", count=3):
    config = config or PipelineConfig(10, 20)
    result_id = config_key(config)
    directory = root / result_id
    (directory / "frames").mkdir(parents=True, exist_ok=True)
    (directory / "aligned").mkdir(exist_ok=True)
    frames = []
    for index in range(count):
        image, fits = f"frames/{index:03d}.png", f"aligned/{index:03d}.fits"
        (directory / image).write_bytes(b"mock-png")
        (directory / fits).write_bytes(b"mock-fits")
        frames.append({"image": image, "aligned_fits": fits, "mjd": 61000 + index,
                       "date_utc": "2026-01-01T00:00:00", "detector": "SPHEREx-D1",
                       "collection": COLLECTIONS[0], "cutout_url": "https://irsa.ipac.caltech.edu/",
                       "quality": {"valid_coverage": 1.0, "center_pixel_valid": True, "center_pixel_flag_names": []},
                       "wavelength_at_target": {"central_um": None, "width_um": None}})
    from dataclasses import asdict
    value = {"pipeline_version": PIPELINE_VERSION, "status": status, "schema_version": 1,
             "created_at_utc": "2026-01-01T00:00:00", "credit": "NASA/JPL-Caltech; IRSA",
             "collections": list(COLLECTIONS), "quality_policy": {"mask_bits": list(MASK_BITS)},
             "parameters": asdict(config), "frames": frames, "warnings": ["Centro enmascarado"],
             "caveats": ["No confirma detección"], "queries": {}, "failures": []}
    path = directory / "manifest.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def wait_for_job(client, job_id):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        value = client.get(f"/api/status/{job_id}").json()
        if value["status"] in {"ready", "partial", "error", "empty"}:
            return value
        time.sleep(0.01)
    raise AssertionError("El trabajo no terminó en cinco segundos.")


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.cache, self.raw = self.root / "cache", self.root / "raw"

    def app(self, **kwargs):
        return create_app(cache_root=self.cache, raw_root=self.raw,
                          frontend_root=self.root / "no-build", **kwargs)

    def test_decimal_and_sexagesimal_and_invalid_ranges(self):
        self.assertEqual(parse_coordinates(0, 90), (0.0, 90.0))
        self.assertEqual(parse_coordinates(0, -90), (0.0, -90.0))
        self.assertEqual(parse_coordinates("133.795", "-7.245"), (133.795, -7.245))
        ra, dec = parse_coordinates("08h55m10.831s", "-07d14m42.53s")
        self.assertAlmostEqual(ra, 133.7951291667, places=8)
        self.assertAlmostEqual(dec, -7.2451472222, places=8)
        self.assertAlmostEqual(parse_coordinates("08:55:10.831", "-07:14:42.53")[0], ra)
        self.assertAlmostEqual(parse_coordinates("133d47m42.465s", "-07d14m42.53s")[0], ra)
        for first, second in [("nan", 0), (360, 0), (-1, 0), (0, 91), ("abc", 0), ("25h", 0)]:
            with self.subTest(ra=first, dec=second), self.assertRaises(ValueError):
                parse_coordinates(first, second)

    def test_invalid_requests_and_unknown_routes(self):
        with TestClient(self.app()) as client:
            for body in [{}, {"ra": 1}, {"ra": 360, "dec": 0}, {"name": " "},
                         {"preset": "unknown"}, {"name": "x", "ra": 1, "dec": 2},
                         {"ra": 1, "dec": 2, "frames": 17}, {"ra": 1, "dec": 2, "frames": 1.5},
                         {"ra": 1, "dec": 2, "detector": "D1"}, {"name": "x", "fov": 31}]:
                with self.subTest(body=body):
                    self.assertEqual(client.post("/api/search", json=body).status_code, 422)
            self.assertEqual(client.get("/api/status/unknown").status_code, 404)
            self.assertEqual(client.get("/api/unknown").status_code, 404)
            self.assertEqual(client.get("/").status_code, 503)

    def test_cache_first_and_only_registered_assets_are_public(self):
        path = fixture(self.cache)
        def forbidden(*args, **kwargs):
            raise AssertionError("Una secuencia cacheada no debe tocar la red.")
        with TestClient(self.app(builder=forbidden, resolver=forbidden)) as client:
            response = client.post("/api/search", json={"ra": 10, "dec": 20})
            self.assertEqual(response.status_code, 202)
            job = response.json()
            self.assertEqual(job["status"], "ready")
            self.assertTrue(job["cached"])
            manifest = client.get(job["manifest_url"]).json()
            self.assertEqual(manifest["warnings"], ["Centro enmascarado"])
            self.assertEqual(client.get(manifest["frames"][0]["image_url"]).content, b"mock-png")
            self.assertEqual(client.get(manifest["frames"][0]["fits_url"]).content, b"mock-fits")
            self.assertEqual(client.get(f"/api/results/{path.parent.name}/frames/-1.png").status_code, 404)
            self.assertEqual(client.get("/api/results/not-a-key/manifest").status_code, 404)
            self.assertEqual(client.get("/data/raw/secret").status_code, 404)

    def test_cached_presets_load_report_without_absolute_path_dependency(self):
        path = fixture(self.cache)
        target = {"name": "Barnard's Star", "ra_deg": 10, "dec_deg": 20}
        (self.cache / "preset_verification.json").write_text(json.dumps({"results": [
            {"preset": "barnard", "manifest": f"C:\\old-workspace\\data\\cache\\{path.parent.name}\\manifest.json", "target": target}
        ]}), encoding="utf-8")
        with TestClient(self.app()) as client:
            self.assertEqual(client.get("/api/health").json()["cached_presets"], 1)
            self.assertTrue(client.get("/api/presets").json()[0]["cached"])
            self.assertEqual(client.post("/api/search", json={"preset": "barnard"}).json()["status"], "ready")

    def test_post_returns_before_compute_and_polling_remains_responsive(self):
        started, release = threading.Event(), threading.Event()
        def builder(config, **kwargs):
            started.set()
            if not release.wait(5):
                raise AssertionError("No se liberó el constructor.")
            return fixture(self.cache, config)
        with TestClient(self.app(builder=builder)) as client:
            try:
                response = client.post("/api/search", json={"ra": 11, "dec": 20})
                self.assertEqual(response.status_code, 202)
                self.assertTrue(started.wait(2))
                self.assertEqual(client.get("/api/health").status_code, 200)
                self.assertEqual(client.get(f"/api/status/{response.json()['job_id']}").json()["status"], "searching")
            finally:
                release.set()
            self.assertEqual(wait_for_job(client, response.json()["job_id"])["status"], "ready")

    def test_same_search_joins_job_and_per_ip_limit_releases_on_completion(self):
        release = threading.Event()
        def builder(config, **kwargs):
            release.wait(5)
            return fixture(self.cache, config)
        with TestClient(self.app(builder=builder)) as client:
            try:
                first = client.post("/api/search", json={"ra": 11, "dec": 20}).json()
                second = client.post("/api/search", json={"ra": 11, "dec": 20}).json()
                self.assertEqual(first["job_id"], second["job_id"])
                other = client.post("/api/search", json={"ra": 12, "dec": 20}).json()
                rejected = client.post("/api/search", json={"ra": 13, "dec": 20})
                self.assertEqual(rejected.status_code, 429)
                self.assertIn("Retry-After", rejected.headers)
            finally:
                release.set()
            wait_for_job(client, first["job_id"]); wait_for_job(client, other["job_id"])
            self.assertEqual(client.post("/api/search", json={"ra": 13, "dec": 20}).status_code, 202)

    def test_rate_limit_applies_to_cached_searches_too(self):
        fixture(self.cache)
        with TestClient(self.app(per_minute=2)) as client:
            for _ in range(2):
                self.assertEqual(client.post("/api/search", json={"ra": 10, "dec": 20}).status_code, 202)
            self.assertEqual(client.post("/api/search", json={"ra": 10, "dec": 20}).status_code, 429)

    def test_name_resolution_is_cached_and_target_coordinates_reach_pipeline(self):
        calls = []
        def resolver(client, name, epoch):
            calls.append(name)
            return {"name": name, "ra_deg": 42.5, "dec_deg": -15.25,
                    "coordinate_epoch_jyear": epoch}
        def builder(config, **kwargs):
            self.assertEqual((config.ra, config.dec), (42.5, -15.25))
            return fixture(self.cache, config)
        with TestClient(self.app(resolver=resolver, builder=builder)) as client:
            for fov in [5, 6]:
                first = client.post("/api/search", json={"name": "Synthetic star", "fov": fov}).json()
                job = wait_for_job(client, first["job_id"])
                self.assertEqual(job["status"], "ready")
                self.assertEqual(job["target"]["coordinate_epoch_jyear"], 2026.5)
            self.assertEqual(calls, ["Synthetic star"])

    def test_partial_empty_error_are_preserved(self):
        for status, count in [("partial", 2), ("empty", 0), ("error", 0)]:
            with self.subTest(status=status):
                def builder(config, **kwargs):
                    return fixture(self.cache, config, status, count)
                with TestClient(self.app(builder=builder)) as client:
                    response = client.post("/api/search", json={"ra": 15 + count + (status == "error"), "dec": 25}).json()
                    job = wait_for_job(client, response["job_id"])
                    self.assertEqual(job["status"], status)
                    self.assertEqual(client.get(job["manifest_url"]).json()["status"], status)

    def test_failures_are_reported_without_leaking_local_paths(self):
        def resolver(*args):
            raise ValueError("Private C:/some/path")
        with TestClient(self.app(resolver=resolver)) as client:
            first = client.post("/api/search", json={"name": "unknown"}).json()
            job = wait_for_job(client, first["job_id"])
            self.assertEqual(job["status"], "error")
            self.assertNotIn("Private", job["message"])
            self.assertIsNone(job["manifest_url"])

    def test_incomplete_or_unsafe_cache_is_not_registered(self):
        path = fixture(self.cache)
        value = json.loads(path.read_text())
        value["frames"][0]["image"] = "../../secret.txt"
        path.write_text(json.dumps(value))
        with TestClient(self.app()) as client:
            self.assertEqual(client.get(f"/api/results/{path.parent.name}/manifest").status_code, 404)


class QueueTests(unittest.IsolatedAsyncioTestCase):
    async def test_three_heavy_jobs_and_queue_position_and_dedup_across_ips(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            release, guard = threading.Event(), threading.Lock()
            running = 0
            maximum = 0
            def builder(config, **kwargs):
                nonlocal running, maximum
                with guard:
                    running += 1
                    maximum = max(maximum, running)
                release.wait(5)
                path = fixture(root / "cache", config)
                with guard:
                    running -= 1
                return path
            manager = JobManager(root / "raw", root / "cache", builder=builder)
            jobs = []
            try:
                for number in range(4):
                    jobs.append(manager.submit(SearchInput(ra=number, dec=0), f"ip-{number}"))
                joined = manager.submit(SearchInput(ra=0, dec=0), "another-ip")
                self.assertEqual(joined["job_id"], jobs[0]["job_id"])
                for _ in range(100):
                    if running == 3:
                        break
                    await asyncio.sleep(0.01)
                self.assertEqual(running, 3)
                fourth = manager.jobs[jobs[3]["job_id"]]
                self.assertEqual(manager.status(fourth)["queue_position"], 1)
                self.assertEqual(fourth.state, "queued")
            finally:
                release.set()
                await asyncio.gather(*list(manager.tasks))
            self.assertEqual(maximum, 3)
            self.assertEqual(len(manager.active), 0)
            self.assertTrue(all(job.state == "ready" for job in manager.jobs.values()))


if __name__ == "__main__":
    unittest.main()
