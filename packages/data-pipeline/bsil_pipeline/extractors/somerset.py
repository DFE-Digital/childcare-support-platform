"""Somerset childcare directory extractor.

Extracts all fields from the WordPress REST API JSON stored in raw_json.
Structure: { "id": ..., "title": {"rendered": "..."}, "acf": { ... } }
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
)


class SomersetExtractor(BaseExtractor):
    @property
    def platform_key(self) -> str:
        return "somerset"

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
            post = json.loads(raw_json)
        except json.JSONDecodeError as e:
            warnings.append(f"JSON parse error: {e}")
            return ExtractedProvider(
                lad25cd=lad25cd,
                provider_id=provider_id,
                extraction_warnings=warnings,
            )

        # Provider name from title
        title_obj = post.get("title", {})
        data["provider_name"] = (
            clean_text(title_obj.get("rendered"))
            if isinstance(title_obj, dict)
            else provider_name
        )

        acf = post.get("acf", {}) or {}

        # Address from ACF Google Map field
        phys_addr = acf.get("physical_address", {}) or {}
        address_text = phys_addr.get("address", "")
        if address_text:
            data["address_raw"] = clean_text(address_text)
            postcode = extract_postcode(address_text)
            if postcode:
                data["postcode"] = postcode
        lat = phys_addr.get("lat")
        lng = phys_addr.get("lng")
        if lat is not None:
            data["latitude"] = float(lat)
        if lng is not None:
            data["longitude"] = float(lng)

        # Contact
        phone = clean_text(str(acf.get("phone_number", ""))) or None
        if phone:
            data["phone"] = phone
        email = clean_text(str(acf.get("service_email", ""))) or None
        if email:
            data["email"] = email
        website = clean_text(str(acf.get("website", ""))) or None
        if website:
            data["website"] = website

        # Ofsted URN
        accreditations = acf.get("service_accreditations", {}) or {}
        urn = clean_text(str(accreditations.get("ofsted_urn", ""))) or None
        if urn:
            data["ofsted_urn"] = urn

        # Collect all remaining ACF fields into extra{}
        extra: dict[str, Any] = {}
        _known_acf = {
            "physical_address",
            "phone_number",
            "service_email",
            "website",
            "service_accreditations",
        }
        for key, value in acf.items():
            if (
                key not in _known_acf
                and value is not None
                and value != ""
                and value != []
            ):
                extra[key] = value

        # Remaining accreditation fields beyond ofsted_urn
        for key, value in accreditations.items():
            if (
                key != "ofsted_urn"
                and value is not None
                and value != ""
                and value != []
            ):
                extra[f"accreditations.{key}"] = value

        if extra:
            data["extra"] = extra

        # Classification from ACF type fields
        for type_key in ("childcare_type", "service_type", "provider_type", "type"):
            val = acf.get(type_key)
            if val:
                if isinstance(val, list):
                    for item in val:
                        label = (
                            item.get("label", str(item))
                            if isinstance(item, dict)
                            else str(item)
                        )
                        source_labels.append(label.strip())
                elif isinstance(val, str):
                    source_labels.append(val.strip())

        classification = classify_provider_types(source_labels)

        return ExtractedProvider(
            lad25cd=lad25cd,
            provider_id=provider_id,
            extracted_data=data,
            classification=classification,
            source_classification=source_labels,
            extraction_warnings=warnings,
        )
