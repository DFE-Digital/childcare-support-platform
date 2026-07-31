"""FID (Family Information Directory) extractor.

Extracts all fields from FID detail page HTML stored in raw_html.
Detail pages use <b>Label:</b> followed by text content.
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


class FidExtractor(BaseExtractor):
    @property
    def platform_key(self) -> str:
        return "fid"

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

        h1 = soup.find("h1")
        data["provider_name"] = clean_text(h1.get_text()) if h1 else provider_name

        # Extract <b>Label:</b> Value patterns
        all_pairs = extract_strong_text_pairs(soup)

        _LABEL_MAP = {
            "address": "_address_raw",
            "postcode": "postcode",
            "telephone": "phone",
            "phone": "phone",
            "email": "email",
            "website": "website",
            "type": "provider_type",
            "provider type": "provider_type",
            "type of childcare": "provider_type",
            "ofsted urn": "ofsted_urn",
            "age range": "age_range",
            "number of places": "places_total",
            "vacancies": "places_available",
            "opening hours": "opening_hours_raw",
            "fees": "fees_raw",
            "description": "description",
        }

        extra: dict[str, str] = {}
        for label, value in all_pairs.items():
            canonical = _LABEL_MAP.get(label)
            if canonical:
                data[canonical] = value
            else:
                extra[label] = value

        addr_raw = data.pop("_address_raw", None)
        if addr_raw:
            parts = [p.strip() for p in addr_raw.split(",") if p.strip()]
            pc = extract_postcode(addr_raw)
            if pc and not data.get("postcode"):
                data["postcode"] = pc
                parts = [p for p in parts if extract_postcode(p) != pc]
            if parts:
                data["town"] = parts[-1]
                parts = parts[:-1]
            if len(parts) >= 1:
                data["address_line1"] = parts[0]
            if len(parts) >= 2:
                data["address_line2"] = parts[1]
            if len(parts) >= 3:
                data["address_line3"] = ", ".join(parts[2:])

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
