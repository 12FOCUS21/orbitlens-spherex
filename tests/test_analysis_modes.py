"""Valores científicos sintéticos y contrato HTTP de los modos exploratorios."""
import base64
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from astropy.io import fits
from fastapi.testclient import TestClient
from PIL import Image

from analysis_modes import AnalysisInput, analyze, combine, compatible, preview
from api import create_app
from spherex_pipeline import PipelineConfig, common_grid
from test_api import fixture


def make_data(root):
    root.mkdir(parents=True, exist_ok=True)
    wcs, _ = common_grid(PipelineConfig(10, 20))
    header = wcs.to_header()
    header["BUNIT"] = "MJy / sr"
    frames = []
    for i, value in enumerate((2., 5., 8.)):
        fits.HDUList([fits.PrimaryHDU(np.full((3, 3), value), header),
                      fits.ImageHDU(np.ones((3, 3), dtype=np.uint8), name="VALID")]).writeto(root / f"{i}.fits")
        frames.append({"aligned_fits": f"{i}.fits", "mjd": 61000 + i * .1,
                       "date_utc": f"2025-11-21T0{i}:00:00", "detector": "SPHEREx-D1",
                       "quality": {"center_pixel_valid": True},
                       "wavelength_at_target": {"central_um": 1.0, "width_um": .05}})
    return {"frames": frames}


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.manifest = make_data(self.root)

    def run_mode(self, mode, indices):
        return analyze(self.root, self.manifest, AnalysisInput(mode=mode, indices=indices))

    def test_difference_sign_and_masks(self):
        a = np.array([[2., np.nan], [7., 3.]])
        b = np.array([[5., 2.], [np.nan, 3.]])
        value, _ = combine([a, b], "difference")
        self.assertEqual(value[0, 0], -3)
        self.assertEqual(value[1, 1], 0)
        self.assertTrue(np.isnan(value[0, 1]) and np.isnan(value[1, 0]))

    def test_mean_uses_counts_and_requires_two_contributors(self):
        value, count = combine([np.array([[2., np.nan, 4.]]), np.array([[6., 1., np.nan]]), np.array([[np.nan, np.nan, 8.]])], "stack")
        np.testing.assert_allclose(value, [[4., np.nan, 6.]], equal_nan=True)
        np.testing.assert_array_equal(count, [[2, 1, 2]])

    def test_signed_png_color_orientation_and_transparency(self):
        url, limits = preview(np.array([[-2., np.nan], [2., 0.]]), True)
        image = np.array(Image.open(io.BytesIO(base64.b64decode(url.split(",")[1]))))
        self.assertGreater(image[0, 0, 0], image[0, 0, 2])
        self.assertGreater(image[1, 0, 2], image[1, 0, 0])
        self.assertEqual(image[1, 1, 3], 0)
        self.assertEqual(limits[0], -limits[1])

    def test_lightcurve_preserves_zero_and_masked_point(self):
        with fits.open(self.root / "0.fits", mode="update") as hdul:
            hdul[0].data[1, 1] = 0
        with fits.open(self.root / "1.fits", mode="update") as hdul:
            hdul["VALID"].data[1, 1] = 0
        result = self.run_mode("lightcurve", [2, 0, 1])
        self.assertEqual([p["value"] for p in result["points"]], [0, None, 8])

    def test_difference_and_stack_render_fits_values(self):
        for mode in ("difference", "stack"):
            result = self.run_mode(mode, [0, 1])
            self.assertEqual(result["valid_fraction"], 1)
            self.assertTrue(result["image"].startswith("data:image/png;base64,"))

    def test_incompatible_or_unknown_spectrum_rejects_combination(self):
        for wavelength in (None, 2.):
            self.manifest["frames"][1]["wavelength_at_target"]["central_um"] = wavelength
            with self.assertRaisesRegex(ValueError, "bandas compatibles"):
                self.run_mode("difference", [0, 1])
        self.assertEqual(len(self.run_mode("lightcurve", [0, 1])["points"]), 2)

    def test_epoch_and_duplicate_indices_rejected(self):
        self.manifest["frames"][1]["mjd"] += 10
        with self.assertRaisesRegex(ValueError, "época"):
            self.run_mode("stack", [0, 1])
        with self.assertRaises(ValueError):
            self.run_mode("stack", [0, 0])

    def test_different_detector_rejected(self):
        self.manifest["frames"][1]["detector"] = "SPHEREx-D2"
        self.assertFalse(compatible(*self.manifest["frames"][:2]))

    def test_grid_mismatch_rejected(self):
        with fits.open(self.root / "1.fits", mode="update") as hdul:
            hdul[0].header["CRVAL1"] = 11
        with self.assertRaisesRegex(ValueError, "WCS"):
            self.run_mode("difference", [0, 1])

    def test_different_observation_dates_do_not_change_spatial_grid(self):
        for index in (0, 1):
            with fits.open(self.root / f"{index}.fits", mode="update") as hdul:
                hdul[0].header["MJD-OBS"] = 61000.0 + index * .1
        result = self.run_mode("difference", [0, 1])
        self.assertEqual(result["valid_fraction"], 1)

    def test_no_common_pixels_is_explicit_error(self):
        with fits.open(self.root / "1.fits", mode="update") as hdul:
            hdul["VALID"].data[:] = 0
        with self.assertRaisesRegex(ValueError, "píxeles válidos"):
            self.run_mode("difference", [0, 1])

    def test_http_validation_unknown_result_and_rate_limit(self):
        cache = self.root / "cache"
        path = fixture(cache)
        app = create_app(raw_root=self.root / "raw", cache_root=cache, frontend_root=self.root / "absent", per_minute=1)
        url = f"/api/results/{path.parent.name}/analysis"
        with TestClient(app) as client, patch("api.analyze", return_value={"mode": "lightcurve"}):
            self.assertEqual(client.post(url, json={"mode": "lightcurve", "indices": [True]}).status_code, 422)
            self.assertEqual(client.post("/api/results/unknown/analysis", json={"mode": "lightcurve", "indices": [0]}).status_code, 404)
            self.assertEqual(client.post(url, json={"mode": "lightcurve", "indices": [0]}).status_code, 200)
            self.assertEqual(client.post(url, json={"mode": "lightcurve", "indices": [0]}).status_code, 429)
