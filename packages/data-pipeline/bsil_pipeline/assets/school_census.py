"""Load DfE school census data into dfe.school_census.

Reads spc_school_level_underlying_data_2025.csv (School Pupils and their
Characteristics) and loads all columns as TEXT into Postgres.

Source: https://explore-education-statistics.service.gov.uk/find-statistics/school-pupils-and-their-characteristics
"""

import csv
import re
from pathlib import Path

from dagster import asset, AssetExecutionContext, MetadataValue

from bsil_pipeline.resources.postgres import BsilPostgresResource

CSV_PATH = Path(
    "/opt/dagster/app/source_data/spc_school_level_underlying_data_2025.csv"
)

BATCH_SIZE = 1000


PG_MAX_IDENTIFIER = 63

# Shorten verbose DfE column name fragments before snake_casing
_ABBREVIATIONS = [
    ("number of pupils classified as ", "n_eth_"),
    ("% of pupils classified as ", "pct_eth_"),
    ("number of pupils whose first language is known or believed to be ", "n_lang_"),
    ("% of pupils whose first language is known or believed to be ", "pct_lang_"),
    ("number of pupils whose first language is ", "n_lang_"),
    ("% of pupils whose first language is ", "pct_lang_"),
    ("number of pupils known to be eligible for free school meals", "n_fsm_eligible"),
    ("% of pupils known to be eligible for free school meals", "pct_fsm_eligible"),
    (
        "number of FSM eligible pupils taking a free school meal on census day",
        "n_fsm_taking",
    ),
    ("% of FSM eligible pupils taking free school meals", "pct_fsm_taking"),
    (
        "Number of pupils (used for FSM calculation in Performance Tables)",
        "n_pupils_fsm_perf_tables",
    ),
    (
        "number of pupils of compulsory school age and above (rounded)",
        "n_pupils_compulsory_age",
    ),
    ("any other Asian background ethnic origin", "other_asian"),
    ("any other black background ethnic origin", "other_black"),
    ("any other ethnic group ethnic origin", "other_ethnic"),
    ("any other mixed background ethnic origin", "other_mixed"),
    ("any other white background ethnic origin", "other_white"),
    ("traveller of Irish heritage ethnic origin", "traveller_irish"),
    ("white and black Caribbean ethnic origin", "white_black_caribbean"),
    ("white and black African ethnic origin", "white_black_african"),
    ("white and Asian ethnic origin", "white_asian"),
    ("white British ethnic origin", "white_british"),
    ("Gypsy/Roma ethnic origin", "gypsy_roma"),
    ("Bangladeshi ethnic origin", "bangladeshi"),
    ("Caribbean ethnic origin", "caribbean"),
    ("Pakistani ethnic origin", "pakistani"),
    ("Chinese ethnic origin", "chinese"),
    ("African ethnic origin", "african"),
    ("Indian ethnic origin", "indian"),
    ("Irish ethnic origin", "irish"),
    ("ethnic origin", ""),
    ("(Performance Tables)", "perf_tables"),
    ("Infants taken a free school meal on census day", "infants_fsm_taking"),
    ("Number of key stage ", "n_ks"),
    ("Number of early year pupils (years E1 and E2)", "n_early_years"),
    ("Number of nursery pupils (years N1 and N2)", "n_nursery"),
    ("Number of reception pupils (year R)", "n_reception"),
    ("Number of pupils not reception or key stage 1 to 5", "n_pupils_other"),
    ("sex of school description", "sex_of_school"),
    ("district administrative ", "district_admin_"),
]


def _snake_case(name: str) -> str:
    """Convert CSV header to a valid snake_case Postgres column name."""
    s = name.strip()
    # Apply abbreviations before converting (case-insensitive)
    s_lower = s.lower()
    for long, short in _ABBREVIATIONS:
        if long.lower() in s_lower:
            idx = s_lower.index(long.lower())
            s = s[:idx] + short + s[idx + len(long) :]
            s_lower = s.lower()
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_").lower()
    # Column names can't start with a digit in Postgres
    if s and s[0].isdigit():
        s = "c_" + s
    if len(s) > PG_MAX_IDENTIFIER:
        s = s[:PG_MAX_IDENTIFIER]
    return s


@asset(group_name="dfe", deps=["dfe_school_census_table"])
def school_census(context: AssetExecutionContext, bsil_postgres: BsilPostgresResource):
    """Load DfE school census CSV into dfe.school_census.

    All columns loaded as TEXT. Idempotent: TRUNCATE + reload.
    """
    if not CSV_PATH.exists():
        context.log.error(f"CSV not found: {CSV_PATH}")
        return {"error": MetadataValue.text(f"CSV not found: {CSV_PATH}")}

    with open(CSV_PATH, "r", encoding="cp1252") as f:
        reader = csv.reader(f)
        raw_headers = next(reader)

    columns = [_snake_case(h) for h in raw_headers]

    # Deduplicate column names (append _2, _3 etc.)
    seen = {}
    deduped = []
    for col in columns:
        if col in seen:
            seen[col] += 1
            deduped.append(f"{col}_{seen[col]}")
        else:
            seen[col] = 1
            deduped.append(col)
    columns = deduped

    context.log.info(f"CSV has {len(columns)} columns, first 5: {columns[:5]}")

    col_defs = ",\n    ".join(f'"{col}" TEXT' for col in columns)
    create_sql = f"""
    CREATE TABLE IF NOT EXISTS dfe.school_census (
        {col_defs}
    )
    """

    placeholders = ", ".join(f"%({col})s" for col in columns)
    col_names = ", ".join(f'"{col}"' for col in columns)
    insert_sql = f"INSERT INTO dfe.school_census ({col_names}) VALUES ({placeholders})"  # nosec B608

    row_count = 0
    with bsil_postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS dfe.school_census")
            cur.execute(create_sql)
        conn.commit()

        with open(CSV_PATH, "r", encoding="cp1252") as f:
            reader = csv.reader(f)
            next(reader)  # skip header

            batch = []
            with conn.cursor() as cur:
                for raw_row in reader:
                    # Pad or truncate to match column count
                    row_data = {}
                    for i, col in enumerate(columns):
                        val = raw_row[i].strip() if i < len(raw_row) else None
                        row_data[col] = val if val else None
                    batch.append(row_data)

                    if len(batch) >= BATCH_SIZE:
                        cur.executemany(insert_sql, batch)
                        row_count += len(batch)
                        batch = []
                        if row_count % 10000 == 0:
                            context.log.info(f"Inserted {row_count} rows...")

                if batch:
                    cur.executemany(insert_sql, batch)
                    row_count += len(batch)

        conn.commit()

    context.log.info(f"Loaded {row_count} rows into dfe.school_census")
    return {"row_count": MetadataValue.int(row_count)}
