"""Unit tests for Phase 3 age enrichment logic in care_types.

Covers the fallthrough from unparseable age_range text to direct numeric
fields, and the flipped-age heuristic (min > max → min is months).
"""

import pytest

from bsil_pipeline.assets.care_types import parse_age_range


class TestParseAgeRange:
    """parse_age_range returns (None, None, None) for cost-band-style text."""

    @pytest.mark.parametrize(
        "text",
        [
            "Under two, Two, Three, Four",
            "Baby, Toddler, Pre-school",
            "2, 3, 4",
        ],
    )
    def test_unparseable_age_bands(self, text):
        assert parse_age_range(text) == (None, None, None)

    def test_valid_range(self):
        assert parse_age_range("From 2 years to 5 years") == (None, 2, 5)

    def test_from_months(self):
        min_mo, min_yr, max_yr = parse_age_range("From 3 months to 5 years")
        assert min_mo == 3
        assert max_yr == 5


class TestFlippedAgeHeuristic:
    """When eligible_min_years > eligible_max_years, min is treated as months.

    This tests the logic inline in care_types Phase 3, not a standalone
    function — so we replicate the logic here for unit coverage.
    """

    def _apply_flipped_logic(self, raw_min, raw_max):
        """Replicate the Phase 3 numeric fallback logic."""
        try:
            min_yr = int(raw_min) if raw_min is not None else None
        except (ValueError, TypeError):
            min_yr = None
        try:
            max_yr = int(raw_max) if raw_max is not None else None
        except (ValueError, TypeError):
            max_yr = None

        fields = {}
        if min_yr is not None and max_yr is not None and min_yr > max_yr:
            fields["eligible_min_months"] = min_yr
            min_yr = None
        if min_yr is not None and min_yr > 0:
            fields["eligible_min_years"] = min_yr
        if max_yr is not None and max_yr > 0:
            fields["eligible_max_years"] = max_yr
        return fields

    def test_flipped_8_5(self):
        """min=8, max=5 → min_months=8, max_years=5 (Becket Hall case)."""
        result = self._apply_flipped_logic("8", "5")
        assert result == {"eligible_min_months": 8, "eligible_max_years": 5}

    def test_flipped_3_2(self):
        """min=3, max=2 → min_months=3, max_years=2."""
        result = self._apply_flipped_logic("3", "2")
        assert result == {"eligible_min_months": 3, "eligible_max_years": 2}

    def test_normal_range_not_flipped(self):
        """min=2, max=5 → normal, no month conversion."""
        result = self._apply_flipped_logic("2", "5")
        assert result == {"eligible_min_years": 2, "eligible_max_years": 5}

    def test_none_values(self):
        """None inputs produce empty fields."""
        result = self._apply_flipped_logic(None, None)
        assert result == {}

    def test_zero_min(self):
        """min=0 is not stored (only >0 stored)."""
        result = self._apply_flipped_logic("0", "5")
        assert result == {"eligible_max_years": 5}
