import json
import unittest
from pathlib import Path

from modules.m6_rotation_planner import CropRotationEngine, StrategyList

ROOT = Path(__file__).resolve().parents[1]
CROPS_PATH = ROOT / "dataset" / "crops.json"
SOILS_PATH = ROOT / "dataset" / "soils.json"


class TestRotationPlanner(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = CropRotationEngine()
        cls.valid_crops = {x["id"] for x in json.loads(CROPS_PATH.read_text(encoding="utf-8"))}
        cls.valid_soils = {x["id"] for x in json.loads(SOILS_PATH.read_text(encoding="utf-8"))}
        cls.climate_sample = {
            "nasa_smap_moisture_m3m3": 0.202,
            "nasa_gldas_evapotranspiration_mm": 444.8,
            "nasa_imerg_precipitation_mm": 297.0,
            "climate_stress_level": "MILD_STRESS",
        }
        cls.priorities_sample = {
            "yield_profit": 0.35,
            "water_saving": 0.35,
            "soil_health": 0.20,
            "cost_minimization": 0.10,
        }

    def test_generate_strategies_returns_three_contract_strategies(self):
        strategies = self.engine.generate_strategies(
            soil_id="chernozem_southern_ordinary",
            region="sko",
            priorities=self.priorities_sample,
            climate_data=self.climate_sample,
            duration_years=4,
        )
        self.assertIsInstance(strategies, StrategyList)
        self.assertEqual(len(strategies), 3)

        strat_ids = {s["strategy_id"] for s in strategies}
        self.assertEqual(strat_ids, {"recommended", "soil_resilience", "traditional_risk"})

        # Backward compatibility check: strategies["strategies"]
        self.assertEqual(len(strategies["strategies"]), 3)

    def test_all_crop_and_soil_ids_valid(self):
        strategies = self.engine.generate_strategies(
            soil_id="chernozem_southern_ordinary",
            region="sko",
            priorities=self.priorities_sample,
            climate_data=self.climate_sample,
            duration_years=4,
        )
        for s in strategies:
            for yr in s["rotation_years"]:
                self.assertIn(
                    yr["crop_id"],
                    self.valid_crops,
                    f"Invalid crop_id: {yr['crop_id']} not found in dataset/crops.json",
                )

    def test_duration_years_3_and_4(self):
        for years in (3, 4):
            strategies = self.engine.generate_strategies(
                soil_id="chernozem_southern_ordinary",
                region="kostanay",
                priorities=self.priorities_sample,
                climate_data=self.climate_sample,
                duration_years=years,
            )
            for s in strategies:
                self.assertEqual(
                    len(s["rotation_years"]),
                    years,
                    f"Strategy {s['strategy_id']} has {len(s['rotation_years'])} years, expected {years}",
                )
                self.assertEqual(
                    [yr["year"] for yr in s["rotation_years"]],
                    list(range(1, years + 1)),
                )

    def test_traditional_risk_violates_monoculture_rule_intentionally(self):
        strategies = self.engine.generate_strategies(
            soil_id="chernozem_southern_ordinary",
            region="sko",
            priorities=self.priorities_sample,
            climate_data=self.climate_sample,
            duration_years=4,
        )
        traditional = next(s for s in strategies if s["strategy_id"] == "traditional_risk")
        crops_used = [yr["crop_id"] for yr in traditional["rotation_years"]]
        self.assertEqual(crops_used, ["spring_wheat"] * 4)
        self.assertEqual(traditional["water_saved_percent"], 0.0)
        self.assertTrue(traditional["soil_health_delta"].startswith("-"))
        self.assertLess(traditional["summary_score"], 60.0)

        # Sequence validation must flag violation for continuous wheat
        valid, violations = self.engine.validate_rotation_sequence(crops_used)
        self.assertFalse(valid)
        self.assertTrue(any("spring_wheat" in v for v in violations))

    def test_recommended_and_resilience_respect_agronomic_rules(self):
        strategies = self.engine.generate_strategies(
            soil_id="chernozem_southern_ordinary",
            region="sko",
            priorities=self.priorities_sample,
            climate_data=self.climate_sample,
            duration_years=4,
        )
        for s in strategies:
            if s["strategy_id"] == "traditional_risk":
                continue
            crops_seq = [yr["crop_id"] for yr in s["rotation_years"]]
            valid, violations = self.engine.validate_rotation_sequence(crops_seq)
            self.assertTrue(valid, f"Strategy {s['strategy_id']} violates rules: {violations}")

    def test_nitrogen_balance_for_legumes(self):
        strategies = self.engine.generate_strategies(
            soil_id="chernozem_southern_ordinary",
            region="sko",
            priorities=self.priorities_sample,
            climate_data=self.climate_sample,
            duration_years=4,
        )
        legume_ids = {"chickpea", "lentil", "pea", "alfalfa"}
        for s in strategies:
            for yr in s["rotation_years"]:
                if yr["crop_id"] in legume_ids:
                    self.assertGreater(
                        yr["nitrogen_balance_kg_ha"],
                        0,
                        f"Legume {yr['crop_id']} should have positive nitrogen balance",
                    )

    def test_zero_weights_normalization(self):
        zero_weights = {
            "yield_profit": 0.0,
            "water_saving": 0.0,
            "soil_health": 0.0,
            "cost_minimization": 0.0,
        }
        strategies = self.engine.generate_strategies(
            soil_id="chernozem_southern_ordinary",
            region="sko",
            priorities=zero_weights,
            climate_data=self.climate_sample,
            duration_years=4,
        )
        for s in strategies:
            self.assertIn("explain", s)
            self.assertIn("0.25", s["rotation_years"][0]["rationale_ru"])
            self.assertIn("0.25", s["rotation_years"][0]["rationale_kk"])

    def test_all_seven_soils_supported(self):
        for soil_id in self.valid_soils:
            strategies = self.engine.generate_strategies(
                soil_id=soil_id,
                region="akmola",
                priorities=self.priorities_sample,
                climate_data=self.climate_sample,
                duration_years=4,
            )
            self.assertEqual(len(strategies), 3)

    def test_invalid_soil_raises_error(self):
        with self.assertRaises(ValueError):
            self.engine.generate_strategies(
                soil_id="mars_regolith",
                region="sko",
                priorities=self.priorities_sample,
                climate_data=self.climate_sample,
            )

    def test_accepts_payload_dictionary_directly(self):
        payload = {
            "region": "kostanay",
            "soil_type": "chestnut_dark_light",
            "field_area_ha": 400.0,
            "priorities": self.priorities_sample,
            "duration_years": 4,
            "climate_data": self.climate_sample,
        }
        strategies = self.engine.generate_strategies(payload)
        self.assertEqual(len(strategies), 3)
        self.assertEqual(len(strategies[0]["rotation_years"]), 4)

    def test_contract_output_schema(self):
        strategies = self.engine.generate_strategies(
            soil_id="chernozem_southern_ordinary",
            region="kostanay",
            priorities=self.priorities_sample,
            climate_data=self.climate_sample,
            duration_years=4,
        )
        for s in strategies:
            self.assertIn(s["strategy_id"], {"recommended", "soil_resilience", "traditional_risk"})
            self.assertIsInstance(s["title_ru"], str)
            self.assertIsInstance(s["title_kk"], str)
            self.assertTrue(len(s["title_ru"]) > 0)
            self.assertTrue(len(s["title_kk"]) > 0)

            self.assertIsInstance(s["summary_score"], float)
            self.assertGreaterEqual(s["summary_score"], 0.0)
            self.assertLessEqual(s["summary_score"], 100.0)

            self.assertIsInstance(s["water_saved_percent"], float)
            self.assertGreaterEqual(s["water_saved_percent"], 0.0)

            self.assertIsInstance(s["soil_health_delta"], str)
            self.assertTrue(s["soil_health_delta"].endswith("%"))

            for yr in s["rotation_years"]:
                self.assertIsInstance(yr["year"], int)
                self.assertIsInstance(yr["crop_id"], str)
                self.assertIsInstance(yr["crop_name_ru"], str)
                self.assertIsInstance(yr["crop_name_kk"], str)
                self.assertIsInstance(yr["water_demand_mm"], (int, float))
                self.assertIsInstance(yr["soil_health_score"], int)
                self.assertIsInstance(yr["nitrogen_balance_kg_ha"], (int, float))
                self.assertIsInstance(yr["rationale_ru"], str)
                self.assertIsInstance(yr["rationale_kk"], str)
                self.assertTrue(len(yr["rationale_ru"]) > 0)
                self.assertTrue(len(yr["rationale_kk"]) > 0)


if __name__ == "__main__":
    unittest.main()
