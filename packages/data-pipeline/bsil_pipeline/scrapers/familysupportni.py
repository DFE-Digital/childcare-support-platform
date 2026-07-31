"""Family Support NI platform scraper.

Covers 11 Northern Ireland local authorities via the centralised
familysupportni.gov.uk portal.

All NI childcare providers are listed on a single portal. The scraper
fetches all ~3,800 providers once and caches the results; subsequent
LA calls use the cache and filter by assigned lad25cd (all NI LAs
share the same portal, so each LA just gets the full set stored
against its own code).

URL patterns:
  - Listing:  /Search/Results?sTypeID=138&page={N}  (25 per page)
  - Detail:   /Search/Details/{id}?slug={slug}       (200 OK, no redirect needed)
  - Categories API: POST /Search/GetDDCategories/ with typeID=138

Detail page structure:
  - Provider name in <h1>
  - Contact info in <dl> inside #organisationDetails
  - Address as comma-separated string in <dd> after <dt>Address</dt>
  - NI postcodes start with BT
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Iterator
from urllib.parse import urljoin

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

_BASE_URL = "https://www.familysupportni.gov.uk"
_SEARCH_URL = f"{_BASE_URL}/Search/Results"
_USER_AGENT = "BSIL-DataPipeline/1.0 (research; best-start-in-life)"
_REQUEST_TIMEOUT = 20

_rate_limiter = DomainRateLimiter(default_interval=1.0)

# Module-level cache: once we scrape the portal, store raw results
_ni_cache: list[dict] | None = None


class FamilySupportNIScraper(BaseScraper):
    @property
    def platform_key(self) -> str:
        return "familysupportni"

    def scrape_la(
        self,
        lad25cd: str,
        fis_url: str,
        existing_provider_ids: set[str],
        logger: Logger,
    ) -> Iterator[ProviderResult]:
        """Scrape childcare providers from familysupportni.gov.uk.

        The portal is shared by all NI LAs. We scrape it once and cache;
        each LA gets all providers stored against its own lad25cd.
        """
        global _ni_cache

        if _ni_cache is None:
            logger.info("Family Support NI: scraping all providers (first LA call)")
            _ni_cache = _scrape_all_providers(logger)
            logger.info(f"Cached {len(_ni_cache)} NI providers")
        else:
            logger.info(
                f"Family Support NI: using cached results "
                f"({len(_ni_cache)} providers) for {lad25cd}"
            )

        yielded = 0
        skipped = 0
        for raw in _ni_cache:
            pid = raw["provider_id"]
            if pid in existing_provider_ids:
                continue
            # Assign provider to correct NI LGD based on postcode
            resolved_lad = postcode_to_lad(raw.get("postcode"))
            if resolved_lad and resolved_lad != lad25cd:
                skipped += 1
                continue  # Provider belongs to a different NI LGD
            yield ProviderResult(
                lad25cd=lad25cd,
                provider_id=pid,
                provider_name=raw.get("provider_name"),
                provider_address_line1=raw.get("address_line1"),
                provider_address_line2=raw.get("address_line2"),
                provider_address_line3=raw.get("address_line3"),
                provider_town=raw.get("town"),
                provider_postcode=raw.get("postcode"),
                provider_phone=raw.get("phone"),
                provider_email=raw.get("email"),
                source_url=raw.get("source_url"),
                raw_html=raw.get("raw_html"),
                scrape_status=raw.get("scrape_status", "error"),
            )
            yielded += 1

        logger.info(
            f"Family Support NI: yielded {yielded} providers for {lad25cd} "
            f"(skipped {skipped} belonging to other LGDs)"
        )


def _scrape_all_providers(logger: Logger) -> list[dict]:
    """Scrape all childcare providers from the NI portal.

    Strategy:
    1. Paginate listing pages to collect provider IDs and basic info
    2. Fetch each detail page for full address and metadata
    """
    session = requests.Session()
    session.headers.update({"User-Agent": _USER_AGENT})

    # Step 1: Collect all provider IDs from listing pages
    provider_entries = _collect_listing_entries(session, logger)
    logger.info(f"Collected {len(provider_entries)} provider entries from listings")

    # Step 2: Fetch detail pages
    # Use a fresh session to avoid WAF cookie accumulation from listing phase.
    # Rotate sessions periodically to prevent the WAF from blocking us.
    detail_session = requests.Session()
    detail_session.headers.update({"User-Agent": _USER_AGENT})

    results: list[dict] = []
    for i, entry in enumerate(provider_entries):
        pid = entry["provider_id"]
        detail_url = entry["detail_url"]

        # Rotate session every 50 requests to prevent cookie buildup
        if i > 0 and i % 50 == 0:
            detail_session = requests.Session()
            detail_session.headers.update({"User-Agent": _USER_AGENT})

        result = _scrape_detail_page(detail_session, pid, detail_url, logger)

        # Fill in name from listing if detail page didn't have it
        if not result.get("provider_name") and entry.get("name"):
            result["provider_name"] = entry["name"]

        # Fill in address from listing if detail page didn't have it
        if not result.get("postcode") and entry.get("listing_address"):
            addr_parts = parse_address_parts(entry["listing_address"])
            for key, val in addr_parts.items():
                if val and not result.get(key):
                    result[key] = val

        results.append(result)

        if (i + 1) % 100 == 0:
            logger.info(f"Scraped {i + 1}/{len(provider_entries)} detail pages")

    return results


def _collect_listing_entries(session: requests.Session, logger: Logger) -> list[dict]:
    """Paginate through listing pages and collect provider entries.

    Returns list of dicts with: provider_id, name, detail_url, listing_address.
    """
    entries: list[dict] = []
    seen_ids: set[str] = set()
    page = 1

    while True:
        url = f"{_SEARCH_URL}?sTypeID=138&page={page}"

        resp = fetch(session, url, timeout=_REQUEST_TIMEOUT, rate_limiter=_rate_limiter)
        soup = BeautifulSoup(resp.text, "html.parser")
        page_entries = _parse_listing_page(soup)

        if not page_entries:
            if page == 1:
                logger.warning("No entries found on first listing page")
            break

        for entry in page_entries:
            pid = entry["provider_id"]
            if pid not in seen_ids:
                seen_ids.add(pid)
                entries.append(entry)

        # Check for last page
        last_page = _get_last_page_number(soup)
        if page >= last_page:
            break

        page += 1

        # Safety limit
        if page > 200:
            logger.warning("Hit pagination safety limit (200 pages)")
            break

    return entries


def _parse_listing_page(soup: BeautifulSoup) -> list[dict]:
    """Extract provider entries from a listing page.

    Each result is a <div class="organisation top-buffer"> with:
    - data-orgname attribute
    - <p class="resultheading"> with link to /Search/Details/{id}
    - <p><strong>Address:</strong> ... </p>
    """
    entries: list[dict] = []

    for org_div in soup.find_all("div", class_="organisation"):
        entry: dict = {}

        # Get provider ID from the detail link
        heading = org_div.find("p", class_="resultheading")
        if not heading:
            continue

        link = heading.find("a", href=True)
        if not link:
            continue

        href = link["href"]
        # Extract ID from /Search/Details/{id} or /Service/{id}
        match = re.search(r"/(?:Search/Details|Service)/(\d+)", href)
        if not match:
            continue

        entry["provider_id"] = match.group(1)
        entry["name"] = clean_text(link.get_text())
        # Use the listing page's own URL (/Search/Details/{id}?slug=...)
        # which returns 200 directly. The old /Service/{id} pattern caused
        # 400 errors because the 302 redirect fails with accumulated WAF cookies.
        entry["detail_url"] = urljoin(_BASE_URL, href)

        # Extract address from listing
        for p_tag in org_div.find_all("p"):
            strong = p_tag.find("strong")
            if strong and "address" in (strong.get_text() or "").lower():
                # Address text follows the <strong>Address:</strong>
                full_text = p_tag.get_text()
                addr_text = re.sub(
                    r"^.*?Address:\s*", "", full_text, flags=re.IGNORECASE
                )
                entry["listing_address"] = clean_text(addr_text)
                break

        entries.append(entry)

    return entries


def _get_last_page_number(soup: BeautifulSoup) -> int:
    """Extract the last page number from pagination.

    Looks for PagedList-skipToLast link with href containing page={N}.
    """
    last_link = soup.find("li", class_="PagedList-skipToLast")
    if last_link:
        a_tag = last_link.find("a", href=True)
        if a_tag:
            match = re.search(r"page=(\d+)", a_tag["href"])
            if match:
                return int(match.group(1))

    # Fallback: find the highest page number in pagination links
    max_page = 1
    pagination = soup.find("ul", class_="pagination")
    if pagination:
        for a_tag in pagination.find_all("a", href=True):
            match = re.search(r"page=(\d+)", a_tag["href"])
            if match:
                max_page = max(max_page, int(match.group(1)))

    return max_page


def _scrape_detail_page(
    session: requests.Session,
    provider_id: str,
    detail_url: str,
    logger: Logger,
) -> dict:
    """Fetch and parse a Family Support NI detail page."""
    result: dict = {
        "provider_id": provider_id,
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

    # Parse the <dl> inside #organisationDetails
    org_details = soup.find(id="organisationDetails")
    if org_details:
        _parse_dl_pairs(org_details, result)

    # Determine scrape status
    has_name = bool(result.get("provider_name"))
    has_postcode = bool(result.get("postcode"))

    if has_name and has_postcode:
        result["scrape_status"] = "success"
    elif has_name or has_postcode:
        result["scrape_status"] = "partial"

    return result


def _parse_dl_pairs(container, result: dict) -> None:
    """Extract address, phone, email and other fields from dt/dd pairs."""
    dl = container.find("dl")
    if not dl:
        return

    current_dt = None
    for child in dl.children:
        if child.name == "dt":
            current_dt = clean_text(child.get_text())
        elif child.name == "dd" and current_dt:
            dd_text = clean_text(child.get_text())
            dt_lower = (current_dt or "").lower()

            if dt_lower == "address" and dd_text:
                _parse_ni_address(dd_text, result)
            elif "telephone" in dt_lower and dd_text:
                result["phone"] = dd_text
            elif "email" in dt_lower and dd_text:
                result["email"] = dd_text
            elif "ccp reference" in dt_lower and dd_text:
                # CCP reference could be useful as an alternative ID
                pass

            current_dt = None


def _parse_ni_address(address_text: str, result: dict) -> None:
    """Parse a comma-separated NI address into structured fields.

    Format: {street}, {town}, Co {county}, {postcode}
    NI postcodes always start with BT.
    """
    parts = [p.strip() for p in address_text.split(",") if p.strip()]
    if not parts:
        return

    # Check if last part is a postcode (BT...)
    if parts and re.match(r"BT\d", parts[-1], re.IGNORECASE):
        result["postcode"] = parts[-1].strip().upper()
        parts = parts[:-1]

    # Remove county (Co Antrim, Co Down, etc.)
    if parts and re.match(r"Co\s+\w+", parts[-1], re.IGNORECASE):
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
