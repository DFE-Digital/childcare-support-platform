import pytest

from bsil_pipeline.assets.providers import Offering, _resolve_field


def _make_offering(
    source: str, care_type: str, provider_name: str | None = None, **kwargs
):
    defaults = dict(
        id=1,
        source=source,
        source_id="test-1",
        lad25cd=None,
        care_type=care_type,
        provider_name=provider_name,
        postcode=None,
        ofsted_urn=None,
        school_urn=None,
        phase_type=None,
        ofsted_provider_type=None,
        ofsted_provider_subtype=None,
    )
    defaults.update(kwargs)
    return Offering(**defaults)


class TestResolveField:
    def test_la_scrape_wins_for_single_care_type(self):
        offerings = [
            _make_offering("la_scrape", "after_school_club", provider_name="LA Name"),
            _make_offering(
                "ofsted", "after_school_club", provider_name="Ofsted Name", id=2
            ),
        ]
        priority = ["la_scrape", "ofsted", "free_breakfast"]
        value, source = _resolve_field(offerings, "provider_name", priority)
        assert value == "LA Name"
        assert source == "la_scrape"

    def test_ofsted_wins_when_priority_reversed(self):
        offerings = [
            _make_offering("la_scrape", "after_school_club", provider_name="LA Name"),
            _make_offering(
                "ofsted", "after_school_club", provider_name="Ofsted Name", id=2
            ),
        ]
        priority = ["ofsted", "la_scrape", "free_breakfast"]
        value, source = _resolve_field(offerings, "provider_name", priority)
        assert value == "Ofsted Name"
        assert source == "ofsted"

    def test_falls_through_when_higher_priority_is_none(self):
        offerings = [
            _make_offering("la_scrape", "after_school_club", provider_name=None),
            _make_offering(
                "ofsted", "after_school_club", provider_name="Ofsted Name", id=2
            ),
        ]
        priority = ["la_scrape", "ofsted", "free_breakfast"]
        value, source = _resolve_field(offerings, "provider_name", priority)
        assert value == "Ofsted Name"
        assert source == "ofsted"

    def test_returns_none_when_no_source_has_value(self):
        offerings = [
            _make_offering("la_scrape", "after_school_club", provider_name=None),
            _make_offering("ofsted", "after_school_club", provider_name=None, id=2),
        ]
        priority = ["la_scrape", "ofsted", "free_breakfast"]
        value, source = _resolve_field(offerings, "provider_name", priority)
        assert value is None
        assert source is None


class TestMultiCareTypeNamePriority:
    """Verify that multi-care-type non-school providers prefer Ofsted name."""

    def test_multi_care_type_uses_ofsted_priority(self):
        offerings = [
            _make_offering(
                "la_scrape",
                "after_school_club",
                provider_name="LA After School Club Name",
            ),
            _make_offering(
                "la_scrape",
                "holiday_club",
                provider_name="LA Holiday Club Name",
                id=2,
                source_id="test-2",
            ),
            _make_offering(
                "ofsted",
                "after_school_club",
                provider_name="Ofsted Operator Name",
                id=3,
                source_id="test-3",
            ),
        ]
        care_types = sorted({o.care_type for o in offerings if o.care_type})
        assert len(care_types) > 1

        # Simulate the logic from providers.py
        has_school = False
        priority = ["la_scrape", "ofsted", "free_breakfast"]
        name_priority = priority
        if not has_school and len(care_types) > 1:
            name_priority = ["ofsted", "la_scrape", "free_breakfast"]

        value, source = _resolve_field(offerings, "provider_name", name_priority)
        assert value == "Ofsted Operator Name"
        assert source == "ofsted"

    def test_single_care_type_keeps_la_priority(self):
        offerings = [
            _make_offering("la_scrape", "after_school_club", provider_name="LA Name"),
            _make_offering(
                "ofsted", "after_school_club", provider_name="Ofsted Name", id=2
            ),
        ]
        care_types = sorted({o.care_type for o in offerings if o.care_type})
        assert len(care_types) == 1

        has_school = False
        priority = ["la_scrape", "ofsted", "free_breakfast"]
        name_priority = priority
        if not has_school and len(care_types) > 1:
            name_priority = ["ofsted", "la_scrape", "free_breakfast"]

        value, source = _resolve_field(offerings, "provider_name", name_priority)
        assert value == "LA Name"
        assert source == "la_scrape"

    def test_school_provider_ignores_multi_care_type_override(self):
        offerings = [
            _make_offering(
                "school_census", "breakfast_club", provider_name="School Census Name"
            ),
            _make_offering(
                "la_scrape", "after_school_club", provider_name="LA Name", id=2
            ),
            _make_offering(
                "ofsted", "after_school_club", provider_name="Ofsted Name", id=3
            ),
        ]
        care_types = sorted({o.care_type for o in offerings if o.care_type})
        assert len(care_types) > 1

        has_school = True
        priority = ["school_census", "la_scrape", "ofsted", "free_breakfast"]
        name_priority = priority
        if not has_school and len(care_types) > 1:
            name_priority = ["ofsted", "la_scrape", "free_breakfast"]

        value, source = _resolve_field(offerings, "provider_name", name_priority)
        assert value == "School Census Name"
        assert source == "school_census"
