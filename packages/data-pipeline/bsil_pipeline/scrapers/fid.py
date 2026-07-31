"""Family Information Directory (FID) scraper.

Covers 3 LAs using the ASP.NET MVC "Family Information Directory" platform:
- fid.cumberland.gov.uk (Cumberland, E06000063)
- familydirectory.northlincs.gov.uk (North Lincolnshire, E06000013)
- fid.bexley.gov.uk (Bexley, E09000004)

All sites share the same structure:
  - Search form: GET /Provider with category select dropdown
  - Results: div.panel.panel-default with <h3> names and "View Profile" links
  - Detail: GET /Provider/Details?providerId={id} with structured fields
  - No pagination (capped at 200 results per search)
  - Strategy: iterate subcategories, deduplicate by provider ID
  - Fallback: when a site has no usable categories, use geo-search grid
    (postcode + lat/lon + radius) to work around the 200-result cap
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Iterator
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from bsil_pipeline.scrapers.base import (
    BaseScraper,
    ProviderResult,
    clean_text,
    parse_address_parts,
)
from bsil_pipeline.scrapers.http import fetch
from bsil_pipeline.scrapers.rate_limiter import DomainRateLimiter

if TYPE_CHECKING:
    from logging import Logger


# ---------------------------------------------------------------------------
# Per-deployment configuration
# ---------------------------------------------------------------------------


@dataclass
class _GeoPoint:
    """A postcode + lat/lon used for radius-based searches."""

    postcode: str
    lat: float
    lon: float


@dataclass
class FidDeployment:
    """Configuration for a single FID deployment."""

    domain: str
    lad25cd: str
    # Geo-search grid: when categories are empty, search these points
    # at 1-mile radius to work around the 200-result cap.
    geo_points: list[_GeoPoint] | None = None


DEPLOYMENTS: dict[str, FidDeployment] = {
    "fid.cumberland.gov.uk": FidDeployment(
        domain="fid.cumberland.gov.uk",
        lad25cd="E06000063",
    ),
    "familydirectory.northlincs.gov.uk": FidDeployment(
        domain="familydirectory.northlincs.gov.uk",
        lad25cd="E06000013",
    ),
    "fid.bexley.gov.uk": FidDeployment(
        domain="fid.bexley.gov.uk",
        lad25cd="E09000004",
        geo_points=[
            _GeoPoint("DA5 1AA", 51.432, 0.134),  # Bexley village
            _GeoPoint("DA6 7AP", 51.441, 0.150),  # Bexleyheath centre
            _GeoPoint("DA7 4NR", 51.455, 0.158),  # Barnehurst
            _GeoPoint("DA8 1QY", 51.480, 0.176),  # Erith
            _GeoPoint("DA14 5BN", 51.424, 0.105),  # Sidcup
            _GeoPoint("DA15 7HB", 51.434, 0.115),  # Blackfen
            _GeoPoint("DA16 1QQ", 51.462, 0.115),  # Welling
            _GeoPoint("DA17 5AW", 51.490, 0.138),  # Belvedere
            _GeoPoint("DA18 4AJ", 51.497, 0.117),  # Thamesmead
            _GeoPoint("SE2 0AT", 51.486, 0.107),  # Abbey Wood
            _GeoPoint("DA8 3LS", 51.468, 0.185),  # Slade Green
            _GeoPoint("SE9 2PW", 51.445, 0.098),  # New Eltham border
        ],
    ),
}

_USER_AGENT = "BSIL-DataPipeline/1.0 (research; best-start-in-life)"
_REQUEST_TIMEOUT = 30

_rate_limiter = DomainRateLimiter(default_interval=1.0)


class FidScraper(BaseScraper):
    @property
    def platform_key(self) -> str:
        return "fid"

    def scrape_la(
        self,
        lad25cd: str,
        fis_url: str,
        existing_provider_ids: set[str],
        logger: Logger,
    ) -> Iterator[ProviderResult]:
        """Scrape childcare providers from a FID platform site."""
        deployment = _get_deployment(fis_url)
        if deployment is None:
            logger.warning(f"No FID deployment config for {fis_url} ({lad25cd})")
            yield ProviderResult(
                lad25cd=lad25cd,
                provider_id="__no_deployment_config__",
                scrape_status="unsupported_platform",
                source_url=fis_url,
            )
            return

        session = requests.Session()
        session.headers.update({"User-Agent": _USER_AGENT})

        base_url = f"https://{deployment.domain}"

        # Step 1: Discover categories from the search form
        categories = _discover_categories(session, base_url, logger)

        # Step 2: Collect provider IDs — category search or geo-search fallback
        if categories:
            logger.info(f"FID {deployment.domain}: found {len(categories)} categories")
            all_provider_ids = _collect_provider_ids(
                session, base_url, categories, logger
            )
        elif deployment.geo_points:
            logger.info(
                f"FID {deployment.domain}: no categories, using geo-search "
                f"with {len(deployment.geo_points)} grid points"
            )
            all_provider_ids = _collect_provider_ids_geo(
                session, base_url, deployment.geo_points, logger
            )
        else:
            logger.warning(f"FID {deployment.domain}: no categories and no geo_points")
            yield ProviderResult(
                lad25cd=lad25cd,
                provider_id="__no_categories__",
                scrape_status="error",
                source_url=fis_url,
            )
            return

        logger.info(
            f"FID {deployment.domain}: found {len(all_provider_ids)} unique providers"
        )

        # Step 3: Fetch detail pages for new providers
        new_ids = all_provider_ids - existing_provider_ids
        logger.info(
            f"FID {deployment.domain}: {len(new_ids)} new providers to scrape "
            f"({len(existing_provider_ids)} already exist)"
        )

        yielded = 0
        for i, provider_id in enumerate(sorted(new_ids)):
            detail_url = f"{base_url}/Provider/Details?providerId={provider_id}"

            result = _scrape_detail_page(
                session, lad25cd, provider_id, detail_url, logger
            )
            yield result
            yielded += 1

            if yielded % 50 == 0:
                logger.info(
                    f"FID {deployment.domain}: scraped {yielded}/{len(new_ids)} detail pages"
                )

        logger.info(
            f"FID {deployment.domain}: yielded {yielded} providers for {lad25cd}"
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_deployment(fis_url: str) -> FidDeployment | None:
    """Look up the deployment config for a given FIS URL."""
    parsed = urlparse(fis_url.lower())
    domain = parsed.netloc

    if domain in DEPLOYMENTS:
        return DEPLOYMENTS[domain]

    for key, dep in DEPLOYMENTS.items():
        if key in domain or domain in key:
            return dep

    return None


def _discover_categories(
    session: requests.Session,
    base_url: str,
    logger: Logger,
) -> list[tuple[str, str]]:
    """Fetch the search page and extract category options.

    Returns list of (category_id, category_name) tuples.
    """
    search_url = f"{base_url}/Provider"

    resp = fetch(
        session, search_url, timeout=_REQUEST_TIMEOUT, rate_limiter=_rate_limiter
    )

    soup = BeautifulSoup(resp.text, "html.parser")
    select = soup.find("select", id="CategorySelectList")
    if not select:
        # Try alternative IDs
        select = soup.find("select", attrs={"name": re.compile(r"category", re.I)})

    if not select:
        logger.warning(f"No category select found on {search_url}")
        return []

    categories = []
    for option in select.find_all("option"):
        value = option.get("value", "").strip()
        text = clean_text(option.get_text()) or ""
        # Skip empty/placeholder options
        if value and value != "0" and value != "":
            categories.append((value, text))

    return categories


def _collect_provider_ids(
    session: requests.Session,
    base_url: str,
    categories: list[tuple[str, str]],
    logger: Logger,
) -> set[str]:
    """Search each category and collect all unique provider IDs."""
    all_ids: set[str] = set()

    for cat_id, cat_name in categories:
        search_url = f"{base_url}/Provider?SelectedCategory={cat_id}"

        resp = fetch(
            session, search_url, timeout=_REQUEST_TIMEOUT, rate_limiter=_rate_limiter
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        page_ids = _extract_provider_ids_from_results(soup)
        new_count = len(page_ids - all_ids)
        all_ids.update(page_ids)

        logger.info(
            f"  Category '{cat_name}' ({cat_id}): "
            f"{len(page_ids)} results, {new_count} new (total: {len(all_ids)})"
        )

    return all_ids


def _collect_provider_ids_geo(
    session: requests.Session,
    base_url: str,
    geo_points: list[_GeoPoint],
    logger: Logger,
    proximity: int = 1,
) -> set[str]:
    """Search by postcode + radius at each grid point and collect provider IDs.

    Uses 1-mile radius by default to stay under the 200-result cap per search.
    """
    all_ids: set[str] = set()

    for point in geo_points:
        pc_encoded = point.postcode.replace(" ", "+")
        search_url = (
            f"{base_url}/Provider"
            f"?Postcode={pc_encoded}"
            f"&Proximity={proximity}"
            f"&Latitude={point.lat}"
            f"&Longitude={point.lon}"
        )

        resp = fetch(
            session, search_url, timeout=_REQUEST_TIMEOUT, rate_limiter=_rate_limiter
        )
        soup = BeautifulSoup(resp.text, "html.parser")
        page_ids = _extract_provider_ids_from_results(soup)
        new_count = len(page_ids - all_ids)
        all_ids.update(page_ids)

        logger.info(
            f"  Geo '{point.postcode}' ({proximity}mi): "
            f"{len(page_ids)} results, {new_count} new (total: {len(all_ids)})"
        )

    return all_ids


def _extract_provider_ids_from_results(soup: BeautifulSoup) -> set[str]:
    """Extract provider IDs from search results page.

    Provider IDs come from "View Profile" links with href like
    /Provider/Details?providerId={N}
    """
    ids: set[str] = set()

    # Find all links containing "providerId" in their href
    links = soup.find_all("a", href=re.compile(r"providerId=\d+", re.I))
    for link in links:
        href = link.get("href", "")
        match = re.search(r"providerId=(\d+)", href, re.I)
        if match:
            ids.add(match.group(1))

    return ids


def _scrape_detail_page(
    session: requests.Session,
    lad25cd: str,
    provider_id: str,
    detail_url: str,
    logger: Logger,
) -> ProviderResult:
    """Fetch and parse a FID provider detail page."""
    result = ProviderResult(
        lad25cd=lad25cd,
        provider_id=provider_id,
        source_url=detail_url,
        scrape_status="error",
    )

    resp = fetch(
        session, detail_url, timeout=_REQUEST_TIMEOUT, rate_limiter=_rate_limiter
    )

    html = resp.text
    result.raw_html = html
    soup = BeautifulSoup(html, "html.parser")

    # Provider name from <h1>
    h1 = soup.find("h1")
    if h1:
        result.provider_name = clean_text(h1.get_text())

    # Extract fields from bold labels
    _extract_bold_fields(soup, result)

    # Determine scrape status
    has_name = bool(result.provider_name)
    has_postcode = bool(result.provider_postcode)

    if has_name and has_postcode:
        result.scrape_status = "success"
    elif has_name or has_postcode:
        result.scrape_status = "partial"

    return result


def _extract_bold_fields(soup: BeautifulSoup, result: ProviderResult) -> None:
    """Extract address, phone, email from <b>Label:</b> text patterns.

    FID detail pages use <b>Address:</b>, <b>Phone:</b>, <b>Email:</b>
    followed by text content.
    """
    for bold in soup.find_all("b"):
        label = clean_text(bold.get_text()) or ""
        label_lower = label.lower().rstrip(":")

        # Get the text that follows the <b> tag
        # Walk next siblings to collect text until next <b> or block element
        value_parts = []
        for sibling in bold.next_siblings:
            if hasattr(sibling, "name") and sibling.name in (
                "b",
                "h1",
                "h2",
                "h3",
                "hr",
                "div",
            ):
                break
            text = sibling.get_text() if hasattr(sibling, "get_text") else str(sibling)
            text = text.strip()
            if text:
                value_parts.append(text)

        value = clean_text(" ".join(value_parts))
        if not value:
            continue

        if label_lower == "address":
            addr = parse_address_parts(value)
            result.provider_address_line1 = addr.get("address_line1")
            result.provider_address_line2 = addr.get("address_line2")
            result.provider_address_line3 = addr.get("address_line3")
            result.provider_town = addr.get("town")
            result.provider_postcode = addr.get("postcode")

        elif label_lower == "phone" or label_lower == "telephone":
            result.provider_phone = value

        elif label_lower == "email":
            result.provider_email = value
