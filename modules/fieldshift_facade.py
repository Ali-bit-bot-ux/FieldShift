from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from modules.m6_rotation_planner import CropRotationEngine
from pipeline.gee_client import get_nasa_climate_summary

ENGINE = CropRotationEngine()
Weight = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class Priorities(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    yield_profit: Weight
    water_saving: Weight
    soil_health: Weight
    cost_minimization: Weight


class RecommendationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    region: Literal["sko", "kostanay", "akmola", "pavlodar"]
    soil_type: str
    field_area_ha: float = Field(gt=0, le=50_000, allow_inf_nan=False)
    priorities: Priorities
    duration_years: int = Field(ge=3, le=4)

    @field_validator("soil_type")
    @classmethod
    def check_soil(cls, value: str) -> str:
        if value not in ENGINE.soils_by_id:
            raise ValueError("Unknown soil_type; use an ID from dataset/soils.json")
        return value


def get_fieldshift_recommendation(payload: dict) -> dict:
    request = RecommendationRequest.model_validate(payload)
    climate = get_nasa_climate_summary(request.region, allow_live=False)
    strategies = ENGINE.generate_strategies(
        soil_id=request.soil_type,
        region=request.region,
        priorities=request.priorities.model_dump(),
        climate_data=climate,
        duration_years=request.duration_years,
    )
    # Demand is mm per hectare; 1 mm over 1 ha equals 10 m³.
    for strategy in strategies:
        for year in strategy["rotation_years"]:
            year["water_volume_m3"] = round(
                year["water_demand_mm"] * request.field_area_ha * 10, 2
            )
    return {
        "status": "success",
        "climate_context": climate,
        "strategies": list(strategies),
    }
