"""Schema definition assets — single source of truth for all pipeline DDL.

Each asset ensures its schema and table exist in Postgres. Data-loading
assets and restore_all_parquet depend on these so that table creation
is never skipped.

Tables with dynamic DDL (ofsted.inspections, dfe.school_census) only
create their schema here; the data-loading asset builds the table from
source-file headers at runtime. The parquet restore path auto-creates
these tables from parquet metadata when needed.
"""

from dagster import asset, MetadataValue
from psycopg.errors import UniqueViolation

from bsil_pipeline.resources.postgres import BsilPostgresResource


def _ensure_schema(conn, schema_name: str) -> None:
    """Create schema if not exists, handling concurrent creation race conditions.

    PostgreSQL's CREATE SCHEMA IF NOT EXISTS can raise UniqueViolation when
    multiple processes try to create the same schema concurrently (the IF NOT
    EXISTS check isn't atomic). We catch that and retry in a new transaction.
    """
    try:
        with conn.cursor() as cur:
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")  # nosec B608
        conn.commit()
    except UniqueViolation:
        conn.rollback()


# ---------------------------------------------------------------------------
# dfe schema
# ---------------------------------------------------------------------------

DFE_GIAS_SCHOOLS_DDL = """
CREATE TABLE IF NOT EXISTS dfe.gias_schools (
    urn TEXT PRIMARY KEY,
    establishment_name TEXT,
    street TEXT,
    locality TEXT,
    address3 TEXT,
    town TEXT,
    county TEXT,
    postcode TEXT,
    easting TEXT,
    northing TEXT,
    establishment_type_group TEXT,
    phase_of_education TEXT,
    establishment_status TEXT,
    telephone_num TEXT,
    school_website TEXT,
    statutory_low_age TEXT,
    statutory_high_age TEXT,
    nursery_provision TEXT,
    number_of_pupils TEXT,
    religious_character TEXT,
    latitude REAL,
    longitude REAL
)
"""

DFE_FREE_BREAKFAST_CLUB_SCHOOLS_DDL = """
CREATE TABLE IF NOT EXISTS dfe.free_breakfast_club_schools (
    urn                    TEXT PRIMARY KEY,
    school_name            TEXT,
    type                   TEXT,
    establishment_type_group TEXT,
    gor_name               TEXT,
    la_name                TEXT
)
"""

# ---------------------------------------------------------------------------
# la schema
# ---------------------------------------------------------------------------

LA_FAMILY_INFORMATION_SERVICES_DDL = """
CREATE TABLE IF NOT EXISTS la.family_information_services (
    lad25cd TEXT NOT NULL,
    lad25nm TEXT,
    fis_url TEXT NOT NULL,
    childcare_types TEXT,
    notes TEXT,
    PRIMARY KEY (lad25cd, fis_url)
)
"""

LA_SCRAPE_RESULTS_DDL = """
CREATE TABLE IF NOT EXISTS la.scrape_results (
    lad25cd TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    provider_name TEXT,
    provider_address_line1 TEXT,
    provider_address_line2 TEXT,
    provider_address_line3 TEXT,
    provider_town TEXT,
    provider_postcode TEXT,
    provider_urn TEXT,
    provider_phone TEXT,
    provider_email TEXT,
    provider_latitude DOUBLE PRECISION,
    provider_longitude DOUBLE PRECISION,
    source_url TEXT,
    raw_html TEXT,
    raw_json TEXT,
    metadata_json JSONB,
    scrape_status TEXT NOT NULL,
    scraped_at TIMESTAMP DEFAULT now(),
    PRIMARY KEY (lad25cd, provider_id)
)
"""

LA_EXTRACT_RESULTS_DDL = """
CREATE TABLE IF NOT EXISTS la.extract_results (
    lad25cd TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    extracted_data JSONB NOT NULL,
    classification TEXT[] NOT NULL DEFAULT '{}',
    source_classification TEXT[] NOT NULL DEFAULT '{}',
    field_count INTEGER NOT NULL DEFAULT 0,
    extraction_warnings TEXT[] NOT NULL DEFAULT '{}',
    lad_source TEXT,
    draft_exclude BOOLEAN NOT NULL DEFAULT false,
    extracted_at TIMESTAMP DEFAULT now(),
    PRIMARY KEY (lad25cd, provider_id)
)
"""

# ---------------------------------------------------------------------------
# ofsted schema
# ---------------------------------------------------------------------------

OFSTED_SCHOOL_INSPECTIONS_DDL = """
CREATE TABLE IF NOT EXISTS ofsted.school_inspections (
    urn TEXT PRIMARY KEY,
    school_name TEXT,
    ofsted_phase TEXT,
    inspection_date TEXT,
    safeguarding_standards TEXT,
    achievement TEXT,
    curriculum_and_teaching TEXT,
    attendance_and_behaviour TEXT,
    personal_development_wellbeing TEXT,
    inclusion TEXT,
    leadership_and_governance TEXT,
    early_years TEXT,
    post_16 TEXT,
    oeif_inspection_date TEXT,
    oeif_overall_effectiveness TEXT,
    oeif_quality_of_education TEXT,
    oeif_behaviour_and_attitudes TEXT,
    oeif_personal_development TEXT,
    oeif_leadership_and_management TEXT,
    oeif_safeguarding_effective TEXT,
    oeif_early_years TEXT,
    oeif_sixth_form TEXT,
    ungraded_inspection_date TEXT,
    ungraded_overall_outcome TEXT
)
"""

OFSTED_SCRAPE_RESULTS_DDL = """
CREATE TABLE IF NOT EXISTS ofsted.scrape_results (
    provider_urn TEXT PRIMARY KEY,
    provider_name TEXT,
    provider_address_line1 TEXT,
    provider_address_line2 TEXT,
    provider_address_line3 TEXT,
    provider_town TEXT,
    provider_postcode TEXT,
    scrape_status TEXT,
    scraped_at TIMESTAMP DEFAULT now()
)
"""

OFSTED_CONSENTED_ADDRESSES_DDL = """
CREATE TABLE IF NOT EXISTS ofsted.consented_addresses (
    provider_urn TEXT PRIMARY KEY,
    provider_type TEXT,
    register_combo TEXT,
    eyr_flag TEXT,
    ccr_flag TEXT,
    vcr_flag TEXT,
    provider_name TEXT,
    address_line_1 TEXT,
    address_line_2 TEXT,
    address_line_3 TEXT,
    town TEXT,
    postcode TEXT,
    parliamentary_constituency TEXT,
    local_authority TEXT,
    region TEXT,
    ofsted_region TEXT
)
"""

# ---------------------------------------------------------------------------
# os schema
# ---------------------------------------------------------------------------

OS_BOUNDING_BOXES_DDL = """
CREATE TABLE IF NOT EXISTS os.bounding_boxes (
    geo_type TEXT NOT NULL,
    geo_code TEXT NOT NULL,
    geo_name TEXT,
    bbox_north DOUBLE PRECISION NOT NULL,
    bbox_south DOUBLE PRECISION NOT NULL,
    bbox_east DOUBLE PRECISION NOT NULL,
    bbox_west DOUBLE PRECISION NOT NULL,
    postcode_count INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (geo_type, geo_code)
)
"""

OS_LA_NAME_LOOKUP_DDL = """
CREATE TABLE IF NOT EXISTS os.la_name_lookup (
    la_name TEXT PRIMARY KEY,
    geo_type TEXT NOT NULL,
    geo_code TEXT NOT NULL
)
"""

OS_OFSTED_PLACES_DDL = """
CREATE TABLE IF NOT EXISTS os.ofsted_places (
    provider_urn TEXT PRIMARY KEY,
    provider_address_line_1 TEXT,
    provider_address_line_2 TEXT,
    provider_address_line_3 TEXT,
    provider_town TEXT,
    provider_postcode TEXT,
    query_used TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    geocode_status TEXT NOT NULL,
    bbox_geo_type TEXT,
    bbox_geo_code TEXT,
    geocoded_at TIMESTAMP DEFAULT now()
)
"""

OS_LA_PLACES_DDL = """
CREATE TABLE IF NOT EXISTS os.la_places (
    lad25cd TEXT NOT NULL,
    provider_id TEXT NOT NULL,
    address_line1 TEXT,
    address_line2 TEXT,
    address_line3 TEXT,
    town TEXT,
    postcode TEXT,
    query_used TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    geocode_status TEXT NOT NULL,
    bbox_geo_type TEXT,
    bbox_geo_code TEXT,
    geocoded_at TIMESTAMP DEFAULT now(),
    PRIMARY KEY (lad25cd, provider_id)
)
"""


# ---------------------------------------------------------------------------
# ten_ds schema
# ---------------------------------------------------------------------------

TEN_DS_COST_ESTIMATES_DDL = """
CREATE TABLE IF NOT EXISTS ten_ds.cost_estimates (
    la_code TEXT NOT NULL,
    la_name TEXT NOT NULL,
    region TEXT NOT NULL,
    age_group TEXT NOT NULL,
    prov_group TEXT NOT NULL,
    hourly_lower DOUBLE PRECISION,
    hourly_mean DOUBLE PRECISION,
    hourly_weighted_mean DOUBLE PRECISION,
    hourly_upper DOUBLE PRECISION,
    meal_lower DOUBLE PRECISION,
    meal_mean DOUBLE PRECISION,
    meal_upper DOUBLE PRECISION,
    funding_rate DOUBLE PRECISION,
    data_level TEXT NOT NULL,
    n_la INTEGER,
    n_region INTEGER,
    n_national INTEGER,
    PRIMARY KEY (la_code, age_group, prov_group)
)
"""


# ---------------------------------------------------------------------------
# Schema assets — dfe
# ---------------------------------------------------------------------------


@asset(group_name="schema")
def dfe_gias_schools_table(bsil_postgres: BsilPostgresResource):
    """Ensure dfe.gias_schools table exists."""
    with bsil_postgres.get_connection() as conn:
        _ensure_schema(conn, "dfe")
        with conn.cursor() as cur:
            cur.execute(DFE_GIAS_SCHOOLS_DDL)
        conn.commit()
    return MetadataValue.text("dfe.gias_schools ready")


@asset(group_name="schema")
def dfe_school_census_table(bsil_postgres: BsilPostgresResource):
    """Ensure dfe schema exists for school_census (table DDL is dynamic)."""
    with bsil_postgres.get_connection() as conn:
        _ensure_schema(conn, "dfe")
    return MetadataValue.text("dfe schema ready (school_census DDL is dynamic)")


@asset(group_name="schema")
def dfe_free_breakfast_club_schools_table(bsil_postgres: BsilPostgresResource):
    """Ensure dfe.free_breakfast_club_schools table exists."""
    with bsil_postgres.get_connection() as conn:
        _ensure_schema(conn, "dfe")
        with conn.cursor() as cur:
            cur.execute(DFE_FREE_BREAKFAST_CLUB_SCHOOLS_DDL)
        conn.commit()
    return MetadataValue.text("dfe.free_breakfast_club_schools ready")


# ---------------------------------------------------------------------------
# Schema assets — la
# ---------------------------------------------------------------------------


@asset(group_name="schema")
def la_family_information_services_table(bsil_postgres: BsilPostgresResource):
    """Ensure la.family_information_services table exists."""
    with bsil_postgres.get_connection() as conn:
        _ensure_schema(conn, "la")
        with conn.cursor() as cur:
            cur.execute(LA_FAMILY_INFORMATION_SERVICES_DDL)
        conn.commit()
    return MetadataValue.text("la.family_information_services ready")


@asset(group_name="schema")
def la_scrape_results_table(bsil_postgres: BsilPostgresResource):
    """Ensure la.scrape_results table exists."""
    with bsil_postgres.get_connection() as conn:
        _ensure_schema(conn, "la")
        with conn.cursor() as cur:
            cur.execute(LA_SCRAPE_RESULTS_DDL)
        conn.commit()
    return MetadataValue.text("la.scrape_results ready")


@asset(group_name="schema")
def la_extract_results_table(bsil_postgres: BsilPostgresResource):
    """Ensure la.extract_results table exists."""
    with bsil_postgres.get_connection() as conn:
        _ensure_schema(conn, "la")
        with conn.cursor() as cur:
            cur.execute(LA_EXTRACT_RESULTS_DDL)
            cur.execute(
                "ALTER TABLE la.extract_results"
                " ADD COLUMN IF NOT EXISTS draft_exclude BOOLEAN NOT NULL DEFAULT false"
            )
        conn.commit()
    return MetadataValue.text("la.extract_results ready")


# ---------------------------------------------------------------------------
# Schema assets — ofsted
# ---------------------------------------------------------------------------


@asset(group_name="schema")
def ofsted_inspections_table(bsil_postgres: BsilPostgresResource):
    """Ensure ofsted schema exists for inspections (table DDL is dynamic)."""
    with bsil_postgres.get_connection() as conn:
        _ensure_schema(conn, "ofsted")
    return MetadataValue.text("ofsted schema ready (inspections DDL is dynamic)")


@asset(group_name="schema")
def ofsted_school_inspections_table(bsil_postgres: BsilPostgresResource):
    """Ensure ofsted.school_inspections table exists."""
    with bsil_postgres.get_connection() as conn:
        _ensure_schema(conn, "ofsted")
        with conn.cursor() as cur:
            cur.execute(OFSTED_SCHOOL_INSPECTIONS_DDL)
        conn.commit()
    return MetadataValue.text("ofsted.school_inspections ready")


@asset(group_name="schema")
def ofsted_scrape_results_table(bsil_postgres: BsilPostgresResource):
    """Ensure ofsted.scrape_results table exists."""
    with bsil_postgres.get_connection() as conn:
        _ensure_schema(conn, "ofsted")
        with conn.cursor() as cur:
            cur.execute(OFSTED_SCRAPE_RESULTS_DDL)
        conn.commit()
    return MetadataValue.text("ofsted.scrape_results ready")


@asset(group_name="schema")
def ofsted_consented_addresses_table(bsil_postgres: BsilPostgresResource):
    """Ensure ofsted.consented_addresses table exists."""
    with bsil_postgres.get_connection() as conn:
        _ensure_schema(conn, "ofsted")
        with conn.cursor() as cur:
            cur.execute(OFSTED_CONSENTED_ADDRESSES_DDL)
        conn.commit()
    return MetadataValue.text("ofsted.consented_addresses ready")


# ---------------------------------------------------------------------------
# Schema assets — os
# ---------------------------------------------------------------------------


@asset(group_name="schema")
def os_bounding_boxes_table(bsil_postgres: BsilPostgresResource):
    """Ensure os.bounding_boxes table exists."""
    with bsil_postgres.get_connection() as conn:
        _ensure_schema(conn, "os")
        with conn.cursor() as cur:
            cur.execute(OS_BOUNDING_BOXES_DDL)
        conn.commit()
    return MetadataValue.text("os.bounding_boxes ready")


@asset(group_name="schema")
def os_la_name_lookup_table(bsil_postgres: BsilPostgresResource):
    """Ensure os.la_name_lookup table exists."""
    with bsil_postgres.get_connection() as conn:
        _ensure_schema(conn, "os")
        with conn.cursor() as cur:
            cur.execute(OS_LA_NAME_LOOKUP_DDL)
        conn.commit()
    return MetadataValue.text("os.la_name_lookup ready")


@asset(group_name="schema")
def os_ofsted_places_table(bsil_postgres: BsilPostgresResource):
    """Ensure os.ofsted_places table exists."""
    with bsil_postgres.get_connection() as conn:
        _ensure_schema(conn, "os")
        with conn.cursor() as cur:
            cur.execute(OS_OFSTED_PLACES_DDL)
        conn.commit()
    return MetadataValue.text("os.ofsted_places ready")


@asset(group_name="schema")
def os_la_places_table(bsil_postgres: BsilPostgresResource):
    """Ensure os.la_places table exists."""
    with bsil_postgres.get_connection() as conn:
        _ensure_schema(conn, "os")
        with conn.cursor() as cur:
            cur.execute(OS_LA_PLACES_DDL)
        conn.commit()
    return MetadataValue.text("os.la_places ready")


# ---------------------------------------------------------------------------
# Schema assets — ten_ds
# ---------------------------------------------------------------------------


@asset(group_name="schema")
def ten_ds_cost_estimates_table(bsil_postgres: BsilPostgresResource):
    """Ensure ten_ds.cost_estimates table exists."""
    with bsil_postgres.get_connection() as conn:
        _ensure_schema(conn, "ten_ds")
        with conn.cursor() as cur:
            cur.execute(TEN_DS_COST_ESTIMATES_DDL)
        conn.commit()
    return MetadataValue.text("ten_ds.cost_estimates ready")


# ---------------------------------------------------------------------------
# mhclg schema
# ---------------------------------------------------------------------------

MHCLG_IOD_2025_DDL = """
CREATE TABLE IF NOT EXISTS mhclg.iod_2025 (
    lsoa21cd TEXT PRIMARY KEY,
    lsoa21nm TEXT,
    lad24cd TEXT,
    lad24nm TEXT,
    imd_rank INTEGER NOT NULL,
    imd_decile SMALLINT NOT NULL
)
"""


@asset(group_name="schema")
def mhclg_iod_2025_table(bsil_postgres: BsilPostgresResource):
    """Ensure mhclg.iod_2025 table exists."""
    with bsil_postgres.get_connection() as conn:
        _ensure_schema(conn, "mhclg")
        with conn.cursor() as cur:
            cur.execute(MHCLG_IOD_2025_DDL)
        conn.commit()
    return MetadataValue.text("mhclg.iod_2025 ready")


# ---------------------------------------------------------------------------
# tiney schema
# ---------------------------------------------------------------------------

TINEY_CHILDMINDERS_DDL = """
CREATE TABLE IF NOT EXISTS tiney.childminders (
    ofsted_urn TEXT PRIMARY KEY,
    provider_name TEXT,
    address_line_1 TEXT,
    address_city TEXT,
    postcode TEXT,
    uk_region TEXT,
    local_authority_name TEXT,
    website_url TEXT,
    ofsted_register_combination TEXT,
    tiney_registration_type TEXT,
    tiney_registration_date DATE,
    age_range TEXT,
    last_inspection_date DATE,
    last_inspection_type TEXT,
    cma_qa_grading TEXT,
    registered_places INTEGER,
    operating_weeks_per_year INTEGER,
    minimum_commitment TEXT,
    opening_hours TEXT,
    placement_type TEXT,
    funded_hours_accepted BOOLEAN,
    hourly_rate_gbp NUMERIC(8,2),
    daily_rate_gbp NUMERIC(8,2),
    additional_charges TEXT,
    tiney_lifecycle_status TEXT
)
"""


@asset(group_name="schema")
def tiney_childminders_table(bsil_postgres: BsilPostgresResource):
    """Ensure tiney.childminders table exists."""
    with bsil_postgres.get_connection() as conn:
        _ensure_schema(conn, "tiney")
        with conn.cursor() as cur:
            cur.execute(TINEY_CHILDMINDERS_DDL)
        conn.commit()
    return MetadataValue.text("tiney.childminders ready")


POSTHOG_EVENTS_DDL = """
CREATE TABLE IF NOT EXISTS posthog.events (
    uuid TEXT PRIMARY KEY,
    event TEXT NOT NULL,
    properties JSONB,
    timestamp TIMESTAMPTZ NOT NULL,
    distinct_id TEXT,
    session_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_posthog_events_event_ts
    ON posthog.events (event, timestamp);
"""


@asset(group_name="schema")
def posthog_events_table(bsil_postgres: BsilPostgresResource):
    """Ensure posthog.events table exists."""
    with bsil_postgres.get_connection() as conn:
        _ensure_schema(conn, "posthog")
        with conn.cursor() as cur:
            cur.execute(POSTHOG_EVENTS_DDL)
        conn.commit()
    return MetadataValue.text("posthog.events ready")
