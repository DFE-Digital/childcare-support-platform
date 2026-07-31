"""Synergy FIS platform extractor.

Extracts all fields from Synergy detail page HTML stored in raw_html.
Detail pages use eyo-data-label / eyo-data-field span pairs, plus
fallback dt/dd pairs for some deployments.
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
    parse_soup,
    validate_email,
)


def _extract_eyo_pairs(soup) -> dict[str, str]:
    """Extract eyo-data-label / eyo-data-field pairs from Synergy HTML.

    Matches ANY element with the eyo-data-label class (not just <span>),
    mirroring the scraper's approach.  Finds the corresponding value element
    by searching the parent container first, then falling back to siblings.
    """
    pairs: dict[str, str] = {}
    for label_el in soup.find_all(class_="eyo-data-label"):
        label = clean_text(label_el.get_text())
        if not label:
            continue
        label = label.rstrip(":").strip().lower()

        # Find corresponding field — parent first (same row), then sibling
        row = label_el.parent
        field_el = row.find(class_="eyo-data-field") if row else None
        if not field_el:
            field_el = label_el.find_next_sibling(class_="eyo-data-field")
        if not field_el and row:
            grandparent = row.parent
            if grandparent:
                field_el = grandparent.find(class_="eyo-data-field")
        if field_el:
            value = clean_text(field_el.get_text())
            if value:
                pairs[label] = value
    return pairs


class SynergyExtractor(BaseExtractor):
    @property
    def platform_key(self) -> str:
        return "synergy"

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

        # Provider name — from card header or h1
        name = None
        header = soup.find("div", class_="card-header")
        if header:
            name_el = header.find(["h1", "h2", "h3"])
            if name_el:
                name = clean_text(name_el.get_text())
        if not name:
            h1 = soup.find("h1")
            if h1:
                name = clean_text(h1.get_text())
        data["provider_name"] = name or provider_name

        # Extract ALL eyo-data-label/field pairs — use Synergy-specific
        # extraction that matches any element (not just <span>) with the
        # eyo-data-label/field classes, mirroring the scraper's approach.
        eyo_pairs = _extract_eyo_pairs(soup)

        # Also extract dt/dd pairs as fallback
        dd_pairs = extract_dt_dd(soup)

        # Merge — eyo pairs take precedence
        all_pairs: dict[str, str] = {}
        all_pairs.update(dd_pairs)
        all_pairs.update(eyo_pairs)

        _LABEL_MAP = {
            "address": "_address_raw",
            "address / area": "_address_raw",
            "location": "_address_raw",
            "postcode": "postcode",
            "post code": "postcode",
            "tel": "phone",
            "telephone": "phone",
            "telephone number": "phone",
            "mobile": "phone_secondary",
            "mobile no.": "phone_secondary",
            "email": "email",
            "e-mail": "email",
            "email address": "email",
            "website": "website",
            "web address": "website",
            "web site": "website",
            "fax": "fax",
            "ofsted reference": "ofsted_urn",
            "ofsted reference number": "ofsted_urn",
            "ofsted urn": "ofsted_urn",
            "ofsted rating": "ofsted_rating",
            "type of childcare": "provider_type",
            "provider type": "provider_type",
            "type of provision": "provider_type",
            "childcare provision type": "provider_type",
            "childcare type": "provider_type",
            "type": "provider_type",
            "age range": "age_range",
            "age ranges": "age_range",
            "ages": "age_range",
            "age group": "age_range",
            "age groups": "age_range",
            "from age": "age_from",
            "to age": "age_to",
            "number of places": "places_total",
            "places": "places_total",
            "vacancies": "places_available",
            "opening times": "opening_hours_raw",
            "opening hours": "opening_hours_raw",
            "hours of operation": "opening_hours_raw",
            "sessions": "session_types_raw",
            "session times": "session_types_raw",
            "fees": "fees_raw",
            "cost": "fees_raw",
            "charges": "fees_raw",
            "funded places": "funded_info",
            "free entitlement": "funded_info",
            "special educational needs": "send_provision",
            "sen provision": "send_provision",
            "send": "send_provision",
            "languages spoken": "languages_raw",
            "description": "description",
            "additional information": "description",
            "about us": "description",
            "facilities": "facilities_raw",
            "qualifications": "qualifications_raw",
            "schools collected from": "school_pickups_raw",
            "pick up from school": "school_pickups_raw",
            "term time only": "term_time_only",
            "weeks open per year": "weeks_per_year",
            "town": "town",
            "district": "district",
            "area": "area",
        }

        extra: dict[str, str] = {}
        for label, value in all_pairs.items():
            canonical = _LABEL_MAP.get(label)
            if canonical:
                data[canonical] = value
            else:
                extra[label] = value

        # Parse address
        addr_raw = data.pop("_address_raw", None)
        if addr_raw:
            lines = [
                p.strip().rstrip(",")
                for p in re.split(r"[\n,]", addr_raw)
                if p.strip().rstrip(",")
            ]
            pc = extract_postcode(addr_raw)
            if pc:
                if not data.get("postcode"):
                    data["postcode"] = pc
                lines = [ln for ln in lines if extract_postcode(ln) != pc]
            if lines:
                data["address_line1"] = lines[0] if len(lines) >= 1 else None
                data["address_line2"] = lines[1] if len(lines) >= 2 else None
                if len(lines) >= 4:
                    data["town"] = data.get("town") or lines[-1]
                    data["address_line3"] = ", ".join(lines[2:-1])
                elif len(lines) >= 3:
                    data["town"] = data.get("town") or lines[-1]

        # Email/phone fallback from links
        if not data.get("email"):
            email = extract_email_from_soup(soup)
            if email:
                data["email"] = email
        if not data.get("phone"):
            phone = extract_phone_from_soup(soup)
            if phone:
                data["phone"] = phone

        # Validate email format — names, phones, and placeholders end up here
        if data.get("email") and not validate_email(data["email"]):
            extra["invalid_email"] = data["email"]
            del data["email"]

        if extra:
            data["extra"] = extra

        # Classification
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
