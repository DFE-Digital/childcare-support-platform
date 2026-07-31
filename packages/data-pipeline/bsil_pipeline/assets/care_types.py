"""Dagster asset building draft.care_types — explodes the care_types array
on draft.providers into a normalised table with one row per
(provider_id, care_type), then enriches from Ofsted and LA extract data.

Phase 1: Skeleton — explode draft.providers.care_types[] into rows.
Phase 2: Ofsted age enrichment — set eligible_min/max from register combos.
Phase 3: LA extract enrichment — age_range, weeks, funding.
Phase 4: School defaults for school_based_nursery rows.
Phase 7: Age range completeness — ensure min+max always paired.
"""

import json
import re

from dagster import asset, AssetExecutionContext, MetadataValue

from bsil_pipeline.automation import PIPELINE_CONDITION
from bsil_pipeline.resources.postgres import BsilPostgresResource


BATCH_SIZE = 2000

# ---------- Phase 1: Skeleton ----------

DROP_SQL = "DROP TABLE IF EXISTS draft.care_types CASCADE"

CREATE_SQL = """
CREATE TABLE draft.care_types (
    id                      BIGSERIAL PRIMARY KEY,
    provider_id             TEXT NOT NULL REFERENCES draft.providers(provider_id)
                            ON DELETE CASCADE,
    care_type               TEXT NOT NULL,
    operating_weeks_per_year INTEGER,
    session_hours_morning   NUMERIC(5,2),
    session_hours_afternoon NUMERIC(5,2),
    session_hours_full_day  NUMERIC(5,2),
    eligible_min_months     INTEGER,
    eligible_min_years      INTEGER,
    eligible_max_years      INTEGER,
    ofsted_register_combination TEXT,
    eligible_attendees_only BOOLEAN NOT NULL DEFAULT false,
    eligible_institutions   TEXT[],
    eligible_other          TEXT[],
    funded_hours_accepted   BOOLEAN,
    min_commitment_amount   INTEGER,
    min_commitment_unit     TEXT,
    min_commitment_duration TEXT,
    no_minimum_commitment   BOOLEAN NOT NULL DEFAULT false,
    website                 TEXT,
    fis_url                 TEXT,
    metadata                JSONB NOT NULL DEFAULT '{}',
    built_at                TIMESTAMP DEFAULT now()
)
"""

INDEX_SQL = [
    "CREATE INDEX idx_draft_care_types_provider_id ON draft.care_types(provider_id)",
    "CREATE INDEX idx_draft_care_types_care_type ON draft.care_types(care_type)",
]

EXPLODE_SQL = """
SELECT provider_id, unnest(care_types) AS care_type
FROM draft.providers
WHERE NOT excluded
  AND care_types IS NOT NULL
  AND array_length(care_types, 1) > 0
"""

INSERT_SQL = """
INSERT INTO draft.care_types (provider_id, care_type)
VALUES (%(provider_id)s, %(care_type)s)
"""

# ---------- Phase 2: Ofsted age enrichment ----------

# Ofsted register combinations -> (eligible_min_months, eligible_min_years, eligible_max_years)
# EYR = Early Years Register (0-5)
# CCR = Compulsory Childcare Register (5-8)
# VCR = Voluntary Childcare Register (8-18)
_REGISTER_AGE_MAP = {
    "ALL": (0, None, 18),
    "EYR only": (0, None, 5),
    "EYR-CCR": (0, None, 8),
    "EYR-VCR": (0, None, 18),
    "CCR only": (None, 5, 8),
    "CCR-VCR": (None, 5, 18),
    "VCR only": (None, 8, 18),
}

LOAD_OFSTED_REGISTERS_SQL = """
SELECT provider_urn, individual_register_combinations
FROM ofsted.inspections
WHERE individual_register_combinations IS NOT NULL
  AND individual_register_combinations != ''
"""

LOAD_CARE_TYPE_PROVIDERS_SQL = """
SELECT ct.id, ct.provider_id, ct.care_type, p.ofsted_urn
FROM draft.care_types ct
JOIN draft.providers p ON p.provider_id = ct.provider_id
WHERE p.ofsted_urn IS NOT NULL
"""

UPDATE_AGE_SQL = """
UPDATE draft.care_types
SET eligible_min_months         = %(eligible_min_months)s,
    eligible_min_years          = %(eligible_min_years)s,
    eligible_max_years          = %(eligible_max_years)s,
    ofsted_register_combination = %(ofsted_register_combination)s,
    metadata                    = %(metadata)s
WHERE id = %(id)s
"""

# ---------- Phase 3: LA extract enrichment ----------

LOAD_LA_EXTRACTS_SQL = """
SELECT ps.provider_id, ps.source_id, e.extracted_data, co.care_type
FROM draft.provider_sources ps
JOIN la.extract_results e
    ON e.lad25cd = split_part(ps.source_id, ':', 1)
   AND e.provider_id = substring(ps.source_id FROM position(':' IN ps.source_id) + 1)
JOIN draft.care_offerings co ON co.id = ps.care_offering_id
WHERE ps.source = 'la_scrape'
ORDER BY ps.provider_id, co.care_type
"""

LOAD_CARE_TYPES_FOR_LA_SQL = """
SELECT ct.id, ct.provider_id, ct.care_type, ct.eligible_min_months, ct.eligible_min_years,
       ct.eligible_max_years, ct.metadata
FROM draft.care_types ct
WHERE ct.provider_id = ANY(%(provider_ids)s)
ORDER BY ct.provider_id, ct.id
"""

UPDATE_LA_SQL = """
UPDATE draft.care_types
SET eligible_min_months   = %(eligible_min_months)s,
    eligible_min_years    = %(eligible_min_years)s,
    eligible_max_years    = %(eligible_max_years)s,
    operating_weeks_per_year = %(operating_weeks_per_year)s,
    funded_hours_accepted = %(funded_hours_accepted)s,
    eligible_institutions = %(eligible_institutions)s,
    metadata              = %(metadata)s
WHERE id = %(id)s
"""

# ---------- Phase 4: School defaults ----------

# school_based_nursery defaults (statutory requirements for maintained nursery classes)
# - Term time: 38 weeks
# - Funded hours: always accepted (universal entitlement)
# - Age: derived from census youngest pupil age, fallback 3-4 years
_SBN_DEFAULT_MAX_YEARS = 4
_SBN_DEFAULT_MIN_YEARS = 3
_SBN_DEFAULT_FUNDED = True

# Default weeks for school-based care types (sbn, breakfast_club, after_school_club)
_SCHOOL_DEFAULT_WEEKS = 38

LOAD_SCHOOL_CLUBS_SQL = """
SELECT ct.id, ct.care_type, ct.operating_weeks_per_year, ct.metadata
FROM draft.care_types ct
WHERE ct.care_type IN ('school_based_nursery', 'breakfast_club', 'after_school_club')
"""

UPDATE_CLUB_WEEKS_SQL = """
UPDATE draft.care_types
SET operating_weeks_per_year = %(operating_weeks_per_year)s,
    metadata                 = %(metadata)s
WHERE id = %(id)s
"""

LOAD_SBN_SQL = """
SELECT ct.id, ct.eligible_min_months, ct.eligible_min_years, ct.eligible_max_years,
       ct.operating_weeks_per_year, ct.funded_hours_accepted, ct.metadata,
       p.school_urn
FROM draft.care_types ct
JOIN draft.providers p ON p.provider_id = ct.provider_id
WHERE ct.care_type = 'school_based_nursery'
"""

# Derive youngest pupil age per school from census headcounts (ages 0-4).
# For each age, sum part-time + full-time across male + female.
# Only ages 0-4 are relevant for nursery provision.
LOAD_CENSUS_MIN_AGE_SQL = """
SELECT urn,
    COALESCE(NULLIF(part_time_female_aged_0,''),'0')::int + COALESCE(NULLIF(part_time_male_aged_0,''),'0')::int
    + COALESCE(NULLIF(full_time_female_aged_0,''),'0')::int + COALESCE(NULLIF(full_time_male_aged_0,''),'0')::int AS age0,
    COALESCE(NULLIF(part_time_female_aged_1,''),'0')::int + COALESCE(NULLIF(part_time_male_aged_1,''),'0')::int
    + COALESCE(NULLIF(full_time_female_aged_1,''),'0')::int + COALESCE(NULLIF(full_time_male_aged_1,''),'0')::int AS age1,
    COALESCE(NULLIF(part_time_female_aged_2,''),'0')::int + COALESCE(NULLIF(part_time_male_aged_2,''),'0')::int
    + COALESCE(NULLIF(full_time_female_aged_2,''),'0')::int + COALESCE(NULLIF(full_time_male_aged_2,''),'0')::int AS age2,
    COALESCE(NULLIF(part_time_female_aged_3,''),'0')::int + COALESCE(NULLIF(part_time_male_aged_3,''),'0')::int
    + COALESCE(NULLIF(full_time_female_aged_3,''),'0')::int + COALESCE(NULLIF(full_time_male_aged_3,''),'0')::int AS age3,
    COALESCE(NULLIF(part_time_female_aged_4,''),'0')::int + COALESCE(NULLIF(part_time_male_aged_4,''),'0')::int
    + COALESCE(NULLIF(full_time_female_aged_4,''),'0')::int + COALESCE(NULLIF(full_time_male_aged_4,''),'0')::int AS age4
FROM dfe.school_census
WHERE geographic_level = 'School'
"""

UPDATE_SBN_SQL = """
UPDATE draft.care_types
SET eligible_min_months  = %(eligible_min_months)s,
    eligible_min_years   = %(eligible_min_years)s,
    eligible_max_years   = %(eligible_max_years)s,
    operating_weeks_per_year = %(operating_weeks_per_year)s,
    funded_hours_accepted    = %(funded_hours_accepted)s,
    metadata                 = %(metadata)s
WHERE id = %(id)s
"""


# ---------- Phase 5: Care-type URL enrichment ----------

LOAD_CT_URLS_SQL = """
SELECT ps.provider_id, co.care_type, ps.source_id, sr.source_url,
       e.extracted_data->>'website' as extracted_website,
       e.extracted_data
FROM draft.provider_sources ps
JOIN draft.care_offerings co ON co.id = ps.care_offering_id
LEFT JOIN la.scrape_results sr
    ON sr.lad25cd = split_part(ps.source_id, ':', 1)
   AND sr.provider_id = substring(ps.source_id FROM position(':' IN ps.source_id) + 1)
LEFT JOIN la.extract_results e
    ON e.lad25cd = split_part(ps.source_id, ':', 1)
   AND e.provider_id = substring(ps.source_id FROM position(':' IN ps.source_id) + 1)
WHERE ps.source = 'la_scrape'
ORDER BY ps.provider_id, co.care_type
"""

LOAD_PROVIDER_URLS_SQL = """
SELECT provider_id, website, fis_url
FROM draft.providers
WHERE provider_id = ANY(%(provider_ids)s)
"""

UPDATE_CT_URLS_SQL = """
UPDATE draft.care_types
SET website = %(website)s,
    fis_url = %(fis_url)s,
    metadata = %(metadata)s
WHERE provider_id = %(provider_id)s AND care_type = %(care_type)s
"""


def _census_youngest_age(age0, age1, age2, age3, age4):
    """Return (min_months, min_years) from census age headcounts.

    Uses the youngest age bucket with >0 pupils.
    Returns (None, None) if all zero.
    """
    if age0 > 0:
        return 0, None
    if age1 > 0:
        return None, 1
    if age2 > 0:
        return None, 2
    if age3 > 0:
        return None, 3
    if age4 > 0:
        return None, 4
    return None, None


# Junk age_range values to skip
_AGE_JUNK = frozenset(
    {
        "not available",
        "-",
        "no information given",
        "please see 'additional information' for details",
        "adults",
        "16+",
        "18+",
        "preschool, adults",
        "preschool, children",
        "children",
    }
)

# Availability -> operating_weeks_per_year
_AVAILABILITY_WEEKS = {
    "open all year": 52,
    "all year": 52,
    "term time only": 38,
    "term time": 38,
    "term time only option": 38,
    "school holidays only": None,  # not regular care
}

# ---------- Parsers ----------

# Matches "X years", "X year(s)", "X yr" etc
_RE_YEARS = re.compile(r"(\d+)\s*(?:years?|year\(s\)|yr)", re.IGNORECASE)
# Matches "X months", "X month(s)", "X mo" etc
_RE_MONTHS = re.compile(r"(\d+)\s*(?:months?|month\(s\)|mo)", re.IGNORECASE)
# Matches simple numeric-dash-numeric: "0-12", "3-4"
_RE_SIMPLE_RANGE = re.compile(r"^(\d+)\s*[-–]\s*(\d+)$")
# Matches "X Years Y Months" compound
_RE_COMPOUND = re.compile(
    r"(\d+)\s*(?:years?|year\(s\))\s*(\d+)\s*(?:months?|month\(s\))",
    re.IGNORECASE,
)
# Weeks from "number of weeks opens" text: "for XX weeks"
_RE_WEEKS_NUM = re.compile(r"for\s+(\d+)\s+weeks", re.IGNORECASE)


def _parse_age_value(text):
    """Parse an age fragment into total months.

    Returns total months, or None if unparseable.
    """
    text = text.strip()

    # Compound: "2 Years 10 Months" or "2 years 0 months"
    m = _RE_COMPOUND.search(text)
    if m:
        return int(m.group(1)) * 12 + int(m.group(2))

    # "From X Year(s) Y month(s)"
    yr_match = _RE_YEARS.search(text)
    mo_match = _RE_MONTHS.search(text)

    if yr_match and mo_match:
        return int(yr_match.group(1)) * 12 + int(mo_match.group(1))
    if mo_match:
        return int(mo_match.group(1))
    if yr_match:
        return int(yr_match.group(1)) * 12

    # Bare number (e.g. in "0-12" split: "0", "12")
    try:
        return int(text) * 12
    except ValueError:
        return None


def _months_to_fields(total_months):
    """Convert total months to (min_months, min_years).

    If < 12 months: return (months, None).
    If >= 12 months: return (None, years).
    Special: 0 -> (0, None).
    """
    if total_months is None:
        return None, None
    if total_months < 12:
        return total_months, None
    return None, total_months // 12


def _months_to_max_years(total_months):
    """Convert total months to max_years (round up to include partial years)."""
    if total_months is None:
        return None
    # e.g. 59 months (4yr 11mo) -> 4 years (they're still in year 4)
    return total_months // 12


def parse_age_range(raw):
    """Parse an age_range string into (min_months, min_years, max_years).

    Returns (None, None, None) if unparseable.
    """
    if not raw:
        return None, None, None

    text = raw.strip()
    if text.lower() in _AGE_JUNK:
        return None, None, None

    # "All ages" / "All Ages"
    if text.lower() in ("all ages",):
        return 0, None, 18

    # Handle concatenated ranges: "0-5 Years5-8 Years" -> take overall span
    if re.search(r"Years?\d", text, re.IGNORECASE):
        # Multiple ranges glued together — extract all numbers, take min/max
        nums = [int(x) for x in re.findall(r"\d+", text)]
        if len(nums) >= 2:
            min_val = min(nums) * 12
            max_val = max(nums) * 12
            min_months, min_years = _months_to_fields(min_val)
            return min_months, min_years, _months_to_max_years(max_val)

    # "Up to X years" -> min=0, max=X
    up_to = re.match(r"Up\s+to\s+(\d+)\s*(?:years?)?", text, re.IGNORECASE)
    if up_to:
        return 0, None, int(up_to.group(1))

    # "From X (years/months) [to Y]"
    from_match = re.match(r"From\s+(.+?)(?:\s+to\s+(.+))?$", text, re.IGNORECASE)
    if from_match:
        min_val = _parse_age_value(from_match.group(1))
        max_val = _parse_age_value(from_match.group(2)) if from_match.group(2) else None
        min_months, min_years = _months_to_fields(min_val)
        max_years = _months_to_max_years(max_val)
        if min_months is not None or min_years is not None or max_years is not None:
            return min_months, min_years, max_years
        return None, None, None

    # "X (years/months) to Y (years/months)"
    to_match = re.match(r"(.+?)\s+to\s+(.+)", text, re.IGNORECASE)
    if to_match:
        min_val = _parse_age_value(to_match.group(1))
        max_val = _parse_age_value(to_match.group(2))
        min_months, min_years = _months_to_fields(min_val)
        max_years = _months_to_max_years(max_val)
        if min_months is not None or min_years is not None or max_years is not None:
            return min_months, min_years, max_years

    # "X months - Y years" (dash separator)
    dash_match = re.match(r"(.+?)\s*[-–]\s*(.+)", text)
    if dash_match:
        min_val = _parse_age_value(dash_match.group(1))
        max_val = _parse_age_value(dash_match.group(2))
        if min_val is not None and max_val is not None:
            min_months, min_years = _months_to_fields(min_val)
            max_years = _months_to_max_years(max_val)
            if min_months is not None or min_years is not None or max_years is not None:
                return min_months, min_years, max_years

    # Simple "X-Y" (bare numbers, no units) stripped down
    stripped = re.sub(
        r"\s*(?:years?|year\(s\))\s*", "", text, flags=re.IGNORECASE
    ).strip()
    simple = _RE_SIMPLE_RANGE.match(stripped)
    if simple:
        min_val = int(simple.group(1)) * 12
        max_val = int(simple.group(2)) * 12
        min_months, min_years = _months_to_fields(min_val)
        max_years = _months_to_max_years(max_val)
        if max_years is not None:
            return min_months, min_years, max_years

    return None, None, None


def parse_operating_weeks(availability, weeks_text):
    """Parse operating weeks from availability and/or 'number of weeks opens'.

    weeks_text takes priority (explicit number).
    Returns int or None.
    """
    # Explicit week count: "The setting is open : for 48 weeks, ..."
    if weeks_text:
        m = _RE_WEEKS_NUM.search(weeks_text)
        if m:
            return int(m.group(1))

    # Availability keyword
    if availability:
        return _AVAILABILITY_WEEKS.get(availability.strip().lower())

    return None


def parse_funded_hours(extra):
    """Derive funded_hours_accepted from LA extra fields.

    Returns True if any funding registration is "Yes" or "Funded",
    False if all are "No" or "Not Funded", None if no data.
    """
    keys = [
        "registered for 9m-2yr old funding",
        "registered for 2yr old funding",
        "registered for 3/4yr old funding",
        "3 & 4 year old funding",
        "FundedPlaces3_4yr",
        "FundedPlaces2yr",
        "FundedPlacesUnder2yr",
    ]
    values = [extra.get(k) for k in keys if extra.get(k)]

    # Funded_Provision uses "Funded" / "Not Funded" instead of Yes/No
    fp = extra.get("Funded_Provision")
    if fp:
        values.append(fp)

    if not values:
        return None
    normalised = [v.strip().lower() for v in values]
    if any(v in ("yes", "funded") for v in normalised):
        return True
    if all(v in ("no", "not funded") for v in normalised):
        return False
    return None


def parse_funded_info(funded_info):
    """Derive funded_hours_accepted from the top-level funded_info field.

    This field contains concatenated entitlement text like
    "2 year old funded places3 and 4 year old funded placesOffers 30 hours..."
    or "Early Education and Childcare for 3 & 4 year olds - Universal entitlement".

    Returns True if the text mentions funded places or entitlements,
    None if no usable data.
    """
    if not funded_info:
        return None
    lower = funded_info.strip().lower()
    if not lower:
        return None
    # If it mentions funded places, entitlement, or early education/childcare schemes
    if "funded" in lower or "entitlement" in lower or "early education" in lower:
        return True
    return None


def parse_schools_served(raw):
    """Parse schools_served JSON array into a clean list of school names.

    Input: '["groes primary school - Margam", "central primary school - Port Talbot"]'
    Returns: ["Groes Primary School", "Central Primary School"] or None.
    Strips the " - Town" suffix as it's location info, not the school name.
    """
    if not raw:
        return None
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return None
    if not isinstance(raw, list) or not raw:
        return None
    schools = []
    for entry in raw:
        if not isinstance(entry, str) or not entry.strip():
            continue
        # Strip " - Town" suffix
        name = re.sub(r"\s*-\s*[^-]+$", "", entry.strip())
        if name:
            schools.append(name.strip().title())
    return schools if schools else None


def parse_school_pickups(raw):
    """Parse school_pickups_raw into a clean list of school names.

    Input: "Horsford Primary School: AM & PM\\nDrake Primary: PM"
    The format is school names separated by colons, with optional AM/PM suffixes.
    Returns: ["Horsford Primary School", "Drake Primary"] or None.
    """
    if not raw:
        return None
    # Split on known patterns: "School Name: AM & PM" or "School Name:"
    # The entries are concatenated without clear delimiters, but school names
    # are followed by ": AM", ": PM", ": AM & PM", or just ":"
    entries = re.split(r":\s*(?:AM\s*(?:&\s*)?PM|AM|PM)?\s*", raw)
    schools = []
    for entry in entries:
        name = entry.strip()
        if not name or name.lower() == "no school name":
            continue
        schools.append(name.title())
    return schools if schools else None


# ---------- Helpers ----------


def _flush_inserts(conn, batch):
    if not batch:
        return
    with conn.cursor() as cur:
        for row in batch:
            cur.execute(INSERT_SQL, row)
    conn.commit()


def _flush_updates(conn, batch, sql):
    if not batch:
        return
    with conn.cursor() as cur:
        for row in batch:
            cur.execute(sql, row)
    conn.commit()


# ---------- Dagster asset ----------


@asset(
    group_name="draft",
    deps=["provider_details"],
    automation_condition=PIPELINE_CONDITION,
)
def care_types(context: AssetExecutionContext, bsil_postgres: BsilPostgresResource):
    """Build draft.care_types — one row per (provider, care_type).

    Phase 1: Explode draft.providers.care_types[] into normalised rows.
    Phase 2: Enrich with Ofsted age ranges from register combinations.
    Phase 3: Enrich with LA extract data (age, weeks, funding).
    Phase 4: Apply school defaults for school_based_nursery rows.
    """
    with bsil_postgres.get_connection() as conn:
        # ---- Phase 1: Skeleton ----
        context.log.info("Phase 1: creating draft.care_types table")
        with conn.cursor() as cur:
            cur.execute(DROP_SQL)
            cur.execute(CREATE_SQL)
            for idx_sql in INDEX_SQL:
                cur.execute(idx_sql)
            conn.commit()

        context.log.info("Exploding provider care_types into rows")
        rows = []
        with conn.cursor("care_types_cursor", withhold=True) as cur:
            cur.execute(EXPLODE_SQL)
            for provider_id, care_type_val in cur:
                rows.append(provider_id)
                rows.append(care_type_val)

        total = len(rows) // 2
        context.log.info(f"Inserting {total} care_type rows")

        batch = []
        inserted = 0
        for i in range(0, len(rows), 2):
            batch.append({"provider_id": rows[i], "care_type": rows[i + 1]})
            if len(batch) >= BATCH_SIZE:
                _flush_inserts(conn, batch)
                inserted += len(batch)
                batch.clear()

        _flush_inserts(conn, batch)
        inserted += len(batch)

        with conn.cursor() as cur:
            cur.execute(
                "SELECT care_type, count(*) FROM draft.care_types GROUP BY care_type ORDER BY count DESC"
            )
            dist = {row[0]: row[1] for row in cur.fetchall()}

        context.log.info(f"Phase 1 complete: {inserted} care_type rows")
        for ct, cnt in dist.items():
            context.log.info(f"  {ct}: {cnt}")

        # ---- Phase 2: Ofsted age enrichment ----
        context.log.info("Phase 2: enriching age ranges from Ofsted registers")

        register_lookup = {}
        with conn.cursor("ofsted_reg_cursor", withhold=True) as cur:
            cur.execute(LOAD_OFSTED_REGISTERS_SQL)
            for urn, combo in cur:
                register_lookup[urn] = combo
        context.log.info(f"  Loaded {len(register_lookup)} Ofsted register records")

        ct_rows = []
        with conn.cursor("ct_provider_cursor", withhold=True) as cur:
            cur.execute(LOAD_CARE_TYPE_PROVIDERS_SQL)
            for ct_id, provider_id, care_type_val, ofsted_urn in cur:
                ct_rows.append((ct_id, provider_id, care_type_val, ofsted_urn))
        context.log.info(
            f"  {len(ct_rows)} care_type rows have Ofsted-linked providers"
        )

        p2_enriched = 0
        skipped_unknown_combo = 0
        batch = []

        for ct_id, provider_id, care_type_val, ofsted_urn in ct_rows:
            if care_type_val != "childminder":
                continue

            combo = register_lookup.get(ofsted_urn)
            if not combo:
                continue

            age_range = _REGISTER_AGE_MAP.get(combo)
            if not age_range:
                skipped_unknown_combo += 1
                continue

            min_months, min_years, max_years = age_range

            field_sources = {}
            if min_months is not None:
                field_sources["eligible_min_months"] = "ofsted:register_combinations"
            if min_years is not None:
                field_sources["eligible_min_years"] = "ofsted:register_combinations"
            if max_years is not None:
                field_sources["eligible_max_years"] = "ofsted:register_combinations"

            metadata = {"field_sources": field_sources} if field_sources else {}

            batch.append(
                {
                    "id": ct_id,
                    "eligible_min_months": min_months,
                    "eligible_min_years": min_years,
                    "eligible_max_years": max_years,
                    "ofsted_register_combination": combo,
                    "metadata": json.dumps(metadata),
                }
            )
            p2_enriched += 1

            if len(batch) >= BATCH_SIZE:
                _flush_updates(conn, batch, UPDATE_AGE_SQL)
                batch.clear()

        _flush_updates(conn, batch, UPDATE_AGE_SQL)

        if skipped_unknown_combo:
            context.log.warning(
                f"  Skipped {skipped_unknown_combo} rows with unrecognised register combinations"
            )
        context.log.info(
            f"Phase 2 complete: {p2_enriched}/{len(ct_rows)} rows enriched"
        )

        # ---- Phase 3: LA extract enrichment ----
        context.log.info("Phase 3: enriching from LA extract data")

        # 3a: Load LA extracts and parse per (provider, care_type)
        la_enrichments = {}  # (provider_id, care_type) -> {fields + field_sources}
        with conn.cursor("la_ct_cursor", withhold=True) as cur:
            cur.execute(LOAD_LA_EXTRACTS_SQL)
            for provider_id, source_id, extracted_data, care_type in cur:
                if not extracted_data:
                    continue
                if isinstance(extracted_data, str):
                    extracted_data = json.loads(extracted_data)

                extra = extracted_data.get("extra") or {}
                src_label = f"la_extract:{source_id}"

                # Take the first LA extract per (provider, care_type).
                if (provider_id, care_type) in la_enrichments:
                    continue

                fields = {}
                field_sources = {}

                # Age range: try top-level age_range first, fall back to
                # extra."age range catered for", then direct numeric fields
                age_resolved = False
                age_raw = extracted_data.get("age_range")
                age_source_key = "age_range"
                if not age_raw:
                    age_raw = extra.get("age range catered for")
                    age_source_key = "age_range_catered_for"
                if age_raw:
                    min_mo, min_yr, max_yr = parse_age_range(age_raw)
                    if min_mo is not None or min_yr is not None or max_yr is not None:
                        fields["eligible_min_months"] = min_mo
                        fields["eligible_min_years"] = min_yr
                        fields["eligible_max_years"] = max_yr
                        if min_mo is not None:
                            field_sources["eligible_min_months"] = (
                                f"{src_label}:{age_source_key}"
                            )
                        if min_yr is not None:
                            field_sources["eligible_min_years"] = (
                                f"{src_label}:{age_source_key}"
                            )
                        if max_yr is not None:
                            field_sources["eligible_max_years"] = (
                                f"{src_label}:{age_source_key}"
                            )
                        age_resolved = True
                if not age_resolved:
                    # Direct numeric min/max age fields (e.g. from liquidlogic)
                    raw_min = extracted_data.get("eligible_min_years")
                    raw_max = extracted_data.get("eligible_max_years")
                    try:
                        min_yr = int(raw_min) if raw_min is not None else None
                    except (ValueError, TypeError):
                        min_yr = None
                    try:
                        max_yr = int(raw_max) if raw_max is not None else None
                    except (ValueError, TypeError):
                        max_yr = None
                    # When min > max, the min is likely in months (unitless source field)
                    if min_yr is not None and max_yr is not None and min_yr > max_yr:
                        fields["eligible_min_months"] = min_yr
                        field_sources["eligible_min_months"] = (
                            f"{src_label}:eligible_min_years"
                        )
                        min_yr = None
                    if min_yr is not None and min_yr > 0:
                        fields["eligible_min_years"] = min_yr
                        field_sources["eligible_min_years"] = (
                            f"{src_label}:eligible_min_years"
                        )
                    if max_yr is not None and max_yr > 0:
                        fields["eligible_max_years"] = max_yr
                        field_sources["eligible_max_years"] = (
                            f"{src_label}:eligible_max_years"
                        )

                # Operating weeks: try availability/weeks_text first,
                # then term_time_info, then session_types_raw
                avail_raw = extra.get("availability")
                weeks_raw = extra.get("number of weeks opens")
                weeks = parse_operating_weeks(avail_raw, weeks_raw)
                weeks_source_key = None
                if weeks is not None:
                    if weeks_raw and _RE_WEEKS_NUM.search(weeks_raw):
                        weeks_source_key = "number_of_weeks_opens"
                    else:
                        weeks_source_key = "availability"

                if weeks is None:
                    tti = extracted_data.get("term_time_info")
                    if tti:
                        weeks = _AVAILABILITY_WEEKS.get(tti.strip().lower())
                        if weeks is not None:
                            weeks_source_key = "term_time_info"

                if weeks is None:
                    str_raw = extracted_data.get("session_types_raw")
                    if str_raw:
                        str_lower = str_raw.lower()
                        if "all year round" in str_lower:
                            weeks = 52
                            weeks_source_key = "session_types_raw"
                        elif (
                            "school term only" in str_lower
                            and "school holidays" not in str_lower
                        ):
                            weeks = 38
                            weeks_source_key = "session_types_raw"

                if weeks is None:
                    raw_weeks = extracted_data.get("operating_weeks_per_year")
                    try:
                        weeks = int(raw_weeks) if raw_weeks is not None else None
                        weeks_source_key = "operating_weeks_per_year"
                    except (ValueError, TypeError):
                        weeks = None

                if weeks is not None:
                    fields["operating_weeks_per_year"] = weeks
                    field_sources["operating_weeks_per_year"] = (
                        f"{src_label}:{weeks_source_key}"
                    )

                # Funded hours: try extra keys (including marketplace
                # FundedPlaces* and Funded_Provision), then top-level
                # funded_info, then funded_2yr
                funded = parse_funded_hours(extra)
                funded_source_key = "registered_for_funding"
                if funded is None:
                    funded = parse_funded_info(extracted_data.get("funded_info"))
                    funded_source_key = "funded_info"
                if funded is None:
                    f2yr = extracted_data.get("funded_2yr")
                    if f2yr and f2yr.strip().lower() == "yes":
                        funded = True
                        funded_source_key = "funded_2yr"
                if funded is not None:
                    fields["funded_hours_accepted"] = funded
                    field_sources["funded_hours_accepted"] = (
                        f"{src_label}:{funded_source_key}"
                    )

                # Eligible institutions: schools_served or
                # school_pickups_raw
                institutions = parse_schools_served(
                    extracted_data.get("schools_served")
                )
                inst_source_key = "schools_served"
                if not institutions:
                    institutions = parse_school_pickups(
                        extracted_data.get("school_pickups_raw")
                    )
                    inst_source_key = "school_pickups_raw"
                if institutions:
                    fields["eligible_institutions"] = institutions
                    field_sources["eligible_institutions"] = (
                        f"{src_label}:{inst_source_key}"
                    )

                if fields:
                    la_enrichments[(provider_id, care_type)] = {
                        "fields": fields,
                        "field_sources": field_sources,
                    }

        context.log.info(
            f"  Parsed LA extracts: {len(la_enrichments)} providers with enrichable data"
        )

        # 3b: Load care_type rows for those providers and apply updates
        provider_ids = list({pid for pid, _ in la_enrichments})
        if not provider_ids:
            context.log.info("  No LA enrichments to apply")
        else:
            ct_rows_la = []
            with conn.cursor("ct_la_cursor", withhold=True) as cur:
                cur.execute(LOAD_CARE_TYPES_FOR_LA_SQL, {"provider_ids": provider_ids})
                for row in cur:
                    ct_rows_la.append(row)
            context.log.info(f"  {len(ct_rows_la)} care_type rows to update")

            p3_enriched = 0
            p3_age_overwrites = 0
            p3_conflicts = 0
            batch = []

            for (
                ct_id,
                provider_id,
                care_type,
                existing_min_mo,
                existing_min_yr,
                existing_max_yr,
                existing_meta,
            ) in ct_rows_la:
                enrichment = la_enrichments.get((provider_id, care_type))

                if not enrichment:
                    continue

                la_fields = enrichment["fields"]
                la_sources = enrichment["field_sources"]

                # Resolve age: LA overwrites Ofsted (higher priority)
                new_min_mo = la_fields.get("eligible_min_months")
                new_min_yr = la_fields.get("eligible_min_years")
                new_max_yr = la_fields.get("eligible_max_years")

                has_la_age = (
                    new_min_mo is not None
                    or new_min_yr is not None
                    or new_max_yr is not None
                )
                # Detect conflicts (LA vs existing Ofsted)
                conflicts = {}
                if has_la_age and existing_max_yr is not None:
                    if new_max_yr is not None and new_max_yr != existing_max_yr:
                        conflicts["eligible_max_years"] = {
                            "la_extract": new_max_yr,
                            "ofsted:register_combinations": existing_max_yr,
                        }
                        p3_conflicts += 1
                    p3_age_overwrites += 1

                # If LA has age data, use it; otherwise keep existing
                final_min_mo = new_min_mo if has_la_age else existing_min_mo
                final_min_yr = new_min_yr if has_la_age else existing_min_yr
                final_max_yr = new_max_yr if has_la_age else existing_max_yr

                # Merge metadata
                if isinstance(existing_meta, str):
                    existing_meta = json.loads(existing_meta)
                meta = existing_meta or {}
                existing_fs = meta.get("field_sources", {})

                # LA sources overwrite Ofsted sources for age fields
                if has_la_age:
                    # Clear Ofsted age sources that LA is replacing
                    for k in (
                        "eligible_min_months",
                        "eligible_min_years",
                        "eligible_max_years",
                    ):
                        existing_fs.pop(k, None)

                existing_fs.update(la_sources)
                if existing_fs:
                    meta["field_sources"] = existing_fs
                if conflicts:
                    meta["conflicts"] = conflicts

                batch.append(
                    {
                        "id": ct_id,
                        "eligible_min_months": final_min_mo,
                        "eligible_min_years": final_min_yr,
                        "eligible_max_years": final_max_yr,
                        "operating_weeks_per_year": la_fields.get(
                            "operating_weeks_per_year"
                        ),
                        "funded_hours_accepted": la_fields.get("funded_hours_accepted"),
                        "eligible_institutions": la_fields.get("eligible_institutions"),
                        "metadata": json.dumps(meta),
                    }
                )

                p3_enriched += 1

                if len(batch) >= BATCH_SIZE:
                    _flush_updates(conn, batch, UPDATE_LA_SQL)
                    batch.clear()

            _flush_updates(conn, batch, UPDATE_LA_SQL)

            context.log.info(
                f"Phase 3 complete: {p3_enriched} care_type rows updated "
                f"({p3_age_overwrites} age overwrites, {p3_conflicts} conflicts)"
            )

        # ---- Phase 4: School defaults ----
        context.log.info("Phase 4: applying school_based_nursery defaults")

        # 4a: Load census youngest-pupil-age lookup
        census_age_lookup = {}  # urn -> (min_months, min_years)
        with conn.cursor("census_age_cursor", withhold=True) as cur:
            cur.execute(LOAD_CENSUS_MIN_AGE_SQL)
            for urn, age0, age1, age2, age3, age4 in cur:
                min_mo, min_yr = _census_youngest_age(age0, age1, age2, age3, age4)
                if min_mo is not None or min_yr is not None:
                    census_age_lookup[urn] = (min_mo, min_yr)
        context.log.info(f"  Census age lookup: {len(census_age_lookup)} schools")

        # 4b: Load SBN care_type rows with school_urn
        sbn_rows = []
        with conn.cursor("sbn_cursor", withhold=True) as cur:
            cur.execute(LOAD_SBN_SQL)
            for row in cur:
                sbn_rows.append(row)
        context.log.info(f"  {len(sbn_rows)} school_based_nursery rows")

        p4_enriched = 0
        p4_census_age = 0
        p4_default_age = 0
        p4_fields_filled = {
            "eligible_min": 0,
            "eligible_max_years": 0,
            "funded_hours_accepted": 0,
        }
        batch = []

        for (
            ct_id,
            existing_min_mo,
            existing_min_yr,
            existing_max_yr,
            existing_weeks,
            existing_funded,
            existing_meta,
            school_urn,
        ) in sbn_rows:
            if isinstance(existing_meta, str):
                existing_meta = json.loads(existing_meta)
            meta = existing_meta or {}
            existing_fs = meta.get("field_sources", {})

            final_min_mo = existing_min_mo
            final_min_yr = existing_min_yr
            final_max_yr = existing_max_yr
            final_weeks = existing_weeks
            final_funded = existing_funded
            any_filled = False

            # Age: only apply if all min/max are NULL (no prior source)
            if (
                existing_min_mo is None
                and existing_min_yr is None
                and existing_max_yr is None
            ):
                # Try census-derived youngest pupil age
                census_min = census_age_lookup.get(school_urn) if school_urn else None

                if census_min is not None:
                    census_min_mo, census_min_yr = census_min
                    final_min_mo = census_min_mo
                    final_min_yr = census_min_yr
                    if census_min_mo is not None:
                        existing_fs["eligible_min_months"] = (
                            "school_census:youngest_pupil_age"
                        )
                    if census_min_yr is not None:
                        existing_fs["eligible_min_years"] = (
                            "school_census:youngest_pupil_age"
                        )
                    p4_census_age += 1
                else:
                    # Fallback: statutory default
                    final_min_yr = _SBN_DEFAULT_MIN_YEARS
                    existing_fs["eligible_min_years"] = (
                        "school_default:maintained_nursery_class"
                    )
                    p4_default_age += 1

                final_max_yr = _SBN_DEFAULT_MAX_YEARS
                existing_fs["eligible_max_years"] = (
                    "school_default:maintained_nursery_class"
                )
                p4_fields_filled["eligible_min"] += 1
                p4_fields_filled["eligible_max_years"] += 1
                any_filled = True

            if existing_funded is None:
                final_funded = _SBN_DEFAULT_FUNDED
                existing_fs["funded_hours_accepted"] = (
                    "school_default:maintained_nursery_class"
                )
                p4_fields_filled["funded_hours_accepted"] += 1
                any_filled = True

            if not any_filled:
                continue

            if existing_fs:
                meta["field_sources"] = existing_fs

            batch.append(
                {
                    "id": ct_id,
                    "eligible_min_months": final_min_mo,
                    "eligible_min_years": final_min_yr,
                    "eligible_max_years": final_max_yr,
                    "operating_weeks_per_year": final_weeks,
                    "funded_hours_accepted": final_funded,
                    "metadata": json.dumps(meta),
                }
            )
            p4_enriched += 1

            if len(batch) >= BATCH_SIZE:
                _flush_updates(conn, batch, UPDATE_SBN_SQL)
                batch.clear()

        _flush_updates(conn, batch, UPDATE_SBN_SQL)

        context.log.info(
            f"Phase 4 complete: {p4_enriched}/{len(sbn_rows)} rows updated"
        )
        context.log.info(
            f"  Age source: {p4_census_age} census, {p4_default_age} default"
        )
        for field, cnt in p4_fields_filled.items():
            context.log.info(f"  {field}: {cnt} filled")

        # ---- Phase 4b: School club week defaults ----
        context.log.info("Phase 4b: applying school club operating_weeks defaults")

        club_rows = []
        with conn.cursor("school_clubs_cursor", withhold=True) as cur:
            cur.execute(LOAD_SCHOOL_CLUBS_SQL)
            for row in cur:
                club_rows.append(row)
        context.log.info(
            f"  {len(club_rows)} school_based_nursery/breakfast_club/after_school_club rows"
        )

        p4b_enriched = 0
        batch = []

        for ct_id, care_type, existing_weeks, existing_meta in club_rows:
            if existing_weeks is not None:
                continue

            if isinstance(existing_meta, str):
                existing_meta = json.loads(existing_meta)
            meta = existing_meta or {}
            existing_fs = meta.get("field_sources", {})

            source = (
                "school_default:maintained_nursery_class"
                if care_type == "school_based_nursery"
                else "school_default:school_club"
            )
            existing_fs["operating_weeks_per_year"] = source
            meta["field_sources"] = existing_fs

            batch.append(
                {
                    "id": ct_id,
                    "operating_weeks_per_year": _SCHOOL_DEFAULT_WEEKS,
                    "metadata": json.dumps(meta),
                }
            )
            p4b_enriched += 1

            if len(batch) >= BATCH_SIZE:
                _flush_updates(conn, batch, UPDATE_CLUB_WEEKS_SQL)
                batch.clear()

        _flush_updates(conn, batch, UPDATE_CLUB_WEEKS_SQL)
        context.log.info(
            f"Phase 4b complete: {p4b_enriched} rows defaulted to {_SCHOOL_DEFAULT_WEEKS} weeks"
        )

        # ---- Phase 4c: Tiney enrichment ----
        p4c_enriched = 0
        with conn.cursor() as cur:
            cur.execute(
                "SELECT EXISTS ("
                "  SELECT 1 FROM information_schema.tables"
                "  WHERE table_schema = 'tiney' AND table_name = 'childminders'"
                ")"
            )
            has_tiney = cur.fetchone()[0]

        if has_tiney:
            context.log.info("Phase 4c: enriching Tiney childminder care types")
            tiney_ct_rows = []
            with conn.cursor("tiney_ct_cursor", withhold=True) as cur:
                cur.execute(
                    """
                    SELECT ct.id, ct.eligible_min_months, ct.eligible_min_years,
                           ct.eligible_max_years, ct.operating_weeks_per_year,
                           ct.funded_hours_accepted, ct.ofsted_register_combination,
                           ct.metadata,
                           t.age_range, t.operating_weeks_per_year AS tiney_weeks,
                           t.funded_hours_accepted AS tiney_funded,
                           t.ofsted_register_combination AS tiney_register,
                           t.placement_type
                    FROM draft.care_types ct
                    JOIN draft.providers p ON p.provider_id = ct.provider_id
                    JOIN tiney.childminders t ON t.ofsted_urn = p.ofsted_urn
                    WHERE p.ofsted_urn LIKE 'TY%%'
                      AND ct.care_type = 'childminder'
                    """
                )
                for row in cur:
                    tiney_ct_rows.append(row)

            batch = []
            for (
                ct_id,
                existing_min_mo,
                existing_min_yr,
                existing_max_yr,
                existing_weeks,
                existing_funded,
                existing_register,
                existing_meta,
                tiney_age_range,
                tiney_weeks,
                tiney_funded,
                tiney_register,
                tiney_placement,
            ) in tiney_ct_rows:
                if isinstance(existing_meta, str):
                    existing_meta = json.loads(existing_meta)
                meta = existing_meta or {}
                existing_fs = meta.get("field_sources", {})
                changed = False

                # Age range (only if not already set)
                final_min_mo = existing_min_mo
                final_min_yr = existing_min_yr
                final_max_yr = existing_max_yr
                if (
                    existing_min_mo is None
                    and existing_min_yr is None
                    and existing_max_yr is None
                    and tiney_age_range
                ):
                    min_mo, min_yr, max_yr = parse_age_range(tiney_age_range)
                    if min_mo is not None or min_yr is not None or max_yr is not None:
                        final_min_mo = min_mo
                        final_min_yr = min_yr
                        final_max_yr = max_yr
                        if min_mo is not None:
                            existing_fs["eligible_min_months"] = "tiney:age_range"
                        if min_yr is not None:
                            existing_fs["eligible_min_years"] = "tiney:age_range"
                        if max_yr is not None:
                            existing_fs["eligible_max_years"] = "tiney:age_range"
                        changed = True

                # Operating weeks (only if not already set)
                final_weeks = existing_weeks
                if existing_weeks is None and tiney_weeks is not None:
                    final_weeks = tiney_weeks
                    existing_fs["operating_weeks_per_year"] = "tiney:operating_weeks"
                    changed = True

                # Funded hours (only if not already set)
                final_funded = existing_funded
                if existing_funded is None and tiney_funded is not None:
                    final_funded = tiney_funded
                    existing_fs["funded_hours_accepted"] = "tiney:funded_hours"
                    changed = True

                # Register combination (only if not already set)
                final_register = existing_register
                if existing_register is None and tiney_register:
                    final_register = tiney_register
                    existing_fs["ofsted_register_combination"] = "tiney:register"
                    changed = True

                if not changed:
                    continue

                if existing_fs:
                    meta["field_sources"] = existing_fs

                batch.append(
                    {
                        "id": ct_id,
                        "eligible_min_months": final_min_mo,
                        "eligible_min_years": final_min_yr,
                        "eligible_max_years": final_max_yr,
                        "ofsted_register_combination": final_register,
                        "metadata": json.dumps(meta),
                    }
                )
                p4c_enriched += 1

                if len(batch) >= BATCH_SIZE:
                    _flush_updates(conn, batch, UPDATE_AGE_SQL)
                    batch.clear()

            _flush_updates(conn, batch, UPDATE_AGE_SQL)

            # Separately update weeks and funded (uses UPDATE_LA_SQL which
            # handles those columns)
            batch = []
            for (
                ct_id,
                existing_min_mo,
                existing_min_yr,
                existing_max_yr,
                existing_weeks,
                existing_funded,
                existing_register,
                existing_meta,
                tiney_age_range,
                tiney_weeks,
                tiney_funded,
                tiney_register,
                tiney_placement,
            ) in tiney_ct_rows:
                if isinstance(existing_meta, str):
                    existing_meta = json.loads(existing_meta)
                meta = existing_meta or {}

                needs_update = (existing_weeks is None and tiney_weeks is not None) or (
                    existing_funded is None and tiney_funded is not None
                )
                if not needs_update:
                    continue

                batch.append(
                    {
                        "id": ct_id,
                        "eligible_min_months": existing_min_mo,
                        "eligible_min_years": existing_min_yr,
                        "eligible_max_years": existing_max_yr,
                        "operating_weeks_per_year": tiney_weeks
                        if existing_weeks is None
                        else existing_weeks,
                        "funded_hours_accepted": tiney_funded
                        if existing_funded is None
                        else existing_funded,
                        "eligible_institutions": None,
                        "metadata": json.dumps(meta),
                    }
                )

                if len(batch) >= BATCH_SIZE:
                    _flush_updates(conn, batch, UPDATE_LA_SQL)
                    batch.clear()

            _flush_updates(conn, batch, UPDATE_LA_SQL)
            context.log.info(
                f"Phase 4c complete: {p4c_enriched} Tiney care_type rows enriched"
            )
        else:
            context.log.info("Phase 4c: tiney.childminders not found — skipping")

        # ---- Phase 5: Care-type URL enrichment ----
        context.log.info("Phase 5: enriching care types with per-offering URLs")
        from bsil_pipeline.assets.provider_details import _clean_website

        # 5a: Load source URLs per (provider_id, care_type)
        # Group by (provider_id, care_type), pick richest source for tiebreaking
        # Each candidate: (source_id, source_url, extracted_website, richness)
        ct_url_candidates = {}
        with conn.cursor("ct_url_cursor", withhold=True) as cur:
            cur.execute(LOAD_CT_URLS_SQL)
            for (
                provider_id,
                care_type,
                source_id,
                source_url,
                extracted_website,
                extracted_data,
            ) in cur:
                key = (provider_id, care_type)
                if extracted_data and isinstance(extracted_data, str):
                    extracted_data = json.loads(extracted_data)
                richness = (
                    sum(1 for v in (extracted_data or {}).values() if v is not None)
                    if extracted_data
                    else 0
                )
                if key not in ct_url_candidates:
                    ct_url_candidates[key] = []
                ct_url_candidates[key].append(
                    (source_id, source_url, extracted_website, richness)
                )

        # 5b: Resolve best URL per (provider_id, care_type), tracking source
        # ct_urls: key -> (fis_url, fis_source_id, website, website_source_id)
        ct_urls = {}
        for key, candidates in ct_url_candidates.items():
            candidates.sort(key=lambda x: x[3], reverse=True)
            best_fis_url = None
            best_fis_source = None
            best_website = None
            best_website_source = None
            for source_id, source_url, extracted_website, _ in candidates:
                if best_fis_url is None and source_url:
                    best_fis_url = source_url
                    best_fis_source = source_id
                if best_website is None and extracted_website:
                    cleaned = _clean_website(extracted_website)
                    if cleaned:
                        best_website = cleaned
                        best_website_source = source_id
                if best_fis_url and best_website:
                    break
            ct_urls[key] = (
                best_fis_url,
                best_fis_source,
                best_website,
                best_website_source,
            )

        # 5c: Load provider-level URLs for dedup comparison
        provider_ids_with_urls = list({pid for pid, _ in ct_urls})
        provider_url_lookup = {}
        if provider_ids_with_urls:
            with conn.cursor("prov_url_cursor", withhold=True) as cur:
                cur.execute(
                    LOAD_PROVIDER_URLS_SQL,
                    {"provider_ids": provider_ids_with_urls},
                )
                for provider_id, website, fis_url in cur:
                    provider_url_lookup[provider_id] = (website, fis_url)

        # 5d: Load existing metadata for care types that will be updated
        ct_metadata_lookup = {}
        if provider_ids_with_urls:
            with conn.cursor("ct_meta_cursor", withhold=True) as cur:
                cur.execute(
                    "SELECT provider_id, care_type, metadata FROM draft.care_types "
                    "WHERE provider_id = ANY(%(provider_ids)s)",
                    {"provider_ids": provider_ids_with_urls},
                )
                for provider_id, care_type, metadata in cur:
                    if isinstance(metadata, str):
                        metadata = json.loads(metadata)
                    ct_metadata_lookup[(provider_id, care_type)] = metadata or {}

        # 5e: Apply URLs, deduplicating against provider-level
        p5_fis_url_set = 0
        p5_website_set = 0
        batch = []
        for (provider_id, care_type), (
            ct_fis_url,
            fis_src,
            ct_website,
            web_src,
        ) in ct_urls.items():
            prov_website, prov_fis_url = provider_url_lookup.get(
                provider_id, (None, None)
            )

            # Only store if different from provider-level
            final_fis_url = ct_fis_url if ct_fis_url != prov_fis_url else None
            final_website = ct_website if ct_website != prov_website else None

            if final_fis_url is None and final_website is None:
                continue

            # Update metadata with field_sources
            meta = ct_metadata_lookup.get((provider_id, care_type), {}).copy()
            field_sources = meta.get("field_sources", {})
            if final_fis_url:
                field_sources["fis_url"] = f"la_scrape:{fis_src}"
                p5_fis_url_set += 1
            if final_website:
                field_sources["website"] = f"la_scrape:{web_src}"
                p5_website_set += 1
            meta["field_sources"] = field_sources

            batch.append(
                {
                    "provider_id": provider_id,
                    "care_type": care_type,
                    "website": final_website,
                    "fis_url": final_fis_url,
                    "metadata": json.dumps(meta),
                }
            )

            if len(batch) >= BATCH_SIZE:
                _flush_updates(conn, batch, UPDATE_CT_URLS_SQL)
                batch.clear()

        _flush_updates(conn, batch, UPDATE_CT_URLS_SQL)
        context.log.info(
            f"Phase 5 complete: {p5_fis_url_set} fis_url set, "
            f"{p5_website_set} website set"
        )

        # ---- Phase 6: Reassign nursery-like care types on school providers ----
        # Temporary rule: private_nursery on school institutions → school_based_nursery
        context.log.info(
            "Phase 6: reassigning private_nursery → school_based_nursery "
            "on school institution providers"
        )
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE draft.care_types ct
                SET care_type = 'school_based_nursery',
                    metadata = jsonb_set(
                        COALESCE(ct.metadata, '{}'::jsonb),
                        '{reassigned_from}',
                        '"private_nursery"'
                    )
                FROM draft.providers p
                WHERE ct.provider_id = p.provider_id
                  AND ct.care_type = 'private_nursery'
                  AND p.institution_type LIKE 'school_%'
            """)
            p6_reassigned = cur.rowcount
            conn.commit()
        context.log.info(f"Phase 6 complete: {p6_reassigned} rows reassigned")

        # ---- Phase 6b: Deduplicate school_based_nursery rows ----
        # Phase 6 can create duplicates when both LA scrape and school_census
        # contributed an SBN row. Keep the LA-scraped row (richer metadata/URLs),
        # drop the school_census duplicate.
        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM draft.care_types
                WHERE id IN (
                    SELECT ct.id
                    FROM draft.care_types ct
                    JOIN (
                        SELECT provider_id
                        FROM draft.care_types
                        WHERE care_type = 'school_based_nursery'
                        GROUP BY provider_id
                        HAVING COUNT(*) > 1
                    ) dupes ON dupes.provider_id = ct.provider_id
                    WHERE ct.care_type = 'school_based_nursery'
                      AND ct.metadata @> '{"reassigned_from": "private_nursery"}'::jsonb IS NOT TRUE
                      AND EXISTS (
                          SELECT 1 FROM draft.care_types other
                          WHERE other.provider_id = ct.provider_id
                            AND other.care_type = 'school_based_nursery'
                            AND other.id != ct.id
                            AND other.metadata @> '{"reassigned_from": "private_nursery"}'::jsonb
                      )
                )
            """)
            p6b_deduped = cur.rowcount
            conn.commit()
        if p6b_deduped:
            context.log.info(
                f"Phase 6b: removed {p6b_deduped} duplicate school_based_nursery rows"
            )

        # ---- Phase 7: Age range completeness ----
        context.log.info("Phase 7: ensuring age range min+max always paired")
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE draft.care_types
                SET eligible_min_months = 0
                WHERE eligible_max_years IS NOT NULL
                  AND eligible_min_months IS NULL
                  AND eligible_min_years IS NULL
            """)
            p7_filled_min = cur.rowcount
            cur.execute("""
                UPDATE draft.care_types
                SET eligible_min_months = NULL,
                    eligible_min_years = NULL
                WHERE eligible_max_years IS NULL
                  AND (eligible_min_months IS NOT NULL
                       OR eligible_min_years IS NOT NULL)
            """)
            p7_cleared = cur.rowcount
            conn.commit()
        context.log.info(
            f"Phase 7 complete: {p7_filled_min} rows defaulted min_months=0, "
            f"{p7_cleared} rows cleared (min without max)"
        )

        # ---- Final stats ----
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    count(*) AS total,
                    count(*) FILTER (WHERE eligible_max_years IS NOT NULL) AS has_age,
                    count(*) FILTER (WHERE operating_weeks_per_year IS NOT NULL)
                        AS has_weeks,
                    count(*) FILTER (WHERE funded_hours_accepted IS NOT NULL)
                        AS has_funded
                FROM draft.care_types ct
            """)
            stats = cur.fetchone()

        context.log.info(f"Final stats ({stats[0]} total rows):")
        context.log.info(f"  age range:  {stats[1]} ({stats[1] / stats[0] * 100:.1f}%)")
        context.log.info(f"  weeks/year: {stats[2]} ({stats[2] / stats[0] * 100:.1f}%)")
        context.log.info(
            f"  funded hours: {stats[3]} ({stats[3] / stats[0] * 100:.1f}%)"
        )

    return {
        "total_rows": MetadataValue.int(inserted),
        "ofsted_age_enriched": MetadataValue.int(p2_enriched),
        "la_enriched": MetadataValue.int(p3_enriched if provider_ids else 0),
        "school_defaults_applied": MetadataValue.int(p4_enriched),
        "school_nursery_reassigned": MetadataValue.int(p6_reassigned),
        "age_range_min_defaulted": MetadataValue.int(p7_filled_min),
        "age_range_partial_cleared": MetadataValue.int(p7_cleared),
        "has_age": MetadataValue.int(stats[1]),
        "has_weeks": MetadataValue.int(stats[2]),
        "has_funded": MetadataValue.int(stats[3]),
        **{f"ct_{ct}": MetadataValue.int(cnt) for ct, cnt in dist.items()},
    }
