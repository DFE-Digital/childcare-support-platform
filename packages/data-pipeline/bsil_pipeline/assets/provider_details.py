"""Dagster asset enriching draft.providers with contact/location fields.

Resolves address, lat/lon, phone, email, website, and fis_url from all upstream sources
with priority ordering based on provider type (school vs Ofsted-linked vs LA-only).
Tracks provenance of each resolved field in metadata.field_sources.
"""

import hashlib
import json
import logging
import re
from collections import defaultdict
from datetime import datetime

from dagster import asset, AssetExecutionContext, MetadataValue

from bsil_pipeline.assets._geocode_helpers import bbox_fallback, outward_code
from bsil_pipeline.automation import PIPELINE_CONDITION
from bsil_pipeline.resources.postgres import BsilPostgresResource

# ---------- Constants ----------

BATCH_SIZE = 500
_COARSE_BBOX_TYPES = frozenset({"local_authority", "county"})

DETAIL_FIELDS = [
    "address_line1",
    "address_line2",
    "city",
    "latitude",
    "longitude",
    "phone",
    "email",
    "website",
    "fis_url",
    "ofsted_legacy_rating",
    "ofsted_inspection_date",
    "ofsted_framework",
    "ofsted_safeguarding_met",
    "ofsted_achievement",
    "ofsted_curriculum_and_teaching",
    "ofsted_behaviour_attitudes_routines",
    "ofsted_childrens_welfare_wellbeing",
    "ofsted_attendance_and_behaviour",
    "ofsted_personal_development_wellbeing",
    "ofsted_inclusion",
    "ofsted_leadership_and_governance",
    "ofsted_early_years",
    "ofsted_sixth_form",
    "ofsted_legacy_quality_of_education",
    "ofsted_legacy_behaviour_and_attitudes",
    "ofsted_legacy_personal_development",
    "ofsted_legacy_leadership_and_management",
    "ofsted_legacy_early_years",
    "ofsted_legacy_sixth_form",
    "ofsted_ccr_met",
    "ofsted_vcr_met",
    "ofsted_oosc_met",
    "registered_places",
    "staff_graduate_percentage",
    "staff_turnover_percentage",
    "has_garden",
    "has_kitchen",
    "cma_agency",
    "cma_qa_grading",
    "cma_inspection_date",
    "bbox_geo_type",
    "bbox_geo_code",
]

# ---------- SQL ----------

ALTER_SQL = """
ALTER TABLE draft.providers
    ADD COLUMN IF NOT EXISTS address_line1 TEXT,
    ADD COLUMN IF NOT EXISTS address_line2 TEXT,
    ADD COLUMN IF NOT EXISTS city TEXT,
    ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS phone TEXT,
    ADD COLUMN IF NOT EXISTS email TEXT,
    ADD COLUMN IF NOT EXISTS website TEXT,
    ADD COLUMN IF NOT EXISTS fis_url TEXT,
    ADD COLUMN IF NOT EXISTS ofsted_legacy_rating TEXT,
    ADD COLUMN IF NOT EXISTS ofsted_inspection_date DATE,
    ADD COLUMN IF NOT EXISTS ofsted_framework TEXT,
    ADD COLUMN IF NOT EXISTS ofsted_safeguarding_met BOOLEAN,
    ADD COLUMN IF NOT EXISTS ofsted_achievement TEXT,
    ADD COLUMN IF NOT EXISTS ofsted_curriculum_and_teaching TEXT,
    ADD COLUMN IF NOT EXISTS ofsted_behaviour_attitudes_routines TEXT,
    ADD COLUMN IF NOT EXISTS ofsted_childrens_welfare_wellbeing TEXT,
    ADD COLUMN IF NOT EXISTS ofsted_attendance_and_behaviour TEXT,
    ADD COLUMN IF NOT EXISTS ofsted_personal_development_wellbeing TEXT,
    ADD COLUMN IF NOT EXISTS ofsted_inclusion TEXT,
    ADD COLUMN IF NOT EXISTS ofsted_leadership_and_governance TEXT,
    ADD COLUMN IF NOT EXISTS ofsted_early_years TEXT,
    ADD COLUMN IF NOT EXISTS ofsted_sixth_form TEXT,
    ADD COLUMN IF NOT EXISTS ofsted_legacy_quality_of_education TEXT,
    ADD COLUMN IF NOT EXISTS ofsted_legacy_behaviour_and_attitudes TEXT,
    ADD COLUMN IF NOT EXISTS ofsted_legacy_personal_development TEXT,
    ADD COLUMN IF NOT EXISTS ofsted_legacy_leadership_and_management TEXT,
    ADD COLUMN IF NOT EXISTS ofsted_legacy_early_years TEXT,
    ADD COLUMN IF NOT EXISTS ofsted_legacy_sixth_form TEXT,
    ADD COLUMN IF NOT EXISTS ofsted_ccr_met BOOLEAN,
    ADD COLUMN IF NOT EXISTS ofsted_vcr_met BOOLEAN,
    ADD COLUMN IF NOT EXISTS ofsted_oosc_met BOOLEAN,
    ADD COLUMN IF NOT EXISTS registered_places INTEGER,
    ADD COLUMN IF NOT EXISTS staff_graduate_percentage NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS staff_turnover_percentage NUMERIC(5,2),
    ADD COLUMN IF NOT EXISTS has_garden BOOLEAN,
    ADD COLUMN IF NOT EXISTS has_kitchen BOOLEAN,
    ADD COLUMN IF NOT EXISTS cma_agency TEXT,
    ADD COLUMN IF NOT EXISTS cma_qa_grading TEXT,
    ADD COLUMN IF NOT EXISTS cma_inspection_date DATE,
    ADD COLUMN IF NOT EXISTS bbox_geo_type TEXT,
    ADD COLUMN IF NOT EXISTS bbox_geo_code TEXT
"""

LOAD_PROVIDERS_SQL = """
SELECT provider_id, school_urn, ofsted_urn, postcode, lad25cd, metadata
FROM draft.providers
"""

LOAD_GIAS_SQL = """
SELECT urn, street, locality, town, NULLIF(postcode, 'NULL') AS postcode,
       latitude, longitude, telephone_num, school_website
FROM dfe.gias_schools
WHERE establishment_status = 'Open'
"""

LOAD_OFSTED_SQL = """
SELECT i.provider_urn,
       COALESCE(NULLIF(i.provider_address_line_1, 'REDACTED'), sr.provider_address_line1, ca.address_line_1) AS address_line1,
       COALESCE(NULLIF(i.provider_address_line_2, 'REDACTED'), sr.provider_address_line2, ca.address_line_2) AS address_line2,
       COALESCE(NULLIF(i.provider_town, 'REDACTED'), sr.provider_town, ca.town) AS town,
       COALESCE(NULLIF(NULLIF(i.provider_postcode, 'REDACTED'), ''), sr.provider_postcode, ca.postcode) AS postcode
FROM ofsted.inspections i
LEFT JOIN ofsted.scrape_results sr
    ON i.provider_urn = sr.provider_urn
    AND sr.scrape_status IN ('success', 'partial')
LEFT JOIN ofsted.consented_addresses ca
    ON i.provider_urn = ca.provider_urn
"""

LOAD_OFSTED_INSPECTIONS_ONLY_SQL = """
SELECT provider_urn,
       NULLIF(provider_address_line_1, 'REDACTED') AS address_line1,
       NULLIF(provider_address_line_2, 'REDACTED') AS address_line2,
       NULLIF(provider_town, 'REDACTED') AS town,
       NULLIF(NULLIF(provider_postcode, 'REDACTED'), '') AS postcode
FROM ofsted.inspections
"""

LOAD_OFSTED_GEO_SQL = """
SELECT provider_urn, latitude, longitude
FROM os.ofsted_places
WHERE geocode_status IN ('success', 'success_postcode_fallback')
"""

LOAD_OFSTED_META_SQL = """
SELECT provider_urn,
       most_recent_full_overall_effectiveness,
       most_recent_full_inspection_date
FROM ofsted.inspections
WHERE most_recent_full_overall_effectiveness IS NOT NULL
  AND most_recent_full_overall_effectiveness != ''
"""

LOAD_OFSTED_COMPLIANCE_SQL = """
SELECT provider_urn,
       CASE
           WHEN ccr_requirements_suitability = 'Met' THEN true
           WHEN ccr_requirements_suitability LIKE 'Not Met%%' THEN false
           ELSE NULL
       END AS ccr_met,
       CASE
           WHEN vcr_requirements_suitability = 'Met' THEN true
           WHEN vcr_requirements_suitability LIKE 'Not Met%%' THEN false
           ELSE NULL
       END AS vcr_met,
       CASE
           WHEN oosc_overall_effectiveness = 'Met' THEN true
           WHEN oosc_overall_effectiveness LIKE 'Not Met%%' THEN false
           ELSE NULL
       END AS oosc_met
FROM ofsted.inspections
WHERE ccr_requirements_suitability IS NOT NULL
   OR vcr_requirements_suitability IS NOT NULL
   OR oosc_overall_effectiveness IS NOT NULL
"""

LOAD_SCHOOL_INSPECTIONS_SQL = """
SELECT urn,
       inspection_date,
       safeguarding_standards,
       achievement,
       curriculum_and_teaching,
       attendance_and_behaviour,
       personal_development_wellbeing,
       inclusion,
       leadership_and_governance,
       early_years,
       post_16,
       oeif_inspection_date,
       oeif_overall_effectiveness,
       oeif_safeguarding_effective,
       oeif_quality_of_education,
       oeif_behaviour_and_attitudes,
       oeif_personal_development,
       oeif_leadership_and_management,
       oeif_early_years,
       oeif_sixth_form,
       ungraded_inspection_date,
       ungraded_overall_outcome
FROM ofsted.school_inspections
"""

LOAD_OFSTED_PLACES_SQL = """
SELECT provider_urn, places::integer
FROM ofsted.inspections
WHERE places IS NOT NULL AND places != '' AND places != '0'
"""

LOAD_LA_EXTRACTS_SQL = """
SELECT ps.provider_id, ps.source_id, e.extracted_data, sr.source_url
FROM draft.provider_sources ps
JOIN la.extract_results e
    ON e.lad25cd = split_part(ps.source_id, ':', 1)
   AND e.provider_id = substring(ps.source_id FROM position(':' IN ps.source_id) + 1)
LEFT JOIN la.scrape_results sr
    ON sr.lad25cd = split_part(ps.source_id, ':', 1)
   AND sr.provider_id = substring(ps.source_id FROM position(':' IN ps.source_id) + 1)
WHERE ps.source = 'la_scrape'
ORDER BY ps.provider_id
"""

LOAD_LA_GEO_SQL = """
SELECT ps.provider_id, p.latitude, p.longitude
FROM draft.provider_sources ps
JOIN os.la_places p
    ON p.lad25cd = split_part(ps.source_id, ':', 1)
   AND p.provider_id = substring(ps.source_id FROM position(':' IN ps.source_id) + 1)
WHERE ps.source = 'la_scrape'
  AND p.geocode_status IN ('success', 'success_postcode_fallback')
"""

LOAD_OFSTED_BBOX_SQL = """
SELECT provider_urn, bbox_geo_type, bbox_geo_code
FROM os.ofsted_places
WHERE bbox_geo_type IS NOT NULL
"""

LOAD_LA_BBOX_SQL = """
SELECT ps.provider_id, p.bbox_geo_type, p.bbox_geo_code
FROM draft.provider_sources ps
JOIN os.la_places p
    ON p.lad25cd = split_part(ps.source_id, ':', 1)
   AND p.provider_id = substring(ps.source_id FROM position(':' IN ps.source_id) + 1)
WHERE ps.source = 'la_scrape'
  AND p.bbox_geo_type IS NOT NULL
"""

LOAD_TINEY_SQL = """
SELECT ofsted_urn, website_url, registered_places, address_line_1, address_city,
       cma_qa_grading, last_inspection_date
FROM tiney.childminders
WHERE tiney_lifecycle_status = 'open'
"""

UPDATE_SQL = """
UPDATE draft.providers
SET address_line1 = %(address_line1)s,
    address_line2 = %(address_line2)s,
    city = %(city)s,
    latitude = %(latitude)s,
    longitude = %(longitude)s,
    phone = %(phone)s,
    email = %(email)s,
    website = %(website)s,
    fis_url = %(fis_url)s,
    ofsted_legacy_rating = %(ofsted_legacy_rating)s,
    ofsted_inspection_date = %(ofsted_inspection_date)s,
    ofsted_framework = %(ofsted_framework)s,
    ofsted_safeguarding_met = %(ofsted_safeguarding_met)s,
    ofsted_achievement = %(ofsted_achievement)s,
    ofsted_curriculum_and_teaching = %(ofsted_curriculum_and_teaching)s,
    ofsted_behaviour_attitudes_routines = %(ofsted_behaviour_attitudes_routines)s,
    ofsted_childrens_welfare_wellbeing = %(ofsted_childrens_welfare_wellbeing)s,
    ofsted_attendance_and_behaviour = %(ofsted_attendance_and_behaviour)s,
    ofsted_personal_development_wellbeing = %(ofsted_personal_development_wellbeing)s,
    ofsted_inclusion = %(ofsted_inclusion)s,
    ofsted_leadership_and_governance = %(ofsted_leadership_and_governance)s,
    ofsted_early_years = %(ofsted_early_years)s,
    ofsted_sixth_form = %(ofsted_sixth_form)s,
    ofsted_legacy_quality_of_education = %(ofsted_legacy_quality_of_education)s,
    ofsted_legacy_behaviour_and_attitudes = %(ofsted_legacy_behaviour_and_attitudes)s,
    ofsted_legacy_personal_development = %(ofsted_legacy_personal_development)s,
    ofsted_legacy_leadership_and_management = %(ofsted_legacy_leadership_and_management)s,
    ofsted_legacy_early_years = %(ofsted_legacy_early_years)s,
    ofsted_legacy_sixth_form = %(ofsted_legacy_sixth_form)s,
    ofsted_ccr_met = %(ofsted_ccr_met)s,
    ofsted_vcr_met = %(ofsted_vcr_met)s,
    ofsted_oosc_met = %(ofsted_oosc_met)s,
    registered_places = %(registered_places)s,
    staff_graduate_percentage = %(staff_graduate_percentage)s,
    staff_turnover_percentage = %(staff_turnover_percentage)s,
    has_garden = %(has_garden)s,
    has_kitchen = %(has_kitchen)s,
    cma_agency = %(cma_agency)s,
    cma_qa_grading = %(cma_qa_grading)s,
    cma_inspection_date = %(cma_inspection_date)s,
    bbox_geo_type = %(bbox_geo_type)s,
    bbox_geo_code = %(bbox_geo_code)s,
    metadata = %(metadata)s
WHERE provider_id = %(provider_id)s
"""


# ---------- Data loaders ----------


def _load_gias(conn):
    """Load GIAS school records → {urn: {field: value}}."""
    result = {}
    with conn.cursor("gias_detail_cursor", withhold=True) as cur:
        cur.execute(LOAD_GIAS_SQL)
        for urn, street, locality, town, postcode, lat, lon, phone, website in cur:
            result[urn] = {
                "address_line1": street,
                "address_line2": locality,
                "city": town,
                "postcode": postcode,
                "latitude": float(lat) if lat is not None else None,
                "longitude": float(lon) if lon is not None else None,
                "phone": _normalise_phone(phone) if phone else None,
                "website": _clean_website(website),
            }
    return result


def _load_ofsted(conn):
    """Load Ofsted address data → {urn: {field: value}}.

    Coalesces inspections + scrape_results, filtering REDACTED values.
    """
    # Check whether scrape_results exists
    with conn.cursor() as cur:
        cur.execute(
            "SELECT EXISTS ("
            "  SELECT 1 FROM information_schema.tables"
            "  WHERE table_schema = 'ofsted' AND table_name = 'scrape_results'"
            ")"
        )
        has_scrape = cur.fetchone()[0]

    sql = LOAD_OFSTED_SQL if has_scrape else LOAD_OFSTED_INSPECTIONS_ONLY_SQL
    result = {}
    with conn.cursor("ofsted_detail_cursor", withhold=True) as cur:
        cur.execute(sql)
        for urn, addr1, addr2, town, postcode in cur:
            if not urn:
                continue
            result[urn] = {
                "address_line1": _strip_address_prefix(addr1),
                "address_line2": _strip_address_prefix(addr2),
                "city": town,
                "postcode": postcode,
            }
    return result


def _load_ofsted_geo(conn):
    """Load geocoded Ofsted places → {urn: (lat, lon)}."""
    result = {}
    with conn.cursor() as cur:
        cur.execute(
            "SELECT EXISTS ("
            "  SELECT 1 FROM information_schema.tables"
            "  WHERE table_schema = 'os' AND table_name = 'ofsted_places'"
            ")"
        )
        if not cur.fetchone()[0]:
            return result

    with conn.cursor("ofsted_geo_cursor", withhold=True) as cur:
        cur.execute(LOAD_OFSTED_GEO_SQL)
        for urn, lat, lon in cur:
            result[urn] = (float(lat), float(lon))
    return result


_OFSTED_NUMERIC_RATING = {
    "1": "Outstanding",
    "2": "Good",
    "3": "Requires Improvement",
    "4": "Inadequate",
}

_OFSTED_NEW_LABELS = frozenset(
    {
        "Exceptional",
        "Strong standard",
        "Expected standard",
        "Needs attention",
        "Urgent improvement",
    }
)

_logger = logging.getLogger(__name__)


def _map_ofsted_rating(raw):
    """Map numeric Ofsted rating to text label, pass through new-system labels."""
    if raw in _OFSTED_NUMERIC_RATING:
        return _OFSTED_NUMERIC_RATING[raw]
    if raw in _OFSTED_NEW_LABELS:
        return raw
    _logger.warning("Unrecognised Ofsted rating value: %s", raw)
    return raw


_UNGRADED_OUTCOME_MAP = {
    "school remains good": "Good",
    "school remains good (improving) - s5 next": "Good",
    "school remains good (concerns) - s5 next": "Good",
    "school remains outstanding": "Outstanding",
    "school remains outstanding (concerns) - s5 next": "Outstanding",
}


def _derive_rating_from_ungraded(outcome: str) -> str | None:
    """Derive a legacy rating from an ungraded inspection outcome."""
    if not outcome:
        return None
    return _UNGRADED_OUTCOME_MAP.get(outcome.strip().lower())


def _map_ofsted_subgrade(raw):
    """Map numeric OEIF sub-grade to text label, treating '0' and '9' as N/A."""
    if raw is None or raw in ("", "0", "9"):
        return None
    return _map_ofsted_rating(raw)


def _parse_ofsted_date(raw):
    """Parse DD/MM/YYYY Ofsted date to ISO YYYY-MM-DD string."""
    if not raw:
        return None
    raw = raw.strip()
    try:
        return datetime.strptime(raw, "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return raw


def _load_ofsted_meta(conn):
    """Load Ofsted rating/inspection metadata → {urn: {rating, inspection_date}}."""
    result = {}
    with conn.cursor("ofsted_meta_cursor", withhold=True) as cur:
        cur.execute(LOAD_OFSTED_META_SQL)
        for urn, effectiveness, inspection_date in cur:
            if not urn:
                continue
            result[urn] = {
                "ofsted_legacy_rating": _map_ofsted_rating(effectiveness),
                "ofsted_inspection_date": _parse_ofsted_date(inspection_date),
            }
    return result


def _load_ofsted_compliance(conn):
    """Load CCR/VCR/OOSC compliance data → {urn: {ccr_met, vcr_met, oosc_met}}."""
    result = {}
    with conn.cursor("ofsted_compliance_cursor", withhold=True) as cur:
        cur.execute(LOAD_OFSTED_COMPLIANCE_SQL)
        for urn, ccr_met, vcr_met, oosc_met in cur:
            if not urn:
                continue
            result[urn] = {"ccr_met": ccr_met, "vcr_met": vcr_met, "oosc_met": oosc_met}
    return result


def _load_school_inspections(conn):
    """Load school inspection data → {urn: {...}}.

    Returns both report-card grades and legacy OEIF data per school URN.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT EXISTS ("
            "  SELECT 1 FROM information_schema.tables"
            "  WHERE table_schema = 'ofsted' AND table_name = 'school_inspections'"
            ")"
        )
        if not cur.fetchone()[0]:
            return {}

    result = {}
    with conn.cursor("school_insp_cursor", withhold=True) as cur:
        cur.execute(LOAD_SCHOOL_INSPECTIONS_SQL)
        for (
            urn,
            inspection_date,
            safeguarding,
            achievement,
            curriculum,
            attendance,
            personal_dev,
            inclusion,
            leadership,
            early_years,
            post_16,
            oeif_date,
            oeif_overall,
            oeif_safeguarding,
            oeif_quality_of_ed,
            oeif_behaviour,
            oeif_personal_dev,
            oeif_leadership,
            oeif_early_years,
            oeif_sixth_form,
            ungraded_date,
            ungraded_outcome,
        ) in cur:
            if not urn:
                continue
            result[urn] = {
                "inspection_date": _parse_ofsted_date(inspection_date),
                "safeguarding_met": safeguarding == "Met" if safeguarding else None,
                "achievement": achievement,
                "curriculum_and_teaching": curriculum,
                "attendance_and_behaviour": attendance,
                "personal_development_wellbeing": personal_dev,
                "inclusion": inclusion,
                "leadership_and_governance": leadership,
                "early_years": early_years,
                "sixth_form": post_16,
                "oeif_date": _parse_ofsted_date(oeif_date),
                "oeif_overall": oeif_overall,
                "oeif_safeguarding": oeif_safeguarding,
                "oeif_quality_of_education": oeif_quality_of_ed,
                "oeif_behaviour_and_attitudes": oeif_behaviour,
                "oeif_personal_development": oeif_personal_dev,
                "oeif_leadership_and_management": oeif_leadership,
                "oeif_early_years": oeif_early_years,
                "oeif_sixth_form": oeif_sixth_form,
                "ungraded_date": _parse_ofsted_date(ungraded_date),
                "ungraded_overall_outcome": ungraded_outcome,
            }
    return result


def _load_ofsted_places(conn):
    """Load Ofsted registered places → {urn: places_int}."""
    result = {}
    with conn.cursor("ofsted_places_cursor", withhold=True) as cur:
        cur.execute(LOAD_OFSTED_PLACES_SQL)
        for urn, places in cur:
            if urn and places and places > 0:
                result[urn] = places
    return result


_RE_LEADING_INT = re.compile(r"^(\d+)")
_RE_ADMISSIONS_INT = re.compile(r"Admissions:\s*(\d+)", re.IGNORECASE)


def _parse_registered_children(raw):
    """Parse 'number of children registered' into an integer.

    Handles: "26", "6 (3 under 5 years)", "Admissions: 52 (Full Time Places)",
    "N/A", etc.  Returns int or None.
    """
    if not raw:
        return None
    raw = raw.strip()
    if raw.lower() in ("n/a", "-", ""):
        return None
    # "Admissions: 52 ..."
    m = _RE_ADMISSIONS_INT.search(raw)
    if m:
        return int(m.group(1))
    # Leading integer: "6 (3 under 5 years)" -> 6, "26" -> 26
    m = _RE_LEADING_INT.match(raw)
    if m:
        return int(m.group(1))
    return None


def _load_la_extracts(conn):
    """Load LA scrape extracted data → {provider_id: [(source_id, {fields})]}.

    Multiple LA sources may map to one provider. We keep all, sorted so that
    entries with more fields come first (richer data preferred).
    """
    raw = defaultdict(list)
    with conn.cursor("la_extract_cursor", withhold=True) as cur:
        cur.execute(LOAD_LA_EXTRACTS_SQL)
        for provider_id, source_id, extracted_data, source_url in cur:
            if not extracted_data:
                continue
            if isinstance(extracted_data, str):
                extracted_data = json.loads(extracted_data)

            extra = extracted_data.get("extra") or {}
            fields = {
                "address_line1": extracted_data.get("address_line1"),
                "address_line2": extracted_data.get("address_line2"),
                "city": extracted_data.get("town"),
                "phone": _clean_phone(extracted_data.get("phone")),
                "email": _clean_email(extracted_data.get("email")),
                "website": _clean_website(extracted_data.get("website")),
                "latitude": _safe_float(extracted_data.get("latitude")),
                "longitude": _safe_float(extracted_data.get("longitude")),
                "registered_places": _parse_registered_children(
                    extra.get("number of children registered")
                )
                or _parse_registered_children(
                    str(extracted_data["places_total"])
                    if extracted_data.get("places_total") is not None
                    else None
                ),
            }
            # Count non-null fields for ranking
            richness = sum(1 for v in fields.values() if v is not None)
            raw[provider_id].append((source_id, fields, richness))

    # Sort each provider's extracts by richness descending
    result = {}
    for pid, entries in raw.items():
        entries.sort(key=lambda x: x[2], reverse=True)
        result[pid] = [(sid, flds) for sid, flds, _ in entries]
    return result


def _load_la_geo(conn):
    """Load geocoded LA places → {provider_id: (lat, lon)}.

    If multiple LA sources for a provider have geocodes, take the first one.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT EXISTS ("
            "  SELECT 1 FROM information_schema.tables"
            "  WHERE table_schema = 'os' AND table_name = 'la_places'"
            ")"
        )
        if not cur.fetchone()[0]:
            return {}

    result = {}
    with conn.cursor("la_geo_cursor", withhold=True) as cur:
        cur.execute(LOAD_LA_GEO_SQL)
        for provider_id, lat, lon in cur:
            if provider_id not in result:
                result[provider_id] = (float(lat), float(lon))
    return result


def _load_ofsted_bbox(conn):
    """Load Ofsted bbox assignments → {urn: (geo_type, geo_code)}."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT EXISTS ("
            "  SELECT 1 FROM information_schema.tables"
            "  WHERE table_schema = 'os' AND table_name = 'ofsted_places'"
            ")"
        )
        if not cur.fetchone()[0]:
            return {}

    result = {}
    with conn.cursor("ofsted_bbox_cursor", withhold=True) as cur:
        cur.execute(LOAD_OFSTED_BBOX_SQL)
        for urn, geo_type, geo_code in cur:
            result[urn] = (geo_type, geo_code)
    return result


def _load_la_bbox(conn):
    """Load LA bbox assignments → {provider_id: (geo_type, geo_code)}.

    If multiple LA sources for a provider have bbox, take the first one.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT EXISTS ("
            "  SELECT 1 FROM information_schema.tables"
            "  WHERE table_schema = 'os' AND table_name = 'la_places'"
            ")"
        )
        if not cur.fetchone()[0]:
            return {}

    result = {}
    with conn.cursor("la_bbox_cursor", withhold=True) as cur:
        cur.execute(LOAD_LA_BBOX_SQL)
        for provider_id, geo_type, geo_code in cur:
            if provider_id not in result:
                result[provider_id] = (geo_type, geo_code)
    return result


def _load_tiney(conn):
    """Load Tiney childminder data → {urn: {fields}}.

    Provides website, registered_places (default 6), address, and city.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT EXISTS ("
            "  SELECT 1 FROM information_schema.tables"
            "  WHERE table_schema = 'tiney' AND table_name = 'childminders'"
            ")"
        )
        if not cur.fetchone()[0]:
            return {}

    result = {}
    with conn.cursor("tiney_detail_cursor", withhold=True) as cur:
        cur.execute(LOAD_TINEY_SQL)
        for urn, website, places, addr1, city, qa_grading, inspection_date in cur:
            if not urn:
                continue
            result[urn] = {
                "address_line1": addr1,
                "address_line2": None,
                "city": city,
                "phone": None,
                "email": None,
                "website": website.split("?")[0] if website else None,
                "registered_places": places if places else 6,
                "cma_agency": "Tiney",
                "cma_qa_grading": qa_grading,
                "cma_inspection_date": inspection_date,
            }
    return result


# ---------- Helpers ----------


def _safe_float(val):
    if val is None:
        return None
    try:
        f = float(val)
        return f if f != 0.0 else None
    except (ValueError, TypeError):
        return None


def _strip_address_prefix(val):
    """Strip 'Address:' prefix (with or without space) from Ofsted scrape addresses."""
    if val and val.startswith("Address:"):
        return val[8:].lstrip()
    return val


_ALWAYS_JUNK_DOMAINS = frozenset(
    {
        "google.co.uk",
        "google.com",
        "www.google.co.uk",
        "www.google.com",
        "yahoo.co.uk",
        "yahoo.com",
        "www.yahoo.co.uk",
        "www.yahoo.com",
        "bing.com",
        "www.bing.com",
    }
)

_PLATFORM_DOMAINS = frozenset(
    {
        "facebook.com",
        "www.facebook.com",
        "m.facebook.com",
        "twitter.com",
        "www.twitter.com",
        "x.com",
        "www.x.com",
        "instagram.com",
        "www.instagram.com",
        "youtube.com",
        "www.youtube.com",
        "linkedin.com",
        "www.linkedin.com",
        "nextdoor.co.uk",
        "www.nextdoor.co.uk",
        "nextdoor.com",
        "www.nextdoor.com",
    }
)


def _has_meaningful_path(url: str) -> bool:
    """Return True if the URL has a path beyond the bare homepage."""
    try:
        after_host = url.split("//", 1)[1].split("/", 1)
    except IndexError:
        return False
    if len(after_host) < 2:
        return False
    path = after_host[1].split("?")[0].split("#")[0].strip("/")
    return len(path) > 0


_BARE_DOMAIN_RE = re.compile(
    r"^(?:www\.)?[a-z0-9]([a-z0-9-]*[a-z0-9])?"
    r"(?:\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)*"
    r"\.[a-z]{2,}(?:[:/?\#]|$)",
    re.IGNORECASE,
)


def _clean_website(val):
    """Return website only if it looks like a URL, else None."""
    if not val:
        return None
    val = val.strip().rstrip(".")
    lower = val.lower()
    if not lower.startswith("http://") and not lower.startswith("https://"):
        if _BARE_DOMAIN_RE.match(val):
            val = "https://" + val
        else:
            return None
    # Remove spaces within the URL (e.g. "childbasepartner ship.com")
    val = val.replace(" ", "")
    # Strip trailing text appended after the domain
    # (e.g. "https://example.co.ukOut of School Care")
    # TLD match is case-sensitive so uppercase after TLD triggers truncation
    match = re.match(r"(https?://[^\s]*\.[a-z]{2,})(:\d+)?([/?#][^\s]*)?", val)
    if match:
        val = match.group(1) + (match.group(2) or "") + (match.group(3) or "")
    # Reject bare scheme with no host (e.g. "https://")
    if val in ("http://", "https://"):
        return None
    # Reject generic domains that aren't real provider sites
    try:
        host = val.split("//", 1)[1].split("/", 1)[0].lower()
    except IndexError:
        return None
    if host in _ALWAYS_JUNK_DOMAINS:
        _logger.info("Rejected junk website (search engine): %s", val)
        return None
    if host in _PLATFORM_DOMAINS and not _has_meaningful_path(val):
        _logger.info("Rejected junk website (bare platform homepage): %s", val)
        return None
    return val


_JUNK_PHONE = frozenset(
    {
        "none",
        "-",
        "not available",
        "n/a",
        "contact details withheld",
    }
)


def _normalise_phone(val: str) -> str | None:
    """Strip formatting from a phone number and return digits-only.

    Handles spaces, hyphens, parens, international +44/44 prefix, and
    leading dots. Returns None if the result isn't a valid-length UK number.
    """
    # Strip +44 / 44 international prefix → 0
    val = re.sub(r"^\+?44\s*", "0", val)
    # Remove all non-digit characters
    digits = re.sub(r"[^0-9]", "", val)
    # UK numbers are 10-11 digits starting with 0
    if len(digits) >= 10 and digits.startswith("0"):
        # Take first 11 digits (handles concatenated/duplicated numbers)
        return digits[:11]
    return None


def _clean_phone(val):
    """Return None for placeholder phone values; take first number from multi-values."""
    if not val:
        return None
    val = val.strip()
    if val.lower() in _JUNK_PHONE:
        return None
    # Leading dot (e.g. ".07763356262")
    if val.startswith("."):
        val = val[1:]
    # Multi-number: "X or Y" → take first; "X / Y" → take first; "X;Y" → take first
    if " or " in val:
        val = val.split(" or ")[0].strip()
    if "/" in val:
        val = val.split("/")[0].strip()
    if ";" in val:
        val = val.split(";")[0].strip()
    return _normalise_phone(val)


def _clean_email(val):
    """Return None for junk email values; take first from multi-values."""
    if not val:
        return None
    val = val.strip()
    if not val or val.startswith("www."):
        return None
    # Multi-email: "a@b.com; c@d.com" → take first
    if ";" in val:
        val = val.split(";")[0].strip()
    # Basic sanity: must contain @ and a dot after @
    if "@" not in val or "." not in val.split("@")[-1]:
        return None
    # Strip leading // (seen in data: "//Two.YearOldFunding@...")
    if val.startswith("//"):
        val = val[2:]
    # Fix trailing dot (e.g. "user@domain.org.uk.")
    val = val.rstrip(".")
    # Fix double dots in domain (e.g. "admin@example..org")
    local, domain = val.rsplit("@", 1)
    domain = re.sub(r"\.{2,}", ".", domain)
    # Fix comma instead of dot (e.g. "user@example.org,uk")
    domain = domain.replace(",", ".")
    val = f"{local}@{domain}"
    return val or None


def _first_non_null(candidates, field):
    """Return (value, source_label) for the first candidate with a non-null field."""
    for label, data in candidates:
        val = data.get(field) if isinstance(data, dict) else None
        if val is not None:
            return val, label
    return None, None


def _resolve_location(
    conn,
    provider_id,
    school_urn,
    ofsted_urn,
    postcode,
    lad25cd,
    gias_lookup,
    ofsted_geo_lookup,
    la_geo_lookup,
    la_extract_lookup,
    ofsted_bbox_lookup,
    la_bbox_lookup,
    has_bounding_boxes=True,
):
    """Resolve lat/lon and bbox from the best available source.

    Priority for point coords:
      1. GIAS (for schools)
      2. os.ofsted_places (for Ofsted-linked)
      3. os.la_places (geocoded from OS Places API)
      4. LA extract embedded coords (fallback)

    When no point coords, try bbox:
      5. os.ofsted_places bbox assignment (refined via postcode if coarse)
      6. os.la_places bbox assignment (refined via postcode if coarse)
      7. Direct bbox_fallback() lookup (for providers never geocoded)

    Returns (lat, lon, source, bbox_geo_type, bbox_geo_code).
    lat/lon are None when only bbox is available.
    """
    # 1. GIAS
    if school_urn and school_urn in gias_lookup:
        g = gias_lookup[school_urn]
        if g.get("latitude") is not None and g.get("longitude") is not None:
            return g["latitude"], g["longitude"], "gias", None, None

    # 2. os.ofsted_places
    if ofsted_urn and ofsted_urn in ofsted_geo_lookup:
        lat, lon = ofsted_geo_lookup[ofsted_urn]
        return lat, lon, "os.ofsted_places", None, None

    # 3. os.la_places
    if provider_id in la_geo_lookup:
        lat, lon = la_geo_lookup[provider_id]
        return lat, lon, "os.la_places", None, None

    # 4. LA extract embedded coords
    for source_id, fields in la_extract_lookup.get(provider_id, []):
        lat = fields.get("latitude")
        lon = fields.get("longitude")
        if lat is not None and lon is not None:
            return lat, lon, f"la_scrape:{source_id}", None, None

    # No point coords — try bbox assignments
    # 5. os.ofsted_places bbox (refined via postcode if coarse)
    if ofsted_urn and ofsted_urn in ofsted_bbox_lookup:
        geo_type, geo_code = ofsted_bbox_lookup[ofsted_urn]
        if geo_type in _COARSE_BBOX_TYPES and postcode and has_bounding_boxes:
            bbox = bbox_fallback(conn, postcode, lad25cd)
            if bbox and bbox["bbox_geo_type"] not in _COARSE_BBOX_TYPES:
                return (
                    None,
                    None,
                    f"bbox:{bbox['geocode_status']}",
                    bbox["bbox_geo_type"],
                    bbox["bbox_geo_code"],
                )
        return None, None, "bbox:os.ofsted_places", geo_type, geo_code

    # 6. os.la_places bbox (refined via postcode if coarse)
    if provider_id in la_bbox_lookup:
        geo_type, geo_code = la_bbox_lookup[provider_id]
        if geo_type in _COARSE_BBOX_TYPES and postcode and has_bounding_boxes:
            bbox = bbox_fallback(conn, postcode, lad25cd)
            if bbox and bbox["bbox_geo_type"] not in _COARSE_BBOX_TYPES:
                return (
                    None,
                    None,
                    f"bbox:{bbox['geocode_status']}",
                    bbox["bbox_geo_type"],
                    bbox["bbox_geo_code"],
                )
        return None, None, "bbox:os.la_places", geo_type, geo_code

    # 7. Direct bbox_fallback for providers never geocoded
    if not has_bounding_boxes:
        return None, None, None, None, None
    bbox = bbox_fallback(conn, postcode, lad25cd)
    if bbox:
        return (
            None,
            None,
            f"bbox:{bbox['geocode_status']}",
            bbox["bbox_geo_type"],
            bbox["bbox_geo_code"],
        )

    return None, None, None, None, None


def _resolve_provider_fields(
    conn,
    provider_id,
    school_urn,
    ofsted_urn,
    postcode,
    lad25cd,
    gias_lookup,
    ofsted_lookup,
    ofsted_geo_lookup,
    ofsted_meta_lookup,
    ofsted_compliance_lookup,
    school_inspections_lookup,
    ofsted_places_lookup,
    la_extract_lookup,
    la_geo_lookup,
    ofsted_bbox_lookup,
    la_bbox_lookup,
    tiney_lookup,
    has_bounding_boxes=True,
):
    """Resolve all detail fields for one provider.

    Returns (values_dict, field_sources_dict).
    """
    # Build ordered candidate list for address/contact fields
    candidates = []

    if school_urn and school_urn in gias_lookup:
        candidates.append(("gias", gias_lookup[school_urn]))

    if ofsted_urn and ofsted_urn in ofsted_lookup:
        candidates.append(("ofsted", ofsted_lookup[ofsted_urn]))

    # LA scrape extracts (may have multiple, pre-sorted by richness)
    for source_id, fields in la_extract_lookup.get(provider_id, []):
        candidates.append((f"la_scrape:{source_id}", fields))

    # Tiney childminder data (lower priority than LA/Ofsted)
    if ofsted_urn and ofsted_urn in tiney_lookup:
        candidates.append(("tiney", tiney_lookup[ofsted_urn]))

    # Resolve each address/contact field
    values = {}
    sources = {}

    # Resolve address as atomic block — pick first source with a non-null address_line1
    address_fields = ("address_line1", "address_line2", "city")
    for label, data in candidates:
        if isinstance(data, dict) and data.get("address_line1"):
            for field in address_fields:
                values[field] = data.get(field)
                if data.get(field):
                    sources[field] = label
            break
    else:
        for field in address_fields:
            values[field] = None

    # Resolve contact fields independently
    for field in ["phone", "email", "website"]:
        val, src = _first_non_null(candidates, field)
        values[field] = val
        if src:
            sources[field] = src
    values["fis_url"] = None

    # Resolve lat/lon and bbox separately (geocoded sources preferred)
    lat, lon, coord_src, bbox_geo_type, bbox_geo_code = _resolve_location(
        conn,
        provider_id,
        school_urn,
        ofsted_urn,
        postcode,
        lad25cd,
        gias_lookup,
        ofsted_geo_lookup,
        la_geo_lookup,
        la_extract_lookup,
        ofsted_bbox_lookup,
        la_bbox_lookup,
        has_bounding_boxes=has_bounding_boxes,
    )

    # Tiney providers: force bbox to postcode_district level in draft
    if ofsted_urn and ofsted_urn in tiney_lookup:
        oc = outward_code(postcode)
        if oc:
            bbox_geo_type = "postcode_district"
            bbox_geo_code = oc
            coord_src = "bbox:bbox_postcode_district"
        else:
            bbox_geo_type = None
            bbox_geo_code = None
            coord_src = None

    values["latitude"] = lat
    values["longitude"] = lon
    values["bbox_geo_type"] = bbox_geo_type
    values["bbox_geo_code"] = bbox_geo_code
    if coord_src:
        sources["latitude"] = coord_src
        sources["longitude"] = coord_src
    if bbox_geo_type:
        sources["bbox"] = coord_src

    # Resolve Ofsted metadata — school inspections MI, then EY inspections
    school_insp = school_inspections_lookup.get(school_urn) if school_urn else None
    ofsted_meta = ofsted_meta_lookup.get(ofsted_urn) if ofsted_urn else None

    # Report-card graded properties (from school inspections MI)
    if school_insp and school_insp.get("achievement"):
        values["ofsted_framework"] = "report_card"
        values["ofsted_inspection_date"] = school_insp["inspection_date"]
        values["ofsted_safeguarding_met"] = school_insp["safeguarding_met"]
        values["ofsted_achievement"] = school_insp["achievement"]
        values["ofsted_curriculum_and_teaching"] = school_insp[
            "curriculum_and_teaching"
        ]
        values["ofsted_attendance_and_behaviour"] = school_insp[
            "attendance_and_behaviour"
        ]
        values["ofsted_personal_development_wellbeing"] = school_insp[
            "personal_development_wellbeing"
        ]
        values["ofsted_inclusion"] = school_insp["inclusion"]
        values["ofsted_leadership_and_governance"] = school_insp[
            "leadership_and_governance"
        ]
        values["ofsted_early_years"] = school_insp["early_years"]
        values["ofsted_sixth_form"] = school_insp["sixth_form"]
        # These are EY-register-specific, not applicable to schools
        values["ofsted_behaviour_attitudes_routines"] = None
        values["ofsted_childrens_welfare_wellbeing"] = None
        sources["ofsted_framework"] = "school_inspections"
        sources["ofsted_inspection_date"] = "school_inspections"
    else:
        values["ofsted_safeguarding_met"] = None
        values["ofsted_achievement"] = None
        values["ofsted_curriculum_and_teaching"] = None
        values["ofsted_behaviour_attitudes_routines"] = None
        values["ofsted_childrens_welfare_wellbeing"] = None
        values["ofsted_attendance_and_behaviour"] = None
        values["ofsted_personal_development_wellbeing"] = None
        values["ofsted_inclusion"] = None
        values["ofsted_leadership_and_governance"] = None
        values["ofsted_early_years"] = None
        values["ofsted_sixth_form"] = None

    # Legacy rating: school MI (OEIF) first, then EY inspections, then ungraded
    if school_insp and school_insp.get("oeif_overall"):
        values["ofsted_legacy_rating"] = _map_ofsted_rating(school_insp["oeif_overall"])
        if not values.get("ofsted_inspection_date"):
            values["ofsted_inspection_date"] = school_insp["oeif_date"]
        if not values.get("ofsted_framework"):
            values["ofsted_framework"] = "legacy"
        sources["ofsted_legacy_rating"] = "school_inspections"
        if not sources.get("ofsted_inspection_date"):
            sources["ofsted_inspection_date"] = "school_inspections"
    elif ofsted_meta:
        values["ofsted_legacy_rating"] = ofsted_meta["ofsted_legacy_rating"]
        if not values.get("ofsted_inspection_date"):
            values["ofsted_inspection_date"] = ofsted_meta["ofsted_inspection_date"]
        if not values.get("ofsted_framework"):
            values["ofsted_framework"] = "legacy"
        sources["ofsted_legacy_rating"] = "ofsted"
        if not sources.get("ofsted_inspection_date"):
            sources["ofsted_inspection_date"] = "ofsted"
    elif school_insp and school_insp.get("ungraded_overall_outcome"):
        derived = _derive_rating_from_ungraded(school_insp["ungraded_overall_outcome"])
        if derived:
            values["ofsted_legacy_rating"] = derived
            values["ofsted_inspection_date"] = school_insp["ungraded_date"]
            values["ofsted_framework"] = "ungraded_confirmed"
            sources["ofsted_legacy_rating"] = "school_inspections:ungraded"
            sources["ofsted_inspection_date"] = "school_inspections:ungraded"
        else:
            if "ofsted_legacy_rating" not in values:
                values["ofsted_legacy_rating"] = None
            if "ofsted_inspection_date" not in values:
                values["ofsted_inspection_date"] = None
            if "ofsted_framework" not in values:
                values["ofsted_framework"] = None
    else:
        if "ofsted_legacy_rating" not in values:
            values["ofsted_legacy_rating"] = None
        if "ofsted_inspection_date" not in values:
            values["ofsted_inspection_date"] = None
        if "ofsted_framework" not in values:
            values["ofsted_framework"] = None

    # Legacy sub-grades (from school inspections MI)
    _LEGACY_SUBGRADE_FIELDS = [
        ("oeif_quality_of_education", "ofsted_legacy_quality_of_education"),
        ("oeif_behaviour_and_attitudes", "ofsted_legacy_behaviour_and_attitudes"),
        ("oeif_personal_development", "ofsted_legacy_personal_development"),
        ("oeif_leadership_and_management", "ofsted_legacy_leadership_and_management"),
        ("oeif_early_years", "ofsted_legacy_early_years"),
        ("oeif_sixth_form", "ofsted_legacy_sixth_form"),
    ]
    has_legacy_subgrades = False
    if school_insp:
        for src_key, dest_key in _LEGACY_SUBGRADE_FIELDS:
            mapped = _map_ofsted_subgrade(school_insp.get(src_key))
            values[dest_key] = mapped
            if mapped is not None:
                has_legacy_subgrades = True
                sources[dest_key] = "school_inspections"
    else:
        for _, dest_key in _LEGACY_SUBGRADE_FIELDS:
            values[dest_key] = None

    # Transition schools: have sub-grades but no overall effectiveness
    if has_legacy_subgrades and not values.get("ofsted_legacy_rating"):
        if not values.get("ofsted_framework") or values["ofsted_framework"] == "legacy":
            values["ofsted_framework"] = "legacy_transition"
            sources["ofsted_framework"] = "school_inspections"
        # Use the OEIF inspection date if no date set yet
        if not values.get("ofsted_inspection_date") and school_insp:
            values["ofsted_inspection_date"] = school_insp.get("oeif_date")
            if values["ofsted_inspection_date"]:
                sources["ofsted_inspection_date"] = "school_inspections"
        # Safeguarding from OEIF (Yes/No) if not already set by report-card
        if values.get("ofsted_safeguarding_met") is None and school_insp:
            oeif_safeguarding = school_insp.get("oeif_safeguarding")
            if oeif_safeguarding:
                values["ofsted_safeguarding_met"] = oeif_safeguarding == "Yes"
                sources["ofsted_safeguarding_met"] = "school_inspections"

    # CCR/VCR/OOSC compliance from ofsted.inspections
    compliance = ofsted_compliance_lookup.get(ofsted_urn) if ofsted_urn else None
    if compliance:
        values["ofsted_ccr_met"] = compliance["ccr_met"]
        values["ofsted_vcr_met"] = compliance["vcr_met"]
        values["ofsted_oosc_met"] = compliance["oosc_met"]
        if compliance["ccr_met"] is not None:
            sources["ofsted_ccr_met"] = "ofsted"
        if compliance["vcr_met"] is not None:
            sources["ofsted_vcr_met"] = "ofsted"
        if compliance["oosc_met"] is not None:
            sources["ofsted_oosc_met"] = "ofsted"
    else:
        values["ofsted_ccr_met"] = None
        values["ofsted_vcr_met"] = None
        values["ofsted_oosc_met"] = None

    # Resolve registered_places: Ofsted first, then LA extract, then Tiney
    places = None
    places_src = None
    if ofsted_urn and ofsted_urn in ofsted_places_lookup:
        places = ofsted_places_lookup[ofsted_urn]
        places_src = "ofsted"
    if places is None:
        for source_id, fields in la_extract_lookup.get(provider_id, []):
            la_places = fields.get("registered_places")
            if la_places is not None:
                places = la_places
                places_src = f"la_scrape:{source_id}"
                break
    if places is None and ofsted_urn and ofsted_urn in tiney_lookup:
        tiney_places = tiney_lookup[ofsted_urn].get("registered_places")
        if tiney_places is not None:
            places = tiney_places
            places_src = "tiney"
    values["registered_places"] = places
    if places_src:
        sources["registered_places"] = places_src

    # Staff and facilities — no automated source yet, placeholder for future
    values["staff_graduate_percentage"] = None
    values["staff_turnover_percentage"] = None
    values["has_garden"] = None
    values["has_kitchen"] = None

    # CMA inspection data (from Tiney or future CMA sources)
    if ofsted_urn and ofsted_urn in tiney_lookup:
        tiney = tiney_lookup[ofsted_urn]
        values["cma_agency"] = tiney.get("cma_agency")
        values["cma_qa_grading"] = tiney.get("cma_qa_grading")
        values["cma_inspection_date"] = tiney.get("cma_inspection_date")
    else:
        values["cma_agency"] = None
        values["cma_qa_grading"] = None
        values["cma_inspection_date"] = None

    return values, sources


def _flush_updates(conn, batch):
    if not batch:
        return
    with conn.cursor() as cur:
        for row in batch:
            cur.execute(UPDATE_SQL, row)
    conn.commit()


# ---------- Dagster asset ----------


@asset(
    group_name="draft",
    deps=[
        "providers",
        "ofsted_consented_addresses",
        "ofsted_places_geocode",
        "la_places_geocode",
    ],
    automation_condition=PIPELINE_CONDITION,
)
def provider_details(
    context: AssetExecutionContext, bsil_postgres: BsilPostgresResource
):
    """Enrich draft.providers with address, coordinates, phone, email, website, fis_url.

    Adds columns via ALTER TABLE and resolves values from GIAS, Ofsted,
    OS Places geocoding, and LA scrape extracts with priority ordering.
    """
    with bsil_postgres.get_connection() as conn:
        # Phase 1: Add columns
        context.log.info("Phase 1: ALTER TABLE — adding detail columns")
        with conn.cursor() as cur:
            cur.execute(ALTER_SQL)
            conn.commit()

        # Phase 2: Load lookup dicts
        context.log.info("Phase 2: loading source data")

        gias_lookup = _load_gias(conn)
        context.log.info(f"  GIAS: {len(gias_lookup)} schools")

        ofsted_lookup = _load_ofsted(conn)
        context.log.info(f"  Ofsted: {len(ofsted_lookup)} providers")

        ofsted_geo_lookup = _load_ofsted_geo(conn)
        context.log.info(f"  Ofsted geo: {len(ofsted_geo_lookup)} geocoded")

        ofsted_meta_lookup = _load_ofsted_meta(conn)
        context.log.info(f"  Ofsted meta: {len(ofsted_meta_lookup)} with ratings")

        ofsted_compliance_lookup = _load_ofsted_compliance(conn)
        context.log.info(
            f"  Ofsted compliance: {len(ofsted_compliance_lookup)} with CCR/VCR/OOSC data"
        )

        school_inspections_lookup = _load_school_inspections(conn)
        context.log.info(
            f"  School inspections: {len(school_inspections_lookup)} schools"
        )

        ofsted_places_lookup = _load_ofsted_places(conn)
        context.log.info(f"  Ofsted places: {len(ofsted_places_lookup)} with capacity")

        la_extract_lookup = _load_la_extracts(conn)
        context.log.info(f"  LA extracts: {len(la_extract_lookup)} providers")

        la_geo_lookup = _load_la_geo(conn)
        context.log.info(f"  LA geo: {len(la_geo_lookup)} geocoded")

        ofsted_bbox_lookup = _load_ofsted_bbox(conn)
        context.log.info(f"  Ofsted bbox: {len(ofsted_bbox_lookup)} with bbox")

        la_bbox_lookup = _load_la_bbox(conn)
        context.log.info(f"  LA bbox: {len(la_bbox_lookup)} with bbox")

        tiney_lookup = _load_tiney(conn)
        context.log.info(f"  Tiney: {len(tiney_lookup)} childminders")

        # Check if os.bounding_boxes exists for direct fallback
        with conn.cursor() as cur:
            cur.execute(
                "SELECT EXISTS ("
                "  SELECT 1 FROM information_schema.tables"
                "  WHERE table_schema = 'os' AND table_name = 'bounding_boxes'"
                ")"
            )
            has_bounding_boxes = cur.fetchone()[0]

        # Phase 3: Resolve and update
        context.log.info("Phase 3: resolving fields and updating providers")

        # Stream all providers
        providers = []
        with conn.cursor("provider_detail_cursor", withhold=True) as cur:
            cur.execute(LOAD_PROVIDERS_SQL)
            for provider_id, school_urn, ofsted_urn, postcode, lad25cd, metadata in cur:
                providers.append(
                    (provider_id, school_urn, ofsted_urn, postcode, lad25cd, metadata)
                )

        total = len(providers)
        context.log.info(f"  Processing {total} providers")

        # Stats tracking
        field_counts = {f: 0 for f in DETAIL_FIELDS}
        source_counts = defaultdict(lambda: defaultdict(int))
        enriched = 0

        batch = []
        for (
            provider_id,
            school_urn,
            ofsted_urn,
            postcode,
            lad25cd,
            metadata,
        ) in providers:
            values, field_sources = _resolve_provider_fields(
                conn,
                provider_id,
                school_urn,
                ofsted_urn,
                postcode,
                lad25cd,
                gias_lookup,
                ofsted_lookup,
                ofsted_geo_lookup,
                ofsted_meta_lookup,
                ofsted_compliance_lookup,
                school_inspections_lookup,
                ofsted_places_lookup,
                la_extract_lookup,
                la_geo_lookup,
                ofsted_bbox_lookup,
                la_bbox_lookup,
                tiney_lookup,
                has_bounding_boxes=has_bounding_boxes,
            )

            # Track stats
            any_enriched = False
            for field in DETAIL_FIELDS:
                if values.get(field) is not None:
                    field_counts[field] += 1
                    any_enriched = True
            if any_enriched:
                enriched += 1

            for field, src in field_sources.items():
                # Normalise la_scrape:xxx → la_scrape for stats
                src_key = "la_scrape" if src.startswith("la_scrape:") else src
                source_counts[field][src_key] += 1

            # Merge field_sources into existing metadata
            if isinstance(metadata, str):
                metadata = json.loads(metadata)
            metadata = metadata or {}
            existing_fs = metadata.get("field_sources", {})
            existing_fs.update(field_sources)
            if existing_fs:
                metadata["field_sources"] = existing_fs

            batch.append(
                {
                    "provider_id": provider_id,
                    "address_line1": values["address_line1"],
                    "address_line2": values["address_line2"],
                    "city": values["city"],
                    "latitude": values["latitude"],
                    "longitude": values["longitude"],
                    "phone": values["phone"],
                    "email": values["email"],
                    "website": values["website"],
                    "fis_url": values["fis_url"],
                    "ofsted_legacy_rating": values["ofsted_legacy_rating"],
                    "ofsted_inspection_date": values["ofsted_inspection_date"],
                    "ofsted_framework": values["ofsted_framework"],
                    "ofsted_safeguarding_met": values["ofsted_safeguarding_met"],
                    "ofsted_achievement": values["ofsted_achievement"],
                    "ofsted_curriculum_and_teaching": values[
                        "ofsted_curriculum_and_teaching"
                    ],
                    "ofsted_behaviour_attitudes_routines": values[
                        "ofsted_behaviour_attitudes_routines"
                    ],
                    "ofsted_childrens_welfare_wellbeing": values[
                        "ofsted_childrens_welfare_wellbeing"
                    ],
                    "ofsted_attendance_and_behaviour": values[
                        "ofsted_attendance_and_behaviour"
                    ],
                    "ofsted_personal_development_wellbeing": values[
                        "ofsted_personal_development_wellbeing"
                    ],
                    "ofsted_inclusion": values["ofsted_inclusion"],
                    "ofsted_leadership_and_governance": values[
                        "ofsted_leadership_and_governance"
                    ],
                    "ofsted_early_years": values["ofsted_early_years"],
                    "ofsted_sixth_form": values["ofsted_sixth_form"],
                    "ofsted_legacy_quality_of_education": values[
                        "ofsted_legacy_quality_of_education"
                    ],
                    "ofsted_legacy_behaviour_and_attitudes": values[
                        "ofsted_legacy_behaviour_and_attitudes"
                    ],
                    "ofsted_legacy_personal_development": values[
                        "ofsted_legacy_personal_development"
                    ],
                    "ofsted_legacy_leadership_and_management": values[
                        "ofsted_legacy_leadership_and_management"
                    ],
                    "ofsted_legacy_early_years": values["ofsted_legacy_early_years"],
                    "ofsted_legacy_sixth_form": values["ofsted_legacy_sixth_form"],
                    "ofsted_ccr_met": values["ofsted_ccr_met"],
                    "ofsted_vcr_met": values["ofsted_vcr_met"],
                    "ofsted_oosc_met": values["ofsted_oosc_met"],
                    "registered_places": values["registered_places"],
                    "staff_graduate_percentage": values["staff_graduate_percentage"],
                    "staff_turnover_percentage": values["staff_turnover_percentage"],
                    "has_garden": values["has_garden"],
                    "has_kitchen": values["has_kitchen"],
                    "cma_agency": values["cma_agency"],
                    "cma_qa_grading": values["cma_qa_grading"],
                    "cma_inspection_date": values["cma_inspection_date"],
                    "bbox_geo_type": values["bbox_geo_type"],
                    "bbox_geo_code": values["bbox_geo_code"],
                    "metadata": json.dumps(metadata),
                }
            )

            if len(batch) >= BATCH_SIZE:
                _flush_updates(conn, batch)
                batch.clear()

        _flush_updates(conn, batch)

        # Phase 4: Log stats
        context.log.info(
            f"Phase 4: enrichment stats ({enriched}/{total} providers enriched)"
        )
        for field in DETAIL_FIELDS:
            pct = (field_counts[field] / total * 100) if total else 0
            context.log.info(f"  {field}: {field_counts[field]}/{total} ({pct:.1f}%)")

        context.log.info("Source breakdown per field:")
        for field in DETAIL_FIELDS:
            if source_counts[field]:
                parts = ", ".join(
                    f"{src}={cnt}"
                    for src, cnt in sorted(
                        source_counts[field].items(), key=lambda x: -x[1]
                    )
                )
                context.log.info(f"  {field}: {parts}")

        # Phase 5: Promote referenced bounding boxes into draft
        bbox_count = 0
        if has_bounding_boxes and field_counts["bbox_geo_type"] > 0:
            context.log.info("Phase 5: promoting referenced bounding boxes to draft")
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS draft.bounding_boxes (
                        geo_type TEXT NOT NULL,
                        geo_code TEXT NOT NULL,
                        geo_name TEXT,
                        bbox_north DOUBLE PRECISION NOT NULL,
                        bbox_south DOUBLE PRECISION NOT NULL,
                        bbox_east DOUBLE PRECISION NOT NULL,
                        bbox_west DOUBLE PRECISION NOT NULL,
                        PRIMARY KEY (geo_type, geo_code)
                    )
                    """
                )
                cur.execute("DELETE FROM draft.bounding_boxes")
                cur.execute(
                    """
                    INSERT INTO draft.bounding_boxes
                        (geo_type, geo_code, geo_name, bbox_north, bbox_south, bbox_east, bbox_west)
                    SELECT DISTINCT bb.geo_type, bb.geo_code, bb.geo_name,
                           bb.bbox_north, bb.bbox_south, bb.bbox_east, bb.bbox_west
                    FROM draft.providers p
                    JOIN os.bounding_boxes bb
                        ON bb.geo_type = p.bbox_geo_type AND bb.geo_code = p.bbox_geo_code
                    WHERE p.bbox_geo_type IS NOT NULL
                    """
                )
                bbox_count = cur.rowcount
                conn.commit()
            context.log.info(f"  Promoted {bbox_count} bounding boxes to draft")

        # Phase 6: Compute bigint_id for each provider
        context.log.info("Phase 6: computing bigint_id (blake2b) for each provider")
        with conn.cursor() as cur:
            cur.execute(
                "ALTER TABLE draft.providers ADD COLUMN IF NOT EXISTS bigint_id BIGINT"
            )
            conn.commit()

        id_map = {}
        with conn.cursor("bigint_cursor", withhold=True) as cur:
            cur.execute("SELECT provider_id FROM draft.providers")
            for (provider_id,) in cur:
                digest = hashlib.blake2b(provider_id.encode(), digest_size=8).digest()
                bigint_id = int.from_bytes(digest, "big") & 0x7FFFFFFFFFFFFFFF
                id_map[provider_id] = bigint_id

        # Check for collisions
        seen = {}
        for pid, bid in id_map.items():
            if bid in seen:
                raise RuntimeError(
                    f"blake2b collision: {pid!r} and {seen[bid]!r} both map to {bid}"
                )
            seen[bid] = pid

        with conn.cursor() as cur:
            for provider_id, bigint_id in id_map.items():
                cur.execute(
                    "UPDATE draft.providers SET bigint_id = %s WHERE provider_id = %s",
                    (bigint_id, provider_id),
                )
            conn.commit()

        context.log.info(f"  Assigned {len(id_map)} bigint IDs (0 collisions)")

    return {
        "total_providers": MetadataValue.int(total),
        "enriched_providers": MetadataValue.int(enriched),
        "has_address": MetadataValue.int(field_counts["address_line1"]),
        "has_coords": MetadataValue.int(field_counts["latitude"]),
        "has_phone": MetadataValue.int(field_counts["phone"]),
        "has_email": MetadataValue.int(field_counts["email"]),
        "has_website": MetadataValue.int(field_counts["website"]),
        "has_fis_url": MetadataValue.int(field_counts["fis_url"]),
        "has_ofsted_legacy_rating": MetadataValue.int(
            field_counts["ofsted_legacy_rating"]
        ),
        "has_legacy_subgrades": MetadataValue.int(
            field_counts["ofsted_legacy_quality_of_education"]
        ),
        "has_ccr_met": MetadataValue.int(field_counts["ofsted_ccr_met"]),
        "has_vcr_met": MetadataValue.int(field_counts["ofsted_vcr_met"]),
        "has_oosc_met": MetadataValue.int(field_counts["ofsted_oosc_met"]),
        "has_registered_places": MetadataValue.int(field_counts["registered_places"]),
        "has_bbox": MetadataValue.int(field_counts["bbox_geo_type"]),
        "bbox_promoted": MetadataValue.int(bbox_count),
        "bigint_ids_assigned": MetadataValue.int(len(id_map)),
    }
