"""South Gloucestershire extractor.

The life.southglos.gov.uk directory is a standard OpenObjects kb5 portal
with two South Glos-specific quirks:

- Opening hours label is "When is it on" (alongside the standard "Opening Times")
- Emails are Cloudflare-obfuscated via <span class="__cf_email__" data-cfemail="...">
"""

import json
from typing import Any

from bsil_pipeline.extractors.base import (
    ExtractedProvider,
    classify_provider_types,
    decode_cloudflare_email,
    parse_soup,
    validate_email,
    is_council_email,
)
from bsil_pipeline.extractors.openobjects import OpenObjectsExtractor


_FIS_DEFAULT_EMAIL = "cis@southglos.gov.uk"
_FIS_DEFAULT_PHONE = "01454 868008"


class SouthGlosExtractor(OpenObjectsExtractor):
    @property
    def platform_key(self) -> str:
        return "south_gloucestershire"

    def extract(
        self,
        lad25cd: str,
        provider_id: str,
        raw_html: str | None,
        raw_json: str | None,
        metadata_json: str | None,
        provider_name: str | None,
    ) -> ExtractedProvider:
        result = super().extract(
            lad25cd, provider_id, raw_html, raw_json, metadata_json, provider_name
        )

        # Merge search categories from scraper metadata into classification
        if metadata_json:
            meta = (
                metadata_json
                if isinstance(metadata_json, dict)
                else json.loads(metadata_json)
            )
            search_cats = meta.get("search_categories", [])
            if search_cats:
                merged_labels = list(result.source_classification) + search_cats
                merged_classification = classify_provider_types(merged_labels)
                if set(merged_classification) != set(result.classification):
                    result = ExtractedProvider(
                        lad25cd=result.lad25cd,
                        provider_id=result.provider_id,
                        extracted_data=dict(result.extracted_data),
                        classification=merged_classification,
                        source_classification=merged_labels,
                        extraction_warnings=list(result.extraction_warnings),
                    )

        if not raw_html:
            return result

        data: dict[str, Any] = dict(result.extracted_data)
        warnings = list(result.extraction_warnings)

        if data.get("email") == _FIS_DEFAULT_EMAIL:
            data["email"] = None
        if (data.get("phone") or "").replace(" ", "") == _FIS_DEFAULT_PHONE.replace(
            " ", ""
        ):
            data["phone"] = None
        soup = parse_soup(raw_html)

        # Opening hours: South Glos uses "When is it on" in addition to
        # the standard "Opening Times" label handled by OpenObjectsExtractor.
        if not data.get("opening_hours_raw"):
            for dt in soup.find_all("dt"):
                if dt.get_text(strip=True).lower() == "when is it on":
                    dd = dt.find_next_sibling("dd")
                    if dd:
                        from bsil_pipeline.extractors.base import clean_text

                        data["opening_hours_raw"] = clean_text(dd.get_text())
                    break

        # Email: Cloudflare obfuscates emails as
        # <span class="__cf_email__" data-cfemail="...">
        if not data.get("email"):
            for span in soup.find_all("span", class_="__cf_email__"):
                encoded = span.get("data-cfemail")
                if encoded:
                    decoded = decode_cloudflare_email(encoded)
                    if (
                        decoded
                        and validate_email(decoded)
                        and not is_council_email(decoded)
                        and decoded != _FIS_DEFAULT_EMAIL
                    ):
                        data["email"] = decoded
                        break

        return ExtractedProvider(
            lad25cd=result.lad25cd,
            provider_id=result.provider_id,
            extracted_data=data,
            classification=result.classification,
            source_classification=result.source_classification,
            extraction_warnings=warnings,
        )
