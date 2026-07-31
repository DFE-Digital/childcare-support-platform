"""Open Objects Marketplace extractor.

Extracts all fields from Marketplace detail page HTML stored in raw_html.
Detail pages use <dt>/<dd> pairs for all data fields.
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
)


class MarketplaceExtractor(BaseExtractor):
    @property
    def platform_key(self) -> str:
        return "marketplace"

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

        # Extract ALL dt/dd pairs
        all_pairs = extract_dt_dd(soup)

        _LABEL_MAP = {
            "locations": "_address_raw",
            "address": "_address_raw",
            "postcode": "postcode",
            "telephone": "phone",
            "phone": "phone",
            "email": "email",
            "mobile": "phone_secondary",
            "website": "website",
            "fax": "fax",
            "contact name": "contact_name",
            "ofsted reference": "ofsted_urn",
            "ofsted unique reference number": "ofsted_urn",
            "ofsted report": "ofsted_report_url",
            "ofsted reports": "ofsted_report_url",
            "ofsted inspection report": "ofsted_report_url",
            "inspection (early years register)": "ofsted_rating",
            "re-inspection (early years register)": "ofsted_rating",
            "type of childcare": "provider_type",
            "category": "provider_type",
            "type": "provider_type",
            "provider type": "provider_type",
            "main service type": "provider_type",
            "childcare type": "provider_type",
            "age range": "age_range",
            "childcare ages": "age_range",
            "age groups": "age_range",
            "number of places": "places_total",
            "vacancies": "places_available",
            "vacancy notes": "places_available",
            "opening times": "opening_hours_raw",
            "opening hours": "opening_hours_raw",
            "session times": "opening_hours_raw",
            "sessions": "session_types_raw",
            "childcare periods": "session_types_raw",
            "availability": "term_time_info",
            "fees": "fees_raw",
            "cost": "fees_raw",
            "charges and costs": "fees_raw",
            "costs": "fees_raw",
            "funded places": "funded_info",
            "childcare support": "funded_info",
            "offers tax free childcare": "tax_free_childcare",
            "special educational needs": "send_provision",
            "send local offer details": "send_provision",
            "part of the send local offer": "send_local_offer",
            "district": "district",
            "area": "area",
            "description": "description",
            "summary": "description",
            "facilities": "facilities_raw",
            "childcare facilities": "facilities_raw",
            "schools visited": "school_pickups_raw",
            "facebook page": "facebook_url",
            "facebook link": "facebook_url",
        }

        # Labels that contribute to provider type classification
        _TYPE_LABELS = {
            "type of childcare",
            "category",
            "type",
            "provider type",
            "main service type",
            "childcare type",
        }

        extra: dict[str, str] = {}
        for label, value in all_pairs.items():
            canonical = _LABEL_MAP.get(label)
            if canonical:
                data.setdefault(canonical, value)
            else:
                extra[label] = value
            # Collect ALL type labels for classification
            if label in _TYPE_LABELS and value:
                for part in re.split(r"[,/;]", value):
                    part = part.strip()
                    if part:
                        source_labels.append(part)

        # Parse Ofsted URN from report URL or text
        report_url = data.get("ofsted_report_url", "")
        if report_url and not data.get("ofsted_urn"):
            urn_match = re.search(r"/(\d{5,7})(?:\D|$)", report_url)
            if urn_match:
                data["ofsted_urn"] = urn_match.group(1)
        # Also check for URN in the dd text of ofsted fields
        for dt in soup.find_all("dt"):
            label = clean_text(dt.get_text()) or ""
            if "ofsted" in label.lower():
                dd = dt.find_next_sibling("dd")
                if dd:
                    link = dd.find("a", href=re.compile(r"ofsted\.gov\.uk"))
                    if link and not data.get("ofsted_urn"):
                        urn_match = re.search(r"/(\d{5,7})(?:\D|$)", link["href"])
                        if urn_match:
                            data["ofsted_urn"] = urn_match.group(1)

        # Parse address — strip "(directions displayed on map)" noise
        addr_raw = data.pop("_address_raw", None)
        if addr_raw:
            addr_raw = re.sub(
                r"\s*\(directions displayed on map\)", "", addr_raw, flags=re.IGNORECASE
            )
            parts = [p.strip() for p in addr_raw.split(",") if p.strip()]
            pc = extract_postcode(addr_raw)
            if pc:
                if not data.get("postcode"):
                    data["postcode"] = pc
                parts = [p for p in parts if extract_postcode(p) != pc]
            if parts:
                data["address_line1"] = parts[0] if len(parts) >= 1 else None
                data["address_line2"] = parts[1] if len(parts) >= 2 else None
                if len(parts) >= 4:
                    data["town"] = parts[-1]
                    data["address_line3"] = ", ".join(parts[2:-1])
                elif len(parts) >= 3:
                    data["town"] = parts[-1]

        # Email/phone fallback from links
        if not data.get("email"):
            email = extract_email_from_soup(soup)
            if email:
                data["email"] = email
        if not data.get("phone"):
            phone = extract_phone_from_soup(soup)
            if phone:
                data["phone"] = phone

        if extra:
            data["extra"] = extra

        classification = classify_provider_types(source_labels)

        return ExtractedProvider(
            lad25cd=lad25cd,
            provider_id=provider_id,
            extracted_data=data,
            classification=classification,
            source_classification=source_labels,
            extraction_warnings=warnings,
        )
