"""OpenObjects kb5 platform scraper.

Covers ~68 LAs using the OpenObjects kb5 directory platform.
Uses requests + BeautifulSoup (no Playwright needed).

Key URL patterns:
  - Results listing: {base}/results.page?{channel_param}&sr={offset}
  - Provider detail: {base}/service.page?id={record_id}
  - Pagination: sr=0, sr=10, sr=20, ... (10 results per page)

Detail page structure:
  - Title in <h1>
  - Venue section: class="field_section service_venue" contains <dl>
    with <dt>Name, <dt>Address (with <span> lines), <dt>Postcode
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Iterator
from urllib.parse import urlencode, urljoin, urlparse, parse_qs

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

# Channel parameter names used across kb5 sites
_CHANNEL_PARAMS = (
    "familychannelnew",
    "familychannel",
    "familieschannel",  # Oxfordshire
    "camcommunitychannel",
    "directorychannel",
    "childcarechannel",
)

# If no channel info in the URL, try these in order to find childcare
_CHILDCARE_CHANNEL_ATTEMPTS = [
    {"familychannelnew": "1"},
    {"familychannel": "2"},
    {"familychannel": "1"},
]

_USER_AGENT = "BSIL-DataPipeline/1.0 (research; best-start-in-life)"
_REQUEST_TIMEOUT = 20

_rate_limiter = DomainRateLimiter(default_interval=1.0)


class OpenObjectsScraper(BaseScraper):
    @property
    def platform_key(self) -> str:
        return "openobjects_kb5"

    def scrape_la(
        self,
        lad25cd: str,
        fis_url: str,
        existing_provider_ids: set[str],
        logger: Logger,
    ) -> Iterator[ProviderResult]:
        """Scrape all childcare providers from a kb5 directory."""
        session = requests.Session()
        session.headers.update({"User-Agent": _USER_AGENT})

        base_url = _extract_base_url(fis_url)
        logger.info(f"kb5 base URL: {base_url}")

        # Determine channel parameters for childcare results
        channel_params = _extract_channel_params(fis_url)
        results_url = _build_results_url(base_url, channel_params)
        logger.info(f"Results URL: {results_url}")

        # Paginate through all results
        provider_ids_found = 0
        offset = 0
        page_num = 0

        while True:
            page_url = results_url + (f"&sr={offset}" if offset > 0 else "")

            resp = fetch(
                session, page_url, timeout=_REQUEST_TIMEOUT, rate_limiter=_rate_limiter
            )

            soup = BeautifulSoup(resp.text, "html.parser")

            # Extract service links from this page
            service_links = _extract_service_links(soup, base_url)
            if not service_links:
                if page_num == 0:
                    logger.warning(
                        f"No service links found on first results page for {lad25cd}"
                    )
                break

            for record_id, detail_url in service_links:
                if record_id in existing_provider_ids:
                    continue

                result = _scrape_detail_page(
                    session, lad25cd, record_id, detail_url, logger
                )
                provider_ids_found += 1
                yield result

            # Check if there are more pages
            next_offset = _get_next_offset(soup, offset)
            if next_offset is None:
                break

            offset = next_offset
            page_num += 1

        logger.info(
            f"kb5 scrape complete for {lad25cd}: "
            f"{provider_ids_found} providers found across {page_num + 1} pages"
        )


def _extract_base_url(fis_url: str) -> str:
    """Extract the kb5 base URL (everything up to and including the directory name).

    e.g. https://fis.middlesbrough.gov.uk/kb5/middlesbrough/fsd/home.page
      -> https://fis.middlesbrough.gov.uk/kb5/middlesbrough/fsd/
    """
    parsed = urlparse(fis_url)
    # Find /kb5/{council}/{directory}/ part
    match = re.search(r"(/kb5/[^/]+/[^/]+/)", parsed.path)
    if match:
        return f"{parsed.scheme}://{parsed.netloc}{match.group(1)}"
    # Fallback: use everything up to the last / in path
    path = parsed.path.rsplit("/", 1)[0] + "/"
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def _extract_channel_params(fis_url: str) -> dict[str, str]:
    """Extract channel parameters from the FIS URL if present."""
    parsed = urlparse(fis_url)
    qs = parse_qs(parsed.query)

    params = {}
    for param_name in _CHANNEL_PARAMS:
        if param_name in qs:
            params[param_name] = qs[param_name][0]

    return params


def _build_results_url(base_url: str, channel_params: dict[str, str]) -> str:
    """Build the results page URL from base and channel parameters."""
    if channel_params:
        return base_url + "results.page?" + urlencode(channel_params)

    # No channel params — use the most common childcare channel
    return base_url + "results.page?" + urlencode(_CHILDCARE_CHANNEL_ATTEMPTS[0])


def _extract_service_links(soup: BeautifulSoup, base_url: str) -> list[tuple[str, str]]:
    """Extract (record_id, full_url) tuples from a results page.

    Only extracts service.page links — advice.page links are info/guidance
    pages, not childcare providers.
    """
    links = []
    seen_ids: set[str] = set()

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if "service.page?id=" not in href:
            continue

        match = re.search(r"service\.page\?id=([^&\"]+)", href)
        if not match:
            continue

        record_id = match.group(1)
        if record_id in seen_ids:
            continue
        seen_ids.add(record_id)

        full_url = urljoin(base_url, f"service.page?id={record_id}")
        links.append((record_id, full_url))

    return links


def _get_next_offset(soup: BeautifulSoup, current_offset: int) -> int | None:
    """Find the next pagination offset from the results page.

    Looks for pagination links with sr= parameter.
    Returns the next offset, or None if we're on the last page.
    """
    offsets = set()
    for a_tag in soup.find_all("a", href=True):
        match = re.search(r"sr=(\d+)", a_tag["href"])
        if match:
            offsets.add(int(match.group(1)))

    # Find the smallest offset larger than current
    next_offsets = sorted(o for o in offsets if o > current_offset)

    # Only follow the immediately next page (current + 10)
    expected_next = current_offset + 10
    if expected_next in offsets:
        return expected_next

    # If exact next isn't there but there are higher offsets, it might be
    # the last page link — check if next sequential page exists
    if next_offsets and next_offsets[0] == expected_next:
        return next_offsets[0]

    return None


def _scrape_detail_page(
    session: requests.Session,
    lad25cd: str,
    record_id: str,
    detail_url: str,
    logger: Logger,
) -> ProviderResult:
    """Fetch and parse a kb5 service/advice detail page."""
    resp = fetch(
        session, detail_url, timeout=_REQUEST_TIMEOUT, rate_limiter=_rate_limiter
    )

    html = resp.text
    soup = BeautifulSoup(html, "html.parser")

    # Extract provider name from <h1>
    h1 = soup.find("h1")
    provider_name = clean_text(h1.get_text()) if h1 else None

    # Extract address from service_venue section
    address_info = _parse_venue_section(soup)

    status = "error"
    if provider_name and address_info.get("postcode"):
        status = "success"
    elif provider_name or address_info.get("postcode"):
        status = "partial"

    return ProviderResult(
        lad25cd=lad25cd,
        provider_id=record_id,
        provider_name=provider_name,
        provider_address_line1=address_info.get("address_line1"),
        provider_address_line2=address_info.get("address_line2"),
        provider_address_line3=address_info.get("address_line3"),
        provider_town=address_info.get("town"),
        provider_postcode=address_info.get("postcode"),
        source_url=detail_url,
        raw_html=html,
        scrape_status=status,
    )


def _parse_venue_section(soup: BeautifulSoup) -> dict[str, str | None]:
    """Parse the service_venue section for address details.

    Expected structure:
        <section class="field_section service_venue">
            <dl>
                <dt>Name</dt><dd>...</dd>
                <dt>Address</dt><dd><span>line1</span><br/><span>line2</span>...</dd>
                <dt>Postcode</dt><dd><span>XX1 2YY</span></dd>
            </dl>
        </section>
    """
    result: dict[str, str | None] = {
        "address_line1": None,
        "address_line2": None,
        "address_line3": None,
        "town": None,
        "postcode": None,
    }

    # Find the venue section
    venue = soup.find(class_=re.compile(r"service_venue"))
    if not venue:
        return result

    dl = venue.find("dl")
    if not dl:
        return result

    # Walk through dt/dd pairs
    current_dt = None
    for child in dl.children:
        if child.name == "dt":
            current_dt = clean_text(child.get_text())
        elif child.name == "dd" and current_dt:
            if current_dt.lower() == "postcode":
                result["postcode"] = clean_text(child.get_text())
            elif current_dt.lower() == "address":
                # Address lines are in <span> tags separated by <br/>
                spans = child.find_all("span")
                if spans:
                    lines = [
                        clean_text(s.get_text())
                        for s in spans
                        if clean_text(s.get_text())
                    ]
                else:
                    # Fallback: split by <br> or commas
                    text = child.get_text(separator=",")
                    lines = [clean_text(p) for p in text.split(",") if clean_text(p)]

                # Last line is typically the town
                if lines:
                    result["town"] = lines[-1]
                    lines = lines[:-1]

                if len(lines) >= 1:
                    result["address_line1"] = lines[0]
                if len(lines) >= 2:
                    result["address_line2"] = lines[1]
                if len(lines) >= 3:
                    result["address_line3"] = ", ".join(lines[2:])

            current_dt = None

    return result
