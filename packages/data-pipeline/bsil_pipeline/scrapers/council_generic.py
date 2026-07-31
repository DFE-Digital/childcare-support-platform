"""Council-generic fallback scraper.

Covers ~211 LAs whose FIS URLs don't match any known platform. These
need individual classification and potentially custom handling.

Phase A: Classify each page (has directory / links to directory /
         inline providers / purely informational).
Phase B: Build sub-handlers based on classification results, or fall
         back to Ofsted cross-reference.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterator

from bsil_pipeline.scrapers.base import BaseScraper, ProviderResult

if TYPE_CHECKING:
    from logging import Logger


class CouncilGenericScraper(BaseScraper):
    @property
    def platform_key(self) -> str:
        return "council_generic"

    def scrape_la(
        self,
        lad25cd: str,
        fis_url: str,
        existing_provider_ids: set[str],
        logger: Logger,
    ) -> Iterator[ProviderResult]:
        """Stub — marks LA as unsupported until classification is done.

        TODO Phase 5-6:
        - Phase A: Visit URL with Playwright, classify page type
        - Phase B: Build targeted handlers or use Ofsted cross-reference
        """
        logger.info(
            f"Council generic stub for {lad25cd}: {fis_url} "
            f"(unsupported_platform until classified)"
        )
        yield ProviderResult(
            lad25cd=lad25cd,
            provider_id="__stub__",
            scrape_status="unsupported_platform",
            source_url=fis_url,
        )
