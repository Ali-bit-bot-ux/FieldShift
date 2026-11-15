"""Portable, exact-ID loader for the existing bilingual drought knowledge base."""

import json
import math
from pathlib import Path

from .legacy_common import LegacyDataUnavailable

DATASET_DIR = Path(__file__).resolve().parents[1] / "dataset"
GENERIC_PRACTICES = {"foliar_osmoprotectants", "antitranspirant_spraying", "no_till_stubble"}


def _reject_constant(value):
    raise ValueError(f"Non-finite JSON number: {value}")


def _validate_record(item, strings, lists=(), numbers=()):
    if not isinstance(item, dict):
        raise ValueError("Expected dataset object")
    for key in ("id", *strings):
        if not isinstance(item.get(key), str) or not item[key].strip():
            raise ValueError(f"Missing or invalid {key}")
    for key in lists:
        value = item.get(key)
        if not isinstance(value, list) or not value or any(not isinstance(v, str) or not v for v in value):
            raise ValueError(f"Invalid list {key}")
    for key in numbers:
        value = item.get(key)
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError(f"Invalid number {key}")
    # Translations are optional in the legacy engine, but must have the same type.
    for key, value in item.items():
        if key.endswith("_kk"):
            base = item.get(key[:-3], item.get(key[:-3] + "_ru"))
            if base is not None and (type(value) is not type(base) or not value):
                raise ValueError(f"Invalid translation {key}")
            if isinstance(value, list) and (len(value) != len(base) or any(not isinstance(v, str) or not v for v in value)):
                raise ValueError(f"Invalid translated list {key}")


class DroughtDataset:
    def __init__(self, dataset_dir=None):
        self.dataset_dir = Path(dataset_dir) if dataset_dir is not None else DATASET_DIR
        try:
            self.crops = self._load("crops.json", (
                "name_ru", "latin_name", "crop_type", "drought_mechanism", "root_depth_meters",
                "root_type", "transpiration_coefficient", "drought_symptoms"),
                ("critical_water_phases", "optimal_soil_types"),
                ("drought_tolerance_score", "wilting_threshold_swc_percent"))
            self.soils = self._load("soils.json", (
                "name_ru", "wrb_classification", "region_kz", "texture", "cracking_tendency",
                "crust_formation_risk", "primary_vulnerability", "recommended_tillage_focus"),
                numbers=("available_water_capacity_mm_per_m",))
            self.practices = self._load("drought_practices.json", (
                "name_ru", "category", "action_horizon", "cost_level", "estimated_water_saving_percent",
                "implementation_protocol", "practical_limitations"), ("gale_reference_ids",))
            self.references = self._load("references.json", (
                "source", "title", "authors", "journal_or_publisher", "doi_or_gale_doc_id", "key_findings"),
                numbers=("year",))
            self.matrix = list(self._load("soil_crop_mitigation_matrix.json", (
                "crop_id", "soil_id", "drought_risk_mechanism", "expected_yield_loss_reduction", "scientific_basis"),
                ("emergency_actions_0_48h", "seasonal_tactical_actions", "long_term_strategic_actions",
                 "recommended_practice_ids")).values())
            errors = self.validate_integrity()
            if errors:
                raise ValueError("; ".join(errors))
        except (OSError, ValueError, TypeError, KeyError) as exc:
            raise LegacyDataUnavailable("Drought knowledge base is missing or invalid") from exc

    def _load(self, filename, strings, lists=(), numbers=()):
        with (self.dataset_dir / filename).open(encoding="utf-8") as stream:
            records = json.load(stream, parse_constant=_reject_constant)
        if not isinstance(records, list) or not records:
            raise ValueError(f"Empty or invalid {filename}")
        indexed = {}
        for item in records:
            _validate_record(item, strings, lists, numbers)
            if item["id"] in indexed:
                raise ValueError(f"Duplicate ID in {filename}")
            indexed[item["id"]] = item
        return indexed

    def validate_integrity(self):
        errors = []
        pairs = set()
        for entry in self.matrix:
            pair = (entry["crop_id"], entry["soil_id"])
            if pair in pairs or pair[0] not in self.crops or pair[1] not in self.soils:
                errors.append(f"Invalid matrix pair: {pair}")
            pairs.add(pair)
            if not set(entry["recommended_practice_ids"]).issubset(self.practices):
                errors.append("Unknown matrix practice")
        for crop in self.crops.values():
            if not set(crop["optimal_soil_types"]).issubset(self.soils):
                errors.append("Unknown optimal soil")
        for practice in self.practices.values():
            if not set(practice["gale_reference_ids"]).issubset(self.references):
                errors.append("Unknown citation")
        if not GENERIC_PRACTICES.issubset(self.practices):
            errors.append("Missing generic practice")
        return errors

    def search_crop(self, query):
        return self.crops.get(query)

    def search_soil(self, query):
        return self.soils.get(query)

    def get_matrix_entry(self, crop_id, soil_id):
        """Never substitute another crop's rule, even on the same soil."""
        return next((entry for entry in self.matrix
                     if entry["crop_id"] == crop_id and entry["soil_id"] == soil_id), None)
