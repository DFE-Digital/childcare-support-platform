"""Standalone script to generate LA boundary GeoJSON.

Prefer running this via Dagster: the `la_boundaries` asset in the
`load_source_data` job does the same thing and writes to exported_data/.

This script exists for manual one-off generation outside Dagster.
"""

import logging
import sys
from pathlib import Path

# Add the pipeline package to sys.path so we can import the asset logic
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "data-pipeline"))

from bsil_pipeline.assets.la_boundaries import generate_la_boundaries

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger(__name__)

SOURCE_DIR = Path("/opt/dagster/app/source_data")
OUTPUT_PATH = Path("/opt/dagster/app/output/la_boundaries.geojson")


def main():
    count = generate_la_boundaries(SOURCE_DIR, OUTPUT_PATH, log)
    if count == 0:
        print("No boundaries generated -- check source data path")
        sys.exit(1)
    print(f"Done: {count} features -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
