"""Base classes and utilities for raw-data field extraction.

Each platform extractor reads raw_html or raw_json from la.scrape_results
and produces a structured ExtractedProvider with all discoverable fields.
"""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from bs4 import BeautifulSoup, Tag

# ---------------------------------------------------------------------------
# Care-type classification mapping
# ---------------------------------------------------------------------------

CARE_TYPE_ENUM = [
    "private_nursery",
    "school_based_nursery",
    "childminder",
    "breakfast_club",
    "free_breakfast_club",
    "after_school_club",
    "holiday_club",
]

# Maps lowercase source labels → our CareType enum values.
# Multiple source labels can map to the same enum value.
CARE_TYPE_MAPPING: dict[str, str] = {
    # childminder
    "childminder": "childminder",
    "childminders": "childminder",
    "childminding": "childminder",
    "child minder": "childminder",
    "approved childminder": "childminder",
    "registered childminder": "childminder",
    "childminder (domestic premises)": "childminder",
    # private nursery
    "day nursery": "private_nursery",
    "day nurseries": "private_nursery",
    "nursery": "private_nursery",
    "nurseries": "private_nursery",
    "pre-school": "private_nursery",
    "preschool": "private_nursery",
    "pre school": "private_nursery",
    "pre-school playgroup": "private_nursery",
    "playgroup": "private_nursery",
    "sessional day care": "private_nursery",
    "sessional care": "private_nursery",
    "full day care": "private_nursery",
    "full daycare": "private_nursery",
    "full time day care": "private_nursery",
    "private nursery": "private_nursery",
    "private day nursery": "private_nursery",
    "private nursery school": "private_nursery",
    "private, voluntary and independent nursery": "private_nursery",
    "voluntary nursery": "private_nursery",
    "community nursery": "private_nursery",
    "montessori": "private_nursery",
    "crèche": "private_nursery",
    "creche": "private_nursery",
    "childcare on non-domestic premises": "private_nursery",
    "childcare on domestic premises": "private_nursery",
    "meithrinfa dydd": "private_nursery",  # Welsh: day nursery
    "gofal dydd llawn": "private_nursery",  # Welsh: full day care
    "gofal dydd sesiynol": "private_nursery",  # Welsh: sessional day care
    "cylch meithrin": "private_nursery",  # Welsh: nursery circle / playgroup
    "grŵp chwarae": "private_nursery",  # Welsh: playgroup
    # school-based nursery
    "school nursery": "school_based_nursery",
    "school nursery class": "school_based_nursery",
    "nursery school": "school_based_nursery",
    "nursery class": "school_based_nursery",
    "maintained nursery": "school_based_nursery",
    "maintained nursery school": "school_based_nursery",
    "school based nursery": "school_based_nursery",
    "school-based nursery": "school_based_nursery",
    "local authority nursery": "school_based_nursery",
    "local authority nursery class": "school_based_nursery",
    "la nursery": "school_based_nursery",
    "reception class": "school_based_nursery",
    "school": "school_based_nursery",
    "infant school": "school_based_nursery",
    "primary school": "school_based_nursery",
    "independent school": "school_based_nursery",
    "special school": "school_based_nursery",
    "primary school nursery": "school_based_nursery",
    "school-based nurseries": "school_based_nursery",
    "nursery class at a maintained or academy school": "school_based_nursery",
    "nursery unit of independent sc": "school_based_nursery",  # truncated label
    "nursery unit of independent school": "school_based_nursery",
    "academy nursery": "school_based_nursery",
    "academy": "school_based_nursery",
    "maintained school": "school_based_nursery",
    "maintained schools": "school_based_nursery",
    "governor run": "school_based_nursery",
    "academy governor-run": "school_based_nursery",
    "academy governor run": "school_based_nursery",
    "nursery units of independent schools": "school_based_nursery",
    # breakfast club
    "breakfast club": "breakfast_club",
    "breakfast clubs": "breakfast_club",
    "clwb brecwast": "breakfast_club",  # Welsh
    # after school club
    "after school club": "after_school_club",
    "after-school club": "after_school_club",
    "after school care": "after_school_club",
    "registered after school care": "after_school_club",
    "out of school care": "after_school_club",
    "out of school club": "after_school_club",
    "out-of-school club": "after_school_club",
    "wrap around care": "after_school_club",
    "wraparound care": "after_school_club",
    "wrap-around care": "after_school_club",
    "before and after school club": "after_school_club",
    "before & after school club": "after_school_club",
    "clwb ar ôl ysgol": "after_school_club",  # Welsh
    "gofal cofleidiol": "after_school_club",  # Welsh: wraparound care
    "breakfast or after school club": "after_school_club",
    "before and after school": "after_school_club",
    "before & after school": "after_school_club",
    "out of school": "after_school_club",
    "out of school provision": "after_school_club",
    "clwb y tu allan i'r ysgol": "after_school_club",  # Welsh: out of school club
    # holiday club
    "holiday club": "holiday_club",
    "holiday clubs": "holiday_club",
    "holiday scheme": "holiday_club",
    "holiday playscheme": "holiday_club",
    "holiday play scheme": "holiday_club",
    "holiday care": "holiday_club",
    "holiday childcare": "holiday_club",
    "holiday provision": "holiday_club",
    "clwb gwyliau": "holiday_club",  # Welsh
    "holiday activity": "holiday_club",
    "holiday activities": "holiday_club",
    "holiday programme": "holiday_club",
    "holiday playschemes": "holiday_club",
    "haf": "holiday_club",  # Holiday Activities and Food programme
    # childminder — additional
    "home childcarer": "childminder",
    "home childcare": "childminder",
    "approved home childcarer": "childminder",
    "nanny": "childminder",
    # private nursery — additional
    "pre-school playgroups": "private_nursery",
    "sessional pre-school": "private_nursery",
    "full day care providers": "private_nursery",
    "day nursery / pre-school": "private_nursery",
    "pre-school / day nursery": "private_nursery",
    "childcare provider": "private_nursery",
    "childcare providers": "private_nursery",
    "carescheme": "private_nursery",
    # Welsh — additional
    "gwarchodwr plant": "childminder",  # Welsh: childminder
    "meithrinfa": "private_nursery",  # Welsh: nursery
    # Additional labels found in QA residual analysis
    "early years provider": "private_nursery",
    "early years": "private_nursery",
    "registered childminder (domestic premises)": "childminder",
    "registered childminder – domestic premises": "childminder",
    "childcare on non domestic premises": "private_nursery",
    "childcare on domestic premises (childminder)": "childminder",
    "nurseries and pre-schools": "private_nursery",
    "pre-school / playgroup": "private_nursery",
    "day care": "private_nursery",
    "creches": "private_nursery",
    "workplace nursery": "private_nursery",
    "workplace day nursery": "private_nursery",
    "home child carer": "childminder",
    "childcare in the home": "childminder",
    "babysitter": "childminder",
    "au pair": "childminder",
    "forest school": "private_nursery",
    "before school club": "after_school_club",
    "before school": "after_school_club",
    "before-school club": "after_school_club",
    "before and after school care": "after_school_club",
    "after-school care": "after_school_club",
    "out of school provision wrap around care": "after_school_club",
    "after school activities": "after_school_club",
    "summer club": "holiday_club",
    "holiday activity club": "holiday_club",
    "holiday childcare scheme": "holiday_club",
    "holiday activities and food": "holiday_club",
    "haf programme": "holiday_club",
    "free breakfast": "free_breakfast_club",
    "free breakfast club": "free_breakfast_club",
    "school run breakfast club": "breakfast_club",
    "nursery unit": "school_based_nursery",
    "nursery units": "school_based_nursery",
    "school nurseries": "school_based_nursery",
    "school based provision": "school_based_nursery",
    "school-based provision": "school_based_nursery",
    "foundation stage unit": "school_based_nursery",
    "early years foundation stage": "school_based_nursery",
    "eyfs": "school_based_nursery",
    "reception": "school_based_nursery",
    "special educational needs school": "school_based_nursery",
    "independent nursery school": "school_based_nursery",
    "free early education": "school_based_nursery",
    "state school": "school_based_nursery",
    # ArcGIS / NorthYorks layer types
    "other": None,  # skip unmappable "Other"
    # Contensis / Blackpool
    "early childhood development": "private_nursery",
    "day care setting": "private_nursery",
    # Phase 1 — unmapped labels from QA (>5 occurrences)
    "pre-school and playgroups": "private_nursery",
    "childminder agency": "childminder",
    "nursery classes": "school_based_nursery",
    "nursery schools": "school_based_nursery",
    "school - out of school care": "after_school_club",
    "baby & toddler group": "private_nursery",
    "childcare - domestic": "childminder",
    "la maintained schools": "school_based_nursery",
    # Non-childcare labels — map to None to suppress
    "family hub": None,
    "childrens centre": None,
    "children's centre": None,
    "children's centres": None,
    "study support": None,
    "open access play": None,
    "service": None,
    # FamilySupportNI compound / specific labels
    "parent & toddler": None,  # parent group, not formal childcare
    "parent and toddler": None,
    "parent and toddler group": None,
    "approved home childcare": "childminder",
    "2 year old programme": "private_nursery",
    "day nursery out of school": "private_nursery",
    "day nursery out of school summer scheme": "private_nursery",
    "day nursery out of school pre-school playgroup": "private_nursery",
    "day nursery out of school pre-school playgroup summer scheme": "private_nursery",
    "day nursery pre-school playgroup": "private_nursery",
    "day nursery summer scheme": "private_nursery",
    "out of school summer scheme": "holiday_club",
    "out of school pre-school playgroup": "after_school_club",
    "out of school pre-school playgroup summer scheme": "after_school_club",
    "pre-school playgroup summer scheme": "private_nursery",
    "statutory nursery school": "school_based_nursery",
    "unit": None,  # too generic
    # Disability/condition labels — not childcare types
    "disability - learning disability": None,
    "autism": None,
    "adhd disability - physical & sensory parent & toddler": None,
    # Devon — weekend/Saturday provision
    "saturday club": "holiday_club",
    "weekend club": "holiday_club",
    "holiday service": "holiday_club",
    "kindergarten": "private_nursery",
}


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Council FIS inbox emails that should NOT be stored as provider email.
# These are shared inboxes belonging to the council, not individual providers.
# Patterns match the LOCAL part (before @) at the START of the email.
# Using ^ anchors to avoid false positives like "caterpillar-childcare@live.co.uk".
_COUNCIL_EMAIL_PATTERNS: list[re.Pattern] = [
    re.compile(r"^fis@", re.IGNORECASE),
    re.compile(r"^familyinfo@", re.IGNORECASE),
    re.compile(r"^family\.info@", re.IGNORECASE),
    re.compile(r"^family\.information@", re.IGNORECASE),
    re.compile(r"^info\.families@", re.IGNORECASE),
    re.compile(r"^childcare@", re.IGNORECASE),
    re.compile(r"^earlyyears@", re.IGNORECASE),
    re.compile(r"^early\.years@", re.IGNORECASE),
    re.compile(r"^eycs@", re.IGNORECASE),
    re.compile(r"^(ask)?cyps@", re.IGNORECASE),
    re.compile(r"^children\.services@", re.IGNORECASE),
    re.compile(r"^childrensservices@", re.IGNORECASE),
    re.compile(r"^fsd@", re.IGNORECASE),
    re.compile(r"^familysupport@", re.IGNORECASE),
    re.compile(r"^family\.support@", re.IGNORECASE),
    re.compile(r"^families\.information@", re.IGNORECASE),
    re.compile(r"^housing\.allocations@", re.IGNORECASE),
    re.compile(r"^libraries@", re.IGNORECASE),
    re.compile(r"^libraryevents@", re.IGNORECASE),
    re.compile(r"^bookgroups@", re.IGNORECASE),
    re.compile(r"^lunchclubs@", re.IGNORECASE),
    re.compile(r"^youthinfo@", re.IGNORECASE),
    re.compile(r"^learn@", re.IGNORECASE),
]

# Known council email addresses that are FIS inboxes, not provider contacts
_COUNCIL_EMAIL_EXACT: set[str] = {
    "fis@nelincs.gov.uk",
    "fis@northlincs.gov.uk",
    "fis@northeastlincolnshire.gov.uk",
    "familysupportni@hscni.net",
    "family.information@familysupportni.gov.uk",
    "info.families@wokingham.gov.uk",
    "families.information@cumberland.gov.uk",
    "eycs@devon.gov.uk",
}


def validate_email(email: str | None) -> bool:
    """Check whether a string looks like a valid email address (*@*.*)."""
    if not email:
        return False
    return bool(_EMAIL_RE.match(email.strip()))


def is_council_email(email: str | None) -> bool:
    """Check whether an email address is a known council FIS inbox."""
    if not email:
        return False
    email_lower = email.strip().lower()
    if email_lower in _COUNCIL_EMAIL_EXACT:
        return True
    return any(pat.search(email_lower) for pat in _COUNCIL_EMAIL_PATTERNS)


def classify_provider_types(source_labels: list[str]) -> list[str]:
    """Map a list of source classification labels to CareType enum values.

    Returns deduplicated list preserving insertion order.
    """
    seen: set[str] = set()
    result: list[str] = []
    for label in source_labels:
        mapped = CARE_TYPE_MAPPING.get(label.lower().strip())
        if mapped is not None and mapped and mapped not in seen:
            seen.add(mapped)
            result.append(mapped)
    return result


# ---------------------------------------------------------------------------
# Name-based classification inference
# ---------------------------------------------------------------------------

# Ordered by specificity — specific multi-word patterns first, generic last.
# Each pattern maps to a single CareType value. Multiple patterns can match
# the same provider name (e.g. "ABC Nursery & After School Club" → both).
_NAME_INFERENCE_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Childminder — explicit keyword
    (re.compile(r"\bchildminder\b", re.I), "childminder"),
    (re.compile(r"\bchild\s*minding\b", re.I), "childminder"),
    (re.compile(r"\bgwarchodwr plant\b", re.I), "childminder"),  # Welsh
    # Wrap-around / out-of-school — before generic "school"
    (re.compile(r"\bbreakfast\s+club\b", re.I), "breakfast_club"),
    (re.compile(r"\bafter[\s-]*school\s*(club|care)\b", re.I), "after_school_club"),
    (re.compile(r"\bout[\s-]*of[\s-]*school\b", re.I), "after_school_club"),
    (re.compile(r"\bwrap[\s-]*around\b", re.I), "after_school_club"),
    (re.compile(r"\bholiday\s*(club|scheme|care|play)\b", re.I), "holiday_club"),
    # School-based nursery — "school" with nursery context
    (re.compile(r"\bnursery\s+school\b", re.I), "school_based_nursery"),
    (re.compile(r"\bnursery\s*(class|unit)\b", re.I), "school_based_nursery"),
    (re.compile(r"\bschool\s+nursery\b", re.I), "school_based_nursery"),
    (re.compile(r"\b(primary|infant|junior)\s+school\b", re.I), "school_based_nursery"),
    # School keyword + nursery keyword anywhere in name (either order)
    (
        re.compile(
            r"\b(primary|infants?|junior)\b.*\b(nursery|pre[\s-]*school|playgroup)\b",
            re.I,
        ),
        "school_based_nursery",
    ),
    (
        re.compile(
            r"\b(nursery|pre[\s-]*school|playgroup)\b.*\b(primary|infants?|junior)\b",
            re.I,
        ),
        "school_based_nursery",
    ),
    (
        re.compile(r"first school.*\b(nursery|pre[\s-]*school|playgroup)\b", re.I),
        "school_based_nursery",
    ),
    (
        re.compile(r"\b(nursery|pre[\s-]*school|playgroup)\b.*first school", re.I),
        "school_based_nursery",
    ),
    # Private nursery — generic patterns last
    (re.compile(r"\bday\s+nursery\b", re.I), "private_nursery"),
    (re.compile(r"\bpre[\s-]*school\b", re.I), "private_nursery"),
    (re.compile(r"\bplaygroup\b", re.I), "private_nursery"),
    (
        re.compile(r"(?<!school )\bnursery\b(?!\s*(class|unit))", re.I),
        "private_nursery",
    ),
    (re.compile(r"\bcr[eè]che\b", re.I), "private_nursery"),
    (re.compile(r"\bmontessori\b", re.I), "private_nursery"),
    (re.compile(r"\bcylch\s+meithrin\b", re.I), "private_nursery"),  # Welsh
    (re.compile(r"\bmeithrinfa\b", re.I), "private_nursery"),  # Welsh
]


def infer_classification_from_name(name: str | None) -> list[str]:
    """Infer care-type classification from provider name using regex patterns.

    Returns a deduplicated list of CareType values (may contain multiple
    if the name matches several patterns, e.g. "Nursery & After School Club").
    """
    if not name:
        return []
    seen: set[str] = set()
    result: list[str] = []
    for pattern, care_type in _NAME_INFERENCE_PATTERNS:
        if care_type not in seen and pattern.search(name):
            seen.add(care_type)
            result.append(care_type)
    # School context takes precedence over generic nursery match
    if "school_based_nursery" in seen and "private_nursery" in seen:
        result.remove("private_nursery")
    return result


# ---------------------------------------------------------------------------
# ExtractedProvider dataclass
# ---------------------------------------------------------------------------


@dataclass
class ExtractedProvider:
    """A fully extracted provider record from raw scrape data."""

    lad25cd: str
    provider_id: str
    extracted_data: dict[str, Any] = field(default_factory=dict)
    classification: list[str] = field(default_factory=list)
    source_classification: list[str] = field(default_factory=list)
    field_count: int = 0
    extraction_warnings: list[str] = field(default_factory=list)

    def __post_init__(self):
        self.field_count = self._count_fields()

    def _count_fields(self) -> int:
        """Count non-None, non-empty fields in extracted_data."""
        count = 0
        for k, v in self.extracted_data.items():
            if k == "extra":
                if isinstance(v, dict):
                    count += sum(
                        1
                        for ev in v.values()
                        if ev is not None and ev != "" and ev != []
                    )
            elif v is not None and v != "" and v != []:
                count += 1
        return count

    def as_db_row(self) -> dict:
        """Return a dict suitable for parameterised SQL insertion."""
        return {
            "lad25cd": self.lad25cd,
            "provider_id": self.provider_id,
            "platform": "",  # Set by caller
            "extracted_data": json.dumps(self.extracted_data),
            "classification": self.classification,
            "source_classification": self.source_classification,
            "field_count": self.field_count,
            "extraction_warnings": self.extraction_warnings,
            "lad_source": None,  # Set by caller
        }


# ---------------------------------------------------------------------------
# BaseExtractor ABC
# ---------------------------------------------------------------------------


class BaseExtractor(ABC):
    """Abstract base for platform-specific field extractors."""

    @abstractmethod
    def extract(
        self,
        lad25cd: str,
        provider_id: str,
        raw_html: str | None,
        raw_json: str | None,
        metadata_json: str | None,
        provider_name: str | None,
    ) -> ExtractedProvider:
        """Extract all available fields from the raw scrape data.

        Args:
            lad25cd: Local authority district code.
            provider_id: Provider ID from scrape_results.
            raw_html: Raw HTML from the provider's detail page (if stored).
            raw_json: Raw JSON from the provider's API response (if stored).
            metadata_json: Scraper-generated context (e.g. search categories).
            provider_name: Provider name from scrape_results (fallback).
        """
        ...

    @property
    @abstractmethod
    def platform_key(self) -> str:
        """Return the platform key (must match scrapers registry)."""
        ...


# ---------------------------------------------------------------------------
# Shared utility helpers
# ---------------------------------------------------------------------------

_POSTCODE_RE = re.compile(r"[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}", re.IGNORECASE)
_POSTCODE_DISTRICT_RE = re.compile(r"\b[A-Z]{1,2}\d[A-Z\d]?\b", re.IGNORECASE)


def clean_text(text: str | None) -> str | None:
    """Strip whitespace, collapse internal runs, return None if empty."""
    if text is None:
        return None
    cleaned = " ".join(text.split())
    return cleaned if cleaned else None


def strip_html_tags(text: str | None) -> str | None:
    """Remove HTML tags from text, returning clean plaintext."""
    if not text:
        return None
    soup = BeautifulSoup(text, "html.parser")
    cleaned = soup.get_text(separator=" ")
    return clean_text(cleaned)


def extract_postcode(text: str | None) -> str | None:
    """Extract a UK postcode from text. Returns the first match or None."""
    if not text:
        return None
    m = _POSTCODE_RE.search(text)
    return m.group(0).strip() if m else None


def extract_postcode_district(text: str | None) -> str | None:
    """Extract a UK postcode district (outward code only, e.g. 'BS15') from text.

    Only call when extract_postcode returns None — used as a lower-confidence
    fallback for providers that only publish their district.
    """
    if not text:
        return None
    m = _POSTCODE_DISTRICT_RE.search(text)
    return m.group(0).upper().strip() if m else None


def parse_soup(html: str) -> BeautifulSoup:
    """Parse HTML string into a BeautifulSoup object."""
    return BeautifulSoup(html, "html.parser")


def extract_dt_dd(
    soup: BeautifulSoup | Tag, scope: Tag | None = None
) -> dict[str, str]:
    """Extract all <dt>/<dd> pairs from HTML as {label: value}.

    Labels are lowercased and stripped. Values are cleaned text.
    If scope is provided, only search within that element.
    """
    container = scope or soup
    pairs: dict[str, str] = {}
    for dt in container.find_all("dt"):
        label = clean_text(dt.get_text())
        if not label:
            continue
        dd = dt.find_next_sibling("dd")
        if dd:
            value = clean_text(dd.get_text())
            if value:
                pairs[label.rstrip(":").strip().lower()] = value
    return pairs


def extract_table_rows(
    soup: BeautifulSoup | Tag, scope: Tag | None = None
) -> dict[str, str]:
    """Extract all <th>/<td> pairs from table rows as {label: value}.

    Handles tables where each row has a header cell and a data cell.
    """
    container = scope or soup
    pairs: dict[str, str] = {}
    for tr in container.find_all("tr"):
        th = tr.find("th")
        td = tr.find("td")
        if th and td:
            label = clean_text(th.get_text())
            value = clean_text(td.get_text())
            if label and value:
                pairs[label.rstrip(":").strip().lower()] = value
    return pairs


def extract_strong_text_pairs(
    soup: BeautifulSoup | Tag, scope: Tag | None = None
) -> dict[str, str]:
    """Extract <strong>Label:</strong> Value or <b>Label:</b> Value pairs.

    Returns {lowercase_label: value}.
    """
    container = scope or soup
    pairs: dict[str, str] = {}
    for strong_tag in container.find_all(["strong", "b"]):
        label_text = clean_text(strong_tag.get_text())
        if not label_text:
            continue
        # Strip trailing colon
        label = label_text.rstrip(":").strip().lower()
        # Value is the next sibling text or the parent's remaining text
        value_parts = []
        for sibling in strong_tag.next_siblings:
            if isinstance(sibling, Tag) and sibling.name in ("strong", "b", "br"):
                break
            txt = sibling.get_text() if isinstance(sibling, Tag) else str(sibling)
            txt = txt.strip().lstrip(":").strip()
            if txt:
                value_parts.append(txt)
        value = clean_text(" ".join(value_parts))
        if label and value:
            pairs[label] = value
    return pairs


def extract_labelled_spans(
    soup: BeautifulSoup | Tag, label_class: str, value_class: str
) -> dict[str, str]:
    """Extract pairs of <span class="label_class">Label</span> <span class="value_class">Value</span>.

    Used for Synergy eyo-data-label / eyo-data-field patterns.
    """
    pairs: dict[str, str] = {}
    for label_span in soup.find_all("span", class_=label_class):
        label = clean_text(label_span.get_text())
        if not label:
            continue
        label = label.rstrip(":").strip().lower()
        # Look for the value span — either next sibling or parent's next child
        value_span = label_span.find_next_sibling("span", class_=value_class)
        if not value_span:
            # Try parent level
            parent = label_span.parent
            if parent:
                value_span = parent.find("span", class_=value_class)
        if value_span:
            value = clean_text(value_span.get_text())
            if value:
                pairs[label] = value
    return pairs


def walk_json_keys(data: dict | list, prefix: str = "") -> dict[str, Any]:
    """Flatten a nested JSON structure into dot-separated key paths.

    Returns {key_path: leaf_value} for all non-None, non-empty leaf values.
    """
    result: dict[str, Any] = {}
    if isinstance(data, dict):
        for k, v in data.items():
            full_key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, (dict, list)):
                result.update(walk_json_keys(v, full_key))
            elif v is not None and v != "" and v != []:
                result[full_key] = v
    elif isinstance(data, list):
        for i, item in enumerate(data):
            full_key = f"{prefix}[{i}]"
            if isinstance(item, (dict, list)):
                result.update(walk_json_keys(item, full_key))
            elif item is not None and item != "" and item != []:
                result[full_key] = item
    return result


def extract_email_from_soup(soup: BeautifulSoup | Tag) -> str | None:
    """Extract the first email address from mailto: links in the soup."""
    mailto = soup.find("a", href=re.compile(r"^mailto:", re.IGNORECASE))
    if mailto:
        href = mailto.get("href", "")
        email = href.split("mailto:", 1)[-1].split("?")[0].strip()
        return email if email else None
    return None


def extract_phone_from_soup(soup: BeautifulSoup | Tag) -> str | None:
    """Extract the first phone number from tel: links in the soup."""
    tel = soup.find("a", href=re.compile(r"^tel:", re.IGNORECASE))
    if tel:
        href = tel.get("href", "")
        phone = href.split("tel:", 1)[-1].strip()
        return clean_text(phone) if phone else None
    return None


def extract_latlon_drupal_settings(
    soup: BeautifulSoup,
) -> tuple[float | None, float | None]:
    """Extract lat/lon from Drupal settings JSON (Leaflet map features).

    Used by Lambeth, CnES, and other Drupal sites.
    """
    script = soup.find("script", {"data-drupal-selector": "drupal-settings-json"})
    if not script or not script.string:
        return None, None
    try:
        settings = json.loads(script.string)
        for _map_id, map_data in settings.get("leaflet", {}).items():
            features = map_data.get("features", [])
            if features:
                feat = features[0]
                lat = feat.get("lat")
                lon = feat.get("lon")
                if lat is not None and lon is not None:
                    return float(lat), float(lon)
    except (json.JSONDecodeError, TypeError, ValueError, KeyError):
        pass
    return None, None


def decode_cloudflare_email(encoded: str) -> str | None:
    """Decode Cloudflare-obfuscated email (XOR cipher).

    The data-cfemail attribute contains hex-encoded bytes where the first
    byte is the XOR key and subsequent bytes are XOR'd email characters.
    """
    try:
        key = int(encoded[:2], 16)
        decoded = ""
        for i in range(2, len(encoded), 2):
            decoded += chr(int(encoded[i : i + 2], 16) ^ key)
        return decoded if decoded else None
    except (ValueError, IndexError):
        return None


def map_to_canonical(
    raw_pairs: dict[str, str],
    label_map: dict[str, str],
) -> tuple[dict[str, Any], dict[str, str]]:
    """Map raw label/value pairs to canonical field keys.

    Args:
        raw_pairs: {lowercase_label: value} from HTML extraction.
        label_map: {lowercase_label: canonical_key} mapping.

    Returns:
        (canonical_fields, extra_fields) — canonical fields use standard
        keys, extra captures anything not in the label_map.
    """
    canonical: dict[str, Any] = {}
    extra: dict[str, str] = {}
    for label, value in raw_pairs.items():
        canonical_key = label_map.get(label)
        if canonical_key:
            canonical[canonical_key] = value
        else:
            extra[label] = value
    return canonical, extra
