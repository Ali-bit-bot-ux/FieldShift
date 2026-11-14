import tempfile
import unittest
from pathlib import Path
from unittest import mock

from pipeline import gee_client as gc

SAMPLE_ROWS = [
    {
        "year": 2021,
        "gldas_evapotranspiration_mm": 500.0,
        "imerg_precipitation_mm": 300.0,
        "smap_surface_m3m3": 0.20,
        "smap_rootzone_m3m3": 0.25,
    },
    {
        "year": 2022,
        "gldas_evapotranspiration_mm": 520.0,
        "imerg_precipitation_mm": 320.0,
        "smap_surface_m3m3": 0.22,
        "smap_rootzone_m3m3": 0.27,
    },
]


class TestStressModel(unittest.TestCase):
    def test_wet_balance_is_normal(self):
        self.assertEqual(gc.classify_climate_stress(400.0, 400.0, 0.30), "NORMAL")

    def test_dry_balance_is_severe(self):
        self.assertEqual(
            gc.classify_climate_stress(600.0, 100.0, 0.05), "SEVERE_DROUGHT"
        )

    def test_moderate_level(self):
        self.assertEqual(
            gc.classify_climate_stress(500.0, 250.0, 0.15), "MODERATE_DROUGHT"
        )

    def test_every_result_is_a_contract_level(self):
        samples = [
            (400.0, 400.0, 0.30),
            (500.0, 300.0, 0.20),
            (500.0, 250.0, 0.15),
            (600.0, 100.0, 0.05),
        ]
        for et_mm, precip_mm, moisture in samples:
            level = gc.classify_climate_stress(et_mm, precip_mm, moisture)
            self.assertIn(level, gc.STRESS_LEVELS)

    def test_zero_evapotranspiration_is_rejected(self):
        with self.assertRaises(ValueError):
            gc.compute_stress_index(0.0, 100.0, 0.20)


class TestClimateSummary(unittest.TestCase):
    def test_summary_has_exactly_contract_keys(self):
        summary = gc.build_climate_summary(SAMPLE_ROWS)
        self.assertEqual(set(summary), set(gc.CONTRACT_CLIMATE_KEYS))

    def test_summary_is_the_mean_of_cached_seasons(self):
        summary = gc.build_climate_summary(SAMPLE_ROWS)
        self.assertEqual(summary["nasa_gldas_evapotranspiration_mm"], 510.0)
        self.assertEqual(summary["nasa_imerg_precipitation_mm"], 310.0)
        self.assertEqual(summary["nasa_smap_moisture_m3m3"], 0.21)

    def test_empty_series_is_rejected(self):
        with self.assertRaises(gc.NasaDataUnavailable):
            gc.build_climate_summary([])

    def test_incomplete_series_is_rejected(self):
        with self.assertRaises(gc.NasaDataUnavailable):
            gc.build_climate_summary([{"year": 2021, "gldas_evapotranspiration_mm": 500.0}])


class TestCommittedCache(unittest.TestCase):
    def test_every_region_has_a_contract_cache(self):
        for region in gc.REGIONS:
            with self.subTest(region=region):
                cached = gc.load_cached_climate(region)
                self.assertIsNotNone(cached)
                self.assertEqual(
                    set(cached["summary"]), set(gc.CONTRACT_CLIMATE_KEYS)
                )
                self.assertGreaterEqual(len(cached["years"]), 1)
                years = [row["year"] for row in cached["years"]]
                self.assertEqual(years, sorted(years))

    def test_offline_summary_for_all_regions(self):
        for region in gc.REGIONS:
            with self.subTest(region=region):
                summary = gc.get_nasa_climate_summary(region)
                self.assertEqual(set(summary), set(gc.CONTRACT_CLIMATE_KEYS))
                self.assertIn(
                    summary["climate_stress_level"], gc.STRESS_LEVELS
                )
                self.assertGreater(summary["nasa_gldas_evapotranspiration_mm"], 0)
                self.assertGreater(summary["nasa_imerg_precipitation_mm"], 0)
                self.assertGreater(summary["nasa_smap_moisture_m3m3"], 0)


class TestClimateCache(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(gc, "CACHE_DIR", Path(tmp)):
                path = gc.save_cached_climate("sko", SAMPLE_ROWS)
                self.assertTrue(path.exists())
                loaded = gc.load_cached_climate("sko")
                self.assertIsNotNone(loaded)
                self.assertEqual(
                    loaded["summary"], gc.build_climate_summary(SAMPLE_ROWS)
                )
                self.assertEqual(len(loaded["years"]), 2)

    def test_offline_summary_uses_cache_without_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(gc, "CACHE_DIR", Path(tmp)):
                gc.save_cached_climate("sko", SAMPLE_ROWS)
                with mock.patch.object(
                    gc,
                    "fetch_nasa_climate_series",
                    side_effect=AssertionError("network must not be used"),
                ), mock.patch.object(
                    gc,
                    "_ee",
                    side_effect=AssertionError("Earth Engine must not initialize"),
                ):
                    summary = gc.get_nasa_climate_summary("sko")
                self.assertEqual(set(summary), set(gc.CONTRACT_CLIMATE_KEYS))

    def test_missing_cache_and_offline_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(gc, "CACHE_DIR", Path(tmp)):
                with mock.patch.object(
                    gc,
                    "fetch_nasa_climate_series",
                    side_effect=gc.NasaDataUnavailable("offline"),
                ):
                    with self.assertRaises(gc.NasaDataUnavailable):
                        gc.get_nasa_climate_summary("sko")

    def test_unknown_region_is_rejected(self):
        with self.assertRaises(ValueError):
            gc.get_nasa_climate_summary("almaty")

    def test_corrupt_cache_is_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sko.json"
            path.write_text("{not json", encoding="utf-8")
            with mock.patch.object(gc, "CACHE_DIR", Path(tmp)):
                self.assertIsNone(gc.load_cached_climate("sko"))


if __name__ == "__main__":
    unittest.main()
