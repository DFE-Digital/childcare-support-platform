"""Generate a bounding-box lookup SQLite file from OS open-data products.

Reads two OS OpenData products (mounted via source_data/):
  1. CodePoint with Polygons (Shapefiles in a zip) — per-postcode polygon
     bboxes, aggregated into postcode-district bboxes.
  2. Boundary-Line (GeoPackage) — district/unitary authority polygon bboxes
     and county polygon bboxes.

Both are EPSG:27700 (British National Grid). BNG bbox corners are converted
to WGS84 (EPSG:4326) via pyproj.

Output: data/bbox_lookup.sqlite with four tables (postcode_bbox,
district_bbox, la_bbox, county_bbox).
"""

import glob
import io
import os
import re
import sqlite3
import zipfile
from pathlib import Path

from dagster import asset, AssetExecutionContext, MetadataValue

import shapefile
from pyproj import Transformer

_SOURCE_DATA = Path(__file__).resolve().parent.parent.parent / "source_data"
_DEFAULT_OUTPUT = (
    Path(__file__).resolve().parent.parent.parent / "data" / "bbox_lookup.sqlite"
)

# BNG → WGS84 transformer (always_xy = easting,northing → lon,lat)
_transformer = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)


def _bng_bbox_to_wgs84(minx, maxx, miny, maxy):
    """Convert a BNG bounding box to WGS84, returning (north, south, east, west).

    Transforms all four corners and takes the new envelope because BNG→WGS84
    is not axis-aligned.
    """
    corners_x = [minx, minx, maxx, maxx]
    corners_y = [miny, maxy, miny, maxy]
    lons, lats = _transformer.transform(corners_x, corners_y)
    return max(lats), min(lats), max(lons), min(lons)


def _outward_code(postcode: str) -> str | None:
    """Extract the outward (district) code, e.g. 'SW1A 1AA' → 'SW1A'."""
    pc = postcode.strip().upper()
    if " " in pc:
        return pc.split()[0]
    if len(pc) >= 5:
        return pc[:-3].strip()
    return None


def _find_file(directory: str, extension: str) -> Path | None:
    """Find the first file with the given extension in a directory (recursive)."""
    pattern = os.path.join(directory, "**", f"*{extension}")
    matches = glob.glob(pattern, recursive=True)
    return Path(matches[0]) if matches else None


# ---------- CodePoint with Polygons (zipped Shapefiles) ----------


def _process_codepoint(codepoint_dir: Path, out_conn: sqlite3.Connection, log):
    """Read CodePoint with Polygons Shapefiles → postcode_bbox + district_bbox.

    OS distributes CodePoint with Polygons as a single zip containing
    120 Shapefiles (one per postcode area, e.g. AB.shp, SW.shp).
    Each Shapefile has fields: POSTCODE, UPP, PC_AREA.
    """
    zip_path = _find_file(str(codepoint_dir), ".zip")
    if not zip_path:
        log.error(f"No .zip file found in {codepoint_dir}")
        return 0, 0

    log.info(f"Reading CodePoint Shapefiles from: {zip_path}")
    zf = zipfile.ZipFile(str(zip_path))

    shp_names = sorted(n for n in zf.namelist() if n.endswith(".shp"))
    log.info(f"  Found {len(shp_names)} shapefiles in zip")

    district_agg = {}
    postcode_count = 0
    out_conn.execute("BEGIN")

    for shp_name in shp_names:
        stem = shp_name[:-4]  # e.g. "AB"
        dbf_name = stem + ".dbf"
        shx_name = stem + ".shx"

        if dbf_name not in zf.namelist() or shx_name not in zf.namelist():
            log.warning(f"  Skipping {shp_name} — missing .dbf or .shx")
            continue

        sf = shapefile.Reader(
            shp=io.BytesIO(zf.read(shp_name)),
            dbf=io.BytesIO(zf.read(dbf_name)),
            shx=io.BytesIO(zf.read(shx_name)),
        )

        # Find the POSTCODE field index
        field_names = [f.name for f in sf.fields[1:]]  # skip DeletionFlag
        try:
            pc_idx = field_names.index("POSTCODE")
        except ValueError:
            # Fallback: first field
            pc_idx = 0

        for shape_rec in sf.iterShapeRecords():
            pc_raw = shape_rec.record[pc_idx]
            if not pc_raw:
                continue
            pc = pc_raw.strip().upper()
            if not pc:
                continue

            bbox = shape_rec.shape.bbox  # (minx, miny, maxx, maxy)
            minx, miny, maxx, maxy = bbox
            north, south, east, west = _bng_bbox_to_wgs84(minx, maxx, miny, maxy)

            out_conn.execute(
                """INSERT OR REPLACE INTO postcode_bbox
                   (geo_code, geo_name, bbox_north, bbox_south, bbox_east, bbox_west, postcode_count)
                   VALUES (?, ?, ?, ?, ?, ?, 1)""",
                (pc, pc, north, south, east, west),
            )
            postcode_count += 1

            oc = _outward_code(pc)
            if oc:
                if oc not in district_agg:
                    district_agg[oc] = {
                        "north": north,
                        "south": south,
                        "east": east,
                        "west": west,
                        "count": 1,
                    }
                else:
                    d = district_agg[oc]
                    d["north"] = max(d["north"], north)
                    d["south"] = min(d["south"], south)
                    d["east"] = max(d["east"], east)
                    d["west"] = min(d["west"], west)
                    d["count"] += 1

        if postcode_count % 100_000 == 0 and postcode_count > 0:
            log.info(f"  Progress: {postcode_count} postcodes processed...")

    out_conn.execute("COMMIT")
    log.info(f"  Inserted {postcode_count} postcode bboxes")

    out_conn.execute("BEGIN")
    for oc, d in district_agg.items():
        out_conn.execute(
            """INSERT OR REPLACE INTO district_bbox
               (geo_code, geo_name, bbox_north, bbox_south, bbox_east, bbox_west, postcode_count)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (oc, oc, d["north"], d["south"], d["east"], d["west"], d["count"]),
        )
    out_conn.execute("COMMIT")
    log.info(f"  Inserted {len(district_agg)} district bboxes")

    zf.close()
    return postcode_count, len(district_agg)


# ---------- Boundary-Line (GeoPackage) ----------


def _discover_layer(gpkg_conn, hint_substring: str):
    """Find a spatial layer whose name contains hint_substring (case-insensitive)."""
    rows = gpkg_conn.execute(
        "SELECT table_name FROM gpkg_contents WHERE data_type = 'features'"
    ).fetchall()
    for (tbl,) in rows:
        if hint_substring.lower() in tbl.lower():
            geom_cols = gpkg_conn.execute(
                "SELECT column_name FROM gpkg_geometry_columns WHERE table_name = ?",
                (tbl,),
            ).fetchall()
            if geom_cols:
                return tbl, geom_cols[0][0]
    return None


def _find_layer(gpkg_conn, hints: list[str]):
    """Try multiple hint substrings in order; fall back to first feature layer."""
    for hint in hints:
        result = _discover_layer(gpkg_conn, hint)
        if result:
            return result
    rows = gpkg_conn.execute(
        "SELECT table_name FROM gpkg_contents WHERE data_type = 'features'"
    ).fetchall()
    if rows:
        tbl = rows[0][0]
        geom_cols = gpkg_conn.execute(
            "SELECT column_name FROM gpkg_geometry_columns WHERE table_name = ?",
            (tbl,),
        ).fetchall()
        if geom_cols:
            return tbl, geom_cols[0][0]
    return None


def _find_column(col_info, candidates: list[str]) -> str | None:
    """Find a column whose name (lowercased) matches one of the candidates."""
    col_names = {c[1].lower(): c[1] for c in col_info}
    for candidate in candidates:
        if candidate in col_names:
            return col_names[candidate]
    return None


def _find_pk(col_info) -> str | None:
    """Find the primary key column from PRAGMA table_info results."""
    for c in col_info:
        if c[5] == 1:
            return c[1]
    return None


def _process_boundary_line(boundary_dir: Path, out_conn: sqlite3.Connection, log):
    """Read Boundary-Line GeoPackage → la_bbox table."""
    gpkg_path = _find_file(str(boundary_dir), ".gpkg")
    if not gpkg_path:
        log.error(f"No .gpkg file found in {boundary_dir}")
        return 0

    log.info(f"Reading Boundary-Line from: {gpkg_path}")
    gpkg = sqlite3.connect(str(gpkg_path))

    layers = gpkg.execute(
        "SELECT table_name FROM gpkg_contents WHERE data_type = 'features'"
    ).fetchall()
    log.info(f"  Available layers: {[row[0] for row in layers]}")

    layer = _find_layer(
        gpkg,
        [
            "district_borough_unitary",
            "district",
            "unitary",
            "local_authority",
        ],
    )
    if not layer:
        log.error("Could not find district/unitary layer in Boundary-Line GeoPackage")
        gpkg.close()
        return 0

    table_name, geom_col = layer
    log.info(f"  Layer: {table_name} (geom: {geom_col})")

    rtree_table = f"rtree_{table_name}_{geom_col}"
    col_info = gpkg.execute(f"PRAGMA table_info({table_name})").fetchall()
    log.info(f"  Columns: {[c[1] for c in col_info]}")

    code_col = _find_column(
        col_info,
        [
            "census_code",
            "ons_code",
            "gss_code",
            "lad_code",
            "code",
        ],
    )
    if not code_col:
        for c in col_info:
            if c[2].upper() in ("TEXT", "VARCHAR"):
                sample = gpkg.execute(
                    f"SELECT {c[1]} FROM {table_name} LIMIT 5"  # nosec B608
                ).fetchall()
                if any(
                    s[0] and re.match(r"^[ESNW]\d{8}$", str(s[0]).strip())
                    for s in sample
                    if s[0]
                ):
                    code_col = c[1]
                    break

    name_col = _find_column(col_info, ["name", "area_name", "lad_name"])

    if not code_col:
        log.error(f"Could not find area code column in {table_name}")
        gpkg.close()
        return 0

    log.info(f"  Code column: {code_col}, Name column: {name_col}")

    pk_col = _find_pk(col_info)
    join_col = f"f.{pk_col}" if pk_col else "f.rowid"
    name_select = f", f.{name_col}" if name_col else ""

    query = (
        f"SELECT f.{code_col}{name_select}, r.minx, r.maxx, r.miny, r.maxy"  # nosec B608
        f" FROM {table_name} f"
        f" JOIN {rtree_table} r ON {join_col} = r.id"
    )

    rows = gpkg.execute(query).fetchall()
    log.info(f"  Found {len(rows)} boundary polygons")

    out_conn.execute("BEGIN")
    la_count = 0
    for row in rows:
        if name_col:
            code, name, minx, maxx, miny, maxy = row
        else:
            code, minx, maxx, miny, maxy = row
            name = None

        if not code or not minx:
            continue
        code = str(code).strip()
        if not re.match(r"^[ESNW]\d{8}$", code):
            continue

        north, south, east, west = _bng_bbox_to_wgs84(minx, maxx, miny, maxy)

        out_conn.execute(
            """INSERT OR REPLACE INTO la_bbox
               (geo_code, geo_name, bbox_north, bbox_south, bbox_east, bbox_west, postcode_count)
               VALUES (?, ?, ?, ?, ?, ?, 0)""",
            (code, name, north, south, east, west),
        )
        la_count += 1

    out_conn.execute("COMMIT")
    log.info(f"  Inserted {la_count} LA bboxes")

    gpkg.close()
    return la_count


def _process_county_layer(boundary_dir: Path, out_conn: sqlite3.Connection, log):
    """Read Boundary-Line GeoPackage county layer → county_bbox table."""
    gpkg_path = _find_file(str(boundary_dir), ".gpkg")
    if not gpkg_path:
        log.error(f"No .gpkg file found in {boundary_dir}")
        return 0

    log.info(f"Reading county layer from: {gpkg_path}")
    gpkg = sqlite3.connect(str(gpkg_path))

    layer = _find_layer(gpkg, ["county"])
    if not layer:
        log.warning(
            "Could not find county layer in Boundary-Line GeoPackage — skipping"
        )
        gpkg.close()
        return 0

    table_name, geom_col = layer
    log.info(f"  County layer: {table_name} (geom: {geom_col})")

    rtree_table = f"rtree_{table_name}_{geom_col}"
    col_info = gpkg.execute(f"PRAGMA table_info({table_name})").fetchall()
    log.info(f"  Columns: {[c[1] for c in col_info]}")

    code_col = _find_column(
        col_info,
        [
            "census_code",
            "ons_code",
            "gss_code",
            "code",
        ],
    )
    if not code_col:
        for c in col_info:
            if c[2].upper() in ("TEXT", "VARCHAR"):
                sample = gpkg.execute(
                    f"SELECT {c[1]} FROM {table_name} LIMIT 5"  # nosec B608
                ).fetchall()
                if any(
                    s[0] and re.match(r"^[ESNW]\d{8}$", str(s[0]).strip())
                    for s in sample
                    if s[0]
                ):
                    code_col = c[1]
                    break

    name_col = _find_column(col_info, ["name", "area_name"])

    if not code_col:
        log.error(f"Could not find area code column in {table_name}")
        gpkg.close()
        return 0

    log.info(f"  Code column: {code_col}, Name column: {name_col}")

    pk_col = _find_pk(col_info)
    join_col = f"f.{pk_col}" if pk_col else "f.rowid"
    name_select = f", f.{name_col}" if name_col else ""

    query = (
        f"SELECT f.{code_col}{name_select}, r.minx, r.maxx, r.miny, r.maxy"  # nosec B608
        f" FROM {table_name} f"
        f" JOIN {rtree_table} r ON {join_col} = r.id"
    )

    rows = gpkg.execute(query).fetchall()
    log.info(f"  Found {len(rows)} county polygons")

    out_conn.execute("BEGIN")
    county_count = 0
    for row in rows:
        if name_col:
            code, name, minx, maxx, miny, maxy = row
        else:
            code, minx, maxx, miny, maxy = row
            name = None

        if not code or not minx:
            continue
        code = str(code).strip()
        if not re.match(r"^[ESNW]\d{8}$", code):
            continue

        north, south, east, west = _bng_bbox_to_wgs84(minx, maxx, miny, maxy)

        out_conn.execute(
            """INSERT OR REPLACE INTO county_bbox
               (geo_code, geo_name, bbox_north, bbox_south, bbox_east, bbox_west, postcode_count)
               VALUES (?, ?, ?, ?, ?, ?, 0)""",
            (code, name, north, south, east, west),
        )
        county_count += 1

    out_conn.execute("COMMIT")
    log.info(f"  Inserted {county_count} county bboxes")

    gpkg.close()
    return county_count


# ---------- Asset ----------


@asset(group_name="os")
def bbox_lookup(context: AssetExecutionContext):
    """Generate bbox_lookup.sqlite from OS CodePoint Shapefiles + Boundary-Line GeoPackage.

    Reads source data from source_data/ (mounted into the container),
    converts BNG bounding boxes to WGS84, and writes a SQLite lookup file
    to data/bbox_lookup.sqlite.

    Source data must be downloaded manually from OS Data Hub:
      - CodePoint with Polygons (Shapefile) → source_data/codepoint-poly/
      - Boundary-Line (GeoPackage) → source_data/boundary-line/
    """
    source_dir = Path(os.environ.get("SOURCE_DATA_PATH", str(_SOURCE_DATA)))
    output_path = Path(os.environ.get("BBOX_LOOKUP_PATH", str(_DEFAULT_OUTPUT)))

    codepoint_dir = source_dir / "codepoint-poly"
    boundary_dir = source_dir / "boundary-line"

    # Verify source data exists
    codepoint_zip = _find_file(str(codepoint_dir), ".zip")
    boundary_gpkg = _find_file(str(boundary_dir), ".gpkg")

    if not codepoint_zip:
        context.log.error(
            f"No .zip file found in {codepoint_dir} — "
            "download CodePoint with Polygons (Shapefile) from "
            "https://osdatahub.os.uk/downloads/open/CodePointPolygons"
        )
        return {
            "error": MetadataValue.text(f"CodePoint zip not found in {codepoint_dir}")
        }

    if not boundary_gpkg:
        context.log.error(
            f"No .gpkg file found in {boundary_dir} — "
            "download Boundary-Line (GeoPackage) from "
            "https://osdatahub.os.uk/downloads/open/BoundaryLine"
        )
        return {
            "error": MetadataValue.text(
                f"Boundary-Line GeoPackage not found in {boundary_dir}"
            )
        }

    # Remove existing output to start fresh
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    out_conn = sqlite3.connect(str(output_path))

    for table in ("postcode_bbox", "district_bbox", "la_bbox", "county_bbox"):
        out_conn.execute(f"""
            CREATE TABLE {table} (
                geo_code TEXT PRIMARY KEY,
                geo_name TEXT,
                bbox_north REAL NOT NULL,
                bbox_south REAL NOT NULL,
                bbox_east REAL NOT NULL,
                bbox_west REAL NOT NULL,
                postcode_count INTEGER NOT NULL DEFAULT 1
            )
        """)

    postcode_count, district_count = _process_codepoint(
        codepoint_dir, out_conn, context.log
    )
    la_count = _process_boundary_line(boundary_dir, out_conn, context.log)
    county_count = _process_county_layer(boundary_dir, out_conn, context.log)

    out_conn.close()

    size_mb = output_path.stat().st_size / 1024 / 1024
    context.log.info(
        f"bbox_lookup.sqlite written: {size_mb:.1f} MB "
        f"({postcode_count} postcodes, {district_count} districts, "
        f"{la_count} LAs, {county_count} counties)"
    )

    return {
        "postcodes": MetadataValue.int(postcode_count),
        "districts": MetadataValue.int(district_count),
        "local_authorities": MetadataValue.int(la_count),
        "counties": MetadataValue.int(county_count),
        "file_size_mb": MetadataValue.float(round(size_mb, 1)),
    }
