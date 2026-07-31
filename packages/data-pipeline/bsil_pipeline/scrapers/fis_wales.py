"""fis.wales platform scraper.

Covers 22 Welsh local authorities via the centralised FIS Wales portal
(powered by Dewis Cymru). The site was rebuilt with Blazor Server but all
content is server-side pre-rendered (SSR) — no JS execution needed.
Plain HTTP GET returns the full HTML for both listing and detail pages.

URL patterns:
  Listing:  /resources?localauthoritycode={code}&classifications=7|9|10|...&page={N}
  Detail:   /viewresource?id={UUID}

Classification IDs for childcare (combined with pipe separator):
  7 = Childminder, 9 = Day Nursery, 10 = After School Club,
  11 = Holiday Club, 12 = Breakfast Club, 13 = Playgroups,
  25 = Creche, 27 = Open Access Play, 34 = School-based nurseries

Listing page:
  - 10 items per page
  - Pagination: <ul class="pagination"> with "Page X of Y" text
  - Each card: <div class="media media-list-view ...">
    - h2 > a href="/viewresource?id={UUID}": provider name (may include type suffix)

Detail page (Blazor prerendered HTML):
  - Name: <h2 class="card-header bg-{type}">{Name} - {Type}</h2>
  - Address: <asp:Panel> with id="pnlVisitAddressWrapper" or "pnlPostalAddressWrapper"
    containing <p> with <br>-separated address lines.
    BeautifulSoup finds these by ID regardless of tag name.
  - Phone: near <i class="...fa-phone"> icon
  - Email: near <i class="...fa-envelope"> icon
  - Postcode is the last line before final <br>
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

_BASE_URL = "https://www.fis.wales"
_USER_AGENT = "BSIL-DataPipeline/1.0 (research; best-start-in-life)"
_REQUEST_TIMEOUT = 20

# Childcare classification IDs — combined with pipe separator for single query
_CHILDCARE_CLASSIFICATIONS = "7|9|10|11|12|13|25|27|34"

_rate_limiter = DomainRateLimiter(default_interval=1.0)


class FisWalesScraper(BaseScraper):
    @property
    def platform_key(self) -> str:
        return "fis_wales"

    def scrape_la(
        self,
        lad25cd: str,
        fis_url: str,
        existing_provider_ids: set[str],
        logger: Logger,
    ) -> Iterator[ProviderResult]:
        """Scrape childcare providers from fis.wales for a single LA.

        Each Welsh LA has its own localauthoritycode parameter.
        We query all childcare classifications in a single combined
        request (pipe-separated IDs) and paginate to collect all providers.
        """
        session = requests.Session()
        session.headers.update({"User-Agent": _USER_AGENT})

        # Extract the LA code from the FIS URL
        la_code = _extract_la_code(fis_url, lad25cd)
        logger.info(f"FIS Wales: scraping {lad25cd} (LA code: {la_code})")

        # Collect provider UUIDs using combined classification query
        provider_ids: dict[str, str] = {}  # uuid -> detail_url
        count = _collect_providers(
            session,
            la_code,
            provider_ids,
            existing_provider_ids,
            logger,
        )
        logger.info(
            f"FIS Wales {lad25cd}: {count} new providers found, "
            f"{len(provider_ids)} unique total"
        )

        # Fetch detail pages
        yielded = 0
        for i, (uuid, detail_url) in enumerate(provider_ids.items()):
            result = _scrape_detail_page(session, lad25cd, uuid, detail_url, logger)
            yield result
            yielded += 1

            if (yielded) % 50 == 0:
                logger.info(
                    f"FIS Wales {lad25cd}: scraped {yielded}/{len(provider_ids)} "
                    f"detail pages"
                )

        logger.info(f"FIS Wales scrape complete for {lad25cd}: {yielded} providers")


def _extract_la_code(fis_url: str, lad25cd: str) -> str:
    """Extract the Welsh LA code from the FIS URL.

    FIS URLs use codes like W06000001. If the URL has a localauthoritycode
    parameter, use that. Otherwise, use the lad25cd directly (Welsh LA
    codes use the same W06... format).
    """
    match = re.search(r"localauthoritycode=([A-Z]\d+)", fis_url, re.IGNORECASE)
    if match:
        return match.group(1)

    # Welsh lad25cd codes start with W06
    if lad25cd.startswith("W"):
        return lad25cd

    # Fallback: try to extract from the URL path
    match = re.search(r"/fis/([A-Z]\d+)", fis_url, re.IGNORECASE)
    if match:
        return match.group(1)

    return lad25cd


def _collect_providers(
    session: requests.Session,
    la_code: str,
    provider_ids: dict[str, str],
    existing_provider_ids: set[str],
    logger: Logger,
) -> int:
    """Paginate through combined classifications and collect provider UUIDs.

    Uses pipe-separated classification IDs in a single query to fetch
    all childcare types at once.

    Returns the number of new providers found.
    """
    new_count = 0
    page = 1

    while True:
        # Build URL with literal pipe characters — the server expects
        # unencoded pipes in the classifications parameter.
        url = (
            f"{_BASE_URL}/resources?"
            f"localauthoritycode={la_code}"
            f"&classifications={_CHILDCARE_CLASSIFICATIONS}"
            f"&page={page}"
        )
        resp = fetch(session, url, timeout=_REQUEST_TIMEOUT, rate_limiter=_rate_limiter)

        html = resp.text
        soup = BeautifulSoup(html, "html.parser")

        # Validation: check the first page contains expected markers
        if page == 1:
            has_listing_markers = "media-list-view" in html or "viewresource" in html
            if not has_listing_markers:
                logger.error(
                    f"FIS Wales listing page for {la_code} does not contain "
                    f"expected markers ('media-list-view' or 'viewresource'). "
                    f"The site structure may have changed again. "
                    f"URL: {url}"
                )
                break

        # Extract provider UUIDs from this page
        page_uuids = _extract_provider_uuids(soup)
        if not page_uuids:
            if page == 1:
                logger.warning(
                    f"FIS Wales: no providers found on first page for "
                    f"{la_code}. URL: {url}"
                )
            break

        for uuid, detail_url in page_uuids:
            if uuid not in provider_ids and uuid not in existing_provider_ids:
                provider_ids[uuid] = detail_url
                new_count += 1

        # Check total pages
        total_pages = _get_total_pages(soup)
        if page >= total_pages:
            break

        page += 1

        # Safety limit
        if page > 200:
            logger.warning(f"Hit pagination safety limit (200 pages) for {la_code}")
            break

    return new_count


def _extract_provider_uuids(
    soup: BeautifulSoup,
) -> list[tuple[str, str]]:
    """Extract (uuid, detail_url) tuples from a listing page.

    Provider links: <a href="/viewresource?id={UUID}">
    """
    results: list[tuple[str, str]] = []
    seen: set[str] = set()

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if "viewresource" not in href:
            continue

        match = re.search(
            r"viewresource\?id=([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
            r"[0-9a-f]{4}-[0-9a-f]{12})",
            href,
            re.IGNORECASE,
        )
        if not match:
            continue

        uuid = match.group(1).lower()
        if uuid in seen:
            continue
        seen.add(uuid)

        detail_url = f"{_BASE_URL}/viewresource?id={uuid}"
        results.append((uuid, detail_url))

    return results


def _get_total_pages(soup: BeautifulSoup) -> int:
    """Extract total page count from pagination.

    Looks for "Page X of Y" text in the pagination element.
    """
    pagination = soup.find("ul", class_="pagination")
    if not pagination:
        return 1

    text = pagination.get_text()
    match = re.search(r"Page\s+\d+\s+of\s+(\d+)", text)
    if match:
        return int(match.group(1))

    return 1


def _scrape_detail_page(
    session: requests.Session,
    lad25cd: str,
    uuid: str,
    detail_url: str,
    logger: Logger,
) -> ProviderResult:
    """Fetch and parse a FIS Wales detail page."""
    resp = fetch(
        session, detail_url, timeout=_REQUEST_TIMEOUT, rate_limiter=_rate_limiter
    )

    html = resp.text
    soup = BeautifulSoup(html, "html.parser")

    # Provider name from card-header h2
    provider_name = None
    header = soup.find("h2", class_=re.compile(r"card-header"))
    if header:
        raw_name = clean_text(header.get_text())
        # Strip the type suffix: "Name - Day Nursery" -> "Name"
        if raw_name and " - " in raw_name:
            provider_name = raw_name.rsplit(" - ", 1)[0].strip()
        else:
            provider_name = raw_name

    # Extract address — prefer visit address, fall back to postal
    address_info = _extract_address(soup)

    # Extract phone and email from contact section
    phone = _extract_phone(soup)
    email = _extract_email(soup)

    # Determine status
    has_name = bool(provider_name)
    has_postcode = bool(address_info.get("postcode"))

    if has_name and has_postcode:
        status = "success"
    elif has_name or has_postcode:
        status = "partial"
    else:
        status = "error"

    return ProviderResult(
        lad25cd=lad25cd,
        provider_id=uuid,
        provider_name=provider_name,
        provider_address_line1=address_info.get("address_line1"),
        provider_address_line2=address_info.get("address_line2"),
        provider_address_line3=address_info.get("address_line3"),
        provider_town=address_info.get("town"),
        provider_postcode=address_info.get("postcode"),
        provider_phone=phone,
        provider_email=email,
        source_url=detail_url,
        raw_html=html,
        scrape_status=status,
    )


def _extract_address(soup: BeautifulSoup) -> dict[str, str | None]:
    """Extract address from the detail page.

    Addresses are in <p> tags with <br>-separated lines under
    visit address or postal address panels.
    """
    result: dict[str, str | None] = {
        "address_line1": None,
        "address_line2": None,
        "address_line3": None,
        "town": None,
        "postcode": None,
    }

    # Try visit address first (more complete), then postal
    for panel_id in ("pnlVisitAddressWrapper", "pnlPostalAddressWrapper"):
        panel = soup.find(id=panel_id)
        if not panel:
            continue

        p_tag = panel.find("p")
        if not p_tag:
            continue

        # Get lines from <br>-separated content
        lines = _extract_br_lines(p_tag)
        if not lines:
            continue

        _parse_wales_address_lines(lines, result)

        # If we got a postcode, we're done
        if result["postcode"]:
            break

    return result


def _extract_br_lines(element) -> list[str]:
    """Extract text lines from an element with <br> separators."""
    lines: list[str] = []
    current = ""

    for child in element.children:
        if child.name == "br":
            text = clean_text(current)
            if text:
                lines.append(text)
            current = ""
        elif hasattr(child, "get_text"):
            current += child.get_text()
        else:
            current += str(child)

    # Don't forget the last line
    text = clean_text(current)
    if text:
        lines.append(text)

    return lines


def _parse_wales_address_lines(lines: list[str], result: dict[str, str | None]) -> None:
    """Parse br-separated address lines into structured fields.

    Lines are typically:
    - Street name
    - Area/neighbourhood
    - Town/city
    - Postcode
    """
    if not lines:
        return

    # Check if last line is a postcode
    if lines and POSTCODE_RE.search(lines[-1]):
        result["postcode"] = lines[-1].strip().upper()
        lines = lines[:-1]

    # Town/city is the last remaining line
    if lines:
        result["town"] = lines[-1]
        lines = lines[:-1]

    # Address lines
    if len(lines) >= 1:
        result["address_line1"] = lines[0]
    if len(lines) >= 2:
        result["address_line2"] = lines[1]
    if len(lines) >= 3:
        result["address_line3"] = ", ".join(lines[2:])


def _extract_phone(soup: BeautifulSoup) -> str | None:
    """Extract phone number from the detail page.

    Looks for a <i> tag with fa-phone class, then extracts the adjacent
    text or the text of the parent element.
    """
    icon = soup.find("i", class_=re.compile(r"fa-phone"))
    if not icon:
        return None

    # The phone number is typically in the parent element's text
    parent = icon.parent
    if not parent:
        return None

    # Get text, stripping the icon element itself
    text = clean_text(parent.get_text())
    if not text:
        return None

    # Extract phone-like pattern (digits, spaces, hyphens, parentheses, plus)
    phone_match = re.search(r"[\d\s\-\(\)\+]{7,}", text)
    if phone_match:
        phone = clean_text(phone_match.group())
        return phone if phone else None

    return None


def _extract_email(soup: BeautifulSoup) -> str | None:
    """Extract email address from the detail page.

    Looks for a <i> tag with fa-envelope class, then extracts the
    adjacent mailto link or text containing an email.
    """
    icon = soup.find("i", class_=re.compile(r"fa-envelope"))
    if not icon:
        return None

    parent = icon.parent
    if not parent:
        return None

    # Check for mailto link
    mailto = parent.find("a", href=re.compile(r"^mailto:", re.IGNORECASE))
    if mailto:
        email = clean_text(mailto.get_text())
        if email and "@" in email:
            return email.lower()
        # Try href
        href = mailto.get("href", "")
        if href.startswith("mailto:"):
            email = clean_text(href[7:].split("?")[0])
            if email and "@" in email:
                return email.lower()

    # Fallback: look for email pattern in parent text
    text = clean_text(parent.get_text())
    if text:
        email_match = re.search(r"[\w.\-+]+@[\w.\-]+\.\w+", text)
        if email_match:
            return email_match.group().lower()

    return None
