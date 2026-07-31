"""Round-trip test for providerStats (total, bboxOnly, insufficient).

Loads fixture providers into published, inserts synthetic providers that
exercise the stats query conditions, then runs the exact query from
export_costs.py and verifies the counts match expected values.

Regression guard for the latitude IS NULL condition in bboxOnly — previously
used postcode IS NULL which under-counted bbox-only providers that had a
postcode but failed geocoding.
"""

import os
from pathlib import Path

import pytest

from bsil_pipeline.resources.postgres import BsilPostgresResource
from tests.conftest import load_fixtures_to_published

FIXTURES_DIR = Path("/opt/dagster/app/data/placeholder-providers")

TEST_FIXTURE_IDS = sorted(p.stem for p in FIXTURES_DIR.glob("*.json"))

STATS_QUERY = (
    "SELECT p.lad25cd, ct.care_type,"
    "       COUNT(DISTINCT p.id)"
    "           FILTER (WHERE NOT p.is_insufficient) AS total,"
    "       COUNT(DISTINCT p.id)"
    "           FILTER (WHERE p.is_insufficient) AS insufficient,"
    "       COUNT(DISTINCT p.id)"
    "           FILTER (WHERE NOT p.is_insufficient"
    "                        AND p.bbox_geo_type IS NOT NULL"
    "                        AND p.latitude IS NULL) AS bbox_only"
    " FROM published.providers p"
    " JOIN published.care_types ct ON ct.provider_id = p.id"
    " GROUP BY p.lad25cd, ct.care_type"
)


def _get_resource() -> BsilPostgresResource:
    return BsilPostgresResource(
        host=os.environ.get("POSTGRES_HOST", "postgres"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        user=os.environ.get("POSTGRES_USER", "bsil"),
        password=os.environ.get("POSTGRES_PASSWORD", "bsil_local"),
        dbname=os.environ.get("POSTGRES_DB", "bsil"),
    )


@pytest.fixture()
def db_resource():
    return _get_resource()


# --- Synthetic provider IDs (chosen to avoid fixture collision) ---
BBOX_PROVIDER_ID = 8000000001
BBOX_WITH_POSTCODE_ID = 8000000002
INSUFFICIENT_ID = 8000000003
POINT_PROVIDER_ID = 8000000004

TEST_LAD = "E99000001"


def _insert_synthetic_providers(conn):
    """Insert providers covering the stats edge cases into published."""
    with conn.cursor() as cur:
        # 1. Bbox provider with NO latitude, NO postcode
        cur.execute(
            "INSERT INTO published.providers"
            " (id, name, lad25cd, bbox_geo_type, bbox_geo_code,"
            "  latitude, longitude, postcode, metadata)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                BBOX_PROVIDER_ID,
                "Bbox No Coords",
                TEST_LAD,
                "local_authority",
                TEST_LAD,
                None,
                None,
                None,
                "{}",
            ),
        )
        cur.execute(
            "INSERT INTO published.care_types (provider_id, care_type) VALUES (%s, %s)",
            (BBOX_PROVIDER_ID, "childminder"),
        )

        # 2. Bbox provider WITH postcode but NO latitude (the bug case)
        cur.execute(
            "INSERT INTO published.providers"
            " (id, name, lad25cd, bbox_geo_type, bbox_geo_code,"
            "  latitude, longitude, postcode, metadata)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                BBOX_WITH_POSTCODE_ID,
                "Bbox With Postcode",
                TEST_LAD,
                "local_authority",
                TEST_LAD,
                None,
                None,
                "BS5 0RG",
                "{}",
            ),
        )
        cur.execute(
            "INSERT INTO published.care_types (provider_id, care_type) VALUES (%s, %s)",
            (BBOX_WITH_POSTCODE_ID, "childminder"),
        )

        # 3. Insufficient provider (has bbox but is_insufficient=true)
        cur.execute(
            "INSERT INTO published.providers"
            " (id, name, lad25cd, bbox_geo_type, bbox_geo_code,"
            "  latitude, longitude, is_insufficient, metadata)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                INSUFFICIENT_ID,
                "Insufficient Provider",
                TEST_LAD,
                "local_authority",
                TEST_LAD,
                None,
                None,
                True,
                "{}",
            ),
        )
        cur.execute(
            "INSERT INTO published.care_types (provider_id, care_type) VALUES (%s, %s)",
            (INSUFFICIENT_ID, "childminder"),
        )

        # 4. Normal point provider (has lat/lon, not insufficient)
        cur.execute(
            "INSERT INTO published.providers"
            " (id, name, lad25cd, latitude, longitude, postcode, metadata)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (
                POINT_PROVIDER_ID,
                "Normal Point Provider",
                TEST_LAD,
                51.45,
                -2.59,
                "BS1 1AA",
                "{}",
            ),
        )
        cur.execute(
            "INSERT INTO published.care_types (provider_id, care_type) VALUES (%s, %s)",
            (POINT_PROVIDER_ID, "childminder"),
        )

    conn.commit()


def test_stats_query_bbox_only(db_resource):
    """bboxOnly counts providers with bbox_geo_type but no latitude."""
    with db_resource.get_connection() as conn:
        load_fixtures_to_published(conn, TEST_FIXTURE_IDS, FIXTURES_DIR)
        _insert_synthetic_providers(conn)

        with conn.cursor() as cur:
            cur.execute(STATS_QUERY)
            rows = cur.fetchall()

    stats = {
        (lad, ct): (total, insufficient, bbox_only)
        for lad, ct, total, insufficient, bbox_only in rows
    }

    # Our synthetic LAD should have:
    #   total=3 (BBOX_PROVIDER_ID + BBOX_WITH_POSTCODE_ID + POINT_PROVIDER_ID)
    #   insufficient=1 (INSUFFICIENT_ID)
    #   bbox_only=2 (BBOX_PROVIDER_ID + BBOX_WITH_POSTCODE_ID)
    key = (TEST_LAD, "childminder")
    assert key in stats, f"Expected stats for {key}, got: {list(stats.keys())}"
    total, insufficient, bbox_only = stats[key]

    assert total == 3, f"Expected total=3, got {total}"
    assert insufficient == 1, f"Expected insufficient=1, got {insufficient}"
    assert bbox_only == 2, f"Expected bbox_only=2, got {bbox_only}"


def test_stats_bbox_only_excludes_insufficient(db_resource):
    """Insufficient providers with bbox should NOT count in bboxOnly."""
    with db_resource.get_connection() as conn:
        load_fixtures_to_published(conn, TEST_FIXTURE_IDS, FIXTURES_DIR)
        _insert_synthetic_providers(conn)

        with conn.cursor() as cur:
            cur.execute(STATS_QUERY)
            rows = cur.fetchall()

    stats = {
        (lad, ct): (total, insufficient, bbox_only)
        for lad, ct, total, insufficient, bbox_only in rows
    }
    key = (TEST_LAD, "childminder")
    _, _, bbox_only = stats[key]

    # INSUFFICIENT_ID has bbox_geo_type and no latitude, but is_insufficient=true
    # so it must NOT appear in bbox_only
    assert bbox_only == 2, (
        f"bbox_only should exclude insufficient providers; got {bbox_only}"
    )


def test_stats_bbox_only_requires_null_latitude(db_resource):
    """Providers with bbox_geo_type AND latitude should NOT count in bboxOnly."""
    with db_resource.get_connection() as conn:
        load_fixtures_to_published(conn, TEST_FIXTURE_IDS, FIXTURES_DIR)
        _insert_synthetic_providers(conn)

        # Add a provider with bbox AND latitude (geocoded successfully)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO published.providers"
                " (id, name, lad25cd, bbox_geo_type, bbox_geo_code,"
                "  latitude, longitude, metadata)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    8000000005,
                    "Bbox With Coords",
                    TEST_LAD,
                    "local_authority",
                    TEST_LAD,
                    51.45,
                    -2.59,
                    "{}",
                ),
            )
            cur.execute(
                "INSERT INTO published.care_types (provider_id, care_type)"
                " VALUES (%s, %s)",
                (8000000005, "childminder"),
            )
        conn.commit()

        with conn.cursor() as cur:
            cur.execute(STATS_QUERY)
            rows = cur.fetchall()

    stats = {
        (lad, ct): (total, insufficient, bbox_only)
        for lad, ct, total, insufficient, bbox_only in rows
    }
    key = (TEST_LAD, "childminder")
    total, _, bbox_only = stats[key]

    # Provider 8000000005 has bbox but also has latitude → not bbox_only
    assert total == 4, f"Expected total=4, got {total}"
    assert bbox_only == 2, (
        f"bbox_only should not include providers with latitude; got {bbox_only}"
    )


def test_stats_postcode_does_not_affect_bbox_only(db_resource):
    """Having a postcode but no latitude still counts as bbox_only.

    This is the specific regression: previously the condition was
    'postcode IS NULL' which missed providers like BBOX_WITH_POSTCODE_ID.
    """
    with db_resource.get_connection() as conn:
        load_fixtures_to_published(conn, TEST_FIXTURE_IDS, FIXTURES_DIR)
        _insert_synthetic_providers(conn)

        with conn.cursor() as cur:
            cur.execute(STATS_QUERY)
            rows = cur.fetchall()

    stats = {
        (lad, ct): (total, insufficient, bbox_only)
        for lad, ct, total, insufficient, bbox_only in rows
    }
    key = (TEST_LAD, "childminder")
    _, _, bbox_only = stats[key]

    # BBOX_WITH_POSTCODE_ID has postcode='BS5 0RG' but latitude=NULL
    # It must still count as bbox_only
    assert bbox_only == 2, (
        f"Provider with postcode but no latitude should be bbox_only; got {bbox_only}"
    )
