"""Dagster asset for scraping childcare providers from LA FIS websites.

Partitioned by platform type — each partition processes all LAs on that
platform in a single run.
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
from bsil_pipeline.scrapers import classify_la, get_handler
from bsil_pipeline.scrapers.base import ProviderResult
from bsil_pipeline.scrapers.http import ScrapeHTTPError

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
        "council_generic",
        "bath_ne_somerset",
        "south_gloucestershire",
        "bristol_council",
    ]
)

INSERT_SQL = """
INSERT INTO la.scrape_results (
    lad25cd, provider_id, provider_name,
    provider_address_line1, provider_address_line2, provider_address_line3,
    provider_town, provider_postcode, provider_urn,
    provider_phone, provider_email,
    provider_latitude, provider_longitude,
    source_url, raw_html, raw_json, metadata_json, scrape_status
) VALUES (
    %(lad25cd)s, %(provider_id)s, %(provider_name)s,
    %(provider_address_line1)s, %(provider_address_line2)s,
    %(provider_address_line3)s,
    %(provider_town)s, %(provider_postcode)s, %(provider_urn)s,
    %(provider_phone)s, %(provider_email)s,
    %(provider_latitude)s, %(provider_longitude)s,
    %(source_url)s, %(raw_html)s, %(raw_json)s, %(metadata_json)s, %(scrape_status)s
)
ON CONFLICT (lad25cd, provider_id) DO UPDATE SET
    provider_name = EXCLUDED.provider_name,
    provider_address_line1 = EXCLUDED.provider_address_line1,
    provider_address_line2 = EXCLUDED.provider_address_line2,
    provider_address_line3 = EXCLUDED.provider_address_line3,
    provider_town = EXCLUDED.provider_town,
    provider_postcode = EXCLUDED.provider_postcode,
    provider_urn = EXCLUDED.provider_urn,
    provider_phone = EXCLUDED.provider_phone,
    provider_email = EXCLUDED.provider_email,
    provider_latitude = EXCLUDED.provider_latitude,
    provider_longitude = EXCLUDED.provider_longitude,
    source_url = EXCLUDED.source_url,
    raw_html = EXCLUDED.raw_html,
    raw_json = EXCLUDED.raw_json,
    metadata_json = EXCLUDED.metadata_json,
    scrape_status = EXCLUDED.scrape_status,
    scraped_at = now()
"""


def _save_result(conn, result: ProviderResult) -> None:
    """Persist a single provider result to the database."""
    with conn.cursor() as cur:
        cur.execute(INSERT_SQL, result.as_db_row())
    conn.commit()


def _load_existing_provider_ids(conn, lad25cd: str) -> set[str]:
    """Return provider_ids already scraped for this LA."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT provider_id FROM la.scrape_results WHERE lad25cd = %s",
            (lad25cd,),
        )
        return {row[0] for row in cur.fetchall()}


@asset(
    group_name="la",
    deps=[
        "family_information_services",
        "ofsted_inspections",
        "la_scrape_results_table",
    ],
    partitions_def=PLATFORM_PARTITIONS,
    automation_condition=PIPELINE_CONDITION,
)
def la_scrape_results(
    context: AssetExecutionContext, bsil_postgres: BsilPostgresResource
):
    """Scrape childcare providers from LA FIS websites.

    Partitioned by platform type. Each run processes all LAs that use the
    selected platform. Incremental: skips providers already in scrape_results.
    """
    platform_key = context.partition_key
    context.log.info(f"Starting scrape for platform: {platform_key}")

    with bsil_postgres.get_connection() as conn:
        # Load all LAs and filter to this platform partition
        with conn.cursor() as cur:
            cur.execute(
                "SELECT lad25cd, lad25nm, fis_url FROM la.family_information_services"
            )
            all_las = cur.fetchall()

        platform_las = [
            (lad25cd, lad25nm, fis_url)
            for lad25cd, lad25nm, fis_url in all_las
            if classify_la(fis_url, lad25cd) == platform_key
        ]

        if context.run.tags.get("BETA", "").lower() == "true":
            platform_las = [
                (lad25cd, lad25nm, fis_url)
                for lad25cd, lad25nm, fis_url in platform_las
                if lad25cd in BETA_LA_CODES
            ]
            context.log.info(f"BETA=true: filtered to {len(platform_las)} beta LAs")

        context.log.info(f"Found {len(platform_las)} LAs for platform {platform_key}")

        if not platform_las:
            return {
                "la_count": MetadataValue.int(0),
                "provider_count": MetadataValue.int(0),
            }

        # Instantiate the platform handler
        handler = get_handler(platform_key, conn=conn)
        context.log.info(f"Using handler: {handler.__class__.__name__}")

        counts = {
            "success": 0,
            "partial": 0,
            "error": 0,
            "unsupported_platform": 0,
            "ofsted_crossref": 0,
            "skipped_existing": 0,
        }
        total_providers = 0

        for la_idx, (lad25cd, lad25nm, fis_url) in enumerate(platform_las):
            context.log.info(
                f"[{la_idx + 1}/{len(platform_las)}] Scraping {lad25nm} ({lad25cd})"
            )

            existing_ids = _load_existing_provider_ids(conn, lad25cd)
            if existing_ids:
                context.log.info(f"  {len(existing_ids)} providers already scraped")
                counts["skipped_existing"] += len(existing_ids)

            try:
                for result in handler.scrape_la(
                    lad25cd, fis_url, existing_ids, context.log
                ):
                    _save_result(conn, result)
                    total_providers += 1
                    status = result.scrape_status
                    counts[status] = counts.get(status, 0) + 1

                    if total_providers % 100 == 0:
                        context.log.info(
                            f"  Progress: {total_providers} providers saved — {counts}"
                        )
            except ScrapeHTTPError:
                raise
            except Exception as e:
                context.log.error(f"  Handler error for {lad25nm} ({lad25cd}): {e}")

        context.log.info(
            f"Scraping complete for {platform_key}. "
            f"{len(platform_las)} LAs, {total_providers} providers. "
            f"Counts: {counts}"
        )

        return {
            "la_count": MetadataValue.int(len(platform_las)),
            "provider_count": MetadataValue.int(total_providers),
            **{k: MetadataValue.int(v) for k, v in counts.items()},
        }
