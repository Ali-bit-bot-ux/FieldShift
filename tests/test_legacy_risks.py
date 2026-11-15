import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from modules import legacy_common as common
from modules.legacy_risks import router


class TestLegacyRisks(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(router)

        @app.exception_handler(common.LegacyDataUnavailable)
        async def unavailable(request, exc):
            return JSONResponse(status_code=503, content={"detail": "Dataset unavailable"})

        self.client = self.enterContext(TestClient(app))

    def test_contagion_preserves_statistics_and_labels_limits(self):
        original = common.load_json("causality_report.json")["granger_causality"]
        for region in ("sko", "kostanay", "akmola", "pavlodar"):
            with self.subTest(region=region):
                response = self.client.post("/api/contagion", json={"region": region})
                self.assertEqual(response.status_code, 200, response.text)
                body = response.json()
                json.dumps(body, allow_nan=False)
                data = body["data"]
                self.assertFalse(data["granger"]["significant"])
                self.assertEqual(data["granger"]["n_observations"], 8)
                self.assertEqual(data["granger"]["lag_unit"], "years")
                for row in data["granger"]["per_lag"]:
                    self.assertEqual(row["p_value"], original["per_lag"][f"lag_{row['lag_years']}"]["p_value"])
                self.assertEqual(data["graph"]["kind"], "conceptual_unweighted")
                self.assertTrue(all("value" not in edge for edge in data["graph"]["edges"]))
                self.assertEqual(data["var_model"]["status"], "unavailable")
                self.assertTrue(body["metadata"]["warnings"])
                for row in data["scatter"]:
                    self.assertEqual(row["price_status"], "estimate" if row["year"] >= 2025 else "unverified_historical")

    def test_scatter_uses_selected_region_and_does_not_recompute_granger(self):
        psi = common.load_table("phenoshift_regions.parquet")
        results = []
        for region in ("sko", "kostanay"):
            data = self.client.post("/api/contagion", json={"region": region}).json()["data"]
            expected = psi.loc[psi["region_id"] == region].set_index("year")["psi"].to_dict()
            for row in data["scatter"]:
                self.assertAlmostEqual(row["psi"], expected[row["year"]])
            results.append(data)
        self.assertEqual(results[0]["granger"], results[1]["granger"])
        self.assertNotEqual(results[0]["scatter"], results[1]["scatter"])

    def test_vulnerability_exact_snapshot_and_summary(self):
        original = common.load_table("vuln_map_regions.parquet")
        for region in ("sko", "kostanay", "akmola", "pavlodar"):
            with self.subTest(region=region):
                response = self.client.post("/api/vulnerability", json={"region": region})
                self.assertEqual(response.status_code, 200, response.text)
                body = response.json()
                json.dumps(body, allow_nan=False)
                rows = body["data"]["districts"]
                self.assertEqual(len(rows), 5)
                self.assertEqual(body["data"]["summary"]["total_districts"], 5)
                self.assertEqual(sum(entry["count"] for entry in body["data"]["summary"]["risk_counts"].values()), 5)
                for row in rows:
                    expected = original.loc[(original["region_id"] == region) & (original["district_id"] == row["district_id"])].iloc[0]
                    self.assertEqual(row["vuln_score"], expected["vuln_score"])
                    self.assertEqual(row["risk_level"], expected["risk_level"])
                    self.assertEqual(row["area_ha"], expected["area_ha"])
                self.assertEqual(body["metadata"]["kind"], "model_snapshot")
                self.assertIsNone(body["metadata"]["snapshot_generated_at"])

    def test_district_formula_agrees_with_archived_scores(self):
        frame = common.load_table("vuln_map_regions.parquet")
        for row in frame.to_dict(orient="records"):
            score = 100 * (
                0.4 * min(1, max(0, -row["psi_value"]) / 3)
                + 0.3 * min(1, max(0, -row["smai_value"]) / 2)
                + 0.2 * min(1, max(0, row["nearest_elevator_km"] / 300))
                + 0.1 * (1 - min(1, max(0, row["area_ha"] / 2000)))
            )
            self.assertAlmostEqual(round(score, 1), row["vuln_score"], delta=0.15)

    def test_invalid_regions_years_and_unimplemented_scenarios_rejected(self):
        for route in ("contagion", "vulnerability"):
            for payload in ({}, {"region": "all"}, {"region": "../sko"}, {"region": "sko", "moisture_shock_pct": -50}):
                with self.subTest(route=route, payload=payload):
                    self.assertEqual(self.client.post(f"/api/{route}", json=payload).status_code, 422)
        for year in (2021, 2025, 2027, "2026", True):
            self.assertEqual(self.client.post("/api/vulnerability", json={"region": "sko", "year": year}).status_code, 422)

    def test_missing_dataset_returns_unavailable_without_fallback(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(common, "DATA_DIR", Path(directory)):
            for route in ("contagion", "vulnerability"):
                self.assertEqual(self.client.post(f"/api/{route}", json={"region": "sko"}).status_code, 503)

    def test_invalid_or_nonfinite_statistics_are_rejected(self):
        original = common.load_json("causality_report.json")
        for value in (None, float("nan"), -0.01, 1.01, "0.001", True):
            report = copy.deepcopy(original)
            report["granger_causality"]["per_lag"]["lag_1"]["p_value"] = value
            with self.subTest(value=value), mock.patch("modules.legacy_risks.load_json", return_value=report):
                response = self.client.post("/api/contagion", json={"region": "sko"})
                self.assertEqual(response.status_code, 503)

    def test_invalid_district_cache_rejected(self):
        original = common.load_table("vuln_map_regions.parquet")
        for column, value in (("vuln_score", float("nan")), ("lat", 95), ("area_ha", 0), ("source", "synthetic_grid"), ("risk_level", "FAKE")):
            frame = original.copy()
            frame.loc[0, column] = value
            with self.subTest(column=column), mock.patch("modules.legacy_risks.load_table", return_value=frame):
                self.assertEqual(self.client.post("/api/vulnerability", json={"region": "sko"}).status_code, 503)

    def test_common_loader_rejects_bad_files(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.object(common, "DATA_DIR", Path(directory)):
            (Path(directory) / "bad.parquet").write_bytes(b"invalid")
            (Path(directory) / "bad.json").write_text("{broken", encoding="utf-8")
            with self.assertRaises(common.LegacyDataUnavailable):
                common.load_table("bad.parquet")
            with self.assertRaises(common.LegacyDataUnavailable):
                common.load_json("bad.json")
            pd.DataFrame({"unexpected": [1]}).to_parquet(Path(directory) / "wrong.parquet")
            with self.assertRaises(common.LegacyDataUnavailable):
                common.load_table("wrong.parquet", ("required",))
            (Path(directory) / "null.json").write_text('{"statistic": NaN}', encoding="utf-8")
            self.assertEqual(common.load_json("null.json"), {"statistic": None})


if __name__ == "__main__":
    unittest.main()
