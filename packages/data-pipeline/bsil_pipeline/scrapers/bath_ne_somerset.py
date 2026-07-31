"""Scraper for Bath & North East Somerset childcare providers.

Paginates through the search results at livewell.bathnes.gov.uk/children-and-families/find-childcare
to discover provider URLs, then scrapes each provider page.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Iterator

import requests
from bs4 import BeautifulSoup

from bsil_pipeline.scrapers.base import BaseScraper, ProviderResult
from bsil_pipeline.scrapers.http import fetch
from bsil_pipeline.scrapers.rate_limiter import DomainRateLimiter

if TYPE_CHECKING:
    from logging import Logger

LAD25CD = "E06000022"
REQUEST_DELAY = 0.5
SEARCH_URL = "https://livewell.bathnes.gov.uk/children-and-families/find-childcare"
BASE_URL = "https://livewell.bathnes.gov.uk"
PAGE_SIZE = 10
POSTCODE_RE = re.compile(r"[A-Z]{1,2}\d{1,2}[A-Z]?\s*\d[A-Z]{2}", re.IGNORECASE)
OFSTED_RE = re.compile(r"EY\d+|CA\d+|\b\d{6,7}\b", re.IGNORECASE)

_HEADERS = {"User-Agent": "BSIL-DataPipeline/1.0 (research; best-start-in-life)"}
_rate_limiter = DomainRateLimiter(default_interval=REQUEST_DELAY)


def _extract_provider_links(soup: BeautifulSoup) -> list[str]:
    """Extract provider detail hrefs from a search results listing page."""
    links = []
    for a in soup.select(".views-row h2.govuk-heading-m a, .views-row h2 a"):
        href = a.get("href", "")
        if href and href not in links:
            links.append(href)
    if not links:
        # Fallback: any link in a views-row pointing to a childcare or node path
        for a in soup.find_all(
            "a", href=re.compile(r"^/(?:children-and-families/|node/)\S")
        ):
            href = a["href"]
            # Exclude pagination and category links
            if "find-childcare" not in href and href not in links:
                links.append(href)
    return links


class BathNeSomersetScraper(BaseScraper):
    """Scraper for livewell.bathnes.gov.uk childcare provider pages."""

    platform_key = "bath_ne_somerset"

    def _collect_provider_urls(self, session, logger) -> list[str]:
        """Paginate search results to collect all provider detail URLs."""
        seen: list[str] = []
        seen_set: set[str] = set()
        page = 0
        max_pages = 500  # safety limit

        while page < max_pages:
            page_url = f"{SEARCH_URL}?page={page}"
            resp = fetch(session, page_url, timeout=15, rate_limiter=_rate_limiter)

            soup = BeautifulSoup(resp.text, "html.parser")
            hrefs = _extract_provider_links(soup)

            new_on_page = 0
            for href in hrefs:
                full_url = href if href.startswith("http") else BASE_URL + href
                if full_url not in seen_set:
                    seen.append(full_url)
                    seen_set.add(full_url)
                    new_on_page += 1

            logger.info(
                f"  Page {page}: {len(hrefs)} links, {new_on_page} new (total {len(seen)})"
            )

            if len(hrefs) < PAGE_SIZE:
                break
            page += 1

        return seen

    def _parse_provider(self, url: str, raw_html: str) -> dict:
        """Parse a provider page HTML into structured fields."""
        result: dict = {
            "name": None,
            "phone": None,
            "email": None,
            "website": None,
            "address_line1": None,
            "city": None,
            "postcode": None,
            "registered_places": None,
            "institution_type": None,
            "ofsted_number": None,
            "eligible_age_range": None,
        }

        soup = BeautifulSoup(raw_html, "html.parser")

        h1 = soup.find("h1")
        if h1:
            result["name"] = h1.get_text(strip=True)
        else:
            title = soup.find("title")
            if title:
                result["name"] = title.get_text(strip=True).split(" | ")[0]

        fields: dict[str, str] = {}
        for h3 in soup.find_all("h3"):
            label = h3.get_text(strip=True).lower()
            sib = h3.find_next_sibling()
            value = sib.get_text(strip=True) if sib else ""
            if value:
                fields[label] = value

        def _field(*keys: str) -> str | None:
            for k in keys:
                v = fields.get(k)
                if v:
                    return v
            return None

        result["phone"] = _field("telephone", "phone")
        result["email"] = _field("email")
        result["institution_type"] = _field("registration type")
        result["eligible_age_range"] = _field("what age ranges do you cater for?")

        for h3 in soup.find_all("h3"):
            if h3.get_text(strip=True).lower() == "ofsted number":
                sib = h3.find_next_sibling()
                if sib:
                    a = sib.find("a")
                    text = a.get_text(strip=True) if a else sib.get_text(strip=True)
                    m = OFSTED_RE.search(text)
                    result["ofsted_number"] = m.group().upper() if m else None
                break

        places_raw = _field("what is the maximum children you will cater for")
        if places_raw:
            m = re.search(r"\d+", places_raw)
            result["registered_places"] = int(m.group()) if m else None

        for h3 in soup.find_all("h3"):
            if h3.get_text(strip=True).lower() == "website":
                sib = h3.find_next_sibling()
                if sib:
                    if sib.name == "a" and sib.get("href"):
                        result["website"] = sib["href"]
                    else:
                        link = sib.find("a")
                        result["website"] = (
                            link["href"] if link and link.get("href") else None
                        )
                break

        # Opening hours — parsed from <h2>Opening hours</h2> section
        # Each day is: <strong>Monday:</strong> 15:15 - 18:00
        TIME_RE = re.compile(r"(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})")
        opening_hours_raw = None
        for h2 in soup.find_all("h2"):
            if h2.get_text(strip=True).lower() == "opening hours":
                parts = []
                for p in h2.find_all_next("p"):
                    strong = p.find("strong")
                    if not strong:
                        break
                    day = strong.get_text(strip=True).rstrip(":")
                    text = p.get_text(strip=True)
                    m = TIME_RE.search(text)
                    if m:
                        open_t = m.group(1).zfill(5)
                        close_t = m.group(2).zfill(5)
                        parts.append(f"{day}: {open_t} - {close_t}")
                if parts:
                    opening_hours_raw = " ".join(parts)
                break
        result["opening_hours_raw"] = opening_hours_raw

        addr_raw = _field("address")
        if addr_raw:
            pc_match = POSTCODE_RE.search(addr_raw)
            result["postcode"] = pc_match.group().strip() if pc_match else None
            addr_clean = POSTCODE_RE.sub("", addr_raw).strip().rstrip(",").strip()
            parts = [
                p.strip()
                for p in re.split(r"\n|(?<=[a-z])(?=[A-Z])", addr_clean)
                if p.strip()
            ]
            result["address_line1"] = parts[0] if parts else None
            result["city"] = parts[-1] if len(parts) > 1 else None

        return result

    def scrape_la(
        self,
        lad25cd: str,
        fis_url: str,
        existing_provider_ids: set[str],
        logger: Logger,
    ) -> Iterator[ProviderResult]:
        session = requests.Session()
        session.headers.update(_HEADERS)

        logger.info("Collecting provider URLs from search results pages...")
        all_urls = self._collect_provider_urls(session, logger)
        logger.info(f"Found {len(all_urls)} provider URLs")

        for url in all_urls:
            provider_id = url.rstrip("/").split("/")[-1]
            if provider_id in existing_provider_ids:
                continue

            resp = fetch(session, url, timeout=15, rate_limiter=_rate_limiter)
            raw_html = resp.text

            parsed = self._parse_provider(url, raw_html)

            yield ProviderResult(
                lad25cd=lad25cd,
                provider_id=provider_id,
                provider_name=parsed["name"],
                provider_address_line1=parsed["address_line1"],
                provider_town=parsed["city"],
                provider_postcode=parsed["postcode"],
                provider_urn=parsed["ofsted_number"],
                provider_phone=parsed["phone"],
                provider_email=parsed["email"],
                source_url=url,
                raw_html=raw_html,
                scrape_status="success",
            )
