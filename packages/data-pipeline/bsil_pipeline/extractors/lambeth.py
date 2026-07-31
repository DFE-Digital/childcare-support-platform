"""Lambeth FID extractor.

Extracts all fields from Lambeth Drupal detail page HTML stored in raw_html.
Address uses structured spans, coords from Drupal Leaflet settings JSON.
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
    extract_latlon_drupal_settings,
    extract_phone_from_soup,
    extract_postcode,
    parse_soup,
)


class LambethExtractor(BaseExtractor):
    @property
    def platform_key(self) -> str:
        return "lambeth"

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

        # Name from <title> (strip " | Lambeth Council" suffix)
        title = soup.find("title")
        if title:
            name = clean_text(title.get_text())
            if name and "|" in name:
                name = name.split("|")[0].strip()
            data["provider_name"] = name
        else:
            data["provider_name"] = provider_name

        # Structured address spans
        for cls, key in [
            ("address-line1", "address_line1"),
            ("address-line2", "address_line2"),
            ("locality", "town"),
            ("postal-code", "postcode"),
        ]:
            span = soup.find("span", class_=cls)
            if span:
                val = clean_text(span.get_text())
                if val:
                    data[key] = val

        # Contact from tel/mailto links
        phone = extract_phone_from_soup(soup)
        if phone:
            data["phone"] = phone
        email = extract_email_from_soup(soup)
        if email:
            data["email"] = email

        # Lat/lon from Drupal Leaflet settings
        lat, lon = extract_latlon_drupal_settings(soup)
        if lat is not None:
            data["latitude"] = lat
        if lon is not None:
            data["longitude"] = lon

        # Ofsted URN — search for "Ofsted Unique Ref" text or dt with "ofsted"
        for el in soup.find_all(["dt", "strong", "b", "span", "div", "p"]):
            text = clean_text(el.get_text()) or ""
            if "ofsted" in text.lower() and (
                "ref" in text.lower() or "urn" in text.lower()
            ):
                # Look for a 6+ digit number nearby
                parent = el.parent or el
                parent_text = clean_text(parent.get_text()) or ""
                urn_match = re.search(r"\d{6,}", parent_text)
                if urn_match:
                    data["ofsted_urn"] = urn_match.group(0)
                    break

        # Extract any dt/dd pairs for additional fields
        dd_pairs = extract_dt_dd(soup)
        _LABEL_MAP = {
            "type": "provider_type",
            "provider type": "provider_type",
            "age range": "age_range",
            "opening hours": "opening_hours_raw",
            "fees": "fees_raw",
            "description": "description",
        }

        extra: dict[str, str] = {}
        for label, value in dd_pairs.items():
            canonical = _LABEL_MAP.get(label)
            if canonical:
                data.setdefault(canonical, value)
            else:
                extra[label] = value

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
