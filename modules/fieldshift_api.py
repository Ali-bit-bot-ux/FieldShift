import logging
import os
from typing import Literal

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from modules.fieldshift_facade import RecommendationRequest, get_fieldshift_recommendation
from modules.legacy_advisor import router as advisor_router
from modules.legacy_common import LegacyDataUnavailable
from modules.legacy_risks import router as risks_router
from modules.legacy_satellite import router as satellite_router
from modules.legacy_silogrid import router as silogrid_router
from pipeline.gee_client import NasaDataUnavailable

LOGGER = logging.getLogger(__name__)


class ResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class ClimateContext(ResponseModel):
    nasa_smap_moisture_m3m3: float
    nasa_gldas_evapotranspiration_mm: float
    nasa_imerg_precipitation_mm: float
    climate_stress_level: Literal[
        "NORMAL", "MILD_STRESS", "MODERATE_DROUGHT", "SEVERE_DROUGHT"
    ]


class RotationYear(ResponseModel):
    year: int
    crop_id: str
    crop_name_ru: str
    crop_name_kk: str
    water_demand_mm: float
    water_volume_m3: float = Field(ge=0)
    soil_health_score: float
    nitrogen_balance_kg_ha: float
    rationale_ru: str
    rationale_kk: str


class Strategy(ResponseModel):
    strategy_id: Literal["recommended", "soil_resilience", "traditional_risk"]
    title_ru: str
    title_kk: str
    summary_score: float = Field(ge=0, le=100)
    water_saved_percent: float
    soil_health_delta: str
    rotation_years: list[RotationYear] = Field(min_length=3, max_length=4)
    explain: str | None = None


class RecommendationResponse(ResponseModel):
    status: Literal["success"]
    climate_context: ClimateContext
    strategies: list[Strategy] = Field(min_length=3, max_length=3)


app = FastAPI(title="FieldShift API", version="1.0.0")
origins = os.getenv(
    "FIELDSHIFT_CORS_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000,"
    "http://localhost:3001,http://127.0.0.1:3001,"
    "http://localhost:5173,http://127.0.0.1:5173",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in origins.split(",") if origin.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, exc: RequestValidationError):
    # Invalid numbers can be NaN/Infinity, which cannot be echoed as valid JSON.
    return JSONResponse(
        status_code=422,
        content={
            "detail": [
                {key: error[key] for key in ("loc", "msg", "type")}
                for error in exc.errors()
            ]
        },
    )


@app.exception_handler(NasaDataUnavailable)
async def nasa_unavailable(request: Request, exc: NasaDataUnavailable):
    LOGGER.warning("NASA climate data unavailable: %s", exc)
    return JSONResponse(
        status_code=503,
        content={"detail": "NASA climate data unavailable. Restore or refresh the regional cache."},
    )


@app.exception_handler(LegacyDataUnavailable)
async def legacy_unavailable(request: Request, exc: LegacyDataUnavailable):
    LOGGER.warning("Legacy data unavailable: %s", exc)
    return JSONResponse(
        status_code=503,
        content={"detail": f"Legacy data unavailable: {exc}"},
    )


@app.post(
    "/api/recommendation",
    response_model=RecommendationResponse,
    response_model_exclude_none=True,
    responses={503: {"description": "NASA climate data unavailable"}},
)
@app.post(
    "/fieldshift/recommendation",
    response_model=RecommendationResponse,
    response_model_exclude_none=True,
    responses={503: {"description": "NASA climate data unavailable"}},
)
def recommend(payload: RecommendationRequest):
    return get_fieldshift_recommendation(payload.model_dump())


app.include_router(satellite_router)
app.include_router(risks_router)
app.include_router(silogrid_router)
app.include_router(advisor_router)

