"""Generate a compact postcode→LAD lookup from ONSPD CSV data.

Reads the ONSPD CSV file and outputs a gzipped CSV with columns:
pcds (postcode), oslaua (LAD code), lat, long.
Terminated postcodes are excluded.

Source data: ONSPD FEB 2026 CSV from ONS Geoportal.
"""

import csv
import gzip
import os
import shutil
import tempfile
from pathlib import Path

from dagster import asset, AssetExecutionContext, MetadataValue

_SOURCE_DATA = Path(__file__).resolve().parents[2] / "source_data"
_DEFAULT_INPUT = _SOURCE_DATA / "ONSPD_FEB_2026_UK.csv"
_DEFAULT_OUTPUT = (
    Path(__file__).resolve().parent.parent.parent
    / "data"
    / "postcode_lad_lookup.csv.gz"
)


@asset(group_name="onspd")
def postcode_lookup(context: AssetExecutionContext):
    """Generate postcode_lad_lookup.csv.gz from ONSPD CSV.

    Reads the ONSPD CSV, filters out terminated postcodes and rows without
    LAD codes, and writes a gzipped CSV for use by the postcode_lookup utility.

    Source data must be downloaded manually from ONS Geoportal:
      ONSPD FEB 2026 CSV → source_data/ONSPD_FEB_2026_UK.csv
    """
    input_path = Path(os.environ.get("ONSPD_CSV_PATH", str(_DEFAULT_INPUT)))
    output_path = Path(os.environ.get("POSTCODE_LOOKUP_PATH", str(_DEFAULT_OUTPUT)))

    if not input_path.exists():
        context.log.error(
            f"ONSPD CSV not found at {input_path} — download ONSPD from https://geoportal.statistics.gov.uk/"
        )
        return {"error": MetadataValue.text(f"ONSPD CSV not found at {input_path}")}

    context.log.info(f"Reading ONSPD CSV from: {input_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_str = tempfile.mkstemp(suffix=".csv.gz", dir=output_path.parent)
    os.close(tmp_fd)
    tmp_path = Path(tmp_str)

    total = 0
    live_count = 0

    with (
        open(str(input_path), "r", newline="") as infile,
        gzip.open(str(tmp_path), "wt", newline="") as outfile,
    ):
        reader = csv.DictReader(infile)
        writer = csv.writer(outfile)
        writer.writerow(["pcds", "oslaua", "lat", "long"])

        for row in reader:
            total += 1

            # Skip terminated postcodes (doterm is non-empty)
            if row.get("doterm", "").strip():
                continue

            lad_code = row.get("lad25cd", "").strip()
            if not lad_code:
                continue

            pcds = row.get("pcds", "").strip()
            lat = row.get("lat", "").strip()
            lon = row.get("long", "").strip()

            writer.writerow([pcds, lad_code, lat, lon])
            live_count += 1

            if live_count % 500_000 == 0:
                context.log.info(f"  Progress: {live_count} live postcodes written...")

    size_mb = tmp_path.stat().st_size / 1024 / 1024
    context.log.info(
        f"postcode_lad_lookup.csv.gz written to tmp: {size_mb:.1f} MB (total: {total}, live with LAD: {live_count})"
    )

    # Validate before moving to final location
    try:
        with gzip.open(str(tmp_path), "rt") as f:
            header = next(f)
        context.log.info(f"Validation passed — gzip readable, header: {header.strip()}")
    except Exception as e:
        raise RuntimeError(f"Temp file {tmp_path} is not a valid gzip: {e}") from e

    shutil.move(str(tmp_path), str(output_path))
    context.log.info(f"Moved to final path: {output_path}")

    return {
        "total_postcodes": MetadataValue.int(total),
        "live_postcodes": MetadataValue.int(live_count),
        "file_size_mb": MetadataValue.float(round(size_mb, 1)),
    }
