"""Lambeth Family Information Directory scraper.

Covers 1 LA using a custom Drupal content type (lambeth-fid-entry):
- www.lambeth.gov.uk (Lambeth, E09000022)

Server-side rendered HTML — no JSON API (Drupal JSON:API is disabled,
Views REST returns 403). Uses requests + BeautifulSoup.

Endpoints:
  /family-information-directory?page=,{N}  — listing pages (10/page, N=0-based)
  /family-information-directory/{id}-{slug} — provider detail page

Pagination quirk: the comma prefix in ?page=,N is Drupal's multi-pager
format (the directory view is the second pager on the page).
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

_BASE_URL = "https://www.lambeth.gov.uk"
_LISTING_PATH = "/family-information-directory"
_USER_AGENT = "BSIL-DataPipeline/1.0 (research; best-start-in-life)"
_REQUEST_TIMEOUT = 30
_rate_limiter = DomainRateLimiter(default_interval=1.0)

# Regex to extract provider numeric ID from URL path like /family-information-directory/11388-abacus-nursery
_PROVIDER_ID_RE = re.compile(r"/family-information-directory/(\d+)-")


class LambethScraper(BaseScraper):
    @property
    def platform_key(self) -> str:
        return "lambeth"

    def scrape_la(
        self,
        lad25cd: str,
        fis_url: str,
        existing_provider_ids: set[str],
        logger: Logger,
    ) -> Iterator[ProviderResult]:
        session = requests.Session()
        session.headers.update({"User-Agent": _USER_AGENT})

        # Step 1: Fetch page 0 to determine max page from pagination
        first_page = _fetch_listing_page(session, 0, logger)
        if first_page is None:
            logger.error("Lambeth: failed to fetch first listing page")
            return
        provider_links, max_page = first_page

        all_links = list(provider_links)
        logger.info(f"Lambeth: page 0/{max_page} -> {len(all_links)} providers")

        # Step 2: Fetch remaining pages
        for page_no in range(1, max_page + 1):
            page_links, _ = _fetch_listing_page(session, page_no, logger) or (None, 0)
            if page_links is None:
                break
            all_links.extend(page_links)

            if page_no % 10 == 0:
                logger.info(
                    f"Lambeth: page {page_no}/{max_page} -> {len(all_links)} providers so far"
                )

        logger.info(f"Lambeth: {len(all_links)} total provider links found")

        # Step 3: Filter out existing providers
        new_links = [
            (pid, path) for pid, path in all_links if pid not in existing_provider_ids
        ]
        logger.info(
            f"Lambeth: {len(new_links)} new providers to process "
            f"({len(existing_provider_ids)} already exist)"
        )

        # Step 4: Fetch each provider detail page
        yielded = 0
        for pid, detail_path in new_links:
            detail_url = f"{_BASE_URL}{detail_path}"
            result = _fetch_provider_detail(session, lad25cd, pid, detail_url, logger)
            yield result
            yielded += 1

            if yielded % 50 == 0:
                logger.info(f"Lambeth: processed {yielded}/{len(new_links)} providers")

        logger.info(f"Lambeth: yielded {yielded} providers for {lad25cd}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _fetch_listing_page(
    session: requests.Session,
    page_no: int,
    logger: Logger,
) -> tuple[list[tuple[str, str]], int] | None:
    """Fetch a single listing page.

    Returns (list of (provider_id, detail_path), max_page) or None on failure.
    """
    if page_no == 0:
        url = f"{_BASE_URL}{_LISTING_PATH}"
    else:
        url = f"{_BASE_URL}{_LISTING_PATH}?page=,{page_no}"

    resp = fetch(session, url, timeout=_REQUEST_TIMEOUT, rate_limiter=_rate_limiter)

    soup = BeautifulSoup(resp.text, "html.parser")

    # Extract provider links from listing cards
    links: list[tuple[str, str]] = []
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        match = _PROVIDER_ID_RE.search(href)
        if match:
            pid = match.group(1)
            # Deduplicate within the page
            if not any(p == pid for p, _ in links):
                links.append((pid, href))

    # Extract max page from pagination links (comma may be literal or URL-encoded %2C)
    max_page = 0
    pager = soup.find("nav", class_="pager")
    pager_scope = pager if pager else soup
    for a_tag in pager_scope.find_all("a", href=True):
        href = a_tag["href"]
        page_match = re.search(r"page=(?:,|%2C)(\d+)", href, re.IGNORECASE)
        if page_match:
            pn = int(page_match.group(1))
            if pn > max_page:
                max_page = pn

    return links, max_page


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

    # Provider name — from <title> tag (e.g. "Provider Name | Lambeth Council")
    # The H1 contains the name but split across child spans with poor whitespace;
    # the <title> is always clean.
    name = None
    title_tag = soup.find("title")
    if title_tag:
        title_text = title_tag.get_text()
        # Strip " | Lambeth Council" suffix
        if "|" in title_text:
            name = clean_text(title_text.split("|")[0])
        else:
            name = clean_text(title_text)

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

    # Contact — phone and email from "Contact details" section
    phone = None
    email = None

    tel_link = soup.find("a", href=re.compile(r"^tel:"))
    if tel_link:
        phone = clean_text(tel_link.get_text())

    mailto_link = soup.find("a", href=re.compile(r"^mailto:"))
    if mailto_link:
        email = clean_text(mailto_link.get_text())

    # Lat/lon from Drupal settings JSON (<script type="application/json">)
    lat = None
    lon = None
    settings_script = soup.find(
        "script",
        type="application/json",
        attrs={"data-drupal-selector": "drupal-settings-json"},
    )
    if settings_script and settings_script.string:
        lat, lon = _extract_leaflet_coords(settings_script.string)

    # Ofsted URN — look for text near "Ofsted Unique Ref" in Inspection section
    urn = None
    urn = _extract_ofsted_urn(soup)

    # Determine status
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
        provider_urn=urn,
        source_url=detail_url,
        raw_html=raw_html,
        scrape_status=status,
    )


def _extract_leaflet_coords(json_text: str) -> tuple[float | None, float | None]:
    """Extract lat/lon from Drupal settings JSON.

    The JSON is from <script type="application/json" data-drupal-selector="drupal-settings-json">.
    Leaflet features are at: settings.leaflet[map_id].features[].{lat, lon}
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


def _extract_ofsted_urn(soup: BeautifulSoup) -> str | None:
    """Extract Ofsted URN from the detail page.

    Looks for text containing "Ofsted Unique Ref" or similar labels
    in the Inspection section of the page.
    """
    urn_re = re.compile(r"\d{6,}")

    # Look for elements containing "Ofsted" text
    for element in soup.find_all(
        string=re.compile(r"Ofsted\s+Unique\s+Ref", re.IGNORECASE)
    ):
        # Check the parent and siblings for the URN value
        parent = element.parent
        if parent:
            # The URN might be in a sibling or child element
            full_text = parent.get_text()
            match = urn_re.search(full_text)
            if match:
                return match.group()

            # Check next sibling
            next_sib = parent.find_next_sibling()
            if next_sib:
                match = urn_re.search(next_sib.get_text())
                if match:
                    return match.group()

    # Fallback: look for any field with "ofsted" and a URN-like number
    for dt in soup.find_all("dt"):
        if "ofsted" in (dt.get_text() or "").lower():
            dd = dt.find_next_sibling("dd")
            if dd:
                match = urn_re.search(dd.get_text())
                if match:
                    return match.group()

    return None
