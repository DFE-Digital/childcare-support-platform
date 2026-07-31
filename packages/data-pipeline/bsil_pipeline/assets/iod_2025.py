"""Load IoD 2025 data into mhclg.iod_2025.

Source: MHCLG Index of Multiple Deprivation 2025
Expected file: source_data/File_1_IoD2025_Index_of_Multiple_Deprivation.xlsx
Sheet: IMD25 (33,755 rows — one per LSOA in England)

Parses the XLSX using stdlib zipfile + defusedxml.
Idempotent: DROP + recreate on each run.
"""

import zipfile

import defusedxml.ElementTree as ET
from pathlib import Path

from dagster import asset, AssetExecutionContext, MetadataValue

from bsil_pipeline.resources.postgres import BsilPostgresResource
from bsil_pipeline.assets.schema_tables import MHCLG_IOD_2025_DDL

XLSX_PATH = Path(
    "/opt/dagster/app/source_data/File_1_IoD2025_Index_of_Multiple_Deprivation.xlsx"
)

_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_NS_RELS = "http://schemas.openxmlformats.org/package/2006/relationships"

BATCH_SIZE = 1000

INSERT_SQL = """
INSERT INTO mhclg.iod_2025
    (lsoa21cd, lsoa21nm, lad24cd, lad24nm, imd_rank, imd_decile)
VALUES
    (%(lsoa21cd)s, %(lsoa21nm)s, %(lad24cd)s, %(lad24nm)s,
     %(imd_rank)s, %(imd_decile)s)
"""

_COL_MAP = {
    "LSOA code (2021)": "lsoa21cd",
    "LSOA name (2021)": "lsoa21nm",
    "Local Authority District code (2024)": "lad24cd",
    "Local Authority District name (2024)": "lad24nm",
    "Index of Multiple Deprivation (IMD) Rank": "imd_rank",
    "Index of Multiple Deprivation (IMD) Decile": "imd_decile",
}


def _resolve_sheet_path(z: zipfile.ZipFile, sheet_name: str) -> str:
    """Resolve a sheet name to its physical worksheet path inside the XLSX."""
    wb_tree = ET.parse(z.open("xl/workbook.xml"))
    rid = None
    for sheet_el in wb_tree.findall(f".//{{{_NS}}}sheet"):
        if sheet_el.get("name") == sheet_name:
            rid = sheet_el.get(f"{{{_NS_R}}}id")
            break
    if not rid:
        raise ValueError(f"Sheet '{sheet_name}' not found in workbook")

    rels_tree = ET.parse(z.open("xl/_rels/workbook.xml.rels"))
    for rel in rels_tree.findall(f".//{{{_NS_RELS}}}Relationship"):
        if rel.get("Id") == rid:
            return "xl/" + rel.get("Target")
    raise ValueError(f"Relationship {rid} not found in workbook.xml.rels")


def _read_xlsx(path: Path) -> list[dict]:
    """Parse the IMD25 sheet into a list of dicts."""
    with zipfile.ZipFile(path) as z:
        with z.open("xl/sharedStrings.xml") as f:
            ss_tree = ET.parse(f)
        shared = [
            "".join(t.text or "" for t in si.iter(f"{{{_NS}}}t"))
            for si in ss_tree.findall(f".//{{{_NS}}}si")
        ]

        sheet_path = _resolve_sheet_path(z, "IMD25")
        with z.open(sheet_path) as f:
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

    col_indices: dict[str, int] = {}
    for i, header in enumerate(headers):
        for prefix, pg_col in _COL_MAP.items():
            if header.startswith(prefix):
                col_indices[pg_col] = i
                break

    records = []
    for row in raw_rows[1:]:
        record: dict[str, str | None] = {}
        for pg_col, idx in col_indices.items():
            val = row[idx] if idx < len(row) else None
            record[pg_col] = str(val).strip() if val is not None else None
        if record.get("lsoa21cd"):
            records.append(record)
    return records


@asset(group_name="mhclg", deps=["mhclg_iod_2025_table"])
def iod_2025(context: AssetExecutionContext, bsil_postgres: BsilPostgresResource):
    """Load MHCLG IoD 2025 into mhclg.iod_2025.

    Idempotent: DROP + recreate on each run.
    Source file: File_1_IoD2025_Index_of_Multiple_Deprivation.xlsx — 33,755 LSOAs.
    """
    if not XLSX_PATH.exists():
        context.log.error(f"XLSX not found: {XLSX_PATH}")
        return {"error": MetadataValue.text(f"XLSX not found: {XLSX_PATH}")}

    records = _read_xlsx(XLSX_PATH)
    context.log.info(f"Parsed {len(records)} rows from XLSX")

    with bsil_postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS mhclg.iod_2025")
            cur.execute(MHCLG_IOD_2025_DDL)
            for i in range(0, len(records), BATCH_SIZE):
                cur.executemany(INSERT_SQL, records[i : i + BATCH_SIZE])
        conn.commit()

    context.log.info(f"Loaded {len(records)} rows into mhclg.iod_2025")
    return {"row_count": MetadataValue.int(len(records))}
