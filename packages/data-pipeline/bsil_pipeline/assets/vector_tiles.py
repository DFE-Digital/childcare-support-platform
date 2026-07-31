"""Dagster asset that generates PMTiles vector tiles from published providers.

Exports a GeoJSON FeatureCollection of all providers with coordinates, then
runs Tippecanoe to produce a compact PMTiles file for MapLibre rendering.
"""

import json
import os
import subprocess  # nosec B404
import tempfile
from collections import defaultdict
from pathlib import Path

from dagster import asset, AssetExecutionContext, Config, MetadataValue

from bsil_pipeline.automation import PIPELINE_CONDITION
from bsil_pipeline.resources.postgres import BsilPostgresResource


class VectorTilesConfig(Config):
    output_dir: str = "/opt/dagster/app/output/app"
    lad25cd: list[str] = []


_QUERY_BASE = """
SELECT p.id, p.name, p.latitude, p.longitude,
       p.address_line1, p.postcode, p.institution_type,
       p.ofsted_framework, p.ofsted_legacy_rating, p.ofsted_safeguarding_met,
       p.ofsted_achievement, p.ofsted_curriculum_and_teaching,
       p.ofsted_behaviour_attitudes_routines, p.ofsted_childrens_welfare_wellbeing,
       p.ofsted_inclusion, p.ofsted_leadership_and_governance,
       p.ofsted_attendance_and_behaviour, p.ofsted_personal_development_wellbeing,
       p.ofsted_early_years, p.ofsted_ccr_met, p.ofsted_vcr_met,
       p.cma_agency, p.cma_qa_grading,
       p.registered_places,
       string_agg(ct.care_type, ',' ORDER BY ct.id) AS care_types,
       bool_or(ct.funded_hours_accepted) AS any_funded,
       min(ct.eligible_min_months) AS age_lo_months,
       max(CASE WHEN ct.eligible_max_years IS NOT NULL
                THEN (ct.eligible_max_years + 1) * 12 - 1
                ELSE NULL END) AS age_hi_months,
       bool_or(ct.care_type = 'private_nursery') AS ct_pn,
       bool_or(ct.care_type = 'school_based_nursery') AS ct_sn,
       bool_or(ct.care_type = 'childminder') AS ct_cm,
       bool_or(ct.care_type = 'breakfast_club') AS ct_bc,
       bool_or(ct.care_type = 'free_breakfast_club') AS ct_fb,
       bool_or(ct.care_type = 'after_school_club') AS ct_ac,
       bool_or(ct.care_type = 'holiday_club') AS ct_hc
FROM published.providers p
LEFT JOIN published.care_types ct ON ct.provider_id = p.id
WHERE p.latitude IS NOT NULL AND p.longitude IS NOT NULL
  AND NOT p.is_insufficient
"""

_QUERY_LAD_FILTER = "AND p.lad25cd = ANY(%s)\n"

_QUERY_GROUP_BY = """GROUP BY p.id, p.name, p.latitude, p.longitude,
         p.address_line1, p.postcode, p.institution_type,
         p.ofsted_framework, p.ofsted_legacy_rating, p.ofsted_safeguarding_met,
         p.ofsted_achievement, p.ofsted_curriculum_and_teaching,
         p.ofsted_behaviour_attitudes_routines, p.ofsted_childrens_welfare_wellbeing,
         p.ofsted_inclusion, p.ofsted_leadership_and_governance,
         p.ofsted_attendance_and_behaviour, p.ofsted_personal_development_wellbeing,
         p.ofsted_early_years, p.ofsted_ccr_met, p.ofsted_vcr_met,
         p.cma_agency, p.cma_qa_grading,
         p.registered_places
"""

_INSTITUTION_SORT_ORDER = {
    "school_nursery": 0,
    "nursery": 1,
    "school_primary": 2,
    "school_secondary": 3,
    "school_special": 4,
    "school_independent": 5,
    "out_of_school_club": 6,
    "childminder": 7,
    "unknown": 8,
}

REPORT_CARD_GRADE_RANK = {
    "Exceptional": 0,
    "Strong standard": 1,
    "Expected standard": 2,
    "Needs attention": 3,
    "Urgent improvement": 4,
}

JUDGEMENT_COLS = [
    "ofsted_achievement",
    "ofsted_curriculum_and_teaching",
    "ofsted_behaviour_attitudes_routines",
    "ofsted_childrens_welfare_wellbeing",
    "ofsted_inclusion",
    "ofsted_leadership_and_governance",
    "ofsted_attendance_and_behaviour",
    "ofsted_personal_development_wellbeing",
    "ofsted_early_years",
]

BOOL_COLS = ["ofsted_safeguarding_met", "ofsted_ccr_met", "ofsted_vcr_met"]


def serialise_ofsted(row: dict) -> str | None:
    fw = row.get("ofsted_framework")
    if not fw:
        return None
    if fw == "legacy":
        return (
            f"L:{row['ofsted_legacy_rating']}"
            if row.get("ofsted_legacy_rating")
            else None
        )
    if fw == "legacy_transition":
        return "T"
    if fw == "report_card":
        ranks = sorted(
            REPORT_CARD_GRADE_RANK[row[c]]
            for c in JUDGEMENT_COLS
            if row.get(c) in REPORT_CARD_GRADE_RANK
        )
        bools = "".join(
            "Y" if row.get(c) is True else "N" if row.get(c) is False else "-"
            for c in BOOL_COLS
        )
        return f"R:{''.join(str(r) for r in ranks)}{bools}" if ranks else None
    return None


CT_SHORT = {
    "ct_pn": "ct_pn",
    "ct_sn": "ct_sn",
    "ct_cm": "ct_cm",
    "ct_bc": "ct_bc",
    "ct_fb": "ct_fb",
    "ct_ac": "ct_ac",
    "ct_hc": "ct_hc",
}


def _build_provider_props(row: dict) -> dict:
    """Build tile properties for a single provider row."""
    ofsted = serialise_ofsted(row)
    props = {
        "id": f"p{row['id']}",
        "name": row["name"],
        "care_types": row.get("care_types") or "",
        "address": row.get("address_line1") or "",
        "postcode": row.get("postcode") or "",
        "institution_type": row.get("institution_type") or "",
        "places": row.get("registered_places"),
    }
    if ofsted:
        props["ofsted"] = ofsted
    if row.get("cma_agency"):
        cma_parts = [row["cma_agency"]]
        if row.get("cma_qa_grading"):
            cma_parts.append(row["cma_qa_grading"])
        props["cma"] = "|".join(cma_parts)
    # Per care-type boolean flags (1 if present, omitted if absent)
    for key in CT_SHORT:
        if row.get(key):
            props[key] = 1
    # Funded hours flag
    if row.get("any_funded"):
        props["fh"] = 1
    # Age eligibility range (months)
    if row.get("age_lo_months") is not None:
        props["age_lo"] = int(row["age_lo_months"])
    if row.get("age_hi_months") is not None:
        props["age_hi"] = int(row["age_hi_months"])
    return props


def build_geojson(cur, lad25cd: list[str] | None = None) -> tuple[dict, int]:
    """Build GeoJSON FeatureCollection from published providers. Returns (geojson, provider_count)."""
    if lad25cd:
        cur.execute(_QUERY_BASE + _QUERY_LAD_FILTER + _QUERY_GROUP_BY, (lad25cd,))
    else:
        cur.execute(_QUERY_BASE + _QUERY_GROUP_BY)
    col_names = [desc[0] for desc in cur.description]

    # Group rows by coordinate so co-located providers become one feature
    locations: dict[tuple[float, float], list[dict]] = defaultdict(list)
    for raw_row in cur.fetchall():
        row = dict(zip(col_names, raw_row))
        lat = float(row["latitude"])
        lon = float(row["longitude"])
        locations[(lat, lon)].append(row)

    features = []
    provider_count = 0
    for (lat, lon), rows in locations.items():
        provider_count += len(rows)
        if len(rows) == 1:
            props = _build_provider_props(rows[0])
            props["count"] = 1
        else:
            sub_props = [
                _build_provider_props(r)
                for r in sorted(
                    rows,
                    key=lambda r: _INSTITUTION_SORT_ORDER.get(
                        r.get("institution_type", ""), 99
                    ),
                )
            ]
            props = {
                "count": len(rows),
                "address": rows[0].get("address_line1") or "",
                "postcode": rows[0].get("postcode") or "",
                "providers": json.dumps(sub_props),
            }
            # Aggregate filter flags across all sub-providers
            for key in CT_SHORT:
                if any(sp.get(key) == 1 for sp in sub_props):
                    props[key] = 1
            if any(sp.get("fh") == 1 for sp in sub_props):
                props["fh"] = 1
            lo_vals = [sp["age_lo"] for sp in sub_props if "age_lo" in sp]
            hi_vals = [sp["age_hi"] for sp in sub_props if "age_hi" in sp]
            if lo_vals:
                props["age_lo"] = min(lo_vals)
            if hi_vals:
                props["age_hi"] = max(hi_vals)

        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": props,
            }
        )

    return {"type": "FeatureCollection", "features": features}, provider_count


@asset(
    group_name="publish",
    deps=["publish_providers", "validate_published", "la_boundaries"],
    automation_condition=PIPELINE_CONDITION,
)
def vector_tiles(
    context: AssetExecutionContext,
    config: VectorTilesConfig,
    bsil_postgres: BsilPostgresResource,
):
    """Generate PMTiles vector tiles from published provider data and LA boundaries."""
    output_dir = Path(config.output_dir)
    tiles_dir = output_dir / "tiles"
    tiles_dir.mkdir(parents=True, exist_ok=True)
    output_path = tiles_dir / "providers.pmtiles"

    boundaries_path = Path(config.output_dir).parent / "la_boundaries.geojson"

    with bsil_postgres.get_connection() as conn:
        with conn.cursor() as cur:
            geojson, count = build_geojson(cur, lad25cd=config.lad25cd or None)

    feature_count = len(geojson["features"])
    context.log.info(
        f"Built GeoJSON with {feature_count} features from {count} providers"
    )

    with tempfile.NamedTemporaryFile(mode="w", suffix=".geojson", delete=False) as tmp:
        json.dump(geojson, tmp)
        tmp_path = tmp.name

    try:
        cmd = [
            "tippecanoe",
            "-o",
            str(output_path),
            "-zg",
            "-Z4",
            "--drop-densest-as-needed",
            "--extend-zooms-if-still-dropping",
            "--no-tile-size-limit",
            "--force",
            "-L",
            f"providers:{tmp_path}",
        ]
        if boundaries_path.exists():
            cmd += ["-L", f"boundaries:{boundaries_path}"]
            context.log.info("Including LA boundaries layer in tiles")
        else:
            context.log.warning(
                f"LA boundaries not found at {boundaries_path}, skipping boundaries layer"
            )
        context.log.info(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)  # nosec B603
        if result.stderr:
            context.log.info(f"Tippecanoe output: {result.stderr}")
    finally:
        os.unlink(tmp_path)

    size = output_path.stat().st_size
    context.log.info(
        f"Wrote providers.pmtiles: {count} providers, {size / 1024 / 1024:.1f} MB"
    )
    return MetadataValue.int(count)
