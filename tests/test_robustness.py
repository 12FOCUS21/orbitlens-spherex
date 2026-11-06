"""Regresiones de disco, configuración y red sin servicios externos."""
import argparse
import asyncio
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from archive_config import read_collections
from disk_cache import trim
from api import JobManager, SearchInput
from test_api import fixture
from test_data import query_collection
from spherex_pipeline import cached_cutout
from test_pipeline import synthetic_fits


class RobustnessTests(unittest.TestCase):
    def test_collections_validate_order_and_duplicates(self):
        self.assertEqual(read_collections("spherex_qr4,spherex_qr3_deep"), ("spherex_qr4", "spherex_qr3_deep"))
        for value in ("spherex_qr3,spherex_qr3", "https://elsewhere", "spherex_qr3,"):
            with self.assertRaises(ValueError):
                read_collections(value)

    def test_lru_protects_preset_recent_and_files_outside_roots(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cache, raw = root / "cache", root / "raw"
            now = time.time()
            for index in range(3):
                directory = cache / f"{index:024x}"
                directory.mkdir(parents=True)
                (directory / "frame").write_bytes(b"x" * 100)
                if index < 2:
                    os.utime(directory, (now - 7200, now - 7200))
            outside = root / "outside.txt"
            outside.write_text("keep")
            removed, size = trim(raw, cache, {f"{0:024x}"}, 0, now)
            self.assertEqual(removed, [f"{1:024x}"])
            self.assertEqual(size, 200)
            self.assertTrue(outside.exists())

    def test_raw_cutouts_are_included_in_budget(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cutouts = root / "raw/cutouts"
            cutouts.mkdir(parents=True)
            path = cutouts / "old.fits"
            path.write_bytes(b"large")
            stamp = time.time() - 7200
            os.utime(path, (stamp, stamp))
            removed, size = trim(root / "raw", root / "cache", set(), 0)
            self.assertEqual(size, 0)
            self.assertFalse(path.exists())

    def test_full_disk_still_serves_cached_search(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            fixture(root / "cache")
            manager = JobManager(root / "raw", root / "cache")
            manager.load_cache()
            manager.disk_bytes = manager.disk_budget
            self.assertTrue(manager.submit(SearchInput(ra=10, dec=20), "one")["cached"])
            from fastapi import HTTPException
            with self.assertRaises(HTTPException) as caught:
                manager.submit(SearchInput(ra=11, dec=20), "one")
            self.assertEqual(caught.exception.status_code, 429)

    def test_cleanup_unregisters_evicted_results(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            path = fixture(root / "cache")
            manager = JobManager(root / "raw", root / "cache")
            manager.load_cache()
            manager.disk_budget = 1
            stamp = time.time() - 7200
            os.utime(path.parent, (stamp, stamp))
            asyncio.run(manager.clean_disk())
            self.assertFalse(manager.results)
            self.assertFalse(manager.cache)

    def test_transient_query_retries_but_404_does_not(self):
        for status, expected in ((503, 3), (404, 1)):
            calls = []
            def handler(request):
                calls.append(request)
                return httpx.Response(status)
            with tempfile.TemporaryDirectory() as folder, httpx.Client(transport=httpx.MockTransport(handler)) as client, patch("test_data.time.sleep"):
                args = argparse.Namespace(ra=10, dec=20, maxrec=5, output=Path(folder))
                with self.assertRaises(httpx.HTTPStatusError):
                    query_collection(client, "spherex_qr3", args)
            self.assertEqual(len(calls), expected)

    def test_cutout_recovers_from_503_and_reuses_valid_file(self):
        calls = []
        def handler(request):
            calls.append(request)
            return httpx.Response(503) if len(calls) == 1 else httpx.Response(200, content=synthetic_fits())
        with tempfile.TemporaryDirectory() as folder, httpx.Client(transport=httpx.MockTransport(handler)) as client, patch("spherex_pipeline.time.sleep"):
            path = cached_cutout(client, "https://irsa.ipac.caltech.edu/mock?center=1,2&size=0.1", Path(folder), False)
            self.assertTrue(path.is_file())
            cached_cutout(client, "https://irsa.ipac.caltech.edu/mock?center=1,2&size=0.1", Path(folder), False)
            self.assertEqual(len(calls), 2)

    def test_active_jobs_prevent_cleanup(self):
        with tempfile.TemporaryDirectory() as folder, patch("api.trim") as cleanup:
            root = Path(folder)
            manager = JobManager(root / "raw", root / "cache")
            manager.active["busy"] = object()
            asyncio.run(manager.clean_disk())
            cleanup.assert_not_called()
