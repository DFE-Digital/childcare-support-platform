"""Family Support NI extractor.

Extracts all fields from NI detail page HTML stored in raw_html.
Detail pages have #organisationDetails with <dl>/<dt>/<dd> pairs.
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
    is_council_email,
    parse_soup,
    validate_email,
)

# Regex to detect BT outer-only postcodes (e.g. BT28 without inner code)
_BT_OUTER_ONLY_RE = re.compile(r"^BT\d{1,2}$", re.IGNORECASE)


class FamilySupportNIExtractor(BaseExtractor):
    @property
    def platform_key(self) -> str:
        return "familysupportni"

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

        # Provider name from <h1>
        h1 = soup.find("h1")
        data["provider_name"] = clean_text(h1.get_text()) if h1 else provider_name

        # Extract dt/dd pairs from #organisationDetails
        org_details = soup.find(id="organisationDetails")
        all_pairs: dict[str, str] = {}
        if org_details:
            all_pairs = extract_dt_dd(soup, scope=org_details)
        # Also get page-wide dt/dd as fallback
        all_pairs.update(
            {k: v for k, v in extract_dt_dd(soup).items() if k not in all_pairs}
        )

        _LABEL_MAP = {
            "address": "_address_raw",
            "postcode": "postcode",
            "telephone": "phone",
            "telephone number": "phone",
            "phone": "phone",
            "email": "email",
            "email address": "email",
            "e-mail": "email",
            "website": "website",
            "web address": "website",
            "fax": "fax",
            "ccp reference": "ccp_reference",
            "type of childcare": "provider_type",
            "type of service": "provider_type",
            "category": "provider_type",
            "category of services": "provider_type",
            "provider type": "provider_type",
            "age range": "age_range",
            "available to age groups": "age_range",
            "number of places": "places_total",
            "vacancies": "places_available",
            "opening times": "opening_hours_raw",
            "opening hours": "opening_hours_raw",
            "fees": "fees_raw",
            "cost": "fees_raw",
            "description": "description",
            "about": "description",
            "languages": "languages_raw",
            "area": "area",
            "district": "district",
        }

        extra: dict[str, str] = {}
        for label, value in all_pairs.items():
            canonical = _LABEL_MAP.get(label)
            if canonical:
                data[canonical] = value
            else:
                extra[label] = value

        # Parse NI address
        addr_raw = data.pop("_address_raw", None)
        if addr_raw:
            parts = [p.strip() for p in addr_raw.split(",") if p.strip()]
            # NI postcodes start with BT
            if parts and re.match(r"BT\d", parts[-1], re.IGNORECASE):
                data["postcode"] = parts[-1].strip().upper()
                parts = parts[:-1]
            elif not data.get("postcode"):
                pc = extract_postcode(addr_raw)
                if pc:
                    data["postcode"] = pc
                    parts = [p for p in parts if extract_postcode(p) != pc]
            # Remove county (Co Antrim, etc.)
            if parts and re.match(r"Co\s+\w+", parts[-1], re.IGNORECASE):
                data["county"] = parts[-1]
                parts = parts[:-1]
            if parts:
                data["town"] = parts[-1]
                parts = parts[:-1]
            if len(parts) >= 1:
                data["address_line1"] = parts[0]
            if len(parts) >= 2:
                data["address_line2"] = parts[1]
            if len(parts) >= 3:
                data["address_line3"] = ", ".join(parts[2:])

        # Email/phone fallback
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

        # Warn on BT outer-only postcodes (e.g. "BT28" without inner code)
        if data.get("postcode") and _BT_OUTER_ONLY_RE.match(data["postcode"]):
            warnings.append(f"outer-only postcode: {data['postcode']} (no inner code)")

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
