import os
import time

from dagster import asset, AssetExecutionContext, MetadataValue

from bsil_pipeline.assets._geocode_helpers import (
    bbox_fallback,
    build_query,
    geocode,
    make_session,
    RATE_LIMIT_SECONDS,
)
from bsil_pipeline.assets.publish import BETA_LA_CODES
from bsil_pipeline.automation import PIPELINE_CONDITION
from bsil_pipeline.resources.postgres import BsilPostgresResource


ADDRESS_COLS = [
    "provider_address_line_1",
    "provider_address_line_2",
    "provider_address_line_3",
    "provider_town",
    "provider_postcode",
]


def _build_query(row: dict) -> str | None:
    """Build an address query string from non-REDACTED address fields.

    Returns None when only a postcode is available — a bare postcode is not
    sufficient for the OS Places find API (it would just return the centroid).
    These postcode-only cases fall through the Places API stage and get
    geocoded to a bounding box later in the pipeline via bbox_fallback().
    """
    address_parts = [row.get(col, "") for col in ADDRESS_COLS[:-1]]
    has_address = any(
        p and p.strip() and p.strip().upper() != "REDACTED" for p in address_parts
    )
    if not has_address:
        return None
    return build_query(address_parts + [row.get(ADDRESS_COLS[-1], "")])


def _save_result(
    conn, urn: str, row: dict, query: str | None, geocode_result: dict
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO os.ofsted_places (
                provider_urn,
                provider_address_line_1, provider_address_line_2, provider_address_line_3,
                provider_town, provider_postcode,
                query_used, latitude, longitude, geocode_status,
                bbox_geo_type, bbox_geo_code
            ) VALUES (
                %(urn)s,
                %(provider_address_line_1)s, %(provider_address_line_2)s,
                %(provider_address_line_3)s,
                %(provider_town)s, %(provider_postcode)s,
                %(query_used)s, %(latitude)s, %(longitude)s, %(geocode_status)s,
                %(bbox_geo_type)s, %(bbox_geo_code)s
            )
            ON CONFLICT (provider_urn) DO UPDATE SET
                geocode_status = EXCLUDED.geocode_status,
                latitude = EXCLUDED.latitude,
                longitude = EXCLUDED.longitude,
                bbox_geo_type = EXCLUDED.bbox_geo_type,
                bbox_geo_code = EXCLUDED.bbox_geo_code,
                query_used = EXCLUDED.query_used,
                geocoded_at = now()
            """,
            {
                "urn": urn,
                "provider_address_line_1": row.get("provider_address_line_1"),
                "provider_address_line_2": row.get("provider_address_line_2"),
                "provider_address_line_3": row.get("provider_address_line_3"),
                "provider_town": row.get("provider_town"),
                "provider_postcode": row.get("provider_postcode"),
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
    deps=[
        "ofsted_inspections",
        "ofsted_scrape_results",
        "ofsted_consented_addresses",
        "family_information_services",
        "os_bounding_boxes",
        "os_ofsted_places_table",
    ],
    automation_condition=PIPELINE_CONDITION,
)
def ofsted_places_geocode(
    context: AssetExecutionContext, bsil_postgres: BsilPostgresResource
):
    """Geocode Ofsted provider addresses via Ordnance Survey Places API.

    COALESCEs address data from ofsted.scrape_results (real addresses for
    REDACTED providers) with ofsted.inspections data.

    After API failure, falls back to bounding-box assignment from
    os.bounding_boxes (postcode → district → LA code → LA name → county).
    Uses the local_authority field from inspections for LA name lookup
    so even fully-REDACTED providers get at least an LA/county bbox.

    Incremental with upsert: re-runs can upgrade no_results → bbox_*.
    Rate-limited to ~6.6 requests/second.
    """
    api_key = os.environ.get("ORDINANCE_SURVEY_API_KEY", "")
    if not api_key:
        context.log.error("ORDINANCE_SURVEY_API_KEY not set — aborting")
        return {"error": MetadataValue.text("ORDINANCE_SURVEY_API_KEY not set")}

    is_beta = context.run.tags.get("BETA", "").lower() == "true"

    with bsil_postgres.get_connection() as conn:
        with conn.cursor() as cur:
            # Find rows that haven't been geocoded or previously failed.
            # COALESCE with scrape_results to get real addresses for REDACTED providers.
            # Note: scrape_results uses provider_address_line1 (no underscore before number)
            # vs inspections uses provider_address_line_1 (with underscore).
            beta_clause = ""
            params: list[str] = []
            if is_beta:
                codes = sorted(BETA_LA_CODES)
                placeholders = ", ".join(["%s"] * len(codes))
                beta_clause = f"AND lnl.geo_code IN ({placeholders})"
                params = codes
                context.log.info(f"BETA=true: restricting to {len(codes)} beta LAs")

            query = """
                SELECT
                    i.provider_urn,
                    COALESCE(NULLIF(sr.provider_address_line1, ''), NULLIF(ca.address_line_1, ''), NULLIF(i.provider_address_line_1, 'REDACTED')) as provider_address_line_1,
                    COALESCE(NULLIF(sr.provider_address_line2, ''), NULLIF(ca.address_line_2, ''), NULLIF(i.provider_address_line_2, 'REDACTED')) as provider_address_line_2,
                    COALESCE(NULLIF(sr.provider_address_line3, ''), NULLIF(ca.address_line_3, ''), NULLIF(i.provider_address_line_3, 'REDACTED')) as provider_address_line_3,
                    COALESCE(NULLIF(sr.provider_town, ''), NULLIF(ca.town, ''), NULLIF(i.provider_town, 'REDACTED')) as provider_town,
                    COALESCE(NULLIF(sr.provider_postcode, ''), NULLIF(ca.postcode, ''), NULLIF(i.provider_postcode, 'REDACTED')) as provider_postcode,
                    i.local_authority
                FROM ofsted.inspections i
                LEFT JOIN ofsted.scrape_results sr ON i.provider_urn = sr.provider_urn
                LEFT JOIN ofsted.consented_addresses ca ON i.provider_urn = ca.provider_urn
                LEFT JOIN os.ofsted_places p ON i.provider_urn = p.provider_urn
                WHERE
                    (p.provider_urn IS NULL
                     OR p.geocode_status IN ('no_results', 'insufficient_address'))
                    AND EXISTS (
                        SELECT 1 FROM os.la_name_lookup lnl
                        JOIN la.family_information_services fis
                          ON fis.lad25cd = lnl.geo_code
                        WHERE lnl.la_name = i.local_authority
                        {beta_clause}
                    )
                ORDER BY i.provider_urn
            """.replace("{beta_clause}", beta_clause)  # nosec B608
            cur.execute(query, params)
            rows = cur.fetchall()
            col_names = [desc[0] for desc in cur.description]

        context.log.info(f"Found {len(rows)} rows to geocode")

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
            "bbox_county": 0,
        }

        for idx, raw_row in enumerate(rows):
            if (idx + 1) % 100 == 0:
                context.log.info(
                    f"Progress: {idx + 1}/{len(rows)} — counts so far: {counts}"
                )

            row = dict(zip(col_names, raw_row))
            urn = row["provider_urn"]
            postcode = row.get("provider_postcode")

            query = _build_query(row)

            la_name = row.get("local_authority")

            if not query:
                # No address — try bbox fallback directly (no lad25cd for Ofsted)
                fallback = bbox_fallback(conn, postcode, None, la_name=la_name)
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
                _save_result(conn, urn, row, query, geocode_result)
                counts[geocode_result["geocode_status"]] = (
                    counts.get(geocode_result["geocode_status"], 0) + 1
                )
                continue

            geocode_result = geocode(session, api_key, query, postcode, log=context.log)

            # Log the first error for visibility
            if geocode_result.get("_error") and counts["api_error"] == 0:
                context.log.warning(f"First API error: {geocode_result['_error']}")
            geocode_result.pop("_error", None)

            # If API returned no result, try bbox fallback (no lad25cd for Ofsted)
            if geocode_result["geocode_status"] in (
                "no_results",
                "api_error",
                "insufficient_address",
            ):
                fallback = bbox_fallback(conn, postcode, None, la_name=la_name)
                if fallback:
                    geocode_result.update(fallback)

            _save_result(conn, urn, row, query, geocode_result)
            counts[geocode_result["geocode_status"]] = (
                counts.get(geocode_result["geocode_status"], 0) + 1
            )

            # Fail fast if first 10 API calls all error (likely auth issue)
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

            time.sleep(RATE_LIMIT_SECONDS)

    context.log.info(f"Geocoding complete. Final counts: {counts}")
    return {k: MetadataValue.int(v) for k, v in counts.items()}
