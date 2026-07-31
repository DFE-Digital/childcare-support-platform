"""Load cost estimates by LA, age group and provider type into ten_ds.cost_estimates.

Source: Internally produced CSV of estimated childcare costs per English LA.
Expected file: source_data/estimates_by_la_age_by_provtype.csv
(1359 data rows: 151 LAs x 3 age groups x 3 provider types).

Idempotent: DROP + recreate on each run.
"""

import csv
from pathlib import Path

from dagster import asset, AssetExecutionContext, MetadataValue

from bsil_pipeline.resources.postgres import BsilPostgresResource
from bsil_pipeline.assets.schema_tables import TEN_DS_COST_ESTIMATES_DDL

CSV_PATH = Path("/opt/dagster/app/source_data/estimates_by_la_age_by_provtype.csv")

BATCH_SIZE = 500

_COLUMNS = [
    "la_code",
    "la_name",
    "region",
    "age_group",
    "prov_group",
    "hourly_lower",
    "hourly_mean",
    "hourly_weighted_mean",
    "hourly_upper",
    "meal_lower",
    "meal_mean",
    "meal_upper",
    "funding_rate",
    "data_level",
    "n_la",
    "n_region",
    "n_national",
]

_FLOAT_COLS = {
    "hourly_lower",
    "hourly_mean",
    "hourly_weighted_mean",
    "hourly_upper",
    "meal_lower",
    "meal_mean",
    "meal_upper",
    "funding_rate",
}

_INT_COLS = {"n_la", "n_region", "n_national"}

_col_names = ", ".join(_COLUMNS)
_placeholders = ", ".join(f"%({c})s" for c in _COLUMNS)
INSERT_SQL = (
    f"INSERT INTO ten_ds.cost_estimates ({_col_names}) "  # nosec B608
    f"VALUES ({_placeholders})"
)


def _parse_row(row: dict) -> dict:
    """Parse a CSV row dict, converting numeric fields."""
    parsed = {}
    for col in _COLUMNS:
        val = row.get(col, "").strip()
        if col in _FLOAT_COLS:
            parsed[col] = float(val) if val else None
        elif col in _INT_COLS:
            parsed[col] = int(val) if val else None
        else:
            parsed[col] = val if val else None
    return parsed


@asset(group_name="ten_ds", deps=["ten_ds_cost_estimates_table"])
def cost_estimates(
    context: AssetExecutionContext,
    bsil_postgres: BsilPostgresResource,
):
    """Load cost estimates CSV into ten_ds.cost_estimates.

    Idempotent: DROP + recreate on each run.
    """
    if not CSV_PATH.exists():
        context.log.error(f"CSV not found: {CSV_PATH}")  # noqa: G004
        return {"error": MetadataValue.text(f"CSV not found: {CSV_PATH}")}

    row_count = 0
    la_codes: set[str] = set()

    with bsil_postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS ten_ds.cost_estimates")
            cur.execute(TEN_DS_COST_ESTIMATES_DDL)
        conn.commit()

        with open(CSV_PATH, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            batch: list[dict] = []

            with conn.cursor() as cur:
                for row in reader:
                    parsed = _parse_row(row)
                    batch.append(parsed)
                    if parsed["la_code"]:
                        la_codes.add(parsed["la_code"])

                    if len(batch) >= BATCH_SIZE:
                        cur.executemany(INSERT_SQL, batch)
                        row_count += len(batch)
                        batch = []

                if batch:
                    cur.executemany(INSERT_SQL, batch)
                    row_count += len(batch)

        conn.commit()

    context.log.info(
        f"Loaded {row_count} rows for {len(la_codes)} LAs "  # noqa: G004
        f"into ten_ds.cost_estimates"
    )
    return {
        "row_count": MetadataValue.int(row_count),
        "la_count": MetadataValue.int(len(la_codes)),
    }
