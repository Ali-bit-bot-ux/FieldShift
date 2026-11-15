"""Isolated HTTP contract tests; no dependency on main router wiring."""

import importlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from modules import legacy_advisor
from modules.drought_dataset import DATASET_DIR, DroughtDataset
from modules.legacy_common import LegacyDataUnavailable


class LegacyAdvisorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app = FastAPI()
        app.include_router(legacy_advisor.router)

        @app.exception_handler(LegacyDataUnavailable)
        async def unavailable(request, exc):
            return JSONResponse(status_code=503, content={"detail": str(exc)})

        @app.exception_handler(RequestValidationError)
        async def invalid_request(request, exc: RequestValidationError):
            return JSONResponse(
                status_code=422,
                content={
                    "detail": [
                        {key: error[key] for key in ("loc", "msg", "type")}
                        for error in exc.errors()
                    ]
                },
            )

        cls.client = TestClient(app)
        cls.dataset = DroughtDataset()

    def tearDown(self):
        legacy_advisor.get_engine.cache_clear()

    def post(self, **overrides):
        return self.client.post("/api/agroadvisor", json={"crop_id": "spring_wheat", **overrides})

    def test_all_pairs_bilingual_stable_and_citations(self):
        self.assertEqual((len(self.dataset.crops), len(self.dataset.soils)), (16, 7))
        for lang in ("ru", "kk"):
            for crop_id in self.dataset.crops:
                for soil_id in self.dataset.soils:
                    with self.subTest(lang=lang, crop=crop_id, soil=soil_id):
                        response = self.post(crop_id=crop_id, soil_id=soil_id, lang=lang)
                        self.assertEqual(response.status_code, 200, response.text)
                        body = response.json()
                        self.assertEqual(body, self.post(crop_id=crop_id, soil_id=soil_id, lang=lang).json())
                        self.assertEqual(set(body), {"status", "module", "data", "metadata"})
                        self.assertEqual(body["module"], "agroadvisor")
                        self.assertEqual(body["status"], "success")
                        data, meta = body["data"], body["metadata"]
                        self.assertEqual(data["crop_profile"]["id"], crop_id)
                        self.assertEqual(data["soil_profile"]["id"], soil_id)
                        self.assertEqual(data["crop_profile"]["name"], self.dataset.crops[crop_id][f"name_{lang}"])
                        rule = self.dataset.get_matrix_entry(crop_id, soil_id)
                        self.assertEqual(meta["recommendation_scope"], "exact" if rule else "generic")
                        self.assertEqual(meta["kind"], "knowledge_base")
                        self.assertGreaterEqual(len(meta["warnings"]), 3)
                        citations = data["academic_citations"]
                        ids = [ref["id"] for ref in citations]
                        self.assertEqual(ids, sorted(set(ids)))
                        self.assertEqual(meta["sources"], ids)
                        for ref in citations:
                            self.assertEqual(ref, self.dataset.references[ref["id"]])
                        if rule:
                            suffix = "_kk" if lang == "kk" else ""
                            self.assertEqual(data["drought_risk_mechanism"], rule["drought_risk_mechanism" + suffix])
                            self.assertEqual(data["action_roadmap"]["emergency_0_48h"], rule["emergency_actions_0_48h" + suffix])

    def test_no_wheat_rule_leaks_to_flax(self):
        for soil in ("chestnut_dark_light", "chernozem_southern_ordinary", "sandy_arenosol"):
            for lang in ("ru", "kk"):
                wheat = self.post(soil_id=soil, lang=lang).json()
                flax = self.post(crop_id="flax_linseed", soil_id=soil, lang=lang).json()
                self.assertEqual(wheat["metadata"]["recommendation_scope"], "exact")
                self.assertEqual(flax["metadata"]["recommendation_scope"], "generic")
                self.assertIsNone(self.dataset.get_matrix_entry("flax_linseed", soil))
                self.assertNotEqual(wheat["data"]["action_roadmap"], flax["data"]["action_roadmap"])
                self.assertIn(self.dataset.crops["flax_linseed"][f"name_{lang}"], flax["data"]["drought_risk_mechanism"])

    def test_auto_soil_and_default_language(self):
        for crop in self.dataset.crops.values():
            for extra in ({}, {"soil_id": None}):
                data = self.post(crop_id=crop["id"], **extra).json()["data"]
                self.assertEqual(data["soil_profile"]["id"], crop["optimal_soil_types"][0])
                self.assertEqual(data["lang"], "ru")

    def test_options_and_canonical_stages(self):
        for lang in ("ru", "kk"):
            response = self.client.get("/api/agroadvisor/options", params={"lang": lang})
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertEqual(len(body["data"]["soils"]), 7)
            self.assertEqual(body["metadata"]["sources"], sorted(self.dataset.references))
            for crop in body["data"]["crops"]:
                self.assertIn("name_ru", crop)
                self.assertIn("name_kk", crop)
                for choice in crop["stage_choices"]:
                    for stage in (choice["value"], choice[f"label_{lang}"]):
                        data = self.post(crop_id=crop["id"], lang=lang, growth_stage=stage).json()["data"]
                        self.assertIn(choice[f"label_{lang}"], data["stage_warning"])
            for stage in (None, "", "   ", "unknown phase", "кущение (критическая фаза)"):
                self.assertIsNone(self.post(lang=lang, growth_stage=stage).json()["data"]["stage_warning"])
        self.assertIsNotNone(self.post(growth_stage="выход в трубку").json()["data"]["stage_warning"])
        self.assertEqual(self.post(growth_stage="x" * 120).status_code, 200)

    def test_invalid_inputs(self):
        invalid = [
            {"crop_id": x} for x in ("", "SPRING_WHEAT", " spring_wheat", "пшеница", "unknown", None, 1, True, [])
        ] + [{"soil_id": x} for x in ("", "CHESTNUT_DARK_LIGHT", "каштан", "unknown", 1, False, {})]
        invalid += [{"lang": x} for x in ("en", "RU", None, 1)]
        invalid += [{"growth_stage": x} for x in ("x" * 121, 10, True, [])]
        invalid += [{"extra": 1}]
        for payload in invalid:
            with self.subTest(payload=payload):
                self.assertEqual(self.post(**payload).status_code, 422)
        self.assertEqual(self.client.post("/api/agroadvisor", json={}).status_code, 422)
        for token in ("NaN", "Infinity", "-Infinity"):
            response = self.client.post("/api/agroadvisor", content='{"crop_id": ' + token + '}', headers={"Content-Type": "application/json"})
            self.assertEqual(response.status_code, 422)
        self.assertEqual(self.client.get("/api/agroadvisor/options?lang=en").status_code, 422)

    def test_lazy_import_and_cache(self):
        legacy_advisor.get_engine.cache_clear()
        with patch("modules.drought_dataset.Path.open", side_effect=FileNotFoundError):
            importlib.reload(legacy_advisor)
            importlib.import_module("modules.m6_rotation_planner")
            with self.assertRaises(LegacyDataUnavailable):
                legacy_advisor.get_engine()
        self.assertIs(legacy_advisor.get_engine(), legacy_advisor.get_engine())

    def test_missing_corrupt_and_invalid_data_are_503(self):
        files = ("crops.json", "soils.json", "drought_practices.json", "soil_crop_mitigation_matrix.json", "references.json")
        originals = {name: (DATASET_DIR / name).read_text(encoding="utf-8") for name in files}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in files:
                for broken in (None, "{", "[]", "{}", '[{"id":"broken"}]'):
                    with self.subTest(file=name, broken=broken):
                        for filename, text in originals.items():
                            (root / filename).write_text(text, encoding="utf-8")
                        if broken is None:
                            (root / name).unlink()
                        else:
                            (root / name).write_text(broken, encoding="utf-8")
                        legacy_advisor.get_engine.cache_clear()
                        with patch("modules.drought_dataset.DATASET_DIR", root):
                            self.assertEqual(self.post().status_code, 503)
                            self.assertEqual(self.client.get("/api/agroadvisor/options").status_code, 503)
            mutations = [
                ("crops.json", "optimal_soil_types", ["unknown"]),
                ("crops.json", "critical_water_phases_kk", []),
                ("crops.json", "drought_tolerance_score", float("nan")),
                ("drought_practices.json", "gale_reference_ids", ["unknown"]),
                ("soil_crop_mitigation_matrix.json", "crop_id", "unknown"),
                ("soil_crop_mitigation_matrix.json", "emergency_actions_0_48h", "not a list"),
            ]
            for name, key, value in mutations:
                for filename, text in originals.items():
                    (root / filename).write_text(text, encoding="utf-8")
                records = json.loads(originals[name])
                records[0][key] = value
                (root / name).write_text(json.dumps(records), encoding="utf-8")
                legacy_advisor.get_engine.cache_clear()
                with patch("modules.drought_dataset.DATASET_DIR", root):
                    self.assertEqual(self.post().status_code, 503)


if __name__ == "__main__":
    unittest.main()
