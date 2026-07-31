"""Compute sort_cost_* columns from a care-type row and its fee_rate rows.

Replicates the frontend getHourlyRates() waterfall logic from
packages/app/src/utils/providerCosts.ts.
"""

import math
from datetime import time

_FULL_TIME_HOURS_PER_DAY = 10.0

_COST_BAND_COLUMNS = {
    "all": "sort_cost_all",
    "under2": "sort_cost_under2",
    "age2": "sort_cost_age2",
    "age3to4": "sort_cost_age3to4",
    "age2plus": "sort_cost_age2plus",
    "age5plus": "sort_cost_age5plus",
}

_ALL_COST_KEYS = list(_COST_BAND_COLUMNS.values())


def compute_cost_columns(
    ct_row: dict,
    fee_rows: list[dict],
) -> dict:
    """Return a dict of sort_cost_* keys with float or NaN values.

    ct_row: care-type row dict with keys like care_type, opening_hour_open,
            opening_hour_close, session_hours_morning, etc.
    fee_rows: list of fee_rate row dicts with age_band, per_hour, full_day, etc.
    """
    result = {k: float("nan") for k in _ALL_COST_KEYS}

    if not fee_rows:
        return result

    for fee in fee_rows:
        age_band = fee.get("age_band")
        col = _COST_BAND_COLUMNS.get(age_band)
        if col is None:
            continue

        if age_band == "all":
            rate = _flat_hourly_rate(fee, ct_row)
        else:
            rate = _banded_hourly_rate(fee, ct_row)

        if rate is not None:
            result[col] = rate

    return result


def _to_float(val) -> float | None:
    if val is None:
        return None
    return float(val)


def _hours_from_times(open_time, close_time) -> float | None:
    """Compute hours between two time values. Returns None if either is missing."""
    if open_time is None or close_time is None:
        return None

    if isinstance(open_time, time):
        oh, om = open_time.hour, open_time.minute
    else:
        parts = str(open_time)[:5].split(":")
        oh, om = int(parts[0]), int(parts[1])

    if isinstance(close_time, time):
        ch, cm = close_time.hour, close_time.minute
    else:
        parts = str(close_time)[:5].split(":")
        ch, cm = int(parts[0]), int(parts[1])

    return (ch + cm / 60.0) - (oh + om / 60.0)


def _estimate_session_hours(ct_row: dict) -> float | None:
    """Estimate session hours from opening hours, with care-type caps."""
    total = _hours_from_times(
        ct_row.get("opening_hour_open"),
        ct_row.get("opening_hour_close"),
    )
    if total is None or total <= 0:
        return None

    care_type = ct_row.get("care_type")
    if care_type == "breakfast_club":
        return min(total, 1.5)
    if care_type == "after_school_club":
        return min(total, 3.0)
    return total


def _estimate_day_hours(ct_row: dict) -> float:
    """Estimate day hours from opening hours, defaulting to 10h."""
    total = _hours_from_times(
        ct_row.get("opening_hour_open"),
        ct_row.get("opening_hour_close"),
    )
    if total is not None and total > 0:
        return total
    return _FULL_TIME_HOURS_PER_DAY


def _banded_hourly_rate(fee: dict, ct_row: dict) -> float | None:
    """Priority waterfall for banded (non-flat) fees."""
    # 1. per_hour
    per_hour = _to_float(fee.get("per_hour"))
    if per_hour is not None:
        return per_hour

    # 2. full_day / session_hours_full_day
    full_day = _to_float(fee.get("full_day"))
    sh_full = _to_float(ct_row.get("session_hours_full_day"))
    if full_day is not None and sh_full is not None and sh_full > 0:
        return full_day / sh_full

    # 3. morning_session / session_hours_morning
    morning = _to_float(fee.get("morning_session"))
    sh_morning = _to_float(ct_row.get("session_hours_morning"))
    if morning is not None and sh_morning is not None and sh_morning > 0:
        return morning / sh_morning

    # 4. afternoon_session / session_hours_afternoon
    afternoon = _to_float(fee.get("afternoon_session"))
    sh_afternoon = _to_float(ct_row.get("session_hours_afternoon"))
    if afternoon is not None and sh_afternoon is not None and sh_afternoon > 0:
        return afternoon / sh_afternoon

    # 5. per_session / estimated_session_hours
    per_session = _to_float(fee.get("per_session"))
    if per_session is not None:
        est_session = _estimate_session_hours(ct_row)
        if est_session is not None and est_session > 0:
            return per_session / est_session
        return None

    # 6. per_day / estimated_day_hours
    per_day = _to_float(fee.get("per_day"))
    if per_day is not None:
        day_hours = _estimate_day_hours(ct_row)
        if day_hours > 0:
            return per_day / day_hours

    return None


def _flat_hourly_rate(fee: dict, ct_row: dict) -> float | None:
    """For flat fees (age_band='all'): per_hour > per_session > per_day only."""
    per_hour = _to_float(fee.get("per_hour"))
    if per_hour is not None:
        return per_hour

    per_session = _to_float(fee.get("per_session"))
    if per_session is not None:
        est_session = _estimate_session_hours(ct_row)
        if est_session is not None and est_session > 0:
            return per_session / est_session
        return None

    per_day = _to_float(fee.get("per_day"))
    if per_day is not None:
        day_hours = _estimate_day_hours(ct_row)
        if day_hours > 0:
            return per_day / day_hours

    return None
