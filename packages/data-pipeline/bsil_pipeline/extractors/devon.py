"""Devon CC FIS extractor.

Extracts fields from Devon detail page HTML (raw_html) and/or the
structured metadata dict (raw_json).
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
    extract_dt_dd,
    extract_email_from_soup,
    extract_phone_from_soup,
    extract_postcode,
    parse_soup,
)

# Devon County Council HQ — appears on most detail pages as the contact
# address but is NOT the provider's address.
_DEVON_CC_HQ_POSTCODE = "EX2 4QD"
_ADDRESS_LABELS = {"address", "full address", "postal address", "location"}


def _normalise_postcode(pc: str) -> str:
    """Uppercase and ensure single space before inward code."""
    pc = re.sub(r"\s+", "", pc.strip().upper())
    if len(pc) >= 5:
        return pc[:-3] + " " + pc[-3:]
    return pc


class DevonExtractor(BaseExtractor):
    @property
    def platform_key(self) -> str:
        return "devon"

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

        # Start with JSON metadata if available
        if raw_json:
            try:
                meta = json.loads(raw_json)
                if meta.get("name"):
                    data["provider_name"] = clean_text(meta["name"])
                if meta.get("latitude"):
                    data["latitude"] = float(meta["latitude"])
                if meta.get("longitude"):
                    data["longitude"] = float(meta["longitude"])
                if meta.get("phone"):
                    data["phone"] = clean_text(meta["phone"])
                if meta.get("email"):
                    data["email"] = clean_text(meta["email"])
                # Collect extra keys
                extra_meta: dict[str, Any] = {}
                for k, v in meta.items():
                    if k not in (
                        "name",
                        "latitude",
                        "longitude",
                        "phone",
                        "email",
                        "provider_id",
                        "service_id",
                        "detail_url",
                    ):
                        if v is not None and v != "":
                            extra_meta[k] = v
                if extra_meta:
                    data["extra"] = extra_meta
            except json.JSONDecodeError:
                warnings.append("raw_json parse error")

        # Parse HTML detail page
        if raw_html:
            soup = parse_soup(raw_html)

            h1 = soup.find("h1")
            if h1 and not data.get("provider_name"):
                data["provider_name"] = clean_text(h1.get_text())

            # Extract all labelled pairs
            all_pairs: dict[str, str] = {}
            # From <li><span>Label:</span> or <li><b>Label:</b>
            for li in soup.find_all("li"):
                label_el = li.find(["span", "b", "strong"])
                if not label_el:
                    continue
                label = clean_text(label_el.get_text()) or ""
                label_clean = label.rstrip(":").strip().lower()
                full_text = clean_text(li.get_text()) or ""
                value = re.sub(
                    r"^" + re.escape(label) + r"\s*:?\s*",
                    "",
                    full_text,
                    flags=re.IGNORECASE,
                ).strip()
                if label_clean and value:
                    all_pairs[label_clean] = value

            dd_pairs = extract_dt_dd(soup)
            for k, v in dd_pairs.items():
                if k not in all_pairs:
                    all_pairs[k] = v

            # Devon detail pages often show the council's HQ address
            # (Devon County Council, County Hall, EX2 4QD) rather than the
            # provider's own address.  We extract postcodes from address
            # fields but filter out the known council HQ postcode.
            _LABEL_MAP = {
                "telephone": "phone",
                "phone": "phone",
                "email": "email",
                "website": "website",
                "type": "provider_type",
                "provider type": "provider_type",
                "ofsted urn": "ofsted_urn",
                "ofsted rating": "ofsted_rating",
                "age range": "age_range",
                "opening hours": "opening_hours_raw",
                "fees": "fees_raw",
                "description": "description",
            }

            extra = data.get("extra", {}) if isinstance(data.get("extra"), dict) else {}
            for label, value in all_pairs.items():
                canonical = _LABEL_MAP.get(label)
                if canonical:
                    data.setdefault(canonical, value)
                else:
                    extra[label] = value

            # Extract postcode from address fields in extra, skipping
            # the council HQ postcode that appears on most pages.
            if not data.get("postcode"):
                for addr_key in _ADDRESS_LABELS:
                    addr_raw = extra.get(addr_key)
                    if not addr_raw:
                        continue
                    pc = extract_postcode(addr_raw)
                    if not pc:
                        continue
                    normalised = _normalise_postcode(pc)
                    if normalised == _DEVON_CC_HQ_POSTCODE:
                        if "county hall" in addr_raw.lower():
                            continue
                        warnings.append(
                            f"skipped postcode {normalised} — matches council HQ"
                        )
                        continue
                    data["postcode"] = normalised
                    # Parse comma-separated address, removing postcode
                    # and council parts
                    parts = [p.strip() for p in addr_raw.split(",") if p.strip()]
                    parts = [p for p in parts if extract_postcode(p) != pc]
                    parts = [
                        p
                        for p in parts
                        if "county hall" not in p.lower()
                        and "devon county council" not in p.lower()
                    ]
                    if parts:
                        data.setdefault("town", parts[-1])
                        parts = parts[:-1]
                    if len(parts) >= 1:
                        data.setdefault("address_line1", parts[0])
                    if len(parts) >= 2:
                        data.setdefault("address_line2", ", ".join(parts[1:]))
                    break

            if not data.get("email"):
                email = extract_email_from_soup(soup)
                if email and email != "eycs@devon.gov.uk":
                    data["email"] = email
            if not data.get("phone"):
                phone = extract_phone_from_soup(soup)
                if phone:
                    data["phone"] = phone

            if extra:
                data["extra"] = extra

        if not data.get("provider_name"):
            data["provider_name"] = provider_name

        # Devon names often use "Name - Type" format (e.g. "Brewer, Kelly -
        # Childminder").  Extract the type suffix as a source label — same
        # pattern as fis_wales.py.  Keep full name for display.
        name = data.get("provider_name") or ""
        if " - " in name:
            parts = name.rsplit(" - ", 1)
            if len(parts) == 2:
                type_suffix = parts[1].strip()
                if type_suffix:
                    source_labels.append(type_suffix)

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
