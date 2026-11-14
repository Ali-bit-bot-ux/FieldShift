"""Agro rotation engine. Backend 2 owns this file.

Implement CropRotationEngine.generate_strategies(...) strictly against
docs/features/fieldshift/00_CONTRACT.md and dataset/rotation_rules.json.
"""


class CropRotationEngine:
    def generate_strategies(self, soil_id, region, priorities, climate_data):
        raise NotImplementedError("Backend 2: implement CropRotationEngine")
