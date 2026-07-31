import re
import zipfile
from pathlib import Path
from defusedxml.ElementTree import iterparse

from dagster import asset, AssetExecutionContext, MetadataValue

from bsil_pipeline.resources.postgres import BsilPostgresResource

ODS_PATH = Path(
    "/opt/dagster/app/source_data/"
    "Management_information_-_childcare_providers_and_inspections_"
    "as_at_31_December_2025.ods"
)

SHEET_NAME = "D1_Most_recent_inspections"

# Row indices in the ODS sheet
HEADER_ROW_INDEX = 2
DATA_START_ROW_INDEX = 3

# ODS XML namespaces
NS = {
    "table": "urn:oasis:names:tc:opendocument:xmlns:table:1.0",
    "text": "urn:oasis:names:tc:opendocument:xmlns:text:1.0",
    "office": "urn:oasis:names:tc:opendocument:xmlns:office:1.0",
}

TAG_TABLE = f"{{{NS['table']}}}table"
TAG_ROW = f"{{{NS['table']}}}table-row"
TAG_CELL = f"{{{NS['table']}}}table-cell"
TAG_COVERED_CELL = f"{{{NS['table']}}}covered-table-cell"
TAG_P = f"{{{NS['text']}}}p"
TAG_A = f"{{{NS['text']}}}a"

ATTR_NAME = f"{{{NS['table']}}}name"
ATTR_REPEAT_COL = f"{{{NS['table']}}}number-columns-repeated"
ATTR_REPEAT_ROW = f"{{{NS['table']}}}number-rows-repeated"
ATTR_FORMULA = f"{{{NS['table']}}}formula"


def _snake_case(name: str) -> str:
    """Convert ODS header like 'Most Recent Full: Inspection Date' to snake_case."""
    s = name.strip()
    s = re.sub(r"[^a-zA-Z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_").lower()
    return s


def _cell_text(cell_elem) -> str:
    """Extract all text from <text:p> children of a cell element."""
    parts = []
    for p in cell_elem.iter(TAG_P):
        # Collect text from the <p> and any <a> children
        text = p.text or ""
        for child in p:
            if child.text:
                text += child.text
            if child.tail:
                text += child.tail
        if p.tail:
            text += p.tail
        parts.append(text.strip())
    return " ".join(parts).strip()


def _extract_url(cell_elem) -> str | None:
    """Extract URL from a cell's table:formula attribute (HYPERLINK formula)."""
    formula = cell_elem.get(ATTR_FORMULA)
    if not formula:
        return None
    match = re.search(r'HYPERLINK\("([^"]+)"', formula)
    if match:
        return match.group(1).strip()
    return None


def _expand_row_cells(row_elem) -> list:
    """Expand cells with number-columns-repeated into a flat list of (cell_elem) entries."""
    cells = []
    for child in row_elem:
        if child.tag not in (TAG_CELL, TAG_COVERED_CELL):
            continue
        repeat_str = child.get(ATTR_REPEAT_COL)
        n = int(repeat_str) if repeat_str else 1
        # Skip massive trailing empty blocks
        if n > 100:
            break
        for _ in range(n):
            cells.append(child)
    return cells


def _build_create_table_sql(columns: list[str]) -> str:
    col_defs = ",\n    ".join(f"{col} TEXT" for col in columns)
    return f"""
    CREATE TABLE IF NOT EXISTS ofsted.inspections (
        {col_defs},
        PRIMARY KEY (provider_urn)
    )
    """


def _iter_rows_streaming(ods_path: Path, sheet_name: str):
    """Stream rows from an ODS file without loading the full DOM.

    Yields (row_index_in_sheet, list_of_cell_elements) for each row
    in the target sheet.
    """
    with zipfile.ZipFile(ods_path) as zf:
        with zf.open("content.xml") as f:
            in_target_sheet = False
            row_index = 0

            for event, elem in iterparse(f, events=("start", "end")):
                if event == "start" and elem.tag == TAG_TABLE:
                    name = elem.get(ATTR_NAME)
                    in_target_sheet = name == sheet_name
                    if in_target_sheet:
                        row_index = 0

                elif event == "end" and elem.tag == TAG_TABLE:
                    if in_target_sheet:
                        return
                    # Free memory from non-target sheets
                    elem.clear()

                elif event == "end" and elem.tag == TAG_ROW and in_target_sheet:
                    repeat_str = elem.get(ATTR_REPEAT_ROW)
                    row_repeat = int(repeat_str) if repeat_str else 1

                    # Only yield non-massively-repeated rows (trailing empties)
                    if row_repeat > 100:
                        row_index += row_repeat
                        elem.clear()
                        continue

                    for _ in range(row_repeat):
                        yield row_index, elem
                        row_index += 1

                    # Free memory after processing
                    elem.clear()


@asset(group_name="ofsted", deps=["ofsted_inspections_table"])
def ofsted_inspections(
    context: AssetExecutionContext, bsil_postgres: BsilPostgresResource
):
    """Load Ofsted inspection data from ODS file into ofsted.inspections table.

    Uses streaming XML parsing to avoid loading the full DOM into memory.
    Idempotent: truncates and reloads all rows on each run.
    """
    context.log.info(f"Loading ODS file: {ODS_PATH}")

    columns = None
    num_cols = 0
    insert_sql = None
    row_count = 0
    batch = []

    with bsil_postgres.get_connection() as conn:
        with conn.cursor() as cur:
            for row_idx, row_elem in _iter_rows_streaming(ODS_PATH, SHEET_NAME):
                # Skip title rows (0, 1)
                if row_idx < HEADER_ROW_INDEX:
                    continue

                cells = _expand_row_cells(row_elem)

                # Header row — define columns and create table
                if row_idx == HEADER_ROW_INDEX:
                    raw_headers = [_cell_text(c) for c in cells]
                    columns = ["web_link"] + [
                        _snake_case(h) for h in raw_headers[1:] if h
                    ]
                    num_cols = len(columns)
                    context.log.info(
                        f"Detected {num_cols} columns: {columns[:5]}...{columns[-3:]}"
                    )

                    cur.execute(_build_create_table_sql(columns))
                    cur.execute("TRUNCATE ofsted.inspections")

                    placeholders = ", ".join(f"%({c})s" for c in columns)
                    col_names = ", ".join(columns)
                    insert_sql = (
                        f"INSERT INTO ofsted.inspections ({col_names}) "  # nosec B608
                        f"VALUES ({placeholders})"
                    )
                    continue

                # Data rows
                if len(cells) < 2:
                    continue

                row_data = {}
                row_data["web_link"] = _extract_url(cells[0]) if cells else None

                for col_idx in range(1, num_cols):
                    if col_idx < len(cells):
                        row_data[columns[col_idx]] = _cell_text(cells[col_idx]) or None
                    else:
                        row_data[columns[col_idx]] = None

                batch.append(row_data)

                if len(batch) >= 1000:
                    cur.executemany(insert_sql, batch)
                    row_count += len(batch)
                    batch = []
                    if row_count % 10000 == 0:
                        context.log.info(f"Inserted {row_count} rows so far...")

            if batch:
                cur.executemany(insert_sql, batch)
                row_count += len(batch)

        conn.commit()

    context.log.info(f"Loaded {row_count} rows into ofsted.inspections")
    return {"row_count": MetadataValue.int(row_count)}
