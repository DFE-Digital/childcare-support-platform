"""Somerset childcare directory scraper.

Covers 1 LA: Somerset (E06000066).

The site at somerset.gov.uk uses a WordPress REST API with a custom
`childcare` post type and ACF (Advanced Custom Fields) for provider data.

    GET /wp-json/wp/v2/childcare?per_page=100&page={N}

Pagination via X-WP-Total / X-WP-TotalPages response headers.
~393 providers / 100 per page = 4 requests total.
"""

from __future__ import annotations

import json
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

_USER_AGENT = "BSIL-DataPipeline/1.0 (research; best-start-in-life)"
_REQUEST_TIMEOUT = 30
_rate_limiter = DomainRateLimiter(default_interval=1.0)

_API_URL = "https://www.somerset.gov.uk/wp-json/wp/v2/childcare"
_PER_PAGE = 100


class SomersetScraper(BaseScraper):
    @property
    def platform_key(self) -> str:
        return "somerset"

    def scrape_la(
        self,
        lad25cd: str,
        fis_url: str,
        existing_provider_ids: set[str],
        logger: Logger,
    ) -> Iterator[ProviderResult]:
        """Scrape Somerset childcare providers from WP REST API."""
        session = requests.Session()
        session.headers.update({"User-Agent": _USER_AGENT})

        page = 1
        total_pages = None
        yielded = 0

        while True:
            url = f"{_API_URL}?per_page={_PER_PAGE}&page={page}"

            resp = fetch(
                session, url, timeout=_REQUEST_TIMEOUT, rate_limiter=_rate_limiter
            )

            if total_pages is None:
                total_pages = int(resp.headers.get("X-WP-TotalPages", "1"))
                total = resp.headers.get("X-WP-Total", "?")
                logger.info(f"Somerset: {total} providers across {total_pages} pages")

            try:
                providers = resp.json()
            except Exception as e:
                logger.error(f"Somerset: JSON parse error on page {page}: {e}")
                break

            for provider in providers:
                provider_id = str(provider.get("id", ""))
                if not provider_id:
                    continue
                if provider_id in existing_provider_ids:
                    continue

                result = _parse_provider(lad25cd, provider, fis_url)
                yield result
                yielded += 1

            page += 1
            if page > total_pages:
                break

        logger.info(f"Somerset: yielded {yielded} providers for {lad25cd}")


def _parse_provider(lad25cd: str, provider: dict, source_url: str) -> ProviderResult:
    """Convert a WP REST API childcare post to a ProviderResult."""
    provider_id = str(provider.get("id", ""))

    # Title is in rendered form (may contain HTML entities)
    title_obj = provider.get("title", {})
    name = (
        clean_text(title_obj.get("rendered")) if isinstance(title_obj, dict) else None
    )

    acf = provider.get("acf", {}) or {}

    # Address from ACF Google Map field
    phys_addr = acf.get("physical_address", {}) or {}
    address_text = phys_addr.get("address", "")
    lat = phys_addr.get("lat")
    lng = phys_addr.get("lng")

    addr_parts = parse_address_parts(address_text) if address_text else {}

    phone = clean_text(str(acf.get("phone_number", ""))) or None
    email = clean_text(str(acf.get("service_email", ""))) or None

    # Ofsted URN from nested accreditations field
    accreditations = acf.get("service_accreditations", {}) or {}
    urn = clean_text(str(accreditations.get("ofsted_urn", ""))) or None

    has_name = bool(name)
    has_postcode = bool(addr_parts.get("postcode"))

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
        provider_address_line1=addr_parts.get("address_line1"),
        provider_address_line2=addr_parts.get("address_line2"),
        provider_address_line3=addr_parts.get("address_line3"),
        provider_town=addr_parts.get("town"),
        provider_postcode=addr_parts.get("postcode"),
        provider_urn=urn,
        provider_phone=phone,
        provider_email=email,
        provider_latitude=float(lat) if lat is not None else None,
        provider_longitude=float(lng) if lng is not None else None,
        source_url=source_url,
        raw_json=json.dumps(provider),
        scrape_status=status,
    )
