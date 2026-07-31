"""Dagster asset building draft.care_offerings — a flat enumeration of every
childcare offering from all sources.

One row per (source, source_id, care_type).  Five sources:
  1. la_scrape   — LA-scraped providers via draft.linkage + la.extract_results
  2. ofsted      — all ofsted.inspections records
  3. school_census — dfe.school_census (filtered)
  4. free_breakfast — dfe.free_breakfast_club_schools
  5. tiney       — Tiney CMA childminder agency feed
"""

import json
import re

from dagster import asset, AssetExecutionContext, MetadataValue

from bsil_pipeline.automation import PIPELINE_CONDITION
from bsil_pipeline.extractors.base import infer_classification_from_name
from bsil_pipeline.resources.postgres import BsilPostgresResource
from bsil_pipeline.utils.postcode_lookup import postcode_to_lad

# ---------- Constants ----------

_POSTCODE_RE = re.compile(r"^([A-Z]{1,2}\d[A-Z\d]?)\s*(\d[A-Z]{2})$", re.IGNORECASE)

BATCH_SIZE = 1000

# Ofsted provider_type + subtype → care_type
_OFSTED_TYPE_MAP = {
    ("Childminder", None): "childminder",
    ("Childminder without domestic premises", None): "childminder",
    ("Home childcarer", None): "childminder",
    ("Childcare on domestic premises", None): "childminder",
    ("Childcare on non-domestic premises", "Full day care"): "private_nursery",
    ("Childcare on non-domestic premises", "Sessional day care"): "private_nursery",
    (
        "Childcare on non-domestic premises",
        "Out-of-school day care",
    ): "after_school_club",
    ("Childcare on non-domestic premises", None): "private_nursery",
}

# Registers without Early Years Register — providers on these only cannot
# serve under-5s. VCR/CCR-only providers are skipped entirely unless their
# name matches a recognisable care type. CCR-VCR providers are kept (with or
# without a care type) since they serve ages 5-18.
_VCR_CCR_ONLY_REGISTERS = frozenset({"VCR only", "CCR only"})
_CCR_VCR_REGISTER = "CCR-VCR"

_NAME_CARE_TYPE_PATTERNS = [
    ("breakfast club", "breakfast_club"),
    ("breakfast", "breakfast_club"),
    ("after school", "after_school_club"),
    ("afterschool", "after_school_club"),
    ("out of school", "after_school_club"),
    (" asc", "after_school_club"),
    ("holiday club", "holiday_club"),
    ("holiday camp", "holiday_club"),
    ("holiday", "holiday_club"),
    ("play scheme", "holiday_club"),
    ("playscheme", "holiday_club"),
    ("forest school", "holiday_club"),
    ("active camp", "holiday_club"),
]


def _match_name_pattern(name: str) -> str | None:
    if not name:
        return None
    lower = name.lower()
    for pattern, care_type in _NAME_CARE_TYPE_PATTERNS:
        if pattern in lower:
            return care_type
    return None


# Phase types to exclude from school census
_EXCLUDED_PHASE_TYPES = frozenset(
    {
        "Pupil referral unit",
        "Non-maintained special school",
    }
)

# ---------- SQL ----------

CREATE_SCHEMA_SQL = "CREATE SCHEMA IF NOT EXISTS draft"

DROP_TABLE_SQL = "DROP TABLE IF EXISTS draft.care_offerings"

CREATE_TABLE_SQL = """
CREATE TABLE draft.care_offerings (
    id                      BIGSERIAL PRIMARY KEY,
    source                  TEXT NOT NULL,
    source_id               TEXT NOT NULL,
    lad25cd                 TEXT,
    care_type               TEXT,
    source_label            TEXT,
    classification_method   TEXT,

    provider_name           TEXT,
    postcode                TEXT,

    ofsted_urn              TEXT,
    school_urn              TEXT,

    phase_type              TEXT,
    ofsted_provider_type    TEXT,
    ofsted_provider_subtype TEXT,

    built_at                TIMESTAMP DEFAULT now(),
    UNIQUE (source, source_id, care_type)
)
"""

INSERT_SQL = """
INSERT INTO draft.care_offerings (
    source, source_id, lad25cd, care_type, source_label, classification_method,
    provider_name, postcode, ofsted_urn, school_urn,
    phase_type, ofsted_provider_type, ofsted_provider_subtype
) VALUES (
    %(source)s, %(source_id)s, %(lad25cd)s, %(care_type)s, %(source_label)s,
    %(classification_method)s, %(provider_name)s, %(postcode)s,
    %(ofsted_urn)s, %(school_urn)s,
    %(phase_type)s, %(ofsted_provider_type)s, %(ofsted_provider_subtype)s
)
ON CONFLICT (source, source_id, care_type) DO NOTHING
"""


# ---------- Helpers ----------


def _normalise_postcode(pc: str | None) -> str | None:
    if not pc or pc.strip().upper() in ("NULL", "N/A", "NA"):
        return None
    m = _POSTCODE_RE.match(pc.strip())
    if m:
        return f"{m.group(1).upper()} {m.group(2).upper()}"
    cleaned = pc.strip().upper()
    return cleaned if cleaned else None


def _safe_int(val: str | None) -> int:
    """Parse a TEXT column to int, returning 0 for NULL/empty/non-numeric."""
    if not val:
        return 0
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0


def _load_la_name_lookup(conn) -> dict[str, str]:
    """Load os.la_name_lookup → {la_name: geo_code} (all geo_types)."""
    result = {}
    with conn.cursor() as cur:
        cur.execute("SELECT la_name, geo_code FROM os.la_name_lookup")
        for name, code in cur:
            result[name] = code
    return result


def _flush_batch(conn, batch: list[dict]) -> None:
    if not batch:
        return
    with conn.cursor() as cur:
        for row in batch:
            cur.execute(INSERT_SQL, row)
    conn.commit()


def _make_row(
    *,
    source: str,
    source_id: str,
    lad25cd: str | None = None,
    care_type: str | None = None,
    source_label: str | None = None,
    classification_method: str | None = None,
    provider_name: str | None = None,
    postcode: str | None = None,
    ofsted_urn: str | None = None,
    school_urn: str | None = None,
    phase_type: str | None = None,
    ofsted_provider_type: str | None = None,
    ofsted_provider_subtype: str | None = None,
) -> dict:
    return {
        "source": source,
        "source_id": source_id,
        "lad25cd": lad25cd,
        "care_type": care_type,
        "source_label": source_label,
        "classification_method": classification_method,
        "provider_name": provider_name,
        "postcode": postcode,
        "ofsted_urn": ofsted_urn,
        "school_urn": school_urn,
        "phase_type": phase_type,
        "ofsted_provider_type": ofsted_provider_type,
        "ofsted_provider_subtype": ofsted_provider_subtype,
    }


# ---------- Phase functions ----------


def _phase_la_scrape(conn, context) -> int:
    """Source 1: LA-scraped providers from draft.linkage + la.extract_results."""
    context.log.info(
        "Phase 1: la_scrape — loading from draft.linkage + la.extract_results"
    )

    sql = """
        SELECT l.lad25cd, l.provider_id, l.ofsted_urn, l.school_urn,
               e.classification, e.source_classification,
               e.extracted_data
        FROM draft.linkage l
        JOIN la.extract_results e
            ON l.lad25cd = e.lad25cd AND l.provider_id = e.provider_id
    """

    count = 0
    batch: list[dict] = []
    seen: set[tuple[str, str | None]] = set()

    with conn.cursor("la_scrape_cursor", withhold=True) as cur:
        cur.execute(sql)

        for (
            lad25cd,
            provider_id,
            ofsted_urn,
            school_urn,
            classification,
            source_classification,
            extracted_data,
        ) in cur:
            source_id = f"{lad25cd}:{provider_id}"

            if isinstance(extracted_data, str):
                extracted_data = json.loads(extracted_data)

            provider_name = (
                extracted_data.get("provider_name") if extracted_data else None
            )
            postcode = _normalise_postcode(
                extracted_data.get("postcode") if extracted_data else None
            )

            classifications = classification or []
            source_labels = source_classification or []

            if classifications:
                for i, ct in enumerate(classifications):
                    key = (source_id, ct)
                    if key in seen:
                        continue
                    seen.add(key)
                    label = source_labels[i] if i < len(source_labels) else None
                    batch.append(
                        _make_row(
                            source="la_scrape",
                            source_id=source_id,
                            lad25cd=lad25cd,
                            care_type=ct,
                            source_label=label,
                            classification_method="structured",
                            provider_name=provider_name,
                            postcode=postcode,
                            ofsted_urn=ofsted_urn,
                            school_urn=school_urn,
                        )
                    )
                    count += 1
            else:
                # Try name inference
                inferred = infer_classification_from_name(provider_name)
                if inferred:
                    for ct in inferred:
                        key = (source_id, ct)
                        if key in seen:
                            continue
                        seen.add(key)
                        batch.append(
                            _make_row(
                                source="la_scrape",
                                source_id=source_id,
                                lad25cd=lad25cd,
                                care_type=ct,
                                source_label=provider_name,
                                classification_method="inferred_from_name",
                                provider_name=provider_name,
                                postcode=postcode,
                                ofsted_urn=ofsted_urn,
                                school_urn=school_urn,
                            )
                        )
                        count += 1
                else:
                    # No classification at all
                    key = (source_id, None)
                    if key not in seen:
                        seen.add(key)
                        batch.append(
                            _make_row(
                                source="la_scrape",
                                source_id=source_id,
                                lad25cd=lad25cd,
                                care_type=None,
                                source_label=None,
                                classification_method="none",
                                provider_name=provider_name,
                                postcode=postcode,
                                ofsted_urn=ofsted_urn,
                                school_urn=school_urn,
                            )
                        )
                        count += 1

            if len(batch) >= BATCH_SIZE:
                _flush_batch(conn, batch)
                batch.clear()

    _flush_batch(conn, batch)
    context.log.info(f"Phase 1 complete: {count} la_scrape offerings")
    return count


def _phase_ofsted(conn, context, la_name_to_lad: dict[str, str]) -> tuple[int, int]:
    """Source 2: Ofsted inspections (all records).

    Returns (count, e10_resolved) — total offerings and how many had
    their county-level E10 lad25cd resolved to a district via postcode.
    """
    context.log.info("Phase 2: ofsted — loading from ofsted.inspections")

    # Check for scrape_results
    with conn.cursor() as cur:
        cur.execute(
            "SELECT EXISTS ("
            "  SELECT 1 FROM information_schema.tables"
            "  WHERE table_schema = 'ofsted' AND table_name = 'scrape_results'"
            ")"
        )
        has_scrape_results = cur.fetchone()[0]

    # Check for consented_addresses
    with conn.cursor() as cur:
        cur.execute(
            "SELECT EXISTS ("
            "  SELECT 1 FROM information_schema.tables"
            "  WHERE table_schema = 'ofsted' AND table_name = 'consented_addresses'"
            ")"
        )
        has_consented_addresses = cur.fetchone()[0]

    if has_scrape_results:
        if has_consented_addresses:
            sql = """
                SELECT i.provider_urn,
                       i.provider_type,
                       i.provider_subtype,
                       i.local_authority,
                       CASE WHEN i.provider_name = 'REDACTED'
                            THEN COALESCE(sr.provider_name, ca.provider_name)
                            ELSE i.provider_name END AS provider_name,
                       COALESCE(
                           NULLIF(NULLIF(i.provider_postcode, ''), 'REDACTED'),
                           sr.provider_postcode,
                           ca.postcode
                       ) AS postcode,
                       i.individual_register_combinations
                FROM ofsted.inspections i
                LEFT JOIN ofsted.scrape_results sr
                    ON i.provider_urn = sr.provider_urn
                    AND sr.scrape_status IN ('success', 'partial')
                LEFT JOIN ofsted.consented_addresses ca
                    ON i.provider_urn = ca.provider_urn
            """
        else:
            sql = """
                SELECT i.provider_urn,
                       i.provider_type,
                       i.provider_subtype,
                       i.local_authority,
                       CASE WHEN i.provider_name = 'REDACTED' AND sr.provider_name IS NOT NULL
                            THEN sr.provider_name ELSE i.provider_name END AS provider_name,
                       COALESCE(
                           NULLIF(NULLIF(i.provider_postcode, ''), 'REDACTED'),
                           sr.provider_postcode
                       ) AS postcode,
                       i.individual_register_combinations
                FROM ofsted.inspections i
                LEFT JOIN ofsted.scrape_results sr
                    ON i.provider_urn = sr.provider_urn
                    AND sr.scrape_status IN ('success', 'partial')
            """
    else:
        context.log.info("ofsted.scrape_results not found — using inspections only")
        sql = """
            SELECT provider_urn, provider_type, provider_subtype,
                   local_authority, provider_name, provider_postcode,
                   individual_register_combinations
            FROM ofsted.inspections
        """

    count = 0
    e10_resolved = 0
    no_eyr_skipped = 0
    no_eyr_name_matched = 0
    no_eyr_unclassified = 0
    batch: list[dict] = []

    with conn.cursor("ofsted_cursor", withhold=True) as cur:
        cur.execute(sql)

        for urn, ptype, psubtype, la_name, name, postcode, register in cur:
            if not urn:
                continue

            # Map provider_type + subtype → care_type
            # Try exact match first, then wildcard (subtype=None)
            care_type = _OFSTED_TYPE_MAP.get((ptype, psubtype))
            if care_type is None:
                care_type = _OFSTED_TYPE_MAP.get((ptype, None))

            if register in _VCR_CCR_ONLY_REGISTERS:
                name_care_type = _match_name_pattern(name)
                if name_care_type:
                    care_type = name_care_type
                    no_eyr_name_matched += 1
                else:
                    no_eyr_skipped += 1
                    continue
            elif register == _CCR_VCR_REGISTER and care_type != "after_school_club":
                name_care_type = _match_name_pattern(name)
                care_type = name_care_type
                if name_care_type:
                    no_eyr_name_matched += 1
                else:
                    no_eyr_unclassified += 1

            label_parts = [p for p in [ptype, psubtype] if p]
            source_label = " — ".join(label_parts) if label_parts else None

            lad25cd = la_name_to_lad.get(la_name) if la_name else None

            # Resolve county-level E10 codes to district via postcode
            if lad25cd and lad25cd.startswith("E10"):
                postcode_norm = _normalise_postcode(postcode)
                if postcode_norm:
                    resolved = postcode_to_lad(postcode_norm)
                    if resolved:
                        lad25cd = resolved
                        e10_resolved += 1

            batch.append(
                _make_row(
                    source="ofsted",
                    source_id=urn,
                    lad25cd=lad25cd,
                    care_type=care_type,
                    source_label=source_label,
                    classification_method="registration_type_map"
                    if care_type
                    else None,
                    provider_name=name if name != "REDACTED" else None,
                    postcode=_normalise_postcode(postcode),
                    ofsted_urn=urn,
                    ofsted_provider_type=ptype,
                    ofsted_provider_subtype=psubtype,
                )
            )
            count += 1

            if len(batch) >= BATCH_SIZE:
                _flush_batch(conn, batch)
                batch.clear()

    _flush_batch(conn, batch)
    context.log.info(
        f"Phase 2 complete: {count} ofsted offerings"
        f" ({e10_resolved} E10→district via postcode,"
        f" {no_eyr_skipped} VCR/CCR-only skipped,"
        f" {no_eyr_name_matched} no-EYR name-matched,"
        f" {no_eyr_unclassified} CCR-VCR unclassified)"
    )
    return count, e10_resolved


def _phase_school_census(conn, context) -> int:
    """Source 3: DfE school census (filtered)."""
    context.log.info("Phase 3: school_census — loading from dfe.school_census")

    sql = """
        SELECT c.urn, c.school_name, c.school_postcode,
               c.district_administrative_code, c.phase_type_grouping,
               c.n_nursery,
               g.nursery_provision
        FROM dfe.school_census c
        LEFT JOIN dfe.gias_schools g ON g.urn = c.urn
    """

    count = 0
    batch: list[dict] = []

    with conn.cursor("school_census_cursor", withhold=True) as cur:
        cur.execute(sql)

        for (
            urn,
            name,
            postcode,
            lad25cd,
            phase_type,
            n_nursery,
            nursery_provision,
        ) in cur:
            if not urn:
                continue
            if phase_type in _EXCLUDED_PHASE_TYPES:
                continue

            nursery_pupils = _safe_int(n_nursery)

            if phase_type == "State-funded nursery":
                care_type = "school_based_nursery"
                method = "phase_type"
            elif nursery_pupils > 0:
                care_type = "school_based_nursery"
                method = "census_nursery_pupils"
            elif nursery_provision == "Has Nursery Classes":
                care_type = "school_based_nursery"
                method = "gias_nursery_provision"
            else:
                care_type = None
                method = None

            batch.append(
                _make_row(
                    source="school_census",
                    source_id=urn,
                    lad25cd=lad25cd,
                    care_type=care_type,
                    source_label=phase_type,
                    classification_method=method,
                    provider_name=name,
                    postcode=_normalise_postcode(postcode),
                    school_urn=urn,
                    phase_type=phase_type,
                )
            )
            count += 1

            if len(batch) >= BATCH_SIZE:
                _flush_batch(conn, batch)
                batch.clear()

    _flush_batch(conn, batch)
    context.log.info(f"Phase 3 complete: {count} school_census offerings")
    return count


def _phase_free_breakfast(
    conn, context, la_name_to_lad: dict[str, str]
) -> tuple[int, int]:
    """Source 4: Free breakfast club schools.

    Joins with school_census to enrich rows with postcode, phase_type,
    and precise lad25cd. Special_AP records (PRUs, alternative provision,
    special schools) are skipped — consistent with census exclusions.
    """
    context.log.info(
        "Phase 4: free_breakfast — loading from dfe.free_breakfast_club_schools"
    )

    sql = """
        SELECT f.urn, f.school_name, f.la_name, f.type,
               sc.school_postcode, sc.phase_type_grouping,
               sc.district_administrative_code
        FROM dfe.free_breakfast_club_schools f
        LEFT JOIN dfe.school_census sc ON sc.urn = f.urn
    """

    count = 0
    skipped = 0
    batch: list[dict] = []

    with conn.cursor("breakfast_cursor", withhold=True) as cur:
        cur.execute(sql)

        for urn, name, la_name, fb_type, sc_postcode, sc_phase, sc_lad in cur:
            if not urn:
                continue

            if fb_type == "Special_AP":
                skipped += 1
                continue

            # Prefer census district code; fall back to LA name lookup
            if sc_lad:
                lad25cd = sc_lad
            else:
                lad25cd = la_name_to_lad.get(la_name) if la_name else None

            has_census = sc_postcode is not None or sc_phase is not None

            batch.append(
                _make_row(
                    source="free_breakfast",
                    source_id=urn,
                    lad25cd=lad25cd,
                    care_type="free_breakfast_club",
                    source_label="Free breakfast club scheme",
                    classification_method=(
                        "scheme_membership_census_enriched"
                        if has_census
                        else "scheme_membership"
                    ),
                    provider_name=name,
                    postcode=_normalise_postcode(sc_postcode),
                    school_urn=urn,
                    phase_type=sc_phase,
                )
            )
            count += 1

            if len(batch) >= BATCH_SIZE:
                _flush_batch(conn, batch)
                batch.clear()

    _flush_batch(conn, batch)
    context.log.info(
        f"Phase 4 complete: {count} free_breakfast offerings"
        f" ({skipped} Special_AP skipped)"
    )
    return count, skipped


def _phase_tiney(conn, context, la_name_to_lad: dict[str, str]) -> int:
    """Source 5: Tiney childminder agency feed (open providers only)."""
    context.log.info("Phase 5: tiney — loading from tiney.childminders")

    with conn.cursor() as cur:
        cur.execute(
            "SELECT EXISTS ("
            "  SELECT 1 FROM information_schema.tables"
            "  WHERE table_schema = 'tiney' AND table_name = 'childminders'"
            ")"
        )
        if not cur.fetchone()[0]:
            context.log.info("tiney.childminders not found — skipping")
            return 0

    sql = """
        SELECT ofsted_urn, provider_name, postcode, local_authority_name
        FROM tiney.childminders
        WHERE tiney_lifecycle_status = 'open'
    """

    count = 0
    batch: list[dict] = []

    with conn.cursor("tiney_cursor", withhold=True) as cur:
        cur.execute(sql)

        for urn, name, postcode, la_name in cur:
            if not urn:
                continue

            lad25cd = la_name_to_lad.get(la_name) if la_name else None
            if not lad25cd and postcode:
                lad25cd = postcode_to_lad(_normalise_postcode(postcode))

            batch.append(
                _make_row(
                    source="tiney",
                    source_id=urn,
                    lad25cd=lad25cd,
                    care_type="childminder",
                    source_label="Tiney CMA childminder",
                    classification_method="source_feed",
                    provider_name=name,
                    postcode=_normalise_postcode(postcode),
                    ofsted_urn=urn,
                )
            )
            count += 1

            if len(batch) >= BATCH_SIZE:
                _flush_batch(conn, batch)
                batch.clear()

    _flush_batch(conn, batch)
    context.log.info(f"Phase 5 complete: {count} tiney offerings")
    return count


def _phase_bristol_wraparound(conn, context) -> int:
    """Source 6: Bristol Council wraparound childcare directory.

    Reads matched schools from draft.bristol_wraparound (written by
    bristol_wraparound_matches asset) and creates breakfast_club /
    after_school_club offerings based on space availability.
    """
    context.log.info(
        "Phase 6: bristol_wraparound — loading from draft.bristol_wraparound"
    )

    with conn.cursor() as cur:
        cur.execute(
            "SELECT EXISTS ("
            "  SELECT 1 FROM information_schema.tables"
            "  WHERE table_schema = 'draft' AND table_name = 'bristol_wraparound'"
            ")"
        )
        if not cur.fetchone()[0]:
            context.log.info("draft.bristol_wraparound not found — skipping")
            return 0

    sql = """
        SELECT school_urn, school_name, postcode, before_spaces, after_spaces
        FROM draft.bristol_wraparound
    """

    count = 0
    batch: list[dict] = []
    lad25cd = "E06000023"

    with conn.cursor() as cur:
        cur.execute(sql)

        for school_urn, name, postcode, before_spaces, after_spaces in cur.fetchall():
            if before_spaces and before_spaces > 0:
                batch.append(
                    _make_row(
                        source="bristol_wraparound",
                        source_id=school_urn,
                        lad25cd=lad25cd,
                        care_type="breakfast_club",
                        source_label="Wraparound childcare (before school)",
                        classification_method="council_wraparound_directory",
                        provider_name=name,
                        postcode=_normalise_postcode(postcode),
                        school_urn=school_urn,
                    )
                )
                count += 1

            if after_spaces and after_spaces > 0:
                batch.append(
                    _make_row(
                        source="bristol_wraparound",
                        source_id=school_urn,
                        lad25cd=lad25cd,
                        care_type="after_school_club",
                        source_label="Wraparound childcare (after school)",
                        classification_method="council_wraparound_directory",
                        provider_name=name,
                        postcode=_normalise_postcode(postcode),
                        school_urn=school_urn,
                    )
                )
                count += 1

            if len(batch) >= BATCH_SIZE:
                _flush_batch(conn, batch)
                batch.clear()

    _flush_batch(conn, batch)
    context.log.info(f"Phase 6 complete: {count} bristol_wraparound offerings")
    return count


# ---------- Dagster asset ----------


@asset(
    group_name="draft",
    deps=[
        "provider_linkage",
        "la_extract_results",
        "ofsted_inspections",
        "ofsted_consented_addresses",
        "school_census",
        "gias_schools",
        "free_breakfast_club_schools",
        "os_bounding_boxes",
        "tiney_childminders",
        "bristol_wraparound_matches",
    ],
    automation_condition=PIPELINE_CONDITION,
)
def care_offerings(context: AssetExecutionContext, bsil_postgres: BsilPostgresResource):
    """Build draft.care_offerings — flat enumeration of every childcare
    offering from all sources (la_scrape, ofsted, school_census, free_breakfast).
    """

    with bsil_postgres.get_connection() as conn:
        # Fresh table each run
        with conn.cursor() as cur:
            cur.execute(CREATE_SCHEMA_SQL)
            cur.execute(DROP_TABLE_SQL)
            cur.execute(CREATE_TABLE_SQL)
            conn.commit()

        # Load LA name → LAD code lookup
        la_name_to_lad = _load_la_name_lookup(conn)
        context.log.info(f"Loaded {len(la_name_to_lad)} LA name → LAD code mappings")

        # Run five phases
        la_count = _phase_la_scrape(conn, context)
        ofsted_count, e10_resolved = _phase_ofsted(conn, context, la_name_to_lad)
        school_count = _phase_school_census(conn, context)
        breakfast_count, breakfast_skipped = _phase_free_breakfast(
            conn, context, la_name_to_lad
        )
        tiney_count = _phase_tiney(conn, context, la_name_to_lad)
        wraparound_count = _phase_bristol_wraparound(conn, context)

        total = (
            la_count
            + ofsted_count
            + school_count
            + breakfast_count
            + tiney_count
            + wraparound_count
        )
        context.log.info(f"care_offerings complete: {total} total rows")

    return {
        "total_rows": MetadataValue.int(total),
        "la_scrape": MetadataValue.int(la_count),
        "ofsted": MetadataValue.int(ofsted_count),
        "ofsted_e10_resolved": MetadataValue.int(e10_resolved),
        "school_census": MetadataValue.int(school_count),
        "free_breakfast": MetadataValue.int(breakfast_count),
        "free_breakfast_special_ap_skipped": MetadataValue.int(breakfast_skipped),
        "tiney": MetadataValue.int(tiney_count),
        "bristol_wraparound": MetadataValue.int(wraparound_count),
    }
