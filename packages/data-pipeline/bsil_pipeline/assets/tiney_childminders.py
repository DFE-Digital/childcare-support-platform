"""Load Tiney childminder agency feed into tiney.childminders.

Source: tiney-childminder-feed.csv — Tiney CMA-registered childminders.
Idempotent: TRUNCATE + reload on each run.
All lifecycle statuses stored; filtering to 'open' happens downstream in care_offerings.
"""

import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from dagster import asset, AssetExecutionContext, MetadataValue

from bsil_pipeline.resources.postgres import BsilPostgresResource

CSV_PATH = Path("/opt/dagster/app/source_data/tiney-childminder-feed.csv")

INSERT_SQL = """
INSERT INTO tiney.childminders (
    ofsted_urn, provider_name, address_line_1, address_city, postcode,
    uk_region, local_authority_name, website_url, ofsted_register_combination,
    tiney_registration_type, tiney_registration_date, age_range,
    last_inspection_date, last_inspection_type, cma_qa_grading,
    registered_places, operating_weeks_per_year, minimum_commitment,
    opening_hours, placement_type, funded_hours_accepted,
    hourly_rate_gbp, daily_rate_gbp, additional_charges, tiney_lifecycle_status
) VALUES (
    %(ofsted_urn)s, %(provider_name)s, %(address_line_1)s, %(address_city)s,
    %(postcode)s, %(uk_region)s, %(local_authority_name)s, %(website_url)s,
    %(ofsted_register_combination)s, %(tiney_registration_type)s,
    %(tiney_registration_date)s, %(age_range)s, %(last_inspection_date)s,
    %(last_inspection_type)s, %(cma_qa_grading)s, %(registered_places)s,
    %(operating_weeks_per_year)s, %(minimum_commitment)s, %(opening_hours)s,
    %(placement_type)s, %(funded_hours_accepted)s, %(hourly_rate_gbp)s,
    %(daily_rate_gbp)s, %(additional_charges)s, %(tiney_lifecycle_status)s
)
"""


def _parse_date(val: str | None) -> date | None:
    if not val or not val.strip():
        return None
    try:
        parts = val.strip().split("-")
        return date(int(parts[0]), int(parts[1]), int(parts[2]))
    except (ValueError, IndexError):
        return None


def _parse_bool(val: str | None) -> bool | None:
    if not val or not val.strip():
        return None
    return val.strip().lower() == "true"


def _parse_decimal(val: str | None) -> Decimal | None:
    if not val or not val.strip():
        return None
    try:
        return Decimal(val.strip())
    except InvalidOperation:
        return None


def _parse_int(val: str | None) -> int | None:
    if not val or not val.strip():
        return None
    try:
        return int(val.strip())
    except ValueError:
        return None


def _text_or_none(val: str | None) -> str | None:
    if not val or not val.strip():
        return None
    return val.strip()


@asset(group_name="tiney", deps=["tiney_childminders_table"])
def tiney_childminders(
    context: AssetExecutionContext, bsil_postgres: BsilPostgresResource
):
    """Load Tiney childminder feed from CSV into tiney.childminders.

    Idempotent: truncates and reloads all rows on each run.
    """
    context.log.info(f"Loading CSV file: {CSV_PATH}")

    rows = []
    with open(CSV_PATH, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(
                {
                    "ofsted_urn": _text_or_none(row.get("ofsted_urn")),
                    "provider_name": _text_or_none(row.get("provider_name")),
                    "address_line_1": _text_or_none(row.get("address_line_1")),
                    "address_city": _text_or_none(row.get("address_city")),
                    "postcode": _text_or_none(row.get("postcode")),
                    "uk_region": _text_or_none(row.get("uk_region")),
                    "local_authority_name": _text_or_none(
                        row.get("local_authority_name")
                    ),
                    "website_url": _text_or_none(row.get("website_url")),
                    "ofsted_register_combination": _text_or_none(
                        row.get("ofsted_register_combination")
                    ),
                    "tiney_registration_type": _text_or_none(
                        row.get("tiney_registration_type")
                    ),
                    "tiney_registration_date": _parse_date(
                        row.get("tiney_registration_date")
                    ),
                    "age_range": _text_or_none(row.get("age_range")),
                    "last_inspection_date": _parse_date(
                        row.get("last_inspection_date")
                    ),
                    "last_inspection_type": _text_or_none(
                        row.get("last_inspection_type")
                    ),
                    "cma_qa_grading": _text_or_none(row.get("cma_qa_grading")),
                    "registered_places": _parse_int(row.get("registered_places")),
                    "operating_weeks_per_year": _parse_int(
                        row.get("operating_weeks_per_year")
                    ),
                    "minimum_commitment": _text_or_none(row.get("minimum_commitment")),
                    "opening_hours": _text_or_none(row.get("opening_hours")),
                    "placement_type": _text_or_none(row.get("placement_type")),
                    "funded_hours_accepted": _parse_bool(
                        row.get("funded_hours_accepted")
                    ),
                    "hourly_rate_gbp": _parse_decimal(row.get("hourly_rate_gbp")),
                    "daily_rate_gbp": _parse_decimal(row.get("daily_rate_gbp")),
                    "additional_charges": _text_or_none(row.get("additional_charges")),
                    "tiney_lifecycle_status": _text_or_none(
                        row.get("tiney_lifecycle_status")
                    ),
                }
            )

    context.log.info(f"Read {len(rows)} rows from CSV")

    with bsil_postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE tiney.childminders")
            cur.executemany(INSERT_SQL, rows)
        conn.commit()

    context.log.info(f"Loaded {len(rows)} rows into tiney.childminders")
    return {"row_count": MetadataValue.int(len(rows))}
