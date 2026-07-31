"""Hartlepool Family Hubs extractor.

Extracts all fields from the inline JavaScript provider object stored in raw_json.
Structure: { "id": ..., "name": "...", "location": "...", "postcode": "...",
             "phone_number": "...", "email_address": "...", "ofsted_reference": "...",
             "latitude": ..., "longitude": ..., ... }
"""

from __future__ import annotations

import json
from typing import Any

from bsil_pipeline.extractors.base import (
    BaseExtractor,
    ExtractedProvider,
    classify_provider_types,
    clean_text,
)

_FIELD_MAP: dict[str, str] = {
    "name": "provider_name",
    "location": "address_line1",
    "postcode": "postcode",
    "phone_number": "phone",
    "email_address": "email",
    "ofsted_reference": "ofsted_urn",
    "latitude": "latitude",
    "longitude": "longitude",
    "website": "website",
    "description": "description",
}


class HartlepoolExtractor(BaseExtractor):
    @property
    def platform_key(self) -> str:
        return "hartlepool"

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
            provider = json.loads(raw_json)
        except json.JSONDecodeError as e:
            warnings.append(f"JSON parse error: {e}")
            return ExtractedProvider(
                lad25cd=lad25cd,
                provider_id=provider_id,
                extraction_warnings=warnings,
            )

        # Map known fields
        for json_key, canonical_key in _FIELD_MAP.items():
            val = provider.get(json_key)
            if val is not None and str(val).strip():
                if canonical_key in ("latitude", "longitude"):
                    try:
                        data[canonical_key] = float(val)
                    except (ValueError, TypeError):
                        pass
                else:
                    data[canonical_key] = clean_text(str(val))

        if not data.get("provider_name"):
            data["provider_name"] = provider_name

        # Collect remaining fields into extra{}
        extra: dict[str, Any] = {}
        mapped_keys = set(_FIELD_MAP.keys()) | {"id"}
        for key, value in provider.items():
            if (
                key not in mapped_keys
                and value is not None
                and value != ""
                and value != []
            ):
                extra[key] = value

        if extra:
            data["extra"] = extra

        # Classification from type/service fields
        for type_key in ("service_type", "type", "category", "provider_type"):
            val = provider.get(type_key)
            if val and isinstance(val, str):
                source_labels.append(val.strip())
            elif val and isinstance(val, list):
                for label in val:
                    if isinstance(label, str) and label.strip():
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
