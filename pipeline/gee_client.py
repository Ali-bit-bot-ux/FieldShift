"""NASA climate access for FieldShift. Backend 1 owns this module.

The contract-facing entry point is ``get_nasa_climate_summary(region)``. It
always prefers the local cache, so the dashboard keeps working without a
network connection; Earth Engine is contacted only when no cache exists.

Sources (verified against the live Earth Engine catalog):
    * GLDAS 2.1 Noah 3-hourly: ``Evap_tavg`` -> seasonal evapotranspiration (mm)
    * GPM IMERG V07 half-hourly: ``precipitation`` -> seasonal precipitation (mm)
    * SMAP L4 SPL4SMGP: ``sm_surface`` -> mean surface soil moisture (m3/m3)
    * FAO GAUL 2025 level 1: region boundaries

Season: 1 April - 1 October, the grain-belt growing season. The cached summary
is a recent climatology (mean of the cached seasons); per-year values are kept
in ``data/processed/nasa_cache/<region>.json`` for transparency.

Climate stress is an explicit heuristic, not a hidden constant:
``index = 0.6 * (1 - P/ET) + 0.4 * (1 - SM/0.30)`` with thresholds
``<0.25 NORMAL``, ``<0.40 MILD_STRESS``, ``<0.60 MODERATE_DROUGHT``,
otherwise ``SEVERE_DROUGHT``. The formula is exposed as
``compute_stress_index`` so the integrator can audit it.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence

LOGGER = logging.getLogger(__name__)

CACHE_SCHEMA_VERSION = "fieldshift.nasa_cache/1"
CACHE_DIR = Path(__file__).resolve().parents[1] / "data/processed/nasa_cache"

CONTRACT_CLIMATE_KEYS = (
    "nasa_smap_moisture_m3m3",
    "nasa_gldas_evapotranspiration_mm",
    "nasa_imerg_precipitation_mm",
    "climate_stress_level",
)
STRESS_LEVELS = ("NORMAL", "MILD_STRESS", "MODERATE_DROUGHT", "SEVERE_DROUGHT")

REGION_ADMIN1 = {
    "sko": "North Kazakhstan Region",
    "kostanay": "Kostanay Region",
    "akmola": "Akmola Region",
    "pavlodar": "Pavlodar Region",
}
REGIONS = tuple(REGION_ADMIN1)
DEFAULT_YEARS = tuple(range(2021, 2027))

GAUL_ASSET = "FAO/GAUL/2025/level1"
GLDAS_COLLECTION = "NASA/GLDAS/V021/NOAH/G025/T3H"
GLDAS_ET_BAND = "Evap_tavg"
GLDAS_STEP_SECONDS = 3 * 3600
IMERG_COLLECTION = "NASA/GPM_L3/IMERG_V07"
IMERG_PRECIP_BAND = "precipitation"
IMERG_STEP_HOURS = 0.5
SMAP_COLLECTION = "NASA/SMAP/SPL4SMGP/008"
SMAP_BANDS = {"surface": "sm_surface", "rootzone": "sm_rootzone"}

SEASON_START_MONTH = 4
SEASON_END_MONTH = 10
REGION_SCALE_M = 25_000
MAX_PIXELS = 1_000_000_000
REQUEST_ATTEMPTS = 3

# Reference wetness for the composite stress index: close to field capacity
# for the loamy chernozems and chestnut soils of the grain belt.
SM_REFERENCE_M3M3 = 0.30
STRESS_WEIGHT_WATER = 0.6
STRESS_WEIGHT_MOISTURE = 0.4


class NasaDataUnavailable(RuntimeError):
    """Raised when neither a cache nor a live Earth Engine response is usable."""


_EE_LOCK = threading.Lock()
_EE_MODULE = None


def _ee():
    """Import and initialize Earth Engine once, with an auth-friendly error."""
    global _EE_MODULE
    with _EE_LOCK:
        if _EE_MODULE is not None:
            return _EE_MODULE
        try:
            import ee  # type: ignore
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise NasaDataUnavailable("earthengine-api is not installed") from exc
        try:
            project = os.getenv("GEE_PROJECT")
            if project:
                ee.Initialize(project=project)
            else:
                ee.Initialize()
        except Exception as exc:  # pragma: no cover - environment specific
            raise NasaDataUnavailable(
                "Earth Engine is not authenticated; run `earthengine authenticate` "
                "or set GEE_PROJECT/GOOGLE_APPLICATION_CREDENTIALS"
            ) from exc
        _EE_MODULE = ee
        return _EE_MODULE


def _normalise_region(region: str) -> str:
    key = str(region).strip().lower()
    if key not in REGION_ADMIN1:
        raise ValueError(f"Unknown region {region!r}; expected one of {REGIONS}")
    return key


def _season_bounds(ee_module, year: int):
    year = int(year)
    start = ee_module.Date.fromYMD(year, SEASON_START_MONTH, 1)
    end = ee_module.Date.fromYMD(year, SEASON_END_MONTH, 1)
    return start, end


def _get_info(ee_object, attempts: int = REQUEST_ATTEMPTS):
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            return ee_object.getInfo()
        except Exception as exc:  # pragma: no cover - network/GEE specific
            last_error = exc
            if attempt < attempts:
                time.sleep(2.0 * attempt)
    raise NasaDataUnavailable(f"Earth Engine request failed: {last_error}") from last_error


def _reduce_mean(ee_module, image, geometry, band: str, scale: int = REGION_SCALE_M) -> float:
    value = image.reduceRegion(
        reducer=ee_module.Reducer.mean(),
        geometry=geometry,
        scale=scale,
        maxPixels=MAX_PIXELS,
        bestEffort=False,
    ).get(band)
    if value is None:
        raise NasaDataUnavailable(f"Band {band!r} produced no value")
    result = _get_info(value)
    if result is None:
        raise NasaDataUnavailable(f"Band {band!r} produced no value")
    return float(result)


def get_region_geometry(region: str, ee_module=None):
    """Return the GAUL 2025 polygon for one of the four contract regions."""
    key = _normalise_region(region)
    ee = ee_module or _ee()
    admin1 = REGION_ADMIN1[key]
    features = ee.FeatureCollection(GAUL_ASSET).filter(
        ee.Filter.eq("GAUL1_NAME", admin1)
    )
    if not _get_info(features.size()):
        raise NasaDataUnavailable(f"GAUL boundary not found for {admin1!r}")
    return features.geometry()


def get_gldas_evapotranspiration(geometry, year: int, ee_module=None) -> float:
    """Seasonal evapotranspiration in mm from GLDAS Noah."""
    ee = ee_module or _ee()
    start, end = _season_bounds(ee, year)
    image = (
        ee.ImageCollection(GLDAS_COLLECTION)
        .filterDate(start, end)
        .select(GLDAS_ET_BAND)
        .sum()
        .multiply(GLDAS_STEP_SECONDS)
    )
    return round(_reduce_mean(ee, image, geometry, GLDAS_ET_BAND), 1)


def get_imerg_precipitation(geometry, year: int, ee_module=None) -> float:
    """Seasonal precipitation in mm from GPM IMERG V07."""
    ee = ee_module or _ee()
    start, end = _season_bounds(ee, year)
    image = (
        ee.ImageCollection(IMERG_COLLECTION)
        .filterDate(start, end)
        .select(IMERG_PRECIP_BAND)
        .sum()
        .multiply(IMERG_STEP_HOURS)
    )
    return round(_reduce_mean(ee, image, geometry, IMERG_PRECIP_BAND), 1)


def get_smap_moisture(
    geometry, year: int, layer: str = "surface", ee_module=None
) -> float:
    """Mean seasonal SMAP soil moisture in m3/m3 (surface or root zone)."""
    if layer not in SMAP_BANDS:
        raise ValueError(f"layer must be one of {tuple(SMAP_BANDS)}")
    ee = ee_module or _ee()
    start, end = _season_bounds(ee, year)
    band = SMAP_BANDS[layer]
    image = ee.ImageCollection(SMAP_COLLECTION).filterDate(start, end).select(band).mean()
    return round(_reduce_mean(ee, image, geometry, band), 4)


def get_smap_moisture_profile(geometry, year: int, ee_module=None) -> dict:
    """Mean seasonal surface and root-zone SMAP moisture in one request."""
    ee = ee_module or _ee()
    start, end = _season_bounds(ee, year)
    surface_band = SMAP_BANDS["surface"]
    rootzone_band = SMAP_BANDS["rootzone"]
    image = (
        ee.ImageCollection(SMAP_COLLECTION)
        .filterDate(start, end)
        .select([surface_band, rootzone_band])
        .mean()
    )
    reduced = image.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=geometry,
        scale=REGION_SCALE_M,
        maxPixels=MAX_PIXELS,
        bestEffort=False,
    )
    data = _get_info(reduced)
    if not data or data.get(surface_band) is None or data.get(rootzone_band) is None:
        raise NasaDataUnavailable("SMAP produced no moisture value")
    return {
        "surface": round(float(data[surface_band]), 4),
        "rootzone": round(float(data[rootzone_band]), 4),
    }


def compute_stress_index(et_mm: float, precip_mm: float, sm_m3m3: float) -> float:
    """Composite water stress in [0, 1] from water balance and soil moisture."""
    if et_mm <= 0:
        raise ValueError("evapotranspiration must be positive")
    water_deficit = min(1.0, max(0.0, 1.0 - precip_mm / et_mm))
    moisture_deficit = min(1.0, max(0.0, 1.0 - sm_m3m3 / SM_REFERENCE_M3M3))
    return (
        STRESS_WEIGHT_WATER * water_deficit
        + STRESS_WEIGHT_MOISTURE * moisture_deficit
    )


def classify_climate_stress(et_mm: float, precip_mm: float, sm_m3m3: float) -> str:
    """Map the composite index to one of the four contract stress levels."""
    index = compute_stress_index(et_mm, precip_mm, sm_m3m3)
    if index < 0.25:
        return "NORMAL"
    if index < 0.40:
        return "MILD_STRESS"
    if index < 0.60:
        return "MODERATE_DROUGHT"
    return "SEVERE_DROUGHT"


def _mean(values: Iterable[float]) -> float | None:
    present = [float(value) for value in values if value is not None]
    if not present:
        return None
    return sum(present) / len(present)


def build_climate_summary(series: Sequence[Mapping]) -> dict:
    """Aggregate per-year rows into the exact four contract keys."""
    if not series:
        raise NasaDataUnavailable("Climate series is empty")
    et = _mean(row.get("gldas_evapotranspiration_mm") for row in series)
    precip = _mean(row.get("imerg_precipitation_mm") for row in series)
    moisture = _mean(row.get("smap_surface_m3m3") for row in series)
    if et is None or precip is None or moisture is None:
        raise NasaDataUnavailable("Climate series is missing one of the NASA metrics")
    return {
        "nasa_smap_moisture_m3m3": round(moisture, 3),
        "nasa_gldas_evapotranspiration_mm": round(et, 1),
        "nasa_imerg_precipitation_mm": round(precip, 1),
        "climate_stress_level": classify_climate_stress(et, precip, moisture),
    }


def _cache_path(region: str, cache_dir: Path | str | None = None) -> Path:
    key = _normalise_region(region)
    return Path(cache_dir or CACHE_DIR) / f"{key}.json"


def load_cached_climate(region: str, cache_dir: Path | str | None = None) -> dict | None:
    """Return a validated cache document, or None when it is absent/invalid."""
    path = _cache_path(region, cache_dir)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        LOGGER.warning("Ignoring unreadable NASA cache %s", path)
        return None
    if data.get("schema_version") != CACHE_SCHEMA_VERSION:
        return None
    if data.get("region") != _normalise_region(region):
        return None
    summary = data.get("summary")
    if not isinstance(summary, dict) or set(summary) != set(CONTRACT_CLIMATE_KEYS):
        return None
    if summary.get("climate_stress_level") not in STRESS_LEVELS:
        return None
    if not isinstance(data.get("years"), list) or not data["years"]:
        return None
    return data


def save_cached_climate(
    region: str,
    series: Sequence[Mapping],
    summary: Mapping | None = None,
    cache_dir: Path | str | None = None,
) -> Path:
    """Write an atomic, contract-shaped cache document and return its path."""
    key = _normalise_region(region)
    rows = sorted((dict(row) for row in series), key=lambda row: int(row["year"]))
    if not rows:
        raise ValueError("Cannot cache an empty climate series")
    summary = dict(summary) if summary is not None else build_climate_summary(rows)
    missing = set(CONTRACT_CLIMATE_KEYS) - set(summary)
    if missing:
        raise ValueError(f"Summary is missing contract keys: {sorted(missing)}")
    years = [int(row["year"]) for row in rows]
    payload = {
        "schema_version": CACHE_SCHEMA_VERSION,
        "region": key,
        "region_admin1": REGION_ADMIN1[key],
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "season": f"{SEASON_START_MONTH:02d}-01..{SEASON_END_MONTH:02d}-01",
        "years": rows,
        "summary": {name: summary[name] for name in CONTRACT_CLIMATE_KEYS},
        "summary_period": [min(years), max(years)],
        "sources": {
            "evapotranspiration": GLDAS_COLLECTION,
            "precipitation": IMERG_COLLECTION,
            "soil_moisture": SMAP_COLLECTION,
            "boundaries": GAUL_ASSET,
        },
    }
    path = _cache_path(key, cache_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(path)
    return path


def _fetch_year(ee_module, geometry, year: int) -> dict:
    moisture = get_smap_moisture_profile(geometry, year, ee_module=ee_module)
    return {
        "year": int(year),
        "gldas_evapotranspiration_mm": get_gldas_evapotranspiration(
            geometry, year, ee_module=ee_module
        ),
        "imerg_precipitation_mm": get_imerg_precipitation(
            geometry, year, ee_module=ee_module
        ),
        "smap_surface_m3m3": moisture["surface"],
        "smap_rootzone_m3m3": moisture["rootzone"],
    }


def fetch_nasa_climate_year(region: str, year: int) -> dict:
    """Fetch one complete growing season for a region from Earth Engine."""
    ee = _ee()
    geometry = get_region_geometry(region, ee)
    return _fetch_year(ee, geometry, year)


def fetch_nasa_climate_series(
    region: str,
    years: Iterable[int] | None = None,
    on_row=None,
) -> list[dict]:
    """Fetch several seasons for one region, skipping years that fail."""
    key = _normalise_region(region)
    requested = sorted({int(year) for year in (years or DEFAULT_YEARS)})
    ee = _ee()
    geometry = get_region_geometry(key, ee)
    rows: list[dict] = []
    for year in requested:
        try:
            row = _fetch_year(ee, geometry, year)
        except NasaDataUnavailable as exc:
            LOGGER.warning("Skipping %s %s: %s", key, year, exc)
            continue
        rows.append(row)
        if on_row is not None:
            on_row(row)
    if not rows:
        raise NasaDataUnavailable(f"No NASA seasons could be fetched for {key}")
    return rows


def get_nasa_climate_series(region: str) -> list[dict]:
    """Return cached per-year rows, fetching and caching them when absent."""
    key = _normalise_region(region)
    cached = load_cached_climate(key)
    if cached is not None:
        return cached["years"]
    rows = fetch_nasa_climate_series(key)
    save_cached_climate(key, rows)
    return rows


def get_nasa_climate_summary(region: str) -> dict:
    """Return exactly the contract climate keys for one region.

    Cache-first by design: the offline demo never depends on Earth Engine.
    """
    key = _normalise_region(region)
    cached = load_cached_climate(key)
    if cached is not None:
        return {name: cached["summary"][name] for name in CONTRACT_CLIMATE_KEYS}

    try:
        rows = fetch_nasa_climate_series(key)
    except NasaDataUnavailable:
        raise
    except Exception as exc:  # pragma: no cover - defensive boundary
        raise NasaDataUnavailable(
            f"No NASA cache for {key} and live fetch failed: {exc}"
        ) from exc

    summary = build_climate_summary(rows)
    save_cached_climate(key, rows, summary)
    return {name: summary[name] for name in CONTRACT_CLIMATE_KEYS}
