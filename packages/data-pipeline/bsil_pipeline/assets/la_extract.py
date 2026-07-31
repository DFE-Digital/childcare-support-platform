"""Dagster asset for extracting structured fields from raw scrape data.

Partitioned by platform type — mirrors la_scraper.py. Each partition reads
all raw_html/raw_json rows for that platform from la.scrape_results and
runs the platform extractor to produce structured records in la.extract_results.
"""

from dagster import (
    asset,
    AssetExecutionContext,
    MetadataValue,
    StaticPartitionsDefinition,
)

from bsil_pipeline.assets.publish import BETA_LA_CODES
from bsil_pipeline.automation import PIPELINE_CONDITION
from bsil_pipeline.resources.postgres import BsilPostgresResource
from bsil_pipeline.extractors import (
    get_extractor,
    has_extractor,
    PLATFORMS_WITHOUT_RAW_DATA,
)
from bsil_pipeline.extractors.base import infer_classification_from_name
from collections import Counter
from urllib.parse import urlparse

from bsil_pipeline.scrapers import classify_la
from bsil_pipeline.utils.postcode_lookup import postcode_to_lad, coords_to_lad

# Shared-platform scrapers that cache all providers and broadcast to every
# LA.  These need DISTINCT ON (provider_id) to deduplicate, and postcode/
# coordinate resolution to assign the correct LA.
SHARED_PLATFORMS = {
    "devon",
    "essex",
    "surrey",
    "familysupportni",
    "marketplace",
    "synergy",
}

# Same partitions as la_scraper (minus council_generic which has no raw data).
PLATFORM_PARTITIONS = StaticPartitionsDefinition(
    [
        "openobjects_kb5",
        "synergy",
        "fis_wales",
        "familysupportni",
        "afc",
        "jadu",
        "surrey",
        "essex",
        "devon",
        "marketplace",
        "fid",
        "hartlepool",
        "pcg",
        "liquidlogic",
        "lambeth",
        "localgov_drupal",
        "somerset",
        "nelincs",
        "oldham",
        "eastayrshire",
        "cne_siar",
        "blackpool",
        "northyorks",
        "bath_ne_somerset",
        "south_gloucestershire",
        "bristol_council",
    ]
)

INSERT_SQL = """
INSERT INTO la.extract_results (
    lad25cd, provider_id, platform,
    extracted_data, classification, source_classification,
    field_count, extraction_warnings, lad_source
) VALUES (
    %(lad25cd)s, %(provider_id)s, %(platform)s,
    %(extracted_data)s::jsonb, %(classification)s, %(source_classification)s,
    %(field_count)s, %(extraction_warnings)s, %(lad_source)s
)
ON CONFLICT (lad25cd, provider_id) DO UPDATE SET
    platform = EXCLUDED.platform,
    extracted_data = EXCLUDED.extracted_data,
    classification = EXCLUDED.classification,
    source_classification = EXCLUDED.source_classification,
    field_count = EXCLUDED.field_count,
    extraction_warnings = EXCLUDED.extraction_warnings,
    lad_source = EXCLUDED.lad_source,
    extracted_at = now()
"""


def _save_batch(conn, batch: list[dict]) -> None:
    """Persist a batch of extraction results to the database."""
    with conn.cursor() as cur:
        for row in batch:
            cur.execute(INSERT_SQL, row)
    conn.commit()


@asset(
    group_name="la",
    deps=["la_scrape_results", "la_extract_results_table", "postcode_lookup"],
    partitions_def=PLATFORM_PARTITIONS,
    automation_condition=PIPELINE_CONDITION,
)
def la_extract_results(
    context: AssetExecutionContext, bsil_postgres: BsilPostgresResource
):
    """Extract structured fields from raw scrape data.

    Partitioned by platform type. Each run processes all providers on the
    selected platform, re-parsing their raw_html/raw_json into structured
    JSONB records.
    """
    platform_key = context.partition_key
    context.log.info(f"Starting extraction for platform: {platform_key}")

    if platform_key in PLATFORMS_WITHOUT_RAW_DATA:
        context.log.info(f"Platform {platform_key} has no raw data — skipping")
        return {"provider_count": MetadataValue.int(0)}

    if not has_extractor(platform_key):
        context.log.warning(f"No extractor registered for {platform_key} — skipping")
        return {"provider_count": MetadataValue.int(0)}

    extractor = get_extractor(platform_key)
    context.log.info(f"Using extractor: {extractor.__class__.__name__}")

    with bsil_postgres.get_connection() as conn:
        is_shared = platform_key in SHARED_PLATFORMS

        # Find all LAs on this platform
        with conn.cursor() as cur:
            cur.execute(
                "SELECT lad25cd, lad25nm, fis_url FROM la.family_information_services"
            )
            all_las = cur.fetchall()

        platform_lad_codes = {
            lad25cd
            for lad25cd, _lad25nm, fis_url in all_las
            if classify_la(fis_url, lad25cd) == platform_key
        }

        if context.run.tags.get("BETA", "").lower() == "true":
            platform_lad_codes = platform_lad_codes & BETA_LA_CODES
            context.log.info(
                f"BETA=true: filtered to {len(platform_lad_codes)} beta LAs"
            )

        context.log.info(
            f"Found {len(platform_lad_codes)} LAs for platform {platform_key}"
        )

        if not platform_lad_codes:
            return {
                "la_count": MetadataValue.int(0),
                "provider_count": MetadataValue.int(0),
            }

        # Count rows first (cheap — no raw data loaded)
        placeholders = ",".join(["%s"] * len(platform_lad_codes))
        lad_tuple = tuple(platform_lad_codes)

        _where = (
            f" WHERE lad25cd IN ({placeholders})"  # nosec B608
            " AND scrape_status IN ('success', 'partial')"
            " AND (raw_html IS NOT NULL OR raw_json IS NOT NULL)"
        )

        # For multi-platform LAs, restrict to scrape results from this
        # platform's domain so partitions don't cross-contaminate.
        la_platform_count = Counter(lad for lad, _, _ in all_las)
        multi_platform_lads = {
            lad for lad, count in la_platform_count.items() if count > 1
        }
        for lad25cd, _nm, fis_url in all_las:
            if (
                lad25cd in (multi_platform_lads & platform_lad_codes)
                and classify_la(fis_url, lad25cd) == platform_key
            ):
                domain = urlparse(fis_url).hostname
                _where += " AND (lad25cd != %s OR source_url LIKE %s)"  # nosec B608
                lad_tuple = lad_tuple + (lad25cd, f"%{domain}%")

        # SQL expression for source URL domain — used to scope provider_id
        # dedup to the same instance (prevents collisions across e.g.
        # separate Synergy sites that reuse the same ID sequences).
        _domain = "substring(source_url from 'https?://([^/]+)')"

        if is_shared:
            count_sql = (
                "SELECT COUNT(*) FROM ("  # nosec B608
                f" SELECT DISTINCT ON ({_domain}, provider_id) provider_id"
                f" FROM la.scrape_results{_where}"
                f" ORDER BY {_domain}, provider_id) sub"
            )
        else:
            count_sql = f"SELECT COUNT(*) FROM la.scrape_results{_where}"  # nosec B608

        with conn.cursor() as cur:
            cur.execute(count_sql, lad_tuple)
            total_rows = cur.fetchone()[0]

        context.log.info(
            f"Found {total_rows} providers with raw data to extract"
            + (" (deduplicated)" if is_shared else "")
        )

        counts = {
            "extracted": 0,
            "warnings": 0,
            "errors": 0,
            "resolved_postcode": 0,
            "resolved_coords": 0,
            "unresolved": 0,
        }

        # Stream rows via server-side cursor to avoid loading all raw HTML
        # into memory at once (openobjects_kb5 alone is 50k+ rows of HTML).
        # Use a second connection for writes so commits don't close the
        # server-side cursor on the read connection.
        BATCH_SIZE = 200

        if is_shared:
            query = (
                f"SELECT DISTINCT ON ({_domain}, provider_id)"  # nosec B608
                " lad25cd, provider_id, provider_name, raw_html, raw_json,"
                " metadata_json, source_url"
                f" FROM la.scrape_results{_where}"
                f" ORDER BY {_domain}, provider_id, lad25cd"
            )
        else:
            query = (
                "SELECT lad25cd, provider_id, provider_name, raw_html, raw_json,"  # nosec B608
                " metadata_json, source_url"
                f" FROM la.scrape_results{_where}"
            )
        with bsil_postgres.get_connection() as write_conn:
            with conn.cursor(name="extract_cursor") as cur:
                cur.itersize = BATCH_SIZE
                cur.execute(query, lad_tuple)
                write_batch: list[dict] = []
                for (
                    lad25cd,
                    provider_id,
                    provider_name,
                    raw_html,
                    raw_json,
                    metadata_json,
                    source_url,
                ) in cur:
                    try:
                        result = extractor.extract(
                            lad25cd=lad25cd,
                            provider_id=provider_id,
                            raw_html=raw_html,
                            raw_json=raw_json,
                            metadata_json=metadata_json,
                            provider_name=provider_name,
                        )
                        if source_url and not result.extracted_data.get("fis_url"):
                            result.extracted_data["fis_url"] = source_url
                        # Fallback: infer classification from provider name
                        if not result.classification:
                            inferred = infer_classification_from_name(
                                result.extracted_data.get("provider_name")
                            )
                            if inferred:
                                result.classification = inferred
                                result.extraction_warnings.append(
                                    "classification_inferred_from_name"
                                )
                        db_row = result.as_db_row()
                        db_row["platform"] = platform_key

                        # Resolve LA from extracted postcode / coordinates
                        ed = result.extracted_data
                        resolved_lad = None
                        lad_source = "scraper_assigned"

                        pc = ed.get("postcode")
                        if pc:
                            resolved_lad = postcode_to_lad(pc)
                            if resolved_lad:
                                lad_source = "postcode_lookup"

                        if not resolved_lad:
                            lat = ed.get("latitude")
                            lon = ed.get("longitude")
                            if lat is not None and lon is not None:
                                try:
                                    resolved_lad = coords_to_lad(
                                        float(lat),
                                        float(lon),
                                        platform_lad_codes,
                                    )
                                    if resolved_lad:
                                        lad_source = "coords_lookup"
                                except (ValueError, TypeError):
                                    pass

                        if resolved_lad:
                            db_row["lad25cd"] = resolved_lad
                        elif is_shared:
                            # Shared platform, can't resolve — mark as
                            # unresolved but still store with the original
                            # scrape lad25cd.
                            lad_source = "unresolved"
                            counts["unresolved"] += 1

                        db_row["lad_source"] = lad_source
                        if lad_source == "postcode_lookup":
                            counts["resolved_postcode"] += 1
                        elif lad_source == "coords_lookup":
                            counts["resolved_coords"] += 1

                        write_batch.append(db_row)
                        counts["extracted"] += 1
                        if result.extraction_warnings:
                            counts["warnings"] += 1
                    except Exception as e:
                        context.log.error(
                            f"Extraction error for {lad25cd}/{provider_id}: {e}"
                        )
                        counts["errors"] += 1

                    if len(write_batch) >= BATCH_SIZE:
                        _save_batch(write_conn, write_batch)
                        write_batch = []

                    processed = counts["extracted"] + counts["errors"]
                    if processed % 500 == 0:
                        context.log.info(
                            f"  Progress: {processed}/{total_rows} providers — {counts}"
                        )

                # Flush remaining rows
                if write_batch:
                    _save_batch(write_conn, write_batch)

        context.log.info(
            f"Extraction complete for {platform_key}. "
            f"{len(platform_lad_codes)} LAs, {total_rows} providers. "
            f"Counts: {counts}"
        )

        return {
            "la_count": MetadataValue.int(len(platform_lad_codes)),
            "provider_count": MetadataValue.int(total_rows),
            **{k: MetadataValue.int(v) for k, v in counts.items()},
        }
