"""Tests for Tiney childminder loader and opening hours parser."""

import csv
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from bsil_pipeline.assets.tiney_childminders import (
    _parse_bool,
    _parse_date,
    _parse_decimal,
    _parse_int,
    _text_or_none,
)
from bsil_pipeline.assets.opening_hours import _parse_tiney_hours


# ---------- Type coercion helpers ----------


class TestParseDate:
    def test_valid_iso(self):
        assert _parse_date("2024-02-06") == date(2024, 2, 6)

    def test_valid_iso_with_whitespace(self):
        assert _parse_date("  2025-03-24  ") == date(2025, 3, 24)

    def test_empty_string(self):
        assert _parse_date("") is None

    def test_none(self):
        assert _parse_date(None) is None

    def test_whitespace_only(self):
        assert _parse_date("   ") is None

    def test_malformed(self):
        assert _parse_date("not-a-date") is None

    def test_partial(self):
        assert _parse_date("2024-02") is None


class TestParseBool:
    def test_true_lower(self):
        assert _parse_bool("true") is True

    def test_true_mixed_case(self):
        assert _parse_bool("True") is True

    def test_false_lower(self):
        assert _parse_bool("false") is False

    def test_false_mixed_case(self):
        assert _parse_bool("False") is False

    def test_empty_string(self):
        assert _parse_bool("") is None

    def test_none(self):
        assert _parse_bool(None) is None

    def test_whitespace(self):
        assert _parse_bool("  ") is None

    def test_true_with_whitespace(self):
        assert _parse_bool("  true  ") is True


class TestParseDecimal:
    def test_integer(self):
        assert _parse_decimal("8") == Decimal("8")

    def test_decimal(self):
        assert _parse_decimal("8.75") == Decimal("8.75")

    def test_large(self):
        assert _parse_decimal("100") == Decimal("100")

    def test_empty_string(self):
        assert _parse_decimal("") is None

    def test_none(self):
        assert _parse_decimal(None) is None

    def test_invalid(self):
        assert _parse_decimal("abc") is None

    def test_whitespace(self):
        assert _parse_decimal("  8.75  ") == Decimal("8.75")


class TestParseInt:
    def test_valid(self):
        assert _parse_int("52") == 52

    def test_empty_string(self):
        assert _parse_int("") is None

    def test_none(self):
        assert _parse_int(None) is None

    def test_invalid(self):
        assert _parse_int("abc") is None

    def test_whitespace(self):
        assert _parse_int("  52  ") == 52


class TestTextOrNone:
    def test_normal(self):
        assert _text_or_none("hello") == "hello"

    def test_strips_whitespace(self):
        assert _text_or_none("  hello  ") == "hello"

    def test_empty_string(self):
        assert _text_or_none("") is None

    def test_whitespace_only(self):
        assert _text_or_none("   ") is None

    def test_none(self):
        assert _text_or_none(None) is None


# ---------- Tiney opening hours parser ----------


class TestParseTineyHours:
    def test_full_week_same_time(self):
        raw = "Mon 08:00-18:00; Tue 08:00-18:00; Wed 08:00-18:00; Thu 08:00-18:00; Fri 08:00-18:00"
        result = _parse_tiney_hours(raw)
        assert result is not None
        assert len(result) == 1
        slot = result[0]
        assert slot["open"] == "08:00"
        assert slot["close"] == "18:00"
        assert slot["monday"] is True
        assert slot["tuesday"] is True
        assert slot["wednesday"] is True
        assert slot["thursday"] is True
        assert slot["friday"] is True
        assert slot["saturday"] is False
        assert slot["sunday"] is False

    def test_mixed_times_produces_multiple_slots(self):
        raw = "Mon 07:30-17:30; Tue 07:30-17:30; Wed 08:00-18:00"
        result = _parse_tiney_hours(raw)
        assert result is not None
        assert len(result) == 2
        slots_by_open = {s["open"]: s for s in result}
        assert "07:30" in slots_by_open
        assert "08:00" in slots_by_open
        assert slots_by_open["07:30"]["monday"] is True
        assert slots_by_open["07:30"]["tuesday"] is True
        assert slots_by_open["07:30"]["wednesday"] is False
        assert slots_by_open["08:00"]["wednesday"] is True

    def test_partial_week(self):
        raw = "Tue 08:00-17:30; Wed 08:00-17:30; Thu 08:00-17:30"
        result = _parse_tiney_hours(raw)
        assert result is not None
        assert len(result) == 1
        slot = result[0]
        assert slot["monday"] is False
        assert slot["tuesday"] is True
        assert slot["wednesday"] is True
        assert slot["thursday"] is True
        assert slot["friday"] is False

    def test_none_returns_none(self):
        assert _parse_tiney_hours(None) is None

    def test_empty_returns_none(self):
        assert _parse_tiney_hours("") is None

    def test_invalid_format_returns_none(self):
        assert _parse_tiney_hours("Monday to Friday") is None


# ---------- CSV round-trip ----------


_TINEY_CSV = "source_data/tiney-childminder-feed.csv"
# In Docker: /opt/dagster/app/source_data/; locally: repo_root/source_data/
_CONTAINER_PATH = Path(__file__).resolve().parent.parent / _TINEY_CSV
_LOCAL_PATH = Path(__file__).resolve().parent.parent.parent.parent / _TINEY_CSV
CSV_PATH = _CONTAINER_PATH if _CONTAINER_PATH.exists() else _LOCAL_PATH


@pytest.mark.skipif(not CSV_PATH.exists(), reason="source_data CSV not available")
class TestCsvRoundTrip:
    @pytest.fixture
    def parsed_rows(self):
        rows = []
        with open(CSV_PATH, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(
                    {
                        "ofsted_urn": _text_or_none(row.get("ofsted_urn")),
                        "provider_name": _text_or_none(row.get("provider_name")),
                        "postcode": _text_or_none(row.get("postcode")),
                        "tiney_registration_date": _parse_date(
                            row.get("tiney_registration_date")
                        ),
                        "funded_hours_accepted": _parse_bool(
                            row.get("funded_hours_accepted")
                        ),
                        "hourly_rate_gbp": _parse_decimal(row.get("hourly_rate_gbp")),
                        "daily_rate_gbp": _parse_decimal(row.get("daily_rate_gbp")),
                        "registered_places": _parse_int(row.get("registered_places")),
                        "operating_weeks_per_year": _parse_int(
                            row.get("operating_weeks_per_year")
                        ),
                        "tiney_lifecycle_status": _text_or_none(
                            row.get("tiney_lifecycle_status")
                        ),
                        "website_url": _text_or_none(row.get("website_url")),
                    }
                )
        return rows

    def test_row_count(self, parsed_rows):
        assert len(parsed_rows) == 8

    def test_first_row_urn(self, parsed_rows):
        assert parsed_rows[0]["ofsted_urn"] == "TY0224005"

    def test_first_row_date(self, parsed_rows):
        assert parsed_rows[0]["tiney_registration_date"] == date(2024, 2, 6)

    def test_first_row_rate(self, parsed_rows):
        assert parsed_rows[0]["hourly_rate_gbp"] == Decimal("8")
        assert parsed_rows[0]["daily_rate_gbp"] == Decimal("72")

    def test_funded_hours_is_bool(self, parsed_rows):
        assert parsed_rows[0]["funded_hours_accepted"] is True
        assert not isinstance(parsed_rows[0]["funded_hours_accepted"], str)

    def test_empty_registered_places(self, parsed_rows):
        assert parsed_rows[0]["registered_places"] is None

    def test_operating_weeks(self, parsed_rows):
        assert parsed_rows[0]["operating_weeks_per_year"] == 52

    def test_lifecycle_status_values(self, parsed_rows):
        statuses = {r["tiney_lifecycle_status"] for r in parsed_rows}
        assert statuses == {"open", "new"}

    def test_new_provider_is_last(self, parsed_rows):
        assert parsed_rows[-1]["tiney_lifecycle_status"] == "new"

    def test_website_url_stripped(self, parsed_rows):
        """_load_tiney strips query strings; verify the logic on real data."""
        raw = parsed_rows[0]["website_url"]
        assert "?" in raw, "expected UTM params in raw URL"
        stripped = raw.split("?")[0]
        assert stripped == "https://tiney.co/childminder/alex-currie"
        assert "utm_" not in stripped
