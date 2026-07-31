"""PCG / PPL Innovate directory scraper.

Covers 3 LAs using the PCG (PPL Innovate) directory platform:
- directory.westberks.gov.uk (West Berkshire, E06000037)
- fyi.bradford.gov.uk (Bradford, E08000032)
- www.sheffielddirectory.org.uk (Sheffield, E08000019)

All sites share the same JSON API:
  GET /api/s4s-advanced-search/directory-search/get-list?searchParams={JSON}

The search API accepts a postcode, radius, and free-text search term.
Results are paginated (pageSize up to 100).

West Berkshire also has a working detail API:
  GET /api/s4s-advanced-search/directory-search/get-event/{id}
which returns full address/postcode/phone/email/lat/lon.

Bradford and Sheffield have no working detail API, so we use data from
list results only (phone/email but no address) → status "partial".
"""

from __future__ import annotations

import json
import urllib.parse
from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterator

import requests

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
class PcgDeployment:
    """Configuration for a single PCG directory deployment."""

    domain: str
    lad25cd: str
    base_url: str
    search_postcode: str  # Central postcode for the LA area
    search_radius: int  # In metres (32186 ≈ 20mi)
    has_detail_api: bool  # Whether get-event/{id} works
    value_wrapped: bool  # Whether response JSON is wrapped in {"value": ...}


DEPLOYMENTS: dict[str, PcgDeployment] = {
    "directory.westberks.gov.uk": PcgDeployment(
        domain="directory.westberks.gov.uk",
        lad25cd="E06000037",
        base_url="https://directory.westberks.gov.uk",
        search_postcode="RG14 1JN",
        search_radius=32186,
        has_detail_api=True,
        value_wrapped=False,
    ),
    "fyi.bradford.gov.uk": PcgDeployment(
        domain="fyi.bradford.gov.uk",
        lad25cd="E08000032",
        base_url="https://fyi.bradford.gov.uk",
        search_postcode="BD1 1HX",
        search_radius=32186,
        has_detail_api=False,
        value_wrapped=True,
    ),
    "www.sheffielddirectory.org.uk": PcgDeployment(
        domain="www.sheffielddirectory.org.uk",
        lad25cd="E08000019",
        base_url="https://www.sheffielddirectory.org.uk",
        search_postcode="S1 2HH",
        search_radius=32186,
        has_detail_api=False,
        value_wrapped=False,
    ),
}

_USER_AGENT = "BSIL-DataPipeline/1.0 (research; best-start-in-life)"
_REQUEST_TIMEOUT = 30
_rate_limiter = DomainRateLimiter(default_interval=1.0)

# Childcare-related search terms to union across
_SEARCH_TERMS = [
    "childminder",
    "nursery",
    "childcare",
    "pre-school",
    "after school club",
]

_PAGE_SIZE = 100


class PcgScraper(BaseScraper):
    @property
    def platform_key(self) -> str:
        return "pcg"

    def scrape_la(
        self,
        lad25cd: str,
        fis_url: str,
        existing_provider_ids: set[str],
        logger: Logger,
    ) -> Iterator[ProviderResult]:
        """Scrape childcare providers from a PCG directory site."""
        deployment = _get_deployment(fis_url)
        if deployment is None:
            logger.warning(f"No PCG deployment config for {fis_url} ({lad25cd})")
            yield ProviderResult(
                lad25cd=lad25cd,
                provider_id="__no_deployment_config__",
                scrape_status="unsupported_platform",
                source_url=fis_url,
            )
            return

        session = requests.Session()
        session.headers.update({"User-Agent": _USER_AGENT})

        # Step 1: Search with multiple terms and collect all unique provider IDs
        all_items: dict[str, dict] = {}  # id → list item dict
        for term in _SEARCH_TERMS:
            items = _search_all_pages(session, deployment, term, logger)
            new_count = 0
            for item in items:
                item_id = _extract_id(item)
                if item_id and item_id not in all_items:
                    all_items[item_id] = item
                    new_count += 1
            logger.info(
                f"PCG {deployment.domain}: term '{term}' → "
                f"{len(items)} results, {new_count} new (total: {len(all_items)})"
            )

        logger.info(f"PCG {deployment.domain}: {len(all_items)} unique providers found")

        # Step 2: Filter out existing providers
        new_ids = {pid for pid in all_items if pid not in existing_provider_ids}
        logger.info(
            f"PCG {deployment.domain}: {len(new_ids)} new providers to process "
            f"({len(existing_provider_ids)} already exist)"
        )

        # Step 3: For each new provider, fetch detail (if available) or use list data
        yielded = 0
        for pid in sorted(new_ids):
            list_item = all_items[pid]

            if deployment.has_detail_api:
                result = _fetch_detail(
                    session, deployment, lad25cd, pid, list_item, logger
                )
            else:
                result = _parse_list_item(deployment, lad25cd, pid, list_item)

            yield result
            yielded += 1

            if yielded % 50 == 0:
                logger.info(
                    f"PCG {deployment.domain}: processed {yielded}/{len(new_ids)} providers"
                )

        logger.info(
            f"PCG {deployment.domain}: yielded {yielded} providers for {lad25cd}"
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_deployment(fis_url: str) -> PcgDeployment | None:
    """Look up the deployment config for a given FIS URL."""
    parsed = urllib.parse.urlparse(fis_url.lower())
    domain = parsed.netloc

    if domain in DEPLOYMENTS:
        return DEPLOYMENTS[domain]

    for key, dep in DEPLOYMENTS.items():
        if key in domain or domain in key:
            return dep

    return None


def _extract_id(item: dict) -> str | None:
    """Extract the provider/event ID from a list result item."""
    # ID can be in 'id', 'eventId', or 'Id'
    for key in ("id", "eventId", "Id"):
        val = item.get(key)
        if val is not None:
            return str(val)
    return None


def _build_search_params(deployment: PcgDeployment, term: str, page_number: int) -> str:
    """Build the JSON searchParams query string."""
    params = {
        "searchText": term,
        "pageNumber": page_number,
        "pageSize": _PAGE_SIZE,
        "sortOption": "Rank;asc",
        "categories": [],
        "postcode": deployment.search_postcode,
        "distance": str(deployment.search_radius),
    }
    return json.dumps(params, separators=(",", ":"))


def _search_all_pages(
    session: requests.Session,
    deployment: PcgDeployment,
    term: str,
    logger: Logger,
) -> list[dict]:
    """Paginate through the search API for a single term, returning all items."""
    all_items: list[dict] = []
    page = 1

    while True:
        search_params = _build_search_params(deployment, term, page)
        url = (
            f"{deployment.base_url}"
            f"/api/s4s-advanced-search/directory-search/get-list"
            f"?searchParams={urllib.parse.quote(search_params)}"
        )

        resp = fetch(session, url, timeout=_REQUEST_TIMEOUT, rate_limiter=_rate_limiter)

        try:
            data = resp.json()
        except Exception:
            logger.warning(
                f"PCG {deployment.domain}: invalid JSON for '{term}' page {page}"
            )
            break

        # Bradford wraps response in {"value": {...}, "success": true}
        if deployment.value_wrapped and "value" in data:
            data = data["value"]

        # Extract items list and pagination info
        items = data.get("pageItems") or []

        all_items.extend(items)

        # Check if there are more pages
        total_pages = data.get("totalPages", 1)
        if page >= total_pages or not items:
            break

        page += 1

    return all_items


def _fetch_detail(
    session: requests.Session,
    deployment: PcgDeployment,
    lad25cd: str,
    provider_id: str,
    list_item: dict,
    logger: Logger,
) -> ProviderResult:
    """Fetch the detail API for a provider and build a ProviderResult."""
    detail_url = (
        f"{deployment.base_url}"
        f"/api/s4s-advanced-search/directory-search/get-event/{provider_id}"
    )

    resp = fetch(
        session, detail_url, timeout=_REQUEST_TIMEOUT, rate_limiter=_rate_limiter
    )
    detail = resp.json()

    # Bradford wraps detail too
    if deployment.value_wrapped and "value" in detail:
        detail = detail["value"]

    # Extract structured fields from detail response
    name = clean_text(detail.get("name") or list_item.get("name"))
    postcode = clean_text(detail.get("postcode"))
    phone = clean_text(detail.get("phone"))
    email = clean_text(detail.get("email"))
    urn = clean_text(detail.get("urn"))

    # Address is a single comma-separated string, parse into parts
    address_raw = clean_text(detail.get("address"))
    addr = parse_address_parts(address_raw) if address_raw else {}
    address_line1 = addr.get("address_line1")
    address_line2 = addr.get("address_line2")
    address_line3 = addr.get("address_line3")
    town = addr.get("town")

    # Coordinates
    lat = detail.get("latitude")
    lon = detail.get("longitude")

    has_name = bool(name)
    has_postcode = bool(postcode)
    has_coords = lat is not None and lon is not None

    if has_name and (has_postcode or has_coords):
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
        provider_address_line2=address_line2,
        provider_address_line3=address_line3,
        provider_town=town,
        provider_postcode=postcode,
        provider_urn=urn,
        provider_phone=phone,
        provider_email=email,
        provider_latitude=float(lat) if lat is not None else None,
        provider_longitude=float(lon) if lon is not None else None,
        source_url=detail_url,
        raw_json=json.dumps(detail),
        scrape_status=status,
    )


def _parse_list_item(
    deployment: PcgDeployment,
    lad25cd: str,
    provider_id: str,
    item: dict,
) -> ProviderResult:
    """Build a ProviderResult from list-only data (no detail API).

    List items typically have name/phone/email but no address → "partial".
    """
    name = clean_text(item.get("name"))
    phone = clean_text(item.get("phone"))
    email = clean_text(item.get("email"))

    # Some list items may include coordinates
    lat = item.get("latitude")
    lon = item.get("longitude")

    has_name = bool(name)
    has_coords = lat is not None and lon is not None
    if has_name and has_coords:
        status = "success"
    elif has_name:
        status = "partial"
    else:
        status = "error"

    return ProviderResult(
        lad25cd=lad25cd,
        provider_id=provider_id,
        provider_name=name,
        provider_phone=phone,
        provider_email=email,
        provider_latitude=float(lat) if lat is not None else None,
        provider_longitude=float(lon) if lon is not None else None,
        source_url=f"{deployment.base_url}/services/{provider_id}",
        raw_json=json.dumps(item),
        scrape_status=status,
    )
