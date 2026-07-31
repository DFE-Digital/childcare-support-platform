"""Export per-LA JSON files from ten_ds.cost_estimates and la.family_information_services.

Reads cost estimates and FIS URLs from Postgres, groups by la_code, and writes
one JSON file per LA to {output_dir}/lad/{la_code}.json.

Each JSON file matches the PostcodeAreaCosts TypeScript interface shape.
"""

import json
import os
import re
from collections import defaultdict
from pathlib import Path

from dagster import asset, AssetExecutionContext, Config, MetadataValue

from bsil_pipeline.assets.publish import BETA_LA_CODES
from bsil_pipeline.automation import PIPELINE_CONDITION
from bsil_pipeline.resources.postgres import BsilPostgresResource


_EXPORT_DIR = Path("/opt/dagster/app/output/app")


class ExportCostsConfig(Config):
    output_dir: str = str(_EXPORT_DIR)
    last_updated: str = "2026-04"


# --- Mapping constants ---

PROV_GROUP_MAP = {
    "CM": "childminder",
    "GBP": "private_nursery",
    "SBP": "school_based_nursery",
}

AGE_GROUP_MAP = {
    "under_2": "under2",
    "2yr": "age2",
    "3_4yr": "age3to4",
}

DATA_LEVEL_MAP = {
    "la": "la",
    "region": "region",
    "national": "national",
}

CARE_TYPE_TEMPLATE = {
    "private_nursery": {
        "sessionHours": {"morning": 5, "afternoon": 5, "fullDay": 10},
        "operatingWeeksPerYear": 50,
        "meal_description": "Lunch and snacks",
    },
    "school_based_nursery": {
        "sessionHours": {"morning": 3.25, "afternoon": 3.25},
        "operatingWeeksPerYear": 38,
        "meal_description": "Hot lunch if attending full day or over lunchtime",
    },
    "childminder": {
        "meal_description": "Lunch and snacks if attending over lunchtime",
    },
}


_COMMA_INVERSION_RE = re.compile(r"^(.+),\s+(.+)$")


def _normalise_la_name(name: str) -> str:
    """Rewrite ONS comma-inverted names: 'Bristol, City of' → 'City of Bristol'."""
    m = _COMMA_INVERSION_RE.match(name)
    return f"{m.group(2)} {m.group(1)}" if m else name


def _build_la_json(
    la_code: str,
    rows: list[dict],
    last_updated: str,
    fis_url: str | None = None,
    beta_mode: bool = False,
) -> dict:
    """Build the per-LA JSON dict from DB rows for that LA.

    Args:
        la_code: The LA code (e.g. "E06000005")
        rows: All DB rows for this LA (up to 9: 3 ages x 3 prov types)
        last_updated: The lastUpdated string (e.g. "2026-04")
        fis_url: Optional Family Information Service URL for this LA
        beta_mode: If True, set showBetaWarning=True for LAs outside BETA_LA_CODES

    Returns:
        A dict matching the PostcodeAreaCosts shape.
    """
    la_name = _normalise_la_name(rows[0]["la_name"])
    region = rows[0]["region"]

    result: dict = {
        "laName": la_name,
        "regionName": region,
        "nationName": "England",
        "lastUpdated": last_updated,
        "showBetaWarning": beta_mode and la_code not in BETA_LA_CODES,
        "averageCosts": {},
        "governmentFundingRates": {},
    }

    # Extract shared meal data (identical across all rows for an LA)
    meal_mean = None
    meal_lower = None
    meal_upper = None
    for row in rows:
        if row["meal_mean"] is not None:
            meal_mean = row["meal_mean"]
            meal_lower = row["meal_lower"]
            meal_upper = row["meal_upper"]
            break

    # Group rows by prov_group
    by_prov: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_prov[row["prov_group"]].append(row)

    for prov_group, prov_rows in by_prov.items():
        care_type_key = PROV_GROUP_MAP.get(prov_group)
        if care_type_key is None:
            continue

        template = CARE_TYPE_TEMPLATE.get(care_type_key, {})
        care_type: dict = {"fees": {}, "additionalCharges": []}

        if "sessionHours" in template:
            care_type["sessionHours"] = template["sessionHours"]
        if "operatingWeeksPerYear" in template:
            care_type["operatingWeeksPerYear"] = template["operatingWeeksPerYear"]

        for row in prov_rows:
            age_key = AGE_GROUP_MAP.get(row["age_group"])
            if age_key is None:
                continue

            area = DATA_LEVEL_MAP.get(row["data_level"])
            if area is None:
                continue

            if row["hourly_mean"] is not None:
                care_type["fees"][age_key] = {
                    "perHour": {
                        "mean": round(row["hourly_mean"], 2),
                        "lower": round(row["hourly_lower"], 2),
                        "upper": round(row["hourly_upper"], 2),
                        "area": area,
                    }
                }

        # Add meal charge if we have meal data
        if meal_mean is not None:
            care_type["additionalCharges"].append(
                {
                    "item": "Meals",
                    "cost": {
                        "mean": round(meal_mean, 2),
                        "lower": round(meal_lower, 2),
                        "upper": round(meal_upper, 2),
                        "area": "la",
                    },
                    "unit": "per day",
                    "description": template.get("meal_description", "Lunch and snacks"),
                }
            )

        # Only include care type if it has at least one fee entry
        if care_type["fees"]:
            result["averageCosts"][care_type_key] = care_type

    # Build governmentFundingRates (same across all prov_groups for a given age)
    funding_by_age: dict[str, float] = {}
    for row in rows:
        age_key = AGE_GROUP_MAP.get(row["age_group"])
        if age_key and row["funding_rate"] is not None:
            funding_by_age[age_key] = round(row["funding_rate"], 2)

    for age_key in ["under2", "age2", "age3to4"]:
        if age_key in funding_by_age:
            result["governmentFundingRates"][age_key] = {
                "perHour": funding_by_age[age_key]
            }

    if fis_url:
        result["familyInformationServices"] = [{"url": fis_url}]

    return result


@asset(
    group_name="ten_ds",
    deps=[
        "cost_estimates",
        "family_information_services",
        "publish_providers",
        "validate_published",
        "la_boundaries",
    ],
    automation_condition=PIPELINE_CONDITION,
)
def export_costs(
    context: AssetExecutionContext,
    config: ExportCostsConfig,
    bsil_postgres: BsilPostgresResource,
):
    """Export per-LA JSON files from ten_ds.cost_estimates and la.family_information_services."""
    beta_mode = context.run.tags.get("BETA", "false").lower() == "true"
    output_dir = Path(os.environ.get("EXPORT_APP_DIR", config.output_dir))
    lad_dir = output_dir / "lad"
    lad_dir.mkdir(parents=True, exist_ok=True)

    # Clear existing files for idempotency
    for f in lad_dir.iterdir():
        if f.suffix == ".json":
            f.unlink()

    with bsil_postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT la_code, la_name, region, age_group, prov_group, "
                "       hourly_lower, hourly_mean, hourly_weighted_mean, "
                "       hourly_upper, meal_lower, meal_mean, meal_upper, "
                "       funding_rate, data_level, n_la, n_region, n_national "
                "FROM ten_ds.cost_estimates "
                "ORDER BY la_code, age_group, prov_group"
            )
            col_names = [desc[0] for desc in cur.description]
            all_rows = cur.fetchall()

        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT ON (lad25cd) lad25cd, fis_url"
                " FROM la.family_information_services ORDER BY lad25cd"
            )
            fis_col_names = [desc[0] for desc in cur.description]
            fis_rows = cur.fetchall()

        with conn.cursor() as cur:
            cur.execute(
                "SELECT p.lad25cd, ct.care_type,"
                "       COUNT(DISTINCT p.id)"
                "           FILTER (WHERE NOT p.is_insufficient) AS total,"
                "       COUNT(DISTINCT p.id)"
                "           FILTER (WHERE p.is_insufficient) AS insufficient,"
                "       COUNT(DISTINCT p.id)"
                "           FILTER (WHERE NOT p.is_insufficient"
                "                        AND p.bbox_geo_type IS NOT NULL"
                "                        AND p.latitude IS NULL) AS bbox_only"
                " FROM published.providers p"
                " JOIN published.care_types ct ON ct.provider_id = p.id"
                " GROUP BY p.lad25cd, ct.care_type"
            )
            stats_rows = cur.fetchall()

        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT ON (lad25cd) lad25cd, lad25nm"
                " FROM la.family_information_services ORDER BY lad25cd"
            )
            la_name_rows = cur.fetchall()

    # Read laBounds from the simplified la_boundaries.geojson (BFC-clipped)
    boundaries_path = output_dir.parent / "la_boundaries.geojson"
    la_bbox_rows = []
    if boundaries_path.exists():
        with open(boundaries_path) as f:
            boundaries = json.load(f)
        for feat in boundaries.get("features", []):
            props = feat.get("properties", {})
            geom = feat.get("geometry")
            if not props.get("LAD25CD") or not geom:
                continue
            coords = geom.get("coordinates", [])
            all_lons: list[float] = []
            all_lats: list[float] = []
            if geom["type"] == "Polygon":
                for ring in coords:
                    for c in ring:
                        all_lons.append(c[0])
                        all_lats.append(c[1])
            elif geom["type"] == "MultiPolygon":
                for poly in coords:
                    for ring in poly:
                        for c in ring:
                            all_lons.append(c[0])
                            all_lats.append(c[1])
            if all_lons:
                la_bbox_rows.append(
                    (
                        props["LAD25CD"],
                        min(all_lats),
                        min(all_lons),
                        max(all_lats),
                        max(all_lons),
                    )
                )

    fis_by_lad: dict[str, str] = {}
    for row_tuple in fis_rows:
        row_dict = dict(zip(fis_col_names, row_tuple))
        if row_dict.get("fis_url"):
            fis_by_lad[row_dict["lad25cd"]] = row_dict["fis_url"]

    la_name_by_code: dict[str, str] = {}
    for lad25cd, lad25nm in la_name_rows:
        if lad25nm:
            la_name_by_code[lad25cd] = _normalise_la_name(lad25nm)

    bbox_by_lad: dict[str, dict] = {}
    for geo_code, south, west, north, east in la_bbox_rows:
        bbox_by_lad[geo_code] = {
            "south": round(float(south), 6),
            "west": round(float(west), 6),
            "north": round(float(north), 6),
            "east": round(float(east), 6),
        }

    stats_by_la: dict[str, dict[str, dict]] = defaultdict(dict)
    for lad25cd, care_type, total, insufficient, bbox_only in stats_rows:
        if lad25cd and care_type:
            stats_by_la[lad25cd][care_type] = {
                "total": total,
                "bboxOnly": bbox_only,
                "insufficient": insufficient,
            }

    by_la: dict[str, list[dict]] = defaultdict(list)
    for row_tuple in all_rows:
        row_dict = dict(zip(col_names, row_tuple))
        by_la[row_dict["la_code"]].append(row_dict)

    file_count = 0
    for la_code, la_rows in sorted(by_la.items()):
        la_json = _build_la_json(
            la_code,
            la_rows,
            config.last_updated,
            fis_by_lad.get(la_code),
            beta_mode=beta_mode,
        )

        if la_code in stats_by_la:
            la_json["providerStats"] = stats_by_la[la_code]
        if la_code in bbox_by_lad:
            la_json["laBounds"] = bbox_by_lad[la_code]

        out_path = lad_dir / f"{la_code}.json"
        out_path.write_text(json.dumps(la_json, indent=2, ensure_ascii=False) + "\n")
        file_count += 1

    # Write stats-only files for LAs with providers but no cost data
    for la_code in sorted(stats_by_la.keys()):
        if la_code in by_la:
            continue
        la_json: dict = {
            "laName": la_name_by_code.get(la_code, la_code),
            "lastUpdated": config.last_updated,
            "providerStats": stats_by_la[la_code],
        }
        if la_code in bbox_by_lad:
            la_json["laBounds"] = bbox_by_lad[la_code]
        out_path = lad_dir / f"{la_code}.json"
        out_path.write_text(json.dumps(la_json, indent=2, ensure_ascii=False) + "\n")
        file_count += 1

    context.log.info(
        f"Exported {file_count} LAD files to {lad_dir}"  # noqa: G004
    )
    return {
        "file_count": MetadataValue.int(file_count),
        "output_dir": MetadataValue.text(str(lad_dir)),
    }
