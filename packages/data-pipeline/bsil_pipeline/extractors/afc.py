"""AFC info portal extractor.

Extracts all fields from AFC detail page HTML stored in raw_html.
Detail pages use <dt>/<dd> pairs.
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


class AfcExtractor(BaseExtractor):
    @property
    def platform_key(self) -> str:
        return "afc"

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

        all_pairs = extract_dt_dd(soup)

        _LABEL_MAP = {
            "address 1": "address_line1",
            "address 2": "address_line2",
            "address line 1": "address_line1",
            "address line 2": "address_line2",
            "postcode": "postcode",
            "town": "town",
            "city": "town",
            "borough": "borough",
            "telephone": "phone",
            "phone": "phone",
            "email": "email",
            "website": "website",
            "ofsted number": "ofsted_urn",
            "ofsted urn": "ofsted_urn",
            "type": "provider_type",
            "provider type": "provider_type",
            "type of childcare": "provider_type",
            "age range": "age_range",
            "number of places": "places_total",
            "vacancies": "places_available",
            "opening hours": "opening_hours_raw",
            "fees": "fees_raw",
            "description": "description",
            "facilities": "facilities_raw",
        }

        extra: dict[str, str] = {}
        for label, value in all_pairs.items():
            canonical = _LABEL_MAP.get(label)
            if canonical:
                data[canonical] = value
            else:
                extra[label] = value

        # Fallback postcode search
        if not data.get("postcode"):
            for tag in soup.find_all(["p", "span", "div"]):
                text = clean_text(tag.get_text())
                if text and "postcode" in text.lower():
                    pc = extract_postcode(text)
                    if pc:
                        data["postcode"] = pc
                        break

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
