"""Hartlepool Family Hubs scraper.

Covers 1 LA: Hartlepool (E06000001).

The site at search.hartlepoolfamilyhubs.co.uk is a Laravel/Vite app that
embeds all provider data as inline JSON in a JavaScript variable:

    var providersToShow = [ { id: 1, name: "...", ... }, ... ];

This makes scraping trivial — HTTP GET the page and extract the JSON.
Each provider object contains name, location (address), postcode, phone,
email, Ofsted reference, lat/lon, and service type.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Iterator

import requests

from bsil_pipeline.scrapers.base import BaseScraper, ProviderResult
from bsil_pipeline.scrapers.http import fetch
from bsil_pipeline.scrapers.rate_limiter import DomainRateLimiter

if TYPE_CHECKING:
    from logging import Logger

_USER_AGENT = "BSIL-DataPipeline/1.0 (research; best-start-in-life)"
_REQUEST_TIMEOUT = 30
_rate_limiter = DomainRateLimiter(default_interval=1.0)

_PROVIDERS_RE = re.compile(r"var\s+providersToShow\s*=\s*(\[.*?\])\s*;", re.DOTALL)


class HartlepoolScraper(BaseScraper):
    @property
    def platform_key(self) -> str:
        return "hartlepool"

    def scrape_la(
        self,
        lad25cd: str,
        fis_url: str,
        existing_provider_ids: set[str],
        logger: Logger,
    ) -> Iterator[ProviderResult]:
        """Scrape Hartlepool providers from inline JSON."""
        session = requests.Session()
        session.headers.update({"User-Agent": _USER_AGENT})

        resp = fetch(
            session, fis_url, timeout=_REQUEST_TIMEOUT, rate_limiter=_rate_limiter
        )

        html = resp.text
        match = _PROVIDERS_RE.search(html)
        if not match:
            logger.error("Hartlepool: could not find providersToShow JSON")
            yield ProviderResult(
                lad25cd=lad25cd,
                provider_id="__no_json__",
                scrape_status="error",
                source_url=fis_url,
            )
            return

        try:
            providers = json.loads(match.group(1))
        except json.JSONDecodeError as e:
            logger.error(f"Hartlepool: JSON parse error: {e}")
            yield ProviderResult(
                lad25cd=lad25cd,
                provider_id="__json_parse_error__",
                scrape_status="error",
                source_url=fis_url,
                raw_json=match.group(1)[:2000],
            )
            return

        logger.info(f"Hartlepool: found {len(providers)} providers in inline JSON")

        yielded = 0
        for provider in providers:
            provider_id = str(provider.get("id", ""))
            if not provider_id:
                continue
            if provider_id in existing_provider_ids:
                continue

            result = _parse_provider(lad25cd, provider, fis_url)
            yield result
            yielded += 1

        logger.info(f"Hartlepool: yielded {yielded} providers for {lad25cd}")


def _parse_provider(lad25cd: str, provider: dict, source_url: str) -> ProviderResult:
    """Convert a Hartlepool JSON provider object to a ProviderResult."""
    provider_id = str(provider.get("id", ""))
    name = provider.get("name")
    postcode = provider.get("postcode")
    address = provider.get("location")
    phone = provider.get("phone_number")
    email = provider.get("email_address")
    ofsted_ref = provider.get("ofsted_reference")
    lat = provider.get("latitude")
    lon = provider.get("longitude")

    has_name = bool(name)
    has_postcode = bool(postcode)

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
        provider_address_line1=address,
        provider_postcode=postcode,
        provider_urn=ofsted_ref,
        provider_phone=phone,
        provider_email=email,
        provider_latitude=float(lat) if lat is not None else None,
        provider_longitude=float(lon) if lon is not None else None,
        source_url=source_url,
        raw_json=json.dumps(provider),
        scrape_status=status,
    )
