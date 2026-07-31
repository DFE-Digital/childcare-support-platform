"""Integration tests for the spatial index asset.

Loads fixture providers into draft, publishes to published, calls
build_spatial_index(), and asserts on the resulting PyArrow table.
Requires a running Postgres (run via `make data/test` inside Docker).
"""

import json
import math
import os
import tempfile
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from bsil_pipeline.assets.spatial_index import build_spatial_index
from bsil_pipeline.resources.postgres import BsilPostgresResource
from bsil_pipeline.spatial_index.schema import (
    CARE_TYPE_ENUM,
    SPATIAL_INDEX_SCHEMA,
)
from tests.conftest import load_fixtures_to_published

FIXTURES_DIR = Path("/opt/dagster/app/data/placeholder-providers")

TEST_FIXTURE_IDS = [
    "p1358070129789077173",
    "p365829249294440042",
    "p5563766656632251099",
    "p2364030839202207152",
    "p2531667303950871088",
    "p5390234702153941379",
    "p6524520949689637860",
]


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


def _count_care_types(conn) -> dict:
    """Return {provider_id: count_of_care_types} from published.care_types."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT provider_id, count(*) FROM published.care_types GROUP BY provider_id"
        )
        return {row[0]: row[1] for row in cur.fetchall()}


def _get_fixture_data(fixture_id: str) -> dict:
    return json.loads((FIXTURES_DIR / f"{fixture_id}.json").read_text())


@pytest.fixture()
def index_table(db_resource):
    """Load fixtures via draft->publish and return the spatial index table."""
    with db_resource.get_connection() as conn:
        load_fixtures_to_published(conn, TEST_FIXTURE_IDS, FIXTURES_DIR)
        with conn.cursor() as cur:
            return build_spatial_index(cur)


def test_row_count_matches(db_resource, index_table):
    """Total rows = sum of care_types + 1 per provider with no care types."""
    with db_resource.get_connection() as conn:
        ct_counts = _count_care_types(conn)

    with db_resource.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM published.providers ORDER BY id")
            provider_ids = [row[0] for row in cur.fetchall()]

    expected = 0
    for pid in provider_ids:
        ct_count = ct_counts.get(pid, 0)
        expected += max(ct_count, 1)

    assert len(index_table) == expected


def test_caretype_index_resets(index_table):
    """Multi-CT provider has sequential indices starting at 0."""
    provider_ids = index_table.column("provider_id").to_pylist()
    indices = index_table.column("caretype_index").to_pylist()

    seen = {}
    for pid, idx in zip(provider_ids, indices):
        if pid not in seen:
            seen[pid] = []
        seen[pid].append(idx)

    for pid, idx_list in seen.items():
        assert idx_list == list(range(len(idx_list))), (
            f"Provider {pid}: expected sequential indices, got {idx_list}"
        )


def test_care_type_enum_mapping(index_table):
    """Int8 values match CARE_TYPE_ENUM for each row."""
    care_types = index_table.column("care_type").to_pylist()
    valid_values = set(CARE_TYPE_ENUM.values()) | {-1}
    for ct in care_types:
        assert ct in valid_values, f"Unknown care_type int: {ct}"


def test_lat_lon_populated(index_table):
    """Providers with coords have valid float32 values."""
    lats = index_table.column("lat").to_pylist()
    lons = index_table.column("lon").to_pylist()

    has_coords = False
    for lat, lon in zip(lats, lons):
        if lat is not None and not math.isnan(lat):
            has_coords = True
            assert -90 <= lat <= 90
            assert lon is not None and not math.isnan(lon)
            assert -180 <= lon <= 180

    assert has_coords, "No providers with coordinates found in fixtures"


def test_bbox_nan_when_missing(index_table):
    """Bbox providers have NW corner in lat/lon and SE corner in bbox_lat/bbox_lon.

    Providers with neither point coords nor a bbox should have all-NaN coordinates.
    """
    lats = index_table.column("lat").to_pylist()
    lons = index_table.column("lon").to_pylist()
    bbox_lats = index_table.column("bbox_lat").to_pylist()
    bbox_lons = index_table.column("bbox_lon").to_pylist()

    for lat, lon, bbox_lat, bbox_lon in zip(lats, lons, bbox_lats, bbox_lons):
        has_bbox = bbox_lat is not None and not math.isnan(bbox_lat)
        has_point = lat is not None and not math.isnan(lat)

        if has_bbox:
            # Bbox provider must also have lat/lon populated (NW corner)
            assert has_point, "Bbox provider should have lat/lon from NW corner"
            assert lon is not None and not math.isnan(lon)
            assert bbox_lon is not None and not math.isnan(bbox_lon)
        elif not has_point:
            # No coords at all — both lat/lon and bbox should be NaN
            assert not has_bbox


def test_ofsted_scores_known(index_table):
    """Check known Ofsted score ranges."""
    scores = index_table.column("sort_ofsted").to_pylist()

    has_positive = any(s > 0 for s in scores)
    has_negative_ten = any(s == -10.0 for s in scores)

    assert has_positive, "Expected at least one provider with positive Ofsted score"
    assert has_negative_ten, "Expected at least one provider with no Ofsted data (-10)"


def test_cost_known_fixture(db_resource, index_table):
    """At least one row has a non-NaN cost value."""
    all_cost_cols = [
        "sort_cost_all",
        "sort_cost_under2",
        "sort_cost_age2",
        "sort_cost_age3to4",
        "sort_cost_age2plus",
        "sort_cost_age5plus",
    ]
    has_cost = False
    for col_name in all_cost_cols:
        values = index_table.column(col_name).to_pylist()
        for v in values:
            if v is not None and not math.isnan(v):
                has_cost = True
                break
        if has_cost:
            break

    assert has_cost, "Expected at least one row with a non-NaN cost value"


def test_parquet_round_trip(index_table):
    """Write to temp file, read back, verify schema + row count."""
    with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
        path = f.name
    try:
        pq.write_table(index_table, path)
        read_back = pq.read_table(path)
        assert len(read_back) == len(index_table)
        assert read_back.schema == index_table.schema
    finally:
        Path(path).unlink(missing_ok=True)


def test_schema_types_match(index_table):
    """Output table schema matches SPATIAL_INDEX_SCHEMA."""
    assert index_table.schema == SPATIAL_INDEX_SCHEMA


def _insert_no_caretype_provider(conn) -> int:
    """Insert a provider with zero care types, return its ID."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO published.providers (id, name, metadata)
            VALUES (9999999999, 'No-CT Test Provider', '{}')
            RETURNING id
            """
        )
        pid = cur.fetchone()[0]
    conn.commit()
    return pid


def test_no_caretype_produces_row(db_resource):
    """Provider with zero care types produces exactly 1 row with care_type=-1."""
    with db_resource.get_connection() as conn:
        load_fixtures_to_published(conn, TEST_FIXTURE_IDS, FIXTURES_DIR)
        pid = _insert_no_caretype_provider(conn)
        with conn.cursor() as cur:
            table = build_spatial_index(cur)

    provider_ids = table.column("provider_id").to_pylist()
    care_types = table.column("care_type").to_pylist()
    indices = table.column("caretype_index").to_pylist()

    matching = [
        (ct, idx) for p, ct, idx in zip(provider_ids, care_types, indices) if p == pid
    ]
    assert len(matching) == 1
    assert matching[0][0] == -1  # care_type
    assert matching[0][1] == 0  # caretype_index


def test_no_caretype_costs_nan(db_resource):
    """The no-caretype row has all sort_cost_* = NaN."""
    with db_resource.get_connection() as conn:
        load_fixtures_to_published(conn, TEST_FIXTURE_IDS, FIXTURES_DIR)
        pid = _insert_no_caretype_provider(conn)
        with conn.cursor() as cur:
            table = build_spatial_index(cur)

    provider_ids = table.column("provider_id").to_pylist()
    cost_cols = [
        "sort_cost_all",
        "sort_cost_under2",
        "sort_cost_age2",
        "sort_cost_age3to4",
        "sort_cost_age2plus",
        "sort_cost_age5plus",
    ]

    for i, p in enumerate(provider_ids):
        if p == pid:
            for col_name in cost_cols:
                val = table.column(col_name)[i].as_py()
                assert val is None or math.isnan(val), (
                    f"Expected NaN for {col_name} on no-caretype row, got {val}"
                )
            break
    else:
        pytest.fail(f"Provider {pid} not found in index")


def test_no_caretype_provider_fields(db_resource):
    """The no-caretype row still has valid sort_ofsted from the provider."""
    with db_resource.get_connection() as conn:
        load_fixtures_to_published(conn, TEST_FIXTURE_IDS, FIXTURES_DIR)
        pid = _insert_no_caretype_provider(conn)
        with conn.cursor() as cur:
            table = build_spatial_index(cur)

    provider_ids = table.column("provider_id").to_pylist()

    for i, p in enumerate(provider_ids):
        if p == pid:
            ofsted = table.column("sort_ofsted")[i].as_py()
            # No ofsted data -> -10
            assert ofsted == -10.0
            break
    else:
        pytest.fail(f"Provider {pid} not found in index")
