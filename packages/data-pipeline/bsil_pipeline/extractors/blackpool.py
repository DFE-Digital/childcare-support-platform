"""Blackpool FYI Directory extractor (Contensis CMS).

Extracts all fields from the Contensis entry JSON stored in raw_json.
Structure: { "sys": {...}, "entryTitle": "...", "address": {...},
             "contact": {...}, "location": {...}, ... }
"""

from __future__ import annotations

import json
from typing import Any

from bsil_pipeline.extractors.base import (
    BaseExtractor,
    ExtractedProvider,
    classify_provider_types,
    clean_text,
    strip_html_tags,
)


class BlackpoolExtractor(BaseExtractor):
    @property
    def platform_key(self) -> str:
        return "blackpool"

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
            entry = json.loads(raw_json)
        except json.JSONDecodeError as e:
            warnings.append(f"JSON parse error: {e}")
            return ExtractedProvider(
                lad25cd=lad25cd,
                provider_id=provider_id,
                extraction_warnings=warnings,
            )

        data["provider_name"] = clean_text(entry.get("entryTitle")) or provider_name

        # Address
        address = entry.get("address") or {}
        if clean_text(address.get("addressLine1")):
            data["address_line1"] = clean_text(address.get("addressLine1"))
        if clean_text(address.get("addressLine2")):
            data["address_line2"] = clean_text(address.get("addressLine2"))
        if clean_text(address.get("city")):
            data["town"] = clean_text(address.get("city"))
        if clean_text(address.get("postcode")):
            data["postcode"] = clean_text(address.get("postcode"))
        if clean_text(address.get("county")):
            data["county"] = clean_text(address.get("county"))

        # Contact
        contact = entry.get("contact") or {}
        phones = contact.get("telephone") or []
        if phones:
            data["phone"] = (
                clean_text(phones[0]) if isinstance(phones[0], str) else None
            )
            if len(phones) > 1:
                data["phone_secondary"] = clean_text(phones[1])
        emails = contact.get("email") or []
        if emails:
            data["email"] = (
                clean_text(emails[0]) if isinstance(emails[0], str) else None
            )

        # Location
        location = entry.get("location") or {}
        if location.get("lat") is not None:
            data["latitude"] = float(location["lat"])
        if location.get("lon") is not None:
            data["longitude"] = float(location["lon"])

        # Extract text fields that contain HTML — strip tags
        _HTML_FIELDS = {
            "description": "description",
            "openingHours": "opening_hours_raw",
            "loInformation": "send_provision",
            "additionalInformation": "description_additional",
            "vacancyInformation": "places_available",
        }
        for json_key, canonical_key in _HTML_FIELDS.items():
            val = entry.get(json_key)
            if val and isinstance(val, str):
                cleaned = strip_html_tags(val)
                if cleaned:
                    data[canonical_key] = cleaned

        # Collect all remaining top-level fields into extra{}
        extra: dict[str, Any] = {}
        _known_keys = {
            "sys",
            "entryTitle",
            "address",
            "contact",
            "location",
            *_HTML_FIELDS.keys(),
        }
        for key, value in entry.items():
            if (
                key not in _known_keys
                and value is not None
                and value != ""
                and value != []
            ):
                if isinstance(value, dict) and all(
                    v is None or v == "" for v in value.values()
                ):
                    continue
                extra[key] = value

        if extra:
            data["extra"] = extra

        # Classification from entry type fields
        for type_key in ("serviceType", "category", "type", "providerType", "ecd"):
            val = entry.get(type_key)
            if val and isinstance(val, str):
                source_labels.append(val.strip())
            elif val and isinstance(val, list):
                for item in val:
                    if isinstance(item, dict):
                        label = (
                            item.get("entryTitle")
                            or item.get("title")
                            or item.get("name", "")
                        )
                    else:
                        label = str(item)
                    if label.strip():
                        source_labels.append(label.strip())

        classification = classify_provider_types(source_labels)

        return ExtractedProvider(
            lad25cd=lad25cd,
            provider_id=provider_id,
            extracted_data=data,
            classification=classification,
            source_classification=source_labels,
            extraction_warnings=warnings,
        )
