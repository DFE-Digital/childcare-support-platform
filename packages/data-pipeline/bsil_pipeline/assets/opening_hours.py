"""Dagster asset building draft.opening_hours.

Parses opening hours from LA extract data and inserts one row per
(care_type_id, time_slot) into draft.opening_hours.
"""

import json
import re

from dagster import asset, AssetExecutionContext, MetadataValue

from bsil_pipeline.automation import PIPELINE_CONDITION
from bsil_pipeline.resources.postgres import BsilPostgresResource


BATCH_SIZE = 2000

CREATE_SQL = """
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

DROP_SQL = "DROP TABLE IF EXISTS draft.opening_hours CASCADE"

INDEX_SQL = "CREATE INDEX idx_draft_opening_hours_care_type_id ON draft.opening_hours(care_type_id)"

LOAD_LA_EXTRACTS_SQL = """
SELECT ps.provider_id, ps.source_id, e.extracted_data, e.classification
FROM draft.provider_sources ps
JOIN la.extract_results e
    ON e.lad25cd = split_part(ps.source_id, ':', 1)
   AND e.provider_id = substring(ps.source_id FROM position(':' IN ps.source_id) + 1)
WHERE ps.source = 'la_scrape'
ORDER BY ps.provider_id
"""

LOAD_CARE_TYPES_SQL = """
SELECT ct.id, ct.provider_id, ct.care_type
FROM draft.care_types ct
WHERE ct.provider_id = ANY(%(provider_ids)s)
ORDER BY ct.provider_id, ct.id
"""

INSERT_SQL = """
INSERT INTO draft.opening_hours (
    care_type_id, monday, tuesday, wednesday, thursday, friday,
    saturday, sunday, open, close
) VALUES (
    %(care_type_id)s, %(monday)s, %(tuesday)s, %(wednesday)s,
    %(thursday)s, %(friday)s, %(saturday)s, %(sunday)s,
    %(open)s, %(close)s
)
"""

# ---------- Parsers ----------

_RE_SESSION_TIME = re.compile(r"(\d{2}:\d{2})\s*[-–]\s*(\d{2}:\d{2})")
_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_RE_DAY = re.compile(
    r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
    re.IGNORECASE,
)
_DAY_ORDER = {d: i for i, d in enumerate(_DAYS)}
_RE_TABLE_TIME_24 = re.compile(r"(\d{1,2}[.:]\d{2})\s+(\d{1,2}[.:]\d{2})")
_RE_AMPM_TIME = re.compile(r"(\d{1,2}(?:[.:]\d{2})?)\s*(am|pm)", re.IGNORECASE)


def _days_from_text(text):
    """Return a set of lowercase day names mentioned in text."""
    return {m.group(1).lower() for m in _RE_DAY.finditer(text)}


def _days_in_range(start, end):
    """Return all days between start and end inclusive (by week order)."""
    i_start = _DAY_ORDER[start]
    i_end = _DAY_ORDER[end]
    if i_start <= i_end:
        return set(_DAYS[i_start : i_end + 1])
    return set()


def _make_opening_hours(open_t, close_t, days):
    return {
        "open": open_t,
        "close": close_t,
        "monday": "monday" in days,
        "tuesday": "tuesday" in days,
        "wednesday": "wednesday" in days,
        "thursday": "thursday" in days,
        "friday": "friday" in days,
        "saturday": "saturday" in days,
        "sunday": "sunday" in days,
    }


def parse_session_times(raw):
    """Parse daily session times into a list of opening hours dicts.

    Input: "Monday: 07:30 - 18:00 Tuesday: 08:00 - 17:30 Saturday: 09:00 - 13:00"
    Returns: list[dict] or None.

    Each distinct (open, close) time slot becomes a separate entry,
    with the days that share that slot grouped together.
    Falls back to a single Mon-Fri entry if no day names are found.
    """
    if not raw:
        return None

    time_matches = list(_RE_SESSION_TIME.finditer(raw))
    if not time_matches:
        return None

    day_matches = list(_RE_DAY.finditer(raw))

    if not day_matches:
        opens = [_maybe_pm(m.group(1)) for m in time_matches]
        closes = [_maybe_pm(m.group(2)) for m in time_matches]
        open_t = min(opens)
        close_t = max(closes)
        return [
            _make_opening_hours(
                open_t,
                close_t,
                {"monday", "tuesday", "wednesday", "thursday", "friday"},
            )
        ]

    slot_days: dict[tuple[str, str], set[str]] = {}
    for tm in time_matches:
        preceding = [dm for dm in day_matches if dm.start() < tm.start()]
        if not preceding:
            continue
        day = preceding[-1].group(1).lower()
        open_t = _maybe_pm(tm.group(1))
        close_t = _maybe_pm(tm.group(2))
        if close_t < open_t:
            close_h = int(close_t.split(":")[0])
            if close_h < 12:
                close_t = f"{close_h + 12:02d}:{close_t.split(':')[1]}"
        slot = (open_t, close_t)
        slot_days.setdefault(slot, set()).add(day)

    if not slot_days:
        return None

    return [
        _make_opening_hours(open_t, close_t, days)
        for (open_t, close_t), days in slot_days.items()
    ]


def _ampm_to_24(time_str, ampm):
    normalised = time_str.replace(".", ":")
    parts = normalised.split(":")
    hour = int(parts[0])
    minute = int(parts[1]) if len(parts) > 1 else 0
    if ampm.lower() == "pm" and hour < 12:
        hour += 12
    elif ampm.lower() == "am" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute:02d}"


def _normalise_dot_time(time_str):
    normalised = time_str.replace(".", ":")
    parts = normalised.split(":")
    hour = int(parts[0])
    minute = int(parts[1]) if len(parts) > 1 else 0
    return f"{hour:02d}:{minute:02d}"


def _maybe_pm(time_str: str) -> str:
    """Infer PM for bare times with no AM/PM marker.

    Hour < 6 is assumed PM — no childcare setting opens at 1–5 AM.
    Hour 6–12 is left unchanged (valid for morning breakfast clubs).
    """
    hour = int(time_str.split(":")[0])
    if hour < 6:
        return f"{hour + 12:02d}:{time_str.split(':')[1]}"
    return time_str


def parse_opening_hours_raw(raw):
    """Parse opening_hours_raw into a list of opening hours dicts.

    Handles formats:
    - "Monday: 07:30 - 18:00 ..." (delegates to parse_session_times)
    - "Opening Times DayOpening TimeClosing Time Monday to Friday 08:00 18:00"
    - "Opening Times DayOpening TimeClosing Time Monday 8.00 5.00 Tuesday ..."
    - "Opening Times DayOpening TimeClosing Time ... 7.15am 8.15pm"
    Returns: list[dict] or None.
    """
    if not raw:
        return None

    if _RE_SESSION_TIME.search(raw):
        return parse_session_times(raw)

    text = re.sub(
        r"Opening Times\s+DayOpening TimeClosing Time\s*"
        r"|Opening TimesDayOpening TimeClosing Time\s*"
        r"|Day\s+Opening Time\s+Closing Time\s*",
        "",
        raw,
        flags=re.IGNORECASE,
    ).strip()

    if not text or text.lower() == "not available":
        return None

    text = re.sub(r"(\d{2}:\d{2}):\d{2}", r"\1", text)

    # Split concatenated 8-digit time pairs (e.g. "07000850" → "0700 0850")
    text = re.sub(r"([01]\d[0-5]\d)([01]\d[0-5]\d)", r"\1 \2", text)

    # Insert spaces between concatenated day names and digits (e.g. "Monday0730")
    text = re.sub(r"([a-zA-Z])(\d)", r"\1 \2", text)
    text = re.sub(r"(\d)([a-zA-Z])", r"\1 \2", text)

    # Normalise 4-digit HHMM times (e.g. "0730", "1800") to "HH:MM"
    text = re.sub(r"\b([01]\d)([0-5]\d)\b", r"\1:\2", text)

    day_range_match = re.search(
        r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)"
        r"\s+to\s+"
        r"(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        text,
        re.IGNORECASE,
    )
    if day_range_match:
        days = _days_in_range(
            day_range_match.group(1).lower(), day_range_match.group(2).lower()
        )
    else:
        mentioned = _days_from_text(text)
        days = (
            mentioned
            if mentioned
            else {"monday", "tuesday", "wednesday", "thursday", "friday"}
        )

    open_str, close_str = None, None

    ampm_matches = _RE_AMPM_TIME.findall(text)
    if len(ampm_matches) >= 1:
        # Also collect bare HH:MM times not tagged with am/pm (e.g. "17:30")
        text_without_ampm = _RE_AMPM_TIME.sub("", text)
        bare_times = [
            _normalise_dot_time(m)
            for m in re.findall(r"\b(\d{1,2}[.:]\d{2})\b", text_without_ampm)
        ]
        times_24 = [_ampm_to_24(t, ap) for t, ap in ampm_matches] + bare_times
        if len(times_24) >= 2:
            open_str = min(times_24)
            close_str = max(times_24)

    if open_str is None:
        table_matches = _RE_TABLE_TIME_24.findall(text)
        opens = []
        closes = []
        for open_t, close_t in table_matches:
            o = _maybe_pm(_normalise_dot_time(open_t))
            c = _maybe_pm(_normalise_dot_time(close_t))
            if c < o:
                c_hour = int(c.split(":")[0])
                if c_hour < 12:
                    c = f"{c_hour + 12:02d}:{c.split(':')[1]}"
            if int(o.split(":")[0]) >= 24 or int(c.split(":")[0]) >= 24:
                continue
            opens.append(o)
            closes.append(c)
        if opens and closes:
            open_str = min(opens)
            close_str = max(closes)

    if open_str is None:
        return None

    return [_make_opening_hours(open_str, close_str, days)]


_TINEY_DAY_MAP = {
    "mon": "monday",
    "tue": "tuesday",
    "wed": "wednesday",
    "thu": "thursday",
    "fri": "friday",
    "sat": "saturday",
    "sun": "sunday",
}


def _parse_tiney_hours(raw):
    """Parse Tiney opening hours format into opening hours dicts.

    Input: "Mon 08:00-18:00; Tue 08:00-18:00; Wed 08:00-18:00"
    Groups days sharing the same time slot together.
    """
    if not raw:
        return None

    slot_days: dict[tuple[str, str], set[str]] = {}

    for segment in raw.split(";"):
        segment = segment.strip()
        if not segment:
            continue
        parts = segment.split(None, 1)
        if len(parts) < 2:
            continue
        day_abbr = parts[0].lower().rstrip(".")
        day = _TINEY_DAY_MAP.get(day_abbr)
        if not day:
            continue
        time_match = _RE_SESSION_TIME.search(parts[1])
        if not time_match:
            continue
        open_t = time_match.group(1)
        close_t = time_match.group(2)
        slot_days.setdefault((open_t, close_t), set()).add(day)

    if not slot_days:
        return None

    return [
        _make_opening_hours(open_t, close_t, days)
        for (open_t, close_t), days in slot_days.items()
    ]


# ---------- Helper ----------


def _flush(conn, batch):
    if not batch:
        return
    with conn.cursor() as cur:
        for row in batch:
            cur.execute(INSERT_SQL, row)
    conn.commit()


# ---------- Dagster asset ----------


@asset(group_name="draft", deps=["care_types"], automation_condition=PIPELINE_CONDITION)
def opening_hours(context: AssetExecutionContext, bsil_postgres: BsilPostgresResource):
    """Build draft.opening_hours from LA extract data.

    Parses opening times from LA extracts and inserts one row per
    (care_type_id, time_slot). When a provider has multiple LA nodes
    covering different care types, hours are matched per care type.
    """
    with bsil_postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(DROP_SQL)
            cur.execute(CREATE_SQL)
            cur.execute(INDEX_SQL)
            conn.commit()

        # Load LA extracts and parse opening hours per (provider, care_type)
        oh_by_care_type: dict[tuple[str, str], list[dict]] = {}
        with conn.cursor("oh_extract_cursor", withhold=True) as cur:
            cur.execute(LOAD_LA_EXTRACTS_SQL)
            for provider_id, source_id, extracted_data, classification in cur:
                if not extracted_data:
                    continue
                if isinstance(extracted_data, str):
                    extracted_data = json.loads(extracted_data)

                extra = extracted_data.get("extra") or {}

                opening_hours_parsed = None

                times_raw = extra.get("daily session times")
                if times_raw:
                    opening_hours_parsed = parse_session_times(times_raw)

                if opening_hours_parsed is None:
                    times_raw = extra.get("opening times/sessions")
                    if times_raw:
                        opening_hours_parsed = parse_session_times(times_raw)

                if opening_hours_parsed is None:
                    hours_raw = extracted_data.get("opening_hours_raw")
                    if hours_raw:
                        opening_hours_parsed = parse_opening_hours_raw(hours_raw)

                if opening_hours_parsed is not None:
                    for ct in classification or []:
                        key = (provider_id, ct)
                        if key not in oh_by_care_type:
                            oh_by_care_type[key] = opening_hours_parsed

        provider_ids = list({k[0] for k in oh_by_care_type})
        context.log.info(f"Parsed opening hours for {len(provider_ids)} providers")

        if not provider_ids:
            context.log.info("No opening hours to insert")
            return {"inserted": MetadataValue.int(0)}

        # Load care_type rows and insert opening hours
        batch = []
        inserted = 0
        with conn.cursor("oh_ct_cursor", withhold=True) as cur:
            cur.execute(LOAD_CARE_TYPES_SQL, {"provider_ids": provider_ids})
            for ct_id, provider_id, care_type in cur:
                oh = oh_by_care_type.get((provider_id, care_type))
                if not oh:
                    continue
                for slot in oh:
                    batch.append({"care_type_id": ct_id, **slot})
                if len(batch) >= BATCH_SIZE:
                    _flush(conn, batch)
                    inserted += len(batch)
                    batch.clear()

        _flush(conn, batch)
        inserted += len(batch)

        context.log.info(f"Inserted {inserted} opening hours rows from LA extracts")

        # Phase 2: Tiney opening hours
        tiney_inserted = 0
        with conn.cursor() as cur:
            cur.execute(
                "SELECT EXISTS ("
                "  SELECT 1 FROM information_schema.tables"
                "  WHERE table_schema = 'tiney' AND table_name = 'childminders'"
                ")"
            )
            has_tiney = cur.fetchone()[0]

        if has_tiney:
            context.log.info("Phase 2: loading Tiney opening hours")
            batch = []

            with conn.cursor("tiney_oh_cursor", withhold=True) as cur:
                cur.execute(
                    """
                    SELECT ct.id AS care_type_id, t.opening_hours
                    FROM draft.care_types ct
                    JOIN draft.providers p ON p.provider_id = ct.provider_id
                    JOIN tiney.childminders t ON t.ofsted_urn = p.ofsted_urn
                    WHERE p.ofsted_urn LIKE 'TY%%'
                      AND t.opening_hours IS NOT NULL
                      AND ct.id NOT IN (
                          SELECT care_type_id FROM draft.opening_hours
                      )
                    """
                )
                for care_type_id, raw_hours in cur:
                    parsed = _parse_tiney_hours(raw_hours)
                    if not parsed:
                        continue
                    for slot in parsed:
                        batch.append({"care_type_id": care_type_id, **slot})

                    if len(batch) >= BATCH_SIZE:
                        _flush(conn, batch)
                        tiney_inserted += len(batch)
                        batch.clear()

            _flush(conn, batch)
            tiney_inserted += len(batch)
            context.log.info(
                f"Phase 2 complete: {tiney_inserted} Tiney opening hours rows"
            )

        total_inserted = inserted + tiney_inserted
        context.log.info(f"Total opening hours rows: {total_inserted}")
        return {
            "inserted": MetadataValue.int(total_inserted),
            "tiney_inserted": MetadataValue.int(tiney_inserted),
        }
