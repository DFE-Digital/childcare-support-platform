"""Load provider fixture JSONs into the draft schema.

Reads p*.json files from the placeholder-providers directory and inserts them
into draft.providers, draft.care_types, draft.fee_rates, draft.additional_charges,
draft.waiting_list_entries, and draft.care_type_notes — the same tables the real
pipeline builds from scraped data.

This lets the downstream publish_providers → export pipeline run identically
for both placeholder and real data.
"""

import json
import re
from pathlib import Path

from dagster import asset, AssetExecutionContext, MetadataValue

from bsil_pipeline.resources.postgres import BsilPostgresResource

FIXTURES_DIR = Path("/opt/dagster/app/data/placeholder-providers")

# Top-level fee keys that indicate a flat rate (not age-banded)
FLAT_RATE_KEYS = {"perSession", "perHour", "perDay"}

# Known age band keys in the fee structure
AGE_BAND_KEYS = {"under2", "age2", "age3to4", "age2plus", "age5plus"}


def _parse_provider_id(raw_id: str) -> int:
    if not raw_id.startswith("p"):
        raise ValueError(f"Expected provider ID starting with 'p', got: {raw_id!r}")
    return int(raw_id[1:])


def _normalize_phone(raw: str | None) -> str | None:
    if raw is None:
        return None
    digits = re.sub(r"[^0-9+]", "", raw)
    if digits.startswith("+44"):
        digits = "0" + digits[3:]
    elif digits.startswith("44") and len(digits) > 10:
        digits = "0" + digits[2:]
    return digits


def _parse_fee_rows(fees: dict) -> list[dict]:
    """Parse the fees dict into a list of fee_rates row dicts.

    Fees come in two shapes:
    1. Flat-rate: { "perSession": 6.5 } or { "perDay": 22 }
       -> single row with age_band='all'
    2. Age-banded: { "under2": { "morningSession": 55, ... }, "age2": {...} }
       -> one row per age band
    """
    rows = []

    # Check if any top-level keys are flat rates
    flat_keys_present = FLAT_RATE_KEYS & fees.keys()
    if flat_keys_present:
        row = {"age_band": "all"}
        row["per_session"] = fees.get("perSession")
        row["per_hour"] = fees.get("perHour")
        row["per_day"] = fees.get("perDay")
        row["morning_session"] = None
        row["afternoon_session"] = None
        row["full_day"] = None
        rows.append(row)
        return rows

    # Age-banded fees
    for band_key, band_fees in fees.items():
        if band_key not in AGE_BAND_KEYS:
            continue
        if not isinstance(band_fees, dict):
            continue
        row = {"age_band": band_key}
        row["morning_session"] = band_fees.get("morningSession")
        row["afternoon_session"] = band_fees.get("afternoonSession")
        row["full_day"] = band_fees.get("fullDay")
        row["per_session"] = band_fees.get("perSession")
        row["per_hour"] = band_fees.get("perHour")
        row["per_day"] = band_fees.get("perDay")
        rows.append(row)

    return rows


# ---------- Draft schema DDL ----------

_DROP_CHILD_TABLES = """
DROP TABLE IF EXISTS draft.opening_hours;
DROP TABLE IF EXISTS draft.care_type_notes;
DROP TABLE IF EXISTS draft.waiting_list_entries;
DROP TABLE IF EXISTS draft.additional_charges;
DROP TABLE IF EXISTS draft.fee_rates;
DROP TABLE IF EXISTS draft.care_types CASCADE;
DROP TABLE IF EXISTS draft.providers CASCADE;
"""

_CREATE_PROVIDERS = """
CREATE TABLE draft.providers (
    provider_id     TEXT PRIMARY KEY,
    provider_name   TEXT,
    postcode        TEXT,
    lad25cd         TEXT,
    ofsted_urn      TEXT,
    school_urn      TEXT,
    institution_type TEXT,
    care_types      TEXT[],
    excluded        BOOLEAN NOT NULL DEFAULT false,
    metadata        JSONB NOT NULL DEFAULT '{}',
    address_line1   TEXT,
    address_line2   TEXT,
    city            TEXT,
    latitude        DOUBLE PRECISION,
    longitude       DOUBLE PRECISION,
    phone           TEXT,
    email           TEXT,
    website         TEXT,
    fis_url         TEXT,
    ofsted_legacy_rating TEXT,
    ofsted_inspection_date DATE,
    ofsted_framework TEXT,
    ofsted_safeguarding_met BOOLEAN,
    ofsted_achievement TEXT,
    ofsted_curriculum_and_teaching TEXT,
    ofsted_behaviour_attitudes_routines TEXT,
    ofsted_childrens_welfare_wellbeing TEXT,
    ofsted_attendance_and_behaviour TEXT,
    ofsted_personal_development_wellbeing TEXT,
    ofsted_inclusion TEXT,
    ofsted_leadership_and_governance TEXT,
    ofsted_early_years TEXT,
    ofsted_sixth_form TEXT,
    ofsted_legacy_quality_of_education TEXT,
    ofsted_legacy_behaviour_and_attitudes TEXT,
    ofsted_legacy_personal_development TEXT,
    ofsted_legacy_leadership_and_management TEXT,
    ofsted_legacy_early_years TEXT,
    ofsted_legacy_sixth_form TEXT,
    ofsted_ccr_met BOOLEAN,
    ofsted_vcr_met BOOLEAN,
    ofsted_oosc_met BOOLEAN,
    registered_places INTEGER,
    staff_graduate_percentage NUMERIC(5,2),
    staff_turnover_percentage NUMERIC(5,2),
    has_garden BOOLEAN,
    has_kitchen BOOLEAN,
    bbox_geo_type TEXT,
    bbox_geo_code TEXT,
    bigint_id BIGINT
)
"""

_CREATE_CARE_TYPES = """
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
    eligible_attendees_only BOOLEAN NOT NULL DEFAULT false,
    eligible_institutions   TEXT[],
    eligible_other          TEXT[],
    funded_hours_accepted   BOOLEAN,
    min_commitment_amount   INTEGER,
    min_commitment_unit     TEXT,
    min_commitment_duration TEXT,
    no_minimum_commitment   BOOLEAN NOT NULL DEFAULT false,
    metadata                JSONB NOT NULL DEFAULT '{}'
)
"""

_CREATE_FEE_RATES = """
CREATE TABLE draft.fee_rates (
    id              BIGSERIAL PRIMARY KEY,
    care_type_id    BIGINT NOT NULL REFERENCES draft.care_types(id) ON DELETE CASCADE,
    age_band        TEXT NOT NULL,
    morning_session NUMERIC(8,2),
    afternoon_session NUMERIC(8,2),
    full_day        NUMERIC(8,2),
    per_session     NUMERIC(8,2),
    per_hour        NUMERIC(8,2),
    per_day         NUMERIC(8,2),
    metadata        JSONB NOT NULL DEFAULT '{}'
)
"""

_CREATE_ADDITIONAL_CHARGES = """
CREATE TABLE draft.additional_charges (
    id           BIGSERIAL PRIMARY KEY,
    care_type_id BIGINT NOT NULL REFERENCES draft.care_types(id) ON DELETE CASCADE,
    item         TEXT NOT NULL,
    cost         NUMERIC(8,2) NOT NULL,
    unit         TEXT NOT NULL,
    description  TEXT NOT NULL
)
"""

_CREATE_WAITING_LIST_ENTRIES = """
CREATE TABLE draft.waiting_list_entries (
    id           BIGSERIAL PRIMARY KEY,
    care_type_id BIGINT NOT NULL REFERENCES draft.care_types(id) ON DELETE CASCADE,
    age_band     TEXT NOT NULL,
    weeks        INTEGER,
    months       INTEGER
)
"""

_CREATE_CARE_TYPE_NOTES = """
CREATE TABLE draft.care_type_notes (
    id           BIGSERIAL PRIMARY KEY,
    care_type_id BIGINT NOT NULL REFERENCES draft.care_types(id) ON DELETE CASCADE,
    note_type    TEXT NOT NULL,
    description  TEXT NOT NULL
)
"""

_CREATE_OPENING_HOURS = """
CREATE TABLE draft.opening_hours (
    id            BIGSERIAL PRIMARY KEY,
    care_type_id  BIGINT NOT NULL REFERENCES draft.care_types(id) ON DELETE CASCADE,
    monday        BOOLEAN NOT NULL DEFAULT false,
    tuesday       BOOLEAN NOT NULL DEFAULT false,
    wednesday     BOOLEAN NOT NULL DEFAULT false,
    thursday      BOOLEAN NOT NULL DEFAULT false,
    friday        BOOLEAN NOT NULL DEFAULT false,
    saturday      BOOLEAN NOT NULL DEFAULT false,
    sunday        BOOLEAN NOT NULL DEFAULT false,
    open          TIME NOT NULL,
    close         TIME NOT NULL
)
"""

_DAY_MAP = {
    "1": "monday",
    "2": "tuesday",
    "3": "wednesday",
    "4": "thursday",
    "5": "friday",
    "6": "saturday",
    "7": "sunday",
}


def create_draft_tables(cur):
    """Create the draft schema and all fixture tables."""
    cur.execute("CREATE SCHEMA IF NOT EXISTS draft")
    cur.execute(_DROP_CHILD_TABLES)
    cur.execute(_CREATE_PROVIDERS)
    cur.execute(_CREATE_CARE_TYPES)
    cur.execute(_CREATE_FEE_RATES)
    cur.execute(_CREATE_ADDITIONAL_CHARGES)
    cur.execute(_CREATE_WAITING_LIST_ENTRIES)
    cur.execute(_CREATE_CARE_TYPE_NOTES)
    cur.execute(_CREATE_OPENING_HOURS)


def load_fixture_provider(cur, data: dict, counts: dict) -> None:
    """Insert a single provider and all its related data into the draft schema."""
    raw_id = data["id"]
    provider_id = f"fixture:{raw_id}"
    bigint_id = _parse_provider_id(raw_id)

    address = data.get("address", {})
    ofsted = data.get("ofsted", {})
    staff = data.get("staff", {})
    facilities = data.get("facilities", {})
    bbox = data.get("boundingBox", {})
    legacy_sub = ofsted.get("legacySubGrades") or {}

    care_type_strs = [ct["type"] for ct in data.get("careTypes", [])]

    cur.execute(
        """
        INSERT INTO draft.providers (
            provider_id, provider_name, postcode, lad25cd,
            institution_type, care_types, excluded, bigint_id,
            address_line1, address_line2, city, latitude, longitude,
            phone, email, website, fis_url,
            ofsted_legacy_rating, ofsted_inspection_date,
            ofsted_framework, ofsted_safeguarding_met,
            ofsted_achievement, ofsted_curriculum_and_teaching,
            ofsted_behaviour_attitudes_routines, ofsted_childrens_welfare_wellbeing,
            ofsted_attendance_and_behaviour, ofsted_personal_development_wellbeing,
            ofsted_inclusion, ofsted_leadership_and_governance,
            ofsted_early_years, ofsted_sixth_form,
            ofsted_legacy_quality_of_education, ofsted_legacy_behaviour_and_attitudes,
            ofsted_legacy_personal_development, ofsted_legacy_leadership_and_management,
            ofsted_legacy_early_years, ofsted_legacy_sixth_form,
            ofsted_ccr_met, ofsted_vcr_met, ofsted_oosc_met,
            registered_places,
            staff_graduate_percentage, staff_turnover_percentage,
            has_garden, has_kitchen,
            bbox_geo_type, bbox_geo_code
        ) VALUES (
            %(provider_id)s, %(name)s, %(postcode)s, %(lad25cd)s,
            %(institution_type)s, %(care_types)s, false, %(bigint_id)s,
            %(line1)s, %(line2)s, %(city)s, %(latitude)s, %(longitude)s,
            %(phone)s, %(email)s, %(website)s, %(fis_url)s,
            %(ofsted_legacy_rating)s, %(inspection_date)s,
            %(ofsted_framework)s, %(ofsted_safeguarding_met)s,
            %(ofsted_achievement)s, %(ofsted_curriculum_and_teaching)s,
            %(ofsted_behaviour_attitudes_routines)s, %(ofsted_childrens_welfare_wellbeing)s,
            %(ofsted_attendance_and_behaviour)s, %(ofsted_personal_development_wellbeing)s,
            %(ofsted_inclusion)s, %(ofsted_leadership_and_governance)s,
            %(ofsted_early_years)s, %(ofsted_sixth_form)s,
            %(ofsted_legacy_quality_of_education)s, %(ofsted_legacy_behaviour_and_attitudes)s,
            %(ofsted_legacy_personal_development)s, %(ofsted_legacy_leadership_and_management)s,
            %(ofsted_legacy_early_years)s, %(ofsted_legacy_sixth_form)s,
            %(ofsted_ccr_met)s, %(ofsted_vcr_met)s, %(ofsted_oosc_met)s,
            %(registered_places)s,
            %(graduate_pct)s, %(turnover_pct)s,
            %(has_garden)s, %(has_kitchen)s,
            %(bbox_geo_type)s, %(bbox_geo_code)s
        )
        """,
        {
            "provider_id": provider_id,
            "name": data["name"],
            "postcode": address.get("postcode"),
            "lad25cd": data.get("lad25cd"),
            "institution_type": data.get("institutionType"),
            "care_types": care_type_strs or None,
            "bigint_id": bigint_id,
            "line1": address.get("line1"),
            "line2": address.get("line2"),
            "city": address.get("city"),
            "latitude": data.get("latitude"),
            "longitude": data.get("longitude"),
            "phone": _normalize_phone(data.get("phone")),
            "email": data.get("email"),
            "website": data.get("website"),
            "fis_url": data.get("fisUrl"),
            "ofsted_legacy_rating": ofsted.get("legacyRating") or ofsted.get("rating"),
            "inspection_date": ofsted.get("inspectionDate"),
            "ofsted_framework": ofsted.get("framework"),
            "ofsted_safeguarding_met": ofsted.get("safeguardingMet"),
            "ofsted_achievement": ofsted.get("achievement"),
            "ofsted_curriculum_and_teaching": ofsted.get("curriculumAndTeaching"),
            "ofsted_behaviour_attitudes_routines": ofsted.get(
                "behaviourAttitudesRoutines"
            ),
            "ofsted_childrens_welfare_wellbeing": ofsted.get(
                "childrensWelfareWellbeing"
            ),
            "ofsted_attendance_and_behaviour": ofsted.get("attendanceAndBehaviour"),
            "ofsted_personal_development_wellbeing": ofsted.get(
                "personalDevelopmentWellbeing"
            ),
            "ofsted_inclusion": ofsted.get("inclusion"),
            "ofsted_leadership_and_governance": ofsted.get("leadershipAndGovernance"),
            "ofsted_early_years": ofsted.get("earlyYears"),
            "ofsted_sixth_form": ofsted.get("sixthForm"),
            "ofsted_legacy_quality_of_education": legacy_sub.get("qualityOfEducation"),
            "ofsted_legacy_behaviour_and_attitudes": legacy_sub.get(
                "behaviourAndAttitudes"
            ),
            "ofsted_legacy_personal_development": legacy_sub.get("personalDevelopment"),
            "ofsted_legacy_leadership_and_management": legacy_sub.get(
                "leadershipAndManagement"
            ),
            "ofsted_legacy_early_years": legacy_sub.get("earlyYears"),
            "ofsted_legacy_sixth_form": legacy_sub.get("sixthForm"),
            "ofsted_ccr_met": ofsted.get("ccrMet"),
            "ofsted_vcr_met": ofsted.get("vcrMet"),
            "ofsted_oosc_met": ofsted.get("ooscMet"),
            "registered_places": data.get("registeredPlaces"),
            "graduate_pct": staff.get("graduatePercentage"),
            "turnover_pct": staff.get("turnoverPercentage"),
            "has_garden": facilities.get("hasGarden"),
            "has_kitchen": facilities.get("hasKitchen"),
            "bbox_geo_type": bbox.get("geoType") or data.get("bboxGeoType"),
            "bbox_geo_code": bbox.get("geoCode") or data.get("bboxGeoCode"),
        },
    )
    counts["providers"] += 1

    for ct in data.get("careTypes", []):
        _load_care_type(cur, provider_id, ct, counts)


def _load_care_type(cur, provider_id: str, ct: dict, counts: dict) -> None:
    """Insert a care type and its child rows into draft tables."""
    session_hours = ct.get("sessionHours", {})
    age_range = ct.get("eligibleAgeRange", {})

    min_commit_raw = ct.get("minimumCommitment")
    no_minimum_commitment = min_commit_raw is False
    if not min_commit_raw or min_commit_raw is False:
        mc_amount = None
        mc_unit = None
        mc_duration = None
    else:
        mc_amount = min_commit_raw.get("amount")
        mc_unit = min_commit_raw.get("unitPerWeek")
        mc_duration = min_commit_raw.get("duration")

    cur.execute(
        """
        INSERT INTO draft.care_types (
            provider_id, care_type,
            operating_weeks_per_year,
            session_hours_morning, session_hours_afternoon, session_hours_full_day,
            eligible_min_months, eligible_min_years, eligible_max_years,
            eligible_attendees_only, eligible_institutions, eligible_other,
            funded_hours_accepted,
            min_commitment_amount, min_commitment_unit, min_commitment_duration,
            no_minimum_commitment
        ) VALUES (
            %(provider_id)s, %(care_type)s,
            %(weeks_per_year)s,
            %(sh_morning)s, %(sh_afternoon)s, %(sh_full_day)s,
            %(min_months)s, %(min_years)s, %(max_years)s,
            %(attendees_only)s, %(institutions)s, %(other)s,
            %(funded)s,
            %(mc_amount)s, %(mc_unit)s, %(mc_duration)s,
            %(no_minimum_commitment)s
        )
        RETURNING id
        """,
        {
            "provider_id": provider_id,
            "care_type": ct["type"],
            "weeks_per_year": ct.get("operatingWeeksPerYear"),
            "sh_morning": session_hours.get("morning"),
            "sh_afternoon": session_hours.get("afternoon"),
            "sh_full_day": session_hours.get("fullDay"),
            "min_months": age_range.get("minMonths"),
            "min_years": age_range.get("minYears"),
            "max_years": age_range.get("maxYears"),
            "attendees_only": ct.get("eligibleAttendeesOnly", False),
            "institutions": ct.get("eligibleInstitutions", []) or [],
            "other": ct.get("eligibleOther", []) or [],
            "funded": ct.get("fundedHoursAccepted"),
            "mc_amount": mc_amount,
            "mc_unit": mc_unit,
            "mc_duration": mc_duration,
            "no_minimum_commitment": no_minimum_commitment,
        },
    )
    care_type_id = cur.fetchone()[0]
    counts["care_types"] += 1

    # Opening hours
    for oh in ct.get("openingHours", []):
        day_bools = {d: False for d in _DAY_MAP.values()}
        for ch in oh["days"]:
            day_bools[_DAY_MAP[ch]] = True
        cur.execute(
            """
            INSERT INTO draft.opening_hours (
                care_type_id, monday, tuesday, wednesday, thursday, friday,
                saturday, sunday, open, close
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                care_type_id,
                day_bools["monday"],
                day_bools["tuesday"],
                day_bools["wednesday"],
                day_bools["thursday"],
                day_bools["friday"],
                day_bools["saturday"],
                day_bools["sunday"],
                oh["open"],
                oh["close"],
            ),
        )
        counts["opening_hours"] = counts.get("opening_hours", 0) + 1

    # Fee rates
    fees = ct.get("fees", {})
    for fee_row in _parse_fee_rows(fees):
        cur.execute(
            """
            INSERT INTO draft.fee_rates (
                care_type_id, age_band,
                morning_session, afternoon_session, full_day,
                per_session, per_hour, per_day
            ) VALUES (
                %(care_type_id)s, %(age_band)s,
                %(morning_session)s, %(afternoon_session)s, %(full_day)s,
                %(per_session)s, %(per_hour)s, %(per_day)s
            )
            """,
            {"care_type_id": care_type_id, **fee_row},
        )
        counts["fee_rates"] += 1

    # Additional charges
    for charge in ct.get("additionalCharges", []):
        cur.execute(
            """
            INSERT INTO draft.additional_charges (care_type_id, item, cost, unit, description)
            VALUES (%(care_type_id)s, %(item)s, %(cost)s, %(unit)s, %(description)s)
            """,
            {
                "care_type_id": care_type_id,
                "item": charge["item"],
                "cost": charge["cost"],
                "unit": charge["unit"],
                "description": charge["description"],
            },
        )
        counts["additional_charges"] += 1

    # Waiting list entries
    for band_key, wl_data in ct.get("waitingList", {}).items():
        cur.execute(
            """
            INSERT INTO draft.waiting_list_entries (care_type_id, age_band, weeks, months)
            VALUES (%(care_type_id)s, %(age_band)s, %(weeks)s, %(months)s)
            """,
            {
                "care_type_id": care_type_id,
                "age_band": band_key,
                "weeks": wl_data.get("weeks"),
                "months": wl_data.get("months"),
            },
        )
        counts["waiting_list_entries"] += 1

    # Notes
    for note in ct.get("notes", []):
        cur.execute(
            """
            INSERT INTO draft.care_type_notes (care_type_id, note_type, description)
            VALUES (%(care_type_id)s, %(note_type)s, %(description)s)
            """,
            {
                "care_type_id": care_type_id,
                "note_type": note["type"],
                "description": note["description"],
            },
        )
        counts["care_type_notes"] += 1


@asset(group_name="bsil")
def provider_fixtures(
    context: AssetExecutionContext, bsil_postgres: BsilPostgresResource
):
    """Load provider fixture data from JSON files into the draft schema.

    Creates draft tables and loads fixture JSONs. Downstream publish_providers
    then copies draft -> published using the same code path as the real pipeline.
    """
    fixture_files = sorted(FIXTURES_DIR.glob("p*.json"))
    context.log.info(f"Found {len(fixture_files)} fixture files in {FIXTURES_DIR}")

    counts = {
        "providers": 0,
        "care_types": 0,
        "fee_rates": 0,
        "additional_charges": 0,
        "waiting_list_entries": 0,
        "care_type_notes": 0,
    }

    with bsil_postgres.get_connection() as conn:
        with conn.cursor() as cur:
            create_draft_tables(cur)

            for fixture_file in fixture_files:
                data = json.loads(fixture_file.read_text())
                load_fixture_provider(cur, data, counts)

        conn.commit()

    context.log.info(f"Loaded row counts: {counts}")
    return {k: MetadataValue.int(v) for k, v in counts.items()}
