#!/usr/bin/env python3
"""
Run the data pipeline filtered to BETA_REGION_CODES and copy outputs to
packages/data-quality/data/vX/.

Run from packages/data-quality/:
    python run_pipeline.py
"""

import os
import shutil
import subprocess  # nosec B404
import sys
from pathlib import Path

from analyse_parquet import next_version_dir

PROJECT_ROOT = Path(__file__).parents[2]
PARQUET_SRC = PROJECT_ROOT / "exported_data" / "parquet" / "published"


def run(cmd: str, extra_env: dict[str, str] | None = None) -> None:
    print(f"\n>>> {cmd}")
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    result = subprocess.run(cmd.split(), cwd=PROJECT_ROOT, env=env)  # nosec B603
    if result.returncode != 0:
        print(f"ERROR: exit code {result.returncode}")
        sys.exit(result.returncode)


def main() -> None:
    run("make data/wipe")
    run("make data/up")
    run("make data/fetch-source")
    run("make data/load-sources")
    run("make data/scrape-ofsted")
    run("make data/scrape-la BETA=true partition=bath_ne_somerset")
    run("make data/extract-la BETA=true partition=bath_ne_somerset")
    run("make data/scrape-la BETA=true partition=liquidlogic")
    run("make data/extract-la BETA=true partition=liquidlogic")
    run("make data/scrape-la BETA=true partition=bristol_council")
    run("make data/extract-la BETA=true partition=bristol_council")
    run("make data/scrape-la BETA=true partition=south_gloucestershire")
    run("make data/extract-la BETA=true partition=south_gloucestershire")
    run("make data/geocode-ofsted BETA=true")
    run("make data/geocode-la BETA=true")
    run("make data/draft BETA=true")
    run("make data/publish BETA=true")
    run("make data/export-parquet")
    # run("make data/export-app-beta")
    # run("make prod/deploy-bsil env=dev")

    out_dir = next_version_dir()
    out_dir.mkdir(parents=True)
    print(f"\nCopying parquet files to {out_dir}")
    for filename in (
        "providers.parquet",
        "care_types.parquet",
        "opening_hours.parquet",
    ):
        shutil.copy2(PARQUET_SRC / filename, out_dir / filename)
        print(f"  {filename} → {out_dir / filename}")

    print(f"\nDone. Output in {out_dir}")


if __name__ == "__main__":
    main()
