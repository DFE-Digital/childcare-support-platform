"""System C / Liquidlogic parent portal scraper.

Covers 2 LAs using the Liquidlogic parent portal platform (v25.1.2.4):
- parent.bristol.gov.uk (Bristol, E06000023)
- parentportal.wakefield.gov.uk (Wakefield, E08000036)

Server-side rendered HTML — no JSON API. Uses requests + BeautifulSoup.

Endpoints:
  /web/portal/pages/fislanding     — landing page (sets session cookies)
  /web/portal/fissearch?category=0&pageNo={n} — search results (10/page)
  /web/portal/pages/fisprovider?provider={hash} — provider detail

Session cookies (BIGipServer~...) are required and set by visiting the
landing page first.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterator
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

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


# ---------------------------------------------------------------------------
# Per-deployment configuration
# ---------------------------------------------------------------------------


@dataclass
class LiquidlogicDeployment:
    """Configuration for a single Liquidlogic portal deployment."""

    domain: str
    lad25cd: str
    base_url: str


DEPLOYMENTS: dict[str, LiquidlogicDeployment] = {
    "parent.bristol.gov.uk": LiquidlogicDeployment(
        domain="parent.bristol.gov.uk",
        lad25cd="E06000023",
        base_url="https://parent.bristol.gov.uk",
    ),
    "parentportal.wakefield.gov.uk": LiquidlogicDeployment(
        domain="parentportal.wakefield.gov.uk",
        lad25cd="E08000036",
        base_url="https://parentportal.wakefield.gov.uk",
    ),
}

_USER_AGENT = "BSIL-DataPipeline/1.0 (research; best-start-in-life)"
_REQUEST_TIMEOUT = 30
_rate_limiter = DomainRateLimiter(default_interval=1.0)

# Regex to extract numeric Ofsted URN from text like "123456Link to Ofsted Report"
_URN_RE = re.compile(r"\d{6,}")


class LiquidlogicScraper(BaseScraper):
    @property
    def platform_key(self) -> str:
        return "liquidlogic"

    def scrape_la(
        self,
        lad25cd: str,
        fis_url: str,
        existing_provider_ids: set[str],
        logger: Logger,
    ) -> Iterator[ProviderResult]:
        deployment = _get_deployment(fis_url)
        if deployment is None:
            logger.warning(
                f"No Liquidlogic deployment config for {fis_url} ({lad25cd})"
            )
            yield ProviderResult(
                lad25cd=lad25cd,
                provider_id="__no_deployment_config__",
                scrape_status="unsupported_platform",
                source_url=fis_url,
            )
            return

        session = requests.Session()
        session.headers.update({"User-Agent": _USER_AGENT})

        # Step 1: Visit landing page to establish session cookies
        landing_url = f"{deployment.base_url}/web/portal/pages/fislanding"
        fetch(
            session, landing_url, timeout=_REQUEST_TIMEOUT, rate_limiter=_rate_limiter
        )

        logger.info(f"Liquidlogic {deployment.domain}: session established")

        # Step 2: Fetch first page and determine max pages
        all_links, max_page = _fetch_search_results(session, deployment, 1)
        logger.info(
            f"Liquidlogic {deployment.domain}: page 1/{max_page} → {len(all_links)} providers"
        )

        # Step 3: Fetch remaining pages
        for page_no in range(2, max_page + 1):
            page_links, _ = _fetch_search_results(session, deployment, page_no)
            all_links.extend(page_links)

            if page_no % 5 == 0:
                logger.info(
                    f"Liquidlogic {deployment.domain}: page {page_no}/{max_page} "
                    f"→ {len(all_links)} providers so far"
                )

        logger.info(
            f"Liquidlogic {deployment.domain}: {len(all_links)} total provider links found"
        )

        # Step 4: Filter out existing providers
        new_links = [
            (pid, href) for pid, href in all_links if pid not in existing_provider_ids
        ]
        logger.info(
            f"Liquidlogic {deployment.domain}: {len(new_links)} new providers to process "
            f"({len(existing_provider_ids)} already exist)"
        )

        # Step 5: Fetch each provider detail page
        yielded = 0
        for pid, href in new_links:
            detail_url = f"{deployment.base_url}{href}"
            result = _fetch_provider_detail(
                session, deployment, lad25cd, pid, detail_url
            )
            yield result
            yielded += 1

            if yielded % 50 == 0:
                logger.info(
                    f"Liquidlogic {deployment.domain}: processed {yielded}/{len(new_links)} providers"
                )

        logger.info(
            f"Liquidlogic {deployment.domain}: yielded {yielded} providers for {lad25cd}"
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_deployment(fis_url: str) -> LiquidlogicDeployment | None:
    parsed = urlparse(fis_url.lower())
    domain = parsed.netloc

    if domain in DEPLOYMENTS:
        return DEPLOYMENTS[domain]

    for key, dep in DEPLOYMENTS.items():
        if key in domain or domain in key:
            return dep

    return None


def _fetch_search_results(
    session: requests.Session,
    deployment: LiquidlogicDeployment,
    page_no: int,
) -> tuple[list[tuple[str, str]], int]:
    """Fetch a single search results page.

    Returns (list of (provider_id, href) tuples, max_page_number).
    """
    url = f"{deployment.base_url}/web/portal/fissearch?category=0&pageNo={page_no}"
    resp = fetch(session, url, timeout=_REQUEST_TIMEOUT, rate_limiter=_rate_limiter)

    soup = BeautifulSoup(resp.text, "html.parser")

    # Extract provider links from search result items
    links: list[tuple[str, str]] = []
    for item in soup.select("div.search-result-item h4 a[href]"):
        href = item.get("href", "")
        if "fisprovider" not in href:
            continue
        # Extract provider hash from ?provider={hash}
        match = re.search(r"provider=([a-f0-9]+)", href)
        if match:
            pid = match.group(1)
            links.append((pid, href))

    # Extract max page number from pagination
    max_page = page_no
    pagination = soup.select_one("div.pagination, ul.pagination, nav.pagination")
    if pagination:
        for a_tag in pagination.find_all("a", href=True):
            page_match = re.search(r"pageNo=(\d+)", a_tag["href"])
            if page_match:
                pn = int(page_match.group(1))
                if pn > max_page:
                    max_page = pn

    return links, max_page


def _fetch_provider_detail(
    session: requests.Session,
    deployment: LiquidlogicDeployment,
    lad25cd: str,
    provider_id: str,
    detail_url: str,
) -> ProviderResult:
    """Fetch and parse a provider detail page."""
    resp = fetch(
        session, detail_url, timeout=_REQUEST_TIMEOUT, rate_limiter=_rate_limiter
    )

    soup = BeautifulSoup(resp.text, "html.parser")
    raw_html = resp.text

    # Provider name from first h4 (or h1/h2/h3)
    name = None
    for tag in ("h4", "h3", "h2", "h1"):
        heading = soup.find(tag)
        if heading:
            name = clean_text(heading.get_text())
            break

    # Parse all tables for key-value pairs
    phone = None
    email = None
    postcode = None
    address_raw = None
    urn = None

    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            th = row.find("th")
            td = row.find("td")
            if not th or not td:
                continue

            label = clean_text(th.get_text()) or ""
            label_lower = label.lower().rstrip(":")

            if label_lower == "telephone":
                phone = _clean_phone(clean_text(td.get_text()))
            elif label_lower == "email":
                # Email may be in an anchor tag
                email_a = td.find("a")
                if email_a:
                    email = clean_text(email_a.get_text())
                else:
                    email = clean_text(td.get_text())
            elif label_lower == "address":
                address_raw = clean_text(td.get_text())
            elif label_lower == "postcode":
                postcode = clean_text(td.get_text())
            elif "ofsted" in label_lower and "urn" in label_lower:
                urn_text = clean_text(td.get_text()) or ""
                urn_match = _URN_RE.search(urn_text)
                if urn_match:
                    urn = urn_match.group()

    # Parse address if present
    addr_parts: dict[str, str | None] = {}
    if address_raw:
        addr_parts = parse_address_parts(address_raw)
        # Don't override postcode from address if we already have one from the Postcode row
        if not postcode and addr_parts.get("postcode"):
            postcode = addr_parts["postcode"]

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
        provider_address_line1=addr_parts.get("address_line1"),
        provider_address_line2=addr_parts.get("address_line2"),
        provider_address_line3=addr_parts.get("address_line3"),
        provider_town=addr_parts.get("town"),
        provider_postcode=postcode,
        provider_urn=urn,
        provider_phone=phone,
        provider_email=email,
        source_url=detail_url,
        raw_html=raw_html,
        scrape_status=status,
    )


def _clean_phone(phone: str | None) -> str | None:
    """Clean phone numbers — strip trailing dots and detect duplicated numbers."""
    if not phone:
        return None

    # Strip trailing dots/periods
    phone = phone.rstrip(".")

    # Detect duplicated numbers (e.g., "0791268881607912688816" → "07912688816")
    # If the string is even-length and both halves are identical, take one half
    if len(phone) >= 10 and len(phone) % 2 == 0:
        half = len(phone) // 2
        if phone[:half] == phone[half:]:
            phone = phone[:half]

    return phone if phone else None
