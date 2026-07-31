"""Generate two-phase postcode autocomplete JSON files.

Reads bbox_lookup.sqlite (postcode + district bboxes) and ONSPD CSV (full
postcode list with lat/lon) to produce:
  - exported_data/app/outward.json — sorted flat array of ~2,900 outward codes
  - exported_data/app/inward/<outward>.json — one file per outward code with
    inward codes, bboxes and centroids
"""

import bisect
import csv
import heapq
import json
import math
import os
import sqlite3
import struct
from collections import defaultdict
from pathlib import Path
from typing import Optional

from dagster import asset, AssetExecutionContext, Config, MetadataValue

from bsil_pipeline.assets.publish import BETA_LA_CODES
from bsil_pipeline.automation import PIPELINE_CONDITION
from bsil_pipeline.resources.postgres import BsilPostgresResource


_SOURCE_DATA = Path(__file__).resolve().parent.parent.parent / "source_data"
_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
_EXPORT_DIR = Path("/opt/dagster/app/output/app")

# Point bbox half-width for postcodes without polygon data (~200m)
_POINT_DELTA = 0.002

# Maximum expansion radius in degrees (~20 km)
_MAX_EXPANSION_RADIUS = 0.18

# Expanding search radii for efficient nearest-neighbor lookup via lat-band
_SEARCH_RADII = (0.005, 0.01, 0.02, 0.05, 0.1, _MAX_EXPANSION_RADIUS)

# Compact struct formats for memory-efficient storage
_BBOX_STRUCT = struct.Struct("<4f")  # west, south, east, north
_PC_STRUCT = struct.Struct("<6f")  # west, south, east, north, cx, cy


def _expand_outward_entries(entries, sorted_providers, sorted_lats, k=3):
    """Expand bboxes for one outward code's entries dict."""
    for entry in entries.values():
        west, south, east, north = entry["b"]
        cx, cy = entry["c"]  # cx=lon, cy=lat

        # Find distance to k-th nearest provider using expanding lat-band
        r = None
        for search_r in _SEARCH_RADII:
            lo = bisect.bisect_left(sorted_lats, cy - search_r)
            hi = bisect.bisect_right(sorted_lats, cy + search_r)
            if hi - lo < k:
                continue
            kth_dist = heapq.nsmallest(
                k,
                (
                    math.hypot(
                        cy - sorted_providers[j][0],
                        cx - sorted_providers[j][1],
                    )
                    for j in range(lo, hi)
                ),
            )[-1]
            if kth_dist <= search_r or search_r >= _MAX_EXPANSION_RADIUS:
                r = min(kth_dist, _MAX_EXPANSION_RADIUS)
                break

        if r is None or r <= 0:
            continue

        cos_lat = math.cos(math.radians(cy))
        r_lon = r / cos_lat if cos_lat > 0.01 else r
        entry["b"] = [
            round(min(west, cx - r_lon), 6),
            round(min(south, cy - r), 6),
            round(max(east, cx + r_lon), 6),
            round(max(north, cy + r), 6),
        ]


def _expand_bboxes(inward_data, provider_coords, k=3):
    """Expand postcode bboxes symmetrically to include k nearest point providers.

    For each postcode centroid, finds the k nearest point-based providers using
    a sorted-by-latitude array with bisect for efficient range queries. The bbox
    is expanded to a symmetric rectangle (centroid +/- r in lat, centroid +/- r/cos(lat)
    in lon) unioned with the original bbox, where r is the distance to the k-th
    nearest provider, capped at _MAX_EXPANSION_RADIUS.
    """
    if len(provider_coords) < k:
        return

    sorted_providers = sorted(provider_coords)
    sorted_lats = [p[0] for p in sorted_providers]

    for outward_inwards in inward_data.values():
        _expand_outward_entries(outward_inwards, sorted_providers, sorted_lats, k)


def _outward_code(postcode: str) -> Optional[str]:
    """Extract the outward (district) code, e.g. 'SW1A 1AA' -> 'SW1A'."""
    pc = postcode.strip().upper()
    if " " in pc:
        return pc.split()[0]
    if len(pc) >= 5:
        return pc[:-3].strip()
    return None


def _inward_code(postcode: str) -> Optional[str]:
    """Extract the inward code, e.g. 'SW1A 1AA' -> '1AA'."""
    pc = postcode.strip().upper()
    if " " in pc:
        parts = pc.split()
        return parts[1] if len(parts) >= 2 else None
    if len(pc) >= 5:
        return pc[-3:]
    return None


class PostcodeAutocompleteConfig(Config):
    lad25cd: list[str] = []


@asset(
    group_name="os",
    deps=["bbox_lookup", "publish_providers", "validate_published", "iod_2025"],
    automation_condition=PIPELINE_CONDITION,
)
def postcode_autocomplete(
    context: AssetExecutionContext,
    config: PostcodeAutocompleteConfig,
    bsil_postgres: BsilPostgresResource,
):
    """Generate outward.json + inward/<outward>.json for postcode autocomplete.

    Depends on bbox_lookup having been materialised (reads its SQLite output),
    ONSPD CSV for the full postcode list, and published.providers for bbox
    expansion using nearby point providers.
    """
    try:
        beta_mode = context.run.tags.get("BETA", "false").lower() == "true"
    except Exception:
        beta_mode = False
    source_dir = Path(os.environ.get("SOURCE_DATA_PATH", str(_SOURCE_DATA)))
    data_dir = Path(os.environ.get("DATA_DIR", str(_DATA_DIR)))
    export_dir = Path(os.environ.get("EXPORT_APP_DIR", str(_EXPORT_DIR)))

    # --- Locate inputs ---
    bbox_path = data_dir / "bbox_lookup.sqlite"
    if not bbox_path.exists():
        context.log.error(
            f"bbox_lookup.sqlite not found at {bbox_path} — "  # noqa: G004
            "run the bbox_lookup asset first"
        )
        return {"error": MetadataValue.text("bbox_lookup.sqlite not found")}

    root_csvs = sorted(source_dir.glob("ONSPD_*_UK.csv"))
    if root_csvs:
        onspd_path = root_csvs[0]
    else:
        onspd_path = None
        for child in sorted(source_dir.iterdir()):
            if child.is_dir() and child.name.startswith("ONSPD"):
                candidate = child / "Data"
                csvs = list(candidate.glob("ONSPD_*_UK.csv"))
                if csvs:
                    onspd_path = csvs[0]
                    break
    if not onspd_path:
        context.log.error(
            f"ONSPD CSV not found under {source_dir} or {source_dir}/ONSPD_*/Data/"
        )  # noqa: G004
        return {"error": MetadataValue.text("ONSPD CSV not found")}

    context.log.info(f"Reading bbox_lookup from: {bbox_path}")  # noqa: G004
    context.log.info(f"Reading ONSPD from: {onspd_path}")  # noqa: G004

    # --- Step 1: Load bboxes from SQLite (packed) ---
    conn = sqlite3.connect(str(bbox_path))

    postcode_bboxes: dict[str, bytes] = {}
    for row in conn.execute(
        "SELECT geo_code, bbox_west, bbox_south, bbox_east, bbox_north FROM postcode_bbox"
    ):
        postcode_bboxes[row[0]] = _BBOX_STRUCT.pack(row[1], row[2], row[3], row[4])
    context.log.info(f"Loaded {len(postcode_bboxes)} postcode bboxes from SQLite")  # noqa: G004

    conn.close()

    # --- Load LSOA -> IoD decile lookup ---
    lsoa_decile: dict[str, int] = {}
    with bsil_postgres.get_connection() as pg_conn:
        with pg_conn.cursor() as cur:
            cur.execute("SELECT lsoa21cd, imd_decile FROM mhclg.iod_2025")
            for row in cur.fetchall():
                lsoa_decile[row[0]] = int(row[1])
    context.log.info(
        f"Loaded {len(lsoa_decile)} LSOA->decile mappings"  # noqa: G004
    )

    # --- Step 2: Read ONSPD CSV (pack entries for memory efficiency) ---
    inward_data: dict[str, dict[str, bytes]] = defaultdict(dict)
    inward_lad: dict[str, dict[str, list[str]]] = defaultdict(dict)
    inward_decile: dict[str, dict[str, int]] = defaultdict(dict)
    inward_is_beta: set[tuple[str, str]] = set()
    outward_codes: set[str] = set()
    skipped = 0
    processed = 0
    iod_count = 0

    _lad_filter_set = set(config.lad25cd) if config.lad25cd else None

    with open(onspd_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pcds = row.get("pcds", "").strip().upper()
            if not pcds:
                continue

            # Skip postcodes with no coordinates (gridind == 9)
            gridind = row.get("gridind", "").strip()
            if gridind == "9":
                skipped += 1
                continue

            # Skip postcodes not in the LAD filter
            if _lad_filter_set is not None:
                lad = row.get("lad25cd", "").strip()
                cty = row.get("cty25cd", "").strip()
                if lad not in _lad_filter_set and cty not in _lad_filter_set:
                    skipped += 1
                    continue

            lat_str = row.get("lat", "").strip()
            lon_str = row.get("long", "").strip()
            if not lat_str or not lon_str:
                skipped += 1
                continue

            try:
                lat = float(lat_str)
                lon = float(lon_str)
            except ValueError:
                skipped += 1
                continue

            outward = _outward_code(pcds)
            inward = _inward_code(pcds)
            if not outward or not inward:
                skipped += 1
                continue

            outward_codes.add(outward)

            # Look up bbox from SQLite, fall back to point bbox
            packed_bbox = postcode_bboxes.get(pcds)
            if packed_bbox:
                west, south, east, north = _BBOX_STRUCT.unpack(packed_bbox)
                cx = (west + east) / 2
                cy = (south + north) / 2
            else:
                west = lon - _POINT_DELTA
                east = lon + _POINT_DELTA
                south = lat - _POINT_DELTA
                north = lat + _POINT_DELTA
                cx = lon
                cy = lat

            inward_data[outward][inward] = _PC_STRUCT.pack(
                round(west, 6),
                round(south, 6),
                round(east, 6),
                round(north, 6),
                round(cx, 6),
                round(cy, 6),
            )

            lad_code = row.get("lad25cd", "").strip()
            cty_code = row.get("cty25cd", "").strip()
            codes: list[str] = []
            if lad_code:
                codes.append(lad_code)
            if cty_code and not cty_code.endswith("999999") and cty_code != lad_code:
                codes.append(cty_code)
            if codes:
                inward_lad[outward][inward] = codes
                if any(c in BETA_LA_CODES for c in codes):
                    inward_is_beta.add((outward, inward))

            lsoa_code = row.get("lsoa21cd", "").strip()
            if lsoa_code and lsoa_code in lsoa_decile:
                inward_decile[outward][inward] = lsoa_decile[lsoa_code]
                iod_count += 1

            processed += 1

            if processed % 500_000 == 0:
                context.log.info(f"  Progress: {processed} postcodes processed...")  # noqa: G004

    context.log.info(
        f"Processed {processed} postcodes, skipped {skipped}, "  # noqa: G004
        f"{len(outward_codes)} outward codes"
    )

    del postcode_bboxes  # free ~240 MB of packed bbox data
    del lsoa_decile  # free ~2 MB LSOA lookup

    # --- Steps 2b+3: Load providers, then unpack→expand→write per outward ---
    provider_coords = []
    with bsil_postgres.get_connection() as pg_conn:
        with pg_conn.cursor() as cur:
            cur.execute(
                "SELECT latitude, longitude FROM published.providers "
                "WHERE latitude IS NOT NULL AND longitude IS NOT NULL "
                "AND bbox_geo_type IS NULL"
            )
            provider_coords = [(float(row[0]), float(row[1])) for row in cur.fetchall()]

    context.log.info(
        f"Loaded {len(provider_coords)} point providers for bbox expansion"  # noqa: G004
    )

    if len(provider_coords) >= 3:
        sorted_providers = sorted(provider_coords)
        sorted_lats = [p[0] for p in sorted_providers]
    else:
        sorted_providers = sorted_lats = None

    export_dir.mkdir(parents=True, exist_ok=True)
    inward_dir = export_dir / "inward"
    inward_dir.mkdir(parents=True, exist_ok=True)

    # outward.json — sorted flat array
    sorted_outward = sorted(outward_codes)
    outward_path = export_dir / "outward.json"
    with open(outward_path, "w") as f:
        json.dump(sorted_outward, f, separators=(",", ":"))
    outward_size = outward_path.stat().st_size

    context.log.info(
        f"Wrote outward.json: {len(sorted_outward)} codes, {outward_size / 1024:.1f} KB"  # noqa: G004
    )

    # inward/<outward>.json — unpack, expand, write, free per outward code
    inward_file_count = 0
    total_inward_size = 0
    all_lad_codes: set[str] = set()
    for outward in sorted_outward:
        packed_chunk = inward_data.pop(outward)
        entries = {}
        for ic, packed in packed_chunk.items():
            w, s, e, n, cx, cy = _PC_STRUCT.unpack(packed)
            entries[ic] = {
                "b": [round(w, 6), round(s, 6), round(e, 6), round(n, 6)],
                "c": [round(cx, 6), round(cy, 6)],
            }

        if sorted_providers:
            if beta_mode:
                # In beta mode, only expand postcodes that belong to a beta LA.
                # Non-beta postcodes keep their strict OS CodePoint bbox so the
                # frontend doesn't search a large radius where no providers exist.
                beta_entries = {
                    ic: entry
                    for ic, entry in entries.items()
                    if (outward, ic) in inward_is_beta
                }
                _expand_outward_entries(beta_entries, sorted_providers, sorted_lats)
            else:
                _expand_outward_entries(entries, sorted_providers, sorted_lats)

        # Build compact LAD index for this outward code
        lad_chunk = inward_lad.pop(outward, {})
        decile_chunk = inward_decile.pop(outward, {})
        all_codes_in_chunk: set[str] = set()
        for code_list in lad_chunk.values():
            all_codes_in_chunk.update(code_list)
        unique_lads = sorted(all_codes_in_chunk)
        all_lad_codes.update(unique_lads)
        lad_index = {code: idx for idx, code in enumerate(unique_lads)}

        output: dict = {"_": unique_lads}
        for ic in sorted(entries.keys()):
            entry = entries[ic]
            codes = lad_chunk.get(ic)
            if codes:
                entry["a"] = [lad_index[c] for c in codes]
            decile = decile_chunk.get(ic)
            if decile is not None:
                entry["d"] = decile
            output[ic] = entry

        file_path = inward_dir / f"{outward}.json"
        with open(file_path, "w") as f:
            json.dump(output, f, separators=(",", ":"))
        total_inward_size += file_path.stat().st_size
        inward_file_count += 1

    if sorted_providers:
        context.log.info("Expanded postcode bboxes to include nearby providers")

    context.log.info(
        f"Wrote {inward_file_count} inward files, "  # noqa: G004
        f"total {total_inward_size / 1024 / 1024:.1f} MB"
    )

    return {
        "postcodes_processed": MetadataValue.int(processed),
        "postcodes_skipped": MetadataValue.int(skipped),
        "outward_codes": MetadataValue.int(len(sorted_outward)),
        "inward_files": MetadataValue.int(inward_file_count),
        "outward_json_kb": MetadataValue.float(round(outward_size / 1024, 1)),
        "inward_total_mb": MetadataValue.float(
            round(total_inward_size / 1024 / 1024, 1)
        ),
        "unique_lad_codes": MetadataValue.int(len(all_lad_codes)),
        "postcodes_with_iod": MetadataValue.int(iod_count),
    }
