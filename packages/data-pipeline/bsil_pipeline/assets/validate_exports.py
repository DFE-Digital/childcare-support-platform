"""Post-export validation: checks consistency across provider JSONs,
spatial index parquet, vector tiles, LAD statistics, postcode autocomplete,
and LA boundaries.
"""

import json
import subprocess  # nosec B404
from pathlib import Path

import pyarrow.parquet as pq
from dagster import asset, AssetExecutionContext, Config, Failure, MetadataValue

from bsil_pipeline.automation import PIPELINE_CONDITION
from bsil_pipeline.resources.postgres import BsilPostgresResource


class ValidateExportsConfig(Config):
    output_dir: str = "/opt/dagster/app/output/app"


def _collect_json_ids(output_dir: Path) -> tuple[set[int], set[int], set[int]]:
    """Return (all_ids, point_ids, bbox_ids) from provider JSON files."""
    providers_dir = output_dir / "providers"
    all_ids: set[int] = set()
    point_ids: set[int] = set()
    bbox_ids: set[int] = set()
    for path in providers_dir.glob("p*.json"):
        stem = path.stem
        try:
            pid = int(stem[1:])
        except ValueError:
            continue
        all_ids.add(pid)
        with open(path) as f:
            data = json.load(f)
        if data.get("latitude") is not None:
            point_ids.add(pid)
        else:
            bbox_ids.add(pid)
    return all_ids, point_ids, bbox_ids


def _collect_sis_ids(output_dir: Path) -> tuple[set[int], set[int], set[int]]:
    """Return (all_ids, point_ids, bbox_ids) from spatial_index.parquet."""
    parquet_path = output_dir / "spatial_index.parquet"
    table = pq.read_table(str(parquet_path), columns=["provider_id", "bbox_lat"])
    provider_ids = table.column("provider_id").to_pylist()
    bbox_lats = table.column("bbox_lat").to_pylist()

    all_ids: set[int] = set()
    point_ids: set[int] = set()
    bbox_ids: set[int] = set()
    for pid, bbox_lat in zip(provider_ids, bbox_lats):
        all_ids.add(pid)
        if bbox_lat is not None:
            bbox_ids.add(pid)
        else:
            point_ids.add(pid)
    return all_ids, point_ids, bbox_ids


def _collect_tile_ids(output_dir: Path) -> set[int]:
    """Decode PMTiles and extract all provider IDs from tile features."""
    tiles_path = output_dir / "tiles" / "providers.pmtiles"
    result = subprocess.run(  # nosec B603 B607
        ["tippecanoe-decode", str(tiles_path), "--layer=providers"],
        capture_output=True,
        text=True,
        check=True,
    )
    geojson = json.loads(result.stdout)

    tile_ids: set[int] = set()

    def _extract_from_feature(feature: dict) -> None:
        props = feature.get("properties", {})
        count = props.get("count", 1)
        if count == 1:
            pid_str = props.get("id", "")
            if isinstance(pid_str, str) and pid_str.startswith("p"):
                try:
                    tile_ids.add(int(pid_str[1:]))
                except ValueError:
                    pass
        else:
            providers_json = props.get("providers")
            if providers_json:
                for sub in json.loads(providers_json):
                    pid_str = sub.get("id", "")
                    if isinstance(pid_str, str) and pid_str.startswith("p"):
                        try:
                            tile_ids.add(int(pid_str[1:]))
                        except ValueError:
                            pass

    # tippecanoe-decode outputs nested FeatureCollections:
    # top → per-tile → per-layer → actual features
    for tile_fc in geojson.get("features", []):
        for layer_fc in tile_fc.get("features", []):
            for feature in layer_fc.get("features", []):
                _extract_from_feature(feature)

    return tile_ids


def _check(
    name: str,
    a: set,
    b: set,
    severity: str,
    context: AssetExecutionContext,
) -> dict:
    diff = a - b
    status = "PASS" if len(diff) == 0 else severity
    sample = sorted(diff)[:10]
    if diff:
        msg = f"[{status}] {name}: {len(diff)} mismatches (sample: {sample})"
        if severity == "FAIL":
            context.log.error(msg)
        else:
            context.log.warning(msg)
    else:
        msg = f"[PASS] {name}: OK"
        context.log.info(msg)
    return {"name": name, "status": status, "count": len(diff), "sample": sample}


def _validate_lad_files(
    output_dir: Path, conn, context: AssetExecutionContext
) -> list[dict]:
    """Validate LAD statistics files against published DB state."""
    checks: list[dict] = []
    lad_dir = output_dir / "lad"

    if not lad_dir.exists():
        checks.append(
            {"name": "LAD dir exists", "status": "FAIL", "count": 1, "sample": []}
        )
        return checks

    lad_files = {p.stem: p for p in lad_dir.glob("*.json")}
    context.log.info(f"Found {len(lad_files)} LAD files")

    with conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT lad25cd FROM published.providers "
            "WHERE NOT is_insufficient AND lad25cd IS NOT NULL"
        )
        expected_codes = {row[0] for row in cur.fetchall()}

    missing = expected_codes - set(lad_files.keys())
    checks.append(
        _check("LAD files cover all provider LAs", missing, set(), "WARN", context)
    )

    # Validate providerStats per-care-type totals against DB
    with conn.cursor() as cur:
        cur.execute(
            "SELECT p.lad25cd, ct.care_type, COUNT(DISTINCT p.id) "
            "FROM published.providers p "
            "JOIN published.care_types ct ON ct.provider_id = p.id "
            "WHERE NOT p.is_insufficient AND p.lad25cd IS NOT NULL "
            "GROUP BY p.lad25cd, ct.care_type"
        )
        db_stats: dict[str, dict[str, int]] = {}
        for lad25cd, care_type, count in cur.fetchall():
            db_stats.setdefault(lad25cd, {})[care_type] = count

    mismatched: set[str] = set()
    for code in sorted(expected_codes & set(lad_files.keys())):
        with open(lad_files[code]) as f:
            lad_json = json.load(f)
        file_stats = lad_json.get("providerStats", {})
        db_la_stats = db_stats.get(code, {})

        for care_type, db_count in db_la_stats.items():
            file_count = file_stats.get(care_type, {}).get("total", 0)
            if file_count != db_count:
                mismatched.add(code)
                break

    status = "FAIL" if mismatched else "PASS"
    sample = sorted(mismatched)[:10]
    if mismatched:
        context.log.error(
            f"[FAIL] LAD providerStats match DB: {len(mismatched)} mismatches "
            f"(sample: {sample})"
        )
    else:
        context.log.info("[PASS] LAD providerStats match DB: OK")
    checks.append(
        {
            "name": "LAD providerStats match DB",
            "status": status,
            "count": len(mismatched),
            "sample": sample,
        }
    )

    # Validate laBounds presence
    missing_bounds: set[str] = set()
    for code in sorted(expected_codes & set(lad_files.keys())):
        with open(lad_files[code]) as f:
            lad_json = json.load(f)
        if "laBounds" not in lad_json:
            missing_bounds.add(code)

    checks.append(
        _check("LAD files have laBounds", missing_bounds, set(), "WARN", context)
    )

    return checks


def _validate_postcode_files(
    output_dir: Path, context: AssetExecutionContext
) -> list[dict]:
    """Validate postcode autocomplete export files."""
    checks: list[dict] = []
    outward_path = output_dir / "outward.json"
    inward_dir = output_dir / "inward"

    if not outward_path.exists():
        checks.append(
            {
                "name": "outward.json exists",
                "status": "FAIL",
                "count": 1,
                "sample": [],
            }
        )
        return checks

    outward_codes = json.loads(outward_path.read_text())
    non_empty = len(outward_codes) > 0
    checks.append(
        {
            "name": "outward.json non-empty",
            "status": "PASS" if non_empty else "FAIL",
            "count": 0 if non_empty else 1,
            "sample": [],
        }
    )
    if non_empty:
        context.log.info(f"outward.json: {len(outward_codes)} codes")

    if not inward_dir.exists():
        checks.append(
            {
                "name": "inward/ dir exists",
                "status": "FAIL",
                "count": 1,
                "sample": [],
            }
        )
        return checks

    missing_inward: set[str] = set()
    for code in outward_codes:
        if not (inward_dir / f"{code}.json").exists():
            missing_inward.add(code)

    checks.append(
        _check(
            "Inward files for all outward codes", missing_inward, set(), "FAIL", context
        )
    )

    # Spot-check structure of first few inward files
    malformed: set[str] = set()
    for code in outward_codes[:5]:
        inward_path = inward_dir / f"{code}.json"
        if not inward_path.exists():
            continue
        data = json.loads(inward_path.read_text())
        for key, entry in data.items():
            if key == "_":
                continue
            if not isinstance(entry, dict):
                malformed.add(code)
                break
            if "b" not in entry or "c" not in entry:
                malformed.add(code)
                break
            if len(entry["b"]) != 4 or len(entry["c"]) != 2:
                malformed.add(code)
                break
            break  # only check first entry per file

    checks.append(
        _check("Inward file structure valid", malformed, set(), "FAIL", context)
    )

    return checks


def _validate_la_boundaries(
    output_dir: Path, context: AssetExecutionContext
) -> list[dict]:
    """Validate LA boundaries GeoJSON export."""
    checks: list[dict] = []
    geojson_path = output_dir.parent / "la_boundaries.geojson"

    if not geojson_path.exists():
        checks.append(
            {
                "name": "la_boundaries.geojson exists",
                "status": "WARN",
                "count": 1,
                "sample": [],
            }
        )
        context.log.warning("[WARN] la_boundaries.geojson not found")
        return checks

    data = json.loads(geojson_path.read_text())
    features = data.get("features", [])

    non_empty = len(features) > 0
    checks.append(
        {
            "name": "LA boundaries non-empty",
            "status": "PASS" if non_empty else "WARN",
            "count": 0 if non_empty else 1,
            "sample": [],
        }
    )
    if non_empty:
        context.log.info(f"la_boundaries.geojson: {len(features)} features")

    # Check properties on all features
    missing_props: set[str] = set()
    for feature in features:
        props = feature.get("properties", {})
        code = props.get("LAD25CD", "")
        if not props.get("LAD25CD") or not props.get("LAD25NM"):
            missing_props.add(code or "unknown")
        if not feature.get("geometry"):
            missing_props.add(code or "unknown")

    checks.append(
        _check(
            "LA boundary features have properties + geometry",
            missing_props,
            set(),
            "WARN",
            context,
        )
    )

    return checks


@asset(
    group_name="publish",
    deps=[
        "export_providers",
        "export_spatial_index",
        "vector_tiles",
        "export_costs",
        "postcode_autocomplete",
        "la_boundaries",
    ],
    automation_condition=PIPELINE_CONDITION,
)
def validate_exports(
    context: AssetExecutionContext,
    config: ValidateExportsConfig,
    bsil_postgres: BsilPostgresResource,
):
    """Validate consistency across all exported assets."""
    output_dir = Path(config.output_dir)

    context.log.info("Collecting provider JSON IDs...")
    json_ids, json_point_ids, json_bbox_ids = _collect_json_ids(output_dir)
    context.log.info(
        f"  JSON: {len(json_ids)} total ({len(json_point_ids)} point, {len(json_bbox_ids)} bbox)"
    )

    context.log.info("Collecting spatial index IDs...")
    sis_ids, sis_point_ids, sis_bbox_ids = _collect_sis_ids(output_dir)
    context.log.info(
        f"  SIS: {len(sis_ids)} total ({len(sis_point_ids)} point, {len(sis_bbox_ids)} bbox)"
    )

    context.log.info("Decoding tile IDs from PMTiles...")
    tile_ids = _collect_tile_ids(output_dir)
    context.log.info(f"  Tiles: {len(tile_ids)} providers (point only)")

    context.log.info("Querying insufficient provider IDs from DB...")
    with bsil_postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM published.providers WHERE is_insufficient")
            insufficient_ids = {row[0] for row in cur.fetchall()}
        context.log.info(f"  Insufficient: {len(insufficient_ids)} providers")

        checks = [
            _check("SIS ⊆ JSON", sis_ids, json_ids, "FAIL", context),
            _check("JSON ⊆ SIS", json_ids, sis_ids, "FAIL", context),
            _check("Tiles ⊆ JSON", tile_ids, json_ids, "FAIL", context),
            _check("Tiles ⊆ SIS (point)", tile_ids, sis_point_ids, "FAIL", context),
            _check("SIS point ⊆ Tiles", sis_point_ids, tile_ids, "FAIL", context),
            _check(
                "No insufficient in SIS",
                sis_ids & insufficient_ids,
                set(),
                "FAIL",
                context,
            ),
            _check(
                "No insufficient in Tiles",
                tile_ids & insufficient_ids,
                set(),
                "FAIL",
                context,
            ),
        ]

        context.log.info("Validating LAD statistics files...")
        checks.extend(_validate_lad_files(output_dir, conn, context))

    context.log.info("Validating postcode autocomplete files...")
    checks.extend(_validate_postcode_files(output_dir, context))

    context.log.info("Validating LA boundaries...")
    checks.extend(_validate_la_boundaries(output_dir, context))

    report = {
        "checks": checks,
        "summary": {
            "json_total": len(json_ids),
            "json_point": len(json_point_ids),
            "json_bbox": len(json_bbox_ids),
            "sis_total": len(sis_ids),
            "sis_point": len(sis_point_ids),
            "sis_bbox": len(sis_bbox_ids),
            "tile_total": len(tile_ids),
            "insufficient_total": len(insufficient_ids),
        },
    }

    failures = [c for c in checks if c["status"] == "FAIL"]
    warnings = [c for c in checks if c["status"] == "WARN"]

    if warnings:
        msg = "; ".join(f"{c['name']} ({c['count']})" for c in warnings)
        context.log.warning(f"Export validation warnings: {msg}")

    if failures:
        msg = "; ".join(f"{c['name']} ({c['count']})" for c in failures)
        raise Failure(
            description=f"Export validation failed: {msg}",
            metadata={"report": MetadataValue.json(report)},
        )

    context.log.info("All export validation checks passed.")
    return MetadataValue.json(report)
