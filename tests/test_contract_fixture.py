import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "docs/features/fieldshift/fixtures/contract_response.json"
CROPS = ROOT / "dataset/crops.json"
SOILS = ROOT / "dataset/soils.json"


class TestContractFixture(unittest.TestCase):
    def test_fixture_has_three_contract_strategies(self):
        data = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "success")
        self.assertEqual({s["strategy_id"] for s in data["strategies"]},
                         {"recommended", "soil_resilience", "traditional_risk"})
        self.assertEqual(len(data["strategies"]), 3)

    def test_fixture_uses_real_dataset_ids(self):
        crops = {x["id"] for x in json.loads(CROPS.read_text(encoding="utf-8"))}
        soils = {x["id"] for x in json.loads(SOILS.read_text(encoding="utf-8"))}
        data = json.loads(FIXTURE.read_text(encoding="utf-8"))
        used_crops = {year["crop_id"] for s in data["strategies"] for year in s["rotation_years"]}
        self.assertTrue(used_crops.issubset(crops))
        self.assertIn("chernozem_southern_ordinary", soils)

    def test_climate_context_matches_contract_keys(self):
        data = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(set(data["climate_context"]), {
            "nasa_smap_moisture_m3m3",
            "nasa_gldas_evapotranspiration_mm",
            "nasa_imerg_precipitation_mm",
            "climate_stress_level",
        })


if __name__ == "__main__":
    unittest.main()
