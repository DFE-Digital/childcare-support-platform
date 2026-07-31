"""Scraper for South Gloucestershire childcare directory.

Uses curl_cffi for TLS impersonation to bypass Cloudflare on life.southglos.gov.uk.
Page structure is standard OpenObjects kb5:

- Results listing: results.page?qt=&familychannel=0&term=&childcaretype={n}&sr={offset}
  (20 per page, iterated across all CHILDCARE_TYPES values to find all providers)
- Provider detail: service.page?id={record_id}

Page structure notes:
- Address/postcode live in <section class="service_venue"><dl>
- Ofsted data lives in <section class="childcare_ofsted"><dl>
- Phone lives in <address class="field_section"><dl>
- Postcode dd contains map link text after the postcode — stripped via regex
- Phone dd duplicates the number — first match taken via regex
"""

import json
import re
from typing import TYPE_CHECKING, Iterator

from curl_cffi import requests as cf_requests
from bs4 import BeautifulSoup

from bsil_pipeline.scrapers.base import BaseScraper, ProviderResult, clean_text
from bsil_pipeline.scrapers.http import fetch
from bsil_pipeline.scrapers.openobjects import (
    _extract_service_links,
    _parse_venue_section,
)
from bsil_pipeline.scrapers.rate_limiter import DomainRateLimiter

if TYPE_CHECKING:
    from logging import Logger

LAD25CD = "E06000025"
BASE_URL = "https://life.southglos.gov.uk/kb5/southglos/directory/"
REQUEST_DELAY = 1.0
PAGE_SIZE = 20

CHILDCARE_TYPES = {
    "Early years settings": 1,
    "Maintained nursery classes": 2,
    "Nurseries": 3,
    "Pre school": 4,
    "Childminder": 5,
    "Nannies": 6,
    "Special nurseries": 7,
    "Holiday scheme": 8,
    "Children's centres": 9,
    "Out of school care": 10,
    "Breakfast club": 11,
    "Creche": 12,
}

_POSTCODE_RE = re.compile(r"[A-Z]{1,2}\d{1,2}[A-Z]?\s*\d[A-Z]{2}", re.IGNORECASE)
_PHONE_RE = re.compile(r"[\d\s\(\)\+\-]{7,}")
_rate_limiter = DomainRateLimiter(default_interval=REQUEST_DELAY)


def _extract_postcode(raw: str | None) -> str | None:
    """Extract just the postcode from a string that may include map link text."""
    if not raw:
        return None
    m = _POSTCODE_RE.search(raw)
    return m.group(0).upper() if m else None


def _extract_phone(raw: str | None) -> str | None:
    """Extract the first phone number from a string that may repeat the number."""
    if not raw:
        return None
    # The page renders the number twice (e.g. '01454 77211701454 772117').
    # Take the first run of digit/space/punctuation characters.
    m = _PHONE_RE.search(raw)
    if not m:
        return None
    phone = m.group(0).strip()
    # If the number is repeated, take only the first half
    half = len(phone) // 2
    if half >= 7 and phone[:half].strip() == phone[half:].strip():
        return phone[:half].strip()
    return phone


def _extract_ofsted_urn(soup: BeautifulSoup) -> str | None:
    """Extract Ofsted URN from the childcare_ofsted section."""
    ofsted = soup.find(class_=re.compile(r"childcare_ofsted"))
    if not ofsted:
        return None
    dl = ofsted.find("dl")
    if not dl:
        return None
    for dt in dl.find_all("dt"):
        if "urn" in dt.get_text(strip=True).lower():
            dd = dt.find_next_sibling("dd")
            if dd:
                return clean_text(dd.get_text()) or None
    return None


def _extract_phone_from_page(soup: BeautifulSoup) -> str | None:
    """Extract phone from the address field_section dl."""
    addr_section = soup.find("address", class_=re.compile(r"field_section"))
    if not addr_section:
        return None
    dl = addr_section.find("dl")
    if not dl:
        return None
    for dt in dl.find_all("dt"):
        if dt.get_text(strip=True).lower() == "telephone":
            dd = dt.find_next_sibling("dd")
            if dd:
                return _extract_phone(dd.get_text(strip=True))
    return None


class SouthGlosScraper(BaseScraper):
    platform_key = "south_gloucestershire"

    def _collect_provider_ids(
        self, session, logger
    ) -> dict[str, tuple[str, list[str]]]:
        """Collect all unique provider IDs with their search categories.

        Returns {record_id: (detail_url, [category_name, ...])}.
        """
        seen: dict[str, tuple[str, list[str]]] = {}
        for type_name, type_id in CHILDCARE_TYPES.items():
            offset = 0
            while True:
                page_url = (
                    BASE_URL
                    + f"results.page?qt=&familychannel=0&term=&childcaretype={type_id}&sr={offset}"
                )
                resp = fetch(session, page_url, timeout=20, rate_limiter=_rate_limiter)
                soup = BeautifulSoup(resp.text, "html.parser")
                links = _extract_service_links(soup, BASE_URL)
                for record_id, detail_url in links:
                    if record_id in seen:
                        seen[record_id][1].append(type_name)
                    else:
                        seen[record_id] = (detail_url, [type_name])
                if len(links) < PAGE_SIZE:
                    break
                offset += PAGE_SIZE
            logger.info(
                f"  {type_name}: {sum(1 for _ in links)} on last page, "
                f"{len(seen)} unique total so far"
            )
        return seen

    def scrape_la(
        self, lad25cd, fis_url, existing_provider_ids, logger
    ) -> Iterator[ProviderResult]:
        session = cf_requests.Session(impersonate="chrome")

        logger.info("Collecting provider IDs across all childcare types...")
        all_providers = self._collect_provider_ids(session, logger)
        logger.info(f"Found {len(all_providers)} unique providers")

        providers_found = 0
        for record_id, (detail_url, categories) in all_providers.items():
            if record_id in existing_provider_ids:
                continue

            dresp = fetch(session, detail_url, timeout=20, rate_limiter=_rate_limiter)
            html = dresp.text

            dsoup = BeautifulSoup(html, "html.parser")
            h1 = dsoup.find("h1")
            provider_name = clean_text(h1.get_text()) if h1 else None
            addr = _parse_venue_section(dsoup)
            postcode = _extract_postcode(addr.get("postcode"))
            urn = _extract_ofsted_urn(dsoup)
            phone = _extract_phone_from_page(dsoup)

            status = "error"
            if provider_name and postcode:
                status = "success"
            elif provider_name or postcode:
                status = "partial"

            yield ProviderResult(
                lad25cd=lad25cd,
                provider_id=record_id,
                provider_name=provider_name,
                provider_address_line1=addr.get("address_line1"),
                provider_address_line2=addr.get("address_line2"),
                provider_address_line3=addr.get("address_line3"),
                provider_town=addr.get("town"),
                provider_postcode=postcode,
                provider_urn=urn,
                provider_phone=phone,
                source_url=detail_url,
                raw_html=html,
                metadata_json=json.dumps({"search_categories": categories}),
                scrape_status=status,
            )
            providers_found += 1

        logger.info(f"South Glos complete: {providers_found} new providers scraped")
