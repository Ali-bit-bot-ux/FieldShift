import importlib.util
import io
import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

from pipeline import gee_client as gc

ROOT = Path(__file__).resolve().parents[1]

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

    def test_mild_level(self):
        self.assertEqual(gc.classify_climate_stress(450.0, 300.0, 0.20), "MILD_STRESS")

    def test_every_contract_level_is_reachable(self):
        samples = [
            (400.0, 400.0, 0.30),
            (450.0, 300.0, 0.20),
            (500.0, 250.0, 0.15),
            (600.0, 100.0, 0.05),
        ]
        levels = {gc.classify_climate_stress(*sample) for sample in samples}
        self.assertEqual(levels, set(gc.STRESS_LEVELS))

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

    def test_cached_seasons_are_physically_plausible(self):
        for region in gc.REGIONS:
            for row in gc.load_cached_climate(region)["years"]:
                with self.subTest(region=region, year=row["year"]):
                    self.assertTrue(100 <= row["gldas_evapotranspiration_mm"] <= 1000)
                    self.assertTrue(50 <= row["imerg_precipitation_mm"] <= 800)
                    self.assertTrue(0.03 <= row["smap_surface_m3m3"] <= 0.5)
                    self.assertTrue(0.03 <= row["smap_rootzone_m3m3"] <= 0.5)

    def test_cache_covers_default_climatology(self):
        for region in gc.REGIONS:
            with self.subTest(region=region):
                cached = gc.load_cached_climate(region)
                years = [row["year"] for row in cached["years"]]
                self.assertEqual(years, list(gc.DEFAULT_YEARS))
                self.assertEqual(
                    cached["summary_period"],
                    [gc.DEFAULT_YEARS[0], gc.DEFAULT_YEARS[-1]],
                )

    def test_cached_summary_matches_cached_seasons(self):
        for region in gc.REGIONS:
            with self.subTest(region=region):
                cached = gc.load_cached_climate(region)
                self.assertEqual(
                    cached["summary"], gc.build_climate_summary(cached["years"])
                )

    def test_cache_has_power_cross_check(self):
        for region in gc.REGIONS:
            with self.subTest(region=region):
                cached = gc.load_cached_climate(region)
                validation = cached.get("validation")
                self.assertIsNotNone(validation)
                cached_years = {row["year"] for row in cached["years"]}
                self.assertTrue(set(validation["years"]) <= cached_years)
                for metric in ("precipitation", "evapotranspiration"):
                    check = validation[metric]
                    self.assertLess(abs(check["relative_diff_percent"]), 30)
                    r = check["interannual_pearson_r"]
                    self.assertTrue(r is None or -1.0 <= r <= 1.0)


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


def _power_daily(year, precip_per_day, et_per_day, drop_last=False, fill_day=None):
    precip, et = {}, {}
    day = date(year, 3, 25)
    while day <= date(year, 10, 5):
        stamp = day.strftime("%Y%m%d")
        precip[stamp] = precip_per_day
        et[stamp] = et_per_day
        day += timedelta(days=1)
    if drop_last:
        del precip[f"{year}0930"]
    if fill_day:
        et[fill_day] = gc.POWER_FILL_VALUE
    return {gc.POWER_PRECIP_PARAM: precip, gc.POWER_ET_PARAM: et}


class TestPowerCrossCheck(unittest.TestCase):
    def test_season_sum_ignores_days_outside_april_september(self):
        totals = gc.aggregate_power_seasons(_power_daily(2021, 1.0, 2.0))
        self.assertEqual(totals, {2021: {"precipitation_mm": 183.0, "evapotranspiration_mm": 366.0}})

    def test_incomplete_or_filled_season_is_dropped(self):
        self.assertEqual(gc.aggregate_power_seasons(_power_daily(2021, 1.0, 2.0, drop_last=True)), {})
        self.assertEqual(gc.aggregate_power_seasons(_power_daily(2021, 1.0, 2.0, fill_day="20210715")), {})

    def test_validation_math(self):
        power = {
            2021: {"precipitation_mm": 300.0, "evapotranspiration_mm": 400.0},
            2022: {"precipitation_mm": 400.0, "evapotranspiration_mm": 500.0},
        }
        validation = gc.build_power_validation(SAMPLE_ROWS, power, 54.0, 69.0)
        self.assertEqual(validation["years"], [2021, 2022])
        self.assertEqual(validation["precipitation"]["power_mean_mm"], 350.0)
        self.assertEqual(validation["precipitation"]["relative_diff_percent"], round(100 * (310 - 350) / 350, 1))
        self.assertEqual(validation["evapotranspiration"]["relative_diff_percent"], round(100 * (510 - 450) / 450, 1))
        self.assertIsNone(validation["precipitation"]["interannual_pearson_r"])

    def test_no_overlap_is_rejected(self):
        with self.assertRaises(gc.NasaDataUnavailable):
            gc.build_power_validation(SAMPLE_ROWS, {2030: {"precipitation_mm": 1, "evapotranspiration_mm": 1}}, 0, 0)

    def test_pearson_detects_perfect_correlation(self):
        self.assertEqual(gc._pearson([1, 2, 3], [2, 4, 6]), 1.0)
        self.assertEqual(gc._pearson([1, 2, 3], [6, 4, 2]), -1.0)

    def test_fetch_parses_power_response_without_network(self):
        body = json.dumps({"properties": {"parameter": _power_daily(2021, 1.0, 2.0)}}).encode()
        with mock.patch.object(gc.urllib.request, "urlopen", return_value=io.BytesIO(body)) as urlopen:
            totals = gc.fetch_power_seasons(54.0, 69.0, [2021])
        url = urlopen.call_args.args[0]
        self.assertIn("start=20210401", url)
        self.assertIn("end=20210930", url)
        self.assertEqual(totals[2021]["precipitation_mm"], 183.0)

    def test_prefetch_reuses_cached_validation_offline(self):
        spec = importlib.util.spec_from_file_location("prefetch", ROOT / "scripts/prefetch_nasa_climate.py")
        prefetch = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(prefetch)
        cached = {"validation": {"years": [2021, 2022], "centroid_lat_lon": [54.0, 69.0]}}
        with mock.patch.object(gc, "fetch_power_seasons", side_effect=AssertionError("no network")):
            self.assertIs(
                prefetch.resolve_validation("sko", SAMPLE_ROWS, cached, force=False),
                cached["validation"],
            )


class TestSmapProfileOffline(unittest.TestCase):
    def test_profile_rounds_both_layers(self):
        fake_ee = mock.MagicMock()
        reduced = fake_ee.ImageCollection.return_value.filterDate.return_value.select.return_value.mean.return_value.reduceRegion.return_value
        reduced.getInfo.return_value = {"sm_surface": 0.212345, "sm_rootzone": 0.254321}
        profile = gc.get_smap_moisture_profile("geometry", 2021, ee_module=fake_ee)
        self.assertEqual(profile, {"surface": 0.2123, "rootzone": 0.2543})

    def test_missing_layer_raises(self):
        fake_ee = mock.MagicMock()
        reduced = fake_ee.ImageCollection.return_value.filterDate.return_value.select.return_value.mean.return_value.reduceRegion.return_value
        reduced.getInfo.return_value = {"sm_surface": 0.2, "sm_rootzone": None}
        with self.assertRaises(gc.NasaDataUnavailable):
            gc.get_smap_moisture_profile("geometry", 2021, ee_module=fake_ee)


if __name__ == "__main__":
    unittest.main()
