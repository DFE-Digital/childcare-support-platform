import re
import time

import requests
from bs4 import BeautifulSoup

from dagster import asset, AssetExecutionContext, MetadataValue

from bsil_pipeline.assets.publish import BETA_LA_CODES
from bsil_pipeline.automation import PIPELINE_CONDITION
from bsil_pipeline.resources.postgres import BsilPostgresResource

RATE_LIMIT_SECONDS = 0.5


POSTCODE_RE = re.compile(r"[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}$", re.IGNORECASE)


def _parse_report_page(html: str, urn: str) -> dict:
    """Parse an Ofsted provider report page for name and address."""
    soup = BeautifulSoup(html, "html.parser")

    result = {
        "provider_name": None,
        "provider_address_line1": None,
        "provider_address_line2": None,
        "provider_address_line3": None,
        "provider_town": None,
        "provider_postcode": None,
        "scrape_status": "error",
    }

    # Check for "cannot publish" message
    page_text = soup.get_text()
    if "We cannot publish" in page_text:
        result["scrape_status"] = "not_published"
        return result

    # Extract name from h1
    h1 = soup.find("h1", class_="heading--title")
    if h1:
        name = h1.get_text(strip=True)
        # Skip if it's just "URN: {urn}" — no real name
        if name and not re.match(rf"^URN:\s*{urn}$", name, re.IGNORECASE):
            result["provider_name"] = name

    # Extract address
    address_el = soup.find("address", class_="title-block__address")
    if address_el:
        address_text = address_el.get_text(strip=True)
        parts = [p.strip() for p in address_text.split(",") if p.strip()]

        if parts:
            # Check if last part is a postcode
            postcode_match = POSTCODE_RE.search(parts[-1])
            if postcode_match:
                result["provider_postcode"] = parts[-1].strip()
                parts = parts[:-1]

            # Town is the last remaining part
            if parts:
                result["provider_town"] = parts[-1]
                parts = parts[:-1]

            # Remaining parts are address lines
            if len(parts) >= 1:
                result["provider_address_line1"] = parts[0]
            if len(parts) >= 2:
                result["provider_address_line2"] = parts[1]
            if len(parts) >= 3:
                result["provider_address_line3"] = parts[2]

    if result["provider_name"] or result["provider_postcode"]:
        if result["provider_name"] and result["provider_postcode"]:
            result["scrape_status"] = "success"
        else:
            result["scrape_status"] = "partial"
    else:
        result["scrape_status"] = "not_published"

    return result


@asset(
    group_name="ofsted",
    deps=["ofsted_inspections", "ofsted_scrape_results_table"],
    automation_condition=PIPELINE_CONDITION,
)
def ofsted_scrape_results(
    context: AssetExecutionContext, bsil_postgres: BsilPostgresResource
):
    """Scrape Ofsted web reports for REDACTED provider details.

    Incremental: skips URNs already in scrape_results.
    Rate-limited to one request per 0.5 seconds.
    """
    beta_only = context.run.tags.get("BETA", "").lower() == "true"

    with bsil_postgres.get_connection() as conn:
        with conn.cursor() as cur:
            if beta_only:
                # Resolve BETA_LA_CODES to Ofsted local_authority names
                cur.execute(
                    """SELECT la_name FROM os.la_name_lookup
                       WHERE geo_code = ANY(%s)""",
                    (list(BETA_LA_CODES),),
                )
                beta_la_names = [row[0] for row in cur.fetchall()]
                if not beta_la_names:
                    context.log.warning(
                        "BETA=true but os.la_name_lookup has no rows for "
                        "beta LA codes — run os_bounding_boxes asset first. "
                        "Proceeding without LA filter."
                    )
                    beta_only = False
                else:
                    context.log.info(
                        f"BETA=true: filtering to {len(beta_la_names)} "
                        f"LA names: {beta_la_names}"
                    )

            # Find REDACTED rows not yet scraped
            if beta_only:
                cur.execute(
                    """SELECT i.provider_urn, i.web_link
                       FROM ofsted.inspections i
                       LEFT JOIN ofsted.scrape_results sr
                           ON i.provider_urn = sr.provider_urn
                       WHERE i.provider_name = 'REDACTED'
                         AND sr.provider_urn IS NULL
                         AND i.local_authority = ANY(%s)
                       ORDER BY i.provider_urn""",
                    (beta_la_names,),
                )
            else:
                cur.execute("""
                    SELECT i.provider_urn, i.web_link
                    FROM ofsted.inspections i
                    LEFT JOIN ofsted.scrape_results sr
                        ON i.provider_urn = sr.provider_urn
                    WHERE i.provider_name = 'REDACTED'
                      AND sr.provider_urn IS NULL
                    ORDER BY i.provider_urn
                """)
            rows = cur.fetchall()

        context.log.info(f"Found {len(rows)} REDACTED rows to scrape")

        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": "BSIL-DataPipeline/1.0 (research; best-start-in-life)",
            }
        )

        counts = {"success": 0, "partial": 0, "not_published": 0, "error": 0}

        for idx, (urn, web_link) in enumerate(rows):
            if not web_link:
                _save_result(
                    conn,
                    urn,
                    {
                        "provider_name": None,
                        "provider_address_line1": None,
                        "provider_address_line2": None,
                        "provider_address_line3": None,
                        "provider_town": None,
                        "provider_postcode": None,
                        "scrape_status": "error",
                    },
                )
                counts["error"] += 1
                continue

            try:
                resp = session.get(web_link, timeout=15, allow_redirects=True)
                resp.raise_for_status()
                result = _parse_report_page(resp.text, urn)
            except Exception as e:
                context.log.warning(f"URN {urn}: request failed — {e}")
                result = {
                    "provider_name": None,
                    "provider_address_line1": None,
                    "provider_address_line2": None,
                    "provider_address_line3": None,
                    "provider_town": None,
                    "provider_postcode": None,
                    "scrape_status": "error",
                }

            _save_result(conn, urn, result)
            counts[result["scrape_status"]] += 1

            if (idx + 1) % 100 == 0:
                context.log.info(
                    f"Progress: {idx + 1}/{len(rows)} — counts so far: {counts}"
                )

            time.sleep(RATE_LIMIT_SECONDS)

    context.log.info(f"Scraping complete. Final counts: {counts}")
    return {k: MetadataValue.int(v) for k, v in counts.items()}


def _save_result(conn, urn: str, result: dict) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ofsted.scrape_results (
                provider_urn, provider_name,
                provider_address_line1, provider_address_line2, provider_address_line3,
                provider_town, provider_postcode, scrape_status
            ) VALUES (
                %(urn)s, %(provider_name)s,
                %(provider_address_line1)s, %(provider_address_line2)s,
                %(provider_address_line3)s,
                %(provider_town)s, %(provider_postcode)s, %(scrape_status)s
            )
            ON CONFLICT (provider_urn) DO NOTHING
            """,
            {"urn": urn, **result},
        )
    conn.commit()
