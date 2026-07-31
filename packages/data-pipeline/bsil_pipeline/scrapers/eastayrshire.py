"""East Ayrshire early years centres scraper.

Covers 1 LA: East Ayrshire (S12000008).

The site lists all 44 early learning and childcare centres in a single
static HTML table (class="facilities"). Each provider occupies a pair
of <tr> rows inside its own <tbody>:

  Row 1: provider name (link to /Map.aspx?{id}) + town
  Row 2: contact person, email, phone

No pagination, no JS rendering — plain HTTP GET + BeautifulSoup.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Iterator

import requests
from bs4 import BeautifulSoup

from bsil_pipeline.scrapers.base import BaseScraper, ProviderResult, clean_text
from bsil_pipeline.scrapers.http import fetch
from bsil_pipeline.scrapers.rate_limiter import DomainRateLimiter

if TYPE_CHECKING:
    from logging import Logger

_USER_AGENT = "BSIL-DataPipeline/1.0 (research; best-start-in-life)"
_REQUEST_TIMEOUT = 30
_rate_limiter = DomainRateLimiter(default_interval=1.0)

_MAP_ID_RE = re.compile(r"/Map\.aspx\?(\d+)")


class EastAyrshireScraper(BaseScraper):
    @property
    def platform_key(self) -> str:
        return "eastayrshire"

    def scrape_la(
        self,
        lad25cd: str,
        fis_url: str,
        existing_provider_ids: set[str],
        logger: Logger,
    ) -> Iterator[ProviderResult]:
        """Scrape East Ayrshire providers from a static HTML table."""
        session = requests.Session()
        session.headers.update({"User-Agent": _USER_AGENT})

        resp = fetch(
            session, fis_url, timeout=_REQUEST_TIMEOUT, rate_limiter=_rate_limiter
        )

        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table", class_="facilities")
        if not table:
            logger.error("EastAyrshire: could not find table.facilities")
            yield ProviderResult(
                lad25cd=lad25cd,
                provider_id="__no_table__",
                scrape_status="error",
                source_url=fis_url,
            )
            return

        # Each provider is in its own <tbody> with two <tr> rows
        tbodies = table.find_all("tbody")
        logger.info(f"EastAyrshire: found {len(tbodies)} provider blocks")

        yielded = 0
        for tbody in tbodies:
            rows = tbody.find_all("tr")
            if len(rows) < 2:
                continue

            result = _parse_provider(lad25cd, rows[0], rows[1], fis_url)
            if result is None:
                continue
            if result.provider_id in existing_provider_ids:
                continue

            yield result
            yielded += 1

        logger.info(f"EastAyrshire: yielded {yielded} providers for {lad25cd}")


def _parse_provider(
    lad25cd: str,
    name_row: BeautifulSoup,
    contact_row: BeautifulSoup,
    source_url: str,
) -> ProviderResult | None:
    """Parse a pair of table rows into a ProviderResult."""
    # Row 1: name link + town
    name_link = name_row.find("a", href=_MAP_ID_RE)
    if not name_link:
        return None

    m = _MAP_ID_RE.search(name_link["href"])
    provider_id = m.group(1) if m else ""
    name = clean_text(name_link.get_text())

    tds = name_row.find_all("td")
    town = clean_text(tds[1].get_text()) if len(tds) > 1 else None

    # Row 2: email, phone
    email_link = contact_row.find("a", href=lambda h: h and h.startswith("mailto:"))
    email = email_link["href"].replace("mailto:", "") if email_link else None

    phone_link = contact_row.find("a", href=lambda h: h and h.startswith("tel:"))
    phone = clean_text(phone_link.get_text()) if phone_link else None

    has_name = bool(name)
    has_town = bool(town)

    if has_name and has_town:
        status = "success"
    elif has_name:
        status = "partial"
    else:
        status = "error"

    return ProviderResult(
        lad25cd=lad25cd,
        provider_id=provider_id,
        provider_name=name,
        provider_town=town,
        provider_phone=phone,
        provider_email=email,
        source_url=source_url,
        scrape_status=status,
    )
