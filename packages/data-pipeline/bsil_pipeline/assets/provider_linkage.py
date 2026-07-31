"""Dagster asset linking LA-scraped providers to Ofsted inspections,
DfE school census, and the free breakfast club programme.

One table: draft.linkage — all providers get Ofsted columns;
school-typed providers also get school-census columns.

Ofsted match tiers (first match wins):
  1. urn_exact              — cleaned ofsted_urn exists in ofsted.inspections
  2. postcode_name          — same postcode + name similarity >= 0.80
  2b. postcode_name_stripped — same postcode + name after stripping qualifiers >= 0.80
  2c. postcode_ofsted_venue  — same postcode, LA name vs Ofsted "Operator @ Venue" >= 0.80
  3. postcode_address       — same postcode + address_line1 similarity >= 0.80
  —  not_applicable         — non-England LA (Scotland/Wales/NI)
  —  unmatched              — no match found

School match tiers (school-typed providers only; first match wins):
  1. urn_exact              — ofsted_urn exists in dfe.school_census
  2. postcode_name          — same postcode + name similarity >= 0.80
  2b. postcode_name_venue   — operator prefix stripped + postcode + name (clubs only)
  3. postcode_addr_name     — same postcode + LA address vs school name >= 0.80
  4. postcode_addr_prefix   — same postcode + LA address prefix vs school name >= 0.85
  5. postcode_address       — same postcode + address similarity >= 0.80 (needs GIAS)
  6. la_name                — LA-scope name match >= 0.92 (no-postcode providers only)
  8. national_name          — nationally unique normalised name (no-postcode only)
  7. coord_proximity        — Haversine distance <= 500m via GIAS/la_places coords
  —  not_applicable         — non-England LA
  —  unmatched              — no match found
"""

import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from dagster import asset, AssetExecutionContext, MetadataValue

from bsil_pipeline.automation import PIPELINE_CONDITION
from bsil_pipeline.resources.postgres import BsilPostgresResource

# ---------- normalisation helpers ----------

_LEGAL_SUFFIXES = re.compile(
    r"\b(ltd|limited|cic|cio|llp|plc|inc|co|company|group|uk)\b", re.IGNORECASE
)
_STRIP_LEADING_THE = re.compile(r"^the\s+", re.IGNORECASE)
_PUNCTUATION = re.compile(r"[\-,.()/]")
_WHITESPACE = re.compile(r"\s+")

_ABBREV = [
    # Yorkshire composite school-type abbreviations (most specific first)
    (re.compile(r"\bJ\s+I\s*&\s*N\b", re.IGNORECASE), "junior infant and nursery"),
    (re.compile(r"\bJ\s+I\s+and\s+N\b", re.IGNORECASE), "junior infant and nursery"),
    (re.compile(r"\bI\s*&\s*N\b", re.IGNORECASE), "infant and nursery"),
    (re.compile(r"\bI\s+and\s+N\b", re.IGNORECASE), "infant and nursery"),
    (re.compile(r"\bJ\s*&\s*I\b", re.IGNORECASE), "junior and infant"),
    # Church/faith school abbreviations
    (re.compile(r"\bC\.?\s*of\s*E\.?\b", re.IGNORECASE), "church of england"),
    (re.compile(r"\bCofE\b", re.IGNORECASE), "church of england"),
    (re.compile(r"\bCoE\b", re.IGNORECASE), "church of england"),
    (re.compile(r"(?<!\w)CE(?!\w)", re.IGNORECASE), "church of england"),
    (re.compile(r"\bR\.?C\.?\b", re.IGNORECASE), "roman catholic"),
    # Common word abbreviations
    (re.compile(r"\bSt\b\.?", re.IGNORECASE), "saint"),
    (re.compile(r"\bPrim\b\.?", re.IGNORECASE), "primary"),
    (re.compile(r"\bInf\b\.?", re.IGNORECASE), "infant"),
    (re.compile(r"\bJun\b\.?", re.IGNORECASE), "junior"),
    (re.compile(r"\bAcad\b\.?", re.IGNORECASE), "academy"),
    (re.compile(r"\bVol\.?\s*Aid\.?\b", re.IGNORECASE), "voluntary aided"),
    (re.compile(r"\bVA\b", re.IGNORECASE), "voluntary aided"),
    (re.compile(r"\bVC\b", re.IGNORECASE), "voluntary controlled"),
]


def expand_abbreviations(name: str) -> str:
    for pattern, replacement in _ABBREV:
        name = pattern.sub(replacement, name)
    return name


_POSTCODE_RE = re.compile(
    r"^\s*([A-Z]{1,2}\d[A-Z\d]?)\s*(\d[A-Z]{2})\s*$", re.IGNORECASE
)


def normalise_name(name: str | None) -> str:
    if not name:
        return ""
    s = name.lower().strip()
    s = expand_abbreviations(s)
    s = _STRIP_LEADING_THE.sub("", s)
    s = _LEGAL_SUFFIXES.sub("", s)
    s = s.replace("'", "")
    s = s.replace("&", " and ")
    s = _PUNCTUATION.sub(" ", s)
    s = _WHITESPACE.sub(" ", s).strip()
    return s


def normalise_postcode(pc: str | None) -> str:
    if not pc:
        return ""
    m = _POSTCODE_RE.match(pc.strip())
    if m:
        return f"{m.group(1).upper()} {m.group(2).upper()}"
    return pc.strip().upper()


# ---------- Ofsted name cleaning helpers ----------

# PCG scraper appends category labels to provider names
_LA_NAME_SUFFIX = re.compile(
    r"\s*-\s*"
    r"(?:Before\s*[&]\s*After\s+School\s+Care\s*-\s*)?"
    r"(?:Childminders\s+and\s+)?Childcare\s+providers\s*$",
    re.IGNORECASE,
)

# Strip trailing "Link to latest Ofsted inspection report" from URN fields
_URN_EXTRACT = re.compile(r"^(EY\d+|\d+)", re.IGNORECASE)

# Tier 2b: strip parenthetical qualifiers and trailing care-type words
_LA_BRACKET_QUALIFIER = re.compile(r"\s*\([^)]+\)\s*$")
_LA_TRAILING_CARE = re.compile(
    r"\s*[-\u2013\u2014]?\s*"
    r"(?:Breakfast\s+Club|After[- ]School\s+Club|Holiday\s+Club"
    r"|Out\s+of\s+School\s+Club|Nursery\s+Class|Day\s+Nursery"
    r"|Pre[- ]?School|Wrap[- ]?Around\s+Care|After\s+School\s+Service"
    r"|Holiday\s+Scheme|Holiday\s+Play\s*[Ss]cheme|OOS|Out\s+of\s+School)\s*$",
    re.IGNORECASE,
)

# Tier 2c: extract venue from "Operator @ Venue" Ofsted names
_OFSTED_AT = re.compile(r"@\s*(.+)$")


def _clean_la_name(name: str | None) -> str | None:
    """Strip known scraper-appended category labels from LA provider names."""
    if not name:
        return name
    return _LA_NAME_SUFFIX.sub("", name).strip() or name


def _strip_la_qualifiers(name: str | None) -> str | None:
    """Strip parenthetical and trailing care-type qualifiers.

    Returns the stripped name if it differs from the original, else None.
    """
    if not name:
        return None
    result = _LA_BRACKET_QUALIFIER.sub("", name).strip()
    result = _LA_TRAILING_CARE.sub("", result).strip()
    return result if result and result != name else None


def _clean_urn(raw: str | None) -> str | None:
    """Extract just the URN from a raw extracted_data ofsted_urn field."""
    if not raw:
        return raw
    m = _URN_EXTRACT.match(raw.strip())
    return m.group(1) if m else raw.strip()


# ---------- School suffix stripping ----------

_CARE_SUFFIX = re.compile(
    r"\s*[-\u2013\u2014]\s*("
    r"nursery|breakfast club|after school club|after-school club"
    r"|wrap[ -]?around care|wraparound care|holiday club"
    r"|out of school club|kids club|childcare"
    r"|before\s*[&]\s*after\s+school\s+care|before\s+and\s+after\s+school\s+care"
    r"|before\s+school\s+care|after\s+school\s+care"
    r")\s*$",
    re.IGNORECASE,
)

_TRAILING_CARE_PHRASE = re.compile(
    r"\s+("
    r"nursery class|nursery unit|nursery provision"
    r"|breakfast club|after[- ]?school club|holiday club"
    r"|out of school club|kids club"
    r"|wraparound care|wrap[ -]?around care"
    r"|childminders and childcare providers|childcare"
    r")\s*$",
    re.IGNORECASE,
)

_SCHOOL_TYPE_WORDS = {
    "school",
    "academy",
    "primary",
    "infant",
    "junior",
    "first",
    "middle",
}

# Superset used by _strip_school_words for coord_proximity name comparison.
# Removes generic words that inflate SequenceMatcher ratio between unrelated
# school names (e.g. "newtown primary school" vs "brook street primary school").
_SCHOOL_GENERIC_WORDS = _SCHOOL_TYPE_WORDS | {
    "infants",
    "juniors",
    "nursery",
    "secondary",
    "high",
    "college",
    "cofe",
    "ce",
    "rc",
    "va",
    "vc",
    "voluntary",
    "aided",
    "controlled",
    "community",
    "church",
    "england",
    "catholic",
    "saint",
    "st",
    "the",
    "of",
    "and",
}


def _strip_school_words(name_norm: str) -> str:
    """Remove generic school-type words from a normalised name for coord_proximity comparison."""
    return " ".join(w for w in name_norm.split() if w not in _SCHOOL_GENERIC_WORDS)


def strip_care_suffix(name: str) -> str:
    """Strip trailing care-type suffixes from provider names, applied iteratively."""
    if not name:
        return name
    result = name
    for _ in range(4):
        prev = result
        result = _CARE_SUFFIX.sub("", result)
        result = _TRAILING_CARE_PHRASE.sub("", result)
        stripped = result.rstrip()
        if stripped.lower().endswith(" nursery"):
            prefix = stripped[: -len(" nursery")]
            if prefix:
                words = prefix.rsplit(None, 1)
                if words and words[-1].lower() in _SCHOOL_TYPE_WORDS:
                    result = prefix
        if result == prev:
            break
    return result


_AT_SYMBOL = re.compile(r"@\s*(.+)$")
_AT_WORD = re.compile(
    r"\bat\s+(.+(?:school|academy|primary|infants?|juniors?|college|centre|church)\b.*)",
    re.IGNORECASE,
)


def _extract_venue_name(name: str | None) -> str | None:
    """Extract the host venue name from operator-prefixed club names."""
    if not name:
        return None
    m = _AT_SYMBOL.search(name)
    if m:
        return m.group(1).strip()
    m = _AT_WORD.search(name)
    if m:
        return m.group(1).strip()
    return None


# ---------- data classes ----------


@dataclass
class OfstedRecord:
    provider_urn: str
    provider_name: str | None
    registered_person_name: str | None
    postcode: str
    address_line1: str | None
    name_norm: str = ""
    registered_norm: str = ""
    addr_norm: str = ""
    venue_norm: str = ""  # normalised venue from "Operator @ Venue" names

    def __post_init__(self):
        self.name_norm = normalise_name(self.provider_name)
        self.registered_norm = normalise_name(self.registered_person_name)
        self.addr_norm = normalise_name(self.address_line1)
        m = _OFSTED_AT.search(self.provider_name or "")
        self.venue_norm = normalise_name(m.group(1)) if m else ""


@dataclass
class SchoolRecord:
    urn: str
    school_name: str | None
    postcode: str
    establishment_type: str | None
    phase_type: str | None
    address_line1: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    name_norm: str = field(init=False)
    addr_norm: str = field(init=False)

    def __post_init__(self):
        self.name_norm = normalise_name(self.school_name)
        self.addr_norm = normalise_name(self.address_line1)


# ---------- constants ----------

_NON_ENGLAND_PREFIXES = ("S", "W", "N")

_SCHOOL_TYPES = [
    "school_based_nursery",
    "breakfast_club",
    "after_school_club",
    "holiday_club",
]

_CLUB_TYPES = frozenset(("after_school_club", "breakfast_club", "holiday_club"))

BATCH_SIZE = 500
NAME_THRESHOLD = 0.80
ADDR_THRESHOLD = 0.80
PREFIX_THRESHOLD = 0.85
MIN_PREFIX_LEN = 10
LA_NAME_THRESHOLD = 0.92
COORD_PROXIMITY_M = 500.0
COORD_NAME_THRESHOLD = 0.40


# ---------- Ofsted matching ----------


def _best_name_match(
    la_name_norm: str, candidates: list[OfstedRecord]
) -> tuple[OfstedRecord | None, float]:
    best_rec = None
    best_ratio = 0.0
    for rec in candidates:
        for ofsted_norm in (rec.name_norm, rec.registered_norm):
            if not ofsted_norm:
                continue
            ratio = SequenceMatcher(None, la_name_norm, ofsted_norm).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_rec = rec
    if best_ratio >= NAME_THRESHOLD:
        return best_rec, best_ratio
    return None, 0.0


def _best_venue_match(
    la_name_norm: str, candidates: list[OfstedRecord]
) -> tuple[OfstedRecord | None, float]:
    """Match LA name against the venue part of Ofsted 'Operator @ Venue' names."""
    best_rec = None
    best_ratio = 0.0
    for rec in candidates:
        if not rec.venue_norm:
            continue
        ratio = SequenceMatcher(None, la_name_norm, rec.venue_norm).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_rec = rec
    if best_ratio >= NAME_THRESHOLD:
        return best_rec, best_ratio
    return None, 0.0


def _best_addr_match(
    la_addr_norm: str, candidates: list[OfstedRecord]
) -> tuple[OfstedRecord | None, float]:
    best_rec = None
    best_ratio = 0.0
    for rec in candidates:
        if not rec.addr_norm:
            continue
        ratio = SequenceMatcher(None, la_addr_norm, rec.addr_norm).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_rec = rec
    if best_ratio >= ADDR_THRESHOLD:
        return best_rec, best_ratio
    return None, 0.0


# ---------- School matching ----------


def _best_school_name_match(
    la_name_norm: str,
    candidates: list[SchoolRecord],
    threshold: float = NAME_THRESHOLD,
) -> tuple[SchoolRecord | None, float]:
    best_rec = None
    best_ratio = 0.0
    for rec in candidates:
        if not rec.name_norm:
            continue
        ratio = SequenceMatcher(None, la_name_norm, rec.name_norm).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_rec = rec
    if best_ratio >= threshold:
        return best_rec, best_ratio
    return None, 0.0


def _best_school_subset_match(
    la_name_norm: str,
    candidates: list[SchoolRecord],
    threshold: float = NAME_THRESHOLD,
) -> tuple[SchoolRecord | None, float]:
    """Match where all words of the shorter name appear in the longer name."""
    la_words = set(la_name_norm.split())
    if not la_words:
        return None, 0.0
    best_rec = None
    best_ratio = 0.0
    for rec in candidates:
        if not rec.name_norm:
            continue
        c_words = set(rec.name_norm.split())
        if not c_words:
            continue
        if la_words <= c_words or c_words <= la_words:
            ratio = SequenceMatcher(None, la_name_norm, rec.name_norm).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_rec = rec
    if best_rec and best_ratio >= threshold:
        return best_rec, best_ratio
    return None, 0.0


def _best_school_prefix_match(
    la_addr_norm: str, candidates: list[SchoolRecord]
) -> tuple[SchoolRecord | None, float]:
    """Match the start of a normalised LA address against school names."""
    best_rec = None
    best_ratio = 0.0
    for rec in candidates:
        if not rec.name_norm:
            continue
        n = len(rec.name_norm)
        if n < MIN_PREFIX_LEN:
            continue
        if len(la_addr_norm) <= n:
            continue
        prefix = la_addr_norm[:n]
        ratio = SequenceMatcher(None, prefix, rec.name_norm).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_rec = rec
    if best_ratio >= PREFIX_THRESHOLD:
        return best_rec, best_ratio
    return None, 0.0


def _best_school_addr_match(
    la_addr_norm: str, candidates: list[SchoolRecord]
) -> tuple[SchoolRecord | None, float]:
    best_rec = None
    best_ratio = 0.0
    for rec in candidates:
        if not rec.addr_norm:
            continue
        ratio = SequenceMatcher(None, la_addr_norm, rec.addr_norm).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_rec = rec
    if best_ratio >= ADDR_THRESHOLD:
        return best_rec, best_ratio
    return None, 0.0


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000
    φ1, φ2 = math.radians(lat1), math.radians(lat2)
    dφ = math.radians(lat2 - lat1)
    dλ = math.radians(lon2 - lon1)
    a = math.sin(dφ / 2) ** 2 + math.cos(φ1) * math.cos(φ2) * math.sin(dλ / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def _pick_classification(classification: list[str] | None) -> str | None:
    """Pick the highest-priority school-related type from the classification list."""
    if not classification:
        return None
    for t in _SCHOOL_TYPES:
        if t in classification:
            return t
    return None


# ---------- SQL ----------

CREATE_SCHEMA_SQL = "CREATE SCHEMA IF NOT EXISTS draft"

DROP_TABLE_SQL = "DROP TABLE IF EXISTS draft.linkage"

CREATE_TABLE_SQL = """
CREATE TABLE draft.linkage (
    lad25cd                  TEXT NOT NULL,
    provider_id              TEXT NOT NULL,
    ofsted_urn               TEXT,
    school_urn               TEXT,
    is_free_breakfast_school BOOLEAN DEFAULT FALSE,
    metadata                 JSONB NOT NULL DEFAULT '{}',
    linked_at                TIMESTAMP DEFAULT now(),
    PRIMARY KEY (lad25cd, provider_id)
)
"""

UPSERT_SQL = """
INSERT INTO draft.linkage (
    lad25cd, provider_id, ofsted_urn, school_urn,
    is_free_breakfast_school, metadata
) VALUES (
    %(lad25cd)s, %(provider_id)s, %(ofsted_urn)s, %(school_urn)s,
    %(is_free_breakfast_school)s, %(metadata)s
)
ON CONFLICT (lad25cd, provider_id) DO UPDATE SET
    ofsted_urn               = EXCLUDED.ofsted_urn,
    school_urn               = EXCLUDED.school_urn,
    is_free_breakfast_school  = EXCLUDED.is_free_breakfast_school,
    metadata                 = EXCLUDED.metadata,
    linked_at                = now()
"""


# ---------- Dagster asset ----------


@asset(
    group_name="draft",
    deps=[
        "la_extract_results",
        "ofsted_inspections",
        "school_census",
        "gias_schools",
        "la_places_geocode",
        "free_breakfast_club_schools",
    ],
    automation_condition=PIPELINE_CONDITION,
)
def provider_linkage(
    context: AssetExecutionContext, bsil_postgres: BsilPostgresResource
):
    """Link LA-scraped providers to Ofsted inspections, DfE school census,
    and the free breakfast club programme into a single draft.linkage table.
    """

    with bsil_postgres.get_connection() as conn:
        # ---- Create schema and table (fresh each run) ----
        with conn.cursor() as cur:
            cur.execute(CREATE_SCHEMA_SQL)
            cur.execute(DROP_TABLE_SQL)
            cur.execute(CREATE_TABLE_SQL)
            conn.commit()

        # ---- Load Ofsted data ----
        context.log.info("Loading Ofsted records...")

        with conn.cursor() as cur:
            cur.execute(
                "SELECT EXISTS ("
                "  SELECT 1 FROM information_schema.tables"
                "  WHERE table_schema = 'ofsted' AND table_name = 'scrape_results'"
                ")"
            )
            has_scrape_results = cur.fetchone()[0]

        if has_scrape_results:
            ofsted_sql = """
                SELECT i.provider_urn,
                       CASE WHEN i.provider_name = 'REDACTED' AND sr.provider_name IS NOT NULL
                            THEN sr.provider_name ELSE i.provider_name END AS provider_name,
                       i.registered_person_name,
                       COALESCE(NULLIF(NULLIF(i.provider_postcode, ''), 'REDACTED'), sr.provider_postcode) AS postcode,
                       COALESCE(NULLIF(NULLIF(i.provider_address_line_1, ''), 'REDACTED'), sr.provider_address_line1)
                           AS address_line1
                FROM ofsted.inspections i
                LEFT JOIN ofsted.scrape_results sr
                    ON i.provider_urn = sr.provider_urn
                    AND sr.scrape_status IN ('success', 'partial')
            """
        else:
            context.log.info("ofsted.scrape_results not found — using inspections only")
            ofsted_sql = """
                SELECT provider_urn, provider_name, registered_person_name,
                       provider_postcode, provider_address_line_1
                FROM ofsted.inspections
            """

        by_urn_ofsted: dict[str, OfstedRecord] = {}
        by_postcode_ofsted: dict[str, list[OfstedRecord]] = defaultdict(list)

        with conn.cursor() as cur:
            cur.execute(ofsted_sql)
            for urn, name, reg_name, pc, addr in cur:
                if not urn:
                    continue
                norm_pc = normalise_postcode(pc)
                rec = OfstedRecord(
                    provider_urn=urn,
                    provider_name=name,
                    registered_person_name=reg_name,
                    postcode=norm_pc,
                    address_line1=addr,
                )
                by_urn_ofsted[urn] = rec
                if norm_pc:
                    by_postcode_ofsted[norm_pc].append(rec)

        context.log.info(
            f"Loaded {len(by_urn_ofsted)} Ofsted records, "
            f"{len(by_postcode_ofsted)} unique postcodes"
        )

        # ---- Load school census data ----
        context.log.info("Loading school census records...")

        with conn.cursor() as cur:
            cur.execute(
                "SELECT EXISTS ("
                "  SELECT 1 FROM information_schema.tables"
                "  WHERE table_schema = 'dfe' AND table_name = 'gias_schools'"
                ")"
            )
            has_gias = cur.fetchone()[0]

        if has_gias:
            school_sql = """
                SELECT sc.urn, sc.school_name, sc.school_postcode,
                       sc.typeofestablishment_name, sc.phase_type_grouping,
                       g.street, sc.district_administrative_code,
                       g.latitude, g.longitude
                FROM dfe.school_census sc
                LEFT JOIN dfe.gias_schools g ON g.urn = sc.urn
                WHERE sc.urn IS NOT NULL AND sc.urn != ''
            """
        else:
            context.log.info(
                "dfe.gias_schools not found — Tier 3 address matching disabled"
            )
            school_sql = """
                SELECT urn, school_name, school_postcode,
                       typeofestablishment_name, phase_type_grouping,
                       NULL AS street, district_administrative_code,
                       NULL AS latitude, NULL AS longitude
                FROM dfe.school_census
                WHERE urn IS NOT NULL AND urn != ''
            """

        by_urn_school: dict[str, SchoolRecord] = {}
        by_postcode_school: dict[str, list[SchoolRecord]] = defaultdict(list)
        by_la: dict[str, list[SchoolRecord]] = defaultdict(list)

        with conn.cursor() as cur:
            cur.execute(school_sql)
            for (
                urn,
                name,
                pc,
                est_type,
                phase_type,
                street,
                district_code,
                lat,
                lon,
            ) in cur:
                norm_pc = normalise_postcode(pc)
                rec = SchoolRecord(
                    urn=urn,
                    school_name=name,
                    postcode=norm_pc,
                    establishment_type=est_type,
                    phase_type=phase_type,
                    address_line1=street,
                    latitude=float(lat) if lat else None,
                    longitude=float(lon) if lon else None,
                )
                by_urn_school[urn] = rec
                if norm_pc:
                    by_postcode_school[norm_pc].append(rec)
                if district_code:
                    by_la[district_code].append(rec)

        # Nationally unique-name index (Tier 8)
        _name_count: dict[str, int] = {}
        for rec in by_urn_school.values():
            if rec.name_norm:
                _name_count[rec.name_norm] = _name_count.get(rec.name_norm, 0) + 1
        by_name_unique: dict[str, SchoolRecord] = {
            rec.name_norm: rec
            for rec in by_urn_school.values()
            if rec.name_norm and _name_count[rec.name_norm] == 1
        }

        context.log.info(
            f"Loaded {len(by_urn_school)} school records, "
            f"{len(by_postcode_school)} unique postcodes"
            f"{' (with GIAS addresses)' if has_gias else ''}"
            f", {len(by_name_unique)} nationally unique names"
        )

        # ---- Load provider coordinates ----
        with conn.cursor() as cur:
            cur.execute(
                "SELECT EXISTS ("
                "  SELECT 1 FROM information_schema.tables"
                "  WHERE table_schema = 'os' AND table_name = 'la_places'"
                ")"
            )
            has_la_places = cur.fetchone()[0]

        provider_coords: dict[tuple[str, str], tuple[float, float]] = {}
        if has_la_places:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT lad25cd, provider_id, latitude, longitude"
                    " FROM os.la_places WHERE latitude IS NOT NULL"
                )
                for lad, pid, plat, plon in cur:
                    provider_coords[(lad, pid)] = (float(plat), float(plon))
            context.log.info(
                f"Loaded {len(provider_coords)} provider coordinates from os.la_places"
            )

        # ---- Load free breakfast club URNs ----
        with conn.cursor() as cur:
            cur.execute("SELECT urn FROM dfe.free_breakfast_club_schools")
            free_breakfast_urns: set[str] = {row[0] for row in cur if row[0]}

        context.log.info(
            f"Loaded {len(free_breakfast_urns)} free breakfast club school URNs"
        )

        # ---- Stream all providers and link ----
        ofsted_counts: dict[str, int] = defaultdict(int)
        school_counts: dict[str, int] = defaultdict(int)
        unmatched_ofsted_by_la: dict[str, int] = defaultdict(int)
        unmatched_school_by_la: dict[str, int] = defaultdict(int)

        with bsil_postgres.get_connection() as write_conn:
            with conn.cursor(name="linkage_cursor") as cur:
                cur.itersize = BATCH_SIZE
                cur.execute(
                    "SELECT lad25cd, provider_id, extracted_data, classification"
                    " FROM la.extract_results"
                    " WHERE NOT draft_exclude"
                )

                write_batch: list[dict] = []

                for lad25cd, provider_id, extracted_data, classification in cur:
                    ed = extracted_data or {}
                    la_name = ed.get("provider_name", "")
                    la_postcode = normalise_postcode(ed.get("postcode"))
                    la_addr = ed.get("address_line1", "") or ed.get("address", "")
                    la_classification = _pick_classification(classification)

                    # Resolve provider coordinates
                    try:
                        prov_lat = float(ed["latitude"]) if ed.get("latitude") else None
                        prov_lon = (
                            float(ed["longitude"]) if ed.get("longitude") else None
                        )
                    except (ValueError, TypeError):
                        prov_lat = prov_lon = None
                    if not (prov_lat and prov_lon):
                        coords = provider_coords.get((lad25cd, provider_id))
                        if coords:
                            prov_lat, prov_lon = coords

                    row: dict = {
                        "lad25cd": lad25cd,
                        "provider_id": provider_id,
                        "ofsted_urn": None,
                        "school_urn": None,
                        "is_free_breakfast_school": False,
                        "metadata": {
                            "la": {
                                "provider_name": la_name,
                                "postcode": la_postcode,
                                "classification": la_classification,
                            },
                            "ofsted": {
                                "match_method": "unmatched",
                                "match_confidence": None,
                                "ofsted_provider_name": None,
                                "ofsted_postcode": None,
                            },
                            "school": None,
                        },
                    }

                    # ===== Ofsted cascade =====

                    if lad25cd.startswith(_NON_ENGLAND_PREFIXES):
                        row["metadata"]["ofsted"]["match_method"] = "not_applicable"
                        ofsted_counts["not_applicable"] += 1
                    else:
                        # Tier 1: URN exact
                        cleaned_urn = _clean_urn(ed.get("ofsted_urn"))
                        if cleaned_urn and cleaned_urn in by_urn_ofsted:
                            rec = by_urn_ofsted[cleaned_urn]
                            row["ofsted_urn"] = cleaned_urn
                            row["metadata"]["ofsted"]["match_method"] = "urn_exact"
                            row["metadata"]["ofsted"]["match_confidence"] = 1.0
                            row["metadata"]["ofsted"]["ofsted_provider_name"] = (
                                rec.provider_name
                            )
                            row["metadata"]["ofsted"]["ofsted_postcode"] = rec.postcode
                            ofsted_counts["urn_exact"] += 1
                        else:
                            ofsted_cands = (
                                by_postcode_ofsted.get(la_postcode, [])
                                if la_postcode
                                else []
                            )
                            la_name_clean = _clean_la_name(la_name) or la_name
                            matched = False

                            # Tier 2: postcode + name
                            if ofsted_cands and not matched:
                                la_name_norm = normalise_name(la_name_clean)
                                if la_name_norm:
                                    m_rec, ratio = _best_name_match(
                                        la_name_norm, ofsted_cands
                                    )
                                    if m_rec:
                                        row["ofsted_urn"] = m_rec.provider_urn
                                        row["metadata"]["ofsted"]["match_method"] = (
                                            "postcode_name"
                                        )
                                        row["metadata"]["ofsted"][
                                            "match_confidence"
                                        ] = round(ratio, 4)
                                        row["metadata"]["ofsted"][
                                            "ofsted_provider_name"
                                        ] = m_rec.provider_name
                                        row["metadata"]["ofsted"]["ofsted_postcode"] = (
                                            m_rec.postcode
                                        )
                                        ofsted_counts["postcode_name"] += 1
                                        matched = True

                            # Tier 2b: postcode + stripped qualifier name
                            if ofsted_cands and not matched:
                                stripped_raw = _strip_la_qualifiers(la_name_clean)
                                if stripped_raw:
                                    stripped_norm = normalise_name(stripped_raw)
                                    if (
                                        stripped_norm
                                        and stripped_norm
                                        != normalise_name(la_name_clean)
                                    ):
                                        m_rec, ratio = _best_name_match(
                                            stripped_norm, ofsted_cands
                                        )
                                        if m_rec:
                                            row["ofsted_urn"] = m_rec.provider_urn
                                            row["metadata"]["ofsted"][
                                                "match_method"
                                            ] = "postcode_name_stripped"
                                            row["metadata"]["ofsted"][
                                                "match_confidence"
                                            ] = round(ratio, 4)
                                            row["metadata"]["ofsted"][
                                                "ofsted_provider_name"
                                            ] = m_rec.provider_name
                                            row["metadata"]["ofsted"][
                                                "ofsted_postcode"
                                            ] = m_rec.postcode
                                            ofsted_counts["postcode_name_stripped"] += 1
                                            matched = True

                            # Tier 2c: postcode + Ofsted venue name
                            if ofsted_cands and not matched:
                                la_name_norm_v = normalise_name(la_name_clean)
                                if la_name_norm_v:
                                    m_rec, ratio = _best_venue_match(
                                        la_name_norm_v, ofsted_cands
                                    )
                                    if m_rec:
                                        row["ofsted_urn"] = m_rec.provider_urn
                                        row["metadata"]["ofsted"]["match_method"] = (
                                            "postcode_ofsted_venue"
                                        )
                                        row["metadata"]["ofsted"][
                                            "match_confidence"
                                        ] = round(ratio, 4)
                                        row["metadata"]["ofsted"][
                                            "ofsted_provider_name"
                                        ] = m_rec.provider_name
                                        row["metadata"]["ofsted"]["ofsted_postcode"] = (
                                            m_rec.postcode
                                        )
                                        ofsted_counts["postcode_ofsted_venue"] += 1
                                        matched = True

                            # Tier 3: postcode + address
                            if ofsted_cands and not matched:
                                la_addr_norm = normalise_name(la_addr)
                                if la_addr_norm:
                                    m_rec, ratio = _best_addr_match(
                                        la_addr_norm, ofsted_cands
                                    )
                                    if m_rec:
                                        row["ofsted_urn"] = m_rec.provider_urn
                                        row["metadata"]["ofsted"]["match_method"] = (
                                            "postcode_address"
                                        )
                                        row["metadata"]["ofsted"][
                                            "match_confidence"
                                        ] = round(ratio, 4)
                                        row["metadata"]["ofsted"][
                                            "ofsted_provider_name"
                                        ] = m_rec.provider_name
                                        row["metadata"]["ofsted"]["ofsted_postcode"] = (
                                            m_rec.postcode
                                        )
                                        ofsted_counts["postcode_address"] += 1
                                        matched = True

                            if not matched:
                                ofsted_counts["unmatched"] += 1
                                unmatched_ofsted_by_la[lad25cd] += 1

                    # ===== School cascade (school-typed providers only) =====
                    # Pre-check: runs for ALL providers regardless of classification.
                    # Covers nurseries/clubs hosted at schools that aren't typed as
                    # school_based_nursery etc. but can still be linked via URN,
                    # venue name, or subset name match.
                    if not lad25cd.startswith(_NON_ENGLAND_PREFIXES):
                        raw_urn = ed.get("ofsted_urn")
                        if (
                            raw_urn
                            and raw_urn not in by_urn_ofsted
                            and raw_urn in by_urn_school
                        ):
                            s_rec = by_urn_school[raw_urn]
                            row["school_urn"] = raw_urn
                            row["metadata"]["school"] = {
                                "match_method": "urn_exact",
                                "match_confidence": 1.0,
                                "school_name": s_rec.school_name,
                                "school_postcode": s_rec.postcode,
                            }
                            school_counts["urn_exact"] += 1

                        # Venue + subset matching for non-school-typed providers
                        if (
                            not row["school_urn"]
                            and la_classification not in _SCHOOL_TYPES
                        ):
                            school_cands_pre = (
                                by_postcode_school.get(la_postcode, [])
                                if la_postcode
                                else []
                            )
                            if school_cands_pre:
                                # Venue match
                                venue = _extract_venue_name(la_name)
                                if venue:
                                    venue_norm = normalise_name(
                                        strip_care_suffix(venue)
                                    )
                                    if venue_norm:
                                        s_rec, ratio = _best_school_name_match(
                                            venue_norm, school_cands_pre
                                        )
                                        if s_rec:
                                            row["school_urn"] = s_rec.urn
                                            row["metadata"]["school"] = {
                                                "match_method": "postcode_name_venue",
                                                "match_confidence": round(ratio, 4),
                                                "school_name": s_rec.school_name,
                                                "school_postcode": s_rec.postcode,
                                            }
                                            school_counts["postcode_name_venue"] += 1

                                # Subset match
                                if not row["school_urn"]:
                                    la_name_norm_pre = normalise_name(
                                        strip_care_suffix(la_name)
                                    )
                                    if la_name_norm_pre:
                                        s_rec, ratio = _best_school_subset_match(
                                            la_name_norm_pre, school_cands_pre
                                        )
                                        if s_rec:
                                            row["school_urn"] = s_rec.urn
                                            row["metadata"]["school"] = {
                                                "match_method": "postcode_name_subset",
                                                "match_confidence": round(ratio, 4),
                                                "school_name": s_rec.school_name,
                                                "school_postcode": s_rec.postcode,
                                            }
                                            school_counts["postcode_name_subset"] += 1

                    if la_classification in _SCHOOL_TYPES:
                        if lad25cd.startswith(_NON_ENGLAND_PREFIXES):
                            row["metadata"]["school"] = {
                                "match_method": "not_applicable"
                            }
                            school_counts["not_applicable"] += 1
                        else:
                            s_matched = bool(row["school_urn"])

                            # Tier 1: URN exact
                            raw_urn = ed.get("ofsted_urn")
                            if not s_matched and raw_urn and raw_urn in by_urn_school:
                                s_rec = by_urn_school[raw_urn]
                                row["school_urn"] = raw_urn
                                row["metadata"]["school"] = {
                                    "match_method": "urn_exact",
                                    "match_confidence": 1.0,
                                    "school_name": s_rec.school_name,
                                    "school_postcode": s_rec.postcode,
                                }
                                school_counts["urn_exact"] += 1
                                s_matched = True

                            school_cands = (
                                by_postcode_school.get(la_postcode, [])
                                if la_postcode
                                else []
                            )

                            # Tier 2: postcode + name (care-suffix stripped)
                            if school_cands and not s_matched:
                                stripped_name = strip_care_suffix(la_name)
                                la_name_norm = normalise_name(stripped_name)
                                if la_name_norm:
                                    s_rec, ratio = _best_school_name_match(
                                        la_name_norm, school_cands
                                    )
                                    if s_rec:
                                        row["school_urn"] = s_rec.urn
                                        row["metadata"]["school"] = {
                                            "match_method": "postcode_name",
                                            "match_confidence": round(ratio, 4),
                                            "school_name": s_rec.school_name,
                                            "school_postcode": s_rec.postcode,
                                        }
                                        school_counts["postcode_name"] += 1
                                        s_matched = True

                            # Tier 2b: operator prefix + postcode + name (clubs only)
                            if (
                                school_cands
                                and not s_matched
                                and la_classification in _CLUB_TYPES
                            ):
                                venue = _extract_venue_name(la_name)
                                if venue:
                                    venue_norm = normalise_name(
                                        strip_care_suffix(venue)
                                    )
                                    if venue_norm:
                                        s_rec, ratio = _best_school_name_match(
                                            venue_norm, school_cands
                                        )
                                        if s_rec:
                                            row["school_urn"] = s_rec.urn
                                            row["metadata"]["school"] = {
                                                "match_method": "postcode_name_venue",
                                                "match_confidence": round(ratio, 4),
                                                "school_name": s_rec.school_name,
                                                "school_postcode": s_rec.postcode,
                                            }
                                            school_counts["postcode_name_venue"] += 1
                                            s_matched = True

                            # Tier 2c: venue match for all provider types
                            # (Tier 2b only runs for club types — this catches
                            # nurseries/pre-schools hosted at schools)
                            if school_cands and not s_matched:
                                venue = _extract_venue_name(la_name)
                                if venue:
                                    venue_norm = normalise_name(
                                        strip_care_suffix(venue)
                                    )
                                    if venue_norm:
                                        s_rec, ratio = _best_school_name_match(
                                            venue_norm, school_cands
                                        )
                                        if s_rec:
                                            row["school_urn"] = s_rec.urn
                                            row["metadata"]["school"] = {
                                                "match_method": "postcode_name_venue",
                                                "match_confidence": round(ratio, 4),
                                                "school_name": s_rec.school_name,
                                                "school_postcode": s_rec.postcode,
                                            }
                                            school_counts["postcode_name_venue"] += 1
                                            s_matched = True

                            # Tier 2d: postcode + subset name match
                            # Catches pre-schools/clubs where one name is a
                            # subset of the other (e.g. "Cameley Pre-School"
                            # vs "Cameley CEVC Primary School")
                            if school_cands and not s_matched:
                                stripped_name = strip_care_suffix(la_name)
                                la_name_norm = normalise_name(stripped_name)
                                if la_name_norm:
                                    s_rec, ratio = _best_school_subset_match(
                                        la_name_norm, school_cands
                                    )
                                    if s_rec:
                                        row["school_urn"] = s_rec.urn
                                        row["metadata"]["school"] = {
                                            "match_method": "postcode_name_subset",
                                            "match_confidence": round(ratio, 4),
                                            "school_name": s_rec.school_name,
                                            "school_postcode": s_rec.postcode,
                                        }
                                        school_counts["postcode_name_subset"] += 1
                                        s_matched = True

                            # Tiers 3-5 need la_addr
                            la_addr_as_name = (
                                normalise_name(strip_care_suffix(la_addr))
                                if la_addr
                                else ""
                            )

                            # Tier 3: postcode + LA address vs school name
                            if school_cands and not s_matched and la_addr_as_name:
                                s_rec, ratio = _best_school_name_match(
                                    la_addr_as_name, school_cands
                                )
                                if s_rec:
                                    row["school_urn"] = s_rec.urn
                                    row["metadata"]["school"] = {
                                        "match_method": "postcode_addr_name",
                                        "match_confidence": round(ratio, 4),
                                        "school_name": s_rec.school_name,
                                        "school_postcode": s_rec.postcode,
                                    }
                                    school_counts["postcode_addr_name"] += 1
                                    s_matched = True

                            # Tier 4: postcode + LA address prefix vs school name
                            if school_cands and not s_matched and la_addr_as_name:
                                s_rec, ratio = _best_school_prefix_match(
                                    la_addr_as_name, school_cands
                                )
                                if s_rec:
                                    row["school_urn"] = s_rec.urn
                                    row["metadata"]["school"] = {
                                        "match_method": "postcode_addr_prefix",
                                        "match_confidence": round(ratio, 4),
                                        "school_name": s_rec.school_name,
                                        "school_postcode": s_rec.postcode,
                                    }
                                    school_counts["postcode_addr_prefix"] += 1
                                    s_matched = True

                            # Tier 5: postcode + address
                            if school_cands and not s_matched:
                                la_addr_norm = (
                                    normalise_name(la_addr) if la_addr else ""
                                )
                                if la_addr_norm:
                                    s_rec, ratio = _best_school_addr_match(
                                        la_addr_norm, school_cands
                                    )
                                    if s_rec:
                                        row["school_urn"] = s_rec.urn
                                        row["metadata"]["school"] = {
                                            "match_method": "postcode_address",
                                            "match_confidence": round(ratio, 4),
                                            "school_name": s_rec.school_name,
                                            "school_postcode": s_rec.postcode,
                                        }
                                        school_counts["postcode_address"] += 1
                                        s_matched = True

                            # Tier 6: LA-scope name match (no postcode or no schools at postcode)
                            if (
                                (not la_postcode or not school_cands)
                                and by_la
                                and not s_matched
                            ):
                                la_cands = by_la.get(lad25cd, [])
                                if la_cands:
                                    name_for_la = la_name
                                    if la_classification in _CLUB_TYPES:
                                        venue = _extract_venue_name(la_name)
                                        if venue:
                                            name_for_la = venue
                                    la_name_norm_6 = normalise_name(
                                        strip_care_suffix(name_for_la)
                                    )
                                    if la_name_norm_6:
                                        s_rec, ratio = _best_school_name_match(
                                            la_name_norm_6,
                                            la_cands,
                                            threshold=LA_NAME_THRESHOLD,
                                        )
                                        if s_rec:
                                            row["school_urn"] = s_rec.urn
                                            row["metadata"]["school"] = {
                                                "match_method": "la_name",
                                                "match_confidence": round(ratio, 4),
                                                "school_name": s_rec.school_name,
                                                "school_postcode": s_rec.postcode,
                                            }
                                            school_counts["la_name"] += 1
                                            s_matched = True

                            # Tier 8: nationally unique name (no postcode or no schools at postcode)
                            if (
                                (not la_postcode or not school_cands)
                                and by_name_unique
                                and not s_matched
                            ):
                                name_for_nat = la_name
                                if la_classification in _CLUB_TYPES:
                                    venue = _extract_venue_name(la_name)
                                    if venue:
                                        name_for_nat = venue
                                nat_name_norm = normalise_name(
                                    strip_care_suffix(name_for_nat)
                                )
                                if nat_name_norm:
                                    nat_rec = by_name_unique.get(nat_name_norm)
                                    if nat_rec:
                                        row["school_urn"] = nat_rec.urn
                                        row["metadata"]["school"] = {
                                            "match_method": "national_name",
                                            "match_confidence": 1.0,
                                            "school_name": nat_rec.school_name,
                                            "school_postcode": nat_rec.postcode,
                                        }
                                        school_counts["national_name"] += 1
                                        s_matched = True

                            # Tier 7: coordinate proximity + name gate
                            if prov_lat and prov_lon and not s_matched:
                                la_cands = by_la.get(lad25cd, [])
                                # Prepare provider name for comparison
                                cp_name = la_name  # already cleaned by _clean_la_name
                                if la_classification in _CLUB_TYPES:
                                    venue = _extract_venue_name(cp_name)
                                    if venue:
                                        cp_name = venue
                                cp_norm = _strip_school_words(
                                    normalise_name(strip_care_suffix(cp_name))
                                )

                                best_school: SchoolRecord | None = None
                                best_dist = float("inf")
                                for sc in la_cands:
                                    if sc.latitude is None or sc.longitude is None:
                                        continue
                                    d = _haversine_m(
                                        prov_lat, prov_lon, sc.latitude, sc.longitude
                                    )
                                    if d < best_dist:
                                        best_dist = d
                                        best_school = sc
                                if (
                                    best_school is not None
                                    and best_dist <= COORD_PROXIMITY_M
                                    and cp_norm
                                    and SequenceMatcher(
                                        None,
                                        cp_norm,
                                        _strip_school_words(best_school.name_norm),
                                    ).ratio()
                                    >= COORD_NAME_THRESHOLD
                                ):
                                    confidence = round(
                                        max(0.0, 1.0 - best_dist / COORD_PROXIMITY_M), 4
                                    )
                                    row["school_urn"] = best_school.urn
                                    row["metadata"]["school"] = {
                                        "match_method": "coord_proximity",
                                        "match_confidence": confidence,
                                        "school_name": best_school.school_name,
                                        "school_postcode": best_school.postcode,
                                    }
                                    school_counts["coord_proximity"] += 1
                                    s_matched = True

                            if not s_matched:
                                row["metadata"]["school"] = {
                                    "match_method": "unmatched"
                                }
                                school_counts["unmatched"] += 1
                                unmatched_school_by_la[lad25cd] += 1

                    # ===== Free breakfast flag =====
                    row["is_free_breakfast_school"] = bool(
                        (row["school_urn"] and row["school_urn"] in free_breakfast_urns)
                        or (
                            row["ofsted_urn"]
                            and row["ofsted_urn"] in free_breakfast_urns
                        )
                    )

                    write_batch.append(row)
                    if len(write_batch) >= BATCH_SIZE:
                        _save_batch(write_conn, write_batch)
                        write_batch = []

                if write_batch:
                    _save_batch(write_conn, write_batch)

        # ---- Logging ----
        ofsted_total = sum(ofsted_counts.values())
        school_total = sum(school_counts.values())
        context.log.info(
            f"Linkage complete — {ofsted_total} providers (Ofsted), "
            f"{school_total} school-type providers"
        )
        context.log.info(f"  Ofsted match counts: {dict(ofsted_counts)}")
        context.log.info(f"  School match counts: {dict(school_counts)}")

        if unmatched_ofsted_by_la:
            context.log.info(
                f"Unmatched Ofsted (England only): {ofsted_counts['unmatched']} "
                f"across {len(unmatched_ofsted_by_la)} LAs"
            )
            for lad, n in sorted(unmatched_ofsted_by_la.items(), key=lambda x: -x[1])[
                :20
            ]:
                context.log.info(f"    {lad}: {n} unmatched")

        if unmatched_school_by_la:
            context.log.info(
                f"Unmatched school (England only): {school_counts.get('unmatched', 0)} "
                f"across {len(unmatched_school_by_la)} LAs"
            )
            for lad, n in sorted(unmatched_school_by_la.items(), key=lambda x: -x[1])[
                :20
            ]:
                context.log.info(f"    {lad}: {n} unmatched")

        # Unmatched Ofsted providers in scraped LAs
        with conn.cursor() as cur:
            cur.execute("""
                SELECT i.local_authority, COUNT(*) AS n
                FROM ofsted.inspections i
                LEFT JOIN draft.linkage l ON i.provider_urn = l.ofsted_urn
                WHERE l.ofsted_urn IS NULL
                  AND i.local_authority IN (
                      SELECT DISTINCT extracted_data->>'local_authority'
                      FROM la.extract_results
                      WHERE lad25cd NOT LIKE 'S%%'
                        AND lad25cd NOT LIKE 'W%%'
                        AND lad25cd NOT LIKE 'N%%'
                  )
                GROUP BY i.local_authority
                ORDER BY n DESC
                LIMIT 20
            """)
            unmatched_ofsted = cur.fetchall()

        if unmatched_ofsted:
            total_unmatched_ofsted = sum(n for _, n in unmatched_ofsted)
            context.log.info(
                f"Unmatched Ofsted providers (in scraped LAs): "
                f"{total_unmatched_ofsted} across {len(unmatched_ofsted)} LAs"
            )
            for la_name, n in unmatched_ofsted:
                context.log.info(f"    {la_name}: {n} unmatched")

    return {
        "ofsted_total": MetadataValue.int(ofsted_total),
        "school_total": MetadataValue.int(school_total),
        **{f"ofsted_{k}": MetadataValue.int(v) for k, v in ofsted_counts.items()},
        **{f"school_{k}": MetadataValue.int(v) for k, v in school_counts.items()},
    }


def _save_batch(conn, batch: list[dict]) -> None:
    with conn.cursor() as cur:
        for row in batch:
            row["metadata"] = json.dumps(row["metadata"])
            cur.execute(UPSERT_SQL, row)
    conn.commit()
