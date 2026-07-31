"""Bath & NE Somerset extractor.

Re-parses raw_html stored in la.scrape_results using BathNeSomersetScraper._parse_provider().
"""

from __future__ import annotations

from typing import Any

from bsil_pipeline.scrapers.bath_ne_somerset import BathNeSomersetScraper
from bsil_pipeline.extractors.base import (
    BaseExtractor,
    ExtractedProvider,
    classify_provider_types,
    clean_text,
)


class BathNeSomersetExtractor(BaseExtractor):
    @property
    def platform_key(self) -> str:
        return "bath_ne_somerset"

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

        scraper = BathNeSomersetScraper()
        # Use source_url as a placeholder — _parse_provider only needs url for
        # the result dict's "url" key which we don't use here.
        parsed = scraper._parse_provider(
            f"https://livewell.bathnes.gov.uk/{provider_id}", raw_html
        )

        if parsed.get("name"):
            data["provider_name"] = clean_text(parsed["name"])
        elif provider_name:
            data["provider_name"] = provider_name

        if parsed.get("phone"):
            data["phone"] = clean_text(parsed["phone"])
        if parsed.get("email"):
            data["email"] = clean_text(parsed["email"])
        if parsed.get("website"):
            data["website"] = clean_text(parsed["website"])
        if parsed.get("address_line1"):
            data["address_line1"] = clean_text(parsed["address_line1"])
        if parsed.get("city"):
            data["town"] = clean_text(parsed["city"])
        if parsed.get("postcode"):
            data["postcode"] = clean_text(parsed["postcode"])
        if parsed.get("institution_type"):
            data["provider_type"] = clean_text(parsed["institution_type"])
            source_labels.append(parsed["institution_type"])
        if parsed.get("registered_places") is not None:
            data["places_total"] = parsed["registered_places"]
        if parsed.get("ofsted_number"):
            data["ofsted_urn"] = clean_text(parsed["ofsted_number"])
        if parsed.get("eligible_age_range"):
            data["age_range"] = clean_text(parsed["eligible_age_range"])
        if parsed.get("opening_hours_raw"):
            data["opening_hours_raw"] = clean_text(parsed["opening_hours_raw"])

        classification = classify_provider_types(source_labels)

        return ExtractedProvider(
            lad25cd=lad25cd,
            provider_id=provider_id,
            extracted_data=data,
            classification=classification,
            source_classification=source_labels,
            extraction_warnings=warnings,
        )
