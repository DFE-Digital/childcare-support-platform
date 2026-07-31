import math

import pytest

from bsil_pipeline.spatial_index.ofsted_score import compute_ofsted_score


def _row(**kwargs):
    return kwargs


def test_no_framework():
    assert compute_ofsted_score(_row()) == -10.0


def test_legacy_outstanding_no_sub():
    assert (
        compute_ofsted_score(
            _row(ofsted_framework="legacy", ofsted_legacy_rating="Outstanding")
        )
        == 9.0
    )


def test_legacy_good_mixed_subs():
    score = compute_ofsted_score(
        _row(
            ofsted_framework="legacy",
            ofsted_legacy_rating="Good",
            ofsted_legacy_quality_of_education="Good",
            ofsted_legacy_behaviour_and_attitudes="Good",
            ofsted_legacy_personal_development="Good",
            ofsted_legacy_leadership_and_management="Outstanding",
            ofsted_legacy_early_years="Requires Improvement",
        )
    )
    # 6 + mean(0.67, 0.67, 0.67, 1.0, 0.33) = 6 + 0.668
    assert score == pytest.approx(6.668, abs=0.001)


def test_legacy_inadequate_all_inadequate():
    assert (
        compute_ofsted_score(
            _row(
                ofsted_framework="legacy",
                ofsted_legacy_rating="Inadequate",
                ofsted_legacy_quality_of_education="Inadequate",
                ofsted_legacy_behaviour_and_attitudes="Inadequate",
                ofsted_legacy_personal_development="Inadequate",
                ofsted_legacy_leadership_and_management="Inadequate",
            )
        )
        == 0.0
    )


def test_legacy_outstanding_all_outstanding():
    assert (
        compute_ofsted_score(
            _row(
                ofsted_framework="legacy",
                ofsted_legacy_rating="Outstanding",
                ofsted_legacy_quality_of_education="Outstanding",
                ofsted_legacy_behaviour_and_attitudes="Outstanding",
                ofsted_legacy_personal_development="Outstanding",
                ofsted_legacy_leadership_and_management="Outstanding",
                ofsted_legacy_early_years="Outstanding",
                ofsted_legacy_sixth_form="Outstanding",
            )
        )
        == 10.0
    )


def test_legacy_transition_all_outstanding():
    assert (
        compute_ofsted_score(
            _row(
                ofsted_framework="legacy_transition",
                ofsted_legacy_quality_of_education="Outstanding",
                ofsted_legacy_behaviour_and_attitudes="Outstanding",
                ofsted_legacy_personal_development="Outstanding",
                ofsted_legacy_leadership_and_management="Outstanding",
                ofsted_legacy_early_years="Outstanding",
            )
        )
        == 10.0
    )


def test_legacy_transition_mixed():
    score = compute_ofsted_score(
        _row(
            ofsted_framework="legacy_transition",
            ofsted_legacy_quality_of_education="Outstanding",
            ofsted_legacy_behaviour_and_attitudes="Good",
            ofsted_legacy_personal_development="Requires Improvement",
            ofsted_legacy_leadership_and_management="Inadequate",
        )
    )
    # mean(10, 6.67, 3.33, 0) = 5.0
    assert score == pytest.approx(5.0, abs=0.01)


def test_legacy_transition_no_subs():
    assert compute_ofsted_score(_row(ofsted_framework="legacy_transition")) == -10.0


def test_report_card_all_exceptional():
    assert (
        compute_ofsted_score(
            _row(
                ofsted_framework="report_card",
                ofsted_achievement="Exceptional",
                ofsted_curriculum_and_teaching="Exceptional",
                ofsted_behaviour_attitudes_routines="Exceptional",
                ofsted_childrens_welfare_wellbeing="Exceptional",
                ofsted_inclusion="Exceptional",
            )
        )
        == 10.0
    )


def test_report_card_all_expected():
    assert (
        compute_ofsted_score(
            _row(
                ofsted_framework="report_card",
                ofsted_achievement="Expected standard",
                ofsted_curriculum_and_teaching="Expected standard",
                ofsted_behaviour_attitudes_routines="Expected standard",
                ofsted_childrens_welfare_wellbeing="Expected standard",
                ofsted_inclusion="Expected standard",
            )
        )
        == 5.0
    )


def test_report_card_mixed():
    score = compute_ofsted_score(
        _row(
            ofsted_framework="report_card",
            ofsted_achievement="Exceptional",
            ofsted_curriculum_and_teaching="Strong standard",
            ofsted_behaviour_attitudes_routines="Expected standard",
            ofsted_childrens_welfare_wellbeing="Needs attention",
            ofsted_inclusion="Urgent improvement",
        )
    )
    # mean(10, 7.5, 5, 2.5, 0) = 5.0
    assert score == pytest.approx(5.0, abs=0.01)


def test_report_card_no_judgements():
    assert compute_ofsted_score(_row(ofsted_framework="report_card")) == -10.0


def test_penalty_safeguarding_false():
    score = compute_ofsted_score(
        _row(
            ofsted_framework="legacy",
            ofsted_legacy_rating="Good",
            ofsted_safeguarding_met=False,
        )
    )
    # 6.0 - 1.0 = 5.0
    assert score == 5.0


def test_penalty_multiple_false():
    score = compute_ofsted_score(
        _row(
            ofsted_framework="legacy",
            ofsted_legacy_rating="Good",
            ofsted_safeguarding_met=False,
            ofsted_ccr_met=False,
            ofsted_vcr_met=False,
            ofsted_oosc_met=False,
        )
    )
    # 6.0 - 4.0 = 2.0
    assert score == 2.0


def test_penalty_null_no_effect():
    score = compute_ofsted_score(
        _row(
            ofsted_framework="legacy",
            ofsted_legacy_rating="Good",
            ofsted_safeguarding_met=None,
        )
    )
    assert score == 6.0


def test_penalty_true_no_effect():
    score = compute_ofsted_score(
        _row(
            ofsted_framework="legacy",
            ofsted_legacy_rating="Good",
            ofsted_safeguarding_met=True,
        )
    )
    assert score == 6.0


def test_score_can_go_below_zero():
    score = compute_ofsted_score(
        _row(
            ofsted_framework="legacy",
            ofsted_legacy_rating="Inadequate",
            ofsted_safeguarding_met=False,
            ofsted_ccr_met=False,
            ofsted_vcr_met=False,
            ofsted_oosc_met=False,
        )
    )
    # 0.0 - 4.0 = -4.0
    assert score == -4.0


def test_unknown_framework():
    assert compute_ofsted_score(_row(ofsted_framework="future_thing")) == -10.0
