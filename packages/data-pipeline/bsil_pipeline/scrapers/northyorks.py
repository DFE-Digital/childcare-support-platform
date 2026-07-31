"""North Yorkshire childcare providers scraper (ArcGIS Feature Service).

Covers 1 LA: North Yorkshire (E06000065).

The council uses an ArcGIS Experience Builder map backed by a public Feature
Service with 14 layers (one per provider type). All layers are queried with
``where=1=1&outFields=*&outSR=4326&f=json``. The largest layer has ~129
records and ``maxRecordCount`` is 2000, so no pagination is needed.

No Ofsted URN field is available, but Ofsted Judgement is present.
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

_BASE_URL = (
    "https://utility.arcgis.com/usrsvcs/servers"
    "/aa1120ac4aaf4ce696b2ab0efd672f03/rest/services"
    "/Education/Childcare_Providers/FeatureServer"
)
_LAYER_IDS = list(range(14))  # layers 0–13


class NorthYorksScraper(BaseScraper):
    @property
    def platform_key(self) -> str:
        return "northyorks"

    def scrape_la(
        self,
        lad25cd: str,
        fis_url: str,
        existing_provider_ids: set[str],
        logger: Logger,
    ) -> Iterator[ProviderResult]:
        """Scrape North Yorkshire providers from ArcGIS Feature Service."""
        session = requests.Session()
        session.headers.update({"User-Agent": _USER_AGENT})

        total = 0
        yielded = 0

        for layer_id in _LAYER_IDS:
            query_url = f"{_BASE_URL}/{layer_id}/query"
            params = {
                "where": "1=1",
                "outFields": "*",
                "outSR": "4326",
                "f": "json",
            }

            resp = fetch(
                session,
                query_url,
                params=params,
                timeout=_REQUEST_TIMEOUT,
                rate_limiter=_rate_limiter,
            )

            data = resp.json()

            if "error" in data:
                logger.error(
                    f"NorthYorks: layer {layer_id} returned error: {data['error']}"
                )
                continue

            features = data.get("features", [])
            total += len(features)

            for feature in features:
                attrs = feature.get("attributes", {})
                geometry = feature.get("geometry", {})
                object_id = attrs.get("OBJECTID", "")
                provider_id = f"{layer_id}_{object_id}"

                if provider_id in existing_provider_ids:
                    continue

                yield _parse_feature(lad25cd, layer_id, attrs, geometry, fis_url)
                yielded += 1

        logger.info(
            f"NorthYorks: fetched {total} features across "
            f"{len(_LAYER_IDS)} layers, yielded {yielded} providers"
        )


def _parse_feature(
    lad25cd: str,
    layer_id: int,
    attrs: dict,
    geometry: dict,
    source_url: str,
) -> ProviderResult:
    """Convert an ArcGIS feature to a ProviderResult."""
    object_id = attrs.get("OBJECTID", "")
    provider_id = f"{layer_id}_{object_id}"

    name = clean_text(attrs.get("Name"))

    # Use the dedicated Postcode field; fall back to parsing Full_Address
    postcode = clean_text(attrs.get("Postcode"))
    full_address = attrs.get("Full_Address") or ""

    addr = parse_address_parts(full_address)
    if not postcode:
        postcode = addr.get("postcode")

    # Strip mailto: prefix from email
    raw_email = attrs.get("Provider_Email") or ""
    email = clean_text(raw_email.removeprefix("mailto:").removeprefix("MAILTO:"))

    phone = clean_text(attrs.get("Provider_Telephone"))

    lat = geometry.get("y")
    lon = geometry.get("x")

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
        provider_address_line1=addr.get("address_line1"),
        provider_address_line2=addr.get("address_line2"),
        provider_address_line3=addr.get("address_line3"),
        provider_town=addr.get("town"),
        provider_postcode=postcode,
        provider_phone=phone,
        provider_email=email,
        provider_latitude=float(lat) if lat is not None else None,
        provider_longitude=float(lon) if lon is not None else None,
        source_url=source_url,
        raw_json=json.dumps(attrs),
        scrape_status=status,
    )
