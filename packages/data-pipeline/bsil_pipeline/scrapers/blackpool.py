"""Blackpool FYI Directory scraper (Contensis CMS).

Covers 1 LA: Blackpool (E06000009).

The site at fyidirectory.co.uk is a React SPA backed by a Contensis CMS
with a public REST Delivery API. Childcare entries are fetched via a single
POST to the search endpoint with an ``ecd: true`` filter. All ~84 providers
fit within one page (pageSize=100).

No Ofsted URN is available in the CMS data.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Iterator

import requests

from bsil_pipeline.scrapers.base import BaseScraper, ProviderResult, clean_text
from bsil_pipeline.scrapers.http import fetch
from bsil_pipeline.scrapers.rate_limiter import DomainRateLimiter

if TYPE_CHECKING:
    from logging import Logger

_USER_AGENT = "BSIL-DataPipeline/1.0 (research; best-start-in-life)"
_REQUEST_TIMEOUT = 30
_rate_limiter = DomainRateLimiter(default_interval=1.0)

_API_URL = (
    "https://api-blackpool.cloud.contensis.com/api/delivery/projects/fyi/entries/search"
)
_ACCESS_TOKEN = "Jfnb6XnfR2I6keXe5LspZkkca5RcMjK5lmLkz7v2nevr8xR6"  # nosec B105  # pragma: allowlist secret
_PAGE_SIZE = 100


class BlackpoolScraper(BaseScraper):
    @property
    def platform_key(self) -> str:
        return "blackpool"

    def scrape_la(
        self,
        lad25cd: str,
        fis_url: str,
        existing_provider_ids: set[str],
        logger: Logger,
    ) -> Iterator[ProviderResult]:
        """Scrape Blackpool providers from the Contensis Delivery API."""
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": _USER_AGENT,
                "accessToken": _ACCESS_TOKEN,
                "Content-Type": "application/json",
            }
        )

        body = {
            "pageSize": _PAGE_SIZE,
            "pageIndex": 0,
            "where": [
                {"field": "sys.contentTypeId", "equalTo": "directoryEntry"},
                {"field": "sys.versionStatus", "equalTo": "published"},
                {"field": "ecd", "equalTo": True},
            ],
            "orderBy": [{"asc": "entryTitle"}],
        }

        all_items: list[dict] = []
        page_index = 0

        while True:
            body["pageIndex"] = page_index

            resp = fetch(
                session,
                _API_URL,
                timeout=_REQUEST_TIMEOUT,
                rate_limiter=_rate_limiter,
                method="POST",
                json=body,
            )

            data = resp.json()
            items = data.get("items", [])
            all_items.extend(items)

            page_count = data.get("pageCount", 1)
            page_index += 1
            if page_index >= page_count:
                break

        logger.info(
            f"Blackpool: fetched {len(all_items)} entries "
            f"({page_count} page(s)) from Contensis API"
        )

        yielded = 0
        for item in all_items:
            provider_id = item.get("sys", {}).get("id", "")
            if not provider_id:
                continue
            if provider_id in existing_provider_ids:
                continue

            yield _parse_entry(lad25cd, item, fis_url)
            yielded += 1

        logger.info(f"Blackpool: yielded {yielded} providers for {lad25cd}")


def _parse_entry(lad25cd: str, entry: dict, source_url: str) -> ProviderResult:
    """Convert a Contensis directoryEntry to a ProviderResult."""
    provider_id = entry.get("sys", {}).get("id", "")
    name = clean_text(entry.get("entryTitle"))

    address = entry.get("address") or {}
    line1 = clean_text(address.get("addressLine1"))
    line2 = clean_text(address.get("addressLine2"))
    city = clean_text(address.get("city"))
    postcode = clean_text(address.get("postcode"))

    contact = entry.get("contact") or {}
    phones = contact.get("telephone") or []
    phone = clean_text(phones[0]) if phones else None
    emails = contact.get("email") or []
    email = clean_text(emails[0]) if emails else None

    location = entry.get("location") or {}
    lat = location.get("lat")
    lon = location.get("lon")

    has_name = bool(name)
    has_postcode = bool(postcode)

    if has_name and has_postcode:
        status = "success"
    elif has_name:
        status = "partial"
    else:
        status = "error"

    return ProviderResult(
        lad25cd=lad25cd,
        provider_id=provider_id,
        provider_name=name,
        provider_address_line1=line1,
        provider_address_line2=line2,
        provider_town=city,
        provider_postcode=postcode,
        provider_phone=phone,
        provider_email=email,
        provider_latitude=float(lat) if lat is not None else None,
        provider_longitude=float(lon) if lon is not None else None,
        source_url=source_url,
        raw_json=json.dumps(entry),
        scrape_status=status,
    )
