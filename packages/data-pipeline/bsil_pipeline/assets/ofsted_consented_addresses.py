"""Load Ofsted consented addresses for childminders into ofsted.consented_addresses.

Source: Consented_addresses_for_childminders_and_domestic_childcare_as_at_31_March_2026.csv
The first 3 rows are metadata; column headers are on row 4.

Provides ~7,500 consented home addresses for childminder URNs whose address
fields are REDACTED in ofsted.inspections. Used as a fallback in address
COALESCE chains downstream.
"""

import csv
from pathlib import Path

from dagster import asset, AssetExecutionContext, MetadataValue

from bsil_pipeline.resources.postgres import BsilPostgresResource
from bsil_pipeline.assets.schema_tables import OFSTED_CONSENTED_ADDRESSES_DDL

CSV_PATH = Path(
    "/opt/dagster/app/source_data/"
    "Consented_addresses_for_childminders_and_domestic_childcare_as_at_31_March_2026.csv"
)

BATCH_SIZE = 1000

# Source CSV column → DB column
_COLUMNS = {
    "Provider URN": "provider_urn",
    "Provider Type": "provider_type",
    "Individual Register combinations": "register_combo",
    "Provider Early Years Register Flag": "eyr_flag",
    "Provider Compulsory Childcare Register Flag": "ccr_flag",
    "Provider Voluntary Childcare Register Flag": "vcr_flag",
    "Provider name": "provider_name",
    "Provider address line 1": "address_line_1",
    "Provider address line 2": "address_line_2",
    "Provider address line 3": "address_line_3",
    "Provider town": "town",
    "Postcode": "postcode",
    "Parliamentary Constituency": "parliamentary_constituency",
    "Local Authority": "local_authority",
    "Region": "region",
    "Ofsted Region": "ofsted_region",
}

_PG_COLS = list(_COLUMNS.values())
_col_names = ", ".join(_PG_COLS)
_placeholders = ", ".join(f"%({c})s" for c in _PG_COLS)
INSERT_SQL = (
    f"INSERT INTO ofsted.consented_addresses ({_col_names}) VALUES ({_placeholders})"  # nosec B608
)


@asset(group_name="ofsted", deps=["ofsted_consented_addresses_table"])
def ofsted_consented_addresses(
    context: AssetExecutionContext, bsil_postgres: BsilPostgresResource
):
    """Load consented childminder addresses into ofsted.consented_addresses.

    Skips first 3 metadata rows; column headers on row 4. Idempotent: DROP + recreate.
    """
    if not CSV_PATH.exists():
        context.log.error(f"CSV not found: {CSV_PATH}")
        return {"error": MetadataValue.text(f"CSV not found: {CSV_PATH}")}

    # Read headers from row 4 (skip 3 metadata rows)
    with open(CSV_PATH, "r", encoding="latin-1") as f:
        reader = csv.reader(f)
        for _ in range(3):
            next(reader)
        raw_headers = next(reader)

    header_map: dict[int, str] = {}
    for i, h in enumerate(raw_headers):
        h_stripped = h.strip()
        if h_stripped in _COLUMNS:
            header_map[i] = _COLUMNS[h_stripped]

    missing = set(_COLUMNS.keys()) - {raw_headers[i].strip() for i in header_map}
    if missing:
        context.log.warning(f"CSV missing expected columns: {missing}")

    context.log.info(
        f"CSV: {len(raw_headers)} columns total, {len(header_map)} matched to whitelist"
    )

    row_count = 0
    with bsil_postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS ofsted.consented_addresses")
            cur.execute(OFSTED_CONSENTED_ADDRESSES_DDL)
        conn.commit()

        with open(CSV_PATH, "r", encoding="latin-1") as f:
            reader = csv.reader(f)
            for _ in range(4):  # skip 3 metadata rows + header row
                next(reader)

            batch: list[dict] = []
            with conn.cursor() as cur:
                for raw_row in reader:
                    row_data = {col: None for col in _PG_COLS}
                    for i, pg_col in header_map.items():
                        val = raw_row[i].strip() if i < len(raw_row) else None
                        row_data[pg_col] = val if val else None
                    batch.append(row_data)

                    if len(batch) >= BATCH_SIZE:
                        cur.executemany(INSERT_SQL, batch)
                        row_count += len(batch)
                        batch = []

                if batch:
                    cur.executemany(INSERT_SQL, batch)
                    row_count += len(batch)

        conn.commit()

    context.log.info(f"Loaded {row_count} rows into ofsted.consented_addresses")
    return {"row_count": MetadataValue.int(row_count)}
