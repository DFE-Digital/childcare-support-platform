"""Tests for cost estimate loading and export — pure function tests, no DB needed."""

import pytest

from bsil_pipeline.assets.cost_estimates import _parse_row
from bsil_pipeline.assets.export_costs import _build_la_json


# ---------------------------------------------------------------------------
# _parse_row
# ---------------------------------------------------------------------------


class TestParseRow:
    def test_full_data(self):
        row = {
            "la_code": "E06000005",
            "la_name": "Darlington",
            "region": "North East",
            "age_group": "under_2",
            "prov_group": "CM",
            "hourly_lower": "4.61",
            "hourly_mean": "5.81",
            "hourly_weighted_mean": "5.85",
            "hourly_upper": "7.17",
            "meal_lower": "0.78",
            "meal_mean": "5.43",
            "meal_upper": "10.08",
            "funding_rate": "11.46",
            "data_level": "region",
            "n_la": "4",
            "n_region": "103",
            "n_national": "2707",
        }
        parsed = _parse_row(row)
        assert parsed["la_code"] == "E06000005"
        assert parsed["la_name"] == "Darlington"
        assert parsed["hourly_mean"] == pytest.approx(5.81)
        assert parsed["meal_mean"] == pytest.approx(5.43)
        assert parsed["funding_rate"] == pytest.approx(11.46)
        assert parsed["n_la"] == 4
        assert parsed["n_region"] == 103
        assert parsed["data_level"] == "region"

    def test_insufficient_data(self):
        row = {
            "la_code": "E06000005",
            "la_name": "Darlington",
            "region": "North East",
            "age_group": "under_2",
            "prov_group": "SBP",
            "hourly_lower": "",
            "hourly_mean": "",
            "hourly_weighted_mean": "",
            "hourly_upper": "",
            "meal_lower": "0.78",
            "meal_mean": "5.43",
            "meal_upper": "10.08",
            "funding_rate": "11.46",
            "data_level": "insufficient",
            "n_la": "0",
            "n_region": "2",
            "n_national": "29",
        }
        parsed = _parse_row(row)
        assert parsed["hourly_mean"] is None
        assert parsed["hourly_lower"] is None
        assert parsed["hourly_upper"] is None
        assert parsed["meal_mean"] == pytest.approx(5.43)
        assert parsed["data_level"] == "insufficient"
        assert parsed["n_la"] == 0


# ---------------------------------------------------------------------------
# _build_la_json
# ---------------------------------------------------------------------------


def _row(
    la_code="E06000005",
    la_name="Darlington",
    region="North East",
    age_group="under_2",
    prov_group="CM",
    data_level="la",
    hourly_lower=4.61,
    hourly_mean=5.81,
    hourly_upper=7.17,
    hourly_weighted_mean=5.85,
    meal_lower=0.78,
    meal_mean=5.43,
    meal_upper=10.08,
    funding_rate=11.46,
    **kw,
):
    return {
        "la_code": la_code,
        "la_name": la_name,
        "region": region,
        "age_group": age_group,
        "prov_group": prov_group,
        "hourly_lower": hourly_lower,
        "hourly_mean": hourly_mean,
        "hourly_weighted_mean": hourly_weighted_mean,
        "hourly_upper": hourly_upper,
        "meal_lower": meal_lower,
        "meal_mean": meal_mean,
        "meal_upper": meal_upper,
        "funding_rate": funding_rate,
        "data_level": data_level,
        "n_la": kw.get("n_la", 10),
        "n_region": kw.get("n_region", 100),
        "n_national": kw.get("n_national", 2000),
    }


def _full_la_rows(**overrides):
    """Generate a full set of 9 rows (3 ages x 3 prov types) for one LA."""
    base = {
        "la_code": "E06000005",
        "la_name": "Darlington",
        "region": "North East",
    }
    base.update(overrides)

    ages = [
        ("under_2", 11.46),
        ("2yr", 8.44),
        ("3_4yr", 6.01),
    ]
    provs = [
        ("CM", "la", 4.61, 5.81, 7.17),
        ("GBP", "region", 6.15, 8.29, 11.27),
        ("SBP", "region", 3.59, 5.67, 6.61),
    ]

    rows = []
    for age, fund in ages:
        for prov, level, lo, mean, hi in provs:
            rows.append(
                _row(
                    age_group=age,
                    prov_group=prov,
                    data_level=level,
                    hourly_lower=lo,
                    hourly_mean=mean,
                    hourly_upper=hi,
                    funding_rate=fund,
                    **base,
                )
            )
    return rows


class TestBuildLaJson:
    def test_top_level_structure(self):
        result = _build_la_json("E06000005", _full_la_rows(), "2026-04")
        assert result["laName"] == "Darlington"
        assert result["regionName"] == "North East"
        assert result["nationName"] == "England"
        assert result["lastUpdated"] == "2026-04"
        assert "averageCosts" in result
        assert "governmentFundingRates" in result

    def test_care_types_present(self):
        """All 3 mapped care types should appear."""
        result = _build_la_json("E06000005", _full_la_rows(), "2026-04")
        assert "childminder" in result["averageCosts"]
        assert "private_nursery" in result["averageCosts"]
        assert "school_based_nursery" in result["averageCosts"]

    def test_fee_data_correct(self):
        result = _build_la_json("E06000005", _full_la_rows(), "2026-04")
        pn = result["averageCosts"]["private_nursery"]
        assert pn["fees"]["under2"]["perHour"]["mean"] == pytest.approx(8.29)
        assert pn["fees"]["under2"]["perHour"]["lower"] == pytest.approx(6.15)
        assert pn["fees"]["under2"]["perHour"]["upper"] == pytest.approx(11.27)
        assert pn["fees"]["under2"]["perHour"]["area"] == "region"

    def test_all_three_age_keys_for_childminder(self):
        result = _build_la_json("E06000005", _full_la_rows(), "2026-04")
        cm = result["averageCosts"]["childminder"]
        assert "under2" in cm["fees"]
        assert "age2" in cm["fees"]
        assert "age3to4" in cm["fees"]

    def test_insufficient_fee_omitted(self):
        """Rows with data_level 'insufficient' should not produce fee entries."""
        rows = _full_la_rows()
        # Make all SBP rows insufficient
        for r in rows:
            if r["prov_group"] == "SBP":
                r["data_level"] = "insufficient"
                r["hourly_lower"] = None
                r["hourly_mean"] = None
                r["hourly_upper"] = None
        result = _build_la_json("E06000005", rows, "2026-04")
        assert "school_based_nursery" not in result["averageCosts"]

    def test_partial_insufficient(self):
        """If only one age is insufficient, the care type should still appear."""
        rows = _full_la_rows()
        for r in rows:
            if r["prov_group"] == "SBP" and r["age_group"] == "under_2":
                r["data_level"] = "insufficient"
                r["hourly_lower"] = None
                r["hourly_mean"] = None
                r["hourly_upper"] = None
        result = _build_la_json("E06000005", rows, "2026-04")
        sbn = result["averageCosts"]["school_based_nursery"]
        assert "under2" not in sbn["fees"]
        assert "age2" in sbn["fees"]
        assert "age3to4" in sbn["fees"]

    def test_government_funding_rates(self):
        result = _build_la_json("E06000005", _full_la_rows(), "2026-04")
        gfr = result["governmentFundingRates"]
        assert gfr["under2"]["perHour"] == pytest.approx(11.46)
        assert gfr["age2"]["perHour"] == pytest.approx(8.44)
        assert gfr["age3to4"]["perHour"] == pytest.approx(6.01)

    def test_static_session_hours(self):
        result = _build_la_json("E06000005", _full_la_rows(), "2026-04")

        pn = result["averageCosts"]["private_nursery"]
        assert pn["sessionHours"] == {"morning": 5, "afternoon": 5, "fullDay": 10}
        assert pn["operatingWeeksPerYear"] == 50

        sbn = result["averageCosts"]["school_based_nursery"]
        assert sbn["sessionHours"] == {"morning": 3.25, "afternoon": 3.25}
        assert sbn["operatingWeeksPerYear"] == 38

        cm = result["averageCosts"]["childminder"]
        assert "sessionHours" not in cm
        assert "operatingWeeksPerYear" not in cm

    def test_meals_additional_charge(self):
        result = _build_la_json("E06000005", _full_la_rows(), "2026-04")
        pn = result["averageCosts"]["private_nursery"]
        assert len(pn["additionalCharges"]) == 1
        meal = pn["additionalCharges"][0]
        assert meal["item"] == "Meals"
        assert meal["cost"]["mean"] == pytest.approx(5.43)
        assert meal["cost"]["lower"] == pytest.approx(0.78)
        assert meal["cost"]["upper"] == pytest.approx(10.08)
        assert meal["cost"]["area"] == "la"
        assert meal["unit"] == "per day"

    def test_meal_description_per_care_type(self):
        result = _build_la_json("E06000005", _full_la_rows(), "2026-04")
        pn_desc = result["averageCosts"]["private_nursery"]["additionalCharges"][0][
            "description"
        ]
        cm_desc = result["averageCosts"]["childminder"]["additionalCharges"][0][
            "description"
        ]
        assert pn_desc == "Lunch and snacks"
        assert cm_desc == "Lunch and snacks if attending over lunchtime"

    def test_fis_url_present(self):
        result = _build_la_json(
            "E06000005",
            _full_la_rows(),
            "2026-04",
            fis_url="https://fis.example.gov.uk/",
        )
        assert result["familyInformationServices"] == [
            {"url": "https://fis.example.gov.uk/"}
        ]

    def test_fis_url_absent(self):
        result = _build_la_json("E06000005", _full_la_rows(), "2026-04")
        assert "familyInformationServices" not in result

    def test_fis_url_none(self):
        result = _build_la_json("E06000005", _full_la_rows(), "2026-04", fis_url=None)
        assert "familyInformationServices" not in result

    def test_la_name_comma_inversion(self):
        rows = _full_la_rows(la_name="Bristol, City of")
        result = _build_la_json("E06000023", rows, "2026-04")
        assert result["laName"] == "City of Bristol"

    def test_la_name_no_comma(self):
        rows = _full_la_rows(la_name="Darlington")
        result = _build_la_json("E06000005", rows, "2026-04")
        assert result["laName"] == "Darlington"

    def test_show_beta_warning_outside_beta(self):
        result = _build_la_json(
            "E09000001", _full_la_rows(la_code="E09000001"), "2026-04", beta_mode=True
        )
        assert result["showBetaWarning"] is True

    def test_no_beta_warning_inside_beta(self):
        result = _build_la_json(
            "E06000023", _full_la_rows(la_code="E06000023"), "2026-04", beta_mode=True
        )
        assert result["showBetaWarning"] is False

    def test_no_beta_warning_when_not_beta_mode(self):
        result = _build_la_json(
            "E09000001", _full_la_rows(la_code="E09000001"), "2026-04", beta_mode=False
        )
        assert result["showBetaWarning"] is False
