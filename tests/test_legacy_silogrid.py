"""Isolated HTTP and deterministic scenario tests (no main API wiring)."""
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from modules import legacy_common, legacy_silogrid as silo


class SiloGridTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.include_router(silo.router)

        @app.exception_handler(legacy_common.LegacyDataUnavailable)
        async def unavailable(request, exc):
            return JSONResponse(status_code=503, content={"detail": str(exc)})

        cls.client = TestClient(app)
        cls.base = {"region": "sko", "crop_id": "spring_wheat"}

    def post(self, body=None, suffix=""):
        return self.client.post("/api/silogrid" + suffix, json=self.base if body is None else body)

    def test_regions_crops_determinism_and_shocks(self):
        counts = {"sko": 52, "kostanay": 65, "akmola": 68, "pavlodar": 22}
        for region, count in counts.items():
            for crop in ("spring_wheat", "spring_barley", "sunflower", "flax_linseed", "chickpea"):
                for shock in (0, -20, -50):
                    body = {"region": region, "crop_id": crop, "moisture_shock_pct": shock}
                    response = self.post(body)
                    self.assertEqual(response.status_code, 200)
                    value = response.json()
                    self.assertEqual(value, self.post(body).json())
                    self.assertEqual(value["metadata"]["kind"], "simulation")
                    self.assertEqual(len(value["metadata"]["warnings"]), 3)
                    data = value["data"]
                    self.assertEqual(data["summary"]["facility_count"], count)
                    for row in data["facilities"]:
                        self.assertEqual(row["region"], region)
                        self.assertEqual(row["capacity_t"], row["stored_grain_t"] + row["free_capacity_t"])
                        self.assertLessEqual(row["current_fill_pct"], row["base_fill_pct"])
                        if shock == 0:
                            self.assertEqual(row["current_fill_pct"], row["base_fill_pct"])

    def test_request_validation(self):
        for change in ({"region": "all"}, {"crop_id": "wheat"}, {"crop_id": "winter_wheat"},
                       {"moisture_shock_pct": -51}, {"moisture_shock_pct": 1},
                       {"moisture_shock_pct": "-10"}, {"moisture_shock_pct": True}, {"extra": 1}):
            self.assertEqual(self.post({**self.base, **change}).status_code, 422)
        for volume in (0, -1, 100001, "25000", True):
            self.assertEqual(self.post({**self.base, "source_id": "sko_hpp_01", "volume_t": volume}, "/route").status_code, 422)
        for source, expected in (("unknown", 404), ("akm_hpp_01", 404), ("", 422), ("../bad", 422), (12, 422)):
            self.assertEqual(self.post({**self.base, "source_id": source, "volume_t": 100}, "/route").status_code, expected)
        for value in (-51, 1, "0", True):
            self.assertEqual(self.post({"yield_shock_pct": value}, "/prices").status_code, 422)
        # JSON parser accepts these tokens; strict nonfinite validation must reject them.
        for token in ("NaN", "Infinity", "-Infinity"):
            with self.assertRaises(ValueError):
                silo.PriceRequest(yield_shock_pct=float(token))

    def test_missing_and_corrupt_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(legacy_common, "DATA_DIR", Path(directory)):
                self.assertEqual(self.post().status_code, 503)
                self.assertEqual(self.post({**self.base, "source_id": "sko_hpp_01", "volume_t": 100}, "/route").status_code, 503)
        original = silo.snapshot()
        for column, value in (("capacity_t", -1), ("lat", float("nan")), ("lon", float("inf")),
                              ("base_fill_pct", 101), ("name", None), ("region", "bad")):
            df = original.copy()
            df.loc[0, column] = value
            with patch.object(silo, "load_table", return_value=df):
                self.assertEqual(self.post().status_code, 503)
        for df in (original.drop(columns="lat"), original.iloc[:0],
                   original.assign(railway_access="yes"), original.assign(capacity_t="100"),
                   pd.concat([original, original.iloc[:1]])):
            with patch.object(silo, "load_table", return_value=df):
                self.assertEqual(self.post().status_code, 503)
        with patch.object(silo, "CROPS_PATH", silo.CROPS_PATH.with_name("missing-canonical-crops.json")):
            self.assertEqual(self.post().status_code, 503)

    def test_real_snapshot_route_cost_and_full_volume(self):
        for region, source in (("sko", "sko_hpp_01"), ("kostanay", "kost_hpp_01"),
                               ("akmola", "akm_hpp_01"), ("pavlodar", "pavl_hpp_01")):
            body = {**self.base, "region": region, "source_id": source, "volume_t": 25000}
            result = self.post(body, "/route")
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.json(), self.post(body, "/route").json())
            data = result.json()["data"]
            self.assertEqual(data["status"], "route_found")
            self.assertGreaterEqual(data["target_free_capacity_t"], 25000)
            self.assertEqual(data["volume_t"], 25000)
            self.assertEqual(data["transport_work_tkm"], 25000 * data["distance_km"])
            self.assertEqual(data["cost_road_kzt"], data["transport_work_tkm"] * 38.5)
            self.assertEqual(data["co2_road_t"], data["transport_work_tkm"] * 95 / 1e6)
            self.assertEqual(data["trucks_required"], math.ceil(25000/25))
            if data["rail_flags_on_all_path_nodes"]:
                self.assertEqual(data["cost_rail_kzt"], data["transport_work_tkm"] * 22.5)
                self.assertEqual(data["wagons_required"], math.ceil(25000/68))
            self.assertFalse(data["infrastructure_verified"])

    def test_capacity_disconnection_and_intermediate_rail(self):
        # Deliberate test fixtures, never a production data fallback.
        df = pd.DataFrame([
            {"id": "a", "lat": 50., "lon": 60., "railway_access": True, "free_capacity_t": 100},
            {"id": "b", "lat": 51., "lon": 60., "railway_access": False, "free_capacity_t": 40},
            {"id": "c", "lat": 52., "lon": 60., "railway_access": True, "free_capacity_t": 100},
        ])
        result = silo.route_scenario(df, "a", 100)
        self.assertEqual(result["path_ids"], ["a", "b", "c"])
        self.assertEqual(result["target_id"], "c")
        self.assertFalse(result["rail_flags_on_all_path_nodes"])
        self.assertIsNone(result["cost_rail_kzt"])
        self.assertAlmostEqual(result["distance_km"], silo.distance(df.iloc[0], df.iloc[1]) + silo.distance(df.iloc[1], df.iloc[2]))
        self.assertEqual(silo.route_scenario(df, "a", 101)["status"], "no_route")
        df.loc[2, "lat"] = 58
        self.assertEqual(silo.route_scenario(df, "a", 100)["status"], "no_route")
        response = self.post({**self.base, "region": "pavlodar", "source_id": "pavl_hpp_01", "volume_t": 100000}, "/route")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["status"], "no_route")
        self.assertEqual(response.json()["metadata"]["kind"], "simulation")

    def test_baseline_and_extreme_prices(self):
        for shock in (0, -20, -50):
            response = self.post({"yield_shock_pct": shock}, "/prices")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), self.post({"yield_shock_pct": shock}, "/prices").json())
            data = response.json()["data"]
            for name, base, elasticity in (("wheat", 115000, .61), ("flour", 245, .61*.65), ("bread", 185, .61*.65*.42)):
                item = data[name]
                self.assertEqual(item["baseline"], base)
                self.assertAlmostEqual(item["projected"], base * (1-shock*elasticity/100))
                self.assertEqual(item["curve"][0], base)
                if shock == 0:
                    self.assertEqual(item["curve"], [base]*6)
                    self.assertEqual(item["jump_pct"], 0)


if __name__ == "__main__":
    unittest.main()
