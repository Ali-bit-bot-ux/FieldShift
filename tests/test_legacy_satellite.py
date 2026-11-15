"""Independent HTTP tests for the legacy satellite router and real snapshots."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from modules import legacy_common as common
from modules.legacy_satellite import router


CACHE = Path(__file__).resolve().parents[1] / "data" / "processed" / "legacy"
REGIONS = ("sko", "kostanay", "akmola", "pavlodar")


class LegacySatelliteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.include_router(router)

        @app.exception_handler(common.LegacyDataUnavailable)
        async def unavailable(_request, exc):
            return JSONResponse(status_code=503, content={"detail": str(exc)})

        cls.client = TestClient(app)

    def post(self, endpoint, region="sko", year=2021, **extra):
        payload = {"region": region, **extra}
        if endpoint != "backtest/2021":
            payload["year"] = year
        return self.client.post("/api/" + endpoint, json=payload)

    def test_all_regions_and_success_envelopes(self):
        for endpoint, module in (("phenomap", "phenomap"), ("hydrorisk", "hydrorisk"), ("backtest/2021", "backtesting")):
            for region in REGIONS:
                with self.subTest(endpoint=endpoint, region=region):
                    response = self.post(endpoint, region)
                    self.assertEqual(response.status_code, 200, response.text)
                    body = response.json()
                    self.assertEqual(body["status"], "success")
                    self.assertEqual(body["module"], module)
                    self.assertTrue(body["metadata"]["sources"])
                    self.assertTrue(body["metadata"]["warnings"])
                    self.assertEqual(body["metadata"]["kind"], "retrospective" if module == "backtesting" else "observed_derived")
                    self.assertTrue(all(row["region_id"] == region for row in body["data"]["series"]))
                    json.dumps(body, allow_nan=False)

    def test_strict_input(self):
        for endpoint in ("phenomap", "hydrorisk"):
            for year in ("2021", 2021.0, True, None, 2014, 10000):
                with self.subTest(endpoint=endpoint, year=year):
                    self.assertEqual(self.post(endpoint, year=year).status_code, 422)
            self.assertEqual(self.post(endpoint, region="unknown").status_code, 422)
            self.assertEqual(self.post(endpoint, crop="wheat").status_code, 422)
            self.assertEqual(self.post(endpoint, scenario="dry").status_code, 422)
            self.assertEqual(self.client.post("/api/" + endpoint, json={"region": "sko"}).status_code, 422)
        self.assertEqual(self.post("backtest/2021", region="unknown").status_code, 422)
        self.assertEqual(self.client.post("/api/backtest/2021", json={"region": "sko", "year": 2021}).status_code, 422)

    def test_year_filtering_and_exact_values(self):
        for year in (2021, 2026):
            for region in REGIONS:
                for endpoint, filename in (("phenomap", "ndvi_current_2026.parquet" if year == 2026 else "ndvi_baseline_regions.parquet"), ("hydrorisk", "hydroborder_regions.parquet")):
                    with self.subTest(endpoint=endpoint, year=year, region=region):
                        body = self.post(endpoint, region, year).json()
                        actual = body["data"]["series"]
                        source = pd.read_parquet(CACHE / filename)
                        expected = source.loc[(source.region_id == region) & (source.year == year)].sort_values("date")
                        self.assertEqual(len(actual), len(expected))
                        column = "ndvi" if endpoint == "phenomap" else "smai"
                        self.assertEqual([row[column] for row in actual], expected[column].tolist())
                        self.assertEqual([row["date"] for row in actual], expected.date.dt.strftime("%Y-%m-%d").tolist())
                        self.assertTrue(all(row["year"] == year for row in actual))
                        if endpoint == "hydrorisk":
                            self.assertEqual(body["data"]["latest"], actual[-1])
                            self.assertNotIn("price", json.dumps(body).replace("price prediction", ""))

    def test_psi_preserves_cached_arithmetic(self):
        cache = pd.read_parquet(CACHE / "phenoshift_regions.parquet")
        for region in REGIONS:
            body = self.post("phenomap", region, 2026).json()["data"]
            expected = cache.loc[(cache.region_id == region) & (cache.year == 2026)].iloc[0]
            self.assertEqual(body["selected_metrics"]["psi"], expected.psi)
            self.assertEqual(body["selected_metrics"]["delay_days"], int(expected.delay_days))
            series = pd.DataFrame(body["series"])
            norm = pd.DataFrame(body["norm"])
            matched = series.merge(norm, on="doy")
            recomputed = round(float(((matched.ndvi - matched.ndvi_mean) / matched.ndvi_std).mean()), 4)
            self.assertEqual(body["selected_metrics"]["psi"], recomputed)

    def test_no_future_or_missing_year_substitution(self):
        for endpoint in ("phenomap", "hydrorisk"):
            self.assertEqual(self.post(endpoint, year=2027).status_code, 404)
        response = self.post("phenomap", "pavlodar", 2015)
        self.assertEqual(response.status_code, 404)
        body = self.post("phenomap", "pavlodar", 2026).json()
        self.assertNotIn(2015, body["metadata"]["available_years"])
        # Sparse 2015 observations are legitimate but do not satisfy PSI's >=5 rule.
        body = self.post("phenomap", "sko", 2015).json()
        self.assertIsNone(body["data"]["selected_metrics"])
        self.assertTrue(body["data"]["series"])

    def test_real_backtest_leads(self):
        for region, days in {"sko": 66, "kostanay": 46, "akmola": 25, "pavlodar": 35}.items():
            data = self.post("backtest/2021", region).json()["data"]
            self.assertEqual(data["lead_days"], days)
            self.assertEqual(data["reference_date"], "2021-07-15")
            self.assertEqual(data["threshold"], -1.5)
            self.assertTrue(all("2021-05-01" <= row["date"] <= "2021-09-30" for row in data["series"]))

    def test_missing_files(self):
        with TemporaryDirectory() as directory, patch.object(common, "DATA_DIR", Path(directory)):
            for endpoint in ("phenomap", "hydrorisk", "backtest/2021"):
                self.assertEqual(self.post(endpoint).status_code, 503)

    def test_empty_corrupt_and_missing_columns(self):
        for endpoint, name in (("phenomap", "ndvi_baseline_regions.parquet"), ("hydrorisk", "hydroborder_regions.parquet"), ("backtest/2021", "backtest_2021_regions.parquet")):
            source = pd.read_parquet(CACHE / name)
            with TemporaryDirectory() as directory, patch.object(common, "DATA_DIR", Path(directory)):
                target = Path(directory) / name
                for frame in (source.iloc[:0], source.drop(columns=["region_id"])):
                    frame.to_parquet(target)
                    self.assertEqual(self.post(endpoint).status_code, 503)
                target.write_bytes(b"not a parquet snapshot")
                self.assertEqual(self.post(endpoint).status_code, 503)

    def test_snapshot_validation(self):
        original = common.load_table
        cases = [
            ("phenomap", "ndvi_baseline_regions.parquet", "ndvi", np.inf),
            ("phenomap", "ndvi_baseline_regions.parquet", "ndvi", np.nan),
            ("phenomap", "ndvi_baseline_regions.parquet", "year", 2026),
            ("phenomap", "ndvi_current_2026.parquet", "year", 2025),
            ("phenomap", "phenological_norm_regions.parquet", "ndvi_std", 0),
            ("phenomap", "phenological_norm_regions.parquet", "ndvi_std", -1),
            ("phenomap", "phenological_norm_regions.parquet", "ndvi_upper", np.inf),
            ("phenomap", "phenoshift_regions.parquet", "psi", np.nan),
            ("hydrorisk", "hydroborder_regions.parquet", "smai", -np.inf),
            ("hydrorisk", "hydroborder_regions.parquet", "sm_std", 0),
            ("backtest/2021", "backtest_2021_regions.parquet", "soil_moisture", np.nan),
        ]
        for endpoint, name, column, value in cases:
            def broken(filename, required_columns=()):
                frame = original(filename, required_columns).copy()
                if filename == name:
                    frame.loc[0, column] = value
                return frame
            with self.subTest(name=name, column=column, value=value), patch.object(common, "load_table", side_effect=broken):
                self.assertEqual(self.post(endpoint).status_code, 503)
        for endpoint, name in (("phenomap", "ndvi_baseline_regions.parquet"), ("hydrorisk", "hydroborder_regions.parquet"), ("backtest/2021", "backtest_2021_regions.parquet")):
            for corruption in ("duplicate", "date", "numeric_date"):
                def broken(filename, required_columns=()):
                    frame = original(filename, required_columns).copy()
                    if filename == name:
                        if corruption == "duplicate":
                            frame = pd.concat([frame, frame.iloc[:1]], ignore_index=True)
                        elif corruption == "numeric_date":
                            frame["date"] = 123
                        else:
                            frame["date"] = frame.date.astype(str)
                            frame.loc[0, "date"] = "invalid-date"
                    return frame
                with self.subTest(endpoint=endpoint, corruption=corruption), patch.object(common, "load_table", side_effect=broken):
                    self.assertEqual(self.post(endpoint).status_code, 503)

    def test_missing_observations_and_metrics(self):
        original = common.load_table
        for endpoint, name in (("phenomap", "ndvi_baseline_regions.parquet"), ("hydrorisk", "hydroborder_regions.parquet"), ("backtest/2021", "backtest_2021_regions.parquet")):
            def missing(filename, required_columns=()):
                frame = original(filename, required_columns)
                return frame.loc[frame.region_id != "sko"] if filename == name else frame
            with patch.object(common, "load_table", side_effect=missing):
                self.assertEqual(self.post(endpoint).status_code, 404)
        for name in ("phenological_norm_regions.parquet", "phenoshift_regions.parquet"):
            def missing(filename, required_columns=()):
                frame = original(filename, required_columns)
                return frame.loc[frame.region_id != "sko"] if filename == name else frame
            with patch.object(common, "load_table", side_effect=missing):
                self.assertEqual(self.post("phenomap").status_code, 503)

    def test_threshold_boundaries(self):
        original = common.load_table
        values = [-2.01, -2, -1.01, -1, -0.51, -0.5, 1, 1.01, 2, 2.01]
        expected = ["SEVERE_DRY", "DRY", "DRY", "SLIGHTLY_DRY", "SLIGHTLY_DRY", "NORMAL", "NORMAL", "SLIGHTLY_WET", "SLIGHTLY_WET", "WET"]
        frame = original("hydroborder_regions.parquet")
        frame = frame.loc[(frame.region_id == "sko") & (frame.year == 2021)].iloc[:len(values)].copy()
        frame["smai"] = values
        with patch.object(common, "load_table", return_value=frame):
            data = self.post("hydrorisk").json()["data"]
        self.assertEqual([row["anomaly_level"] for row in data["series"]], expected)

    def test_backtest_signed_null_and_season_filter(self):
        for smai, lead in ((-1.5, None), (-1.6, -17)):
            frame = pd.DataFrame({"region_id": ["sko"] * 4,
                "date": pd.to_datetime(["2020-05-10", "2021-04-30", "2021-08-01", "2021-10-01"]),
                "soil_moisture": [0.1] * 4, "smai": [-5, -5, smai, -5]})
            with patch.object(common, "load_table", return_value=frame):
                data = self.post("backtest/2021").json()["data"]
                self.assertEqual(len(data["series"]), 1)
                self.assertEqual(data["lead_days"], lead)
                self.assertEqual(data["trigger_date"], None if lead is None else "2021-08-01")


if __name__ == "__main__":
    unittest.main()
