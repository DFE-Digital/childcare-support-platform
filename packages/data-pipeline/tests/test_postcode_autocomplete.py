"""Tests for postcode_autocomplete asset — helper functions + integration."""

import csv
import json
import math
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from dagster import build_asset_context

from bsil_pipeline.assets.postcode_autocomplete import (
    _outward_code,
    _inward_code,
    _expand_bboxes,
    _MAX_EXPANSION_RADIUS,
    postcode_autocomplete,
)


# ---------------------------------------------------------------------------
# 1a. _outward_code unit tests
# ---------------------------------------------------------------------------


class TestOutwardCode:
    def test_with_space(self):
        assert _outward_code("SW1A 1AA") == "SW1A"

    def test_no_space(self):
        assert _outward_code("SW1A1AA") == "SW1A"

    def test_short(self):
        assert _outward_code("S1 1AA") == "S1"

    def test_lowercase(self):
        assert _outward_code("sw1a 1aa") == "SW1A"

    def test_extra_whitespace(self):
        assert _outward_code("  SW1A  1AA  ") == "SW1A"

    def test_too_short(self):
        assert _outward_code("AB") is None

    def test_empty(self):
        assert _outward_code("") is None

    def test_single_char(self):
        assert _outward_code("A") is None


# ---------------------------------------------------------------------------
# 1b. _inward_code unit tests
# ---------------------------------------------------------------------------


class TestInwardCode:
    def test_with_space(self):
        assert _inward_code("SW1A 1AA") == "1AA"

    def test_no_space(self):
        assert _inward_code("SW1A1AA") == "1AA"

    def test_short(self):
        assert _inward_code("S1 1AA") == "1AA"

    def test_lowercase(self):
        assert _inward_code("sw1a 1aa") == "1AA"

    def test_extra_whitespace(self):
        assert _inward_code("  SW1A  1AA  ") == "1AA"

    def test_too_short(self):
        assert _inward_code("AB") is None

    def test_empty(self):
        assert _inward_code("") is None

    def test_single_char(self):
        assert _inward_code("A") is None


# ---------------------------------------------------------------------------
# 1c. Asset integration tests (tmp_path, no Docker/DB needed)
# ---------------------------------------------------------------------------


@pytest.fixture()
def autocomplete_env(tmp_path):
    """Set up temp dirs with a tiny bbox_lookup.sqlite and ONSPD CSV."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    source_dir = tmp_path / "source_data"
    onspd_dir = source_dir / "ONSPD_TEST" / "Data"
    onspd_dir.mkdir(parents=True)
    export_dir = tmp_path / "exported_data" / "app"

    # --- bbox_lookup.sqlite with 2 postcodes ---
    db_path = data_dir / "bbox_lookup.sqlite"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE postcode_bbox "
        "(geo_code TEXT PRIMARY KEY, bbox_west REAL, bbox_south REAL, bbox_east REAL, bbox_north REAL)"
    )
    conn.execute(
        "INSERT INTO postcode_bbox VALUES (?, ?, ?, ?, ?)",
        ("SW1A 1AA", -0.1416, 51.4993, -0.1393, 51.5013),
    )
    conn.execute(
        "INSERT INTO postcode_bbox VALUES (?, ?, ?, ?, ?)",
        ("OX2 0AA", -1.2680, 51.7561, -1.2650, 51.7581),
    )
    conn.commit()
    conn.close()

    # --- ONSPD CSV with 6 rows ---
    csv_path = onspd_dir / "ONSPD_TEST_UK.csv"
    rows = [
        # In SQLite — should use polygon bbox (London borough, no county)
        {
            "pcds": "SW1A 1AA",
            "lat": "51.5010",
            "long": "-0.1416",
            "gridind": "1",
            "lad25cd": "E09000033",
            "cty25cd": "E99999999",
            "lsoa21cd": "E01004736",
        },
        # Two-tier area: district E07 + county E10
        {
            "pcds": "OX2 0AA",
            "lat": "51.7571",
            "long": "-1.2665",
            "gridind": "1",
            "lad25cd": "E07000178",
            "cty25cd": "E10000025",
            "lsoa21cd": "E01028522",
        },
        # NOT in SQLite — should use point bbox fallback (Scottish, no county)
        {
            "pcds": "AB1 0AA",
            "lat": "57.1497",
            "long": "-2.0943",
            "gridind": "1",
            "lad25cd": "S12000033",
            "cty25cd": "S99999999",
            "lsoa21cd": "S01006514",
        },
        # Second postcode in SW1A with different LAD — tests multi-LA index
        {
            "pcds": "SW1A 2PW",
            "lat": "51.5074",
            "long": "-0.1278",
            "gridind": "1",
            "lad25cd": "E09000001",
            "cty25cd": "E99999999",
            "lsoa21cd": "E01000001",
        },
        # gridind=9 — should be skipped
        {
            "pcds": "ZZ9 9ZZ",
            "lat": "0.0",
            "long": "0.0",
            "gridind": "9",
            "lad25cd": "",
            "cty25cd": "",
            "lsoa21cd": "",
        },
        # Empty lat/lon — should be skipped
        {
            "pcds": "XX1 1XX",
            "lat": "",
            "long": "",
            "gridind": "1",
            "lad25cd": "E06000001",
            "cty25cd": "E99999999",
            "lsoa21cd": "E01000099",
        },
    ]
    fieldnames = ["pcds", "lat", "long", "gridind", "lad25cd", "cty25cd", "lsoa21cd"]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return {
        "source_dir": str(source_dir),
        "data_dir": str(data_dir),
        "export_dir": str(export_dir),
    }


def _make_mock_pg(provider_rows=None, iod_rows=None):
    """Create a mock BsilPostgresResource returning IoD + provider rows.

    The asset opens two connections sequentially: first IoD, then providers.
    """
    mock_pg = MagicMock()
    call_results = [iod_rows or [], provider_rows or []]
    call_idx = [0]

    def _get_connection():
        ctx = MagicMock()
        idx = call_idx[0]
        call_idx[0] += 1
        mock_cur = MagicMock()
        mock_cur.fetchall.return_value = (
            call_results[idx] if idx < len(call_results) else []
        )
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.__enter__ = MagicMock(return_value=mock_cur)
        mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
        ctx.__enter__ = MagicMock(return_value=mock_conn)
        ctx.__exit__ = MagicMock(return_value=False)
        return ctx

    mock_pg.get_connection = _get_connection
    return mock_pg


def _run_asset(autocomplete_env, provider_rows=None, iod_rows=None):
    """Run postcode_autocomplete with env vars pointing at temp dirs."""
    import os

    env = autocomplete_env
    old_env = {}
    env_vars = {
        "SOURCE_DATA_PATH": env["source_dir"],
        "DATA_DIR": env["data_dir"],
        "EXPORT_APP_DIR": env["export_dir"],
    }
    for k, v in env_vars.items():
        old_env[k] = os.environ.get(k)
        os.environ[k] = v

    try:
        mock_pg = _make_mock_pg(provider_rows, iod_rows)
        ctx = build_asset_context(resources={"bsil_postgres": mock_pg})
        result = postcode_autocomplete(ctx)
    finally:
        for k, v in old_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    return result


class TestAssetIntegration:
    def test_outward_json_is_sorted_array(self, autocomplete_env):
        _run_asset(autocomplete_env)
        outward_path = Path(autocomplete_env["export_dir"]) / "outward.json"
        data = json.loads(outward_path.read_text())
        assert isinstance(data, list)
        assert data == sorted(data)
        # Should contain exactly 3 outward codes (SW1A, OX2, AB1)
        assert set(data) == {"AB1", "OX2", "SW1A"}

    def test_inward_json_has_correct_keys(self, autocomplete_env):
        _run_asset(autocomplete_env)
        inward_path = Path(autocomplete_env["export_dir"]) / "inward" / "SW1A.json"
        data = json.loads(inward_path.read_text())
        assert "1AA" in data
        entry = data["1AA"]
        assert "b" in entry and len(entry["b"]) == 4
        assert "c" in entry and len(entry["c"]) == 2

    def test_polygon_bbox_used_when_available(self, autocomplete_env):
        _run_asset(autocomplete_env)
        inward_path = Path(autocomplete_env["export_dir"]) / "inward" / "SW1A.json"
        data = json.loads(inward_path.read_text())
        bbox = data["1AA"]["b"]
        # Should match the SQLite polygon bbox, not a point fallback
        assert bbox[0] == pytest.approx(-0.1416, abs=1e-4)
        assert bbox[1] == pytest.approx(51.4993, abs=1e-4)
        assert bbox[2] == pytest.approx(-0.1393, abs=1e-4)
        assert bbox[3] == pytest.approx(51.5013, abs=1e-4)

    def test_point_bbox_fallback(self, autocomplete_env):
        _run_asset(autocomplete_env)
        inward_path = Path(autocomplete_env["export_dir"]) / "inward" / "AB1.json"
        data = json.loads(inward_path.read_text())
        bbox = data["0AA"]["b"]
        centroid = data["0AA"]["c"]
        # Point fallback: bbox = lat/lon +/- 0.002
        assert bbox[0] == pytest.approx(-2.0943 - 0.002, abs=1e-4)
        assert bbox[2] == pytest.approx(-2.0943 + 0.002, abs=1e-4)
        assert bbox[1] == pytest.approx(57.1497 - 0.002, abs=1e-4)
        assert bbox[3] == pytest.approx(57.1497 + 0.002, abs=1e-4)
        # Centroid should be lat/lon directly
        assert centroid[0] == pytest.approx(-2.0943, abs=1e-4)
        assert centroid[1] == pytest.approx(57.1497, abs=1e-4)

    def test_gridind_9_skipped(self, autocomplete_env):
        _run_asset(autocomplete_env)
        # ZZ9 outward code should not exist
        outward_path = Path(autocomplete_env["export_dir"]) / "outward.json"
        data = json.loads(outward_path.read_text())
        assert "ZZ9" not in data
        # Nor should an inward file exist
        zz9_path = Path(autocomplete_env["export_dir"]) / "inward" / "ZZ9.json"
        assert not zz9_path.exists()

    def test_metadata_counts(self, autocomplete_env):
        result = _run_asset(autocomplete_env)
        assert result["postcodes_processed"].value == 4
        assert result["postcodes_skipped"].value == 2
        assert result["outward_codes"].value == 3

    def test_inward_json_has_lad_index(self, autocomplete_env):
        """Each inward file should have a '_' array and 'a' index arrays per entry."""
        _run_asset(autocomplete_env)
        # SW1A has two postcodes in two different LAs (both single-tier)
        sw1a_path = Path(autocomplete_env["export_dir"]) / "inward" / "SW1A.json"
        data = json.loads(sw1a_path.read_text())
        assert "_" in data
        assert isinstance(data["_"], list)
        assert len(data["_"]) == 2
        # Sorted: E09000001 < E09000033
        assert data["_"] == ["E09000001", "E09000033"]
        # 1AA is Westminster (E09000033) → index [1]
        assert data["1AA"]["a"] == [1]
        # 2PW is City of London (E09000001) → index [0]
        assert data["2PW"]["a"] == [0]

    def test_two_tier_la_codes(self, autocomplete_env):
        """Two-tier areas should have both district and county codes in 'a'."""
        _run_asset(autocomplete_env)
        ox2_path = Path(autocomplete_env["export_dir"]) / "inward" / "OX2.json"
        data = json.loads(ox2_path.read_text())
        # OX2 has E07000178 (district) and E10000025 (county)
        assert data["_"] == ["E07000178", "E10000025"]
        # 0AA should have indices for both codes
        assert data["0AA"]["a"] == [0, 1]

    def test_single_tier_la_codes(self, autocomplete_env):
        """Single-tier areas should have a single-element 'a' array."""
        _run_asset(autocomplete_env)
        ab1_path = Path(autocomplete_env["export_dir"]) / "inward" / "AB1.json"
        data = json.loads(ab1_path.read_text())
        assert data["_"] == ["S12000033"]
        assert data["0AA"]["a"] == [0]

    def test_lad_index_sorted(self, autocomplete_env):
        """The '_' array should be sorted for deterministic output."""
        _run_asset(autocomplete_env)
        for outward in ["AB1", "OX2", "SW1A"]:
            path = Path(autocomplete_env["export_dir"]) / "inward" / f"{outward}.json"
            data = json.loads(path.read_text())
            assert data["_"] == sorted(data["_"]), f"{outward}: '_' array not sorted"

    def test_unique_lad_codes_metadata(self, autocomplete_env):
        """Metadata should report total unique LAD codes across all files."""
        result = _run_asset(autocomplete_env)
        # 5 unique codes: E09000001, E09000033, E07000178, E10000025, S12000033
        assert result["unique_lad_codes"].value == 5

    def test_iod_decile_present_for_english_postcode(self, autocomplete_env):
        """English postcodes with IoD data should have 'd' property."""
        iod_rows = [("E01004736", 7), ("E01028522", 3), ("E01000001", 9)]
        _run_asset(autocomplete_env, iod_rows=iod_rows)
        sw1a_path = Path(autocomplete_env["export_dir"]) / "inward" / "SW1A.json"
        data = json.loads(sw1a_path.read_text())
        assert data["1AA"]["d"] == 7
        assert data["2PW"]["d"] == 9

    def test_iod_decile_absent_for_scottish_postcode(self, autocomplete_env):
        """Scottish postcodes should NOT have 'd' property (IoD is England-only)."""
        iod_rows = [("E01004736", 7)]
        _run_asset(autocomplete_env, iod_rows=iod_rows)
        ab1_path = Path(autocomplete_env["export_dir"]) / "inward" / "AB1.json"
        data = json.loads(ab1_path.read_text())
        assert "d" not in data["0AA"]

    def test_iod_metadata_count(self, autocomplete_env):
        """Metadata should report how many postcodes got IoD decile."""
        iod_rows = [("E01004736", 7), ("E01028522", 3), ("E01000001", 9)]
        result = _run_asset(autocomplete_env, iod_rows=iod_rows)
        assert result["postcodes_with_iod"].value == 3

    def test_no_iod_when_table_empty(self, autocomplete_env):
        """When IoD table is empty, no 'd' property should appear."""
        _run_asset(autocomplete_env, iod_rows=[])
        sw1a_path = Path(autocomplete_env["export_dir"]) / "inward" / "SW1A.json"
        data = json.loads(sw1a_path.read_text())
        assert "d" not in data["1AA"]


# ---------------------------------------------------------------------------
# 2. _expand_bboxes unit tests
# ---------------------------------------------------------------------------


def _make_entry(cx, cy, delta=0.001):
    """Create an inward_data entry with a small bbox around (cx, cy)."""
    return {
        "b": [cx - delta, cy - delta, cx + delta, cy + delta],
        "c": [cx, cy],
    }


class TestExpandBboxes:
    def test_expands_to_include_3_nearest(self):
        """Bbox should expand to encompass the 3rd-nearest provider."""
        # Postcode at (51.75, -1.26), 3 providers nearby at ~0.01 degree offsets
        entry = _make_entry(-1.26, 51.75)
        inward_data = {"OX": {"2AA": entry}}
        providers = [
            (51.751, -1.259),  # ~0.0014 away
            (51.749, -1.261),  # ~0.0014 away
            (51.755, -1.255),  # ~0.007 away (3rd nearest)
        ]
        _expand_bboxes(inward_data, providers)

        bbox = entry["b"]
        # All 3 providers should be inside the expanded bbox
        for plat, plon in providers:
            assert bbox[0] <= plon <= bbox[2], (
                f"lon {plon} outside [{bbox[0]}, {bbox[2]}]"
            )
            assert bbox[1] <= plat <= bbox[3], (
                f"lat {plat} outside [{bbox[1]}, {bbox[3]}]"
            )

    def test_symmetric_expansion(self):
        """Bbox should extend equally in all directions from centroid."""
        entry = _make_entry(-1.0, 52.0)
        inward_data = {"X": {"1A": entry}}
        # Place all 3 providers to the east — expansion should still be symmetric
        providers = [
            (52.0, -0.99),
            (52.0, -0.98),
            (52.0, -0.97),  # 3rd nearest at 0.03 degree distance
        ]
        _expand_bboxes(inward_data, providers)

        bbox = entry["b"]
        cx, cy = -1.0, 52.0
        # South/north should be symmetric around centroid
        assert bbox[1] == pytest.approx(cy - (cy - bbox[1]), abs=1e-6)
        south_delta = cy - bbox[1]
        north_delta = bbox[3] - cy
        assert south_delta == pytest.approx(north_delta, abs=1e-6)
        # West/east should be symmetric around centroid
        west_delta = cx - bbox[0]
        east_delta = bbox[2] - cx
        assert west_delta == pytest.approx(east_delta, abs=1e-6)

    def test_expansion_capped_at_max_radius(self):
        """r should not exceed _MAX_EXPANSION_RADIUS even for remote postcodes."""
        entry = _make_entry(-6.0, 58.0)
        inward_data = {"ZE": {"1A": entry}}
        # Providers very far away (> 0.18 degrees)
        providers = [
            (58.5, -5.5),
            (58.6, -5.4),
            (58.7, -5.3),
        ]
        _expand_bboxes(inward_data, providers)

        bbox = entry["b"]
        cy = 58.0
        # Lat expansion should be capped at _MAX_EXPANSION_RADIUS
        assert bbox[1] >= cy - _MAX_EXPANSION_RADIUS - 1e-6
        assert bbox[3] <= cy + _MAX_EXPANSION_RADIUS + 1e-6

    def test_original_bbox_preserved_when_larger(self):
        """Union with original bbox — original extends beyond expansion."""
        # Large original bbox (e.g. district-level)
        entry = {
            "b": [-1.5, 51.5, -1.0, 52.0],
            "c": [-1.25, 51.75],
        }
        inward_data = {"X": {"1A": entry}}
        # Providers very close — expansion radius small
        providers = [
            (51.7501, -1.2499),
            (51.7502, -1.2498),
            (51.7503, -1.2497),
        ]
        _expand_bboxes(inward_data, providers)

        bbox = entry["b"]
        # Original bbox was larger, should be preserved
        assert bbox[0] <= -1.5
        assert bbox[1] <= 51.5
        assert bbox[2] >= -1.0
        assert bbox[3] >= 52.0

    def test_no_expansion_with_fewer_than_k_providers(self):
        """With fewer than k=3 providers, bboxes should not be modified."""
        entry = _make_entry(-1.0, 52.0)
        original_bbox = list(entry["b"])
        inward_data = {"X": {"1A": entry}}
        providers = [(52.001, -0.999), (52.002, -0.998)]  # only 2
        _expand_bboxes(inward_data, providers)
        assert entry["b"] == original_bbox

    def test_centroid_unchanged(self):
        """Expansion should never modify the centroid."""
        entry = _make_entry(-1.26, 51.75)
        original_centroid = list(entry["c"])
        inward_data = {"OX": {"2AA": entry}}
        providers = [
            (51.76, -1.25),
            (51.74, -1.27),
            (51.77, -1.24),
        ]
        _expand_bboxes(inward_data, providers)
        assert entry["c"] == original_centroid
