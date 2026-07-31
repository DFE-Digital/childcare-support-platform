"""AFC (Achieving for Children) platform scraper.

Covers 3 LAs via afcinfo.org.uk (powered by "hubb" by focusgov):
- Kingston upon Thames + Richmond upon Thames: kr.afcinfo.org.uk
- Windsor and Maidenhead: rbwm.afcinfo.org.uk

The platform has a JSON API endpoint that returns all providers matching
a category filter in a single request (used by the map component):
  /{subdomain}/childcare_providers?format=json&skip_tracking=true
    &search_childcare_provider[category_ids][]={category_id}

Returns: {"markers": [{"content": "<a href=...>Name</a>", "latitude": ..., "longitude": ...}]}

Detail pages at /childcare_providers/{id}-{slug} have structured fields:
  - Contact Details: Telephone, Email
  - OFSTED number
  - Address Details: Address 1, Address 2, Borough, Town, Postcode

Pagination for HTML: ?page=N with ?per_page=50 (max observed).
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Iterator
from urllib.parse import urljoin, urlparse, urlencode

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
_REQUEST_TIMEOUT = 20

_rate_limiter = DomainRateLimiter(default_interval=1.0)

# Category IDs for childcare providers on AFC sites
# These are the same across both kr. and rbwm. subdomains
_CHILDCARE_CATEGORIES = [
    3575,  # Registered childminders
    3577,  # Full daycare (nursery)
    3578,  # Independent (private) school nurseries
    3579,  # School nurseries and classes
    3580,  # Pre school nursery/playgroup
    3573,  # Breakfast Clubs
    3572,  # After school clubs
    3574,  # Holiday playschemes
    3576,  # Creches
]

# Map LA codes to AFC subdomains
_LA_SUBDOMAINS: dict[str, str] = {
    "E09000021": "kr.afcinfo.org.uk",  # Kingston upon Thames
    "E09000027": "kr.afcinfo.org.uk",  # Richmond upon Thames
    "E06000040": "rbwm.afcinfo.org.uk",  # Windsor and Maidenhead
}

# Module-level cache per domain
_afc_cache: dict[str, list[dict]] = {}


class AfcScraper(BaseScraper):
    @property
    def platform_key(self) -> str:
        return "afc"

    def scrape_la(
        self,
        lad25cd: str,
        fis_url: str,
        existing_provider_ids: set[str],
        logger: Logger,
    ) -> Iterator[ProviderResult]:
        """Scrape childcare providers from an AFC info site."""
        domain = _get_domain(fis_url, lad25cd)
        if not domain:
            logger.warning(f"AFC: unknown domain for {lad25cd}: {fis_url}")
            yield ProviderResult(
                lad25cd=lad25cd,
                provider_id="__unknown_domain__",
                scrape_status="error",
                source_url=fis_url,
            )
            return

        # Cache per domain (kr shares Kingston + Richmond)
        if domain not in _afc_cache:
            logger.info(f"AFC: scraping all providers from {domain}")
            _afc_cache[domain] = _scrape_afc_domain(domain, logger)
            logger.info(
                f"AFC: cached {len(_afc_cache[domain])} providers from {domain}"
            )
        else:
            logger.info(
                f"AFC: using cached results ({len(_afc_cache[domain])} "
                f"providers) for {lad25cd}"
            )

        yielded = 0
        for raw in _afc_cache[domain]:
            pid = raw["provider_id"]
            if pid in existing_provider_ids:
                continue
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
                provider_latitude=raw.get("latitude"),
                provider_longitude=raw.get("longitude"),
                source_url=raw.get("source_url"),
                raw_html=raw.get("raw_html"),
                scrape_status=raw.get("scrape_status", "error"),
            )
            yielded += 1

        logger.info(f"AFC: yielded {yielded} providers for {lad25cd}")


def _get_domain(fis_url: str, lad25cd: str) -> str | None:
    """Determine the AFC domain from URL or LA code."""
    if lad25cd in _LA_SUBDOMAINS:
        return _LA_SUBDOMAINS[lad25cd]

    parsed = urlparse(fis_url)
    domain = parsed.netloc.lower()
    if "afcinfo.org.uk" in domain:
        return domain

    return None


def _scrape_afc_domain(domain: str, logger: Logger) -> list[dict]:
    """Scrape all childcare providers from an AFC domain.

    1. Use JSON API to collect all provider IDs and URLs per category
    2. Fetch detail pages for each unique provider
    """
    session = requests.Session()
    session.headers.update({"User-Agent": _USER_AGENT})

    base_url = f"https://{domain}"

    # Step 1: Collect provider URLs and coords from JSON API for each category
    provider_urls: dict[str, str] = {}  # id -> detail_url
    provider_coords: dict[str, tuple[float, float]] = {}  # id -> (lat, lon)
    for cat_id in _CHILDCARE_CATEGORIES:
        urls, coords = _fetch_json_markers(session, base_url, cat_id, logger)
        for pid, detail_url in urls.items():
            if pid not in provider_urls:
                provider_urls[pid] = detail_url
                if pid in coords:
                    provider_coords[pid] = coords[pid]

    logger.info(
        f"AFC {domain}: collected {len(provider_urls)} unique providers from JSON API"
    )

    # If JSON API returned nothing, fall back to HTML pagination
    if not provider_urls:
        provider_urls = _collect_from_html(session, base_url, logger)
        logger.info(
            f"AFC {domain}: collected {len(provider_urls)} providers from HTML fallback"
        )

    # Step 2: Fetch detail pages
    results: list[dict] = []
    for i, (pid, detail_url) in enumerate(provider_urls.items()):
        result = _scrape_detail_page(session, pid, detail_url, logger)

        # Inject coordinates from JSON markers if available
        if pid in provider_coords and not result.get("latitude"):
            lat, lon = provider_coords[pid]
            result["latitude"] = lat
            result["longitude"] = lon

        # Re-evaluate status now that coords may have been added
        if result.get("scrape_status") == "partial":
            has_name = bool(result.get("provider_name"))
            has_coords = (
                result.get("latitude") is not None
                and result.get("longitude") is not None
            )
            if has_name and has_coords:
                result["scrape_status"] = "success"

        results.append(result)

        if (i + 1) % 50 == 0:
            logger.info(f"AFC {domain}: scraped {i + 1}/{len(provider_urls)} details")

    return results


def _fetch_json_markers(
    session: requests.Session,
    base_url: str,
    category_id: int,
    logger: Logger,
) -> tuple[dict[str, str], dict[str, tuple[float, float]]]:
    """Fetch provider markers from the JSON API for a category.

    Returns (urls, coords) where urls is provider_id -> detail_url
    and coords is provider_id -> (lat, lon).
    """
    params = {
        "format": "json",
        "skip_tracking": "true",
        "search_childcare_provider[category_ids][]": str(category_id),
    }
    url = f"{base_url}/childcare_providers?{urlencode(params)}"

    resp = fetch(session, url, timeout=_REQUEST_TIMEOUT, rate_limiter=_rate_limiter)

    try:
        data = resp.json()
    except (json.JSONDecodeError, ValueError):
        logger.warning(f"AFC JSON API returned invalid JSON for category {category_id}")
        return {}, {}

    markers = data.get("markers", [])
    results: dict[str, str] = {}
    coords: dict[str, tuple[float, float]] = {}

    for marker in markers:
        content = marker.get("content", "")
        # Content is HTML: <a href="/main_site/childcare_providers/39307-...">Name</a>
        # or <a href="/childcare_providers/39307-...">Name</a>
        match = re.search(
            r'href="([^"]*?/childcare_providers/(\d+)-[^"]*)"',
            content,
        )
        if match:
            path = match.group(1)
            pid = match.group(2)
            detail_url = f"{base_url}{path}" if path.startswith("/") else path
            results[pid] = detail_url

            lat = marker.get("latitude")
            lon = marker.get("longitude")
            if lat is not None and lon is not None:
                try:
                    coords[pid] = (float(lat), float(lon))
                except (ValueError, TypeError):
                    pass

    return results, coords


def _collect_from_html(
    session: requests.Session,
    base_url: str,
    logger: Logger,
) -> dict[str, str]:
    """Fallback: collect providers by paginating HTML listing pages."""
    results: dict[str, str] = {}
    page = 1

    while True:
        url = f"{base_url}/childcare_providers?page={page}&per_page=50"

        resp = fetch(session, url, timeout=_REQUEST_TIMEOUT, rate_limiter=_rate_limiter)
        soup = BeautifulSoup(resp.text, "html.parser")

        # Find provider links
        found = 0
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            match = re.search(r"/childcare_providers/(\d+)-", href)
            if match:
                pid = match.group(1)
                if pid not in results:
                    detail_url = urljoin(base_url, href)
                    results[pid] = detail_url
                    found += 1

        if found == 0:
            break

        # Check for next page
        next_link = soup.find("a", rel="next")
        if not next_link:
            break

        page += 1
        if page > 50:
            logger.warning("AFC HTML pagination safety limit")
            break

    return results


def _scrape_detail_page(
    session: requests.Session,
    provider_id: str,
    detail_url: str,
    logger: Logger,
) -> dict:
    """Fetch and parse an AFC provider detail page."""
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

    # Extract address and other fields from labeled sections
    _extract_detail_fields(soup, result)

    # Determine status — accept lat/lng as equivalent to postcode
    has_name = bool(result.get("provider_name"))
    has_postcode = bool(result.get("postcode"))
    has_coords = (
        result.get("latitude") is not None and result.get("longitude") is not None
    )

    if has_name and (has_postcode or has_coords):
        result["scrape_status"] = "success"
    elif has_name or has_postcode:
        result["scrape_status"] = "partial"

    return result


def _extract_detail_fields(soup: BeautifulSoup, result: dict) -> None:
    """Extract structured fields from an AFC detail page.

    The page uses labeled sections with dt/dd pairs or
    label/value patterns like:
      <dt>Address 1</dt><dd>...</dd>
      <dt>Postcode</dt><dd>...</dd>
      <dt>OFSTED number</dt><dd>...</dd>
    """
    # Look for dt/dd pairs
    for dt in soup.find_all("dt"):
        dt_text = clean_text(dt.get_text()) or ""
        dd = dt.find_next_sibling("dd")
        if not dd:
            continue
        dd_text = clean_text(dd.get_text())
        if not dd_text:
            continue

        dt_lower = dt_text.lower().strip()

        if dt_lower == "address 1":
            result["address_line1"] = dd_text
        elif dt_lower == "address 2":
            result["address_line2"] = dd_text
        elif dt_lower == "postcode":
            result["postcode"] = dd_text.upper()
        elif dt_lower in ("town", "city"):
            result["town"] = dd_text
        elif dt_lower == "borough":
            if not result.get("town"):
                result["town"] = dd_text
        elif dt_lower == "ofsted number":
            result["urn"] = dd_text
        elif dt_lower == "telephone":
            pass  # Not stored in ProviderResult

    # Fallback: look for labeled spans/paragraphs
    if not result.get("postcode"):
        for text_el in soup.find_all(["p", "span", "div"]):
            text = text_el.get_text()
            if "Postcode:" in text:
                match = re.search(r"Postcode:\s*(\S+)", text)
                if match:
                    result["postcode"] = match.group(1).upper()
                    break
