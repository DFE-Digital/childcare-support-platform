"""Base classes and utilities for LA FIS scrapers."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Iterator

if TYPE_CHECKING:
    from logging import Logger


POSTCODE_RE = re.compile(r"[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}$", re.IGNORECASE)


@dataclass
class ProviderResult:
    """A single scraped childcare provider record."""

    lad25cd: str
    provider_id: str
    provider_name: str | None = None
    provider_address_line1: str | None = None
    provider_address_line2: str | None = None
    provider_address_line3: str | None = None
    provider_town: str | None = None
    provider_postcode: str | None = None
    provider_urn: str | None = None
    provider_phone: str | None = None
    provider_email: str | None = None
    provider_latitude: float | None = None
    provider_longitude: float | None = None
    source_url: str | None = None
    raw_html: str | None = None
    raw_json: str | None = None
    metadata_json: str | None = None
    scrape_status: str = "error"

    def as_db_row(self) -> dict:
        """Return a dict suitable for parameterised SQL insertion."""
        return {
            "lad25cd": self.lad25cd,
            "provider_id": self.provider_id,
            "provider_name": self.provider_name,
            "provider_address_line1": self.provider_address_line1,
            "provider_address_line2": self.provider_address_line2,
            "provider_address_line3": self.provider_address_line3,
            "provider_town": self.provider_town,
            "provider_postcode": self.provider_postcode,
            "provider_urn": self.provider_urn,
            "provider_phone": self.provider_phone,
            "provider_email": self.provider_email,
            "provider_latitude": self.provider_latitude,
            "provider_longitude": self.provider_longitude,
            "source_url": self.source_url,
            "raw_html": self.raw_html,
            "raw_json": self.raw_json,
            "metadata_json": self.metadata_json,
            "scrape_status": self.scrape_status,
        }


class BaseScraper(ABC):
    """Abstract base for platform-specific scrapers."""

    def __init__(self, conn=None):
        self.conn = conn

    @abstractmethod
    def scrape_la(
        self,
        lad25cd: str,
        fis_url: str,
        existing_provider_ids: set[str],
        logger: Logger,
    ) -> Iterator[ProviderResult]:
        """Yield ProviderResult for each provider found on the LA's FIS page.

        Args:
            lad25cd: Local authority district code.
            fis_url: The FIS URL from la.family_information_services.
            existing_provider_ids: Provider IDs already in scrape_results for
                this LA (for incremental scraping).
            logger: Dagster context logger.
        """
        ...

    @property
    @abstractmethod
    def platform_key(self) -> str:
        """Return the platform partition key (e.g. 'openobjects_kb5')."""
        ...


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def clean_text(text: str | None) -> str | None:
    """Strip whitespace and collapse internal runs of whitespace."""
    if text is None:
        return None
    cleaned = " ".join(text.split())
    return cleaned if cleaned else None


def parse_address_parts(
    address_text: str,
) -> dict[str, str | None]:
    """Split a comma-separated address string into structured parts.

    Returns dict with keys: address_line1, address_line2, address_line3,
    town, postcode.
    """
    result: dict[str, str | None] = {
        "address_line1": None,
        "address_line2": None,
        "address_line3": None,
        "town": None,
        "postcode": None,
    }

    parts = [p.strip() for p in address_text.split(",") if p.strip()]
    if not parts:
        return result

    # Check if last part is a postcode
    if POSTCODE_RE.search(parts[-1]):
        result["postcode"] = parts[-1].strip()
        parts = parts[:-1]

    # Town is the last remaining part
    if parts:
        result["town"] = parts[-1]
        parts = parts[:-1]

    # Remaining parts are address lines
    if len(parts) >= 1:
        result["address_line1"] = parts[0]
    if len(parts) >= 2:
        result["address_line2"] = parts[1]
    if len(parts) >= 3:
        result["address_line3"] = ", ".join(parts[2:])

    return result
