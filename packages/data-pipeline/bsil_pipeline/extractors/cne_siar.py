"""Na h-Eileanan Siar (CnES) nursery directory extractor.

Extracts all fields from CnES LocalGov Drupal detail page HTML.
Address uses structured spans, coords from Drupal Leaflet settings JSON.
"""

from __future__ import annotations

from typing import Any

from bsil_pipeline.extractors.base import (
    BaseExtractor,
    ExtractedProvider,
    classify_provider_types,
    clean_text,
    extract_dt_dd,
    extract_email_from_soup,
    extract_latlon_drupal_settings,
    extract_phone_from_soup,
    parse_soup,
)


class CneSiarExtractor(BaseExtractor):
    @property
    def platform_key(self) -> str:
        return "cne_siar"

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

        # Name from h1 with class lgd-page-title-block__title
        h1 = soup.find("h1", class_="lgd-page-title-block__title")
        if not h1:
            h1 = soup.find("h1")
        data["provider_name"] = clean_text(h1.get_text()) if h1 else provider_name

        # Structured address spans
        for cls, key in [
            ("address-line1", "address_line1"),
            ("address-line2", "address_line2"),
            ("locality", "town"),
            ("postal-code", "postcode"),
        ]:
            span = soup.find("span", class_=cls)
            if span:
                val = clean_text(span.get_text())
                if val:
                    data[key] = val

        # Phone from localgov-directory-phone field
        phone_div = soup.find("div", class_="field--name-localgov-directory-phone")
        if phone_div:
            phone = extract_phone_from_soup(phone_div)
            if phone:
                data["phone"] = phone
        if not data.get("phone"):
            phone = extract_phone_from_soup(soup)
            if phone:
                data["phone"] = phone

        # Email from localgov-directory-email field
        email_div = soup.find("div", class_="field--name-localgov-directory-email")
        if email_div:
            email = extract_email_from_soup(email_div)
            if email:
                data["email"] = email
        if not data.get("email"):
            email = extract_email_from_soup(soup)
            if email:
                data["email"] = email

        # Lat/lon from Drupal settings JSON
        lat, lon = extract_latlon_drupal_settings(soup)
        if lat is not None:
            data["latitude"] = lat
        if lon is not None:
            data["longitude"] = lon

        # Extract any dt/dd pairs
        dd_pairs = extract_dt_dd(soup)
        extra: dict[str, str] = {}
        for label, value in dd_pairs.items():
            extra[label] = value
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
