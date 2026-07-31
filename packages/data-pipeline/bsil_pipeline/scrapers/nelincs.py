"""NE Lincolnshire FIS scraper.

Covers 1 LA: North East Lincolnshire (E06000012).

Server-rendered HTML with Bootstrap modals. No AJAX, no pagination — all
results for a category load on a single page.

    GET https://www.nelincs.gov.uk/fis/?category={URL_ENCODED_CATEGORY}

Modals are ``<div class="modal fade" id="fis_{id}">`` containing provider
details.  Emails may be protected by Cloudflare email obfuscation
(``data-cfemail`` attribute).
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Iterator
from urllib.parse import quote, urljoin

import requests
from bs4 import BeautifulSoup

from bsil_pipeline.scrapers.base import (
    BaseScraper,
    ProviderResult,
    clean_text,
    POSTCODE_RE,
)
from bsil_pipeline.scrapers.http import fetch
from bsil_pipeline.scrapers.rate_limiter import DomainRateLimiter

if TYPE_CHECKING:
    from logging import Logger

_USER_AGENT = "BSIL-DataPipeline/1.0 (research; best-start-in-life)"
_REQUEST_TIMEOUT = 30
_rate_limiter = DomainRateLimiter(default_interval=1.0)

_BASE_URL = "https://www.nelincs.gov.uk/fis/"


def _decode_cfemail(encoded: str) -> str:
    """Decode Cloudflare email obfuscation (XOR cipher)."""
    key = int(encoded[:2], 16)
    return "".join(
        chr(int(encoded[i : i + 2], 16) ^ key) for i in range(2, len(encoded), 2)
    )


class NelincsScraper(BaseScraper):
    @property
    def platform_key(self) -> str:
        return "nelincs"

    def scrape_la(
        self,
        lad25cd: str,
        fis_url: str,
        existing_provider_ids: set[str],
        logger: Logger,
    ) -> Iterator[ProviderResult]:
        """Scrape NE Lincolnshire childcare providers from FIS modals."""
        session = requests.Session()
        session.headers.update({"User-Agent": _USER_AGENT})

        # Step 1: fetch base page and extract category options
        resp = fetch(
            session, fis_url, timeout=_REQUEST_TIMEOUT, rate_limiter=_rate_limiter
        )

        base_soup = BeautifulSoup(resp.text, "html.parser")
        categories = _extract_categories(base_soup)
        logger.info(f"NELincs: found {len(categories)} categories")

        if not categories:
            logger.warning("NELincs: no categories found, scraping base page only")
            categories = [("", "base")]

        # Step 2: scrape each category, dedup by modal ID
        seen_ids: dict[str, ProviderResult] = {}
        provider_categories: dict[str, list[str]] = {}

        # Also parse modals from the base page itself
        _parse_modals_from_soup(
            base_soup, lad25cd, fis_url, seen_ids, provider_categories
        )

        for cat_value, cat_label in categories:
            if not cat_value:
                continue
            cat_url = f"{_BASE_URL}?category={quote(cat_value)}"

            resp = fetch(
                session, cat_url, timeout=_REQUEST_TIMEOUT, rate_limiter=_rate_limiter
            )

            soup = BeautifulSoup(resp.text, "html.parser")
            new_count = _parse_modals_from_soup(
                soup, lad25cd, fis_url, seen_ids, provider_categories, cat_label
            )
            logger.info(f"NELincs: category {cat_label!r} — {new_count} new providers")

        # Step 3: yield results, filtering out existing IDs
        yielded = 0
        for provider_id, result in seen_ids.items():
            if provider_id in existing_provider_ids:
                continue
            cats = provider_categories.get(provider_id, [])
            if cats:
                result.metadata_json = json.dumps({"search_categories": cats})
            yield result
            yielded += 1

        logger.info(f"NELincs: yielded {yielded} providers for {lad25cd}")


def _extract_categories(soup: BeautifulSoup) -> list[tuple[str, str]]:
    """Extract category options from the <select> dropdown."""
    select = soup.find("select", attrs={"name": "category"})
    if select is None:
        # Try other common select patterns
        select = soup.find("select", id=re.compile(r"category", re.I))
    if select is None:
        return []

    categories = []
    for option in select.find_all("option"):
        value = option.get("value", "").strip()
        label = clean_text(option.get_text()) or value
        if value and value.lower() not in ("", "all", "select", "0", "--"):
            categories.append((value, label))
    return categories


def _parse_modals_from_soup(
    soup: BeautifulSoup,
    lad25cd: str,
    source_url: str,
    seen_ids: dict[str, ProviderResult],
    provider_categories: dict[str, list[str]] | None = None,
    category_label: str | None = None,
) -> int:
    """Parse Bootstrap modals from a page and add new ones to seen_ids.

    Records which category each provider appeared under in provider_categories.
    Returns the number of new providers found.
    """
    new_count = 0
    modals = soup.find_all("div", class_="modal", id=re.compile(r"^fis_"))

    for modal in modals:
        modal_id = modal.get("id", "")
        # Extract numeric ID from "fis_123"
        provider_id = modal_id.replace("fis_", "")
        if not provider_id:
            continue

        if provider_categories is not None and category_label:
            provider_categories.setdefault(provider_id, []).append(category_label)

        if provider_id in seen_ids:
            continue

        result = _parse_modal(modal, lad25cd, provider_id, source_url)
        seen_ids[provider_id] = result
        new_count += 1

    return new_count


def _parse_modal(
    modal, lad25cd: str, provider_id: str, source_url: str
) -> ProviderResult:
    """Extract provider data from a single Bootstrap modal."""
    raw_html = str(modal)

    # Provider name from modal title
    title_el = modal.find(re.compile(r"h[1-6]"), class_=re.compile(r"modal-title"))
    name = clean_text(title_el.get_text()) if title_el else None

    # Phone — <a href="tel:...">
    phone = None
    tel_link = modal.find("a", href=re.compile(r"^tel:"))
    if tel_link:
        phone = clean_text(tel_link.get_text())
        if not phone:
            phone = tel_link["href"].replace("tel:", "").strip()

    # Email — check for Cloudflare obfuscation first, then plain mailto
    email = None
    cf_email = modal.find("span", class_="__cf_email__")
    if cf_email and cf_email.get("data-cfemail"):
        try:
            email = _decode_cfemail(cf_email["data-cfemail"])
        except Exception:  # nosec B110
            pass
    if not email:
        # Also check <a> tags with data-cfemail attribute
        cf_link = modal.find("a", attrs={"data-cfemail": True})
        if cf_link:
            try:
                email = _decode_cfemail(cf_link["data-cfemail"])
            except Exception:  # nosec B110
                pass
    if not email:
        mailto_link = modal.find("a", href=re.compile(r"^mailto:"))
        if mailto_link:
            email = mailto_link["href"].replace("mailto:", "").strip()
            if not email:
                email = clean_text(mailto_link.get_text())

    # Address — find the modal body and look for address lines
    address_line1 = None
    postcode = None
    town = None

    modal_body = modal.find("div", class_="modal-body")
    if modal_body:
        # Address is typically in <p> tags — look for lines that contain a postcode
        paragraphs = modal_body.find_all("p")
        for p in paragraphs:
            text = p.get_text(separator="\n").strip()
            lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
            # Check if any line looks like a postcode
            for i, line in enumerate(lines):
                if POSTCODE_RE.search(line):
                    postcode = POSTCODE_RE.search(line).group().strip()
                    # Lines before the postcode are address parts
                    addr_lines = [ln for ln in lines[:i] if ln != name]
                    if addr_lines:
                        address_line1 = addr_lines[0]
                    if len(addr_lines) >= 2:
                        town = addr_lines[-1]
                    break

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
        provider_address_line1=address_line1,
        provider_town=town,
        provider_postcode=postcode,
        provider_phone=phone,
        provider_email=email,
        source_url=source_url,
        raw_html=raw_html,
        scrape_status=status,
    )
