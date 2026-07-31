"""Oldham childcare directory extractor.

Extracts all fields from Oldham Oxygen Builder detail page HTML
stored in raw_html.
"""

from __future__ import annotations

import re
from typing import Any

from bsil_pipeline.extractors.base import (
    BaseExtractor,
    ExtractedProvider,
    classify_provider_types,
    clean_text,
    extract_email_from_soup,
    extract_phone_from_soup,
    extract_postcode,
    parse_soup,
)


class OldhamExtractor(BaseExtractor):
    @property
    def platform_key(self) -> str:
        return "oldham"

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

        # Name from <h1>
        h1 = soup.find("h1")
        data["provider_name"] = clean_text(h1.get_text()) if h1 else provider_name

        # Email from mailto link
        email = extract_email_from_soup(soup)
        if email:
            data["email"] = email

        # Phone — try tel: link first
        phone = extract_phone_from_soup(soup)
        if phone:
            data["phone"] = phone
        else:
            # Fallback: SVG phone icon → sibling ct-span
            for use_tag in soup.find_all("use"):
                href = use_tag.get("xlink:href", "") or use_tag.get("href", "")
                if "phone" in href.lower():
                    # Navigate up to find text
                    parent = use_tag
                    for _ in range(5):
                        parent = parent.parent
                        if not parent:
                            break
                    if parent:
                        span = parent.find("span", class_="ct-span")
                        if span:
                            data["phone"] = clean_text(span.get_text())
                    break

        # Address from Location section
        for heading in soup.find_all(["h2", "h3"]):
            if "location" in (clean_text(heading.get_text()) or "").lower():
                # Walk up to parent, find ct-text-block divs
                section = heading.parent
                if section:
                    for text_block in section.find_all("div", class_="ct-text-block"):
                        text = clean_text(text_block.get_text())
                        if not text:
                            continue
                        lines = [
                            ln.strip()
                            for ln in text_block.get_text().split("\n")
                            if ln.strip()
                        ]
                        for i, line in enumerate(lines):
                            pc = extract_postcode(line)
                            if pc:
                                data["postcode"] = pc
                                addr_lines = lines[:i]
                                if addr_lines:
                                    data["address_line1"] = (
                                        addr_lines[0] if len(addr_lines) >= 1 else None
                                    )
                                    if len(addr_lines) >= 2:
                                        data["address_line2"] = addr_lines[1]
                                    if len(addr_lines) >= 3:
                                        data["town"] = addr_lines[-1]
                                break
                    break

        # Ofsted URN from reports.ofsted.gov.uk link
        for a in soup.find_all("a", href=re.compile(r"reports\.ofsted\.gov\.uk")):
            urn_match = re.search(
                r"reports\.ofsted\.gov\.uk/provider/\d+/(\d+)", a["href"]
            )
            if urn_match:
                data["ofsted_urn"] = urn_match.group(1)
                break

        # Collect extra content from ct-text-block divs
        extra: dict[str, str] = {}
        for heading in soup.find_all(["h2", "h3"]):
            section_name = clean_text(heading.get_text())
            if not section_name or section_name.lower() == "location":
                continue
            section = heading.parent
            if section:
                blocks = section.find_all("div", class_="ct-text-block")
                for block in blocks:
                    text = clean_text(block.get_text())
                    if text:
                        extra[section_name.lower()] = text
                        break

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
