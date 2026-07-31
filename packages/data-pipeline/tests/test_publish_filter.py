"""Tests for the LA filter used in publish_providers."""

from bsil_pipeline.assets.publish import _la_filter, BETA_LA_CODES


class TestLaFilter:
    def test_default_no_tag(self):
        clause, params = _la_filter({})
        assert clause == "p.lad25cd LIKE 'E%%'"
        assert params == []

    def test_beta_true(self):
        clause, params = _la_filter({"BETA": "true"})
        assert "p.lad25cd IN" in clause
        assert params == sorted(BETA_LA_CODES)
        assert clause.count("%s") == len(BETA_LA_CODES)

    def test_beta_false(self):
        clause, params = _la_filter({"PUBLISH_BETA": "false"})
        assert clause == "p.lad25cd LIKE 'E%%'"
        assert params == []

    def test_beta_true_case_insensitive(self):
        clause, params = _la_filter({"BETA": "TRUE"})
        assert "p.lad25cd IN" in clause
        assert params == sorted(BETA_LA_CODES)
