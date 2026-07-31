"""OpenObjects kb5 platform extractor.

Extracts all fields from kb5 detail page HTML stored in raw_html.
Detail pages have <section class="field_section"> containers with
<dl>/<dt>/<dd> pairs for each data section.
"""

from __future__ import annotations

import re
from typing import Any

from bsil_pipeline.extractors.base import (
    BaseExtractor,
    ExtractedProvider,
    classify_provider_types,
    clean_text,
    extract_dt_dd,
    extract_email_from_soup,
    extract_phone_from_soup,
    extract_postcode,
    extract_postcode_district,
    is_council_email,
    parse_soup,
    validate_email,
)

# Known KB5 portal page titles that contaminate provider names.
_PORTAL_NAMES = {
    "cambridgeshire online",
    "childcare online",
    "childcare & family information",
    "family information service",
    "family information directory",
    "family services directory",
    "families information service",
    "family information",
    "childcare finder",
    "fis online",
    "early years & childcare",
    "childcare search",
    "childcare directory",
    "peterborough information network",
    "reading services guide",
    "dorset family information directory",
    "county durham's families information service",
    "dorset fid",
}

# Regex to strip phone label suffixes like "Fax: 01234 567891"
_PHONE_LABEL_RE = re.compile(
    r"\b(?:Fax|fax|FAX|Mobile|mobile|Tel|tel)\s*:\s*", re.IGNORECASE
)

# UK phone number pattern: starts with 0, followed by digits/spaces/hyphens, 10-11 digits total
_UK_PHONE_RE = re.compile(r"\b0\d[\d\s\-]{7,13}\d\b")


def _is_portal_name(name: str, dynamic_portal: str | None = None) -> bool:
    """Check if a name matches a known KB5 portal name.

    Checks both the hardcoded _PORTAL_NAMES set and an optional
    dynamically-detected portal name from <meta name="application-name">.
    """
    lower = name.strip().lower()
    if lower in _PORTAL_NAMES:
        return True
    if dynamic_portal and lower == dynamic_portal.strip().lower():
        return True
    return False


def _detect_portal_name(soup: Any) -> str | None:
    """Detect the KB5 portal name from <meta name="application-name">.

    This meta tag is present on all KB5 pages and contains the exact
    portal/directory name (e.g. "Glosfamilies Directory").
    """
    meta = soup.find("meta", attrs={"name": "application-name"})
    if meta:
        content = meta.get("content", "").strip()
        return content if content else None
    return None


def _extract_provider_name(
    soup: Any,
    provider_name: str | None,
    warnings: list[str],
) -> str | None:
    """Extract provider name, avoiding KB5 portal name contamination.

    Strategy:
    0. Detect portal name dynamically from <meta name="application-name">
    1. Parse <title> tag, split on | or \xa0|\xa0, take the non-portal part
    2. Find second <h1> (skip navbar h1)
    3. Fall back to first <h1> if not a portal name
    4. Fall back to provider_name from scrape_results
    """
    dynamic_portal = _detect_portal_name(soup)

    # Try <title> tag first
    title_tag = soup.find("title")
    if title_tag:
        title_text = clean_text(title_tag.get_text())
        if title_text:
            # Split on | (with optional surrounding whitespace/nbsp)
            parts = re.split(r"\s*\|\s*|\s*\xa0\|\xa0\s*", title_text)
            # Filter out known portal names and empty parts
            non_portal = [
                p.strip()
                for p in parts
                if p.strip() and not _is_portal_name(p.strip(), dynamic_portal)
            ]
            if non_portal:
                return non_portal[0]

    # Try second <h1> or h1 inside #hit-header
    hit_header = soup.find(id="hit-header")
    if hit_header:
        h1_in_header = hit_header.find("h1")
        if h1_in_header:
            name = clean_text(h1_in_header.get_text())
            if name and not _is_portal_name(name, dynamic_portal):
                return name

    all_h1s = soup.find_all("h1")
    if len(all_h1s) >= 2:
        name = clean_text(all_h1s[1].get_text())
        if name and not _is_portal_name(name, dynamic_portal):
            return name

    # Fall back to first h1 if not a portal name
    if all_h1s:
        name = clean_text(all_h1s[0].get_text())
        if name and not _is_portal_name(name, dynamic_portal):
            return name

    # Fall back to scrape_results provider_name
    if provider_name:
        if _is_portal_name(provider_name, dynamic_portal):
            warnings.append("provider_name_contaminated")
        return provider_name

    # Last resort: use first h1 even if it's a portal name
    if all_h1s:
        name = clean_text(all_h1s[0].get_text())
        if name:
            warnings.append("provider_name_contaminated")
            return name

    return None


def _split_digit_chunks(digits: str) -> list[str]:
    """Split a digit string into 11- or 10-digit UK phone numbers starting with 0."""
    results: list[str] = []
    pos = 0
    while pos < len(digits):
        if digits[pos] == "0":
            # Prefer 11-digit (most UK numbers) then 10-digit
            for length in (11, 10):
                if pos + length <= len(digits):
                    results.append(digits[pos : pos + length])
                    pos += length
                    break
            else:
                pos += 1
        else:
            pos += 1
    return results


def _parse_phone_numbers(raw: str) -> list[str]:
    """Extract and deduplicate UK phone numbers from a raw string.

    Handles:
    - Responsive spans with duplicated numbers
    - <br/> separated numbers (concatenated without spaces)
    - Annotated numbers like "0118 937 3283 (Admin Officer)"
    - Label prefixes like "Helpline: 0161 214 4590"
    """
    if not raw:
        return []

    # Reject non-phone text
    if re.match(r"^[a-zA-Z\s]+$", raw.strip()):
        return []

    # Find all UK phone patterns
    matches = _UK_PHONE_RE.findall(raw)

    # Check if any match has too many digits — indicates concatenation
    has_concat = any(len(re.sub(r"\D", "", m)) > 11 for m in matches)

    results: list[str] = []
    if has_concat:
        # Concatenated numbers (e.g. "0115 84119560746 6574794")
        # Fall back to digit chunking on the full raw string
        all_digits = re.sub(r"\D", "", raw)
        results = _split_digit_chunks(all_digits)
    else:
        for m in matches:
            results.append(m.strip())

    if not results:
        # Fallback: strip everything to digits and try chunking
        all_digits = re.sub(r"\D", "", raw)
        results = _split_digit_chunks(all_digits)

    if not results:
        return []

    # Deduplicate by normalised digit form
    seen: set[str] = set()
    unique: list[str] = []
    for r in results:
        normalised = re.sub(r"\D", "", r)
        if normalised not in seen:
            seen.add(normalised)
            unique.append(r)

    return unique


class OpenObjectsExtractor(BaseExtractor):
    @property
    def platform_key(self) -> str:
        return "openobjects_kb5"

    def extract(
        self,
        lad25cd: str,
        provider_id: str,
        raw_html: str | None,
        raw_json: str | None,
        metadata_json: str | None,
        provider_name: str | None,
    ) -> ExtractedProvider:
        warnings: list[str] = []
        data: dict[str, Any] = {}
        source_labels: list[str] = []

        if not raw_html:
            warnings.append("no raw_html available")
            return ExtractedProvider(
                lad25cd=lad25cd,
                provider_id=provider_id,
                extracted_data={"provider_name": provider_name}
                if provider_name
                else {},
                extraction_warnings=warnings,
            )

        soup = parse_soup(raw_html)

        # Provider name — use multi-strategy extraction to avoid KB5 portal
        # name contamination (title tag → second h1 → first h1 → scrape_results).
        data["provider_name"] = _extract_provider_name(soup, provider_name, warnings)

        # Extract ALL dt/dd pairs from ALL field_section containers
        all_pairs: dict[str, str] = {}
        sections = soup.find_all(class_=re.compile(r"field_section"))
        if sections:
            for section in sections:
                pairs = extract_dt_dd(soup, scope=section)
                for label, value in pairs.items():
                    all_pairs[label] = value
        else:
            # Fallback: extract all dt/dd from the entire page
            all_pairs = extract_dt_dd(soup)

        # Map known labels to canonical keys
        _LABEL_MAP = {
            "name": "venue_name",
            "address": "_address_raw",
            "postcode": "postcode",
            "telephone": "phone",
            "phone": "phone",
            "contact telephone": "phone",
            "email": "email",
            "e-mail": "email",
            "contact email": "email",
            "email address": "email",
            "website": "website",
            "fax": "fax",
            "type of childcare": "provider_type",
            "childcare type": "provider_type",
            "type of provision": "provider_type",
            "type": "provider_type",
            "provider type": "provider_type",
            "ofsted urn": "ofsted_urn",
            "ofsted unique reference number": "ofsted_urn",
            "urn": "ofsted_urn",
            "ofsted rating": "ofsted_rating",
            "ofsted report": "ofsted_report_url",
            "age range": "age_range",
            "age ranges": "age_range",
            "age groups": "age_range",
            "available to age groups": "age_range",
            "ages catered for": "age_range",
            "number of places": "places_total",
            "vacancies": "places_available",
            "opening times": "opening_hours_raw",
            "opening hours": "opening_hours_raw",
            "hours": "opening_hours_raw",
            "session times": "session_types_raw",
            "fees": "fees_raw",
            "cost": "fees_raw",
            "free entitlement": "funded_info",
            "funded places": "funded_info",
            "2 year old funding": "funded_2yr",
            "3 and 4 year old funding": "funded_3_4yr",
            "30 hours": "funded_30hrs",
            "special educational needs": "send_provision",
            "sen provision": "send_provision",
            "send": "send_provision",
            "languages": "languages_raw",
            "description": "description",
            "about": "description",
            "facilities": "facilities_raw",
            "pick up from school": "school_pickups_raw",
            "schools collected from": "school_pickups_raw",
            "term time only": "term_time_only",
            "weeks open": "weeks_per_year",
            "district": "district",
            "ward": "ward",
        }

        extra: dict[str, str] = {}
        for label, value in all_pairs.items():
            canonical = _LABEL_MAP.get(label)
            if canonical:
                data[canonical] = value
            else:
                extra[label] = value

        # Clean postcode — remove appended link text (e.g., "GL4 5BQGet directions").
        # Fall back to district-only (e.g. "BS15") when no full postcode available.
        if data.get("postcode"):
            raw_pc = data["postcode"]
            data["postcode"] = extract_postcode(raw_pc) or extract_postcode_district(
                raw_pc
            )

        # Parse phone numbers — extract, deduplicate, split into primary/secondary
        if data.get("phone"):
            phones = _parse_phone_numbers(data["phone"])
            if phones:
                data["phone"] = phones[0]
                if len(phones) >= 2:
                    data["phone_secondary"] = phones[1]
                if len(phones) >= 3:
                    extra["phone_additional"] = ", ".join(phones[2:])
            else:
                # No valid phone numbers found (e.g. "visit website for more information")
                del data["phone"]

        # Remove "undefined" descriptions (JavaScript artifacts)
        if (
            data.get("description")
            and data["description"].strip().lower() == "undefined"
        ):
            data["description"] = None

        # Parse address — re-extract address <dd> directly to preserve line breaks.
        # extract_dt_dd applies clean_text which collapses newlines, causing adjacent
        # spans (e.g. "Tree Rise" + "Hanham") to merge without a separator.
        data.pop("_address_raw", None)
        addr_raw = None
        for dt in soup.find_all("dt"):
            if dt.get_text(strip=True).lower().rstrip(":").strip() == "address":
                dd = dt.find_next_sibling("dd")
                if dd:
                    addr_raw = dd.get_text(separator="\n")
                break
        if addr_raw:
            lines = [p.strip() for p in re.split(r"[,\n]", addr_raw) if p.strip()]
            pc = extract_postcode(addr_raw)
            if pc is None and not data.get("postcode"):
                pc = extract_postcode_district(addr_raw)
            if pc and not data.get("postcode"):
                data["postcode"] = pc
                lines = [ln for ln in lines if extract_postcode(ln) != pc]
            if lines:
                data["address_line1"] = lines[0] if len(lines) >= 1 else None
                data["address_line2"] = lines[1] if len(lines) >= 2 else None
                if len(lines) >= 4:
                    data["town"] = lines[-1]
                    data["address_line3"] = ", ".join(lines[2:-1])
                elif len(lines) >= 3:
                    data["town"] = lines[-1]

        # Website — re-extract from <a href> inside the <dd> element.
        # extract_dt_dd uses get_text() which gives the *display text* of links,
        # but kb5 sites often show a truncated URL as link text (e.g. "https://www.facebook.com/")
        # while the href has the full URL (e.g. "https://www.facebook.com/profile.php?id=12345").
        for dt in soup.find_all("dt"):
            if dt.get_text(strip=True).lower().rstrip(":").strip() == "website":
                dd = dt.find_next_sibling("dd")
                if dd:
                    a_tag = dd.find("a", href=True)
                    if a_tag:
                        data["website"] = a_tag["href"].strip()
                break

        # Email/phone fallback from links
        if not data.get("email"):
            email = extract_email_from_soup(soup)
            if email:
                data["email"] = email
        if not data.get("phone"):
            phone = extract_phone_from_soup(soup)
            if phone:
                data["phone"] = phone

        # Validate email format and filter council FIS inboxes
        if data.get("email"):
            email_val = data["email"]
            if not validate_email(email_val):
                extra["invalid_email"] = email_val
                del data["email"]
            elif is_council_email(email_val):
                extra["council_email"] = email_val
                del data["email"]

        if extra:
            data["extra"] = extra

        # Classification from provider_type field
        pt = data.get("provider_type", "")
        if pt:
            for label in re.split(r"[,/;]", pt):
                label = label.strip()
                if label:
                    source_labels.append(label)

        classification = classify_provider_types(source_labels)

        return ExtractedProvider(
            lad25cd=lad25cd,
            provider_id=provider_id,
            extracted_data=data,
            classification=classification,
            source_classification=source_labels,
            extraction_warnings=warnings,
        )
