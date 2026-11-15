"""Deterministic legacy scenarios; not a facility registry or operational planner."""
import heapq
import json
import math
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import Field

from modules import legacy_common as common
from modules.legacy_common import LegacyDataUnavailable, LegacyRequest, load_table, table_records

# Compatibility with the integrator's Region -> Region4 rename.
Region4 = common.Region4 if hasattr(common, "Region4") else common.Region
Crop = Literal["spring_wheat", "spring_barley", "sunflower", "flax_linseed", "chickpea"]
CROPS_PATH = Path(__file__).resolve().parents[1] / "dataset" / "crops.json"
REQUIRED = ("id", "name", "region", "lat", "lon", "capacity_t", "railway_access", "base_fill_pct")
REGIONS = {"sko", "kostanay", "akmola", "pavlodar"}
WARNINGS = [
    "Snapshot contains invented facilities: 60 named seeds and 147 procedural examples; all fills are formula-generated, not a real registry or live stock.",
    "Proximity routing is not real infrastructure; rail flags do not verify any railway corridor. Not operational optimization.",
    "Prices are heuristic deterministic scenarios, not calibrated Granger estimates or statistical forecasts.",
]
router = APIRouter()


class SiloRequest(LegacyRequest):
    region: Region4
    crop_id: Crop
    moisture_shock_pct: float = Field(default=0, ge=-50, le=0)


class RouteRequest(SiloRequest):
    source_id: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")
    volume_t: float = Field(gt=0, le=100000)


class PriceRequest(LegacyRequest):
    yield_shock_pct: float = Field(default=0, ge=-50, le=0)


def envelope(data, coefficients=None):
    return {"status": "success", "module": "silogrid", "data": data,
            "metadata": {"kind": "simulation", "sources": [
                "EcoEconomicAnalyzer/data/processed/silos.parquet (copied snapshot)",
                "EcoEconomicAnalyzer/modules/elevator_logistics.py (legacy formula assumptions)",
                "EcoEconomicAnalyzer/dashboard/context.py (sensitivity formula)",
                "dataset/crops.json (canonical crop coefficients)"],
                "warnings": WARNINGS, "coefficients": coefficients or {},
                "units": {"volume": "t", "distance": "km", "transport_work": "t*km",
                          "cost": "KZT", "emissions": "t CO2", "fill": "%"}}}


def snapshot():
    try:
        df = load_table("silos.parquet", required_columns=REQUIRED).loc[:, REQUIRED].copy()
        for column in ("id", "name", "region"):
            if not df[column].map(lambda x: isinstance(x, str) and bool(x.strip())).all():
                raise ValueError("Invalid text column")
        if df.id.duplicated().any() or set(df.region) != REGIONS:
            raise ValueError("Invalid IDs or missing regions")
        for column, low, high in (("lat", -90, 90), ("lon", -180, 180),
                                  ("capacity_t", 1, 1000000000), ("base_fill_pct", 0, 100)):
            values = df[column]
            if (not pd.api.types.is_numeric_dtype(values) or pd.api.types.is_bool_dtype(values)
                    or not np.isfinite(values.to_numpy(dtype=float)).all()
                    or not values.between(low, high).all()):
                raise ValueError("Invalid numeric column")
        if df.railway_access.isna().any() or not pd.api.types.is_bool_dtype(df.railway_access):
            raise ValueError("Invalid rail flags")
        return df.sort_values("id").reset_index(drop=True)
    except LegacyDataUnavailable:
        raise
    except (OSError, ValueError, TypeError, KeyError, ImportError) as exc:
        raise LegacyDataUnavailable("Unusable silos.parquet snapshot") from exc


def loads(request):
    try:
        crops = json.loads(CROPS_PATH.read_text(encoding="utf-8"))
        crop = next(c for c in crops if c["id"] == request.crop_id)
        kc, tolerance = crop["fao_kc_coefficient"], crop["drought_tolerance_score"]
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
               for v in (kc, tolerance)) or not 0 < kc <= 3 or not 0 < tolerance <= 5:
            raise ValueError("Invalid crop coefficients")
    except (OSError, ValueError, TypeError, KeyError, StopIteration) as exc:
        raise LegacyDataUnavailable("Unusable canonical crop coefficients") from exc
    sensitivity = (kc / 1.10) * (4.2 / max(tolerance, 1.0))
    df = snapshot()
    df = df[df.region == request.region].copy()
    drop = -request.moisture_shock_pct / 100 * sensitivity * 0.45
    df["stress_drop_pct"] = drop * 100
    df["current_fill_pct"] = (df.base_fill_pct * (1 - drop)).clip(5, 98).round(1)
    df["stored_grain_t"] = (df.capacity_t * df.current_fill_pct / 100).round(0)
    df["free_capacity_t"] = df.capacity_t - df.stored_grain_t
    df["status_code"] = np.where(df.current_fill_pct > 70, "FULL",
                                 np.where(df.current_fill_pct >= 30, "OPTIMAL", "DEFICIT"))
    return df, {"fao_kc_coefficient": kc, "drought_tolerance_score": tolerance,
                "crop_sensitivity": sensitivity, "stress_multiplier": 0.45,
                "sensitivity_formula": "(kc / 1.10) * (4.2 / max(tolerance, 1))",
                "coefficient_units": "dimensionless", "fill_clip_pct": [5, 98]}


def distance(a, b):
    lat1, lat2 = math.radians(a["lat"]), math.radians(b["lat"])
    h = math.sin((lat2-lat1)/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(math.radians(b["lon"]-a["lon"])/2)**2
    return 6371 * 2 * math.asin(math.sqrt(min(1, h)))


def route_scenario(df, source_id, volume):
    """Shortest reachable proximity path, with full receiving capacity; no fallback."""
    rows = {row["id"]: row for row in table_records(df)}
    if source_id not in rows:
        raise HTTPException(404, "Source ID not found in requested region")
    graph = {key: [] for key in rows}
    keys = sorted(rows)
    for i, a in enumerate(keys):
        for b in keys[i+1:]:
            km = distance(rows[a], rows[b])
            if km <= 150:
                km = max(0.8, km)
                graph[a].append((b, km))
                graph[b].append((a, km))
    queue = [(0.0, source_id, [source_id])]
    visited = set()
    while queue:
        km, node, path = heapq.heappop(queue)
        if node in visited:
            continue
        visited.add(node)
        if node != source_id and rows[node]["free_capacity_t"] >= volume:
            rail = all(rows[n]["railway_access"] for n in path)
            work = volume * km
            return {"status": "route_found", "source_id": source_id, "target_id": node,
                    "target_free_capacity_t": rows[node]["free_capacity_t"],
                    "volume_t": volume, "distance_km": km, "transport_work_tkm": work,
                    "path_ids": path, "path_coords": [[rows[n]["lat"], rows[n]["lon"]] for n in path],
                    "rail_flags_on_all_path_nodes": rail, "infrastructure_verified": False,
                    "trucks_required": math.ceil(volume / 25),
                    "wagons_required": math.ceil(volume / 68) if rail else None,
                    "cost_road_kzt": work * 38.5, "cost_rail_kzt": work * 22.5 if rail else None,
                    "savings_rail_kzt": work * (38.5-22.5) if rail else None,
                    "co2_road_t": work * 95 / 1e6, "co2_rail_t": work * 22 / 1e6 if rail else None}
        for neighbor, length in graph[node]:
            if neighbor not in visited:
                heapq.heappush(queue, (km + length, neighbor, path + [neighbor]))
    return {"status": "no_route", "source_id": source_id, "volume_t": volume,
            "reason": "No reachable target in the region has capacity for the full volume."}


@router.post("/api/silogrid")
def silogrid(request: SiloRequest):
    df, coefficients = loads(request)
    return envelope({**request.model_dump(), "facilities": table_records(df),
                     "summary": {"facility_count": len(df), "capacity_t": float(df.capacity_t.sum()),
                                 "stored_grain_t": float(df.stored_grain_t.sum()),
                                 "free_capacity_t": float(df.free_capacity_t.sum())}}, coefficients)


@router.post("/api/silogrid/route")
def silogrid_route(request: RouteRequest):
    df, coefficients = loads(request)
    coefficients.update({"rail_tariff_kzt_per_tkm": 22.5, "road_tariff_kzt_per_tkm": 38.5,
                         "wagon_capacity_t": 68, "truck_capacity_t": 25,
                         "rail_co2_g_per_tkm": 22, "road_co2_g_per_tkm": 95,
                         "proximity_limit_km": 150, "minimum_edge_km": 0.8})
    result = route_scenario(df, request.source_id, request.volume_t)
    result["assumption"] = "Requested volume is hypothetical; source stock is not reserved or verified. No stock is mutated."
    return envelope({**request.model_dump(), **result}, coefficients)


@router.post("/api/silogrid/prices")
def silogrid_prices(request: PriceRequest):
    wheat_jump = -request.yield_shock_pct * 0.61
    jumps = (wheat_jump, wheat_jump * 0.65, wheat_jump * 0.65 * 0.42)
    data = {"yield_shock_pct": request.yield_shock_pct, "timeline_days": [0, 30, 60, 90, 120, 180]}
    # Legacy lag shape retained, but drift applies only to shock increments.
    weights = ((0, .7, 1, 1.02, .98, .95), (0, .2, .75, 1, 1.01, .97), (0, 0, .15, .7, 1, .98))
    for name, base, jump, weight, unit in zip(
            ("wheat", "flour", "bread"), (115000, 245, 185), jumps, weights,
            ("KZT/t", "KZT/kg", "KZT/550g loaf")):
        data[name] = {"baseline": base, "projected": base * (1 + jump / 100),
                      "jump_pct": jump, "unit": unit,
                      "curve": [base * (1 + jump * w / 100) for w in weight]}
    return envelope(data, {"yield_to_wheat": -0.61, "wheat_to_flour": .65, "flour_to_bread": .42,
                           "elasticity_units": "% price change / % input change",
                           "timeline_weights": weights, "baseline_prices_are_assumptions": True})
