"""Liquidlogic parent portal extractor.

Extracts all fields from Liquidlogic detail page HTML stored in raw_html.
Detail pages use <table> with <th>/<td> label/value rows.
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
    extract_table_rows,
    parse_soup,
)


class LiquidlogicExtractor(BaseExtractor):
    @property
    def platform_key(self) -> str:
        return "liquidlogic"

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

        # Name from first heading
        for tag_name in ("h4", "h3", "h2", "h1"):
            h = soup.find(tag_name)
            if h:
                data["provider_name"] = clean_text(h.get_text())
                break
        if not data.get("provider_name"):
            data["provider_name"] = provider_name

        # Extract all table <th>/<td> pairs
        all_pairs = extract_table_rows(soup)

        _LABEL_MAP = {
            "address": "_address_raw",
            "postcode": "postcode",
            "telephone": "phone",
            "phone": "phone",
            "email": "email",
            "website": "website",
            "ofsted urn": "ofsted_urn",
            "type": "provider_type",
            "provider type": "provider_type",
            "type of provision": "provider_type",
            "age range": "age_range",
            "minimum age": "eligible_min_years",
            "maximum age": "eligible_max_years",
            "number of places": "places_total",
            "total registered places": "places_total",
            "weeks open": "operating_weeks_per_year",
            "vacancies": "places_available",
            "opening hours": "opening_hours_raw",
            "fees": "fees_raw",
            "description": "description",
        }

        extra: dict[str, str] = {}
        for label, value in all_pairs.items():
            canonical = _LABEL_MAP.get(label)
            if canonical:
                if canonical == "ofsted_urn":
                    urn_match = re.search(
                        r"EY\d+|CA\d+|\b\d{6,7}\b", value, re.IGNORECASE
                    )
                    data["ofsted_urn"] = (
                        urn_match.group(0).upper() if urn_match else value
                    )
                else:
                    data[canonical] = value
            # Handle partial matches for ofsted
            elif "ofsted" in label and "urn" in label:
                urn_match = re.search(r"EY\d+|CA\d+|\b\d{6,7}\b", value, re.IGNORECASE)
                if urn_match:
                    data["ofsted_urn"] = urn_match.group(0).upper()
                else:
                    extra[label] = value
            else:
                extra[label] = value

        # Clean phone — strip trailing dots, detect duplicated numbers
        phone = data.get("phone")
        if phone:
            phone = phone.rstrip(".")
            if len(phone) % 2 == 0:
                half = len(phone) // 2
                if phone[:half] == phone[half:]:
                    phone = phone[:half]
            data["phone"] = clean_text(phone)

        # Parse address
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

        # Email from links (some have href not text)
        if not data.get("email"):
            for tr in soup.find_all("tr"):
                th = tr.find("th")
                td = tr.find("td")
                if th and td and "email" in (clean_text(th.get_text()) or "").lower():
                    a = td.find("a")
                    if a:
                        data["email"] = clean_text(a.get_text()) or clean_text(
                            a.get("href", "").replace("mailto:", "")
                        )
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
