"""Unit tests for _clean_website in provider_details.py."""

import pytest

from bsil_pipeline.assets.provider_details import _clean_website


class TestBasicValidation:
    """Basic URL format validation."""

    def test_none_returns_none(self):
        assert _clean_website(None) is None

    def test_empty_returns_none(self):
        assert _clean_website("") is None

    def test_no_scheme_prepends_https(self):
        assert _clean_website("www.example.com") == "https://www.example.com"

    def test_bare_http_returns_none(self):
        assert _clean_website("http://") is None

    def test_bare_https_returns_none(self):
        assert _clean_website("https://") is None

    def test_valid_url_passes(self):
        assert (
            _clean_website("https://www.littlepioneers.co.uk")
            == "https://www.littlepioneers.co.uk"
        )

    def test_bare_domain_no_www_prepends_https(self):
        assert _clean_website("elmwoodprimary.co.uk") == "https://elmwoodprimary.co.uk"

    def test_bare_domain_with_path(self):
        assert (
            _clean_website("www.school.co.uk/about") == "https://www.school.co.uk/about"
        )

    def test_bare_subdomain_prepends_https(self):
        assert (
            _clean_website("paddock.wandsworth.sch.uk")
            == "https://paddock.wandsworth.sch.uk"
        )

    def test_postcode_returns_none(self):
        assert _clean_website("NW1 3EX") is None

    def test_county_name_returns_none(self):
        assert _clean_website("Essex") is None

    def test_trailing_dot_stripped(self):
        assert (
            _clean_website("www.lordstreet.derby.sch.uk.")
            == "https://www.lordstreet.derby.sch.uk"
        )

    def test_uppercase_scheme_accepted(self):
        assert (
            _clean_website("HTTPS://avanti.org.uk/avanticourt")
            == "HTTPS://avanti.org.uk/avanticourt"
        )

    def test_strips_whitespace(self):
        assert _clean_website("  https://example.co.uk  ") == "https://example.co.uk"

    def test_removes_internal_spaces(self):
        assert (
            _clean_website("https://childbasepartner ship.com")
            == "https://childbasepartnership.com"
        )


class TestSearchEngineRejection:
    """Search engines are always rejected regardless of path."""

    @pytest.mark.parametrize(
        "url",
        [
            "http://www.google.co.uk",
            "http://google.co.uk",
            "https://www.google.com",
            "https://google.com",
            "http://www.google.com/search?q=childcare",
            "http://www.yahoo.co.uk",
            "https://yahoo.com",
            "https://www.yahoo.com",
            "https://bing.com",
            "https://www.bing.com",
        ],
    )
    def test_rejected(self, url):
        assert _clean_website(url) is None

    def test_google_with_space_in_source(self):
        """The specific bug case: 'http://www. google.co.uk'."""
        assert _clean_website("http://www. google.co.uk") is None


class TestPlatformBareDomainRejection:
    """Platform homepages without a meaningful path are rejected."""

    @pytest.mark.parametrize(
        "url",
        [
            "https://www.facebook.com",
            "https://www.facebook.com/",
            "https://facebook.com",
            "https://m.facebook.com",
            "https://twitter.com",
            "https://www.twitter.com/",
            "https://x.com",
            "https://www.instagram.com",
            "https://www.instagram.com/",
            "https://www.youtube.com",
            "https://www.linkedin.com",
            "https://www.linkedin.com/",
            "https://nextdoor.co.uk",
            "https://www.nextdoor.co.uk/",
        ],
    )
    def test_bare_homepage_rejected(self, url):
        assert _clean_website(url) is None


class TestPlatformWithPathAccepted:
    """Platform URLs with a meaningful path are accepted."""

    @pytest.mark.parametrize(
        "url",
        [
            "https://www.facebook.com/BristolChildminders",
            "https://www.facebook.com/profile.php?id=123456",
            "https://m.facebook.com/groups/3216868375145403/",
            "https://www.instagram.com/happydaysnursery",
            "https://twitter.com/littlestars_cm",
            "https://www.youtube.com/@nursery-channel",
            "https://www.linkedin.com/company/bright-start",
            "https://nextdoor.co.uk/pages/rainbow-childminders",
        ],
    )
    def test_with_path_accepted(self, url):
        assert _clean_website(url) == url


class TestNonGenericDomainsUnaffected:
    """Normal provider websites are not affected by the filter."""

    @pytest.mark.parametrize(
        "url",
        [
            "https://www.happydaysnursery.co.uk",
            "http://brightstartchildcare.com",
            "https://www.littleacorns.org.uk/about",
            "https://childbase.com/nurseries/oxford",
        ],
    )
    def test_normal_provider_websites_pass(self, url):
        assert _clean_website(url) == url


class TestTrailingTextStripping:
    """Trailing non-URL text appended after the TLD is stripped."""

    def test_strips_appended_text(self):
        assert (
            _clean_website("https://example.co.ukOut of School Care")
            == "https://example.co.uk"
        )

    def test_preserves_query_string(self):
        assert (
            _clean_website("https://example.com/page.php?id=123")
            == "https://example.com/page.php?id=123"
        )

    def test_preserves_fragment(self):
        assert (
            _clean_website("https://example.co.uk#section")
            == "https://example.co.uk#section"
        )

    def test_preserves_path_with_query(self):
        assert (
            _clean_website("https://example.com/search?q=test&page=2")
            == "https://example.com/search?q=test&page=2"
        )
