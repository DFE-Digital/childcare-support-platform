"""Load DfE free breakfast club schools data into dfe.free_breakfast_club_schools.

Source: https://www.gov.uk/government/publications/free-breakfast-in-schools
Expected file: source_data/Free_breakfast_clubs_-_schools_on_the_scheme_020226.xlsx

Parses the XLSX using stdlib zipfile + defusedxml.
Idempotent: DROP + recreate on each run.
"""

import zipfile
import defusedxml.ElementTree as ET
from pathlib import Path

from dagster import asset, AssetExecutionContext, MetadataValue

from bsil_pipeline.resources.postgres import BsilPostgresResource
from bsil_pipeline.assets.schema_tables import DFE_FREE_BREAKFAST_CLUB_SCHOOLS_DDL

XLSX_PATH = Path(
    "/opt/dagster/app/source_data"
    "/Free_breakfast_clubs_-_schools_on_the_scheme_020226.xlsx"
)

_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"

CREATE_SQL = DFE_FREE_BREAKFAST_CLUB_SCHOOLS_DDL

INSERT_SQL = """
INSERT INTO dfe.free_breakfast_club_schools
    (urn, school_name, type, establishment_type_group, gor_name, la_name)
VALUES
    (%(urn)s, %(school_name)s, %(type)s, %(establishment_type_group)s,
     %(gor_name)s, %(la_name)s)
"""


def _read_xlsx(path: Path) -> list[dict]:
    """Parse an xlsx file into a list of dicts using only stdlib."""
    with zipfile.ZipFile(path) as z:
        with z.open("xl/sharedStrings.xml") as f:
            ss_tree = ET.parse(f)
        shared = [
            "".join(t.text or "" for t in si.iter(f"{{{_NS}}}t"))
            for si in ss_tree.findall(f".//{{{_NS}}}si")
        ]

        with z.open("xl/worksheets/sheet1.xml") as f:
            ws_tree = ET.parse(f)

    raw_rows: list[list[str | None]] = []
    for row_el in ws_tree.findall(f".//{{{_NS}}}row"):
        vals: list[str | None] = []
        for c in row_el.findall(f"{{{_NS}}}c"):
            cell_type = c.get("t", "")
            v_el = c.find(f"{{{_NS}}}v")
            v = v_el.text if v_el is not None else None
            if cell_type == "s":
                vals.append(shared[int(v)] if v is not None else None)
            elif cell_type == "inlineStr":
                t_el = c.find(f".//{{{_NS}}}t")
                vals.append(t_el.text if t_el is not None else None)
            else:
                vals.append(v)
        raw_rows.append(vals)

    if not raw_rows:
        return []

    headers = [str(h).strip() if h else "" for h in raw_rows[0]]
    col_map = {
        "URN": "urn",
        "School Name": "school_name",
        "Type": "type",
        "Establishment Type Group": "establishment_type_group",
        "GOR Name": "gor_name",
        "LA Name": "la_name",
    }

    records = []
    for row in raw_rows[1:]:
        record: dict[str, str | None] = {pg: None for pg in col_map.values()}
        for i, header in enumerate(headers):
            pg_col = col_map.get(header)
            if pg_col and i < len(row):
                val = row[i]
                record[pg_col] = str(val).strip() if val is not None else None
        records.append(record)
    return records


@asset(group_name="dfe", deps=["dfe_free_breakfast_club_schools_table"])
def free_breakfast_club_schools(
    context: AssetExecutionContext, bsil_postgres: BsilPostgresResource
):
    """Load DfE free breakfast club schools into dfe.free_breakfast_club_schools.

    Idempotent: DROP + recreate on each run.
    Source file updated 02/02/2026 — 1,354 schools on the scheme.
    """
    if not XLSX_PATH.exists():
        context.log.error(f"XLSX not found: {XLSX_PATH}")
        return {"error": MetadataValue.text(f"XLSX not found: {XLSX_PATH}")}

    records = _read_xlsx(XLSX_PATH)
    context.log.info(f"Parsed {len(records)} rows from XLSX")

    with bsil_postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS dfe.free_breakfast_club_schools")
            cur.execute(CREATE_SQL)
            cur.executemany(INSERT_SQL, records)
        conn.commit()

    context.log.info(f"Loaded {len(records)} rows into dfe.free_breakfast_club_schools")
    return {"row_count": MetadataValue.int(len(records))}
