"""Jadu CMS /directory/ scraper.

Originally expected to cover 4 LAs, but research showed:
- Rotherham: Has a childcare directory at ID 197 (not 24 as in CSV)
- Stoke-on-Trent: Directory 24 is "No cold-calling zones" — no childcare
- Swindon: No Jadu directories (uses Synergy for childcare)
- Highland: Directory 25 is policies — no childcare

Only Rotherham has an actual Jadu childcare directory. The other LAs
are handled as council_generic or reclassified.

Rotherham Jadu structure:
  Directory home: /directory/197/childminders-and-childcare-providers
  Categories:     /directory/197/.../category/{categoryID}
  Pagination:     /directory/197/.../category/{categoryID}/{pageNum}
  A-Z listing:    /directory/197/a-to-z/{letter}
  Record detail:  /directory-record/{recordID}/{slug}
  Search:         /directory/search?directoryID=197&keywords={query}

Categories (directory 197):
  410 = Breakfast Clubs, 405 = Childminders, 403 = Day Nurseries,
  408 = Holiday Clubs, 406 = Pre-Schools, 402 = School Nurseries,
  407 = Wraparound
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Iterator
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from bsil_pipeline.scrapers.base import (
    BaseScraper,
    ProviderResult,
    clean_text,
    parse_address_parts,
    POSTCODE_RE,
)
from bsil_pipeline.scrapers.http import fetch
from bsil_pipeline.scrapers.rate_limiter import DomainRateLimiter

if TYPE_CHECKING:
    from logging import Logger

_USER_AGENT = "BSIL-DataPipeline/1.0 (research; best-start-in-life)"
_REQUEST_TIMEOUT = 20

_rate_limiter = DomainRateLimiter(default_interval=1.0)

# Known correct directory IDs for childcare (overrides CSV URLs)
_DIRECTORY_OVERRIDES: dict[str, int] = {
    "E08000018": 197,  # Rotherham
}

# Category IDs for Rotherham directory 197
_ROTHERHAM_CATEGORIES = [410, 405, 403, 408, 406, 402, 407]

# LAs where Jadu has no childcare directory
_NO_CHILDCARE_DIRECTORY: set[str] = {
    "E06000021",  # Stoke-on-Trent
    "S12000017",  # Highland
    "E06000030",  # Swindon (uses Synergy)
}


class JaduScraper(BaseScraper):
    @property
    def platform_key(self) -> str:
        return "jadu"

    def scrape_la(
        self,
        lad25cd: str,
        fis_url: str,
        existing_provider_ids: set[str],
        logger: Logger,
    ) -> Iterator[ProviderResult]:
        """Scrape childcare providers from a Jadu CMS directory."""
        # Check if this LA is known to have no childcare directory
        if lad25cd in _NO_CHILDCARE_DIRECTORY:
            logger.info(
                f"Jadu {lad25cd}: no childcare directory — marking as unsupported"
            )
            yield ProviderResult(
                lad25cd=lad25cd,
                provider_id="__no_childcare_directory__",
                scrape_status="unsupported_platform",
                source_url=fis_url,
            )
            return

        session = requests.Session()
        session.headers.update({"User-Agent": _USER_AGENT})

        # Determine the correct base URL and directory ID
        parsed = urlparse(fis_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        directory_id = _DIRECTORY_OVERRIDES.get(lad25cd)
        if not directory_id:
            # Try to extract from the URL
            match = re.search(r"/directory/(\d+)", fis_url)
            if match:
                directory_id = int(match.group(1))
            else:
                logger.warning(f"Jadu {lad25cd}: cannot determine directory ID")
                yield ProviderResult(
                    lad25cd=lad25cd,
                    provider_id="__no_directory_id__",
                    scrape_status="error",
                    source_url=fis_url,
                )
                return

        logger.info(f"Jadu {lad25cd}: scraping directory {directory_id} on {base_url}")

        # Collect provider records via A-Z listing
        entries = _collect_providers_az(
            session, base_url, directory_id, existing_provider_ids, logger
        )
        logger.info(f"Jadu {lad25cd}: found {len(entries)} provider entries")

        # Fetch detail pages
        yielded = 0
        for entry in entries:
            result = _scrape_detail_page(session, lad25cd, entry, logger)
            yield result
            yielded += 1

            if yielded % 50 == 0:
                logger.info(
                    f"Jadu {lad25cd}: scraped {yielded}/{len(entries)} detail pages"
                )

        logger.info(f"Jadu scrape complete for {lad25cd}: {yielded} providers")


def _collect_providers_az(
    session: requests.Session,
    base_url: str,
    directory_id: int,
    existing_provider_ids: set[str],
    logger: Logger,
) -> list[dict]:
    """Collect provider entries via A-Z listing pages."""
    entries: list[dict] = []
    seen_ids: set[str] = set()

    letters = list("abcdefghijklmnopqrstuvwxyz") + ["0-9"]

    for letter in letters:
        url = f"{base_url}/directory/{directory_id}/a-to-z/{letter}"
        _rate_limiter.wait(url)

        # 404 is expected here — not all letters have results.
        # Uses raw session.get() rather than fetch() because this is
        # exploratory pagination, not a required resource.
        try:
            resp = session.get(url, timeout=_REQUEST_TIMEOUT)
            if resp.status_code == 404:
                continue
            resp.raise_for_status()
        except Exception as e:
            logger.warning(f"Failed to fetch A-Z page {letter}: {e}")
            continue

        soup = BeautifulSoup(resp.text, "html.parser")

        # Extract record links — Jadu uses /directory-record/{id}/{slug}
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            match = re.search(r"/directory-record/(\d+)", href)
            if not match:
                # Try older format: /directory_record/{id}
                match = re.search(r"/directory_record/(\d+)", href)
            if not match:
                continue

            record_id = match.group(1)
            if record_id in seen_ids or record_id in existing_provider_ids:
                continue
            seen_ids.add(record_id)

            name = clean_text(a_tag.get_text())
            detail_url = urljoin(base_url, href)

            entries.append(
                {
                    "record_id": record_id,
                    "name": name,
                    "detail_url": detail_url,
                }
            )

    return entries


def _scrape_detail_page(
    session: requests.Session,
    lad25cd: str,
    entry: dict,
    logger: Logger,
) -> ProviderResult:
    """Fetch and parse a Jadu CMS directory record detail page."""
    record_id = entry["record_id"]
    detail_url = entry["detail_url"]

    resp = fetch(
        session, detail_url, timeout=_REQUEST_TIMEOUT, rate_limiter=_rate_limiter
    )

    html = resp.text
    soup = BeautifulSoup(html, "html.parser")

    # Provider name from <h1>
    h1 = soup.find("h1")
    provider_name = clean_text(h1.get_text()) if h1 else entry.get("name")

    # Extract address fields from detail page
    address_info = _extract_address(soup)

    # Determine status
    has_name = bool(provider_name)
    has_postcode = bool(address_info.get("postcode"))

    if has_name and has_postcode:
        status = "success"
    elif has_name or has_postcode:
        status = "partial"
    else:
        status = "error"

    return ProviderResult(
        lad25cd=lad25cd,
        provider_id=record_id,
        provider_name=provider_name,
        provider_address_line1=address_info.get("address_line1"),
        provider_address_line2=address_info.get("address_line2"),
        provider_address_line3=address_info.get("address_line3"),
        provider_town=address_info.get("town"),
        provider_postcode=address_info.get("postcode"),
        source_url=detail_url,
        raw_html=html,
        scrape_status=status,
    )


def _extract_address(soup: BeautifulSoup) -> dict[str, str | None]:
    """Extract address from a Jadu record detail page.

    Jadu detail pages have structured fields as <strong>Label</strong>: value
    in list items or paragraphs. Fields include Town, Postcode, Area, etc.
    """
    result: dict[str, str | None] = {
        "address_line1": None,
        "address_line2": None,
        "address_line3": None,
        "town": None,
        "postcode": None,
    }

    # Look for labeled fields in list items
    for li in soup.find_all("li"):
        strong = li.find("strong")
        if not strong:
            continue

        label = clean_text(strong.get_text()) or ""
        # Get the text after the label
        full_text = clean_text(li.get_text()) or ""
        value = re.sub(rf"^{re.escape(label)}\s*:?\s*", "", full_text).strip()

        if not value:
            continue

        label_lower = label.lower()
        if label_lower == "postcode":
            result["postcode"] = value.upper()
        elif label_lower == "town":
            result["town"] = value
        elif label_lower in ("address", "street"):
            _parse_jadu_address(value, result)
        elif label_lower == "area":
            if not result["town"]:
                result["town"] = value

    # Also look for dt/dd pairs
    for dt in soup.find_all("dt"):
        dt_text = clean_text(dt.get_text()) or ""
        dd = dt.find_next_sibling("dd")
        if not dd:
            continue
        dd_text = clean_text(dd.get_text())
        if not dd_text:
            continue

        dt_lower = dt_text.lower()
        if "postcode" in dt_lower:
            result["postcode"] = dd_text.upper()
        elif dt_lower == "town":
            result["town"] = dd_text
        elif dt_lower == "address":
            _parse_jadu_address(dd_text, result)

    return result


def _parse_jadu_address(address_text: str, result: dict) -> None:
    """Parse an address string from a Jadu record."""
    parts = [p.strip() for p in address_text.split(",") if p.strip()]
    if not parts:
        return

    # Check if last part is a postcode
    if parts and POSTCODE_RE.search(parts[-1]):
        result["postcode"] = parts[-1].strip().upper()
        parts = parts[:-1]

    if len(parts) >= 1:
        result["address_line1"] = parts[0]
    if len(parts) >= 2:
        result["address_line2"] = parts[1]
    if len(parts) >= 3:
        result["address_line3"] = ", ".join(parts[2:])
