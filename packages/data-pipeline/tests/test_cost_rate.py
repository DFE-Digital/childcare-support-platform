import math
from datetime import time

import pytest

from bsil_pipeline.spatial_index.cost_rate import compute_cost_columns


def _ct(**kwargs):
    """Build a minimal care-type row dict."""
    return kwargs


def _fee(**kwargs):
    """Build a fee_rate row dict."""
    return kwargs


def test_per_hour_direct():
    result = compute_cost_columns(_ct(), [_fee(age_band="under2", per_hour=8.50)])
    assert result["sort_cost_under2"] == pytest.approx(8.50)


def test_full_day_over_session_hours():
    result = compute_cost_columns(
        _ct(session_hours_full_day=10),
        [_fee(age_band="under2", full_day=95)],
    )
    assert result["sort_cost_under2"] == pytest.approx(9.50)


def test_morning_over_session_hours():
    result = compute_cost_columns(
        _ct(session_hours_morning=5),
        [_fee(age_band="under2", morning_session=55)],
    )
    assert result["sort_cost_under2"] == pytest.approx(11.0)


def test_afternoon_over_session_hours():
    result = compute_cost_columns(
        _ct(session_hours_afternoon=4),
        [_fee(age_band="under2", afternoon_session=48)],
    )
    assert result["sort_cost_under2"] == pytest.approx(12.0)


def test_per_session_with_hours():
    result = compute_cost_columns(
        _ct(opening_hour_open=time(15, 15), opening_hour_close=time(17, 45)),
        [_fee(age_band="under2", per_session=15.50)],
    )
    # 17.75 - 15.25 = 2.5 hours; 15.50 / 2.5 = 6.2
    assert result["sort_cost_under2"] == pytest.approx(6.20)


def test_breakfast_club_capped():
    result = compute_cost_columns(
        _ct(
            care_type="breakfast_club",
            opening_hour_open=time(7, 30),
            opening_hour_close=time(9, 0),
        ),
        [_fee(age_band="under2", per_session=6)],
    )
    # 1.5h total, capped at 1.5h; 6 / 1.5 = 4.0
    assert result["sort_cost_under2"] == pytest.approx(4.0)


def test_after_school_capped():
    result = compute_cost_columns(
        _ct(
            care_type="after_school_club",
            opening_hour_open=time(15, 0),
            opening_hour_close=time(18, 30),
        ),
        [_fee(age_band="under2", per_session=15)],
    )
    # 3.5h total, capped at 3.0h; 15 / 3.0 = 5.0
    assert result["sort_cost_under2"] == pytest.approx(5.0)


def test_per_day_with_hours():
    result = compute_cost_columns(
        _ct(opening_hour_open=time(7, 30), opening_hour_close=time(18, 0)),
        [_fee(age_band="under2", per_day=80)],
    )
    # 10.5 hours; 80 / 10.5 = 7.619
    assert result["sort_cost_under2"] == pytest.approx(7.619, abs=0.001)


def test_per_day_no_hours():
    result = compute_cost_columns(_ct(), [_fee(age_band="under2", per_day=80)])
    # default 10h; 80 / 10 = 8.0
    assert result["sort_cost_under2"] == pytest.approx(8.0)


def test_per_session_no_hours():
    result = compute_cost_columns(_ct(), [_fee(age_band="under2", per_session=15)])
    assert math.isnan(result["sort_cost_under2"])


def test_no_fees():
    result = compute_cost_columns(_ct(), [])
    for key in result:
        assert math.isnan(result[key])


def test_flat_per_hour():
    result = compute_cost_columns(_ct(), [_fee(age_band="all", per_hour=7.0)])
    assert result["sort_cost_all"] == pytest.approx(7.0)


def test_flat_per_session():
    result = compute_cost_columns(
        _ct(opening_hour_open=time(8, 0), opening_hour_close=time(18, 0)),
        [_fee(age_band="all", per_session=10)],
    )
    # 10h session; 10 / 10 = 1.0
    assert result["sort_cost_all"] == pytest.approx(1.0)


def test_flat_no_propagation():
    result = compute_cost_columns(_ct(), [_fee(age_band="all", per_hour=7.0)])
    assert result["sort_cost_all"] == pytest.approx(7.0)
    assert math.isnan(result["sort_cost_under2"])
    assert math.isnan(result["sort_cost_age2"])
    assert math.isnan(result["sort_cost_age3to4"])
    assert math.isnan(result["sort_cost_age2plus"])
    assert math.isnan(result["sort_cost_age5plus"])


def test_banded_multiple():
    result = compute_cost_columns(
        _ct(),
        [
            _fee(age_band="under2", per_hour=8.50),
            _fee(age_band="age2plus", per_hour=7.50),
        ],
    )
    assert result["sort_cost_under2"] == pytest.approx(8.50)
    assert result["sort_cost_age2plus"] == pytest.approx(7.50)
    assert math.isnan(result["sort_cost_all"])
    assert math.isnan(result["sort_cost_age2"])
    assert math.isnan(result["sort_cost_age3to4"])


def test_priority_per_hour_over_full_day():
    result = compute_cost_columns(
        _ct(session_hours_full_day=10),
        [_fee(age_band="under2", per_hour=8, full_day=90)],
    )
    assert result["sort_cost_under2"] == pytest.approx(8.0)


def test_priority_full_day_over_morning():
    result = compute_cost_columns(
        _ct(session_hours_full_day=10, session_hours_morning=5),
        [_fee(age_band="under2", full_day=90, morning_session=50)],
    )
    assert result["sort_cost_under2"] == pytest.approx(9.0)


def test_zero_session_hours_falls_through():
    result = compute_cost_columns(
        _ct(
            session_hours_morning=0,
            opening_hour_open=time(8, 0),
            opening_hour_close=time(18, 0),
        ),
        [_fee(age_band="under2", morning_session=50, per_session=20)],
    )
    # morning falls through (0 hours), per_session: 20 / 10h = 2.0
    assert result["sort_cost_under2"] == pytest.approx(2.0)


def test_free_session_returns_zero():
    result = compute_cost_columns(
        _ct(opening_hour_open=time(8, 0), opening_hour_close=time(8, 45)),
        [_fee(age_band="under2", per_session=0)],
    )
    assert result["sort_cost_under2"] == pytest.approx(0.0)
