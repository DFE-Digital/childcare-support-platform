"""Dagster asset that builds a compact spatial index table.

One row per care-type entry. Providers with no care types get one row
with care_type=-1. Contains pre-computed filter flags and sort scores
so the frontend can filter/sort ~50K rows in-memory without loading
individual provider JSON files.
"""

from collections import defaultdict

import pyarrow as pa
from dagster import asset, AssetExecutionContext, MetadataValue

from bsil_pipeline.automation import PIPELINE_CONDITION
from bsil_pipeline.resources.postgres import BsilPostgresResource
from bsil_pipeline.spatial_index.schema import (
    CARE_TYPE_ENUM,
    SPATIAL_INDEX_SCHEMA,
)
from bsil_pipeline.spatial_index.ofsted_score import compute_ofsted_score
from bsil_pipeline.spatial_index.cost_rate import compute_cost_columns


_QUERY_MAIN = """
SELECT
    p.id AS provider_id,
    p.latitude, p.longitude,
    p.bbox_geo_type, p.bbox_geo_code,
    p.lad25cd,
    p.ofsted_framework, p.ofsted_legacy_rating, p.ofsted_safeguarding_met,
    p.ofsted_achievement, p.ofsted_curriculum_and_teaching,
    p.ofsted_behaviour_attitudes_routines, p.ofsted_childrens_welfare_wellbeing,
    p.ofsted_attendance_and_behaviour, p.ofsted_personal_development_wellbeing,
    p.ofsted_inclusion, p.ofsted_leadership_and_governance,
    p.ofsted_early_years, p.ofsted_sixth_form,
    p.ofsted_legacy_quality_of_education, p.ofsted_legacy_behaviour_and_attitudes,
    p.ofsted_legacy_personal_development, p.ofsted_legacy_leadership_and_management,
    p.ofsted_legacy_early_years, p.ofsted_legacy_sixth_form,
    p.ofsted_ccr_met, p.ofsted_vcr_met, p.ofsted_oosc_met,
    p.cma_qa_grading,
    p.staff_graduate_percentage, p.staff_turnover_percentage,
    ct.id AS ct_id, ct.care_type,
    oh_agg.opening_hour_open, oh_agg.opening_hour_close,
    ct.operating_weeks_per_year,
    ct.session_hours_morning, ct.session_hours_afternoon, ct.session_hours_full_day,
    ct.eligible_min_months, ct.eligible_min_years, ct.eligible_max_years,
    ct.funded_hours_accepted,
    bb.bbox_south, bb.bbox_east, bb.bbox_north, bb.bbox_west
FROM published.providers p
LEFT JOIN published.care_types ct ON ct.provider_id = p.id
LEFT JOIN LATERAL (
    SELECT MIN(oh.open) AS opening_hour_open, MAX(oh.close) AS opening_hour_close
    FROM published.opening_hours oh
    WHERE oh.care_type_id = ct.id
) oh_agg ON true
LEFT JOIN published.bounding_boxes bb
    ON bb.geo_type = p.bbox_geo_type AND bb.geo_code = p.bbox_geo_code
WHERE NOT p.is_insufficient
ORDER BY p.id, ct.id
"""

_QUERY_FEES = """
SELECT care_type_id, age_band,
       morning_session, afternoon_session, full_day,
       per_session, per_hour, per_day
FROM published.fee_rates
ORDER BY care_type_id, id
"""


_LAD_PREFIX = {"E": 1, "S": 2, "W": 3, "N": 4}


def _encode_lad(code: str | None) -> int:
    """Encode an ONS LAD code (e.g. 'E06000025') to int32."""
    if not code or len(code) < 2:
        return 0
    prefix = _LAD_PREFIX.get(code[0], 0)
    return prefix * 100_000_000 + int(code[1:])


def _decimal_or_none(v):
    if v is None:
        return None
    return float(v)


def _time_to_hours(t) -> float | None:
    """Convert a time or 'HH:MM' string to hours since midnight."""
    if t is None:
        return None
    from datetime import time

    if isinstance(t, time):
        return t.hour + t.minute / 60.0
    parts = str(t)[:5].split(":")
    return int(parts[0]) + int(parts[1]) / 60.0


def build_spatial_index(cur) -> pa.Table:
    """Build the spatial index PyArrow table from the published DB tables.

    This is the testable core — no Dagster dependency.
    """
    # Load fee_rates into a lookup dict keyed by care_type_id
    cur.execute(_QUERY_FEES)
    fee_col_names = [desc[0] for desc in cur.description]
    fee_lookup: dict[int, list[dict]] = defaultdict(list)
    for row in cur.fetchall():
        row_dict = dict(zip(fee_col_names, row))
        ct_id = row_dict.pop("care_type_id")
        fee_lookup[ct_id].append(row_dict)

    # Load main query
    cur.execute(_QUERY_MAIN)
    col_names = [desc[0] for desc in cur.description]
    rows = cur.fetchall()

    # Build columnar arrays
    columns: dict[str, list] = {field.name: [] for field in SPATIAL_INDEX_SCHEMA}

    prev_provider_id = None
    caretype_index = 0

    for raw_row in rows:
        row = dict(zip(col_names, raw_row))
        provider_id = row["provider_id"]
        ct_id = row["ct_id"]

        # Track caretype_index per provider
        if provider_id != prev_provider_id:
            caretype_index = 0
            prev_provider_id = provider_id
        else:
            caretype_index += 1

        # Care type enum
        is_no_caretype = ct_id is None
        care_type_str = row.get("care_type")
        care_type_int = -1 if is_no_caretype else CARE_TYPE_ENUM.get(care_type_str, -1)

        # Coordinates
        lat = _decimal_or_none(row["latitude"])
        lon = _decimal_or_none(row["longitude"])
        bbox_south = _decimal_or_none(row.get("bbox_south"))
        bbox_east = _decimal_or_none(row.get("bbox_east"))

        # For bbox providers: lat/lon = NW corner, bbox_lat/bbox_lon = SE corner
        if lat is None and bbox_south is not None:
            lat = _decimal_or_none(row.get("bbox_north"))
            lon = _decimal_or_none(row.get("bbox_west"))

        # Ofsted score (provider-level)
        ofsted_score = compute_ofsted_score(row)

        # Staff (provider-level)
        graduates = _decimal_or_none(row.get("staff_graduate_percentage"))
        turnover = _decimal_or_none(row.get("staff_turnover_percentage"))

        # Care-type-level fields
        if is_no_caretype:
            funded = False
            elig_min_months = None
            elig_min_years = None
            elig_max_years = None
            daily_open = float("nan")
            daily_close = float("nan")
            annual_opening = -1
            cost_cols = {
                "sort_cost_all": float("nan"),
                "sort_cost_under2": float("nan"),
                "sort_cost_age2": float("nan"),
                "sort_cost_age3to4": float("nan"),
                "sort_cost_age2plus": float("nan"),
                "sort_cost_age5plus": float("nan"),
            }
        else:
            funded = bool(row.get("funded_hours_accepted")) or False
            elig_min_months = row.get("eligible_min_months")
            elig_min_years = row.get("eligible_min_years")
            elig_max_years = row.get("eligible_max_years")

            daily_open = _time_to_hours(row.get("opening_hour_open"))
            daily_close = _time_to_hours(row.get("opening_hour_close"))

            weeks = row.get("operating_weeks_per_year")
            annual_opening = weeks if weeks is not None else -1

            # Build ct_row dict for cost calculation
            ct_row = {
                "care_type": care_type_str,
                "opening_hour_open": row.get("opening_hour_open"),
                "opening_hour_close": row.get("opening_hour_close"),
                "session_hours_morning": row.get("session_hours_morning"),
                "session_hours_afternoon": row.get("session_hours_afternoon"),
                "session_hours_full_day": row.get("session_hours_full_day"),
            }
            fee_rows = fee_lookup.get(ct_id, [])
            cost_cols = compute_cost_columns(ct_row, fee_rows)

        # Append to columns
        columns["provider_id"].append(provider_id)
        columns["caretype_index"].append(caretype_index)
        columns["care_type"].append(care_type_int)
        columns["lat"].append(lat)
        columns["lon"].append(lon)
        columns["bbox_lat"].append(bbox_south)
        columns["bbox_lon"].append(bbox_east)
        columns["filter_accepts_funded_hours"].append(funded)
        columns["filter_eligible_min_months"].append(elig_min_months)
        columns["filter_eligible_min_years"].append(elig_min_years)
        columns["filter_eligible_max_years"].append(elig_max_years)
        columns["sort_daily_open"].append(
            daily_open if daily_open is not None else float("nan")
        )
        columns["sort_daily_close"].append(
            daily_close if daily_close is not None else float("nan")
        )
        columns["sort_annual_opening"].append(annual_opening)
        columns["sort_ofsted"].append(ofsted_score)
        columns["sort_graduates"].append(graduates)
        columns["sort_turnover"].append(turnover)
        columns["sort_cost_all"].append(cost_cols["sort_cost_all"])
        columns["sort_cost_under2"].append(cost_cols["sort_cost_under2"])
        columns["sort_cost_age2"].append(cost_cols["sort_cost_age2"])
        columns["sort_cost_age3to4"].append(cost_cols["sort_cost_age3to4"])
        columns["sort_cost_age2plus"].append(cost_cols["sort_cost_age2plus"])
        columns["sort_cost_age5plus"].append(cost_cols["sort_cost_age5plus"])
        columns["lad_code"].append(_encode_lad(row.get("lad25cd")))

    # Build PyArrow arrays with schema types
    arrays = []
    for field in SPATIAL_INDEX_SCHEMA:
        arrays.append(pa.array(columns[field.name], type=field.type))

    return pa.table(arrays, schema=SPATIAL_INDEX_SCHEMA)


_CREATE_TABLE = """\
CREATE TABLE IF NOT EXISTS published.spatial_index (
    provider_id         BIGINT NOT NULL,
    caretype_index      SMALLINT NOT NULL,
    care_type           SMALLINT NOT NULL,
    lat                 REAL,
    lon                 REAL,
    bbox_lat            REAL,
    bbox_lon            REAL,
    filter_accepts_funded_hours BOOLEAN NOT NULL,
    filter_eligible_min_months  SMALLINT,
    filter_eligible_min_years   SMALLINT,
    filter_eligible_max_years   SMALLINT,
    sort_daily_open     REAL,
    sort_daily_close    REAL,
    sort_annual_opening SMALLINT NOT NULL,
    sort_ofsted         REAL NOT NULL,
    sort_graduates      REAL,
    sort_turnover       REAL,
    sort_cost_all       REAL,
    sort_cost_under2    REAL,
    sort_cost_age2      REAL,
    sort_cost_age3to4   REAL,
    sort_cost_age2plus  REAL,
    sort_cost_age5plus  REAL,
    lad_code            INTEGER NOT NULL
)
"""


@asset(
    group_name="publish",
    deps=["publish_providers", "validate_published"],
    automation_condition=PIPELINE_CONDITION,
)
def spatial_index(
    context: AssetExecutionContext,
    bsil_postgres: BsilPostgresResource,
):
    """Build a compact spatial index and store in published.spatial_index table."""
    with bsil_postgres.get_connection() as conn:
        with conn.cursor() as cur:
            table = build_spatial_index(cur)

            cur.execute("DROP TABLE IF EXISTS published.spatial_index")
            cur.execute(_CREATE_TABLE)

            col_names = [field.name for field in SPATIAL_INDEX_SCHEMA]
            columns = [table.column(name).to_pylist() for name in col_names]
            num_rows = len(table)

            with cur.copy("COPY published.spatial_index FROM STDIN") as copy:
                for i in range(num_rows):
                    copy.write_row([columns[j][i] for j in range(len(col_names))])

        conn.commit()

    context.log.info(f"Wrote published.spatial_index: {num_rows} rows")
    return MetadataValue.int(num_rows)
