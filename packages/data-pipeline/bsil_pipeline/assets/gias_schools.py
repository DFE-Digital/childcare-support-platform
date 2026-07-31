"""Load GIAS (Get Information About Schools) establishment data into dfe.gias_schools.

Source: https://get-information-schools.service.gov.uk/Downloads
Expected file: source_data/gias_establishments.csv (user downloads and renames).

Loads a whitelist of columns needed for school linkage (address, type, status).
"""

import csv
from pathlib import Path

from dagster import asset, AssetExecutionContext, MetadataValue
from pyproj import Transformer

from bsil_pipeline.resources.postgres import BsilPostgresResource
from bsil_pipeline.assets.schema_tables import DFE_GIAS_SCHOOLS_DDL

_BNGWGS84 = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)

CSV_PATH = Path("/opt/dagster/app/source_data/gias_establishments.csv")

BATCH_SIZE = 1000

# Whitelist of columns to load (GIAS CSV has 120+ columns)
_COLUMNS = {
    "URN": "urn",
    "EstablishmentName": "establishment_name",
    "Street": "street",
    "Locality": "locality",
    "Address3": "address3",
    "Town": "town",
    "County (name)": "county",
    "Postcode": "postcode",
    "Easting": "easting",
    "Northing": "northing",
    "EstablishmentTypeGroup (name)": "establishment_type_group",
    "PhaseOfEducation (name)": "phase_of_education",
    "EstablishmentStatus (name)": "establishment_status",
    "TelephoneNum": "telephone_num",
    "SchoolWebsite": "school_website",
    "StatutoryLowAge": "statutory_low_age",
    "StatutoryHighAge": "statutory_high_age",
    "NurseryProvision (name)": "nursery_provision",
    "NumberOfPupils": "number_of_pupils",
    "ReligiousCharacter (name)": "religious_character",
}

CREATE_SQL = DFE_GIAS_SCHOOLS_DDL

_PG_COLS = list(_COLUMNS.values())
_INSERT_COLS = _PG_COLS + ["latitude", "longitude"]
_col_names = ", ".join(_INSERT_COLS)
_placeholders = ", ".join(f"%({c})s" for c in _INSERT_COLS)
INSERT_SQL = f"INSERT INTO dfe.gias_schools ({_col_names}) VALUES ({_placeholders})"  # nosec B608


def _open_csv(path: Path):
    """Open GIAS CSV with encoding detection (utf-8-sig preferred, cp1252 fallback)."""
    try:
        f = open(path, "r", encoding="utf-8-sig")  # noqa: SIM115
        f.readline()  # test read
        f.seek(0)
        return f
    except UnicodeDecodeError:
        return open(path, "r", encoding="cp1252")  # noqa: SIM115


@asset(group_name="dfe", deps=["dfe_gias_schools_table"])
def gias_schools(context: AssetExecutionContext, bsil_postgres: BsilPostgresResource):
    """Load GIAS establishment CSV into dfe.gias_schools.

    Whitelist of columns loaded as TEXT. Idempotent: DROP + recreate.
    """
    if not CSV_PATH.exists():
        context.log.error(f"CSV not found: {CSV_PATH}")
        return {"error": MetadataValue.text(f"CSV not found: {CSV_PATH}")}

    # Discover column positions from header
    with _open_csv(CSV_PATH) as f:
        reader = csv.reader(f)
        raw_headers = next(reader)

    header_map: dict[int, str] = {}  # CSV column index → pg column name
    for i, h in enumerate(raw_headers):
        h_stripped = h.strip()
        if h_stripped in _COLUMNS:
            header_map[i] = _COLUMNS[h_stripped]

    missing = set(_COLUMNS.keys()) - {raw_headers[i].strip() for i in header_map}
    if missing:
        context.log.warning(f"GIAS CSV missing expected columns: {missing}")

    context.log.info(
        f"GIAS CSV: {len(raw_headers)} columns total, "
        f"{len(header_map)} matched to whitelist"
    )

    row_count = 0
    with bsil_postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS dfe.gias_schools")
            cur.execute(CREATE_SQL)
        conn.commit()

        with _open_csv(CSV_PATH) as f:
            reader = csv.reader(f)
            next(reader)  # skip header

            batch: list[dict] = []
            with conn.cursor() as cur:
                for raw_row in reader:
                    row_data = {}
                    for i, pg_col in header_map.items():
                        val = raw_row[i].strip() if i < len(raw_row) else None
                        row_data[pg_col] = val if val else None
                    try:
                        east = float(row_data.get("easting") or "")
                        north = float(row_data.get("northing") or "")
                        lon, lat = _BNGWGS84.transform(east, north)
                        row_data["latitude"] = round(lat, 6)
                        row_data["longitude"] = round(lon, 6)
                    except (ValueError, TypeError):
                        row_data["latitude"] = None
                        row_data["longitude"] = None
                    batch.append(row_data)

                    if len(batch) >= BATCH_SIZE:
                        cur.executemany(INSERT_SQL, batch)
                        row_count += len(batch)
                        batch = []
                        if row_count % 10000 == 0:
                            context.log.info(f"Inserted {row_count} rows...")

                if batch:
                    cur.executemany(INSERT_SQL, batch)
                    row_count += len(batch)

        conn.commit()

    context.log.info(f"Loaded {row_count} rows into dfe.gias_schools")
    return {"row_count": MetadataValue.int(row_count)}
