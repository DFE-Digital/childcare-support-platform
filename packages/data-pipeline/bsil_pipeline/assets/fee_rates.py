"""Dagster asset building draft.fee_rates from LA extract fee data.

Parses three distinct fee formats from LA scrape extracts:
  1. fees_structured — JSON arrays: '["£65.00 (Day): under 3 years", ...]'
  2. fees_raw — simple text: "£5.50 per hour, £49.50 per day"
  3. extra.costs — text with optional age context: "£6.50 per hour £39.00 per day for under 2"
"""

import json
import re

from dagster import asset, AssetExecutionContext, MetadataValue

from bsil_pipeline.automation import PIPELINE_CONDITION
from bsil_pipeline.resources.postgres import BsilPostgresResource

BATCH_SIZE = 2000

# ---------- SQL ----------

DROP_SQL = "DROP TABLE IF EXISTS draft.fee_rates"

CREATE_SQL = """
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
    metadata        JSONB NOT NULL DEFAULT '{}',
    built_at        TIMESTAMP DEFAULT now()
)
"""

INDEX_SQL = [
    "CREATE INDEX idx_draft_fee_rates_care_type_id ON draft.fee_rates(care_type_id)",
]

INSERT_SQL = """
INSERT INTO draft.fee_rates
    (care_type_id, age_band, morning_session, afternoon_session,
     full_day, per_session, per_hour, per_day, metadata)
VALUES
    (%(care_type_id)s, %(age_band)s, %(morning_session)s, %(afternoon_session)s,
     %(full_day)s, %(per_session)s, %(per_hour)s, %(per_day)s, %(metadata)s)
"""

# Load LA extracts that have fee data, joined to care_type IDs
LOAD_FEE_EXTRACTS_SQL = """
SELECT ct.id AS care_type_id,
       ps.source_id,
       e.extracted_data
FROM draft.care_types ct
JOIN draft.provider_sources ps ON ps.provider_id = ct.provider_id
JOIN la.extract_results e
    ON e.lad25cd = split_part(ps.source_id, ':', 1)
   AND e.provider_id = substring(ps.source_id FROM position(':' IN ps.source_id) + 1)
WHERE ps.source = 'la_scrape'
  AND (e.extracted_data->>'fees_structured' IS NOT NULL
    OR e.extracted_data->>'fees_raw' IS NOT NULL
    OR (e.extracted_data->'extra'->>'costs' IS NOT NULL
        AND e.extracted_data->'extra'->>'costs' ~ '£[0-9]'))
ORDER BY ct.id
"""

# ---------- Parsers ----------

# £XX.XX amount
_RE_AMOUNT = re.compile(r"£(\d+(?:\.\d{1,2})?)")

# fees_structured entry: "£65.00 (Day): under 3 years"
_RE_STRUCTURED = re.compile(r"£(\d+(?:\.\d{1,2})?)\s*\((\w[\w\s]*?)\)(?:\s*:\s*(.+))?$")

# fees_raw / costs: "£5.50 per hour"
_RE_PER_UNIT = re.compile(
    r"£(\d+(?:\.\d{1,2})?)\s+per\s+(hour|day|session|half\s*day|week)",
    re.IGNORECASE,
)

# costs with age context: "£39.00 per day for a child under 2 years"
_RE_COST_AGE = re.compile(
    r"£(\d+(?:\.\d{1,2})?)\s+per\s+(day|session|hour)"
    r"\s+for\s+(?:a\s+)?(?:child\s+)?(under\s*2|2\s*year\s*old|3\s*or\s*4\s*year\s*old)",
    re.IGNORECASE,
)

# Unit mapping for fees_structured
_UNIT_MAP = {
    "hour": "per_hour",
    "day": "full_day",
    "half day": "morning_session",  # half day → morning_session column
    "session": "per_session",
    "week": None,  # skip weekly rates — no column for it
}

# Age band mapping
_AGE_BAND_PATTERNS = [
    (re.compile(r"under\s*2|0[-–]2|babies|baby", re.I), "under2"),
    (re.compile(r"\b2\s*year\s*old|age\s*2\b|2[-–]3", re.I), "age2"),
    (
        re.compile(
            r"3\s*(?:or|&|and)\s*4\s*year|3[-–]4|3[-–]5|age\s*3|over\s*2|2\s*plus|\+2|2'?s?\s+and\s+over",
            re.I,
        ),
        "age3to4",
    ),
    (
        re.compile(r"over\s*3|3\s*plus|\+3|3'?s?\s+and\s+over|3\s*years?\s*\+", re.I),
        "age3to4",
    ),
    (
        re.compile(r"under\s*3|0[-–]3", re.I),
        "under2",
    ),  # conservative: under3 → under2 band
    (re.compile(r"over\s*5|school\s*age|5[-–]", re.I), "age5plus"),
]


def _classify_age_band(text):
    """Classify age description text into an age_band enum value."""
    if not text:
        return "all"
    for pattern, band in _AGE_BAND_PATTERNS:
        if pattern.search(text):
            return band
    return "all"


def _parse_fees_structured(raw):
    """Parse fees_structured JSON array into fee rows.

    Input: '["£65.00 (Day): under 3 years", "£5.50 (Hour): 3years+"]'
    Returns: list of {age_band, column: amount} dicts.
    """
    if not raw:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return []
    if not isinstance(raw, list):
        return []

    # Collect by age_band
    by_band = {}  # age_band -> {column: amount}
    for entry in raw:
        if not isinstance(entry, str):
            continue
        m = _RE_STRUCTURED.match(entry.strip())
        if not m:
            continue
        amount = float(m.group(1))
        unit = m.group(2).strip().lower()
        age_text = m.group(3)

        column = _UNIT_MAP.get(unit)
        if column is None:
            continue

        # For half day, check description for AM/PM to assign correctly
        columns = [column]
        if unit == "half day":
            desc = (age_text or "").lower()
            if re.search(r"afternoon|pm\b", desc) and not re.search(
                r"morning|am\b", desc
            ):
                columns = ["afternoon_session"]
            elif re.search(r"morning|am\b", desc) and not re.search(
                r"afternoon|pm\b", desc
            ):
                columns = ["morning_session"]
            else:
                # No distinction or both mentioned — set both
                columns = ["morning_session", "afternoon_session"]

        age_band = _classify_age_band(age_text)
        if age_band not in by_band:
            by_band[age_band] = {}
        for col in columns:
            # Keep first amount per column per band (don't overwrite)
            if col not in by_band[age_band]:
                by_band[age_band][col] = amount

    return [{"age_band": band, **rates} for band, rates in by_band.items()]


def _parse_fees_raw(raw):
    """Parse fees_raw text into fee rows.

    Input: "£5.50 per hour, £49.50 per day"
    Returns: list of {age_band='all', column: amount} dicts.
    """
    if not raw:
        return []
    matches = _RE_PER_UNIT.findall(raw)
    if not matches:
        return []
    rates = {}
    for amount_str, unit in matches:
        unit_lower = unit.strip().lower()
        if unit_lower in ("hour", "hr"):
            column = "per_hour"
        elif unit_lower == "day":
            column = "per_day"
        elif unit_lower == "session":
            column = "per_session"
        elif "half" in unit_lower:
            column = "morning_session"
        else:
            continue
        if column not in rates:
            rates[column] = float(amount_str)
    if not rates:
        return []
    return [{"age_band": "all", **rates}]


def _parse_costs(raw):
    """Parse extra.costs text into fee rows.

    Handles both simple ("£5.00 per hour") and age-specific
    ("£39.00 per day for a child under 2 years") formats.
    Returns: list of {age_band, column: amount} dicts.
    """
    if not raw:
        return []

    # First try age-specific patterns
    age_matches = _RE_COST_AGE.findall(raw)
    if age_matches:
        by_band = {}
        for amount_str, unit, age_text in age_matches:
            unit_lower = unit.strip().lower()
            if unit_lower == "day":
                column = "per_day"
            elif unit_lower == "session":
                column = "per_session"
            elif unit_lower == "hour":
                column = "per_hour"
            else:
                continue
            age_band = _classify_age_band(age_text)
            if age_band not in by_band:
                by_band[age_band] = {}
            if column not in by_band[age_band]:
                by_band[age_band][column] = float(amount_str)

        # Also extract any general per-hour/per-session that isn't age-qualified
        general = _RE_PER_UNIT.findall(raw)
        for amount_str, unit in general:
            unit_lower = unit.strip().lower()
            if unit_lower in ("hour", "hr"):
                column = "per_hour"
            elif unit_lower == "session":
                column = "per_session"
            else:
                continue
            # Add to all bands that don't already have this column
            for band_rates in by_band.values():
                if column not in band_rates:
                    band_rates[column] = float(amount_str)

        return [{"age_band": band, **rates} for band, rates in by_band.items()]

    # Fall back to simple per-unit parsing
    return _parse_fees_raw(raw)


# ---------- Helpers ----------


def _flush_inserts(conn, batch):
    if not batch:
        return
    with conn.cursor() as cur:
        for row in batch:
            cur.execute(INSERT_SQL, row)
    conn.commit()


# ---------- Dagster asset ----------


@asset(group_name="draft", deps=["care_types"], automation_condition=PIPELINE_CONDITION)
def fee_rates(context: AssetExecutionContext, bsil_postgres: BsilPostgresResource):
    """Build draft.fee_rates — one row per (care_type, age_band) fee schedule.

    Parses fees from LA extract data in three formats:
    fees_structured, fees_raw, and extra.costs.
    """
    with bsil_postgres.get_connection() as conn:
        # Phase 1: Create table
        context.log.info("Phase 1: creating draft.fee_rates table")
        with conn.cursor() as cur:
            cur.execute(DROP_SQL)
            cur.execute(CREATE_SQL)
            for idx_sql in INDEX_SQL:
                cur.execute(idx_sql)
            conn.commit()

        # Phase 2: Load and parse fee data
        context.log.info("Phase 2: loading and parsing fee data from LA extracts")

        seen_care_type_ids = set()
        batch = []
        total_rows = 0
        source_counts = {
            "fees_structured": 0,
            "fees_raw": 0,
            "costs": 0,
        }

        with conn.cursor("fee_cursor", withhold=True) as cur:
            cur.execute(LOAD_FEE_EXTRACTS_SQL)
            for care_type_id, source_id, extracted_data in cur:
                # Only take the first LA extract per care_type
                if care_type_id in seen_care_type_ids:
                    continue

                if isinstance(extracted_data, str):
                    extracted_data = json.loads(extracted_data)

                extra = extracted_data.get("extra") or {}
                src_label = f"la_extract:{source_id}"

                # Try sources in priority order
                fee_rows = []
                source_key = None

                # 1. fees_structured (richest)
                fs = extracted_data.get("fees_structured")
                if fs:
                    fee_rows = _parse_fees_structured(fs)
                    if fee_rows:
                        source_key = "fees_structured"

                # 2. fees_raw
                if not fee_rows:
                    fr = extracted_data.get("fees_raw")
                    if fr:
                        fee_rows = _parse_fees_raw(fr)
                        if fee_rows:
                            source_key = "fees_raw"

                # 3. extra.costs
                if not fee_rows:
                    costs = extra.get("costs")
                    if costs:
                        fee_rows = _parse_costs(costs)
                        if fee_rows:
                            source_key = "costs"

                if not fee_rows:
                    continue

                seen_care_type_ids.add(care_type_id)
                source_counts[source_key] += 1

                for fr in fee_rows:
                    meta = {"field_sources": {"fee_data": f"{src_label}:{source_key}"}}
                    batch.append(
                        {
                            "care_type_id": care_type_id,
                            "age_band": fr["age_band"],
                            "morning_session": fr.get("morning_session"),
                            "afternoon_session": fr.get("afternoon_session"),
                            "full_day": fr.get("full_day"),
                            "per_session": fr.get("per_session"),
                            "per_hour": fr.get("per_hour"),
                            "per_day": fr.get("per_day"),
                            "metadata": json.dumps(meta),
                        }
                    )
                    total_rows += 1

                    if len(batch) >= BATCH_SIZE:
                        _flush_inserts(conn, batch)
                        batch.clear()

        _flush_inserts(conn, batch)

        context.log.info(
            f"Phase 2 complete: {total_rows} fee_rate rows "
            f"from {len(seen_care_type_ids)} care_types"
        )
        for src, cnt in source_counts.items():
            if cnt:
                context.log.info(f"  {src}: {cnt} care_types")

        # Phase 3: Tiney fee data (for providers not already covered by LA extracts)
        tiney_rows = 0
        with conn.cursor() as cur:
            cur.execute(
                "SELECT EXISTS ("
                "  SELECT 1 FROM information_schema.tables"
                "  WHERE table_schema = 'tiney' AND table_name = 'childminders'"
                ")"
            )
            has_tiney = cur.fetchone()[0]

        if has_tiney:
            context.log.info("Phase 3: loading fee data from Tiney childminders")
            batch = []

            with conn.cursor("tiney_fee_cursor", withhold=True) as cur:
                cur.execute(
                    """
                    SELECT ct.id AS care_type_id,
                           t.hourly_rate_gbp,
                           t.daily_rate_gbp,
                           t.additional_charges
                    FROM draft.care_types ct
                    JOIN draft.providers p ON p.provider_id = ct.provider_id
                    JOIN tiney.childminders t ON t.ofsted_urn = p.ofsted_urn
                    WHERE p.ofsted_urn LIKE 'TY%%'
                      AND (t.hourly_rate_gbp IS NOT NULL
                           OR t.daily_rate_gbp IS NOT NULL)
                      AND ct.id NOT IN (
                          SELECT care_type_id FROM draft.fee_rates
                      )
                    """
                )
                for care_type_id, hourly, daily, additional in cur:
                    meta = {
                        "field_sources": {"fee_data": "tiney:direct"},
                    }
                    if additional:
                        meta["additional_charges"] = additional
                    batch.append(
                        {
                            "care_type_id": care_type_id,
                            "age_band": "all",
                            "morning_session": None,
                            "afternoon_session": None,
                            "full_day": daily,
                            "per_session": None,
                            "per_hour": hourly,
                            "per_day": daily,
                            "metadata": json.dumps(meta),
                        }
                    )
                    tiney_rows += 1
                    total_rows += 1
                    seen_care_type_ids.add(care_type_id)

                    if len(batch) >= BATCH_SIZE:
                        _flush_inserts(conn, batch)
                        batch.clear()

            _flush_inserts(conn, batch)
            context.log.info(f"Phase 3 complete: {tiney_rows} Tiney fee_rate rows")
        else:
            context.log.info("Phase 3: tiney.childminders not found — skipping")

    return {
        "total_fee_rates": MetadataValue.int(total_rows),
        "care_types_with_fees": MetadataValue.int(len(seen_care_type_ids)),
        "tiney_fee_rates": MetadataValue.int(tiney_rows),
    }
