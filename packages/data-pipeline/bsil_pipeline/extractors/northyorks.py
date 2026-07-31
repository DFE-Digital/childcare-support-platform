"""North Yorkshire ArcGIS Feature Service extractor.

Extracts all fields from the ArcGIS feature attributes dict stored in raw_json.
Structure: { "OBJECTID": ..., "Name": "...", "Full_Address": "...",
             "Postcode": "...", "Provider_Telephone": "...", ... }

The layer_id is encoded in the provider_id as "{layerId}_{OBJECTID}".
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
    extract_postcode,
)

# Maps ArcGIS attribute names to canonical keys
_FIELD_MAP: dict[str, str] = {
    "Name": "provider_name",
    "Postcode": "postcode",
    "Provider_Telephone": "phone",
    "Provider_Email": "email",
    "Full_Address": "address_raw",
}

# Layer IDs map to provider types.
# Layers 6–8, 12 are mixed: they contain both school-hosted provision and
# private providers listed under the same category.  For these layers the
# label is only used when the provider name looks like a school; otherwise
# a neutral fallback label is emitted so CARE_TYPE_MAPPING can classify
# correctly.
_LAYER_TYPES: dict[int, str] = {
    0: "Childminder",
    1: "Day Nursery",
    2: "Pre-school",
    3: "Out of School Club",
    4: "Holiday Club",
    5: "Breakfast Club",
    6: "Nursery School",
    7: "Nursery Class",
    8: "Independent School",
    9: "After School Club",
    10: "Wrap Around Care",
    11: "Creche",
    12: "School",
    13: "Other",
}

# Layers whose label implies school-based provision but which contain a mix
# of schools and private providers.
_MIXED_SCHOOL_LAYERS = {6, 7, 8, 12}

# Fallback label for providers in mixed layers that don't look like schools.
_MIXED_LAYER_FALLBACK: dict[int, str] = {
    6: "Day Nursery",  # standalone nursery, not a maintained nursery school
    7: "Day Nursery",  # private nursery, not a school nursery class
    8: "Day Nursery",  # private nursery at an independent school site
    12: "Day Nursery",  # private nursery listed under 'School' layer
}

_SCHOOL_NAME_RE = re.compile(
    r"\b(school|academy|primary|infant|junior|secondary|grammar"
    r"|preparatory|prep\b|college|c of e|cofe|ce |church|catholic"
    r"|methodist|baptist)\b",
    re.IGNORECASE,
)


class NorthYorksExtractor(BaseExtractor):
    @property
    def platform_key(self) -> str:
        return "northyorks"

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
            attrs = json.loads(raw_json)
        except json.JSONDecodeError as e:
            warnings.append(f"JSON parse error: {e}")
            return ExtractedProvider(
                lad25cd=lad25cd,
                provider_id=provider_id,
                extraction_warnings=warnings,
            )

        # Map known fields
        for json_key, canonical_key in _FIELD_MAP.items():
            val = attrs.get(json_key)
            if val is not None and str(val).strip():
                data[canonical_key] = clean_text(str(val))

        # Clean email — strip mailto: prefix
        if data.get("email"):
            data["email"] = (
                data["email"].removeprefix("mailto:").removeprefix("MAILTO:").strip()
            )

        # Parse address into parts
        full_addr = data.pop("address_raw", None)
        if full_addr:
            parts = [p.strip() for p in full_addr.split(",") if p.strip()]
            pc = extract_postcode(full_addr)
            if pc:
                data["postcode"] = data.get("postcode") or pc
                # Remove postcode from parts if present
                parts = [p for p in parts if extract_postcode(p) != pc]
            if len(parts) >= 1:
                data["address_line1"] = parts[0]
            if len(parts) >= 2:
                data["address_line2"] = parts[1]
            if len(parts) >= 3:
                data["town"] = parts[-1]

        if not data.get("provider_name"):
            data["provider_name"] = provider_name

        # Provider type from layer ID
        try:
            layer_id = int(provider_id.split("_")[0])
            layer_type = _LAYER_TYPES.get(layer_id)
            if layer_type:
                data["provider_type"] = layer_type
                # For mixed layers, only use the school label when the name
                # actually looks like a school; otherwise use a neutral fallback.
                if layer_id in _MIXED_SCHOOL_LAYERS and not _SCHOOL_NAME_RE.search(
                    data.get("provider_name", "") or ""
                ):
                    source_labels.append(_MIXED_LAYER_FALLBACK[layer_id])
                else:
                    source_labels.append(layer_type)
        except (ValueError, IndexError):
            pass

        # Collect remaining attributes into extra{}
        extra: dict[str, Any] = {}
        mapped_keys = set(_FIELD_MAP.keys()) | {"OBJECTID"}
        for key, value in attrs.items():
            if key not in mapped_keys and value is not None and str(value).strip():
                extra[key] = value

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
