"""LocalGov Drupal Directories scraper (JSON:API).

Covers LAs using the standard localgov_directories Drupal module with
public JSON:API endpoints:
- www.dumfriesandgalloway.gov.uk (Dumfries and Galloway, S12000006)

API pattern:
  GET /jsonapi/node/{content_type}
    ?filter[localgov_directory_channels.id]={channel_uuid}
    &include=localgov_location
    &page[limit]=50

Two content types per deployment:
- localgov_directories_venue — has structured address + lat/lon via geo_entity
- localgov_directories_page  — inline address (often sparse), no coordinates
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Iterator
from urllib.parse import urlparse

import requests

from bsil_pipeline.scrapers.base import (
    BaseScraper,
    ProviderResult,
    clean_text,
)
from bsil_pipeline.scrapers.http import fetch
from bsil_pipeline.scrapers.rate_limiter import DomainRateLimiter

if TYPE_CHECKING:
    from logging import Logger


# ---------------------------------------------------------------------------
# Per-deployment configuration
# ---------------------------------------------------------------------------


@dataclass
class LocalGovDrupalDeployment:
    """Configuration for a single LocalGov Drupal directory deployment."""

    domain: str
    lad25cd: str
    base_url: str
    channel_uuid: str
    content_types: list[str] = field(
        default_factory=lambda: [
            "localgov_directories_venue",
            "localgov_directories_page",
        ]
    )


DEPLOYMENTS: dict[str, LocalGovDrupalDeployment] = {
    "www.dumfriesandgalloway.gov.uk": LocalGovDrupalDeployment(
        domain="www.dumfriesandgalloway.gov.uk",
        lad25cd="S12000006",
        base_url="https://www.dumfriesandgalloway.gov.uk",
        channel_uuid="61cca383-a3e8-4aa8-b477-1d0073f37439",
        content_types=[
            "localgov_directories_venue",
            "localgov_directories_page",
        ],
    ),
}

_USER_AGENT = "BSIL-DataPipeline/1.0 (research; best-start-in-life)"
_REQUEST_TIMEOUT = 30
_PAGE_LIMIT = 50
_rate_limiter = DomainRateLimiter(default_interval=1.0)

# Regex to parse WKT POINT(lon lat) from geo_entity location field
_WKT_POINT_RE = re.compile(r"POINT\s*\(\s*([-\d.]+)\s+([-\d.]+)\s*\)")


class LocalGovDrupalScraper(BaseScraper):
    @property
    def platform_key(self) -> str:
        return "localgov_drupal"

    def scrape_la(
        self,
        lad25cd: str,
        fis_url: str,
        existing_provider_ids: set[str],
        logger: Logger,
    ) -> Iterator[ProviderResult]:
        deployment = _get_deployment(fis_url)
        if deployment is None:
            logger.warning(
                f"No LocalGov Drupal deployment config for {fis_url} ({lad25cd})"
            )
            yield ProviderResult(
                lad25cd=lad25cd,
                provider_id="__no_deployment_config__",
                scrape_status="unsupported_platform",
                source_url=fis_url,
            )
            return

        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": _USER_AGENT,
                "Accept": "application/vnd.api+json",
            }
        )

        total_yielded = 0

        for content_type in deployment.content_types:
            logger.info(f"LocalGov Drupal {deployment.domain}: fetching {content_type}")

            for result in _fetch_content_type(
                session,
                deployment,
                lad25cd,
                content_type,
                existing_provider_ids,
                logger,
            ):
                yield result
                total_yielded += 1

        logger.info(
            f"LocalGov Drupal {deployment.domain}: yielded {total_yielded} providers for {lad25cd}"
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_deployment(fis_url: str) -> LocalGovDrupalDeployment | None:
    parsed = urlparse(fis_url.lower())
    domain = parsed.netloc

    if domain in DEPLOYMENTS:
        return DEPLOYMENTS[domain]

    for key, dep in DEPLOYMENTS.items():
        if key in domain or domain in key:
            return dep

    return None


def _fetch_content_type(
    session: requests.Session,
    deployment: LocalGovDrupalDeployment,
    lad25cd: str,
    content_type: str,
    existing_provider_ids: set[str],
    logger: Logger,
) -> Iterator[ProviderResult]:
    """Paginate through a single JSON:API content type and yield results."""
    # Only venues have a localgov_location relationship to include
    include_param = "&include=localgov_location" if "venue" in content_type else ""
    url = (
        f"{deployment.base_url}/jsonapi/node/{content_type}"
        f"?filter[localgov_directory_channels.id]={deployment.channel_uuid}"
        f"{include_param}"
        f"&page[limit]={_PAGE_LIMIT}"
    )

    page = 0
    while url:
        resp = fetch(session, url, timeout=_REQUEST_TIMEOUT, rate_limiter=_rate_limiter)

        try:
            payload = resp.json()
        except Exception:
            logger.warning(
                f"LocalGov Drupal {deployment.domain}: "
                f"invalid JSON for {content_type} page {page}"
            )
            break

        data = payload.get("data", [])
        included = payload.get("included", [])

        # Build lookup of included resources by (type, id)
        included_map = {
            (inc["type"], inc["id"]): inc
            for inc in included
            if "type" in inc and "id" in inc
        }

        for node in data:
            node_id = node.get("id")
            if not node_id:
                continue
            if node_id in existing_provider_ids:
                continue

            result = _parse_node(node, content_type, included_map, deployment, lad25cd)
            yield result

        logger.info(
            f"LocalGov Drupal {deployment.domain}: "
            f"{content_type} page {page} -> {len(data)} nodes"
        )

        # Follow next page link
        next_link = payload.get("links", {}).get("next")
        if next_link:
            url = next_link.get("href") if isinstance(next_link, dict) else next_link
        else:
            url = None

        page += 1


def _parse_node(
    node: dict,
    content_type: str,
    included_map: dict[tuple[str, str], dict],
    deployment: LocalGovDrupalDeployment,
    lad25cd: str,
) -> ProviderResult:
    """Parse a single JSON:API node into a ProviderResult."""
    node_id = node["id"]
    attrs = node.get("attributes", {})
    rels = node.get("relationships", {})

    name = clean_text(attrs.get("title"))

    phone = None
    email = None

    # Phone — localgov_directory_phone is a list of {value: ...}
    phone_list = attrs.get("localgov_directory_phone") or []
    if phone_list and isinstance(phone_list, list):
        phone = (
            clean_text(phone_list[0].get("value"))
            if isinstance(phone_list[0], dict)
            else clean_text(str(phone_list[0]))
        )

    # Email — localgov_directory_email is a list of {value: ...}
    email_list = attrs.get("localgov_directory_email") or []
    if email_list and isinstance(email_list, list):
        email = (
            clean_text(email_list[0].get("value"))
            if isinstance(email_list[0], dict)
            else clean_text(str(email_list[0]))
        )

    address_line1 = None
    town = None
    postcode = None
    lat = None
    lon = None

    if content_type == "localgov_directories_venue":
        # Venue: address + coords from geo_entity via localgov_location relationship
        address_line1, town, postcode, lat, lon = _parse_venue_location(
            rels, included_map
        )
    else:
        # Page: inline address field
        address_line1, town, postcode = _parse_page_address(attrs)

    # Determine status
    has_name = bool(name)
    has_postcode = bool(postcode)

    if has_name and has_postcode:
        status = "success"
    elif has_name:
        status = "partial"
    else:
        status = "error"

    source_url = (
        (
            f"{deployment.base_url}"
            f"{node.get('attributes', {}).get('path', {}).get('alias', '')}"
        )
        if attrs.get("path", {}).get("alias")
        else f"{deployment.base_url}/node/{node_id}"
    )

    return ProviderResult(
        lad25cd=lad25cd,
        provider_id=node_id,
        provider_name=name,
        provider_address_line1=address_line1,
        provider_town=town,
        provider_postcode=postcode,
        provider_phone=phone,
        provider_email=email,
        provider_latitude=lat,
        provider_longitude=lon,
        source_url=source_url,
        raw_json=None,  # Skip storing full JSON to save space
        scrape_status=status,
    )


def _parse_venue_location(
    rels: dict,
    included_map: dict[tuple[str, str], dict],
) -> tuple[str | None, str | None, str | None, float | None, float | None]:
    """Extract address and coords from a venue's localgov_location relationship."""
    loc_rel = rels.get("localgov_location", {}).get("data")
    if not loc_rel:
        return None, None, None, None, None

    # loc_rel can be a single object or list
    if isinstance(loc_rel, list):
        loc_rel = loc_rel[0] if loc_rel else None
    if not loc_rel:
        return None, None, None, None, None

    loc_type = loc_rel.get("type", "")
    loc_id = loc_rel.get("id", "")
    geo_entity = included_map.get((loc_type, loc_id))
    if not geo_entity:
        return None, None, None, None, None

    geo_attrs = geo_entity.get("attributes", {})

    # Address from postal_address
    postal = geo_attrs.get("postal_address") or {}
    address_line1 = clean_text(postal.get("address_line1"))
    town = clean_text(postal.get("locality"))
    postcode = clean_text(postal.get("postal_code"))

    # Coords from location WKT POINT(lon lat)
    lat = None
    lon = None
    location_wkt = geo_attrs.get("location", {})
    if isinstance(location_wkt, dict):
        location_wkt = location_wkt.get("value", "")
    if isinstance(location_wkt, str):
        match = _WKT_POINT_RE.search(location_wkt)
        if match:
            lon = float(match.group(1))
            lat = float(match.group(2))

    return address_line1, town, postcode, lat, lon


def _parse_page_address(
    attrs: dict,
) -> tuple[str | None, str | None, str | None]:
    """Extract address from a page's inline localgov_directory_address field."""
    addr = attrs.get("localgov_directory_address") or {}
    if not isinstance(addr, dict):
        return None, None, None

    address_line1 = clean_text(addr.get("address_line1"))
    town = clean_text(addr.get("locality"))
    postcode = clean_text(addr.get("postal_code"))

    return address_line1, town, postcode
