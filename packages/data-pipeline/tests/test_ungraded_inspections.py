"""Tests for ungraded inspection rating derivation."""

import pytest

from bsil_pipeline.assets.provider_details import _derive_rating_from_ungraded


class TestDeriveRatingFromUngraded:
    @pytest.mark.parametrize(
        "outcome,expected",
        [
            ("School remains Good", "Good"),
            ("School remains Good (Improving) - S5 Next", "Good"),
            ("School remains Good (Concerns) - S5 Next", "Good"),
            ("School remains Outstanding", "Outstanding"),
            ("School remains Outstanding (Concerns) - S5 Next", "Outstanding"),
        ],
    )
    def test_derivable_outcomes(self, outcome, expected):
        assert _derive_rating_from_ungraded(outcome) == expected

    def test_case_insensitive(self):
        assert _derive_rating_from_ungraded("SCHOOL REMAINS GOOD") == "Good"
        assert (
            _derive_rating_from_ungraded("school remains outstanding") == "Outstanding"
        )

    def test_strips_whitespace(self):
        assert _derive_rating_from_ungraded("  School remains Good  ") == "Good"

    @pytest.mark.parametrize(
        "outcome",
        [
            "Standards maintained",
            "Improved significantly",
            "Some aspects not as strong",
            "NULL",
            "Unknown value",
        ],
    )
    def test_non_derivable_outcomes(self, outcome):
        assert _derive_rating_from_ungraded(outcome) is None

    def test_empty_string(self):
        assert _derive_rating_from_ungraded("") is None

    def test_none(self):
        assert _derive_rating_from_ungraded(None) is None
