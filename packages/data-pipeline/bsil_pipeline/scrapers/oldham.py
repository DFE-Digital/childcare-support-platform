"""Oldham childcare directory scraper.

Covers 1 LA: Oldham (E08000004).

The site at services.oldham.gov.uk uses Oxygen Builder + WP Grid Builder.
The WP REST API is available for the ``childcare-provider`` CPT but ACF
fields are empty — the actual provider data (address, phone, email, Ofsted)
is only in the Oxygen-rendered detail pages.

Strategy: **REST API for listing + detail page HTML for data**.

    1. GET /wp-json/wp/v2/childcare-provider?per_page=100&page={N}
       → provider IDs + detail page URLs (from ``link`` field)
    2. For each detail page, parse structured Oxygen divs:
       - Location section: address lines + postcode (h2 "Location" + ct-text-block divs)
       - Contact section: mailto: link (email) + ct-span (phone)
       - Ofsted section: URN from reports.ofsted.gov.uk link
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Iterator

import requests
from bs4 import BeautifulSoup

from bsil_pipeline.scrapers.base import (
    BaseScraper,
    ProviderResult,
    clean_text,
    POSTCODE_RE,
)
from bsil_pipeline.scrapers.http import fetch
from bsil_pipeline.scrapers.rate_limiter import DomainRateLimiter

if TYPE_CHECKING:
    from logging import Logger

_USER_AGENT = "BSIL-DataPipeline/1.0 (research; best-start-in-life)"
_REQUEST_TIMEOUT = 30
_rate_limiter = DomainRateLimiter(default_interval=1.0)

_BASE_URL = "https://services.oldham.gov.uk"
_CPT_SLUG = "childcare-provider"
_PER_PAGE = 100

# Regex to extract Ofsted URN from report URL
_OFSTED_URN_RE = re.compile(r"reports\.ofsted\.gov\.uk/provider/\d+/(\d+)")


class OldhamScraper(BaseScraper):
    @property
    def platform_key(self) -> str:
        return "oldham"

    def scrape_la(
        self,
        lad25cd: str,
        fis_url: str,
        existing_provider_ids: set[str],
        logger: Logger,
    ) -> Iterator[ProviderResult]:
        """Scrape Oldham childcare providers via REST API + detail pages."""
        session = requests.Session()
        session.headers.update({"User-Agent": _USER_AGENT})

        # Phase 1: Collect all provider listings from REST API
        listings = _collect_listings(session, logger)
        if not listings:
            logger.warning("Oldham: no providers found via REST API")
            yield ProviderResult(
                lad25cd=lad25cd,
                provider_id="__no_results__",
                scrape_status="error",
                source_url=fis_url,
            )
            return

        logger.info(f"Oldham: {len(listings)} providers from REST API")

        # Phase 2: Fetch detail pages for each provider
        yielded = 0
        for provider_id, name, detail_url in listings:
            if provider_id in existing_provider_ids:
                continue

            resp = fetch(
                session,
                detail_url,
                timeout=_REQUEST_TIMEOUT,
                rate_limiter=_rate_limiter,
            )

            result = _parse_detail_page(
                resp.text, lad25cd, provider_id, name, detail_url
            )
            yield result
            yielded += 1

            if yielded % 50 == 0:
                logger.info(f"Oldham: {yielded} providers scraped so far")

        logger.info(f"Oldham: yielded {yielded} providers for {lad25cd}")


def _collect_listings(
    session: requests.Session, logger: Logger
) -> list[tuple[str, str | None, str]]:
    """Collect (provider_id, name, detail_url) tuples from the REST API."""
    listings: list[tuple[str, str | None, str]] = []
    page = 1
    total_pages = None

    while True:
        url = f"{_BASE_URL}/wp-json/wp/v2/{_CPT_SLUG}?per_page={_PER_PAGE}&page={page}"

        resp = fetch(session, url, timeout=_REQUEST_TIMEOUT, rate_limiter=_rate_limiter)

        if total_pages is None:
            total_pages = int(resp.headers.get("X-WP-TotalPages", "1"))
            total = resp.headers.get("X-WP-Total", "?")
            logger.info(f"Oldham REST: {total} providers across {total_pages} pages")

        providers = resp.json()
        if not isinstance(providers, list):
            logger.error("Oldham REST: unexpected response format")
            break

        for p in providers:
            pid = str(p.get("id", ""))
            title_obj = p.get("title", {})
            name = (
                clean_text(title_obj.get("rendered"))
                if isinstance(title_obj, dict)
                else None
            )
            detail_url = p.get("link", "")
            if pid and detail_url:
                listings.append((pid, name, detail_url))

        page += 1
        if page > total_pages:
            break

    return listings


def _parse_detail_page(
    html: str,
    lad25cd: str,
    provider_id: str,
    api_name: str | None,
    url: str,
) -> ProviderResult:
    """Parse an Oldham childcare provider detail page (Oxygen Builder HTML).

    The page structure uses Oxygen ``ct-div-block`` sections:
    - Location section: h2 "Location" → ct-text-block divs for address lines
    - Contact section: mailto: link (email) + ct-span with phone number
    - Ofsted section: link to reports.ofsted.gov.uk containing URN
    """
    soup = BeautifulSoup(html, "html.parser")

    # Provider name from <h1> (Oxygen headline), fall back to API name
    name = None
    h1 = soup.find("h1")
    if h1:
        name = clean_text(h1.get_text())
    if not name:
        name = api_name

    # --- Address (Location section) ---
    address_line1 = None
    town = None
    postcode = None

    location_heading = soup.find(
        lambda tag: tag.name in ("h2", "h3")
        and "location" in (tag.get_text() or "").lower()
    )
    if location_heading:
        # Walk up to the containing div, then find text blocks within it
        container = location_heading.parent
        if container:
            text_blocks = container.find_all("div", class_="ct-text-block")
            addr_lines = []
            for tb in text_blocks:
                text = clean_text(tb.get_text())
                if text:
                    addr_lines.append(text)

            # Last line with postcode pattern is the postcode
            for i, line in enumerate(addr_lines):
                match = POSTCODE_RE.search(line)
                if match:
                    postcode = match.group().strip()
                    # Lines before postcode are address parts
                    non_empty = [ln for ln in addr_lines[:i] if ln]
                    if non_empty:
                        address_line1 = non_empty[0]
                    if len(non_empty) >= 2:
                        town = non_empty[-1]
                    break

    # --- Email ---
    email = None
    mailto_link = soup.find("a", href=re.compile(r"^mailto:"))
    if mailto_link:
        email = mailto_link["href"].replace("mailto:", "").strip()

    # --- Phone ---
    # Phone is in a ct-span near the phone icon (no tel: link on this site)
    phone = None
    tel_link = soup.find("a", href=re.compile(r"^tel:"))
    if tel_link:
        phone = clean_text(tel_link.get_text())
        if not phone:
            phone = tel_link["href"].replace("tel:", "").strip()

    if not phone:
        # Look for phone icon SVG → sibling text block
        phone_icon = soup.find("use", attrs={"xlink:href": re.compile(r"phone")})
        if phone_icon:
            # Navigate up to the icon container, then find sibling text
            icon_container = phone_icon
            for _ in range(4):
                icon_container = icon_container.parent
                if icon_container is None:
                    break
            if icon_container:
                parent_block = icon_container.parent
                if parent_block:
                    span = parent_block.find("span", class_="ct-span")
                    if span:
                        phone = clean_text(span.get_text())

    # --- Ofsted URN ---
    urn = None
    ofsted_link = soup.find("a", href=re.compile(r"reports\.ofsted\.gov\.uk"))
    if ofsted_link:
        match = _OFSTED_URN_RE.search(ofsted_link["href"])
        if match:
            urn = match.group(1)

    has_name = bool(name)
    has_postcode = bool(postcode)

    if has_name and has_postcode:
        status = "success"
    elif has_name or has_postcode:
        status = "partial"
    else:
        status = "error"

    return ProviderResult(
        lad25cd=lad25cd,
        provider_id=provider_id,
        provider_name=name,
        provider_address_line1=address_line1,
        provider_town=town,
        provider_postcode=postcode,
        provider_urn=urn,
        provider_phone=phone,
        provider_email=email,
        source_url=url,
        raw_html=html[:50_000],
        scrape_status=status,
    )
