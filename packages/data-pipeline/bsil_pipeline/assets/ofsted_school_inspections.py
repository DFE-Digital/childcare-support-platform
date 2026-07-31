"""Load Ofsted school inspection MI data into ofsted.school_inspections.

Source: gov.uk "Management information - state-funded schools - latest inspections"
Expected file: source_data/Management_information_-_state-funded_schools_-_*.csv

Loads both legacy OEIF (1-4 grades) and new report-card (named grades) data.
"""

import csv
import re
from datetime import datetime
from pathlib import Path

from dagster import asset, AssetExecutionContext, MetadataValue

from bsil_pipeline.resources.postgres import BsilPostgresResource
from bsil_pipeline.assets.schema_tables import OFSTED_SCHOOL_INSPECTIONS_DDL

SOURCE_DIR = Path("/opt/dagster/app/source_data")
CSV_GLOB = "Management_information_-_state-funded_schools_-_*.csv"

BATCH_SIZE = 1000

# CSV header → pg column name
_COLUMNS = {
    "URN": "urn",
    "School name": "school_name",
    "Ofsted phase": "ofsted_phase",
    "Inspection start date": "inspection_date",
    # Report-card graded properties
    "Safeguarding standards": "safeguarding_standards",
    "Achievement": "achievement",
    "Curriculum and teaching": "curriculum_and_teaching",
    "Attendance and behaviour": "attendance_and_behaviour",
    "Personal development and wellbeing": "personal_development_wellbeing",
    "Inclusion": "inclusion",
    "Leadership and governance": "leadership_and_governance",
    "Early years (where applicable)": "early_years",
    "Post-16 provision (where applicable)": "post_16",
    # Legacy OEIF
    "Inspection start date of latest OEIF graded inspection": "oeif_inspection_date",
    "Latest OEIF overall effectiveness": "oeif_overall_effectiveness",
    "Latest OEIF quality of education": "oeif_quality_of_education",
    "Latest OEIF behaviour and attitudes": "oeif_behaviour_and_attitudes",
    "Latest OEIF personal development": "oeif_personal_development",
    "Latest OEIF effectiveness of leadership and management": "oeif_leadership_and_management",
    "Latest OEIF  safeguarding is effective?": "oeif_safeguarding_effective",
    "Latest OEIF early years provision (where applicable)": "oeif_early_years",
    "Latest OEIF sixth form provision (where applicable)": "oeif_sixth_form",
    # Ungraded inspections
    "Date of latest ungraded inspection": "ungraded_inspection_date",
    "Ungraded inspection overall outcome": "ungraded_overall_outcome",
}

_PG_COLS = list(_COLUMNS.values())

CREATE_SQL = OFSTED_SCHOOL_INSPECTIONS_DDL

_col_names = ", ".join(_PG_COLS)
_placeholders = ", ".join(f"%({c})s" for c in _PG_COLS)
INSERT_SQL = (
    f"INSERT INTO ofsted.school_inspections ({_col_names}) VALUES ({_placeholders})"  # nosec B608
)


def _open_csv(path: Path):
    """Open CSV with encoding detection (utf-8-sig preferred, cp1252 fallback)."""
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            f.read()  # test full file
        return open(path, "r", encoding="utf-8-sig")  # noqa: SIM115
    except UnicodeDecodeError:
        return open(path, "r", encoding="cp1252")  # noqa: SIM115


_DATE_RE = re.compile(r"(\d{1,2}_[A-Za-z]+_\d{4})\.csv$")


def _parse_filename_date(path: Path) -> datetime:
    """Extract and parse the date suffix from a school inspections CSV filename.

    E.g. '...as_at_28_Feb_2026.csv' → datetime(2026, 2, 28).
    Returns datetime.min for unparseable names so they sort last.
    """
    m = _DATE_RE.search(path.name)
    if not m:
        return datetime.min
    try:
        return datetime.strptime(m.group(1), "%d_%b_%Y")
    except ValueError:
        return datetime.min


def _find_csv() -> Path | None:
    """Find the newest school inspections CSV in source_data by date in filename."""
    matches = list(SOURCE_DIR.glob(CSV_GLOB))
    if not matches:
        return None
    return max(matches, key=_parse_filename_date)


def _nullify(val: str | None) -> str | None:
    """Convert empty strings and 'NULL' to None."""
    if not val:
        return None
    val = val.strip()
    if val in ("", "NULL", "Not applicable", "Not judged"):
        return None
    return val


@asset(group_name="ofsted", deps=["ofsted_school_inspections_table"])
def ofsted_school_inspections(
    context: AssetExecutionContext, bsil_postgres: BsilPostgresResource
):
    """Load Ofsted school inspection MI CSV into ofsted.school_inspections.

    Whitelist of columns loaded as TEXT. Idempotent: DROP + recreate.
    """
    csv_path = _find_csv()
    if csv_path is None:
        context.log.warning(f"No school inspections CSV found matching {CSV_GLOB}")
        return {"error": MetadataValue.text("CSV not found")}

    context.log.info(f"Loading: {csv_path.name}")

    # Discover column positions
    with _open_csv(csv_path) as f:
        reader = csv.reader(f)
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
        f"CSV: {len(raw_headers)} columns total, {len(header_map)} matched"
    )

    row_count = 0
    with bsil_postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS ofsted.school_inspections")
            cur.execute(CREATE_SQL)
        conn.commit()

        with _open_csv(csv_path) as f:
            reader = csv.reader(f)
            next(reader)  # skip header

            batch: list[dict] = []
            with conn.cursor() as cur:
                for raw_row in reader:
                    row_data = {}
                    for i, pg_col in header_map.items():
                        val = raw_row[i].strip() if i < len(raw_row) else None
                        row_data[pg_col] = _nullify(val)
                    batch.append(row_data)

                    if len(batch) >= BATCH_SIZE:
                        cur.executemany(INSERT_SQL, batch)
                        row_count += len(batch)
                        batch = []

                if batch:
                    cur.executemany(INSERT_SQL, batch)
                    row_count += len(batch)

        conn.commit()

    context.log.info(f"Loaded {row_count} rows into ofsted.school_inspections")
    return {"row_count": MetadataValue.int(row_count)}
