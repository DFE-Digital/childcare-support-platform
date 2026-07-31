"""Surrey CC directory extractor.

Extracts all fields from Surrey detail page HTML stored in raw_html.
Detail pages use <h2> section headers with <ul>/<li> lists containing
<strong>Label</strong>: Value pairs.
"""

from __future__ import annotations

import re
from typing import Any

from bsil_pipeline.extractors.base import (
    BaseExtractor,
    ExtractedProvider,
    classify_provider_types,
    clean_text,
    extract_email_from_soup,
    extract_phone_from_soup,
    extract_postcode,
    extract_strong_text_pairs,
    parse_soup,
)

_POSTCODE_RE = re.compile(r"[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}", re.IGNORECASE)


class SurreyExtractor(BaseExtractor):
    @property
    def platform_key(self) -> str:
        return "surrey"

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

        # Extract all <strong>Label</strong>: Value pairs from <li> elements
        all_pairs: dict[str, str] = {}
        for li in soup.find_all("li"):
            strong = li.find("strong")
            if not strong:
                continue
            label = clean_text(strong.get_text()) or ""
            label_clean = label.rstrip(":").strip().lower()
            # Value is text after the strong tag
            full_text = clean_text(li.get_text()) or ""
            # Remove the label part
            value = re.sub(
                r"^" + re.escape(label) + r"\s*:?\s*",
                "",
                full_text,
                flags=re.IGNORECASE,
            ).strip()
            if label_clean and value:
                all_pairs[label_clean] = value

        # Also extract any strong/text pairs not in <li>
        strong_pairs = extract_strong_text_pairs(soup)
        for label, value in strong_pairs.items():
            if label not in all_pairs:
                all_pairs[label] = value

        _LABEL_MAP = {
            "address": "_address_raw",
            "postcode": "postcode",
            "telephone": "phone",
            "phone": "phone",
            "email": "email",
            "website": "website",
            "ofsted urn": "ofsted_urn",
            "ofsted rating": "ofsted_rating",
            "type of childcare": "provider_type",
            "type": "provider_type",
            "provider type": "provider_type",
            "childcare type": "provider_type",
            "age range": "age_range",
            "number of places": "places_total",
            "vacancies": "places_available",
            "opening hours": "opening_hours_raw",
            "opening times": "opening_hours_raw",
            "fees": "fees_raw",
            "cost": "fees_raw",
            "description": "description",
            "about": "description",
            "facilities": "facilities_raw",
            "special educational needs": "send_provision",
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
            parts = [p.strip() for p in addr_raw.split(",") if p.strip()]
            pc = extract_postcode(addr_raw)
            if pc:
                if not data.get("postcode"):
                    data["postcode"] = pc
                parts = [p for p in parts if extract_postcode(p) != pc]
            # Remove "Surrey" county
            if parts and parts[-1].lower() == "surrey":
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
