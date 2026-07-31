"""LocalGov Drupal Directories extractor.

Note: The LocalGov Drupal scraper stores raw_json=None to save space,
so this extractor works primarily from whatever data is available.
If raw_json is populated in future, it will extract from the JSON:API node.
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


class LocalGovDrupalExtractor(BaseExtractor):
    @property
    def platform_key(self) -> str:
        return "localgov_drupal"

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
            # This platform typically has raw_json=None
            warnings.append("no raw_json available (by design)")
            if provider_name:
                data["provider_name"] = provider_name
            return ExtractedProvider(
                lad25cd=lad25cd,
                provider_id=provider_id,
                extracted_data=data,
                extraction_warnings=warnings,
            )

        # If raw_json is populated in future, extract from JSON:API node
        try:
            node = json.loads(raw_json)
        except json.JSONDecodeError as e:
            warnings.append(f"JSON parse error: {e}")
            return ExtractedProvider(
                lad25cd=lad25cd,
                provider_id=provider_id,
                extraction_warnings=warnings,
            )

        attrs = node.get("attributes", {}) if "attributes" in node else node

        data["provider_name"] = clean_text(attrs.get("title")) or provider_name

        # Phone
        phone_list = attrs.get("localgov_directory_phone") or []
        if phone_list and isinstance(phone_list, list):
            first = phone_list[0]
            data["phone"] = (
                clean_text(first.get("value"))
                if isinstance(first, dict)
                else clean_text(str(first))
            )

        # Email
        email_list = attrs.get("localgov_directory_email") or []
        if email_list and isinstance(email_list, list):
            first = email_list[0]
            data["email"] = (
                clean_text(first.get("value"))
                if isinstance(first, dict)
                else clean_text(str(first))
            )

        # Address (inline for pages)
        addr = attrs.get("localgov_directory_address") or {}
        if isinstance(addr, dict):
            if addr.get("address_line1"):
                data["address_line1"] = clean_text(addr["address_line1"])
            if addr.get("locality"):
                data["town"] = clean_text(addr["locality"])
            if addr.get("postal_code"):
                data["postcode"] = clean_text(addr["postal_code"])

        # Collect remaining attributes
        extra: dict[str, Any] = {}
        _known = {
            "title",
            "localgov_directory_phone",
            "localgov_directory_email",
            "localgov_directory_address",
        }
        for key, value in attrs.items():
            if key not in _known and value is not None and value != "" and value != []:
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
