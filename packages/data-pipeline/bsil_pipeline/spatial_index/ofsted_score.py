"""Compute a 0–10 normalised inspection score from a provider row dict.

Covers Ofsted (legacy, legacy_transition, report_card) and CMA QA gradings.
"""

_LEGACY_MAIN = {
    "Inadequate": 0,
    "Requires Improvement": 3,
    "Good": 6,
    "Outstanding": 9,
}

_LEGACY_SUB = {
    "Inadequate": 0.0,
    "Requires Improvement": 0.33,
    "Good": 0.67,
    "Outstanding": 1.0,
}

_LEGACY_SUB_FIELDS = [
    "ofsted_legacy_quality_of_education",
    "ofsted_legacy_behaviour_and_attitudes",
    "ofsted_legacy_personal_development",
    "ofsted_legacy_leadership_and_management",
    "ofsted_legacy_early_years",
    "ofsted_legacy_sixth_form",
]

_LEGACY_TRANSITION_SUB = {
    "Inadequate": 0.0,
    "Requires Improvement": 3.33,
    "Good": 6.67,
    "Outstanding": 10.0,
}

_REPORT_CARD_JUDGEMENT_MAP = {
    "Urgent improvement": 0.0,
    "Needs attention": 2.5,
    "Expected standard": 5.0,
    "Strong standard": 7.5,
    "Exceptional": 10.0,
}

_REPORT_CARD_FIELDS = [
    "ofsted_achievement",
    "ofsted_curriculum_and_teaching",
    "ofsted_behaviour_attitudes_routines",
    "ofsted_childrens_welfare_wellbeing",
    "ofsted_attendance_and_behaviour",
    "ofsted_personal_development_wellbeing",
    "ofsted_inclusion",
    "ofsted_leadership_and_governance",
    "ofsted_early_years",
    "ofsted_sixth_form",
]

_PENALTY_FIELDS = [
    "ofsted_safeguarding_met",
    "ofsted_ccr_met",
    "ofsted_vcr_met",
    "ofsted_oosc_met",
]

_CMA_SCORE_MAP = {
    "outstanding": 9.0,
    "good": 6.0,
    "good-with-actions": 4.5,
    "support-required": 3.0,
    "support-plan": 1.5,
}


def compute_ofsted_score(row: dict) -> float:
    """Compute a normalised inspection score from a provider DB row.

    Returns a float in roughly the 0–10 range, or -10 if no data.
    Covers Ofsted frameworks and CMA QA gradings.
    Boolean penalties can push the score below 0.
    """
    framework = row.get("ofsted_framework")
    if not framework:
        cma_grading = row.get("cma_qa_grading")
        if cma_grading:
            return _CMA_SCORE_MAP.get(cma_grading, -10.0)
        return -10.0

    if framework == "legacy":
        score = _score_legacy(row)
    elif framework == "legacy_transition":
        score = _score_legacy_transition(row)
    elif framework == "report_card":
        score = _score_report_card(row)
    else:
        return -10.0

    score += _boolean_penalty(row)
    return score


def _score_legacy(row: dict) -> float:
    main_rating = row.get("ofsted_legacy_rating")
    main_score = _LEGACY_MAIN.get(main_rating)
    if main_score is None:
        return -10.0

    sub_values = []
    for field in _LEGACY_SUB_FIELDS:
        val = row.get(field)
        if val is not None and val in _LEGACY_SUB:
            sub_values.append(_LEGACY_SUB[val])

    if not sub_values:
        return float(main_score)

    return main_score + sum(sub_values) / len(sub_values)


def _score_legacy_transition(row: dict) -> float:
    sub_values = []
    for field in _LEGACY_SUB_FIELDS:
        val = row.get(field)
        if val is not None and val in _LEGACY_TRANSITION_SUB:
            sub_values.append(_LEGACY_TRANSITION_SUB[val])

    if not sub_values:
        return -10.0

    return sum(sub_values) / len(sub_values)


def _score_report_card(row: dict) -> float:
    values = []
    for field in _REPORT_CARD_FIELDS:
        val = row.get(field)
        if val is not None and val in _REPORT_CARD_JUDGEMENT_MAP:
            values.append(_REPORT_CARD_JUDGEMENT_MAP[val])

    if not values:
        return -10.0

    return sum(values) / len(values)


def _boolean_penalty(row: dict) -> float:
    penalty = 0.0
    for field in _PENALTY_FIELDS:
        val = row.get(field)
        if val is False:
            penalty -= 1.0
    return penalty
