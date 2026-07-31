"""Surrey CC shared directory scraper.

Covers 11 Surrey district councils that all share the surreycc.gov.uk
families directory. One scrape covers all districts; providers are
stored against each LA's lad25cd.

The Childcare Finder page at:
  ?queries_category_query=Childcare+finder
returns all ~645 childcare providers in a single 1.6MB HTML page
(client-side pagination only — all items are in the HTML).

Listing tile structure:
  <div class="scc-tile scc-tile-v2">
    <h3><a href="/children/support-and-advice/families/directory/{letter}/{slug}">{name}</a></h3>
    <p><i class="fa-location-dot"></i> {address}, {postcode}</p>

Detail page structure:
  <h1>{name}</h1>
  <h2>Location</h2>
  <ul>
    <li><strong>Address</strong>: {address}, {postcode}</li>
  </ul>
  <h2>Ofsted</h2>
  <ul>
    <li><strong>Ofsted URN</strong>: {urn}</li>
  </ul>
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Iterator
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from bsil_pipeline.scrapers.base import (
    BaseScraper,
    ProviderResult,
    clean_text,
    parse_address_parts,
    POSTCODE_RE,
)
from bsil_pipeline.scrapers.http import fetch
from bsil_pipeline.scrapers.rate_limiter import DomainRateLimiter
from bsil_pipeline.utils.postcode_lookup import postcode_to_lad

if TYPE_CHECKING:
    from logging import Logger

_BASE_URL = "https://www.surreycc.gov.uk"
_CHILDCARE_URL = (
    f"{_BASE_URL}/children/support-and-advice/families/directory"
    "?queries_category_query=Childcare+finder"
)
_USER_AGENT = "BSIL-DataPipeline/1.0 (research; best-start-in-life)"
_REQUEST_TIMEOUT = 30  # Larger page needs more time

_rate_limiter = DomainRateLimiter(default_interval=1.0)

# Module-level cache: scrape once for all 11 Surrey districts
_surrey_cache: list[dict] | None = None


class SurreyScraper(BaseScraper):
    @property
    def platform_key(self) -> str:
        return "surrey"

    def scrape_la(
        self,
        lad25cd: str,
        fis_url: str,
        existing_provider_ids: set[str],
        logger: Logger,
    ) -> Iterator[ProviderResult]:
        """Scrape childcare providers from the Surrey CC directory.

        The directory is shared by all 11 Surrey districts. We scrape
        once and cache; each LA gets all providers stored against its
        own lad25cd.
        """
        global _surrey_cache

        if _surrey_cache is None:
            logger.info("Surrey CC: scraping all childcare providers (first LA call)")
            _surrey_cache = _scrape_surrey_providers(logger)
            logger.info(f"Cached {len(_surrey_cache)} Surrey providers")
        else:
            logger.info(
                f"Surrey CC: using cached results "
                f"({len(_surrey_cache)} providers) for {lad25cd}"
            )

        yielded = 0
        skipped = 0
        for raw in _surrey_cache:
            pid = raw["provider_id"]
            if pid in existing_provider_ids:
                continue
            # Assign provider to correct LA based on postcode
            resolved_lad = postcode_to_lad(raw.get("postcode"))
            if resolved_lad and resolved_lad != lad25cd:
                skipped += 1
                continue  # Provider belongs to a different Surrey district
            yield ProviderResult(
                lad25cd=lad25cd,
                provider_id=pid,
                provider_name=raw.get("provider_name"),
                provider_address_line1=raw.get("address_line1"),
                provider_address_line2=raw.get("address_line2"),
                provider_address_line3=raw.get("address_line3"),
                provider_town=raw.get("town"),
                provider_postcode=raw.get("postcode"),
                provider_urn=raw.get("urn"),
                source_url=raw.get("source_url"),
                raw_html=raw.get("raw_html"),
                scrape_status=raw.get("scrape_status", "error"),
            )
            yielded += 1

        logger.info(
            f"Surrey CC: yielded {yielded} providers for {lad25cd} "
            f"(skipped {skipped} belonging to other districts)"
        )


def _scrape_surrey_providers(logger: Logger) -> list[dict]:
    """Scrape all childcare providers from the Surrey CC directory.

    1. Fetch the Childcare Finder listing page (all providers in HTML)
    2. Extract provider links and basic info from listing tiles
    3. Fetch each detail page for Ofsted URN and structured address
    """
    session = requests.Session()
    session.headers.update({"User-Agent": _USER_AGENT})

    # Step 1: Fetch the big listing page
    resp = fetch(session, _CHILDCARE_URL, timeout=60, rate_limiter=_rate_limiter)

    soup = BeautifulSoup(resp.text, "html.parser")

    # Step 2: Extract provider entries from listing tiles
    entries = _parse_listing_tiles(soup, logger)
    logger.info(f"Found {len(entries)} providers on listing page")

    # Step 3: Fetch detail pages
    results: list[dict] = []
    for i, entry in enumerate(entries):
        result = _scrape_detail_page(session, entry, logger)
        results.append(result)

        if (i + 1) % 100 == 0:
            logger.info(f"Scraped {i + 1}/{len(entries)} detail pages")

    return results


def _parse_listing_tiles(soup: BeautifulSoup, logger: Logger) -> list[dict]:
    """Extract provider entries from the Childcare Finder listing page.

    Each provider is in a <div class="scc-tile scc-tile-v2"> with:
    - h3 > a: name and detail URL
    - p with fa-location-dot icon: address text
    """
    entries: list[dict] = []
    seen_slugs: set[str] = set()

    tiles = soup.find_all("div", class_="scc-tile-v2")
    for tile in tiles:
        h3 = tile.find("h3")
        if not h3:
            continue

        link = h3.find("a", href=True)
        if not link:
            continue

        href = link["href"]
        name = clean_text(link.get_text())

        # Extract slug as provider ID
        slug = _extract_slug(href)
        if not slug or slug in seen_slugs:
            continue
        seen_slugs.add(slug)

        detail_url = urljoin(_BASE_URL, href)

        # Extract address from the location paragraph
        listing_address = None
        for p_tag in tile.find_all("p"):
            icon = p_tag.find("i", class_=re.compile(r"fa-location-dot"))
            if icon:
                listing_address = clean_text(p_tag.get_text())
                break

        entries.append(
            {
                "slug": slug,
                "name": name,
                "detail_url": detail_url,
                "listing_address": listing_address,
            }
        )

    return entries


def _scrape_detail_page(session: requests.Session, entry: dict, logger: Logger) -> dict:
    """Fetch and parse a Surrey CC provider detail page."""
    slug = entry["slug"]
    detail_url = entry["detail_url"]

    result: dict = {
        "provider_id": slug,
        "provider_name": entry.get("name"),
        "source_url": detail_url,
        "scrape_status": "error",
    }

    resp = fetch(
        session, detail_url, timeout=_REQUEST_TIMEOUT, rate_limiter=_rate_limiter
    )

    html = resp.text
    result["raw_html"] = html
    soup = BeautifulSoup(html, "html.parser")

    # Provider name from <h1>
    h1 = soup.find("h1")
    if h1:
        result["provider_name"] = clean_text(h1.get_text())

    # Address from <li><strong>Address</strong>: ...</li>
    _extract_address(soup, result)

    # Ofsted URN from <li><strong>Ofsted URN</strong>: ...</li>
    _extract_ofsted_urn(soup, result)

    # Determine scrape status
    has_name = bool(result.get("provider_name"))
    has_postcode = bool(result.get("postcode"))

    if has_name and has_postcode:
        result["scrape_status"] = "success"
    elif has_name or has_postcode:
        result["scrape_status"] = "partial"

    return result


def _extract_address(soup: BeautifulSoup, result: dict) -> None:
    """Extract address from the Location section of the detail page."""
    for li in soup.find_all("li"):
        strong = li.find("strong")
        if not strong:
            continue
        label = clean_text(strong.get_text()) or ""
        if label.lower() == "address":
            # Get text after the strong tag
            full_text = clean_text(li.get_text())
            # Remove "Address:" prefix
            addr_text = re.sub(
                r"^Address\s*:\s*", "", full_text or "", flags=re.IGNORECASE
            )
            if addr_text:
                _parse_surrey_address(addr_text, result)
            return


def _extract_ofsted_urn(soup: BeautifulSoup, result: dict) -> None:
    """Extract Ofsted URN from the detail page."""
    for li in soup.find_all("li"):
        strong = li.find("strong")
        if not strong:
            continue
        label = clean_text(strong.get_text()) or ""
        if "ofsted urn" in label.lower():
            full_text = clean_text(li.get_text())
            urn = re.sub(
                r"^Ofsted URN\s*:\s*", "", full_text or "", flags=re.IGNORECASE
            )
            if urn:
                result["urn"] = urn.strip()
            return


def _parse_surrey_address(address_text: str, result: dict) -> None:
    """Parse a Surrey address into structured fields.

    Format varies:
    - "Brighton Road Burgh Heath, Tadworth, KT20 6AJ"
    - "Redhill, RH1" (childminder — partial postcode)
    - "16, Commercial Way, Woking, Surrey, GU21 6ET"
    """
    parts = [p.strip() for p in address_text.split(",") if p.strip()]
    if not parts:
        return

    # Check if last part is a postcode
    if parts and POSTCODE_RE.search(parts[-1]):
        result["postcode"] = parts[-1].strip().upper()
        parts = parts[:-1]
    elif parts and re.match(r"[A-Z]{1,2}\d{1,2}$", parts[-1].strip(), re.IGNORECASE):
        # Partial postcode (outcode only, e.g. "RH1")
        result["postcode"] = parts[-1].strip().upper()
        parts = parts[:-1]

    # Remove "Surrey" if it appears as county
    if parts and parts[-1].lower() == "surrey":
        parts = parts[:-1]

    # Town is the last remaining part
    if parts:
        result["town"] = parts[-1]
        parts = parts[:-1]

    # Address lines
    if len(parts) >= 1:
        result["address_line1"] = parts[0]
    if len(parts) >= 2:
        result["address_line2"] = parts[1]
    if len(parts) >= 3:
        result["address_line3"] = ", ".join(parts[2:])


def _extract_slug(url: str) -> str | None:
    """Extract the slug from a Surrey directory URL.

    URL format: /children/support-and-advice/families/directory/{letter}/{slug}
    """
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    parts = path.split("/")
    if len(parts) >= 2:
        return parts[-1]
    return None
