"""FISH (Family Information Service Hub) scraper.

FISH (East Riding) was discovered to be a Synergy deployment (v25.31.5816.21308).
This handler delegates to the Synergy scraper. The 'fish' platform key is kept
for backwards compatibility but classify_la() now routes FISH URLs to 'synergy'.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterator

from bsil_pipeline.scrapers.base import BaseScraper, ProviderResult

if TYPE_CHECKING:
    from logging import Logger


class FishScraper(BaseScraper):
    @property
    def platform_key(self) -> str:
        return "fish"

    def scrape_la(
        self,
        lad25cd: str,
        fis_url: str,
        existing_provider_ids: set[str],
        logger: Logger,
    ) -> Iterator[ProviderResult]:
        """Delegate to Synergy scraper — FISH is a Synergy deployment."""
        from bsil_pipeline.scrapers.synergy import SynergyScraper

        logger.info(f"FISH ({lad25cd}) is a Synergy deployment — delegating")
        synergy = SynergyScraper()
        yield from synergy.scrape_la(lad25cd, fis_url, existing_provider_ids, logger)
