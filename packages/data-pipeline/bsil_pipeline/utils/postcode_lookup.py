"""Postcode→LAD code lookup utility.

Loads a pre-generated gzipped CSV of postcode→LAD mappings (from ONSPD)
and provides lookup functions:
  - postcode_to_lad(postcode) — direct postcode lookup
  - coords_to_lad(lat, lon, target_lads) — nearest-neighbor spatial lookup
    for providers without postcodes (e.g., Devon)

Generate the lookup file with the postcode_lookup Dagster asset (load_source_data job).
"""

from __future__ import annotations

import csv
import gzip
import logging
import math
import os
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Module-level caches
_lookup: dict[str, str] | None = None
_coord_data: list[tuple[float, float, str]] | None = None

# Default path relative to the data-pipeline package
_DEFAULT_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "data"
    / "postcode_lad_lookup.csv.gz"
)

_POSTCODE_NORMALIZE_RE = re.compile(r"\s+")


def _normalize_postcode(postcode: str) -> str:
    """Normalize a postcode for lookup: uppercase, single space before inward code."""
    pc = _POSTCODE_NORMALIZE_RE.sub("", postcode.strip().upper())
    # Insert space before last 3 chars (inward code)
    if len(pc) >= 5:
        return pc[:-3] + " " + pc[-3:]
    return pc


def _get_lookup_path() -> Path:
    return Path(os.environ.get("POSTCODE_LOOKUP_PATH", str(_DEFAULT_PATH)))


def _load_lookup() -> dict[str, str]:
    """Load the postcode→LAD lookup from the CSV file."""
    path = _get_lookup_path()

    if not path.exists():
        logger.warning(
            "Postcode lookup file not found at %s — "
            "LAD assignment will fall back to partition code. "
            "Run the postcode_lookup Dagster asset (load_source_data job).",
            path,
        )
        return {}

    if path.stat().st_size < 50:
        raise RuntimeError(
            f"Postcode lookup file at {path} is a placeholder ({path.stat().st_size} bytes). "
            f"Run the postcode_lookup Dagster asset (load_source_data job) to generate real data "
            f"before running pipeline steps that require LAD assignment."
        )

    logger.info("Loading postcode→LAD lookup from %s", path)
    lookup: dict[str, str] = {}
    with gzip.open(str(path), "rt") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row in reader:
            if len(row) >= 2:
                lookup[_normalize_postcode(row[0])] = row[1]
    logger.info("Loaded %d postcode→LAD mappings", len(lookup))
    return lookup


def _load_coord_data(target_lads: set[str]) -> list[tuple[float, float, str]]:
    """Load coordinate data for postcodes in the target LADs only.

    Returns list of (lat, lon, lad_code) tuples for nearest-neighbor search.
    Only loads postcodes belonging to the specified LAD codes to keep memory
    usage reasonable.
    """
    path = _get_lookup_path()
    if not path.exists():
        return []
    if path.stat().st_size < 50:
        raise RuntimeError(
            f"Postcode lookup file at {path} is a placeholder. "
            f"Run the postcode_lookup Dagster asset first."
        )

    data: list[tuple[float, float, str]] = []
    with gzip.open(str(path), "rt") as f:
        reader = csv.reader(f)
        next(reader)  # skip header: pcds, oslaua, lat, long
        for row in reader:
            if len(row) >= 4 and row[1] in target_lads:
                try:
                    lat = float(row[2])
                    lon = float(row[3])
                    if lat != 0 and lon != 0:
                        data.append((lat, lon, row[1]))
                except (ValueError, IndexError):
                    continue
    logger.info(
        "Loaded %d coordinate points for %d target LADs", len(data), len(target_lads)
    )
    return data


def postcode_to_lad(postcode: str | None) -> str | None:
    """Look up the LAD code for a UK postcode.

    Returns the LAD code (e.g., 'E07000041') or None if not found.
    Gracefully returns None if the lookup file is missing.
    """
    global _lookup
    if _lookup is None:
        _lookup = _load_lookup()

    if not postcode:
        return None

    normalized = _normalize_postcode(postcode)
    return _lookup.get(normalized)


def coords_to_lad(lat: float, lon: float, target_lads: set[str]) -> str | None:
    """Find the LAD code for coordinates using nearest-neighbor lookup.

    Searches ONSPD postcodes within the specified target LADs and returns
    the LAD code of the nearest postcode. Uses simple Euclidean distance
    on lat/lon (sufficient for district-level resolution within a county).

    Args:
        lat: Latitude of the point.
        lon: Longitude of the point.
        target_lads: Set of LAD codes to search within (e.g., Devon districts).

    Returns:
        The LAD code of the nearest postcode, or None if no data available.
    """
    global _coord_data
    if _coord_data is None:
        _coord_data = _load_coord_data(target_lads)

    if not _coord_data:
        return None

    best_dist = math.inf
    best_lad = None
    for plat, plon, lad in _coord_data:
        dist = (plat - lat) ** 2 + (plon - lon) ** 2
        if dist < best_dist:
            best_dist = dist
            best_lad = lad

    return best_lad
