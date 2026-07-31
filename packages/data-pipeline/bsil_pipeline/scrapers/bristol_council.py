"""Scraper for Bristol City Council extended hours childcare directory.

Target: https://www.bristol.gov.uk/.../find-extended-hours-free-childcare
Paginated listing (10 per page, ?start=N), with detail pages per provider.

Stores structured data as raw_json (no HTML needed for extraction).
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Iterator

import requests
from bs4 import BeautifulSoup, Tag

from bsil_pipeline.scrapers.base import BaseScraper, ProviderResult
from bsil_pipeline.scrapers.http import fetch
from bsil_pipeline.scrapers.rate_limiter import DomainRateLimiter

if TYPE_CHECKING:
    from logging import Logger

LAD25CD = "E06000023"
BASE_URL = (
    "https://www.bristol.gov.uk/residents/schools-learning-and-early-years"
    "/early-years-and-childcare/help-with-childcare-costs"
    "/free-childcare-for-under-5s/find-extended-hours-free-childcare"
)
DETAIL_URL = BASE_URL + "/30-hours-free-childcare-provider"
PAGE_SIZE = 10
REQUEST_TIMEOUT = 30

_USER_AGENT = "BSIL-DataPipeline/1.0 (research; best-start-in-life)"
_rate_limiter = DomainRateLimiter(default_interval=1.0)

_SOCIAL_DOMAINS = {
    "facebook.com",
    "twitter.com",
    "youtube.com",
    "instagram.com",
    "nextdoor.co.uk",
    "linkedin.com",
}

_ALIAS_MAP: dict[str, str] = {
    "name": "name",
    "type": "provider_type",
    "area": "area",
    "address": "address",
    "email": "email",
    "phone": "phone",
    "age_range": "age_groups",
}

_POSTCODE_RE = re.compile(r"\b([A-Z]{1,2}\d[\dA-Z]?\s?\d[A-Z]{2})\b", re.IGNORECASE)


def _parse_field_aliases(container: Tag) -> dict[str, str]:
    data: dict[str, str] = {}
    for el in container.find_all(class_=re.compile(r"field-alias-")):
        classes = el.get("class", [])
        alias = ""
        for c in classes:
            if c.startswith("field-alias-"):
                alias = c.removeprefix("field-alias-")
                break
        if not alias:
            continue
        field_name = _ALIAS_MAP.get(alias)
        if not field_name:
            continue

        if alias == "email":
            mailto = el.find("a", href=re.compile(r"^mailto:", re.I))
            if mailto:
                data[field_name] = mailto["href"].removeprefix("mailto:").split("?")[0]
                continue

        if alias == "age_range":
            ul = el.find_next_sibling("ul")
            if ul:
                items = [li.get_text(strip=True) for li in ul.find_all("li")]
                data[field_name] = ", ".join(items)
                continue

        strong = el.find("strong")
        label_text = strong.get_text(strip=True) if strong else ""
        full_text = el.get_text(strip=True)
        value = full_text.removeprefix(label_text).strip()
        if value:
            data[field_name] = value

    return data


class BristolCouncilScraper(BaseScraper):
    """Scrapes the Bristol extended-hours childcare directory."""

    @property
    def platform_key(self) -> str:
        return "bristol_council"

    def scrape_la(
        self,
        lad25cd: str,
        fis_url: str,
        existing_provider_ids: set[str],
        logger: Logger,
    ) -> Iterator[ProviderResult]:
        if lad25cd != LAD25CD:
            logger.warning(f"BristolCouncilScraper called for unexpected LA {lad25cd}")
            return

        session = requests.Session()
        session.headers.update({"User-Agent": _USER_AGENT})
        try:
            yield from self._scrape(session, existing_provider_ids, logger)
        finally:
            session.close()

    def _scrape(
        self,
        session: requests.Session,
        existing_provider_ids: set[str],
        logger: Logger,
    ) -> Iterator[ProviderResult]:
        resp = fetch(
            session, BASE_URL, timeout=REQUEST_TIMEOUT, rate_limiter=_rate_limiter
        )
        soup = BeautifulSoup(resp.text, "html.parser")

        total = self._parse_total(soup)
        logger.info(f"BristolCouncil: {total} providers listed")
        num_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

        listing_rows: list[dict] = []
        for page_idx in range(num_pages):
            start = page_idx * PAGE_SIZE
            if page_idx == 0:
                page_soup = soup
            else:
                r = fetch(
                    session,
                    BASE_URL,
                    params={"start": str(start)},
                    timeout=REQUEST_TIMEOUT,
                    rate_limiter=_rate_limiter,
                )
                page_soup = BeautifulSoup(r.text, "html.parser")
            listing_rows.extend(self._extract_listing_rows(page_soup))

        seen: dict[str, dict] = {}
        for row in listing_rows:
            seen[row["bristol_id"]] = row
        listing_rows = list(seen.values())
        logger.info(f"BristolCouncil: {len(listing_rows)} unique providers")

        for i, row in enumerate(listing_rows, 1):
            provider_id = f"council_{row['bristol_id']}"
            if provider_id in existing_provider_ids:
                continue

            if i % 20 == 0:
                logger.info(f"BristolCouncil: detail page {i}/{len(listing_rows)}")

            detail = self._scrape_detail(session, row["bristol_id"])
            merged = {**row, **{k: v for k, v in detail.items() if v}}

            name = merged.get("name", "")
            postcode = merged.get("postcode", "")

            if name and postcode:
                status = "success"
            elif name:
                status = "partial"
            else:
                status = "error"

            addr = merged.get("address", "")
            parts = [p.strip() for p in addr.split(",") if p.strip()] if addr else []
            address_line1 = parts[0] if parts else None

            yield ProviderResult(
                lad25cd=LAD25CD,
                provider_id=provider_id,
                provider_name=name or None,
                provider_address_line1=address_line1,
                provider_postcode=postcode or None,
                provider_phone=merged.get("phone") or None,
                provider_email=merged.get("email") or None,
                source_url=merged.get("source_url"),
                raw_json=json.dumps(merged),
                scrape_status=status,
            )

    @staticmethod
    def _parse_total(soup: BeautifulSoup) -> int:
        m = re.search(r"of\s+(\d+)", soup.get_text())
        return int(m.group(1)) if m else 0

    @staticmethod
    def _extract_listing_rows(soup: BeautifulSoup) -> list[dict]:
        rows: list[dict] = []
        for card in soup.find_all("div", class_="finder-result"):
            row = _parse_field_aliases(card)
            link = card.find("a", href=re.compile(r"id=\d+"))
            if link is None:
                continue
            m = re.search(r"[?&]id=(\d+)", link["href"])
            if not m:
                continue
            row["bristol_id"] = m.group(1)
            if not row.get("name"):
                row["name"] = link.get_text(strip=True)
            rows.append(row)
        return rows

    @staticmethod
    def _scrape_detail(session: requests.Session, bristol_id: str) -> dict:
        url = f"{DETAIL_URL}?id={bristol_id}"
        resp = fetch(session, url, timeout=REQUEST_TIMEOUT, rate_limiter=_rate_limiter)

        soup = BeautifulSoup(resp.text, "html.parser")
        data: dict[str, str] = {"source_url": url}
        data.update(_parse_field_aliases(soup))

        addr = data.get("address", "")
        if addr:
            pc = _POSTCODE_RE.search(addr.upper())
            if pc:
                data["postcode"] = pc.group(1)

        fis_link = soup.find("a", href=re.compile(r"fisprovider"))
        if fis_link:
            data["fis_url"] = fis_link["href"]

        if not data.get("website"):
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if not href.startswith("http"):
                    continue
                if "bristol.gov.uk" in href:
                    continue
                if any(d in href for d in _SOCIAL_DOMAINS):
                    continue
                data["website"] = href
                break

        return data
