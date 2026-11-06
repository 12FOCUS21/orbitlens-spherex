"""Pruebas científicas con imágenes sintéticas; nunca consultan servicios externos."""

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx
import numpy as np
from astropy.io import fits
from astropy.table import Table
from astropy.wcs import WCS

from spherex_pipeline import (
    BAD_MASK, PipelineConfig, align_cutout, build_sequence, common_grid,
    flag_statistics, global_limits, group_observations, render_frame,
    select_detector, select_times,
)
from targets import SIMBAD_SERVERS, resolve_target


def observation(index, collection="spherex_qr3", detector="SPHEREx-D1"):
    return {"collection": collection, "energy_bandpassname": detector, "obs_id": f"exposure-{index}",
            "t_min": str(61000 + index), "t_exptime": "113.58",
            "access_url": f"https://irsa.ipac.caltech.edu/ibe/data/spherex/{index}.fits"}


def votable(rows, names):
    table = Table(rows=rows, names=names) if rows else Table(names=names, dtype=["U200"] * len(names))
    output = io.BytesIO()
    table.write(output, format="votable")
    return output.getvalue()


def synthetic_fits(angle=0):
    wcs = WCS(naxis=2)
    wcs.wcs.ctype = ["RA---TAN", "DEC--TAN"]
    wcs.wcs.crval = [10, 20]
    wcs.wcs.crpix = [20.5, 20.5]
    scale = 6.15 / 3600
    radians = np.deg2rad(angle)
    wcs.wcs.cd = scale * np.array([[-np.cos(radians), np.sin(radians)],
                                   [np.sin(radians), np.cos(radians)]])
    yy, xx = np.indices((40, 40))
    ra, dec = wcs.pixel_to_world_values(xx, yy)
    dx = (ra - 10) * np.cos(np.deg2rad(20)) / scale
    dy = (dec - 20) / scale
    image = (0.2 + np.exp(-(dx ** 2 + dy ** 2) / 8)).astype(np.float32)
    flags = np.full(image.shape, (1 << 21) | (1 << 12), dtype=np.int32)
    header = wcs.to_header()
    header["BUNIT"] = "MJy / sr"
    output = io.BytesIO()
    fits.HDUList([fits.PrimaryHDU(), fits.ImageHDU(image, header, name="IMAGE"),
                  fits.ImageHDU(flags, name="FLAGS")]).writeto(output)
    return output.getvalue()


class PipelineTests(unittest.TestCase):
    def test_informational_flags_are_not_masked(self):
        flags = np.array([1 << 21, 1 << 12, (1 << 21) | 1, 1 << 6], dtype=np.uint32)
        rejected, summary = flag_statistics(flags)
        np.testing.assert_array_equal(rejected, [False, False, True, True])
        self.assertEqual(summary["nonzero_fraction"], 1)
        self.assertEqual(summary["masked_fraction"], 0.5)
        self.assertFalse(BAD_MASK & (1 << 21))

    def test_duplicate_releases_do_not_duplicate_exposure(self):
        groups = group_observations([observation(1, "spherex_qr2"), observation(1), observation(2)])
        self.assertEqual(len(groups["SPHEREx-D1"]), 2)
        self.assertEqual(groups["SPHEREx-D1"][0]["collection"], "spherex_qr3")

    def test_selection_spans_dates_and_keeps_one_detector(self):
        rows = [observation(i) for i in [0, 0.001, 0.002, 50, 100]]
        rows += [observation(4, detector="SPHEREx-D2")]
        groups = group_observations(rows)
        self.assertEqual(select_detector(groups), "SPHEREx-D1")
        self.assertIsNone(select_detector(groups, "SPHEREx-D6"))
        self.assertEqual([row["t_min"] for row in select_times(groups["SPHEREx-D1"], 3)],
                         ["61000", "61050", "61100"])

    def test_grid_is_centered_north_up_east_left(self):
        wcs, shape = common_grid(PipelineConfig(10, 20, fov=1))
        center = (np.array(shape) - 1) / 2
        ra, dec = wcs.pixel_to_world_values(*center)
        self.assertAlmostEqual(float(ra), 10)
        self.assertAlmostEqual(float(dec), 20)
        ra_east, _ = wcs.pixel_to_world_values(center[0] + 1, center[1])
        _, dec_north = wcs.pixel_to_world_values(center[0], center[1] + 1)
        self.assertLess(ra_east, ra)
        self.assertGreater(dec_north, dec)

    def test_global_stretch_same_brightness_same_gray_and_nan_transparent(self):
        images = [np.array([[0., 1.], [2., np.nan]]), np.array([[1., 3.], [4., 5.]])]
        limits = global_limits(images)
        first, second = [np.asarray(render_frame(image, limits)) for image in images]
        self.assertEqual(first[1, 1, 0], second[1, 0, 0])
        self.assertEqual(first[0, 1, 3], 0)
        self.assertEqual(second[0, 1, 3], 255)

    def test_rotation_alignment_keeps_fixed_source_fixed(self):
        config = PipelineConfig(10, 20, fov=1)
        output_wcs, shape = common_grid(config)
        with tempfile.TemporaryDirectory() as directory:
            images = []
            for angle in (0, 45):
                path = Path(directory) / f"{angle}.fits"
                path.write_bytes(synthetic_fits(angle))
                aligned, _, details = align_cutout(path, config, output_wcs, shape)
                self.assertEqual(details["quality"]["masked_fraction"], 0)
                images.append(aligned)
            # El remuestreo puede variar el pico dentro del píxel central.
            self.assertLess(float(np.nanmax(np.abs(images[0] - images[1]))), 0.08)

    def test_masked_center_keeps_usable_field_and_stays_transparent(self):
        config = PipelineConfig(10, 20, fov=1)
        output_wcs, shape = common_grid(config)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "masked.fits"
            with fits.open(io.BytesIO(synthetic_fits()), memmap=False) as hdul:
                hdul["FLAGS"].data[18:22, 18:22] |= 1  # TRANSIENT en la región central.
                hdul.writeto(path)
            aligned, _, details = align_cutout(path, config, output_wcs, shape)
        center = (shape[0] // 2, shape[1] // 2)
        self.assertGreaterEqual(details["quality"]["valid_coverage"], config.min_coverage)
        self.assertFalse(details["quality"]["center_pixel_valid"])
        self.assertIn("TRANSIENT", details["quality"]["center_pixel_flag_names"])
        self.assertTrue(np.isnan(aligned[center]))
        rgba = np.asarray(render_frame(aligned, global_limits([aligned])))
        self.assertEqual(rgba[shape[0] - 1 - center[0], center[1], 3], 0)

    def test_inadequate_coverage_still_rejects_frame(self):
        config = PipelineConfig(10, 20, fov=1)
        output_wcs, shape = common_grid(config)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.fits"
            with fits.open(io.BytesIO(synthetic_fits()), memmap=False) as hdul:
                hdul["FLAGS"].data[:] |= 1
                hdul.writeto(path)
            with self.assertRaisesRegex(ValueError, "Cobertura válida insuficiente"):
                align_cutout(path, config, output_wcs, shape)

    def test_sequence_outputs_and_cache_without_network(self):
        rows = [observation(i) for i in range(3)]
        names = list(rows[0])
        payload = votable([[row[name] for name in names] for row in rows], names)
        empty = votable([], names)
        counts = {"calls": 0}

        def handler(request):
            counts["calls"] += 1
            if request.url.path == "/SIA":
                self.assertEqual(request.url.params["RESPONSEFORMAT"], "VOTABLE")
                body = payload if request.url.params["COLLECTION"] == "spherex_qr3" else empty
            else:
                self.assertIn("center", request.url.params)
                self.assertIn("size", request.url.params)
                body = synthetic_fits()
            return httpx.Response(200, content=body)

        with tempfile.TemporaryDirectory() as directory, httpx.Client(transport=httpx.MockTransport(handler)) as client:
            raw_root, cache_root = Path(directory) / "raw", Path(directory) / "cache"
            config = PipelineConfig(10, 20, fov=1, frames=3)
            path = build_sequence(config, raw_root=raw_root, cache_root=cache_root, client=client)
            manifest = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "ready")
            self.assertEqual(manifest["frame_count"], 3)
            self.assertEqual([frame["mjd"] for frame in manifest["frames"]], [61000, 61001, 61002])
            for frame in manifest["frames"]:
                self.assertTrue((path.parent / frame["image"]).exists())
                with fits.open(path.parent / frame["aligned_fits"]) as hdul:
                    self.assertIn("FLAGS", hdul)
                    self.assertIn("VALID", hdul)
                    self.assertEqual(hdul[0].data.shape, (10, 10))
            self.assertTrue((path.parent / "preview.gif").exists())
            calls = counts["calls"]
            self.assertEqual(build_sequence(config, raw_root=raw_root, cache_root=cache_root, client=client), path)
            self.assertEqual(counts["calls"], calls)

    def test_no_coverage_and_service_failure_are_distinct(self):
        with tempfile.TemporaryDirectory() as directory, httpx.Client() as client:
            for queries, expected in (({"spherex_qr3": {"rows": 0}}, "empty"),
                                      ({"spherex_qr3": {"error": "timeout"}}, "error")):
                with patch("spherex_pipeline.query_observations", return_value=([], queries)):
                    path = build_sequence(PipelineConfig(10, 20), client=client,
                                          cache_root=Path(directory), raw_root=Path(directory))
                    self.assertEqual(json.loads(path.read_text())["status"], expected)

    def test_simbad_proper_motion_changes_center(self):
        names = ["main_id", "ra", "dec", "pmra", "pmdec"]
        body = votable([["Synthetic star", 10., 0., 1000., 0.]], names)
        with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=body))) as client:
            result = resolve_target(client, "Synthetic star", 2025.0)
        self.assertTrue(result["proper_motion_applied"])
        self.assertAlmostEqual((result["ra_deg"] - 10) * 3600, 25, places=3)
        self.assertEqual(result["coordinate_epoch_jyear"], 2025)

    def test_simbad_falls_back_to_mirror_on_timeout_or_http_failure(self):
        body = votable([["Synthetic star", 10., 0., 0., 0.]],
                       ["main_id", "ra", "dec", "pmra", "pmdec"])
        for failure in ("timeout", "http"):
            with self.subTest(failure=failure):
                calls = []

                def handler(request):
                    calls.append(str(request.url).split("?", 1)[0])
                    self.assertEqual(request.extensions["timeout"]["connect"], 10.0)
                    if len(calls) == 1:
                        if failure == "timeout":
                            raise httpx.ConnectTimeout("unreachable", request=request)
                        return httpx.Response(503, content=b"temporarily unavailable")
                    return httpx.Response(200, content=body)

                with httpx.Client(transport=httpx.MockTransport(handler)) as client:
                    result = resolve_target(client, "Synthetic star")
                self.assertEqual(calls, list(SIMBAD_SERVERS))
                self.assertEqual(result["source"], SIMBAD_SERVERS[1])
                self.assertEqual(len(result["server_failures"]), 1)

    def test_simbad_reports_both_failures_without_coordinate_fallback(self):
        calls = []

        def handler(request):
            calls.append(request.url.host)
            raise httpx.ConnectTimeout("unreachable", request=request)

        with httpx.Client(transport=httpx.MockTransport(handler)) as client:
            with self.assertRaisesRegex(ValueError, "ninguno de los servidores"):
                resolve_target(client, "Synthetic star")
        self.assertEqual(len(calls), 2)


if __name__ == "__main__":
    unittest.main()
