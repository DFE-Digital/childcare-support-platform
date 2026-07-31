"""NE Lincolnshire FIS extractor.

Extracts all fields from Bootstrap modal HTML stored in raw_html.
Modals contain name in h5.modal-title, tel/mailto links, and
Cloudflare-encoded emails.
"""

from __future__ import annotations

import json
from typing import Any

from bsil_pipeline.extractors.base import (
    BaseExtractor,
    ExtractedProvider,
    classify_provider_types,
    clean_text,
    decode_cloudflare_email,
    extract_email_from_soup,
    extract_phone_from_soup,
    extract_postcode,
    is_council_email,
    parse_soup,
    validate_email,
)


class NelincsExtractor(BaseExtractor):
    @property
    def platform_key(self) -> str:
        return "nelincs"

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

        # Name from modal-title heading
        for tag in ("h5", "h4", "h3", "h2", "h1", "h6"):
            h = soup.find(tag, class_="modal-title")
            if h:
                data["provider_name"] = clean_text(h.get_text())
                break
        if not data.get("provider_name"):
            h1 = soup.find(["h1", "h2", "h3", "h4", "h5"])
            if h1:
                data["provider_name"] = clean_text(h1.get_text())
        if not data.get("provider_name"):
            data["provider_name"] = provider_name

        # Phone from tel: link
        phone = extract_phone_from_soup(soup)
        if phone:
            data["phone"] = phone

        # Email — try Cloudflare-encoded first, then mailto
        cf_span = soup.find("span", class_="__cf_email__")
        if cf_span and cf_span.get("data-cfemail"):
            decoded = decode_cloudflare_email(cf_span["data-cfemail"])
            if decoded:
                data["email"] = decoded.lower()

        if not data.get("email"):
            # Check for data-cfemail in <a> tags
            cf_link = soup.find("a", attrs={"data-cfemail": True})
            if cf_link:
                decoded = decode_cloudflare_email(cf_link["data-cfemail"])
                if decoded:
                    data["email"] = decoded.lower()

        if not data.get("email"):
            email = extract_email_from_soup(soup)
            if email:
                data["email"] = email

        # Validate email and filter council FIS inboxes
        if data.get("email"):
            email_val = data["email"]
            if not validate_email(email_val):
                data.setdefault("extra", {})["invalid_email"] = email_val
                del data["email"]
            elif is_council_email(email_val):
                data.setdefault("extra", {})["council_email"] = email_val
                del data["email"]

        # Address from <p> tags in modal body
        modal_body = soup.find(class_="modal-body") or soup
        for p in modal_body.find_all("p"):
            text = clean_text(p.get_text())
            if not text:
                continue
            # Split on newlines
            lines = [ln.strip() for ln in p.get_text().split("\n") if ln.strip()]
            for i, line in enumerate(lines):
                pc = extract_postcode(line)
                if pc:
                    data["postcode"] = pc
                    # Lines before are address
                    addr_lines = [ln.strip() for ln in lines[:i] if ln.strip()]
                    # Filter out name line
                    name = data.get("provider_name", "")
                    addr_lines = [ln for ln in addr_lines if ln != name]
                    if addr_lines:
                        data["address_line1"] = (
                            addr_lines[0] if len(addr_lines) >= 1 else None
                        )
                        data["town"] = addr_lines[-1] if len(addr_lines) >= 2 else None
                    break
            if data.get("postcode"):
                break

        # Collect any remaining structured data
        extra: dict[str, str] = {}
        # Look for any labelled content
        for strong in soup.find_all(["strong", "b"]):
            label = clean_text(strong.get_text())
            if not label:
                continue
            label_clean = label.rstrip(":").strip().lower()
            # Get next sibling text
            value_parts = []
            for sib in strong.next_siblings:
                if hasattr(sib, "name") and sib.name in ("strong", "b", "br"):
                    break
                txt = sib.get_text() if hasattr(sib, "get_text") else str(sib)
                txt = txt.strip().lstrip(":").strip()
                if txt:
                    value_parts.append(txt)
            value = clean_text(" ".join(value_parts))
            if label_clean and value:
                extra[label_clean] = value

        if extra:
            data["extra"] = extra

        if metadata_json:
            meta = (
                metadata_json
                if isinstance(metadata_json, dict)
                else json.loads(metadata_json)
            )
            search_cats = meta.get("search_categories", [])
            for cat in search_cats:
                if cat not in source_labels:
                    source_labels.append(cat)

        classification = classify_provider_types(source_labels)

        return ExtractedProvider(
            lad25cd=lad25cd,
            provider_id=provider_id,
            extracted_data=data,
            classification=classification,
            source_classification=source_labels,
            extraction_warnings=warnings,
        )
