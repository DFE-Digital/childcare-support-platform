"""PCG / PPL Innovate directory extractor.

Extracts all fields from the PCG JSON API response stored in raw_json.
The JSON may be either a detail API response (West Berkshire) or a list
item (Bradford, Sheffield).
"""

from __future__ import annotations

import json
from typing import Any

from bsil_pipeline.extractors.base import (
    BaseExtractor,
    ExtractedProvider,
    classify_provider_types,
    clean_text,
    extract_postcode,
    strip_html_tags,
)

_FIELD_MAP: dict[str, str] = {
    "name": "provider_name",
    "postcode": "postcode",
    "phone": "phone",
    "email": "email",
    "address": "address_raw",
    "latitude": "latitude",
    "longitude": "longitude",
    "urn": "ofsted_urn",
    "website": "website",
    "description": "description",
}


class PcgExtractor(BaseExtractor):
    @property
    def platform_key(self) -> str:
        return "pcg"

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

        # Unwrap value wrapper if present (Bradford)
        if "value" in item and isinstance(item["value"], dict):
            item = item["value"]

        # Map known fields
        for json_key, canonical_key in _FIELD_MAP.items():
            val = item.get(json_key)
            if val is not None and str(val).strip():
                if canonical_key in ("latitude", "longitude"):
                    try:
                        data[canonical_key] = float(val)
                    except (ValueError, TypeError):
                        pass
                else:
                    data[canonical_key] = clean_text(str(val))

        # Parse address into parts
        address_raw = data.pop("address_raw", None)
        if address_raw:
            parts = [p.strip() for p in address_raw.split(",") if p.strip()]
            pc = extract_postcode(address_raw)
            if pc and not data.get("postcode"):
                data["postcode"] = pc
                parts = [p for p in parts if extract_postcode(p) != pc]
            if len(parts) >= 1:
                data["address_line1"] = parts[0]
            if len(parts) >= 2:
                data["address_line2"] = parts[1]
            if len(parts) >= 3:
                data["town"] = parts[-1]

        if not data.get("provider_name"):
            data["provider_name"] = provider_name

        # Collect remaining fields into extra{}
        extra: dict[str, Any] = {}
        mapped_keys = set(_FIELD_MAP.keys()) | {
            "id",
            "eventId",
            "Id",
            "value",
        }
        for key, value in item.items():
            if (
                key not in mapped_keys
                and value is not None
                and value != ""
                and value != []
            ):
                # Strip HTML tags from string extra values
                if isinstance(value, str) and "<" in value:
                    value = strip_html_tags(value)
                extra[key] = value

        if extra:
            data["extra"] = extra

        # Classification from type/category fields
        for type_key in ("category", "serviceType", "type", "categories"):
            val = item.get(type_key)
            if val and isinstance(val, str):
                source_labels.append(val.strip())
            elif val and isinstance(val, list):
                for label in val:
                    if isinstance(label, dict):
                        label = label.get("name", str(label))
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
