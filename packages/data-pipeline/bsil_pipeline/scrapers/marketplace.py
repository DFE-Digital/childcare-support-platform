"""Open Objects Marketplace scraper.

Covers 21 LAs across 6 Marketplace domains:
- directory.hertfordshire.gov.uk (6 Herts districts)
- 1space.eastsussex.gov.uk (5 E.Sussex districts)
- communitydirectory.norfolk.gov.uk (7 Norfolk districts)
- livingwell.darlington.gov.uk (1 LA)
- www.livewell.cheshirewestandchester.gov.uk (1 LA)
- careandsupport.hillingdon.gov.uk (1 LA)

All sites share the same Open Objects Marketplace HTML structure:
  - Search URL: /Search?CategoryId={id}&SM=ServiceSearch&SME=True
  - Results: bem-search-result-item__title links, paginated via ServicePageIndex
  - Service detail: /Services/{id} with <h1> name and <dt>/<dd> pairs
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterator
from urllib.parse import urlparse

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

if TYPE_CHECKING:
    from logging import Logger


# ---------------------------------------------------------------------------
# Per-deployment configuration
# ---------------------------------------------------------------------------


@dataclass
class MarketplaceDeployment:
    """Configuration for a single Marketplace deployment."""

    domain: str
    category_id: int
    multi_la: bool = False


DEPLOYMENTS: dict[str, MarketplaceDeployment] = {
    "directory.hertfordshire.gov.uk": MarketplaceDeployment(
        domain="directory.hertfordshire.gov.uk",
        category_id=31,
        multi_la=True,
    ),
    "1space.eastsussex.gov.uk": MarketplaceDeployment(
        domain="1space.eastsussex.gov.uk",
        category_id=346,
        multi_la=True,
    ),
    "livingwell.darlington.gov.uk": MarketplaceDeployment(
        domain="livingwell.darlington.gov.uk",
        category_id=475,
    ),
    "www.livewell.cheshirewestandchester.gov.uk": MarketplaceDeployment(
        domain="www.livewell.cheshirewestandchester.gov.uk",
        category_id=3948,
    ),
    "careandsupport.hillingdon.gov.uk": MarketplaceDeployment(
        domain="careandsupport.hillingdon.gov.uk",
        category_id=133,
    ),
    "communitydirectory.norfolk.gov.uk": MarketplaceDeployment(
        domain="communitydirectory.norfolk.gov.uk",
        category_id=73,
        multi_la=True,
    ),
}

_USER_AGENT = "BSIL-DataPipeline/1.0 (research; best-start-in-life)"
_REQUEST_TIMEOUT = 30
_DIRECTIONS_NOISE_RE = re.compile(r"\s*\(directions displayed on map\)", re.IGNORECASE)

_rate_limiter = DomainRateLimiter(default_interval=1.0)

# Cache for multi-LA deployments: domain -> list of raw results
_multi_la_cache: dict[str, list[dict]] = {}


class MarketplaceScraper(BaseScraper):
    @property
    def platform_key(self) -> str:
        return "marketplace"

    def scrape_la(
        self,
        lad25cd: str,
        fis_url: str,
        existing_provider_ids: set[str],
        logger: Logger,
    ) -> Iterator[ProviderResult]:
        """Scrape childcare providers from an Open Objects Marketplace site."""
        deployment = _get_deployment(fis_url)
        if deployment is None:
            logger.warning(
                f"No Marketplace deployment config for {fis_url} ({lad25cd})"
            )
            yield ProviderResult(
                lad25cd=lad25cd,
                provider_id="__no_deployment_config__",
                scrape_status="unsupported_platform",
                source_url=fis_url,
            )
            return

        domain = deployment.domain

        # For multi-LA deployments, scrape once and cache
        if deployment.multi_la:
            if domain not in _multi_la_cache:
                logger.info(f"Multi-LA Marketplace {domain}: scraping all providers")
                _multi_la_cache[domain] = _scrape_deployment(deployment, logger)
                logger.info(
                    f"Cached {len(_multi_la_cache[domain])} providers from {domain}"
                )
            else:
                logger.info(
                    f"Multi-LA Marketplace {domain}: using cached results "
                    f"({len(_multi_la_cache[domain])} providers)"
                )
            raw_results = _multi_la_cache[domain]
        else:
            logger.info(f"Single-LA Marketplace {domain}: scraping for {lad25cd}")
            raw_results = _scrape_deployment(deployment, logger)

        # Yield ProviderResults, skipping already-scraped IDs
        yielded = 0
        for raw in raw_results:
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
                source_url=raw.get("source_url"),
                raw_html=raw.get("raw_html"),
                scrape_status=raw.get("scrape_status", "error"),
            )
            yielded += 1

        logger.info(f"Marketplace {domain}: yielded {yielded} providers for {lad25cd}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_deployment(fis_url: str) -> MarketplaceDeployment | None:
    """Look up the deployment config for a given FIS URL."""
    parsed = urlparse(fis_url.lower())
    domain = parsed.netloc

    if domain in DEPLOYMENTS:
        return DEPLOYMENTS[domain]

    # Partial match (e.g. URL with/without www prefix)
    for key, dep in DEPLOYMENTS.items():
        if key in domain or domain in key:
            return dep

    return None


def _scrape_deployment(deployment: MarketplaceDeployment, logger: Logger) -> list[dict]:
    """Scrape all childcare providers from a Marketplace deployment.

    1. Paginate through search results to collect service IDs and links
    2. Fetch each service detail page
    """
    session = requests.Session()
    session.headers.update({"User-Agent": _USER_AGENT})

    base_url = f"https://{deployment.domain}"

    # Step 1: Collect all service listings from paginated search
    listings = _collect_all_listings(session, base_url, deployment.category_id, logger)
    logger.info(f"Found {len(listings)} services on {deployment.domain}")

    # Step 2: Fetch detail pages
    results: list[dict] = []
    for i, listing in enumerate(listings):
        detail_url = listing["detail_url"]

        result = _scrape_detail_page(session, listing["service_id"], detail_url, logger)
        results.append(result)

        if (i + 1) % 50 == 0:
            logger.info(
                f"Scraped {i + 1}/{len(listings)} detail pages on {deployment.domain}"
            )

    return results


def _collect_all_listings(
    session: requests.Session,
    base_url: str,
    category_id: int,
    logger: Logger,
) -> list[dict]:
    """Paginate through search results and collect service listings.

    Marketplace pagination is 1-indexed: the first page has no
    ServicePageIndex param; subsequent pages use ServicePageIndex=2, 3, etc.
    """
    all_listings: list[dict] = []
    seen_ids: set[str] = set()
    page_num = 1  # 1-indexed

    while True:
        search_url = (
            f"{base_url}/Search?CategoryId={category_id}&SM=ServiceSearch&SME=True"
        )
        if page_num > 1:
            search_url += f"&ServicePageIndex={page_num}"

        resp = fetch(
            session, search_url, timeout=_REQUEST_TIMEOUT, rate_limiter=_rate_limiter
        )

        soup = BeautifulSoup(resp.text, "html.parser")
        page_listings = _parse_results_page(soup, base_url)

        # Deduplicate
        new_listings = []
        for listing in page_listings:
            sid = listing["service_id"]
            if sid not in seen_ids:
                seen_ids.add(sid)
                new_listings.append(listing)

        if not new_listings:
            break

        all_listings.extend(new_listings)
        logger.info(
            f"Search page {page_num}: {len(new_listings)} new services "
            f"(total: {len(all_listings)})"
        )

        # Check if there's a next page link (ServicePageIndex={N+1})
        next_page = page_num + 1
        has_next = bool(
            soup.find("a", href=re.compile(rf"ServicePageIndex={next_page}(?:\D|$)"))
        )
        if not has_next:
            break

        page_num += 1

        # Safety limit
        if page_num > 500:
            logger.warning("Hit pagination safety limit (500 pages)")
            break

    return all_listings


def _parse_results_page(soup: BeautifulSoup, base_url: str) -> list[dict]:
    """Extract service listings from a search results page.

    Each result card is a ``<div data-service-id="NNN">`` containing a
    title link. We locate results via the ``data-service-id`` attribute
    rather than CSS class regex, because BS4 4.13+ changed multi-valued
    class matching and broke the old ``class_=re.compile(...)`` approach.
    """
    listings: list[dict] = []

    result_cards = soup.find_all("div", attrs={"data-service-id": True})

    for card in result_cards:
        service_id = card["data-service-id"]

        link = (
            card.find("a", class_="service-name")
            or card.find("a", attrs={"itemprop": "url"})
            or card.find("a", href=re.compile(r"/Services/\d+"))
        )

        name = clean_text(link.get_text()) if link else None
        detail_url = f"{base_url}/Services/{service_id}"

        listings.append(
            {
                "service_id": service_id,
                "name": name,
                "detail_url": detail_url,
            }
        )

    return listings


def _scrape_detail_page(
    session: requests.Session,
    service_id: str,
    detail_url: str,
    logger: Logger,
) -> dict:
    """Fetch and parse a Marketplace service detail page."""
    result: dict = {
        "provider_id": service_id,
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

    # Extract fields from <dt>/<dd> pairs
    _extract_dt_dd_fields(soup, result)

    # Determine scrape status
    has_name = bool(result.get("provider_name"))
    has_postcode = bool(result.get("postcode"))

    if has_name and has_postcode:
        result["scrape_status"] = "success"
    elif has_name or has_postcode:
        result["scrape_status"] = "partial"

    return result


def _extract_dt_dd_fields(soup: BeautifulSoup, result: dict) -> None:
    """Extract address, Ofsted URN, and district from <dt>/<dd> pairs."""
    dts = soup.find_all("dt")

    for dt in dts:
        label = clean_text(dt.get_text()) or ""
        label_lower = label.lower()

        dd = dt.find_next_sibling("dd")
        if not dd:
            continue
        value = clean_text(dd.get_text())
        if not value:
            continue

        if label_lower in ("locations", "address"):
            # Strip "(directions displayed on map)" noise from dd text
            cleaned_value = _DIRECTIONS_NOISE_RE.sub("", value).strip()
            if not cleaned_value:
                continue
            addr = parse_address_parts(cleaned_value)
            if addr.get("address_line1"):
                result["address_line1"] = addr["address_line1"]
            if addr.get("address_line2"):
                result["address_line2"] = addr["address_line2"]
            if addr.get("address_line3"):
                result["address_line3"] = addr["address_line3"]
            if addr.get("town"):
                result["town"] = addr["town"]
            if addr.get("postcode"):
                result["postcode"] = addr["postcode"]

        elif "ofsted" in label_lower and (
            "reference" in label_lower or "report" in label_lower
        ):
            # Norfolk uses "Ofsted reports:" with a link containing the URN
            # Try to extract URN from an Ofsted link URL first
            ofsted_link = dd.find("a", href=re.compile(r"ofsted\.gov\.uk"))
            if ofsted_link:
                urn_match = re.search(r"/(\d{5,7})(?:\D|$)", ofsted_link["href"])
                if urn_match:
                    result["urn"] = urn_match.group(1)
            if "urn" not in result:
                # Fallback: use the text value directly
                urn_text = re.search(r"\d{5,7}", value)
                if urn_text:
                    result["urn"] = urn_text.group(0)

        elif label_lower == "district":
            result["district"] = value
