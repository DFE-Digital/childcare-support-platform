"""Na h-Eileanan Siar (CnES) nursery directory scraper.

Covers 1 LA using a LocalGov Drupal site where JSON:API is not exposed:
- www.cne-siar.gov.uk (Na h-Eileanan Siar, S12000013)

Server-side rendered HTML — requests + BeautifulSoup.

Endpoints:
  /education-and-learning/early-years/nursery-directory?page={N}  — listing (12/page)
  /education-and-learning/early-years/nursery-directory/{slug}    — provider detail
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Iterator

import requests
from bs4 import BeautifulSoup

from bsil_pipeline.scrapers.base import (
    BaseScraper,
    ProviderResult,
    clean_text,
)
from bsil_pipeline.scrapers.http import fetch
from bsil_pipeline.scrapers.rate_limiter import DomainRateLimiter

if TYPE_CHECKING:
    from logging import Logger

_BASE_URL = "https://www.cne-siar.gov.uk"
_LISTING_PATH = "/education-and-learning/early-years/nursery-directory"
_USER_AGENT = "BSIL-DataPipeline/1.0 (research; best-start-in-life)"
_REQUEST_TIMEOUT = 30
_rate_limiter = DomainRateLimiter(default_interval=1.0)

# Match detail links under the nursery-directory path
_DETAIL_HREF_RE = re.compile(
    r"/education-and-learning/early-years/nursery-directory/([^/?#]+)"
)


class CneSiarScraper(BaseScraper):
    @property
    def platform_key(self) -> str:
        return "cne_siar"

    def scrape_la(
        self,
        lad25cd: str,
        fis_url: str,
        existing_provider_ids: set[str],
        logger: Logger,
    ) -> Iterator[ProviderResult]:
        session = requests.Session()
        session.headers.update({"User-Agent": _USER_AGENT})

        # Step 1: Collect all provider links from paginated listing
        all_links: list[tuple[str, str]] = []  # (slug, detail_path)
        page_no = 0

        while True:
            page_links = _fetch_listing_page(session, page_no, logger)

            if not page_links:
                break

            all_links.extend(page_links)
            logger.info(
                f"CnES: page {page_no} -> {len(page_links)} providers "
                f"({len(all_links)} total)"
            )
            page_no += 1

        logger.info(f"CnES: {len(all_links)} total provider links found")

        # Step 2: Filter out existing providers
        new_links = [
            (slug, path)
            for slug, path in all_links
            if slug not in existing_provider_ids
        ]
        logger.info(
            f"CnES: {len(new_links)} new providers to process "
            f"({len(existing_provider_ids)} already exist)"
        )

        # Step 3: Fetch each provider detail page
        yielded = 0
        for slug, detail_path in new_links:
            detail_url = f"{_BASE_URL}{detail_path}"
            result = _fetch_provider_detail(session, lad25cd, slug, detail_url, logger)
            yield result
            yielded += 1

        logger.info(f"CnES: yielded {yielded} providers for {lad25cd}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _fetch_listing_page(
    session: requests.Session,
    page_no: int,
    logger: Logger,
) -> list[tuple[str, str]]:
    """Fetch a single listing page.

    Returns list of (slug, detail_path). Raises ScrapeHTTPError on failure.
    """
    if page_no == 0:
        url = f"{_BASE_URL}{_LISTING_PATH}"
    else:
        url = f"{_BASE_URL}{_LISTING_PATH}?page={page_no}"

    resp = fetch(session, url, timeout=_REQUEST_TIMEOUT, rate_limiter=_rate_limiter)
    soup = BeautifulSoup(resp.text, "html.parser")

    # Extract provider links from views-row cards
    links: list[tuple[str, str]] = []
    seen_slugs: set[str] = set()

    for row in soup.find_all("div", class_="views-row"):
        a_tag = row.find("a", href=True)
        if not a_tag:
            continue
        href = a_tag["href"]
        match = _DETAIL_HREF_RE.search(href)
        if match:
            slug = match.group(1)
            if slug not in seen_slugs:
                seen_slugs.add(slug)
                links.append((slug, href))

    return links


def _fetch_provider_detail(
    session: requests.Session,
    lad25cd: str,
    provider_id: str,
    detail_url: str,
    logger: Logger,
) -> ProviderResult:
    """Fetch and parse a provider detail page."""
    resp = fetch(
        session, detail_url, timeout=_REQUEST_TIMEOUT, rate_limiter=_rate_limiter
    )
    soup = BeautifulSoup(resp.text, "html.parser")
    raw_html = resp.text

    # Provider name
    name = None
    h1 = soup.find("h1", class_="lgd-page-title-block__title")
    if h1:
        name = clean_text(h1.get_text())

    # Address — structured spans
    address_line1 = None
    address_line2 = None
    locality = None
    postcode = None

    addr1_span = soup.find("span", class_="address-line1")
    if addr1_span:
        address_line1 = clean_text(addr1_span.get_text())
    addr2_span = soup.find("span", class_="address-line2")
    if addr2_span:
        address_line2 = clean_text(addr2_span.get_text())
    loc_span = soup.find("span", class_="locality")
    if loc_span:
        locality = clean_text(loc_span.get_text())
    pc_span = soup.find("span", class_="postal-code")
    if pc_span:
        postcode = clean_text(pc_span.get_text())

    # Phone
    phone = None
    phone_field = soup.find(class_="field--name-localgov-directory-phone")
    if phone_field:
        tel_link = phone_field.find("a", href=re.compile(r"^tel:"))
        if tel_link:
            phone = clean_text(tel_link.get_text())

    # Email
    email = None
    email_field = soup.find(class_="field--name-localgov-directory-email")
    if email_field:
        mailto_link = email_field.find("a", href=re.compile(r"^mailto:"))
        if mailto_link:
            email = clean_text(mailto_link.get_text())

    # Lat/lon from Drupal settings JSON
    lat = None
    lon = None
    settings_script = soup.find(
        "script",
        type="application/json",
        attrs={"data-drupal-selector": "drupal-settings-json"},
    )
    if settings_script and settings_script.string:
        lat, lon = _extract_leaflet_coords(settings_script.string)

    # Determine status — Scottish LA, no Ofsted URN
    has_name = bool(name)
    has_postcode = bool(postcode)

    if has_name and has_postcode:
        status = "success"
    elif has_name:
        status = "partial"
    else:
        status = "error"

    return ProviderResult(
        lad25cd=lad25cd,
        provider_id=provider_id,
        provider_name=name,
        provider_address_line1=address_line1,
        provider_address_line2=address_line2,
        provider_town=locality,
        provider_postcode=postcode,
        provider_phone=phone,
        provider_email=email,
        provider_latitude=lat,
        provider_longitude=lon,
        source_url=detail_url,
        raw_html=raw_html,
        scrape_status=status,
    )


def _extract_leaflet_coords(json_text: str) -> tuple[float | None, float | None]:
    """Extract lat/lon from Drupal settings JSON.

    The JSON is at: settings.leaflet[map_id].features[].{lat, lon}
    """
    try:
        settings = json.loads(json_text)
        leaflet = settings.get("leaflet", {})
        for map_key, map_data in leaflet.items():
            if not isinstance(map_data, dict):
                continue
            for feature in map_data.get("features", []):
                if isinstance(feature, dict):
                    lat = feature.get("lat")
                    lon = feature.get("lon")
                    if lat is not None and lon is not None:
                        return float(lat), float(lon)
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    return None, None
