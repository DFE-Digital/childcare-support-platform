"""Geocode LA extract_results providers via OS Places API.

Geocodes providers that have no lat/lon already in their extracted_data
(many platforms supply coordinates directly). After API failure, falls
back to bounding-box assignment from os.bounding_boxes.
Results go to os.la_places with composite PK (lad25cd, provider_id).
"""

import json
import os
import time

from dagster import asset, AssetExecutionContext, MetadataValue

from bsil_pipeline.automation import PIPELINE_CONDITION
from bsil_pipeline.resources.postgres import BsilPostgresResource
from bsil_pipeline.assets._geocode_helpers import (
    bbox_fallback,
    build_query,
    geocode,
    make_session,
    RATE_LIMIT_SECONDS,
)


EXTRACT_FIELDS_SQL = """
    SELECT
        e.lad25cd,
        e.provider_id,
        e.extracted_data
    FROM la.extract_results e
    LEFT JOIN os.la_places p
        ON e.lad25cd = p.lad25cd AND e.provider_id = p.provider_id
    WHERE
        (p.lad25cd IS NULL
         OR p.geocode_status IN ('no_results', 'insufficient_address'))
        AND (
            e.extracted_data->>'latitude' IS NULL
            OR e.extracted_data->>'latitude' = ''
        )
    ORDER BY e.lad25cd, e.provider_id
"""


def _build_query_from_extracted(data: dict) -> str | None:
    """Build address query from extracted_data JSONB fields.

    Returns None when only a postcode is available — a bare postcode is not
    sufficient for the OS Places find API (it would just return the centroid).
    These postcode-only cases fall through the Places API stage and get
    geocoded to a bounding box later in the pipeline via bbox_fallback().
    """
    address_parts = [
        data.get("address_line1", ""),
        data.get("address_line2", ""),
        data.get("address_line3", ""),
        data.get("town", ""),
    ]
    has_address = any(
        p and p.strip() and p.strip().upper() != "REDACTED" for p in address_parts
    )
    if not has_address:
        return None
    return build_query(address_parts + [data.get("postcode", "")])


def _save_result(
    conn,
    lad25cd: str,
    provider_id: str,
    data: dict,
    query: str | None,
    geocode_result: dict,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO os.la_places (
                lad25cd, provider_id,
                address_line1, address_line2, address_line3,
                town, postcode,
                query_used, latitude, longitude, geocode_status,
                bbox_geo_type, bbox_geo_code
            ) VALUES (
                %(lad25cd)s, %(provider_id)s,
                %(address_line1)s, %(address_line2)s, %(address_line3)s,
                %(town)s, %(postcode)s,
                %(query_used)s, %(latitude)s, %(longitude)s, %(geocode_status)s,
                %(bbox_geo_type)s, %(bbox_geo_code)s
            )
            ON CONFLICT (lad25cd, provider_id) DO UPDATE SET
                geocode_status = EXCLUDED.geocode_status,
                latitude = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude,
                bbox_geo_type = EXCLUDED.bbox_geo_type,
                bbox_geo_code = EXCLUDED.bbox_geo_code,
                query_used = EXCLUDED.query_used,
                geocoded_at = now()
            """,
            {
                "lad25cd": lad25cd,
                "provider_id": provider_id,
                "address_line1": data.get("address_line1"),
                "address_line2": data.get("address_line2"),
                "address_line3": data.get("address_line3"),
                "town": data.get("town"),
                "postcode": data.get("postcode"),
                "query_used": query,
                "latitude": geocode_result.get("latitude"),
                "longitude": geocode_result.get("longitude"),
                "geocode_status": geocode_result["geocode_status"],
                "bbox_geo_type": geocode_result.get("bbox_geo_type"),
                "bbox_geo_code": geocode_result.get("bbox_geo_code"),
            },
        )
    conn.commit()


@asset(
    group_name="os",
    deps=["la_extract_results", "os_bounding_boxes", "os_la_places_table"],
    automation_condition=PIPELINE_CONDITION,
)
def la_places_geocode(
    context: AssetExecutionContext, bsil_postgres: BsilPostgresResource
):
    """Geocode LA provider addresses via Ordnance Survey Places API.

    Reads from la.extract_results — providers without existing lat/lon in
    their extracted_data that either haven't been geocoded or previously
    failed (no_results / insufficient_address).

    After API failure, falls back to bounding-box assignment from
    os.bounding_boxes (postcode → district → LA).

    Incremental with upsert: re-runs can upgrade no_results → bbox_*.
    Rate-limited to ~6.6 requests/second.
    """
    api_key = os.environ.get("ORDINANCE_SURVEY_API_KEY", "")
    if not api_key:
        context.log.error("ORDINANCE_SURVEY_API_KEY not set — aborting")
        return {"error": MetadataValue.text("ORDINANCE_SURVEY_API_KEY not set")}

    with bsil_postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(EXTRACT_FIELDS_SQL)
            rows = cur.fetchall()

        context.log.info(f"Found {len(rows)} LA providers to geocode")

        session = make_session()

        counts = {
            "success": 0,
            "success_postcode_fallback": 0,
            "success_postcode_override": 0,
            "no_results": 0,
            "insufficient_address": 0,
            "api_error": 0,
            "bbox_postcode": 0,
            "bbox_postcode_district": 0,
            "bbox_local_authority": 0,
        }

        for idx, (lad25cd, provider_id, extracted_data) in enumerate(rows):
            if isinstance(extracted_data, str):
                extracted_data = json.loads(extracted_data)

            postcode = extracted_data.get("postcode")
            query = _build_query_from_extracted(extracted_data)

            if not query:
                # No address to query API — try bbox fallback directly
                fallback = bbox_fallback(conn, postcode, lad25cd)
                if fallback:
                    geocode_result = {
                        "latitude": None,
                        "longitude": None,
                        **fallback,
                    }
                else:
                    geocode_result = {
                        "latitude": None,
                        "longitude": None,
                        "geocode_status": "insufficient_address",
                    }
                _save_result(
                    conn, lad25cd, provider_id, extracted_data, query, geocode_result
                )
                counts[geocode_result["geocode_status"]] = (
                    counts.get(geocode_result["geocode_status"], 0) + 1
                )
                continue

            geocode_result = geocode(session, api_key, query, postcode, log=context.log)

            if geocode_result.get("_error") and counts["api_error"] == 0:
                context.log.warning(f"First API error: {geocode_result['_error']}")
            geocode_result.pop("_error", None)

            # If API returned no result, try bbox fallback
            if geocode_result["geocode_status"] in (
                "no_results",
                "api_error",
                "insufficient_address",
            ):
                fallback = bbox_fallback(conn, postcode, lad25cd)
                if fallback:
                    geocode_result.update(fallback)
                    # lat/lon stay None — bbox IS the spatial representation

            _save_result(
                conn, lad25cd, provider_id, extracted_data, query, geocode_result
            )
            counts[geocode_result["geocode_status"]] = (
                counts.get(geocode_result["geocode_status"], 0) + 1
            )

            # Fail fast if first 10 API calls all error
            api_attempts = (
                counts["success"]
                + counts["success_postcode_fallback"]
                + counts["no_results"]
                + counts["api_error"]
            )
            if api_attempts == 10 and counts["api_error"] == 10:
                context.log.error(
                    "First 10 API calls all failed — aborting (check ORDINANCE_SURVEY_API_KEY)"
                )
                break

            if (idx + 1) % 100 == 0:
                context.log.info(
                    f"Progress: {idx + 1}/{len(rows)} — counts so far: {counts}"
                )

            time.sleep(RATE_LIMIT_SECONDS)

    context.log.info(f"LA geocoding complete. Final counts: {counts}")
    return {k: MetadataValue.int(v) for k, v in counts.items()}
