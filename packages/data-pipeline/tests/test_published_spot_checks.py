"""Spot-checks against the published schema for known-bad data patterns.

These query the live published schema (main bsil database) and serve as
regression guards after pipeline runs. They do NOT run as part of
`make data/test` (which uses bsil_test).

Run via:
    make data/spot-check
"""

import os

import psycopg
import pytest

pytestmark = pytest.mark.spot_check


@pytest.fixture(scope="module")
def conn():
    db_conn = psycopg.connect(
        host=os.environ.get("POSTGRES_HOST", "postgres"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        user=os.environ.get("POSTGRES_USER", "bsil"),
        password=os.environ.get("POSTGRES_PASSWORD", "bsil_local"),
        dbname=os.environ.get("POSTGRES_DB", "bsil"),
    )
    with db_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM published.providers")
        count = cur.fetchone()[0]
    if count == 0:
        db_conn.close()
        pytest.skip("published.providers is empty")
    yield db_conn
    db_conn.close()


class TestVcrOnlyExcluded:
    """VCR-only providers without recognisable names must not be published."""

    def test_ikea_not_published(self, conn):
        """URN 2700518 — VCR only, Sessional day care."""
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM published.providers WHERE name ILIKE '%%ikea%%'"
            )
            assert cur.fetchall() == []

    def test_kumon_not_published(self, conn):
        """URN 2793603 — VCR only, Full day care."""
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM published.providers WHERE name = 'Kumon Bradley Stoke'"
            )
            assert cur.fetchall() == []


class TestVcrOnlyNameMatchIncluded:
    """VCR-only providers with recognisable names ARE published with care_type."""

    def test_holiday_club_published(self, conn):
        """URN EY559552 — VCR only, 'All-Aboard Watersports Centre Holiday Club'."""
        with conn.cursor() as cur:
            cur.execute(
                "SELECT p.id FROM published.providers p"
                " WHERE p.name = 'All-Aboard Watersports Centre Holiday Club'"
            )
            row = cur.fetchone()
            assert row is not None, "Provider not found in published"
            cur.execute(
                "SELECT care_type FROM published.care_types WHERE provider_id = %s",
                (row[0],),
            )
            care_types = [r[0] for r in cur.fetchall()]
            assert "holiday_club" in care_types


class TestCcrVcrOoscIncluded:
    """CCR-VCR Out-of-school providers are published with after_school_club."""

    def test_bapp_odd_down(self, conn):
        """URN EY244968 — CCR-VCR, Out-of-school day care."""
        with conn.cursor() as cur:
            cur.execute(
                "SELECT p.id FROM published.providers p"
                " WHERE p.name = 'BAPP - Odd Down'"
            )
            row = cur.fetchone()
            assert row is not None, "Provider not found in published"
            cur.execute(
                "SELECT care_type FROM published.care_types WHERE provider_id = %s",
                (row[0],),
            )
            care_types = [r[0] for r in cur.fetchall()]
            assert "after_school_club" in care_types


class TestCcrVcrNameMatchIncluded:
    """CCR-VCR non-OOSC providers with name match get matched care_type."""

    def test_forest_school(self, conn):
        """URN 2699665 — CCR-VCR, Full day care, 'Back2Basics Forest School'."""
        with conn.cursor() as cur:
            cur.execute(
                "SELECT p.id FROM published.providers p"
                " WHERE p.name = 'Back2Basics Forest School'"
            )
            row = cur.fetchone()
            assert row is not None, "Provider not found in published"
            cur.execute(
                "SELECT care_type FROM published.care_types WHERE provider_id = %s",
                (row[0],),
            )
            care_types = [r[0] for r in cur.fetchall()]
            assert "holiday_club" in care_types


class TestCcrVcrUnclassifiedIncluded:
    """CCR-VCR providers with no name match are published with no care_type."""

    def test_made_forever_scheme(self, conn):
        """URN EY560180 — CCR-VCR, Sessional day care, no name match."""
        with conn.cursor() as cur:
            cur.execute(
                "SELECT p.id FROM published.providers p"
                " WHERE p.name = 'Made Forever Scheme'"
            )
            row = cur.fetchone()
            assert row is not None, "Provider not found in published"
            cur.execute(
                "SELECT care_type FROM published.care_types WHERE provider_id = %s",
                (row[0],),
            )
            care_types = cur.fetchall()
            assert care_types == [], "Expected no care_types for unclassified CCR-VCR"


class TestSecondarySchoolsExcluded:
    """Secondary schools must not appear in published providers."""

    def test_no_secondary_schools(self, conn):
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name FROM published.providers"
                " WHERE institution_type = 'school_secondary'"
            )
            rows = cur.fetchall()
        assert rows == [], "Secondary schools found in published: " + ", ".join(
            name for _, name in rows
        )


class TestBristolPlatformSeparation:
    """Bristol has two FIS directories; both should contribute to published."""

    def test_becket_hall_has_age_data(self, conn):
        """Becket Hall (ofsted:EY402789) should have age range from liquidlogic."""
        with conn.cursor() as cur:
            cur.execute(
                "SELECT p.id, ct.eligible_min_months, ct.eligible_max_years"
                " FROM published.providers p"
                " JOIN published.care_types ct ON ct.provider_id = p.id"
                " WHERE p.name = 'Becket Hall Day Nursery'"
            )
            row = cur.fetchone()
        assert row is not None, "Becket Hall not found in published"
        _, min_months, max_years = row
        assert min_months is not None or max_years is not None, (
            "Becket Hall should have age data from liquidlogic extract"
        )

    def test_bristol_has_liquidlogic_providers(self, conn):
        """Bristol should have providers sourced from liquidlogic (not clobbered)."""
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM published.providers"
                " WHERE lad25cd = 'E06000023'"
                " AND metadata->>'sources' LIKE '%%la_scrape%%'"
            )
            count = cur.fetchone()[0]
        assert count > 50, f"Expected >50 Bristol LA-sourced providers, found {count}"


class TestNamePostcodeDedup:
    """Providers with same postcode + near-identical names should be merged."""

    def test_st_pauls_nursery_merged(self, conn):
        """ofsted:EY364275 and school:108901 (BS2 9JF) should be one provider."""
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name FROM published.providers"
                " WHERE name ILIKE '%%st paul%%nursery%%'"
                " AND postcode = 'BS2 9JF'"
            )
            rows = cur.fetchall()
        assert len(rows) <= 1, (
            f"Expected 1 merged provider, found {len(rows)}: "
            + ", ".join(f"{name} (id={id})" for id, name in rows)
        )
