"""Aggregate raw PostHog events into a session-level features Parquet file.

Produces one row per session with ~80 feature columns. The session_id is
used only for grouping and is NOT included in the output (privacy).
"""

import json
import statistics
from collections import Counter
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from dagster import asset, AssetExecutionContext, MetadataValue

from bsil_pipeline.resources.postgres import BsilPostgresResource

_OUTPUT_DIR = Path("/opt/dagster/app/output")

STEP_ORDER = [
    "postcode",
    "partner",
    "immigration",
    "working",
    "benefits",
    "children",
    "childcare",
]

CARE_TYPES_ALL = [
    "childminder",
    "private_nursery",
    "school_based_nursery",
    "after_school_club",
    "breakfast_club",
    "holiday_club",
]

SCHEME_IDS = [
    "15_hours_2_year_olds",
    "15_hours_universal",
    "30_hours_working_families",
    "childcare_grant",
    "free_breakfast_clubs",
    "haf",
    "learner_support",
    "tax_free_childcare",
    "universal_credit_childcare",
    "wraparound_childcare",
]

SCHEME_COL_MAP = {
    "15_hours_2_year_olds": "scheme_15h_2yr",
    "15_hours_universal": "scheme_15h_universal",
    "30_hours_working_families": "scheme_30h_working",
    "childcare_grant": "scheme_childcare_grant",
    "free_breakfast_clubs": "scheme_free_breakfast",
    "haf": "scheme_haf",
    "learner_support": "scheme_learner_support",
    "tax_free_childcare": "scheme_tfc",
    "universal_credit_childcare": "scheme_uc_childcare",
    "wraparound_childcare": "scheme_wraparound",
}


def _safe_json_list(val):
    if val is None:
        return []
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            return parsed if isinstance(parsed, list) else []
        except (json.JSONDecodeError, TypeError):
            return []
    return []


def _get_prop(props, key):
    if isinstance(props, dict):
        return props.get(key)
    if isinstance(props, str):
        try:
            return json.loads(props).get(key)
        except (json.JSONDecodeError, TypeError):
            return None
    return None


def _furthest_step(steps_seen):
    best_idx = -1
    best_step = None
    for s in steps_seen:
        if s in STEP_ORDER:
            idx = STEP_ORDER.index(s)
            if idx > best_idx:
                best_idx = idx
                best_step = s
    return best_step


def _aggregate_session(events):
    row = {}

    timestamps = [e["timestamp"] for e in events if e["timestamp"]]
    if not timestamps:
        return None

    timestamps.sort()
    row["session_date"] = timestamps[0].date()
    row["session_duration_s"] = (timestamps[-1] - timestamps[0]).total_seconds()

    # Event counts by page area
    form_count = 0
    provider_count = 0
    other_count = 0
    for e in events:
        props = e["properties"]
        pathname = _get_prop(props, "$pathname") or ""
        if pathname.startswith("/support") or pathname.startswith("/costs"):
            form_count += 1
        elif pathname.startswith("/providers"):
            provider_count += 1
        else:
            other_count += 1
    row["event_count_form"] = form_count
    row["event_count_provider"] = provider_count
    row["event_count_other"] = other_count

    # Device type (constant per session, take first non-null)
    device = None
    for e in events:
        d = _get_prop(e["properties"], "$device_type")
        if d:
            device = d
            break
    row["device_type"] = device

    # Referrer domain (first event)
    row["referrer_domain"] = _get_prop(events[0]["properties"], "$referring_domain")

    # --- Form steps ---
    step_events = [e for e in events if e["event"] == "step_completed"]
    support_steps = [
        e for e in step_events if _get_prop(e["properties"], "form") == "support"
    ]
    costs_steps = [
        e for e in step_events if _get_prop(e["properties"], "form") == "costs"
    ]

    row["steps_completed_support"] = len(support_steps)
    row["steps_completed_costs"] = len(costs_steps)

    support_step_names = set(_get_prop(e["properties"], "step") for e in support_steps)
    costs_step_names = set(_get_prop(e["properties"], "step") for e in costs_steps)
    support_step_names.discard(None)
    costs_step_names.discard(None)

    row["distinct_steps_support"] = len(support_step_names)
    row["distinct_steps_costs"] = len(costs_step_names)
    row["furthest_step_support"] = _furthest_step(support_step_names)
    row["furthest_step_costs"] = _furthest_step(costs_step_names)

    # Results
    schemes_events = [e for e in events if e["event"] == "schemes_eligible"]
    row["reached_entitlements_results"] = sum(
        1 for e in schemes_events if _get_prop(e["properties"], "form") == "support"
    )
    row["reached_costs_results"] = sum(
        1 for e in schemes_events if _get_prop(e["properties"], "form") == "costs"
    )

    # --- Geography ---
    all_lads = []
    all_iods = []
    for e in events:
        lad = _get_prop(e["properties"], "lad25cd")
        if lad and lad != "null":
            all_lads.append(lad)
        iod = _get_prop(e["properties"], "iod_decile")
        if iod is not None and iod != "null":
            try:
                all_iods.append(int(iod))
            except (ValueError, TypeError):
                pass

    distinct_lads = sorted(set(all_lads))
    row["lad_codes"] = json.dumps(distinct_lads) if distinct_lads else "[]"
    row["lad_mode"] = Counter(all_lads).most_common(1)[0][0] if all_lads else None
    row["lad_count"] = len(distinct_lads)

    row["iod_decile_min"] = min(all_iods) if all_iods else None
    row["iod_decile_max"] = max(all_iods) if all_iods else None
    row["iod_decile_mean"] = round(statistics.mean(all_iods), 2) if all_iods else None
    row["iod_decile_median"] = statistics.median(all_iods) if all_iods else None
    row["iod_deciles"] = json.dumps(sorted(set(all_iods))) if all_iods else "[]"

    # --- Demographics (true/false/pct) ---
    binary_fields = {
        "has_partner": ("partner", "has_partner"),
        "settled_in_uk": ("immigration", "settled_in_uk"),
        "working": ("working", "working"),
        "is_studying": ("working", "is_studying"),
        "receives_benefits": ("benefits", "receives_benefits"),
    }
    for col_prefix, (step_name, prop_name) in binary_fields.items():
        relevant = [
            e for e in step_events if _get_prop(e["properties"], "step") == step_name
        ]
        true_count = 0
        false_count = 0
        for e in relevant:
            val = _get_prop(e["properties"], prop_name)
            if val is True or val == "true":
                true_count += 1
            elif val is False or val == "false":
                false_count += 1
        row[f"{col_prefix}_true"] = true_count
        row[f"{col_prefix}_false"] = false_count
        total = true_count + false_count
        row[f"{col_prefix}_pct"] = round(true_count / total, 4) if total > 0 else None

    # --- Child data ---
    children_events = [
        e for e in step_events if _get_prop(e["properties"], "step") == "children"
    ]
    child_counts = Counter()
    youngest_bands = Counter()
    for e in children_events:
        cc = _get_prop(e["properties"], "child_count")
        if cc is not None:
            try:
                child_counts[int(cc)] += 1
            except (ValueError, TypeError):
                pass
        yb = _get_prop(e["properties"], "youngest_band")
        if yb:
            youngest_bands[yb] += 1

    row["child_count_1"] = child_counts.get(1, 0)
    row["child_count_2"] = child_counts.get(2, 0)
    row["child_count_3plus"] = child_counts.get(3, 0)
    row["youngest_band_0_4"] = youngest_bands.get("0-4", 0)
    row["youngest_band_5_plus"] = youngest_bands.get("5+", 0)

    # --- Care types sought (one-hot frequency) ---
    childcare_events = [
        e for e in step_events if _get_prop(e["properties"], "step") == "childcare"
    ]
    care_sought_counts = Counter()
    for e in childcare_events:
        types = _safe_json_list(_get_prop(e["properties"], "care_types_sought"))
        for t in types:
            care_sought_counts[t] += 1

    row["care_sought_childminder"] = care_sought_counts.get("childminder", 0)
    row["care_sought_private_nursery"] = care_sought_counts.get("private_nursery", 0)
    row["care_sought_school_based_nursery"] = care_sought_counts.get(
        "school_based_nursery", 0
    )

    # --- Schemes eligible (one-hot frequency) ---
    scheme_counts = Counter()
    for e in schemes_events:
        schemes = _safe_json_list(_get_prop(e["properties"], "schemes"))
        for s in schemes:
            scheme_counts[s] += 1

    for scheme_id, col_name in SCHEME_COL_MAP.items():
        row[col_name] = scheme_counts.get(scheme_id, 0)

    # --- Provider search ---
    provider_search_events = [e for e in events if e["event"] == "provider_search"]
    row["provider_searches"] = len(provider_search_events)

    ps_lads = sorted(
        set(
            _get_prop(e["properties"], "lad25cd")
            for e in provider_search_events
            if _get_prop(e["properties"], "lad25cd")
        )
    )
    row["provider_search_lads"] = json.dumps(ps_lads) if ps_lads else "[]"

    ps_iods = []
    for e in provider_search_events:
        iod = _get_prop(e["properties"], "iod_decile")
        if iod is not None and iod != "null":
            try:
                ps_iods.append(int(iod))
            except (ValueError, TypeError):
                pass

    row["provider_search_iod_min"] = min(ps_iods) if ps_iods else None
    row["provider_search_iod_max"] = max(ps_iods) if ps_iods else None
    row["provider_search_iod_mean"] = (
        round(statistics.mean(ps_iods), 2) if ps_iods else None
    )
    row["provider_search_iod_median"] = statistics.median(ps_iods) if ps_iods else None

    # --- Provider filter events ---
    filter_events = [e for e in events if e["event"] == "provider_filter_changed"]
    row["provider_filters_changed"] = len(filter_events)

    filter_care_counts = Counter()
    filter_funded_true = 0
    filter_funded_false = 0
    sort_counts = Counter()
    child_band_counts = Counter()

    for e in filter_events:
        props = e["properties"]
        care_types = _safe_json_list(_get_prop(props, "care_types"))
        for ct in care_types:
            filter_care_counts[ct] += 1

        funded = _get_prop(props, "funded_hours_only")
        if funded is True or funded == "true":
            filter_funded_true += 1
        elif funded is False or funded == "false":
            filter_funded_false += 1

        sort_by = _get_prop(props, "sort_by")
        if sort_by:
            sort_counts[sort_by] += 1

        bands = _safe_json_list(_get_prop(props, "child_age_bands"))
        for b in bands:
            child_band_counts[b] += 1

    for ct in CARE_TYPES_ALL:
        row[f"provider_filter_care_{ct}"] = filter_care_counts.get(ct, 0)

    row["provider_filter_funded_hours_true"] = filter_funded_true
    row["provider_filter_funded_hours_false"] = filter_funded_false
    row["provider_sort_distance"] = sort_counts.get("distance", 0)
    row["provider_sort_best_ofsted"] = sort_counts.get("best_ofsted", 0)
    row["provider_child_band_0_4"] = child_band_counts.get("0-4", 0)
    row["provider_child_band_5_plus"] = child_band_counts.get("5+", 0)

    # --- Provider detail viewed ---
    detail_events = [e for e in events if e["event"] == "provider_detail_viewed"]
    row["provider_details_viewed"] = len(detail_events)

    dist_band_counts = Counter()
    for e in detail_events:
        band = _get_prop(e["properties"], "distance_band")
        if band:
            dist_band_counts[band] += 1

    row["provider_detail_dist_band_lt1"] = dist_band_counts.get("<1mi", 0)
    row["provider_detail_dist_band_1_3"] = dist_band_counts.get("1-3mi", 0)
    row["provider_detail_dist_band_3_5"] = dist_band_counts.get("3-5mi", 0)
    row["provider_detail_dist_band_5_10"] = dist_band_counts.get("5-10mi", 0)
    row["provider_detail_dist_band_10_plus"] = dist_band_counts.get("10+mi", 0)
    row["provider_detail_dist_band_unknown"] = dist_band_counts.get("unknown", 0)

    # --- Provider shortlist ---
    shortlist_events = [e for e in events if e["event"] == "provider_shortlisted"]
    row["provider_shortlist_interactions"] = len(shortlist_events)

    shortlist_type_counts = Counter()
    for e in shortlist_events:
        types = _safe_json_list(_get_prop(e["properties"], "shortlist_care_types"))
        for t in types:
            shortlist_type_counts[t] += 1

    for ct in CARE_TYPES_ALL:
        row[f"provider_shortlist_{ct}"] = shortlist_type_counts.get(ct, 0)

    # --- Provider zoom ---
    zoom_in_events = [e for e in events if e["event"] == "provider_zoom_in"]
    zoom_out_events = [e for e in events if e["event"] == "provider_zoom_out"]
    all_zoom = zoom_in_events + zoom_out_events

    row["provider_zoom_ins"] = len(zoom_in_events)
    row["provider_zoom_outs"] = len(zoom_out_events)
    row["provider_zoom_keyboard"] = sum(
        1 for e in all_zoom if _get_prop(e["properties"], "source") == "keyboard"
    )
    row["provider_zoom_button"] = sum(
        1 for e in all_zoom if _get_prop(e["properties"], "source") == "button"
    )

    zoom_to_la_events = [e for e in events if e["event"] == "provider_zoom_to_la"]
    row["provider_zoom_to_la"] = len(zoom_to_la_events)

    # --- Provider show more ---
    show_more_events = [e for e in events if e["event"] == "provider_show_more"]
    row["provider_show_more_clicks"] = len(show_more_events)

    pages = []
    for e in show_more_events:
        p = _get_prop(e["properties"], "page")
        if p is not None:
            try:
                pages.append(int(p))
            except (ValueError, TypeError):
                pass
    row["provider_max_page"] = max(pages) if pages else None

    # --- Page navigation ---
    pathnames = set()
    pageview_count = 0
    for e in events:
        if e["event"] == "$pageview":
            pageview_count += 1
        pathname = _get_prop(e["properties"], "$pathname")
        if pathname:
            pathnames.add(pathname)

    row["pages_distinct"] = len(pathnames)
    row["pageviews_total"] = pageview_count
    row["visited_support"] = any(p.startswith("/support") for p in pathnames)
    row["visited_costs"] = any(p.startswith("/costs") for p in pathnames)
    row["visited_providers"] = any(p.startswith("/providers") for p in pathnames)
    row["visited_home"] = "/" in pathnames

    return row


@asset(
    group_name="posthog",
    deps=["posthog_events"],
)
def posthog_sessions(
    context: AssetExecutionContext,
    bsil_postgres: BsilPostgresResource,
):
    """Aggregate PostHog events into session-level features and output Parquet."""
    with bsil_postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT uuid, event, properties, timestamp, distinct_id, session_id "
                "FROM posthog.events ORDER BY session_id, timestamp"
            )
            rows = cur.fetchall()

    context.log.info(f"Loaded {len(rows)} raw events")  # noqa: G004

    # Group by session_id
    sessions: dict[str, list] = {}
    for uuid, event, properties, timestamp, distinct_id, session_id in rows:
        if not session_id:
            continue
        if isinstance(properties, str):
            try:
                properties = json.loads(properties)
            except (json.JSONDecodeError, TypeError):
                properties = {}
        sessions.setdefault(session_id, []).append(
            {
                "uuid": uuid,
                "event": event,
                "properties": properties,
                "timestamp": timestamp,
                "distinct_id": distinct_id,
            }
        )

    context.log.info(f"Grouped into {len(sessions)} sessions")  # noqa: G004

    # Aggregate each session
    feature_rows = []
    for session_events in sessions.values():
        row = _aggregate_session(session_events)
        if row:
            feature_rows.append(row)

    context.log.info(f"Produced {len(feature_rows)} feature rows")  # noqa: G004

    if not feature_rows:
        context.log.warning("No sessions to write")
        return {"sessions": MetadataValue.int(0)}

    # Build columnar data from row dicts
    columns = list(feature_rows[0].keys())
    col_data = {col: [row.get(col) for row in feature_rows] for col in columns}

    # Convert to PyArrow table with appropriate types
    fields = []
    arrays = []
    for col in columns:
        values = col_data[col]
        if col == "session_date":
            arrays.append(pa.array(values, type=pa.date32()))
            fields.append(pa.field(col, pa.date32()))
        elif col in (
            "device_type",
            "referrer_domain",
            "furthest_step_support",
            "furthest_step_costs",
            "lad_codes",
            "lad_mode",
            "iod_deciles",
            "provider_search_lads",
        ):
            arrays.append(pa.array(values, type=pa.string()))
            fields.append(pa.field(col, pa.string()))
        elif col.endswith("_pct") or col in (
            "session_duration_s",
            "iod_decile_mean",
            "iod_decile_median",
            "provider_search_iod_mean",
            "provider_search_iod_median",
        ):
            arrays.append(pa.array(values, type=pa.float64()))
            fields.append(pa.field(col, pa.float64()))
        elif col in (
            "visited_support",
            "visited_costs",
            "visited_providers",
            "visited_home",
        ):
            arrays.append(pa.array(values, type=pa.bool_()))
            fields.append(pa.field(col, pa.bool_()))
        else:
            arrays.append(pa.array(values, type=pa.int64()))
            fields.append(pa.field(col, pa.int64()))

    schema = pa.schema(fields)
    table = pa.table(dict(zip(columns, arrays)), schema=schema)

    output_path = _OUTPUT_DIR / "posthog_sessions.parquet"
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, output_path)

    context.log.info(
        f"Wrote {output_path} ({output_path.stat().st_size / 1024:.1f} KB)"
    )  # noqa: G004

    # Also write to posthog.sessions table (truncate + reload)
    with bsil_postgres.get_connection() as conn:
        with conn.cursor() as cur:
            col_defs = []
            for field in schema:
                if field.type == pa.date32():
                    col_defs.append(f"{field.name} DATE")
                elif field.type == pa.float64():
                    col_defs.append(f"{field.name} DOUBLE PRECISION")
                elif field.type == pa.bool_():
                    col_defs.append(f"{field.name} BOOLEAN")
                elif field.type == pa.string():
                    col_defs.append(f"{field.name} TEXT")
                else:
                    col_defs.append(f"{field.name} BIGINT")

            create_sql = (
                "CREATE TABLE IF NOT EXISTS posthog.sessions (\n  "
                + ",\n  ".join(col_defs)
                + "\n)"
            )
            cur.execute(create_sql)
            cur.execute("TRUNCATE posthog.sessions")

            placeholders = ", ".join(f"%({col})s" for col in columns)
            insert_sql = f"INSERT INTO posthog.sessions ({', '.join(columns)}) VALUES ({placeholders})"  # nosec B608  # noqa: S608
            for row in feature_rows:
                cur.execute(insert_sql, row)
        conn.commit()

    context.log.info(f"Wrote {len(feature_rows)} rows to posthog.sessions")  # noqa: G004

    dates = col_data["session_date"]
    return {
        "sessions": MetadataValue.int(len(feature_rows)),
        "columns": MetadataValue.int(len(columns)),
        "date_range": MetadataValue.text(f"{min(dates)} to {max(dates)}"),
        "output_path": MetadataValue.path(str(output_path)),
    }
