"""Extractor registry — maps platform_key to ExtractorClass.

Mirrors the scrapers/__init__.py pattern. Each platform that stores
raw_html or raw_json in la.scrape_results has a corresponding extractor
that can re-parse that content into structured fields.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bsil_pipeline.extractors.base import BaseExtractor


def _get_extractor_classes() -> dict[str, type[BaseExtractor]]:
    """Lazy import of extractor classes to avoid circular imports."""
    from bsil_pipeline.extractors.openobjects import OpenObjectsExtractor
    from bsil_pipeline.extractors.synergy import SynergyExtractor
    from bsil_pipeline.extractors.marketplace import MarketplaceExtractor
    from bsil_pipeline.extractors.essex import EssexExtractor
    from bsil_pipeline.extractors.surrey import SurreyExtractor
    from bsil_pipeline.extractors.fis_wales import FisWalesExtractor
    from bsil_pipeline.extractors.familysupportni import FamilySupportNIExtractor
    from bsil_pipeline.extractors.jadu import JaduExtractor
    from bsil_pipeline.extractors.devon import DevonExtractor
    from bsil_pipeline.extractors.fid import FidExtractor
    from bsil_pipeline.extractors.afc import AfcExtractor
    from bsil_pipeline.extractors.pcg import PcgExtractor
    from bsil_pipeline.extractors.liquidlogic import LiquidlogicExtractor
    from bsil_pipeline.extractors.lambeth import LambethExtractor
    from bsil_pipeline.extractors.localgov_drupal import LocalGovDrupalExtractor
    from bsil_pipeline.extractors.somerset import SomersetExtractor
    from bsil_pipeline.extractors.nelincs import NelincsExtractor
    from bsil_pipeline.extractors.oldham import OldhamExtractor
    from bsil_pipeline.extractors.eastayrshire import EastAyrshireExtractor
    from bsil_pipeline.extractors.cne_siar import CneSiarExtractor
    from bsil_pipeline.extractors.blackpool import BlackpoolExtractor
    from bsil_pipeline.extractors.northyorks import NorthYorksExtractor
    from bsil_pipeline.extractors.hartlepool import HartlepoolExtractor
    from bsil_pipeline.extractors.bath_ne_somerset import BathNeSomersetExtractor
    from bsil_pipeline.extractors.south_gloucestershire import SouthGlosExtractor
    from bsil_pipeline.extractors.bristol_council import BristolCouncilExtractor

    return {
        "openobjects_kb5": OpenObjectsExtractor,
        "synergy": SynergyExtractor,
        "marketplace": MarketplaceExtractor,
        "essex": EssexExtractor,
        "surrey": SurreyExtractor,
        "fis_wales": FisWalesExtractor,
        "familysupportni": FamilySupportNIExtractor,
        "jadu": JaduExtractor,
        "devon": DevonExtractor,
        "fid": FidExtractor,
        "afc": AfcExtractor,
        "pcg": PcgExtractor,
        "liquidlogic": LiquidlogicExtractor,
        "lambeth": LambethExtractor,
        "localgov_drupal": LocalGovDrupalExtractor,
        "somerset": SomersetExtractor,
        "nelincs": NelincsExtractor,
        "oldham": OldhamExtractor,
        "eastayrshire": EastAyrshireExtractor,
        "cne_siar": CneSiarExtractor,
        "blackpool": BlackpoolExtractor,
        "northyorks": NorthYorksExtractor,
        "hartlepool": HartlepoolExtractor,
        "bath_ne_somerset": BathNeSomersetExtractor,
        "south_gloucestershire": SouthGlosExtractor,
        "bristol_council": BristolCouncilExtractor,
    }


# Platforms that don't store raw data and thus have no extractor.
# council_generic yields scrape_status="unsupported_platform" with no raw data.
# eastayrshire doesn't store raw_html (data comes from single listing page).
# localgov_drupal skips raw_json to save space.
PLATFORMS_WITHOUT_RAW_DATA = {"council_generic"}


def get_extractor(platform_key: str) -> BaseExtractor:
    """Instantiate and return the extractor for the given platform key."""
    classes = _get_extractor_classes()
    if platform_key not in classes:
        raise ValueError(f"No extractor for platform key: {platform_key!r}")
    return classes[platform_key]()


def has_extractor(platform_key: str) -> bool:
    """Check whether an extractor exists for the given platform key."""
    return platform_key in _get_extractor_classes()
