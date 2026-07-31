"""East Ayrshire early years centres extractor.

East Ayrshire doesn't store raw_html (data comes from a single listing page).
This extractor works from provider_name only as a minimal fallback.
"""

from __future__ import annotations

from typing import Any

from bsil_pipeline.extractors.base import (
    BaseExtractor,
    ExtractedProvider,
    classify_provider_types,
)


class EastAyrshireExtractor(BaseExtractor):
    @property
    def platform_key(self) -> str:
        return "eastayrshire"

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

        # East Ayrshire doesn't store raw data
        warnings.append("no raw data stored (single listing page scraper)")

        if provider_name:
            data["provider_name"] = provider_name

        return ExtractedProvider(
            lad25cd=lad25cd,
            provider_id=provider_id,
            extracted_data=data,
            classification=[],
            source_classification=[],
            extraction_warnings=warnings,
        )
