"""Synergy FIS platform scraper (HTTP-based).

Covers ~58 LAs across 24 Synergy deployments. Uses plain HTTP requests
(requests + BeautifulSoup) instead of Playwright — the ASP.NET WebForms
__doPostBack mechanism works via standard form POST.

Architecture:
  - Each deployment is identified by its domain + app path
  - Multi-LA deployments (Lancashire=12, Derbyshire=8, Worcs=6) are scraped
    once per domain; results are cached and assigned to LAs by postcode
  - Single-LA deployments (Hull, Cornwall, Hounslow, Doncaster, etc.)
    are scraped directly

Search flow:
  1. GET {base}/Enquiries/Search.aspx?searchID={N}
  2. Collect all form fields (hidden inputs, text inputs, selects)
  3. POST with __EVENTTARGET set to the StartNextLinkButton __doPostBack target
  4. Parse result cards (details-card-provider-{N}) for provider IDs and names
  5. Paginate via POST with topPager __doPostBack targets
  6. GET each provider's detail page (Search.aspx?BX=...&AY=...)
  7. Extract name, address, postcode from detail page; store raw_html

Some deployments require a postcode + radius to submit the search form.
These are configured with default_postcode and search_radius fields.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Iterator
from urllib.parse import urljoin

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


# ---------------------------------------------------------------------------
# Per-deployment configuration
# ---------------------------------------------------------------------------


@dataclass
class SynergyDeployment:
    """Configuration for a single Synergy deployment."""

    domain: str
    app_path: str  # e.g. "/SynergyWeb/"
    search_ids: list[int]  # Childcare search ID(s)
    multi_la: bool = False  # True if multiple LAs share this deployment
    website_path: str | None = None  # Sub-site path if different from app_path
    default_postcode: str | None = None  # Required for some sites
    search_radius: int = 50  # Miles — used when default_postcode is set
    skip: bool = False  # True for known-dead deployments


DEPLOYMENTS: dict[str, SynergyDeployment | list[SynergyDeployment]] = {
    "fisonline.lancashire.gov.uk": SynergyDeployment(
        domain="fisonline.lancashire.gov.uk",
        app_path="/SynergyWeb/",
        search_ids=[226],
        multi_la=True,
    ),
    "familyinfoservice.westsussex.gov.uk": SynergyDeployment(
        domain="familyinfoservice.westsussex.gov.uk",
        app_path="/SynergyWeb/",
        search_ids=[151],
        multi_la=True,
        website_path="/SynergyWeb/PublicEnquiry/",
        skip=True,  # Site decommissioned — shows default IIS page
    ),
    "eycportal.worcestershire.gov.uk": SynergyDeployment(
        domain="eycportal.worcestershire.gov.uk",
        app_path="/SynergyWeb_LIVE/",
        # Quick-search IDs bypass the multi-step wizard (566 = full wizard with
        # category picker). Combined these cover all childcare provider types.
        search_ids=[602, 603, 606, 610, 611, 596, 597, 605],
        multi_la=True,
        default_postcode="WR1 1AA",
        search_radius=50,
    ),
    "synergy.hull.gov.uk": SynergyDeployment(
        domain="synergy.hull.gov.uk",
        app_path="/Synergy/Live/SynergyWeb/",
        search_ids=[3],
        default_postcode="HU1 1AA",
        search_radius=50,
    ),
    "fis.cornwall.gov.uk": SynergyDeployment(
        domain="fis.cornwall.gov.uk",
        app_path="/SynergyWeb/",
        search_ids=[4],
        website_path="/SynergyWeb/CornwallFIS/",
    ),
    "fsd.hounslow.gov.uk": SynergyDeployment(
        domain="fsd.hounslow.gov.uk",
        app_path="/SynergyWeb/",
        search_ids=[40],
    ),
    "fis.doncaster.gov.uk": SynergyDeployment(
        domain="fis.doncaster.gov.uk",
        app_path="/Synergy/",
        search_ids=[384, 386, 388],  # childminders, day nurseries, holiday
        skip=True,  # DNS timeout — site appears down
    ),
    "synergy.hackney.gov.uk": SynergyDeployment(
        domain="synergy.hackney.gov.uk",
        app_path="/SynergyWeb/",
        search_ids=[3],
        skip=True,  # Site appears dead — page loads but no search form
    ),
    # Multi-tenant: Waltham Forest, North Somerset, Harrow
    "live.cloud.servelec-synergy.com": [
        SynergyDeployment(
            domain="live.cloud.servelec-synergy.com",
            app_path="/WalthamForest/SynergyWeb/",
            search_ids=[3],
        ),
        SynergyDeployment(
            domain="live.cloud.servelec-synergy.com",
            app_path="/NorthSomerset/Synergy/",
            search_ids=[3],
        ),
        SynergyDeployment(
            domain="live.cloud.servelec-synergy.com",
            app_path="/Harrow/SynergyWeb/",
            search_ids=[41, 44, 46, 47, 48],
        ),
    ],
    # FISH (East Riding) is actually a Synergy deployment
    "fishwebsearch.eastriding.gov.uk": SynergyDeployment(
        domain="fishwebsearch.eastriding.gov.uk",
        app_path="/fishwebsearch/",
        search_ids=[3],
        skip=True,  # Redirects, no searchIDs discoverable
    ),
    # Swindon
    "education.swindon.gov.uk": SynergyDeployment(
        domain="education.swindon.gov.uk",
        app_path="/Synergy/SynergyWeb/",
        search_ids=[3],
    ),
    # Derbyshire — 8 district LAs
    "caya-apps.derbyshire.gov.uk": SynergyDeployment(
        domain="caya-apps.derbyshire.gov.uk",
        app_path="/Synergy/SynergyWeb/",
        search_ids=[
            6,
            13,
            7,
            17,
            37,
        ],  # childcare, 2yr funded, 3/4yr, before/after, holiday
        multi_la=True,
        default_postcode="DE1 1AA",
        search_radius=50,
    ),
    # Warwickshire — 5 district LAs
    "wcc.synergy.hsc.accessacloud.com": SynergyDeployment(
        domain="wcc.synergy.hsc.accessacloud.com",
        app_path="/synergyweb/",
        search_ids=[3],
        multi_la=True,
        skip=True,  # Redirects, no searchIDs discoverable
    ),
    # --- Deployments from Step 5 ---
    "cyp.halton.gov.uk": SynergyDeployment(
        domain="cyp.halton.gov.uk",
        app_path="/Synergy/Live/SynergyWeb/",
        search_ids=[3],
    ),
    "synergy.york.gov.uk": SynergyDeployment(
        domain="synergy.york.gov.uk",
        app_path="/Live/SynergyWeb/",
        search_ids=[48],
    ),
    "remote.derby.gov.uk": SynergyDeployment(
        domain="remote.derby.gov.uk",
        app_path="/Synergy/ECDPublicEnquiry/",
        # Updated IDs from homepage — old IDs (75-81) are stale
        search_ids=[87, 204, 59, 53, 89, 88],
    ),
    "educationportal.herefordshire.gov.uk": SynergyDeployment(
        domain="educationportal.herefordshire.gov.uk",
        app_path="/Synergy/EarlyYears/",
        search_ids=[11, 16, 3],
    ),
    "admissions.medway.gov.uk": SynergyDeployment(
        domain="admissions.medway.gov.uk",
        app_path="/Synergy/",
        # Category-specific IDs work without postcode (ID=15 needs postcode and errors)
        search_ids=[10, 11, 12, 13, 14],
    ),
    "cbc.cloud.servelec-synergy.com": SynergyDeployment(
        domain="cbc.cloud.servelec-synergy.com",
        app_path="/synergyfis/",
        # ID=22 "Childcare" is broadest; 6, 8 add nurseries and holiday schemes
        search_ids=[22, 6, 8, 3],
    ),
    "familyinfoservice.sthelens.gov.uk": SynergyDeployment(
        domain="familyinfoservice.sthelens.gov.uk",
        app_path="/Synergy/",
        search_ids=[1202, 1204],
    ),
    "barnsley.cloud.servelec-synergy.com": SynergyDeployment(
        domain="barnsley.cloud.servelec-synergy.com",
        app_path="/Synergy/",
        search_ids=[6],
    ),
    "www3.dudley.gov.uk": SynergyDeployment(
        domain="www3.dudley.gov.uk",
        app_path="/Synergy/FSD/",
        search_ids=[3],
        skip=True,  # Redirects, no searchIDs discoverable
    ),
    "educationandchildcare.kirklees.gov.uk": SynergyDeployment(
        domain="educationandchildcare.kirklees.gov.uk",
        app_path="/SynergyWebsite_Live/",
        search_ids=[86],
    ),
    "eyproviders.lewisham.gov.uk": SynergyDeployment(
        domain="eyproviders.lewisham.gov.uk",
        app_path="/SynergyWeb/",
        search_ids=[3],
        skip=True,  # DNS failure — site appears down
    ),
}

_USER_AGENT = "BSIL-DataPipeline/1.0 (research; best-start-in-life)"
_REQUEST_TIMEOUT = 20
_rate_limiter = DomainRateLimiter(default_interval=1.5)

# Cache for multi-LA deployments: domain -> list of raw results
_multi_la_cache: dict[str, list[dict]] = {}


class SynergyScraper(BaseScraper):
    @property
    def platform_key(self) -> str:
        return "synergy"

    def scrape_la(
        self,
        lad25cd: str,
        fis_url: str,
        existing_provider_ids: set[str],
        logger: Logger,
    ) -> Iterator[ProviderResult]:
        """Scrape childcare providers from a Synergy deployment."""
        deployment = _get_deployment(fis_url)
        if deployment is None:
            logger.warning(f"No Synergy deployment config for {fis_url} ({lad25cd})")
            yield ProviderResult(
                lad25cd=lad25cd,
                provider_id="__no_deployment_config__",
                scrape_status="unsupported_platform",
                source_url=fis_url,
            )
            return

        if deployment.skip:
            logger.info(f"Skipping dead deployment {deployment.domain}")
            return

        domain = deployment.domain

        # For multi-LA deployments, scrape once and cache
        if deployment.multi_la:
            if domain not in _multi_la_cache:
                logger.info(f"Multi-LA deployment {domain}: scraping all providers")
                _multi_la_cache[domain] = _scrape_deployment(deployment, logger)
                logger.info(
                    f"Cached {len(_multi_la_cache[domain])} providers from {domain}"
                )
            else:
                logger.info(
                    f"Multi-LA deployment {domain}: using cached results "
                    f"({len(_multi_la_cache[domain])} providers)"
                )
            raw_results = _multi_la_cache[domain]
        else:
            logger.info(f"Single-LA deployment {domain}: scraping for {lad25cd}")
            raw_results = _scrape_deployment(deployment, logger)

        # Yield ProviderResults, skipping already-scraped IDs
        for raw in raw_results:
            pid = raw["provider_id"]
            if pid in existing_provider_ids:
                continue
            yield ProviderResult(
                lad25cd=lad25cd,
                provider_id=pid,
                provider_name=raw.get("provider_name"),
                provider_address_line1=raw.get("address_line1"),
                provider_address_line2=raw.get("address_line2"),
                provider_address_line3=raw.get("address_line3"),
                provider_town=raw.get("town"),
                provider_postcode=raw.get("postcode"),
                provider_urn=raw.get("urn"),
                provider_phone=raw.get("phone"),
                provider_email=raw.get("email"),
                source_url=raw.get("source_url"),
                raw_html=raw.get("raw_html"),
                scrape_status=raw.get("scrape_status", "error"),
            )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_deployment(fis_url: str) -> SynergyDeployment | None:
    """Look up the deployment config for a given FIS URL."""
    from urllib.parse import urlparse

    parsed = urlparse(fis_url.lower())
    domain = parsed.netloc
    path = parsed.path

    # Direct match
    if domain in DEPLOYMENTS:
        entry = DEPLOYMENTS[domain]
        if isinstance(entry, list):
            # Multi-tenant: match by app_path prefix
            for dep in entry:
                if path.startswith(dep.app_path.lower()):
                    return dep
            return None
        return entry

    # Partial match (e.g. fis.wolverhampton.gov.uk)
    for key, dep in DEPLOYMENTS.items():
        if isinstance(dep, list):
            continue
        if key in domain or domain in key:
            return dep

    return None


def _scrape_deployment(deployment: SynergyDeployment, logger: Logger) -> list[dict]:
    """Scrape all childcare providers from a Synergy deployment.

    Uses HTTP requests: GET search page → POST form → paginate → GET detail pages.
    """
    enquiry_base = deployment.website_path or deployment.app_path
    enquiry_url_base = f"https://{deployment.domain}{enquiry_base}"

    session = requests.Session()
    session.headers.update({"User-Agent": _USER_AGENT})

    all_results: list[dict] = []
    seen_ids: set[str] = set()

    for search_id in deployment.search_ids:
        search_url = f"{enquiry_url_base}Enquiries/Search.aspx?searchID={search_id}"
        logger.info(f"Trying search URL: {search_url}")

        resp = fetch(
            session, search_url, timeout=_REQUEST_TIMEOUT, rate_limiter=_rate_limiter
        )

        # Check if we were redirected away (stale searchID)
        if "Search.aspx" not in resp.url:
            logger.warning(f"Redirected to {resp.url} — searchID={search_id} is stale")
            # Try to discover valid search IDs from homepage
            discovered = _discover_search_ids(resp.text, logger)
            if discovered:
                logger.info(f"Discovered search IDs: {discovered}")
                found_valid = False
                for disc_id in discovered:
                    if disc_id in deployment.search_ids:
                        continue  # Already tried or will try
                    disc_url = (
                        f"{enquiry_url_base}Enquiries/Search.aspx?searchID={disc_id}"
                    )
                    resp = fetch(
                        session,
                        disc_url,
                        timeout=_REQUEST_TIMEOUT,
                        rate_limiter=_rate_limiter,
                    )
                    if "Search.aspx" in resp.url:
                        logger.info(f"Using discovered searchID={disc_id}")
                        found_valid = True
                        break
                if not found_valid:
                    continue
            else:
                continue

        # Parse the search form
        soup = BeautifulSoup(resp.text, "html.parser")
        form = soup.find("form")
        if not form:
            logger.warning(f"No form found on {resp.url}")
            continue

        # Find the search button
        btn = soup.find(
            "a",
            id=lambda x: x and "StartNextLinkButton" in str(x),
        )
        if not btn:
            logger.warning(f"No search button found on {resp.url}")
            continue

        # Extract __doPostBack event target from button href
        href = btn.get("href", "")
        target_match = re.search(r"__doPostBack\('([^']+)'", href)
        if not target_match:
            logger.warning(f"Cannot extract __doPostBack target from {href}")
            continue

        event_target = target_match.group(1)

        # Submit the search form, advancing through wizard steps
        soup2, results_url = _submit_wizard(
            session, resp.url, soup, event_target, deployment, logger
        )
        if soup2 is None:
            continue

        # Check for results
        cards = soup2.find_all(id=re.compile(r"^details-card-provider-\d+$"))
        if not cards:
            logger.warning(f"No results after search on {deployment.domain}")
            continue

        # Parse total results count
        text = soup2.get_text()
        total_match = re.search(r"\[(\d+)\s*Result", text)
        total = int(total_match.group(1)) if total_match else "?"
        logger.info(
            f"Search {search_id} on {deployment.domain}: "
            f"{len(cards)} cards, {total} total results"
        )

        # Collect all listing entries from all pages
        listing_entries = _collect_all_pages(session, results_url, soup2, logger)
        logger.info(
            f"Collected {len(listing_entries)} listing entries from {deployment.domain}"
        )

        # Fetch detail pages
        for i, entry in enumerate(listing_entries):
            pid = entry["provider_id"]
            if pid in seen_ids:
                continue
            seen_ids.add(pid)

            detail_url = entry.get("detail_url")
            if not detail_url:
                all_results.append(
                    {
                        "provider_id": pid,
                        "provider_name": entry.get("name"),
                        "scrape_status": "partial",
                        "source_url": results_url,
                    }
                )
                continue

            result = _scrape_detail_page(session, pid, detail_url, logger)

            # Fill in name from listing if detail page didn't have it
            if not result.get("provider_name") and entry.get("name"):
                result["provider_name"] = entry["name"]

            all_results.append(result)

            if (i + 1) % 50 == 0:
                logger.info(
                    f"Scraped {i + 1}/{len(listing_entries)} detail pages "
                    f"from {deployment.domain}"
                )

    return all_results


def _discover_search_ids(html: str, logger: Logger) -> list[int]:
    """Discover valid search IDs from a Synergy homepage."""
    search_ids: list[int] = []
    for match in re.finditer(r"searchID=(\d+)", html):
        sid = int(match.group(1))
        if sid not in search_ids:
            search_ids.append(sid)
    return search_ids


def _submit_wizard(
    session: requests.Session,
    form_url: str,
    soup: BeautifulSoup,
    event_target: str,
    deployment: SynergyDeployment,
    logger: Logger,
) -> tuple[BeautifulSoup | None, str]:
    """Submit the search wizard, advancing through multiple steps if needed.

    ASP.NET Synergy wizards may have 1-3 steps:
      Step 1: category selection / postcode entry → StartNextLinkButton
      Step 2: additional filters → StepNextLinkButton
      Step 3: more filters → FinishLinkButton or StepNextLinkButton
      → Results page with details-card-provider cards

    Returns (results_soup, final_url) or (None, form_url) if submission failed.
    """
    form = soup.find("form")
    if not form:
        return None, form_url

    # Initial submission — try without checkboxes first
    form_data = _collect_form_data(form)
    form_data["__EVENTTARGET"] = event_target
    form_data["__EVENTARGUMENT"] = ""

    if deployment.default_postcode:
        _fill_postcode_fields(form, form_data, deployment)

    resp = fetch(
        session,
        form_url,
        timeout=_REQUEST_TIMEOUT,
        rate_limiter=_rate_limiter,
        method="POST",
        data=form_data,
    )

    if "Error" in resp.url or "500" in resp.url:
        logger.warning(f"Search POST returned error page: {resp.url}")
        return None, form_url

    soup2 = BeautifulSoup(resp.text, "html.parser")

    # Check if we already have results
    cards = soup2.find_all(id=re.compile(r"^details-card-provider-\d+$"))
    if cards:
        return soup2, resp.url

    # Retry with all checkboxes checked if:
    # - explicit validation errors on the page, OR
    # - the form has checkboxes (some sites require them without showing errors)
    has_checkboxes = bool(form.find_all("input", {"type": "checkbox"}))
    needs_retry = _has_validation_errors(soup2) or has_checkboxes

    if needs_retry:
        logger.info(
            f"No results on {deployment.domain}, retrying with all checkboxes checked"
        )
        form_data = _collect_form_data(form, include_checkboxes=True)
        form_data["__EVENTTARGET"] = event_target
        form_data["__EVENTARGUMENT"] = ""
        if deployment.default_postcode:
            _fill_postcode_fields(form, form_data, deployment)

        resp = fetch(
            session,
            form_url,
            timeout=_REQUEST_TIMEOUT,
            rate_limiter=_rate_limiter,
            method="POST",
            data=form_data,
        )

        if "Error" in resp.url or "500" in resp.url:
            return None, form_url

        soup2 = BeautifulSoup(resp.text, "html.parser")
        cards = soup2.find_all(id=re.compile(r"^details-card-provider-\d+$"))
        if cards:
            return soup2, resp.url

    # Advance through wizard steps (max 5 steps to avoid infinite loops)
    for step in range(5):
        next_btn = _find_wizard_next_button(soup2)
        if not next_btn:
            # Log what we see on the page to help debug
            title = soup2.find("title")
            step_text = ""
            for h in soup2.find_all(["h1", "h2", "h3"]):
                t = clean_text(h.get_text())
                if t:
                    step_text = t
                    break
            logger.info(
                f"No next button found on {deployment.domain} "
                f"(title: {clean_text(title.get_text()) if title else '?'}, "
                f"heading: {step_text})"
            )
            break

        logger.info(
            f"Advancing wizard step {step + 2} on {deployment.domain} "
            f"(button: {next_btn})"
        )

        form2 = soup2.find("form")
        if not form2:
            break

        form_data2 = _collect_form_data(form2, include_checkboxes=True)
        form_data2["__EVENTTARGET"] = next_btn
        form_data2["__EVENTARGUMENT"] = ""

        # Also fill postcode fields on subsequent steps in case they appear
        if deployment.default_postcode:
            _fill_postcode_fields(form2, form_data2, deployment)

        resp = fetch(
            session,
            resp.url,
            timeout=_REQUEST_TIMEOUT,
            rate_limiter=_rate_limiter,
            method="POST",
            data=form_data2,
        )

        if "Error" in resp.url or "500" in resp.url:
            logger.warning(f"Wizard step returned error: {resp.url}")
            break

        soup2 = BeautifulSoup(resp.text, "html.parser")
        cards = soup2.find_all(id=re.compile(r"^details-card-provider-\d+$"))
        if cards:
            return soup2, resp.url

    has_cards = soup2.find_all(id=re.compile(r"^details-card-provider-\d+$"))
    return (soup2 if has_cards else None), resp.url


def _find_wizard_next_button(soup: BeautifulSoup) -> str | None:
    """Find the __doPostBack event target for the next wizard step button.

    Looks for StepNextLinkButton, FinishLinkButton, or similar.
    """
    for btn_pattern in [
        "StepNextLinkButton",
        "FinishLinkButton",
        "FinishNavigationTemplateContainerID",
    ]:
        btn = soup.find(
            "a",
            id=lambda x: x and btn_pattern in str(x),
        )
        if btn:
            href = btn.get("href", "")
            match = re.search(r"__doPostBack\('([^']+)'", href)
            if match:
                return match.group(1)
    return None


def _collect_form_data(form, include_checkboxes: bool = False) -> dict[str, str]:
    """Collect all form field values from a BeautifulSoup form element.

    Includes hidden inputs, text inputs, and select defaults.
    Checkboxes are excluded by default (unchecked = absent, to search
    without filters). Set include_checkboxes=True to check all checkboxes
    (used when validation requires them).
    """
    data: dict[str, str] = {}

    for inp in form.find_all("input", {"type": "hidden"}):
        name = inp.get("name")
        if name:
            data[name] = inp.get("value", "")

    for inp in form.find_all("input", {"type": "text"}):
        name = inp.get("name")
        if name:
            data[name] = inp.get("value", "")

    for sel in form.find_all("select"):
        name = sel.get("name")
        if name:
            selected = sel.find("option", selected=True)
            first = sel.find("option")
            opt = selected or first
            data[name] = opt.get("value", "") if opt else ""

    if include_checkboxes:
        for inp in form.find_all("input", {"type": "checkbox"}):
            name = inp.get("name")
            if name:
                val = inp.get("value", "on")
                data[name] = val

    return data


def _fill_postcode_fields(
    form,
    form_data: dict[str, str],
    deployment: SynergyDeployment,
) -> None:
    """Fill in postcode and radius text fields for sites that require them."""
    for name in form_data:
        name_lower = name.lower()
        if "_rpc" in name_lower or "postcode" in name_lower:
            form_data[name] = deployment.default_postcode or ""
        elif "_rr" in name_lower or "range" in name_lower or "radius" in name_lower:
            form_data[name] = str(deployment.search_radius)


def _has_validation_errors(soup: BeautifulSoup) -> bool:
    """Check if the page shows ASP.NET validation error messages."""
    # Check for explicit error/warning elements
    for el in soup.find_all(class_=re.compile(r"error|alert|warning")):
        text = el.get_text().strip()
        if "fill in" in text.lower() or "required" in text.lower():
            return True

    # Check for validation summary
    for el in soup.find_all(class_=re.compile(r"validation")):
        text = el.get_text().strip()
        if "please" in text.lower() or "tick" in text.lower():
            return True

    # Check page text for common validation messages
    page_text = soup.get_text().lower()
    validation_phrases = [
        "please fill in all fields",
        "please tick this box",
        "please enter your post code",
        "field is required",
    ]
    for phrase in validation_phrases:
        if phrase in page_text:
            return True

    return False


def _collect_all_pages(
    session: requests.Session,
    form_url: str,
    first_page_soup: BeautifulSoup,
    logger: Logger,
) -> list[dict]:
    """Parse result cards from all pages."""
    all_entries: list[dict] = []
    soup = first_page_soup
    page_num = 1

    while True:
        entries = _parse_result_cards(soup, form_url)
        all_entries.extend(entries)

        if page_num == 1:
            logger.info(f"Page 1: {len(entries)} entries")

        # Find next page link
        next_target = _find_next_page_target(soup, page_num)
        if not next_target:
            break

        page_num += 1
        if page_num > 500:
            logger.warning("Hit pagination safety limit (500 pages)")
            break

        # POST to get next page
        form = soup.find("form")
        if not form:
            break

        form_data = _collect_form_data(form)
        form_data["__EVENTTARGET"] = next_target
        form_data["__EVENTARGUMENT"] = ""

        resp = fetch(
            session,
            form_url,
            timeout=_REQUEST_TIMEOUT,
            rate_limiter=_rate_limiter,
            method="POST",
            data=form_data,
        )

        if "Error" in resp.url or "500" in resp.url:
            logger.warning(f"Pagination POST returned error on page {page_num}")
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        new_cards = soup.find_all(id=re.compile(r"^details-card-provider-\d+$"))
        if not new_cards:
            break

        if page_num % 20 == 0:
            logger.info(f"Page {page_num}: total {len(all_entries)} entries so far")

    return all_entries


def _parse_result_cards(soup: BeautifulSoup, base_url: str) -> list[dict]:
    """Extract provider entries from result cards on a page.

    Each card is <div id="details-card-provider-{N}"> with:
    - Provider name in h2 > a.web-hyperlink (detail link)
    - Provider ID from addProviderToBasketById({id}, ...) in basket button onclick
    - Detail URL from the web-hyperlink href (Search.aspx?BX=...&AY=...)
    """
    entries: list[dict] = []

    cards = soup.find_all(id=re.compile(r"^details-card-provider-\d+$"))
    for card in cards:
        entry: dict = {}

        # Provider name and detail URL from the main link
        name_el = card.find("a", class_="web-hyperlink")
        if name_el:
            entry["name"] = clean_text(name_el.get_text())
            href = name_el.get("href", "")
            if href and "BX=" in href:
                entry["detail_url"] = urljoin(base_url, href)

        # Provider ID from basket button onclick
        basket_btn = card.find("button", class_=re.compile(r"basket-button-"))
        if basket_btn:
            onclick = basket_btn.get("onclick", "")
            pid_match = re.search(r"addProviderToBasketById\((\d+)", onclick)
            if pid_match:
                entry["provider_id"] = pid_match.group(1)

        # Fallback: extract ID from detail link ID attribute
        if "provider_id" not in entry:
            detail_link = card.find("a", id=re.compile(r"detailsLink\d+"))
            if detail_link:
                link_id = detail_link.get("id", "")
                num = re.search(r"(\d+)", link_id)
                if num:
                    # Use card number as ID — less stable but better than nothing
                    entry["provider_id"] = f"card_{num.group(1)}"

        if "provider_id" not in entry:
            continue

        entries.append(entry)

    return entries


def _find_next_page_target(soup: BeautifulSoup, current_page: int) -> str | None:
    """Find the __doPostBack event target for the next page.

    Pagination links use IDs like topPager_2, topPager_3, etc.
    Also looks for a "next" arrow link (topPager_ctl03).
    """
    next_page = current_page + 1

    # Try direct page number link
    for a in soup.find_all("a", id=re.compile(r"topPager")):
        a_id = a.get("id", "")
        href = a.get("href", "")
        # Match topPager_{N} where N is the next page
        if a_id.endswith(f"_{next_page}") and "__doPostBack" in href:
            target_match = re.search(r"__doPostBack\('([^']+)'", href)
            if target_match:
                return target_match.group(1)

    # Try the "next" arrow link (ctl03 pattern)
    for a in soup.find_all("a", id=re.compile(r"topPager.*ctl03")):
        href = a.get("href", "")
        if "__doPostBack" in href:
            target_match = re.search(r"__doPostBack\('([^']+)'", href)
            if target_match:
                return target_match.group(1)

    return None


def _scrape_detail_page(
    session: requests.Session,
    provider_id: str,
    detail_url: str,
    logger: Logger,
) -> dict:
    """Fetch and parse a Synergy provider detail page."""
    result: dict = {
        "provider_id": provider_id,
        "source_url": detail_url,
        "scrape_status": "error",
    }

    resp = fetch(
        session, detail_url, timeout=_REQUEST_TIMEOUT, rate_limiter=_rate_limiter
    )

    html = resp.text
    result["raw_html"] = html
    soup = BeautifulSoup(html, "html.parser")

    # Provider name — from card header or h1
    name = None
    header = soup.find("div", class_="card-header")
    if header:
        # Name is in the first heading within the card header
        name_el = header.find(["h1", "h2", "h3"])
        if name_el:
            raw_name = clean_text(name_el.get_text())
            if raw_name:
                name = raw_name

    if not name:
        h1 = soup.find("h1")
        if h1:
            name = clean_text(h1.get_text())

    if name:
        result["provider_name"] = name

    # Extract address from eyo-data-row structure
    _extract_address_from_rows(soup, result)

    # Fallback: extract from dt/dd pairs
    if not result.get("postcode"):
        _extract_address_from_dl(soup, result)

    # Final fallback: regex postcode from page text
    if not result.get("postcode"):
        text = soup.get_text()
        pc_match = POSTCODE_RE.search(text)
        if pc_match:
            result["postcode"] = pc_match.group(0).upper()

    # Determine scrape status
    has_name = bool(result.get("provider_name"))
    has_postcode = bool(result.get("postcode"))

    if has_name and has_postcode:
        result["scrape_status"] = "success"
    elif has_name or has_postcode:
        result["scrape_status"] = "partial"

    return result


def _extract_address_from_rows(soup: BeautifulSoup, result: dict) -> None:
    """Extract address and contact fields from eyo-data-label/field pairs.

    Detail pages use Bootstrap rows with labeled spans:
      <div class="row ...">
        <span class="... eyo-data-label">Address:</span>
        <span class="... eyo-data-field">street,<br/>town,postcode</span>
      </div>

    Listing cards use a similar pattern with div.eyo-data-row containers.
    This function handles both layouts by finding all eyo-data-label elements.
    """
    for label_el in soup.find_all(class_="eyo-data-label"):
        label = clean_text(label_el.get_text()) or ""
        label_lower = label.lower().rstrip(":")

        # Find the corresponding field — sibling or within same parent row
        row = label_el.parent
        field_el = row.find(class_="eyo-data-field") if row else None
        if not field_el:
            field_el = label_el.find_next_sibling(class_="eyo-data-field")
        if not field_el:
            continue

        if label_lower in ("address", "address / area", "location"):
            # Use get_text with newline separator — handles mixed
            # <br> and <br/> tags reliably (html.parser nests them
            # inconsistently). Then clean up commas and empty lines.
            raw = field_el.get_text(separator="\n")
            lines = [
                p.strip().rstrip(",") for p in raw.split("\n") if p.strip().rstrip(",")
            ]
            # If we got a single line with commas, split on commas
            if len(lines) == 1 and "," in lines[0]:
                lines = [p.strip() for p in lines[0].split(",") if p.strip()]
            if lines:
                _parse_address_lines(lines, result)
        elif label_lower == "postcode" or label_lower == "post code":
            pc_text = clean_text(field_el.get_text())
            if pc_text and POSTCODE_RE.search(pc_text):
                result["postcode"] = POSTCODE_RE.search(pc_text).group(0).upper()
        elif label_lower in ("tel", "telephone", "mobile no.", "mobile"):
            phone = clean_text(field_el.get_text())
            if phone and phone.lower() not in ("not available", "-"):
                if not result.get("phone"):
                    result["phone"] = phone
        elif "email" in label_lower:
            email_el = field_el.find("a", href=re.compile(r"^mailto:", re.IGNORECASE))
            if email_el:
                email = clean_text(email_el.get_text())
                if email and "@" in email:
                    result["email"] = email.lower()
            else:
                # Fallback: check text for email pattern
                text = clean_text(field_el.get_text())
                if text and "@" in text:
                    result["email"] = text.lower()
        elif "ofsted" in label_lower and "reference" in label_lower:
            urn = clean_text(field_el.get_text())
            if urn and urn.lower() not in ("not available", "-"):
                # URN may be numeric (e.g. 123456) or have prefix (e.g. EY469540)
                urn_match = re.search(r"[A-Z]{0,3}\d{5,}", urn)
                if urn_match:
                    result["urn"] = urn_match.group(0)


def _extract_address_from_dl(soup: BeautifulSoup, result: dict) -> None:
    """Fallback: extract address from dt/dd pairs."""
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
        elif dt_lower == "address":
            _parse_address_into_result(dd_text, result)
        elif "town" in dt_lower:
            result["town"] = dd_text


def _extract_br_lines(element) -> list[str]:
    """Extract text lines from an element with <br> separators."""
    lines: list[str] = []
    current = ""

    for child in element.children:
        if child.name == "br":
            text = clean_text(current)
            if text:
                lines.append(text)
            current = ""
        elif hasattr(child, "get_text"):
            current += child.get_text()
        else:
            current += str(child)

    text = clean_text(current)
    if text:
        lines.append(text)

    return lines


def _parse_address_lines(lines: list[str], result: dict) -> None:
    """Parse br-separated address lines into structured fields.

    Lines typically:
      Street Name,
      Area,
      Town,Postcode

    The last line may contain "Town,Postcode" concatenated.
    """
    if not lines:
        return

    # Check if last line contains a postcode
    last = lines[-1]
    pc_match = POSTCODE_RE.search(last)
    if pc_match:
        result["postcode"] = pc_match.group(0).upper()
        # Remove postcode from last line, leaving town
        remainder = last[: pc_match.start()].rstrip(", ")
        if remainder:
            lines[-1] = remainder
        else:
            lines = lines[:-1]

    # Town is the last remaining line
    if lines:
        result["town"] = lines[-1].rstrip(",")
        lines = lines[:-1]

    # Address lines
    if len(lines) >= 1:
        result["address_line1"] = lines[0].rstrip(",")
    if len(lines) >= 2:
        result["address_line2"] = lines[1].rstrip(",")
    if len(lines) >= 3:
        result["address_line3"] = ", ".join(ln.rstrip(",") for ln in lines[2:])


def _parse_address_into_result(address_text: str, result: dict) -> None:
    """Parse a free-text comma-separated address into structured fields."""
    parts = re.split(r"[,\n]", address_text)
    parts = [clean_text(p) for p in parts if clean_text(p)]

    if not parts:
        return

    # Check if last part is a postcode
    if parts and POSTCODE_RE.search(parts[-1] or ""):
        result["postcode"] = (parts[-1] or "").strip().upper()
        parts = parts[:-1]

    # Town is the last remaining
    if parts:
        result["town"] = parts[-1]
        parts = parts[:-1]

    if len(parts) >= 1:
        result["address_line1"] = parts[0]
    if len(parts) >= 2:
        result["address_line2"] = parts[1]
    if len(parts) >= 3:
        result["address_line3"] = ", ".join(parts[2:])
