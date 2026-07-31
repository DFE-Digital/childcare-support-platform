"""Devon FIS scraper — findchildcareindevon.co.uk.

Covers 8 Devon district councils (E07000040–E07000047) that all share the
Devon CC Family Information Service at findchildcareindevon.co.uk.

The site uses GET-based geographic search at /Provider with Postcode + Proximity
parameters. Without a valid postcode the search returns ALL ~1,171 providers
unfiltered, so we must supply real Devon postcodes for each search circle.

Results are capped at ~200 per request. We cover the county with overlapping
search circles using postcodes from each area, deduplicating by providerId.

Detail pages have provider name, phone, email but NO address/postcode.
Lat/lng coordinates are extracted from Google Maps marker JavaScript on the
listing pages. The pattern is:
    myLatLng = new google.maps.LatLng(lat, lng);
    marker{serviceId} = new google.maps.Marker({
        ...
        url: './Provider/DetailService?providerId=X&serviceId=Y'
    });
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Iterator
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup

from bsil_pipeline.scrapers.base import BaseScraper, ProviderResult, clean_text
from bsil_pipeline.scrapers.http import fetch
from bsil_pipeline.scrapers.rate_limiter import DomainRateLimiter
from bsil_pipeline.utils.postcode_lookup import coords_to_lad

if TYPE_CHECKING:
    from logging import Logger

_BASE_URL = "https://www.findchildcareindevon.co.uk"
_SEARCH_URL = f"{_BASE_URL}/Provider"
_USER_AGENT = "BSIL-DataPipeline/1.0 (research; best-start-in-life)"
_REQUEST_TIMEOUT = 60

# Generic Devon CC contact email — excluded from provider email extraction
_DEVON_CC_EMAIL = "eycs@devon.gov.uk"

# Search points covering Devon with real postcodes.
# Each tuple: (postcode, lat, lng, name, proximity_miles)
# Dense areas use "3" (3mi), rural areas use "5" or "10" (5/10mi).
# NOTE: EX14/EX15 postcodes cause 500 errors on the server — use
#       adjacent EX areas with larger radii to cover those gaps.
_SEARCH_POINTS: list[tuple[str, float, float, str, str]] = [
    # Exeter area (dense — 3mi circles)
    ("EX1 1EE", 50.7236, -3.5275, "Exeter centre", "3"),
    ("EX4 4PL", 50.7500, -3.5400, "Exeter north/St Davids", "3"),
    ("EX2 8BE", 50.7000, -3.5200, "Exeter south/Topsham Rd", "3"),
    ("EX1 3PB", 50.7236, -3.4500, "Exeter east/Pinhoe", "3"),
    ("EX5 4ES", 50.7800, -3.4400, "Clyst/Broadclyst", "5"),
    # Torbay area (Torbay UA — still on Devon FIS site)
    ("TQ1 4QR", 50.4700, -3.5200, "Torquay", "5"),
    ("TQ3 2NE", 50.4600, -3.5600, "Paignton", "5"),
    # North Devon (10mi for rural coverage, stays under 200 cap)
    ("EX31 1DX", 51.0821, -4.0584, "Barnstaple", "10"),
    ("EX36 3BU", 51.0000, -3.7800, "South Molton", "5"),
    ("EX34 9EQ", 51.2100, -4.1200, "Ilfracombe", "5"),
    # Mid Devon (10mi Crediton covers Cullompton gap; 198 results < 200 cap)
    ("EX17 3PG", 50.7900, -3.6600, "Crediton", "10"),
    ("EX16 6LT", 50.9000, -3.4900, "Tiverton", "5"),
    ("EX16 6RQ", 50.9100, -3.4800, "Tiverton NW", "5"),
    # East Devon (EX14/EX15 500 — use adjacent postcodes + wider radii)
    ("EX11 1QA", 50.7500, -3.2800, "Ottery St Mary", "5"),
    ("EX10 8ES", 50.6800, -3.2500, "Sidmouth", "5"),
    ("EX12 2AA", 50.7200, -3.0700, "Seaton", "5"),
    ("EX13 5AQ", 50.7800, -3.0000, "Axminster", "5"),
    ("EX8 2AZ", 50.6300, -3.4100, "Exmouth", "5"),
    # South Devon
    ("TQ12 1AA", 50.5472, -3.4968, "Newton Abbot", "5"),
    ("EX7 9QH", 50.5800, -3.4600, "Dawlish/Teignmouth", "5"),
    ("TQ9 5NP", 50.4300, -3.6900, "Totnes", "5"),
    ("TQ7 1EB", 50.2800, -3.7800, "Kingsbridge", "5"),
    ("PL21 0AE", 50.3900, -3.9400, "Ivybridge", "10"),
    ("PL7 1RF", 50.3900, -4.0500, "Plympton/Plymouth border", "5"),
    # West Devon / Torridge
    ("EX21 5AE", 50.8900, -4.0500, "Holsworthy", "5"),
    ("EX20 1EW", 50.7400, -4.0000, "Okehampton", "10"),
    ("EX39 2QQ", 51.0200, -4.2100, "Bideford", "5"),
]

_rate_limiter = DomainRateLimiter(default_interval=1.0)

# Module-level cache: scrape once, serve all 8 district LAs
_devon_cache: list[ProviderResult] | None = None

# Devon district LAD codes — used for coordinate-based LA assignment
_DEVON_DISTRICTS = {
    "E07000040",
    "E07000041",
    "E07000042",
    "E07000043",
    "E07000044",
    "E07000045",
    "E07000046",
    "E07000047",
}

# Cache: provider_id -> resolved LAD code (from coord lookup)
_devon_lad_cache: dict[str, str | None] = {}

# Regex to extract marker blocks from listing-page JavaScript.
# Pattern: myLatLng = new google.maps.LatLng(lat, lng); marker{serviceId} = ...
# url: './Provider/DetailService?providerId=X&serviceId=Y'
_MARKER_BLOCK_RE = re.compile(
    r"myLatLng\s*=\s*new\s+google\.maps\.LatLng\(\s*"
    r"(-?\d+\.?\d*)\s*,\s*(-?\d+\.?\d*)\s*\);\s*"
    r"marker(\d+)\s*=\s*new\s+google\.maps\.Marker\(\{.*?"
    r"url:\s*'([^']+)'",
    re.DOTALL,
)


class DevonScraper(BaseScraper):
    @property
    def platform_key(self) -> str:
        return "devon"

    def scrape_la(
        self,
        lad25cd: str,
        fis_url: str,
        existing_provider_ids: set[str],
        logger: Logger,
    ) -> Iterator[ProviderResult]:
        global _devon_cache

        global _devon_lad_cache

        if _devon_cache is None:
            logger.info("Devon FIS: scraping all providers (first LA call)")
            _devon_cache = _scrape_devon_providers(logger)
            logger.info(f"Cached {len(_devon_cache)} Devon providers")

            # Pre-resolve LAD codes for all providers using coordinates
            resolved = 0
            for result in _devon_cache:
                if result.provider_latitude and result.provider_longitude:
                    lad = coords_to_lad(
                        result.provider_latitude,
                        result.provider_longitude,
                        _DEVON_DISTRICTS,
                    )
                    _devon_lad_cache[result.provider_id] = lad
                    if lad:
                        resolved += 1
            logger.info(
                f"Devon FIS: resolved {resolved}/{len(_devon_cache)} "
                f"providers to district LADs via coordinates"
            )
        else:
            logger.info(
                f"Devon FIS: using cached results "
                f"({len(_devon_cache)} providers) for {lad25cd}"
            )

        yielded = 0
        skipped = 0
        for cached_result in _devon_cache:
            if cached_result.provider_id in existing_provider_ids:
                continue
            # Assign to correct district based on coordinate lookup
            resolved_lad = _devon_lad_cache.get(cached_result.provider_id)
            if resolved_lad and resolved_lad != lad25cd:
                skipped += 1
                continue  # Provider belongs to a different Devon district
            yield ProviderResult(
                lad25cd=lad25cd,
                provider_id=cached_result.provider_id,
                provider_name=cached_result.provider_name,
                provider_phone=cached_result.provider_phone,
                provider_email=cached_result.provider_email,
                provider_latitude=cached_result.provider_latitude,
                provider_longitude=cached_result.provider_longitude,
                source_url=cached_result.source_url,
                raw_html=cached_result.raw_html,
                raw_json=cached_result.raw_json,
                scrape_status=cached_result.scrape_status,
            )
            yielded += 1

        logger.info(
            f"Devon FIS: yielded {yielded} providers for {lad25cd} "
            f"(skipped {skipped} belonging to other districts)"
        )


def _scrape_devon_providers(logger: Logger) -> list[ProviderResult]:
    """Scrape all childcare providers from findchildcareindevon.co.uk.

    Phase 1: Query overlapping geographic circles via GET with real postcodes.
             Extract provider detail links from HTML and lat/lng from map JS.
             Deduplicate by providerId.
    Phase 2: Fetch each unique detail page for name, phone, email.
    """
    session = requests.Session()
    session.headers.update({"User-Agent": _USER_AGENT})

    # Phase 1: Collect all provider links + lat/lng from listing pages
    # Key: providerId -> dict with service_id, lat, lng, detail_url
    providers: dict[str, dict] = {}

    for postcode, lat, lng, area_name, radius in _SEARCH_POINTS:
        logger.info(f"Devon FIS: searching {area_name} ({postcode}, {radius}mi)")
        listing_html = _fetch_listing(session, postcode, lat, lng, radius, logger)

        # Extract provider detail links from HTML <a> tags
        soup = BeautifulSoup(listing_html, "html.parser")
        page_providers = _extract_provider_links(soup)

        # Extract lat/lng + URL mapping from map JavaScript markers
        marker_data = _extract_marker_data(listing_html)

        # Check for result count text
        count_match = re.search(r"(\d+)\s+providers?\s+found", listing_html)
        result_count = int(count_match.group(1)) if count_match else len(page_providers)

        if result_count >= 200:
            logger.warning(
                f"Devon FIS: {area_name} returned {result_count} results "
                f"— may have hit cap! Consider smaller radius."
            )

        logger.info(
            f"  -> {len(page_providers)} provider links, "
            f"{len(marker_data)} markers from {area_name}"
        )

        # Merge into global providers dict
        for pid, pinfo in page_providers.items():
            if pid not in providers:
                providers[pid] = pinfo

        # Merge marker lat/lng data (keyed by providerId from marker URLs)
        for _sid, mdata in marker_data.items():
            pid = mdata.get("provider_id")
            if pid and pid in providers:
                lat_val = mdata.get("lat")
                lng_val = mdata.get("lng")
                if lat_val and lng_val and lat_val != 0 and lng_val != 0:
                    providers[pid]["latitude"] = lat_val
                    providers[pid]["longitude"] = lng_val

    logger.info(
        f"Devon FIS: {len(providers)} unique providers from "
        f"{len(_SEARCH_POINTS)} search points"
    )

    # Phase 2: Fetch detail pages
    results: list[ProviderResult] = []
    for i, (pid, pinfo) in enumerate(providers.items()):
        if (i + 1) % 50 == 0:
            logger.info(f"Devon FIS: fetching detail {i + 1}/{len(providers)}")

        detail_url = pinfo["detail_url"]
        detail_html = _fetch_detail_page(session, detail_url, logger)

        detail_soup = BeautifulSoup(detail_html, "html.parser")
        name = _extract_name(detail_soup)
        phone = _extract_phone(detail_soup)
        email = _extract_email(detail_soup)

        structured_data = {
            "provider_id": pid,
            "service_id": pinfo.get("service_id"),
            "detail_url": detail_url,
            "latitude": pinfo.get("latitude"),
            "longitude": pinfo.get("longitude"),
            "name": name,
            "phone": phone,
            "email": email,
        }

        results.append(
            ProviderResult(
                lad25cd="",  # Filled in by scrape_la
                provider_id=pid,
                provider_name=name,
                provider_phone=phone,
                provider_email=email,
                provider_latitude=pinfo.get("latitude"),
                provider_longitude=pinfo.get("longitude"),
                source_url=detail_url,
                raw_html=detail_html,
                raw_json=json.dumps(structured_data),
                scrape_status=(
                    "success"
                    if name and pinfo.get("latitude") is not None
                    else "partial"
                    if name
                    else "error"
                ),
            )
        )

    logger.info(f"Devon FIS: scraped {len(results)} provider detail pages")
    return results


def _fetch_listing(
    session: requests.Session,
    postcode: str,
    lat: float,
    lng: float,
    radius: str,
    logger: Logger,
) -> str:
    """GET /Provider with postcode-based geographic search parameters."""
    params = {
        "Postcode": postcode,
        "Proximity": radius,
        "Latitude": str(lat),
        "Longitude": str(lng),
        "IsShortList": "False",
    }

    resp = fetch(
        session,
        _SEARCH_URL,
        params=params,
        timeout=_REQUEST_TIMEOUT,
        rate_limiter=_rate_limiter,
    )
    return resp.text


def _extract_provider_links(soup: BeautifulSoup) -> dict[str, dict]:
    """Extract provider detail links from a listing page.

    Filters out _ShortList links (add-to-shortlist actions, not detail pages).
    Returns dict keyed by providerId with detail_url and optional serviceId.
    """
    providers: dict[str, dict] = {}

    for link in soup.select("a[href*='providerId']"):
        href = link.get("href", "")
        if not href or "_ShortList" in href:
            continue

        parsed = urlparse(href)
        params = parse_qs(parsed.query)

        provider_id = params.get("providerId", [None])[0]
        if not provider_id:
            continue

        service_id = params.get("serviceId", [None])[0]

        # Build full detail URL
        if href.startswith("/"):
            detail_url = f"{_BASE_URL}{href}"
        elif href.startswith("http"):
            detail_url = href
        else:
            detail_url = f"{_BASE_URL}/{href}"

        # Prefer DetailService URLs (with serviceId) over bare Details URLs
        if provider_id not in providers or service_id:
            providers[provider_id] = {
                "service_id": service_id,
                "detail_url": detail_url,
            }

    return providers


def _extract_marker_data(html: str) -> dict[str, dict]:
    """Extract lat/lng and provider IDs from Google Maps marker JavaScript.

    Parses the pattern:
        myLatLng = new google.maps.LatLng(lat, lng);
        marker{serviceId} = new google.maps.Marker({
            ...
            url: './Provider/DetailService?providerId=X&serviceId=Y'
        });

    Returns dict keyed by serviceId with lat, lng, provider_id.
    """
    markers: dict[str, dict] = {}

    for match in _MARKER_BLOCK_RE.finditer(html):
        lat_str, lng_str, service_id, url_path = match.groups()
        try:
            lat = float(lat_str)
            lng = float(lng_str)
        except ValueError:
            continue

        if lat == 0 and lng == 0:
            continue

        # Extract providerId from the URL
        url_params = parse_qs(urlparse(url_path).query)
        provider_id = url_params.get("providerId", [None])[0]

        markers[service_id] = {
            "lat": lat,
            "lng": lng,
            "provider_id": provider_id,
        }

    return markers


def _fetch_detail_page(
    session: requests.Session,
    url: str,
    logger: Logger,
) -> str:
    """Fetch a single provider detail page."""
    resp = fetch(session, url, timeout=_REQUEST_TIMEOUT, rate_limiter=_rate_limiter)
    return resp.text


def _extract_name(soup: BeautifulSoup) -> str | None:
    """Extract provider name from h1 tag."""
    h1 = soup.select_one("h1")
    if h1:
        return clean_text(h1.get_text())
    return None


def _extract_phone(soup: BeautifulSoup) -> str | None:
    """Extract provider phone number from detail page.

    Two patterns exist:
    - DetailService pages: <li><span>Telephone:</span> NUMBER </li>
    - Details pages:       <li><b>Phone: </b> NUMBER</li>

    There is also a generic Devon CC phone in a .contact-details section
    at the bottom which we must skip.
    """
    # Pattern 1: <li> containing <span>Telephone:</span>
    for li in soup.find_all("li"):
        span = li.find("span", string=re.compile(r"Telephone", re.IGNORECASE))
        if span:
            li_text = li.get_text()
            match = re.search(r"Telephone[:\s]*([\d\s()+-]+)", li_text, re.IGNORECASE)
            if match:
                phone = clean_text(match.group(1))
                if phone:
                    return phone

    # Pattern 2: <li> containing <b>Phone:</b>
    for li in soup.find_all("li"):
        bold = li.find("b", string=re.compile(r"Phone", re.IGNORECASE))
        if bold:
            li_text = li.get_text()
            match = re.search(r"Phone[:\s]*([\d\s()+-]+)", li_text, re.IGNORECASE)
            if match:
                phone = clean_text(match.group(1))
                if phone:
                    return phone

    return None


def _extract_email(soup: BeautifulSoup) -> str | None:
    """Extract provider email from first mailto: link.

    Skips the generic Devon CC email (eycs@devon.gov.uk).
    """
    for mailto in soup.select("a[href^='mailto:']"):
        href = mailto.get("href", "")
        email = href.replace("mailto:", "").strip()
        if email and email.lower() != _DEVON_CC_EMAIL:
            return email
    return None
