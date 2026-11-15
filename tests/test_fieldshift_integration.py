import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi.testclient import TestClient
from pydantic import ValidationError

from modules import fieldshift_facade as facade
from modules.fieldshift_api import app
from pipeline import gee_client as gc

PAYLOAD = {
    "region": "sko",
    "soil_type": "chernozem_southern_ordinary",
    "field_area_ha": 400.0,
    "priorities": {
        "yield_profit": 0.35,
        "water_saving": 0.35,
        "soil_health": 0.20,
        "cost_minimization": 0.10,
    },
    "duration_years": 4,
}
STRATEGIES = ["recommended", "soil_resilience", "traditional_risk"]


class TestFieldshiftIntegration(unittest.TestCase):
    def setUp(self):
        self.enterContext(mock.patch.object(gc, "_ee", side_effect=AssertionError("No GEE")))
        self.enterContext(mock.patch.object(gc.urllib.request, "urlopen", side_effect=AssertionError("No network")))
        self.client = self.enterContext(TestClient(app))

    def test_all_regions_soils_and_durations_with_real_backends(self):
        for region in gc.REGIONS:
            for soil in facade.ENGINE.soils_by_id:
                for duration in (3, 4):
                    with self.subTest(region=region, soil=soil, duration=duration):
                        payload = dict(PAYLOAD, region=region, soil_type=soil, duration_years=duration)
                        response = self.client.post("/api/recommendation", json=payload)
                        self.assertEqual(response.status_code, 200, response.text)
                        body = response.json()
                        self.assertEqual(set(body), {"status", "climate_context", "strategies"})
                        self.assertEqual(body["status"], "success")
                        climate = gc.get_nasa_climate_summary(region)
                        self.assertEqual(body["climate_context"], climate)
                        self.assertEqual(set(climate), set(gc.CONTRACT_CLIMATE_KEYS))
                        expected = facade.ENGINE.generate_strategies(
                            soil_id=soil, region=region, priorities=PAYLOAD["priorities"],
                            climate_data=climate, duration_years=duration,
                        )
                        self.assertEqual(body["strategies"], expected)
                        self.assertEqual([s["strategy_id"] for s in body["strategies"]], STRATEGIES)
                        for strategy in body["strategies"]:
                            self.assertEqual(len(strategy["rotation_years"]), duration)
                            self.assertTrue(strategy["title_ru"])
                            self.assertTrue(strategy["title_kk"])
                            self.assertNotIn("explain", strategy)
                            for year in strategy["rotation_years"]:
                                self.assertIn(year["crop_id"], facade.ENGINE.crops_by_id)
                                self.assertTrue(year["rationale_ru"])
                                self.assertTrue(year["rationale_kk"])

    def test_nasa_context_and_duration_are_passed_to_engine(self):
        payload = dict(PAYLOAD, region="kostanay", duration_years=3)
        with mock.patch.object(facade.ENGINE, "generate_strategies", wraps=facade.ENGINE.generate_strategies) as generate:
            result = facade.get_fieldshift_recommendation(payload)
        self.assertEqual(generate.call_args.kwargs["climate_data"], gc.get_nasa_climate_summary("kostanay"))
        self.assertEqual(generate.call_args.kwargs["duration_years"], 3)
        self.assertEqual(result["climate_context"], generate.call_args.kwargs["climate_data"])

    def test_non_normalized_weights_match_normalized_result(self):
        payload = dict(PAYLOAD, priorities={key: value * 2 for key, value in PAYLOAD["priorities"].items()})
        response = self.client.post("/api/recommendation", json=payload)
        normal = self.client.post("/api/recommendation", json=PAYLOAD)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), normal.json())

    def test_zero_priorities_keep_engine_explanation(self):
        payload = dict(PAYLOAD, priorities={key: 0 for key in PAYLOAD["priorities"]})
        response = self.client.post("/api/recommendation", json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        for strategy in response.json()["strategies"]:
            self.assertTrue(strategy["explain"])
        equal = dict(PAYLOAD, priorities={key: 0.25 for key in PAYLOAD["priorities"]})
        result = response.json()
        self.assertEqual(result, facade.get_fieldshift_recommendation(payload))
        normal = self.client.post("/api/recommendation", json=equal).json()
        for zero_strategy, equal_strategy in zip(result["strategies"], normal["strategies"]):
            for key in ("summary_score", "water_saved_percent", "soil_health_delta"):
                self.assertEqual(zero_strategy[key], equal_strategy[key])
            for zero_year, equal_year in zip(zero_strategy["rotation_years"], equal_strategy["rotation_years"]):
                for key in ("crop_id", "water_demand_mm", "soil_health_score", "nitrogen_balance_kg_ha"):
                    self.assertEqual(zero_year[key], equal_year[key])

    def test_area_boundaries(self):
        for area in (0.1, 50_000):
            with self.subTest(area=area):
                response = self.client.post("/api/recommendation", json=dict(PAYLOAD, field_area_ha=area))
                self.assertEqual(response.status_code, 200, response.text)

    def test_invalid_input_never_calls_backends(self):
        invalid = [
            {},
            dict(PAYLOAD, region="almaty"),
            dict(PAYLOAD, soil_type="../secrets"),
            dict(PAYLOAD, field_area_ha=0),
            dict(PAYLOAD, field_area_ha=-1),
            dict(PAYLOAD, field_area_ha=50_001),
            dict(PAYLOAD, field_area_ha=True),
            dict(PAYLOAD, field_area_ha="400"),
            dict(PAYLOAD, duration_years=2),
            dict(PAYLOAD, duration_years=5),
            dict(PAYLOAD, duration_years=3.5),
            dict(PAYLOAD, duration_years="4"),
            dict(PAYLOAD, duration_years=True),
            dict(PAYLOAD, priorities={}),
            dict(PAYLOAD, priorities=None),
            dict(PAYLOAD, priorities=dict(PAYLOAD["priorities"], water_saving=-0.1)),
            dict(PAYLOAD, priorities=dict(PAYLOAD["priorities"], water_saving=35)),
            dict(PAYLOAD, priorities=dict(PAYLOAD["priorities"], water_saving=True)),
            dict(PAYLOAD, priorities=dict(PAYLOAD["priorities"], duration_years=4)),
            dict(PAYLOAD, climate_context={"climate_stress_level": "NORMAL"}),
        ]
        with mock.patch.object(facade, "get_nasa_climate_summary") as climate:
            for payload in invalid:
                with self.subTest(payload=payload):
                    response = self.client.post("/api/recommendation", json=payload)
                    self.assertEqual(response.status_code, 422, response.text)
                    self.assertTrue(response.json()["detail"])
            climate.assert_not_called()

    def test_nonfinite_numbers_return_json_error(self):
        for value in (float("nan"), float("inf"), -float("inf")):
            for field in ("field_area_ha", "water_saving"):
                with self.subTest(value=value, field=field):
                    payload = copy.deepcopy(PAYLOAD)
                    if field == "water_saving":
                        payload["priorities"][field] = value
                    else:
                        payload[field] = value
                    response = self.client.post(
                        "/api/recommendation", content=json.dumps(payload),
                        headers={"Content-Type": "application/json"},
                    )
                    self.assertEqual(response.status_code, 422, response.text)
                    self.assertIsInstance(response.json()["detail"], list)

    def test_malformed_json_is_rejected(self):
        response = self.client.post("/api/recommendation", content="{broken", headers={"Content-Type": "application/json"})
        self.assertEqual(response.status_code, 422)

    def test_missing_cache_offline_returns_503_not_fixture(self):
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch.object(gc, "CACHE_DIR", Path(temporary)), mock.patch.object(
                gc, "fetch_nasa_climate_series", side_effect=AssertionError("No live fallback")
            ) as fetch:
                response = self.client.post("/api/recommendation", json=PAYLOAD)
                fetch.assert_not_called()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("strategies", response.json())
        self.assertNotIn(temporary, response.text)

    def test_corrupt_cache_is_unavailable_before_engine_runs(self):
        cached = gc.load_cached_climate("sko")
        documents = [[], None, {}, "broken", b"\xff"]
        for key, value in (
            ("nasa_imerg_precipitation_mm", -1),
            ("nasa_gldas_evapotranspiration_mm", 0),
            ("nasa_smap_moisture_m3m3", 1.5),
            ("nasa_smap_moisture_m3m3", None),
            ("nasa_smap_moisture_m3m3", True),
            ("nasa_imerg_precipitation_mm", "300"),
            ("nasa_imerg_precipitation_mm", float("nan")),
            ("nasa_imerg_precipitation_mm", float("inf")),
        ):
            document = copy.deepcopy(cached)
            document["summary"][key] = value
            documents.append(document)
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch.object(gc, "CACHE_DIR", Path(temporary)), mock.patch.object(
                facade.ENGINE, "generate_strategies"
            ) as engine:
                for document in documents:
                    with self.subTest(document_type=type(document).__name__):
                        if isinstance(document, bytes):
                            (Path(temporary) / "sko.json").write_bytes(document)
                        else:
                            (Path(temporary) / "sko.json").write_text(json.dumps(document), encoding="utf-8")
                        response = self.client.post("/api/recommendation", json=PAYLOAD)
                        self.assertEqual(response.status_code, 503, response.text)
                engine.assert_not_called()

    def test_facade_validates_before_nasa(self):
        with mock.patch.object(facade, "get_nasa_climate_summary") as climate:
            with self.assertRaises(ValidationError):
                facade.get_fieldshift_recommendation(dict(PAYLOAD, duration_years=0))
            climate.assert_not_called()

    def test_facade_does_not_mutate_input(self):
        payload = copy.deepcopy(PAYLOAD)
        facade.get_fieldshift_recommendation(payload)
        self.assertEqual(payload, PAYLOAD)

    def test_cors_allows_local_react_and_blocks_other_origins(self):
        for origin in ("http://localhost:3001", "http://localhost:5173"):
            with self.subTest(origin=origin):
                headers = {
                    "Origin": origin,
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "content-type",
                }
                preflight = self.client.options("/api/recommendation", headers=headers)
                self.assertEqual(preflight.status_code, 200)
                self.assertEqual(preflight.headers["access-control-allow-origin"], origin)
                response = self.client.post("/api/recommendation", json=PAYLOAD, headers={"Origin": origin})
                self.assertEqual(response.headers["access-control-allow-origin"], origin)
        response = self.client.options("/api/recommendation", headers={
            "Origin": "https://untrusted.example", "Access-Control-Request-Method": "POST",
        })
        self.assertEqual(response.status_code, 400)
        self.assertNotIn("access-control-allow-origin", response.headers)

    def test_cors_headers_on_error_responses(self):
        headers = {"Origin": "http://localhost:3001"}
        invalid = self.client.post("/api/recommendation", json={}, headers=headers)
        self.assertEqual(invalid.headers["access-control-allow-origin"], headers["Origin"])
        with mock.patch.object(facade, "get_nasa_climate_summary", side_effect=gc.NasaDataUnavailable("offline")):
            unavailable = self.client.post("/api/recommendation", json=PAYLOAD, headers=headers)
        self.assertEqual(unavailable.status_code, 503)
        self.assertEqual(unavailable.headers["access-control-allow-origin"], headers["Origin"])

    def test_openapi_describes_request_and_response(self):
        schema = self.client.get("/openapi.json").json()
        endpoint = schema["paths"]["/api/recommendation"]["post"]
        self.assertIn("requestBody", endpoint)
        self.assertIn("200", endpoint["responses"])
        self.assertIn("422", endpoint["responses"])
        self.assertIn("503", endpoint["responses"])


if __name__ == "__main__":
    unittest.main()
