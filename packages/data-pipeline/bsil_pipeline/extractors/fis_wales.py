"""FIS Wales extractor.

Extracts all fields from FIS Wales detail page HTML stored in raw_html.
Detail pages use panel wrappers for address + contact info with
icon-based (<i class="fa-*">) markers for phone and email.
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
    extract_phone_from_soup,
    extract_postcode,
    extract_strong_text_pairs,
    parse_soup,
    validate_email,
)

_POSTCODE_RE = re.compile(r"[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}", re.IGNORECASE)
# Matches fee-amount keys like "£60.00", "£3.50", "£100"
_FEE_RE = re.compile(r"^£\d")


class FisWalesExtractor(BaseExtractor):
    @property
    def platform_key(self) -> str:
        return "fis_wales"

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

        # Provider name and type from card-header h2
        header = soup.find("h2", class_=re.compile(r"card-header"))
        if header:
            raw_name = clean_text(header.get_text())
            if raw_name and " - " in raw_name:
                name_part, type_part = raw_name.rsplit(" - ", 1)
                data["provider_name"] = name_part.strip()
                data["provider_type"] = type_part.strip()
                source_labels.append(type_part.strip())
            else:
                data["provider_name"] = raw_name
            # Extract CSS class for type hint (bg-childminder, bg-daynursery, etc.)
            css_classes = " ".join(header.get("class", []))
            bg_match = re.search(r"bg-(\w+)", css_classes)
            if bg_match:
                data["extra"] = data.get("extra", {})
                data.setdefault("extra", {})["css_type"] = bg_match.group(1)
        else:
            data["provider_name"] = provider_name

        # Address from visit/postal panels
        for panel_id in ("pnlVisitAddressWrapper", "pnlPostalAddressWrapper"):
            panel = soup.find(id=panel_id)
            if not panel:
                continue
            p_tag = panel.find("p")
            if not p_tag:
                continue
            lines = _extract_br_lines(p_tag)
            if not lines:
                continue

            # Parse address lines
            pc = None
            if lines and _POSTCODE_RE.search(lines[-1]):
                pc = lines[-1].strip().upper()
                lines = lines[:-1]
            if pc and not data.get("postcode"):
                data["postcode"] = pc
            if lines:
                data.setdefault("town", lines[-1])
                lines = lines[:-1]
            if len(lines) >= 1:
                data.setdefault("address_line1", lines[0])
            if len(lines) >= 2:
                data.setdefault("address_line2", lines[1])
            if len(lines) >= 3:
                data.setdefault("address_line3", ", ".join(lines[2:]))

            # Store panel type
            addr_type = "visit" if "Visit" in panel_id else "postal"
            data[f"address_type_{addr_type}"] = True
            if data.get("postcode"):
                break

        # Phone from fa-phone icon
        phone_icon = soup.find("i", class_=re.compile(r"fa-phone"))
        if phone_icon:
            parent = phone_icon.parent
            if parent:
                text = clean_text(parent.get_text())
                if text:
                    phone_match = re.search(r"[\d\s\-\(\)\+]{7,}", text)
                    if phone_match:
                        data["phone"] = clean_text(phone_match.group())

        # Email from fa-envelope icon
        email_icon = soup.find("i", class_=re.compile(r"fa-envelope"))
        if email_icon:
            parent = email_icon.parent
            if parent:
                mailto = parent.find("a", href=re.compile(r"^mailto:", re.IGNORECASE))
                if mailto:
                    email_text = clean_text(mailto.get_text())
                    if email_text and "@" in email_text:
                        data["email"] = email_text.lower()
                    else:
                        href = mailto.get("href", "")
                        if href.startswith("mailto:"):
                            data["email"] = href[7:].split("?")[0].lower()

        # Fallback email/phone from links
        if not data.get("email"):
            email = extract_email_from_soup(soup)
            if email:
                data["email"] = email
        if not data.get("phone"):
            phone = extract_phone_from_soup(soup)
            if phone:
                data["phone"] = phone

        # Validate email format — names and placeholders sometimes end up here
        if data.get("email") and not validate_email(data["email"]):
            data.setdefault("extra", {})["invalid_email"] = data["email"]
            del data["email"]

        # Extract any dt/dd and strong/text pairs on the page
        dd_pairs = extract_dt_dd(soup)
        strong_pairs = extract_strong_text_pairs(soup)

        # FIS Wales detail pages use <strong> tags for school names
        # (e.g. <strong>School Name</strong> - Location) and fee amounts
        # (e.g. <strong>£60.00</strong> (Day):).  Extract these as
        # structured lists instead of letting them pollute extra{}.
        schools_served: list[str] = []
        fees_structured: list[str] = []
        filtered_strong: dict[str, str] = {}
        for label, value in strong_pairs.items():
            if _FEE_RE.match(label):
                fee_entry = f"{label} {value}".rstrip(":").strip()
                if fee_entry:
                    fees_structured.append(fee_entry)
            elif value.startswith("- ") or value.startswith("\u2013 "):
                school_entry = f"{label} {value}".strip()
                if school_entry:
                    schools_served.append(school_entry)
            else:
                filtered_strong[label] = value

        _LABEL_MAP = {
            "telephone": "phone",
            "phone": "phone",
            "email": "email",
            "website": "website",
            "ofsted": "ofsted_urn",
            "cssiw": "cssiw_ref",
            "csiw": "cssiw_ref",
            "care inspectorate wales": "cssiw_ref",
            "type": "provider_type",
            "type of childcare": "provider_type",
            "age range": "age_range",
            "number of places": "places_total",
            "vacancies": "places_available",
            "opening hours": "opening_hours_raw",
            "opening times": "opening_hours_raw",
            "fees": "fees_raw",
            "description": "description",
            "languages": "languages_raw",
            "welsh medium": "welsh_medium",
        }

        extra = data.get("extra", {}) if isinstance(data.get("extra"), dict) else {}
        for pairs_dict in (dd_pairs, filtered_strong):
            for label, value in pairs_dict.items():
                canonical = _LABEL_MAP.get(label)
                if canonical:
                    data.setdefault(canonical, value)
                else:
                    extra[label] = value

        if schools_served:
            data["schools_served"] = schools_served
        if fees_structured:
            data["fees_structured"] = fees_structured
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


def _extract_br_lines(element) -> list[str]:
    """Extract text lines from an element with <br> separators."""
    lines: list[str] = []
    current = ""
    for child in element.children:
        if child.name == "br":
            text = clean_text(current)
            if text:
                lines.append(text)
            current = ""
        elif hasattr(child, "get_text"):
            current += child.get_text()
        else:
            current += str(child)
    text = clean_text(current)
    if text:
        lines.append(text)
    return lines
