"""Read-only adapters for the six legacy satellite snapshots (no generated data)."""

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import Field

from modules import legacy_common as common

router = APIRouter()

NDVI_COLUMNS = ("region_id", "date", "doy", "year", "ndvi", "n_scenes", "source")
NORM_COLUMNS = ("region_id", "doy", "ndvi_mean", "ndvi_std", "ndvi_count", "ndvi_upper", "ndvi_lower")
PSI_COLUMNS = ("region_id", "year", "psi", "risk", "delay_days", "ndvi_mean_current", "ndvi_mean_norm")
HYDRO_COLUMNS = ("region_id", "basin", "basin_name", "date", "soil_moisture", "sm_rolling_90d", "month", "year", "sm_mean", "sm_std", "smai", "anomaly_level", "source")
BACKTEST_COLUMNS = ("region_id", "date", "soil_moisture", "smai")
REGIONS = ("sko", "kostanay", "akmola", "pavlodar")
SMAP_WARNING = "SMAP L3 surface soil moisture, not rootzone; region rectangles, not basin measurements; native 9 km, no downscaling."


class RegionRequest(common.LegacyRequest):
    region: common.Region


class YearRequest(RegionRequest):
    year: int = Field(strict=True, ge=2015, le=9999)


def _table(name, columns, numeric, keys, positive=()):
    """Reject broken snapshots before selection or JSON serialization."""
    try:
        frame = common.load_table(name, required_columns=columns).loc[:, list(columns)].copy()
        if frame.empty or frame.isna().any().any():
            raise ValueError("empty or null values")
        if not frame["region_id"].isin(REGIONS).all():
            raise ValueError("unknown region")
        for column in numeric:
            values = frame[column]
            if (not pd.api.types.is_numeric_dtype(values) or
                    pd.api.types.is_bool_dtype(values) or not np.isfinite(values).all()):
                raise ValueError(f"invalid numeric column {column}")
        for column in ("year", "month", "doy", "n_scenes", "ndvi_count", "delay_days"):
            if column in frame and (frame[column] % 1 != 0).any():
                raise ValueError(f"noninteger {column}")
        for column in positive:
            if (frame[column] <= 0).any():
                raise ValueError(f"nonpositive {column}")
        if "date" in frame:
            if pd.api.types.is_numeric_dtype(frame["date"]):
                raise ValueError("numeric dates")
            frame["date"] = pd.to_datetime(frame["date"], errors="raise")
            dates = frame["date"]
            if dates.isna().any() or dates.dt.tz is not None or (dates != dates.dt.normalize()).any():
                raise ValueError("invalid daily dates")
            for column, derived in (("year", dates.dt.year), ("month", dates.dt.month), ("doy", dates.dt.dayofyear)):
                if column in frame and not (frame[column] == derived).all():
                    raise ValueError(f"date/{column} mismatch")
        if "doy" in frame and not frame["doy"].between(1, 366).all():
            raise ValueError("invalid DOY")
        if frame.duplicated(list(keys)).any():
            raise ValueError("duplicate keys")
        return frame
    except common.LegacyDataUnavailable:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError) as exc:
        raise common.LegacyDataUnavailable(f"Invalid legacy dataset {name}: {exc}") from exc


def _records(frame):
    # Keep full cached float precision (DataFrame.to_json defaults to 10 digits).
    frame = frame.copy()
    if "date" in frame:
        frame["date"] = frame["date"].dt.strftime("%Y-%m-%d")
    return frame.to_dict(orient="records")


def _region(frame, region):
    return frame.loc[frame["region_id"] == region].copy()


def _years(frame):
    return sorted(int(year) for year in frame["year"].unique())


def _observations(frame, region, year):
    selected = frame.loc[(frame["region_id"] == region) & (frame["year"] == year)].sort_values("date")
    if selected.empty:
        raise HTTPException(404, f"No observations for {region} in {year}")
    return selected


def _success(module, data, sources, warnings, **metadata):
    return {"status": "success", "module": module, "data": data,
            "metadata": {"kind": "retrospective" if module == "backtesting" else "observed_derived",
                         "sources": sources, "warnings": warnings, **metadata}}


@router.post("/api/phenomap")
def phenomap(request: YearRequest):
    baseline_name = "ndvi_baseline_regions.parquet"
    current_name = "ndvi_current_2026.parquet"
    norm_name = "phenological_norm_regions.parquet"
    psi_name = "phenoshift_regions.parquet"
    numeric = ("doy", "year", "ndvi", "n_scenes")
    baseline = _table(baseline_name, NDVI_COLUMNS, numeric, ("region_id", "date"))
    current = _table(current_name, NDVI_COLUMNS, numeric, ("region_id", "date"))
    if not baseline["year"].between(2015, 2025).all() or not current["year"].eq(2026).all():
        raise common.LegacyDataUnavailable("NDVI snapshot contains wrong-year observations")
    observations = pd.concat([baseline, current], ignore_index=True)
    selected = _observations(observations, request.region, request.year)
    norm = _region(_table(norm_name, NORM_COLUMNS, NORM_COLUMNS[1:], ("region_id", "doy"), ("ndvi_std",)), request.region).sort_values("doy")
    psi = _region(_table(psi_name, PSI_COLUMNS, ("year", "psi", "delay_days", "ndvi_mean_current", "ndvi_mean_norm"), ("region_id", "year")), request.region).sort_values("year")
    if norm.empty:
        raise common.LegacyDataUnavailable(f"Missing norm for {request.region}")
    available = _years(_region(observations, request.region))
    psi = psi.loc[psi["year"].isin(available)]
    metrics = _records(psi.loc[psi["year"] == request.year])
    warnings = [
        "Pheno baseline 2015-2025 includes past target years; this is not predictive validation.",
        "Historical NDVI uses monthly median composites at 1000 m; 2026 uses daily scene aggregates at 500 m. Sampling differs.",
        "The cached norm is interpolated and smoothed over DOY 120-280; PSI is the mean matched-DOY z-score, requiring at least five observations.",
        "Region aggregates only; no district or downscaled anomaly maps are available.",
    ]
    if not metrics:
        matched = selected.loc[selected["doy"].between(120, 280)].merge(norm, on="doy")
        if len(matched) >= 5:
            raise common.LegacyDataUnavailable("Missing PSI despite sufficient matched observations")
        warnings.append("Selected-year PSI unavailable: fewer than five matched vegetation-season observations.")
    return _success("phenomap", {"region": request.region, "year": request.year,
        "series": _records(selected), "norm": _records(norm), "annual_psi": _records(psi),
        "selected_metrics": metrics[0] if metrics else None},
        [baseline_name, current_name, norm_name, psi_name, "COPERNICUS/S2_SR_HARMONIZED"], warnings,
        available_years=available, baseline_years=[2015, 2025],
        sampling="daily" if request.year == 2026 else "monthly")


def _anomaly(smai):
    if smai < -2:
        return "SEVERE_DRY"
    if smai < -1:
        return "DRY"
    if smai < -0.5:
        return "SLIGHTLY_DRY"
    if smai > 2:
        return "WET"
    if smai > 1:
        return "SLIGHTLY_WET"
    return "NORMAL"


@router.post("/api/hydrorisk")
def hydrorisk(request: YearRequest):
    name = "hydroborder_regions.parquet"
    frame = _table(name, HYDRO_COLUMNS, ("soil_moisture", "sm_rolling_90d", "month", "year", "sm_mean", "sm_std", "smai"), ("region_id", "date"), ("sm_std",))
    selected = _observations(frame, request.region, request.year).copy()
    selected["anomaly_level"] = selected["smai"].map(_anomaly)
    series = _records(selected)
    return _success("hydrorisk", {"region": request.region, "year": request.year,
        "series": series, "latest": series[-1]}, [name, "NASA/SMAP/SPL3SMP_E/006"],
        [SMAP_WARNING,
         "Baseline-only monitoring: no crop/scenario adjustment or price prediction.",
         "Cached SMAI uses a 90-observation rolling mean (minimum 10), not necessarily 90 calendar days, and monthly baseline 2015-2025.",
         "Legacy basin_name labels contain encoding damage; basin IDs are retained as labels only."],
        available_years=_years(_region(frame, request.region)), baseline_years=[2015, 2025])


@router.post("/api/backtest/2021")
def backtest_2021(request: RegionRequest):
    name = "backtest_2021_regions.parquet"
    frame = _table(name, BACKTEST_COLUMNS, ("soil_moisture", "smai"), ("region_id", "date"))
    frame["year"] = frame["date"].dt.year
    selected = _observations(frame, request.region, 2021)
    selected = selected.loc[selected["date"].between("2021-05-01", "2021-09-30")]
    if selected.empty:
        raise HTTPException(404, f"No May-September 2021 observations for {request.region}")
    crossings = selected.loc[selected["smai"] < -1.5, "date"]
    trigger = crossings.min() if not crossings.empty else None
    reference = pd.Timestamp("2021-07-15")
    return _success("backtesting", {"region": request.region, "year": 2021,
        "series": _records(selected), "threshold": -1.5,
        "trigger_date": trigger.strftime("%Y-%m-%d") if trigger is not None else None,
        "reference_date": "2021-07-15",
        "lead_days": int((reference - trigger).days) if trigger is not None else None},
        [name, "hydroborder_regions.parquet", "NASA/SMAP/SPL3SMP_E/006"],
        [SMAP_WARNING,
         "Retrospective baseline 2015-2020 excludes 2021; this is not a guarantee of future warning lead time.",
         "Reference date 2021-07-15 is assumed, not independently verified official recognition.",
         "Legacy day31 bucket issue preserved: ((day-1)//10)+1 puts day 31 in a separate fourth bucket, not the third dekad.",
         "Cached SMAI uses period-mean moisture and matching baseline buckets (sigma floor 0.01), not the HydroRisk rolling SMAI."],
        baseline_years=[2015, 2020], season=["2021-05-01", "2021-09-30"],
        lead_days_definition="reference_date minus first date with SMAI < -1.5; signed, null if no crossing")
