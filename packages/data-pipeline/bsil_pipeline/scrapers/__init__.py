"""LA FIS scraper registry and URL classifier.

Maps each LA's FIS URL to the correct platform handler.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from bsil_pipeline.scrapers.base import BaseScraper


def classify_la(fis_url: str | None, lad25cd: str) -> str:
    """Classify an LA's FIS URL to a platform key.

    Returns one of the platform partition keys used by HANDLER_CLASSES.
    Checks are ordered from most specific to most general.
    """
    # Bath & North East Somerset — identified by LAD code because its FIS URL
    # (www.bathnes.gov.uk) doesn't point to the childcare directory; providers
    # are discovered via livewell.bathnes.gov.uk and stored in a separate table.
    if lad25cd == "E06000022":
        return "bath_ne_somerset"

    # South Gloucestershire — kb5 site behind Cloudflare; requires curl_cffi scraper.
    if lad25cd == "E06000025":
        return "south_gloucestershire"

    if not fis_url:
        return "council_generic"

    url_lower = fis_url.lower()
    parsed = urlparse(url_lower)
    domain = parsed.netloc
    path = parsed.path

    # OpenObjects kb5 — URL path contains /kb5/
    if "/kb5/" in path:
        return "openobjects_kb5"

    # Synergy — various URL patterns
    if "synergyweb" in path or "synergyweb" in domain:
        return "synergy"
    if "/synergy/" in path or "synergy." in domain:
        return "synergy"
    if "servelec-synergy.com" in domain:
        return "synergy"

    # fis.wales
    if "fis.wales" in domain:
        return "fis_wales"

    # Family Support NI
    if "familysupportni" in domain:
        return "familysupportni"

    # AFC info
    if "afcinfo.org.uk" in domain:
        return "afc"

    # FISH (East Riding) — actually a Synergy deployment
    if "fishwebsearch" in domain:
        return "synergy"

    # Swindon — uses Synergy (education.swindon.gov.uk/Synergy/SynergyWeb/)
    if "education.swindon.gov.uk" in domain:
        return "synergy"

    # Open Objects Marketplace — /Categories/ path pattern (Herts), 1space subdomain (East Sussex),
    # or communitydirectory subdomain (Norfolk)
    if "/categories/" in path:
        return "marketplace"
    if "1space." in domain:
        return "marketplace"
    if "communitydirectory." in domain:
        return "marketplace"

    # Jadu CMS — /directory/{number}/ pattern
    if re.search(r"/directory/\d+", path):
        return "jadu"

    # Essex CC FIS (JSON API)
    if "secureapps.essex.gov.uk" in domain:
        return "essex"

    # Devon CC FIS (findchildcareindevon.co.uk)
    if "findchildcareindevon" in domain:
        return "devon"

    # Surrey CC shared directory
    if "surreycc.gov.uk" in domain:
        return "surrey"

    # Hull Synergy (synergy in subdomain)
    if "synergy.hull" in domain:
        return "synergy"

    # Hackney Synergy
    if "synergy.hackney" in domain:
        return "synergy"

    # Doncaster FIS (Synergy under fis. subdomain)
    if "fis.doncaster" in domain:
        return "synergy"

    # Hounslow FSD (Synergy)
    if "fsd.hounslow" in domain:
        return "synergy"

    # FID — Family Information Directory (ASP.NET MVC)
    if "fid.cumberland" in domain:
        return "fid"
    if "familydirectory.northlincs" in domain:
        return "fid"
    if "fid.bexley" in domain:
        return "fid"

    # Hartlepool Family Hubs (Laravel/Vite with inline JSON)
    if "hartlepoolfamilyhubs" in domain:
        return "hartlepool"

    # PCG / PPL Innovate directories
    if "directory.westberks" in domain:
        return "pcg"
    if "fyi.bradford" in domain:
        return "pcg"
    if "sheffielddirectory" in domain:
        return "pcg"

    # Bristol City Council childcare directory (separate from Liquidlogic portal)
    if "bristol.gov.uk" in domain and "find-extended-hours" in path:
        return "bristol_council"

    # System C / Liquidlogic parent portals
    if "parent.bristol" in domain:
        return "liquidlogic"
    if "parentportal.wakefield" in domain:
        return "liquidlogic"

    # Lambeth FID (custom Drupal content type)
    if "lambeth.gov.uk" in domain:
        return "lambeth"

    # LocalGov Drupal Directories (JSON:API)
    if "dumfriesandgalloway.gov.uk" in domain:
        return "localgov_drupal"

    # Somerset childcare directory (WP REST API)
    if "somerset.gov.uk" in domain and (
        "childcare" in path or "childcare" in url_lower
    ):
        return "somerset"

    # NE Lincolnshire FIS (server-rendered modals)
    if "nelincs.gov.uk" in domain:
        return "nelincs"

    # Oldham childcare directory (WP Grid Builder)
    if "oldham.gov.uk" in domain:
        return "oldham"

    # East Ayrshire early years centres (static HTML table)
    if "east-ayrshire.gov.uk" in domain:
        return "eastayrshire"

    # Na h-Eileanan Siar (CnES) nursery directory (LocalGov Drupal HTML)
    if "cne-siar.gov.uk" in domain:
        return "cne_siar"

    # Blackpool FYI Directory (Contensis CMS REST API)
    if "fyidirectory.co.uk" in domain or "blackpool.gov.uk" in domain:
        return "blackpool"

    # North Yorkshire (ArcGIS Feature Service)
    if "northyorks.gov.uk" in domain:
        return "northyorks"

    # Fallback
    return "council_generic"


def _get_handler_classes() -> dict[str, type[BaseScraper]]:
    """Lazy import of handler classes to avoid circular imports."""
    from bsil_pipeline.scrapers.openobjects import OpenObjectsScraper
    from bsil_pipeline.scrapers.synergy import SynergyScraper
    from bsil_pipeline.scrapers.fis_wales import FisWalesScraper
    from bsil_pipeline.scrapers.familysupportni import FamilySupportNIScraper
    from bsil_pipeline.scrapers.afc import AfcScraper
    from bsil_pipeline.scrapers.fish import FishScraper
    from bsil_pipeline.scrapers.jadu import JaduScraper
    from bsil_pipeline.scrapers.surrey import SurreyScraper
    from bsil_pipeline.scrapers.essex import EssexScraper
    from bsil_pipeline.scrapers.devon import DevonScraper
    from bsil_pipeline.scrapers.marketplace import MarketplaceScraper
    from bsil_pipeline.scrapers.fid import FidScraper
    from bsil_pipeline.scrapers.hartlepool import HartlepoolScraper
    from bsil_pipeline.scrapers.pcg import PcgScraper
    from bsil_pipeline.scrapers.liquidlogic import LiquidlogicScraper
    from bsil_pipeline.scrapers.lambeth import LambethScraper
    from bsil_pipeline.scrapers.localgov_drupal import LocalGovDrupalScraper
    from bsil_pipeline.scrapers.somerset import SomersetScraper
    from bsil_pipeline.scrapers.nelincs import NelincsScraper
    from bsil_pipeline.scrapers.oldham import OldhamScraper
    from bsil_pipeline.scrapers.eastayrshire import EastAyrshireScraper
    from bsil_pipeline.scrapers.cne_siar import CneSiarScraper
    from bsil_pipeline.scrapers.blackpool import BlackpoolScraper
    from bsil_pipeline.scrapers.northyorks import NorthYorksScraper
    from bsil_pipeline.scrapers.council_generic import CouncilGenericScraper
    from bsil_pipeline.scrapers.bath_ne_somerset import BathNeSomersetScraper
    from bsil_pipeline.scrapers.south_gloucestershire import SouthGlosScraper
    from bsil_pipeline.scrapers.bristol_council import BristolCouncilScraper

    return {
        "openobjects_kb5": OpenObjectsScraper,
        "synergy": SynergyScraper,
        "fis_wales": FisWalesScraper,
        "familysupportni": FamilySupportNIScraper,
        "afc": AfcScraper,
        "fish": FishScraper,
        "jadu": JaduScraper,
        "surrey": SurreyScraper,
        "essex": EssexScraper,
        "devon": DevonScraper,
        "marketplace": MarketplaceScraper,
        "fid": FidScraper,
        "hartlepool": HartlepoolScraper,
        "pcg": PcgScraper,
        "liquidlogic": LiquidlogicScraper,
        "lambeth": LambethScraper,
        "localgov_drupal": LocalGovDrupalScraper,
        "somerset": SomersetScraper,
        "nelincs": NelincsScraper,
        "oldham": OldhamScraper,
        "eastayrshire": EastAyrshireScraper,
        "cne_siar": CneSiarScraper,
        "blackpool": BlackpoolScraper,
        "northyorks": NorthYorksScraper,
        "council_generic": CouncilGenericScraper,
        "bath_ne_somerset": BathNeSomersetScraper,
        "south_gloucestershire": SouthGlosScraper,
        "bristol_council": BristolCouncilScraper,
    }


def get_handler(platform_key: str, conn=None) -> BaseScraper:
    """Instantiate and return the scraper for the given platform key."""
    classes = _get_handler_classes()
    if platform_key not in classes:
        raise ValueError(f"Unknown platform key: {platform_key!r}")
    return classes[platform_key](conn=conn)
