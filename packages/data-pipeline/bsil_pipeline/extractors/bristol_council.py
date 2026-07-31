"""Bristol Council childcare directory extractor.

Parses raw_json stored by BristolCouncilScraper into ExtractedProvider.
Preserves council_bristol_id and council_fis_url for the merge asset.
"""

from __future__ import annotations

import json
import re
from typing import Any

from bsil_pipeline.extractors.base import (
    BaseExtractor,
    ExtractedProvider,
    classify_provider_types,
    clean_text,
    extract_postcode,
    is_council_email,
    validate_email,
)


def _normalise_person_name(name: str) -> str:
    """Invert 'Firstname Surname' → 'Surname, Firstname' for childminders.

    Liquid Logic stores childminder names as 'Surname, Firstname Middle'
    while Bristol Council uses 'Firstname Surname'. Inverting at extraction
    time means the merge script and canonical linkage see consistent formats.

    Only applies to simple person names (2-3 words, no commas already).
    Names that look like organisations are left as-is.
    """
    if "," in name:
        return name
    parts = name.strip().split()
    if len(parts) < 2 or len(parts) > 3:
        return name
    # Skip if it looks like an organisation (contains common org words)
    org_indicators = re.compile(
        r"\b(nursery|school|club|centre|center|academy|college|day|pre|house|park)\b",
        re.IGNORECASE,
    )
    if org_indicators.search(name):
        return name
    # Invert: "Firstname Surname" → "Surname, Firstname"
    # or "Firstname Middle Surname" → "Surname, Firstname Middle"
    return f"{parts[-1]}, {' '.join(parts[:-1])}"


_FIS_DEFAULT_EMAIL = "askcyps@bristol.gov.uk"
_FIS_DEFAULT_PHONE = "0117 357 4192"


class BristolCouncilExtractor(BaseExtractor):
    @property
    def platform_key(self) -> str:
        return "bristol_council"

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
            record = json.loads(raw_json)
        except json.JSONDecodeError as e:
            warnings.append(f"json_parse_error: {e}")
            return ExtractedProvider(
                lad25cd=lad25cd,
                provider_id=provider_id,
                extracted_data={"provider_name": provider_name}
                if provider_name
                else {},
                extraction_warnings=warnings,
            )

        name = clean_text(record.get("name", "")) or provider_name
        pt = clean_text(record.get("provider_type", ""))
        if name:
            # Childminder names from Bristol Council are "Firstname Surname"
            # but Liquid Logic uses "Surname, Firstname" — invert to match
            if pt and "childminder" in pt.lower():
                name = _normalise_person_name(name)
            data["provider_name"] = name

        addr = clean_text(record.get("address", ""))
        if addr:
            parts = [p.strip() for p in addr.split(",") if p.strip()]
            pc = extract_postcode(addr)
            if pc:
                data["postcode"] = pc
                parts = [p for p in parts if extract_postcode(p) != pc]
            if parts:
                data["town"] = parts[-1]
                parts = parts[:-1]
            if len(parts) >= 1:
                data["address_line1"] = parts[0]
            if len(parts) >= 2:
                data["address_line2"] = parts[1]

        pc = clean_text(record.get("postcode", ""))
        if pc and not data.get("postcode"):
            data["postcode"] = pc

        phone = clean_text(record.get("phone", ""))
        if phone:
            if phone.replace(" ", "") == _FIS_DEFAULT_PHONE.replace(" ", ""):
                data.setdefault("extra", {})["council_phone"] = phone
            else:
                data["phone"] = phone

        email = clean_text(record.get("email", ""))
        if email:
            if not validate_email(email):
                data.setdefault("extra", {})["invalid_email"] = email
            elif email.lower() == _FIS_DEFAULT_EMAIL or is_council_email(email):
                data.setdefault("extra", {})["council_email"] = email
            else:
                data["email"] = email

        website = clean_text(record.get("website", ""))
        if website:
            data["website"] = website

        area = clean_text(record.get("area", ""))
        if area:
            data["area"] = area

        age_groups = clean_text(record.get("age_groups", ""))
        if age_groups:
            data["age_range"] = age_groups

        if pt:
            data["provider_type"] = pt

        # Preserve council-specific IDs for the merge asset
        bristol_id = record.get("bristol_id", "")
        if bristol_id:
            data["council_bristol_id"] = bristol_id

        fis_url = clean_text(record.get("fis_url", ""))
        if fis_url:
            data["council_fis_url"] = fis_url

        source_url = clean_text(record.get("source_url", ""))
        if source_url:
            data["fis_url"] = source_url

        source_labels: list[str] = []
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
