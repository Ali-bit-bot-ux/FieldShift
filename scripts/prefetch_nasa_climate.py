"""Prefetch NASA GLDAS/IMERG/SMAP summaries for the four grain-belt regions.
Backend 1 owns this script.

Examples:
    python scripts/prefetch_nasa_climate.py
    python scripts/prefetch_nasa_climate.py --years 2021-2026 --force
    python scripts/prefetch_nasa_climate.py --regions sko,kostanay --workers 2

The script is resumable: already cached years are reused unless --force is set.
Each region is written atomically as soon as it finishes.
"""
from __future__ import annotations

import argparse
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline import gee_client as gee  # noqa: E402


def parse_years(value: str) -> list[int]:
    years: set[int] = set()
    for chunk in value.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            start, end = chunk.split("-", 1)
            years.update(range(int(start), int(end) + 1))
        else:
            years.add(int(chunk))
    if not years:
        raise argparse.ArgumentTypeError("At least one year is required")
    return sorted(years)


def parse_regions(value: str) -> list[str]:
    regions = [item.strip().lower() for item in value.split(",") if item.strip()]
    unknown = [region for region in regions if region not in gee.REGION_ADMIN1]
    if unknown:
        raise argparse.ArgumentTypeError(
            f"Unknown regions {unknown}; expected {list(gee.REGIONS)}"
        )
    return regions


def prefetch_region(region: str, years: list[int], force: bool) -> dict:
    cached = gee.load_cached_climate(region)
    existing = {
        int(row["year"]): row for row in (cached["years"] if cached else [])
    }
    wanted = set(years) if force else set(years) - set(existing)
    rows = [] if force else list(existing.values())

    def persist(row: dict) -> None:
        # Save after every season so an interrupted prefetch is resumable.
        rows.append(row)
        summary = gee.build_climate_summary(rows)
        gee.save_cached_climate(region, rows, summary)
        print(
            f"[{region}] {row['year']}: "
            f"ET={row['gldas_evapotranspiration_mm']:.1f} mm, "
            f"P={row['imerg_precipitation_mm']:.1f} mm, "
            f"SM={row['smap_surface_m3m3']:.3f} m3/m3",
            flush=True,
        )

    if wanted:
        gee.fetch_nasa_climate_series(region, sorted(wanted), on_row=persist)
    if not rows:
        raise RuntimeError("nothing to cache")

    summary = gee.build_climate_summary(rows)
    path = gee.save_cached_climate(region, rows, summary)
    fetched_years = {int(row["year"]) for row in rows}
    return {
        "region": region,
        "path": path,
        "fetched": sorted(wanted & fetched_years),
        "reused": sorted(set(existing) & fetched_years) if not force else [],
        "skipped": sorted(wanted - fetched_years),
        "summary": summary,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--regions",
        default=",".join(gee.REGIONS),
        help="Comma-separated region ids (default: all four)",
    )
    parser.add_argument(
        "--years",
        default=f"{gee.DEFAULT_YEARS[0]}-{gee.DEFAULT_YEARS[-1]}",
        help="Comma-separated years or an inclusive range, e.g. 2021-2026",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Refetch years that already exist in the cache",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Regions fetched in parallel (default: 4, use 1 if GEE throttles)",
    )
    args = parser.parse_args(argv)

    regions = parse_regions(args.regions)
    years = parse_years(args.years)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    print(
        f"Prefetching NASA climate for {len(regions)} region(s), "
        f"years {years[0]}-{years[-1]}, cache: {gee.CACHE_DIR}",
        flush=True,
    )

    failures: list[str] = []
    workers = max(1, min(args.workers, len(regions)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(prefetch_region, region, years, args.force): region
            for region in regions
        }
        for future in as_completed(futures):
            region = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                failures.append(region)
                print(f"[{region}] FAILED: {exc}", file=sys.stderr, flush=True)
                continue
            summary = result["summary"]
            print(
                f"[{region}] wrote {result['path']} "
                f"(fetched {result['fetched'] or 'none'}, "
                f"reused {result['reused'] or 'none'}, "
                f"skipped {result['skipped'] or 'none'})",
                flush=True,
            )
            print(
                f"[{region}] summary: ET={summary['nasa_gldas_evapotranspiration_mm']} mm, "
                f"P={summary['nasa_imerg_precipitation_mm']} mm, "
                f"SM={summary['nasa_smap_moisture_m3m3']} m3/m3, "
                f"stress={summary['climate_stress_level']}",
                flush=True,
            )

    if failures:
        print(f"Failed regions: {failures}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
