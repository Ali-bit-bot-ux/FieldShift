import math
from typing import Literal

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException

from modules.legacy_common import (
    LegacyDataUnavailable,
    LegacyRequest,
    Region,
    load_json,
    load_table,
    table_records,
)

router = APIRouter(tags=["Legacy risk tools"])


class ContagionRequest(LegacyRequest):
    region: Region


class VulnerabilityRequest(LegacyRequest):
    region: Region
    year: Literal[2026] = 2026


def _finite_columns(frame: pd.DataFrame, names: tuple[str, ...]) -> None:
    for name in names:
        values = frame[name]
        if (
            not pd.api.types.is_numeric_dtype(values)
            or pd.api.types.is_bool_dtype(values)
            or not np.isfinite(values.to_numpy(dtype=float)).all()
        ):
            raise LegacyDataUnavailable(f"Invalid numeric column {name}")


@router.post("/api/contagion", summary="Archived economic association analysis, not a causal forecast")
def contagion(payload: ContagionRequest) -> dict:
    psi = load_table("phenoshift_regions.parquet", ("region_id", "year", "psi"))
    prices = load_table("economics.parquet", ("year", "wheat_price_usd_t"))
    report = load_json("causality_report.json")
    _finite_columns(psi, ("year", "psi"))
    _finite_columns(prices, ("year", "wheat_price_usd_t"))
    if psi.duplicated(["region_id", "year"]).any() or prices.duplicated("year").any():
        raise LegacyDataUnavailable("Duplicate annual economic or PSI observations")
    if not prices["wheat_price_usd_t"].gt(0).all():
        raise LegacyDataUnavailable("Invalid wheat prices")
    analysis = report.get("granger_causality") if isinstance(report, dict) else None
    if not isinstance(analysis, dict) or not isinstance(analysis.get("per_lag"), dict):
        raise LegacyDataUnavailable("Missing archived Granger analysis")
    count = analysis.get("n_observations")
    if type(count) is not int or count <= 0 or not analysis["per_lag"]:
        raise LegacyDataUnavailable("Invalid Granger observation count or lags")
    tests = []
    for key, row in analysis["per_lag"].items():
        if not isinstance(key, str) or not key.startswith("lag_") or not key[4:].isdigit():
            raise LegacyDataUnavailable("Invalid Granger lag")
        if not isinstance(row, dict):
            raise LegacyDataUnavailable("Invalid Granger result")
        p_value, f_statistic = row.get("p_value"), row.get("f_statistic")
        for value in (p_value, f_statistic):
            if type(value) not in (float, int) or not math.isfinite(value):
                raise LegacyDataUnavailable("Missing or invalid Granger statistic")
        if not 0 <= p_value <= 1 or f_statistic < 0 or int(key[4:]) <= 0:
            raise LegacyDataUnavailable("Out-of-range Granger statistic")
        tests.append({
            "lag_years": int(key[4:]), "p_value": p_value,
            "f_statistic": f_statistic, "significant": p_value < 0.05,
        })
    selected = psi.loc[psi["region_id"] == payload.region, ["year", "psi"]]
    if selected.empty:
        raise HTTPException(404, "No archived PSI observations for this region")
    merged = selected.merge(prices[["year", "wheat_price_usd_t"]], on="year", validate="one_to_one").sort_values("year")
    if merged.empty:
        raise HTTPException(404, "No overlapping PSI and price observations")
    merged["price_status"] = np.where(merged["year"] >= 2025, "estimate", "unverified_historical")
    significant = any(test["significant"] for test in tests)
    return {
        "status": "success", "module": "contagion",
        "data": {
            "region": payload.region,
            "graph": {
                "kind": "conceptual_unweighted",
                "nodes": [
                    {"id": "water", "name_ru": "Влага", "name_kk": "Ылғал"},
                    {"id": "vegetation", "name_ru": "Растения", "name_kk": "Өсімдіктер"},
                    {"id": "storage", "name_ru": "Хранение зерна", "name_kk": "Астық сақтау"},
                    {"id": "market", "name_ru": "Рынок", "name_kk": "Нарық"},
                ],
                "edges": [
                    {"source": "water", "target": "vegetation"},
                    {"source": "vegetation", "target": "storage"},
                    {"source": "storage", "target": "market"},
                ],
            },
            "scatter": table_records(merged),
            "granger": {
                "scope": "legacy_aggregate_not_region_specific",
                "hypothesis": "PSI -> annual wheat price change",
                "n_observations": count, "lag_unit": "years", "significance_threshold": 0.05,
                "per_lag": sorted(tests, key=lambda test: test["lag_years"]),
                "significant": significant,
                "conclusion": "association_detected_not_causality" if significant else "no_significant_association",
            },
            "var_model": {"status": "unavailable", "reason": "Archived model could not be estimated reliably"},
        },
        "metadata": {
            "kind": "retrospective",
            "sources": ["phenoshift_regions.parquet", "economics.parquet", "causality_report.json"],
            "units": {"wheat_price_usd_t": "USD/t", "psi": "dimensionless", "lag": "years"},
            "warnings": [
                "The graph is a conceptual chain, not a verified geographical or causal network.",
                "The archived Granger report is not recomputed for the selected region or the displayed scatter.",
                "Eight annual observations are insufficient for a strong causal claim; lags are years, not months.",
                "Price provenance is not verified row by row; 2025-2026 prices are estimates.",
            ],
        },
    }


@router.post("/api/vulnerability", summary="2026 district risk snapshot, not farm-level bankruptcy prediction")
def vulnerability(payload: VulnerabilityRequest) -> dict:
    columns = (
        "region_id", "district_id", "name", "name_kk", "lat", "lon", "area_ha",
        "nearest_elevator_km", "nearest_elevator_name", "psi_value", "smai_value",
        "vuln_score", "risk_level", "source",
    )
    frame = load_table("vuln_map_regions.parquet", columns)
    numeric = ("lat", "lon", "area_ha", "nearest_elevator_km", "psi_value", "smai_value", "vuln_score")
    _finite_columns(frame, numeric)
    if (
        frame[list(columns)].isna().any().any()
        or frame.duplicated(["region_id", "district_id"]).any()
        or not frame["source"].eq("district_registry").all()
        or not frame["lat"].between(-90, 90).all()
        or not frame["lon"].between(-180, 180).all()
        or not frame["area_ha"].gt(0).all()
        or not frame["nearest_elevator_km"].ge(0).all()
        or not frame["vuln_score"].between(0, 100).all()
    ):
        raise LegacyDataUnavailable("Invalid district vulnerability snapshot")
    expected_levels = np.select([frame["vuln_score"] > 70, frame["vuln_score"] > 40], ["HIGH", "MEDIUM"], default="LOW")
    if not frame["risk_level"].eq(expected_levels).all():
        raise LegacyDataUnavailable("District risk labels do not match scores")
    selected = frame.loc[frame["region_id"] == payload.region, list(columns)].sort_values(["vuln_score", "district_id"], ascending=[False, True])
    if selected.empty:
        raise HTTPException(404, "No district risk data for this region")
    counts = {}
    for level in ("HIGH", "MEDIUM", "LOW"):
        group = selected.loc[selected["risk_level"] == level]
        counts[level] = {"count": len(group), "percent": round(len(group) / len(selected) * 100, 1), "area_ha": float(group["area_ha"].sum())}
    return {
        "status": "success", "module": "vulnerability",
        "data": {
            "region": payload.region, "year": payload.year,
            "districts": table_records(selected),
            "summary": {
                "total_districts": len(selected), "risk_counts": counts,
                "average_score": round(float(selected["vuln_score"].mean()), 1),
                "max_score": float(selected["vuln_score"].max()),
                "median_nearest_elevator_km": round(float(selected["nearest_elevator_km"].median()), 1),
            },
        },
        "metadata": {
            "kind": "model_snapshot", "sources": ["vuln_map_regions.parquet"],
            "reference_year": 2026, "snapshot_generated_at": None,
            "weights": {"psi": 0.4, "smai": 0.3, "elevator_distance": 0.2, "inverse_area": 0.1},
            "units": {"area_ha": "ha", "nearest_elevator_km": "km", "vuln_score": "index 0-100"},
            "warnings": [
                "These are 20 district proxies across four regions, not individual farms or surveyed field boundaries.",
                "Distances use a partly procedural elevator inventory; the risk score is a heuristic, not a bankruptcy forecast.",
                "The snapshot uses 2026 PSI and regional SMAI with soil adjustments; its exact generation date is not recorded.",
                "All district areas exceed 2000 ha, so the inverse-area component is zero for this snapshot.",
                "No synthetic historical boosts or dashboard scenario overrides are applied.",
            ],
        },
    }
