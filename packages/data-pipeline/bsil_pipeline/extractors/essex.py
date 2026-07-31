"""Essex FIS JSON extractor.

Extracts all fields from the Essex FIS JSON API response stored in raw_json.
The JSON structure is: { "Id": "...", "Name": "...", "Fields": { ... } }
where Fields contains all provider data with PascalCase keys.
"""

from __future__ import annotations

import json
from typing import Any

import re

from bsil_pipeline.extractors.base import (
    BaseExtractor,
    ExtractedProvider,
    classify_provider_types,
    clean_text,
    strip_html_tags,
)

# Maps Essex JSON field names (in Fields object) to canonical keys.
_FIELD_MAP: dict[str, str] = {
    "ProviderName": "provider_name",
    "AddressBuildingNumberOrName": "address_line1",
    "AddressStreet": "address_line2",
    "AddressTown": "town",
    "AddressPostcode": "postcode",
    "OfstedReference": "ofsted_urn",
    "Latitude": "latitude",
    "Longitude": "longitude",
    "Telephone": "phone",
    "Email": "email",
    "Website": "website",
    "Fax": "fax",
}

# Source classification labels found in Essex data
_CATEGORY_KEY = "CategoryName"
_TYPE_KEY = "ProviderType"


class EssexExtractor(BaseExtractor):
    @property
    def platform_key(self) -> str:
        return "essex"

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

        if not raw_json:
            warnings.append("no raw_json available")
            return ExtractedProvider(
                lad25cd=lad25cd,
                provider_id=provider_id,
                extracted_data={"provider_name": provider_name}
                if provider_name
                else {},
                extraction_warnings=warnings,
            )

        try:
            item = json.loads(raw_json)
        except json.JSONDecodeError as e:
            warnings.append(f"JSON parse error: {e}")
            return ExtractedProvider(
                lad25cd=lad25cd,
                provider_id=provider_id,
                extraction_warnings=warnings,
            )

        fields = item.get("Fields", {})

        # Map known fields to canonical keys
        for json_key, canonical_key in _FIELD_MAP.items():
            val = (
                clean_text(str(fields.get(json_key, "")))
                if fields.get(json_key)
                else None
            )
            if val:
                data[canonical_key] = val

        # Fallback provider name from top-level Name
        if not data.get("provider_name"):
            data["provider_name"] = clean_text(item.get("Name")) or provider_name

        # Fix website field — Essex stores <a> tags, extract the href URL
        if data.get("website"):
            website_val = data["website"]
            href_match = re.search(r'href="([^"]*)"', str(fields.get("Website", "")))
            if href_match:
                url = href_match.group(1).strip()
                data["website"] = url if url and url != "http://" else None
            elif "<" in website_val:
                data["website"] = strip_html_tags(website_val)

        # Strip HTML from text fields that may contain markup
        for key in ("description", "opening_hours_raw"):
            if data.get(key) and "<" in str(data[key]):
                data[key] = strip_html_tags(str(data[key]))

        # Collect all remaining fields into extra{}
        extra: dict[str, Any] = {}
        mapped_keys = set(_FIELD_MAP.keys())
        for key, value in fields.items():
            if key not in mapped_keys and value is not None and value != "":
                # Strip HTML tags from all string extra values
                if isinstance(value, str) and "<" in value:
                    value = strip_html_tags(value)
                extra[key] = value
        # Top-level keys beyond Fields
        for key in ("Id", "Name", "Distance", "Lat", "Lng"):
            val = item.get(key)
            if val is not None and val != "":
                extra[f"_top.{key}"] = val

        if extra:
            data["extra"] = extra

        # Classification from category/type fields
        for key in (_CATEGORY_KEY, _TYPE_KEY):
            val = fields.get(key)
            if val and isinstance(val, str):
                for label in val.split(","):
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
