import pytest

from bsil_pipeline.assets.provider_linkage import normalise_name


@pytest.mark.parametrize(
    "input_name,expected",
    [
        # Apostrophe stripping
        ("St Paul's Nursery", "saint pauls nursery"),
        ("Children's Centre", "childrens centre"),
        # Ampersand expansion
        ("Nursery & Children's Centre", "nursery and childrens centre"),
        ("A & B Childcare", "a and b childcare"),
        # Abbreviation expansion
        ("St Mary's", "saint marys"),
        ("C of E Primary", "church of england primary"),
        ("CofE Prim School", "church of england primary school"),
        ("R.C. Junior School", "roman catholic junior school"),
        # Leading "The" stripped
        ("The Willows Nursery", "willows nursery"),
        # Legal suffixes stripped
        ("Happy Days Ltd", "happy days"),
        ("Bright Start CIC", "bright start"),
        ("Clockhouse Preschool Playgroup CIO", "clockhouse preschool playgroup"),
        # Punctuation normalisation
        ("ABC (Main Site)", "abc main site"),
        ("North-East Nursery", "north east nursery"),
        # Whitespace normalisation
        ("  Extra   Spaces  ", "extra spaces"),
        # Empty/None handling
        (None, ""),
        ("", ""),
        # Combined real-world examples
        (
            "St Paul's Nursery School and Children's Centre",
            "saint pauls nursery school and childrens centre",
        ),
        (
            "St Pauls Nursery School & Children's Centre",
            "saint pauls nursery school and childrens centre",
        ),
    ],
)
def test_normalise_name(input_name, expected):
    assert normalise_name(input_name) == expected
