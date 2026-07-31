"""Essex FIS JSON API scraper.

Covers 12 Essex district councils that all share the Essex CC Family
Information Service at secureapps.essex.gov.uk/fis. The FIS exposes a
JSON REST API — no HTML scraping needed.

API endpoint: GET https://secureapps.essex.gov.uk/fis/search/get/
Required header: X-Requested-With: XMLHttpRequest

One scrape (5 overlapping search circles) covers the entire county;
providers are deduplicated by Id and cached for all 12 LAs.
"""

from __future__ import annotations

import json
import time
from typing import TYPE_CHECKING, Iterator

import requests

from bsil_pipeline.scrapers.base import BaseScraper, ProviderResult, clean_text
from bsil_pipeline.scrapers.http import fetch
from bsil_pipeline.scrapers.rate_limiter import DomainRateLimiter
from bsil_pipeline.utils.postcode_lookup import postcode_to_lad

if TYPE_CHECKING:
    from logging import Logger

_API_URL = "https://secureapps.essex.gov.uk/fis/search/get/"
_SOURCE_URL = "https://secureapps.essex.gov.uk/fis"
_USER_AGENT = "BSIL-DataPipeline/1.0 (research; best-start-in-life)"
_REQUEST_TIMEOUT = 60

_CATEGORY_IDS = (
    "ccr-asc,ccr-btg,ccr-brk,ccr-chc,ccr-chm,ccr-cre,"
    "ccr-dyn,ccr-hol,ccr-mns,ccr-nis,ccr-pre,ccr-psn,ccr-cma,ccr-ids"
)

# 5 search points covering the full county with radius 10 miles each
_SEARCH_POINTS: list[tuple[float, float, str]] = [
    (51.734, 0.476, "Chelmsford"),
    (51.889, 0.904, "Colchester"),
    (51.540, 0.710, "Southend"),
    (51.773, 0.102, "Harlow"),
    (51.878, 0.550, "Braintree"),
]
_SEARCH_RADIUS = 10  # miles

_rate_limiter = DomainRateLimiter(default_interval=1.0)

# Module-level cache: scrape once for all 12 Essex districts
_essex_cache: list[dict] | None = None


class EssexScraper(BaseScraper):
    @property
    def platform_key(self) -> str:
        return "essex"

    def scrape_la(
        self,
        lad25cd: str,
        fis_url: str,
        existing_provider_ids: set[str],
        logger: Logger,
    ) -> Iterator[ProviderResult]:
        global _essex_cache

        if _essex_cache is None:
            logger.info("Essex FIS: scraping all providers (first LA call)")
            _essex_cache = _scrape_essex_providers(logger)
            logger.info(f"Cached {len(_essex_cache)} Essex providers")
        else:
            logger.info(
                f"Essex FIS: using cached results "
                f"({len(_essex_cache)} providers) for {lad25cd}"
            )

        yielded = 0
        skipped = 0
        for raw in _essex_cache:
            pid = raw["provider_id"]
            if pid in existing_provider_ids:
                continue
            # Assign provider to correct LA based on postcode
            resolved_lad = postcode_to_lad(raw.get("postcode"))
            if resolved_lad and resolved_lad != lad25cd:
                skipped += 1
                continue  # Provider belongs to a different Essex district
            yield ProviderResult(
                lad25cd=lad25cd,
                provider_id=pid,
                provider_name=raw.get("provider_name"),
                provider_address_line1=raw.get("address_line1"),
                provider_address_line2=raw.get("address_line2"),
                provider_town=raw.get("town"),
                provider_postcode=raw.get("postcode"),
                provider_urn=raw.get("urn"),
                source_url=raw.get("source_url"),
                raw_json=raw.get("raw_json"),
                scrape_status=raw.get("scrape_status", "error"),
            )
            yielded += 1

        logger.info(
            f"Essex FIS: yielded {yielded} providers for {lad25cd} "
            f"(skipped {skipped} belonging to other districts)"
        )


def _scrape_essex_providers(logger: Logger) -> list[dict]:
    """Scrape all childcare providers from the Essex FIS JSON API.

    Queries 5 overlapping search circles and deduplicates by provider Id.
    """
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": _USER_AGENT,
            "X-Requested-With": "XMLHttpRequest",
        }
    )

    seen_ids: set[str] = set()
    results: list[dict] = []

    for lat, lng, area_name in _SEARCH_POINTS:
        logger.info(f"Essex FIS: searching {area_name} ({lat}, {lng})")
        raw_items = _fetch_search_results(session, lat, lng, _SEARCH_RADIUS, logger)
        logger.info(f"  -> {len(raw_items)} results from {area_name}")

        for item in raw_items:
            provider_id = str(item.get("Id", ""))
            if not provider_id or provider_id in seen_ids:
                continue
            seen_ids.add(provider_id)

            fields = item.get("Fields", {})
            postcode = clean_text(fields.get("AddressPostcode"))
            urn = clean_text(fields.get("OfstedReference"))

            results.append(
                {
                    "provider_id": fields.get("ResourceIdentifier", provider_id),
                    "provider_name": clean_text(fields.get("ProviderName"))
                    or clean_text(item.get("Name")),
                    "address_line1": clean_text(
                        fields.get("AddressBuildingNumberOrName")
                    ),
                    "address_line2": clean_text(fields.get("AddressStreet")),
                    "town": clean_text(fields.get("AddressTown")),
                    "postcode": postcode,
                    "urn": urn if urn else None,
                    "source_url": _SOURCE_URL,
                    "raw_json": json.dumps(item),
                    "scrape_status": "success" if postcode else "partial",
                }
            )

    logger.info(
        f"Essex FIS: {len(results)} unique providers from {len(_SEARCH_POINTS)} search points"
    )
    return results


def _fetch_search_results(
    session: requests.Session,
    lat: float,
    lng: float,
    radius: int,
    logger: Logger,
) -> list[dict]:
    """Fetch a single search circle from the Essex FIS API."""
    params = {
        "lat": str(lat),
        "lng": str(lng),
        "radius": str(radius),
        "groupId": "2",
        "categoryId": _CATEGORY_IDS,
        "timestamp": str(int(time.time() * 1000)),
    }

    resp = fetch(
        session,
        _API_URL,
        params=params,
        timeout=_REQUEST_TIMEOUT,
        rate_limiter=_rate_limiter,
    )
    data = resp.json()
    if isinstance(data, list):
        return data
    logger.warning(f"Essex FIS: unexpected response type {type(data)}")
    return []
