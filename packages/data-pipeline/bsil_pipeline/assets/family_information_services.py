import csv
import os
from pathlib import Path

from dagster import asset, AssetExecutionContext, MetadataValue

from bsil_pipeline.resources.postgres import BsilPostgresResource

CSV_PATH = Path(
    os.environ.get(
        "FIS_CSV_PATH", "/opt/dagster/app/source_data/family_information_services.csv"
    )
)

COLUMNS = ["lad25cd", "lad25nm", "fis_url", "childcare_types", "notes"]

INSERT_SQL = (
    "INSERT INTO la.family_information_services (lad25cd, lad25nm, fis_url, childcare_types, notes) "
    "VALUES (%(lad25cd)s, %(lad25nm)s, %(fis_url)s, %(childcare_types)s, %(notes)s)"
)


@asset(group_name="la", deps=["la_family_information_services_table"])
def family_information_services(
    context: AssetExecutionContext, bsil_postgres: BsilPostgresResource
):
    """Load Family Information Services data from CSV into la.family_information_services table.

    Idempotent: truncates and reloads all rows on each run.
    """
    context.log.info(f"Loading CSV file: {CSV_PATH}")

    rows = []
    with open(CSV_PATH, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Normalise CSV headers to lowercase to match DB columns
            normalised = {k.lower(): v for k, v in row.items()}
            rows.append({col: normalised.get(col) or None for col in COLUMNS})

    context.log.info(f"Read {len(rows)} rows from CSV")

    with bsil_postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE la.family_information_services")
            cur.executemany(INSERT_SQL, rows)
        conn.commit()

    context.log.info(f"Loaded {len(rows)} rows into la.family_information_services")
    return {"row_count": MetadataValue.int(len(rows))}
