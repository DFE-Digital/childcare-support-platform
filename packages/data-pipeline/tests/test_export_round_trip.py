"""End-to-end round-trip test: JSON fixtures → draft → publish → exported JSON.

Loads a subset of fixture files into the draft schema, runs publish_providers
to copy them to published, then runs the export and compares to the originals.

Expected to run inside the dagster-user-code container where psycopg,
dagster, and postgres are available.
"""

import json
import os
import re
import tempfile
from copy import deepcopy
from pathlib import Path

import pytest

from bsil_pipeline.assets.export import export_providers_to_dir
from bsil_pipeline.resources.postgres import BsilPostgresResource
from tests.conftest import load_fixtures_to_published

FIXTURES_DIR = Path("/opt/dagster/app/data/placeholder-providers")

TEST_FIXTURE_IDS = sorted(p.stem for p in FIXTURES_DIR.glob("*.json"))


def _get_resource() -> BsilPostgresResource:
    return BsilPostgresResource(
        host=os.environ.get("POSTGRES_HOST", "postgres"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        user=os.environ.get("POSTGRES_USER", "bsil"),
        password=os.environ.get("POSTGRES_PASSWORD", "bsil_local"),
        dbname=os.environ.get("POSTGRES_DB", "bsil"),
    )


def _strip_distance_miles(data: dict) -> dict:
    """Return a copy of the provider dict with distanceMiles removed."""
    d = deepcopy(data)
    d.pop("distanceMiles", None)
    return d


def _sort_keys_recursive(obj):
    """Recursively sort dict keys and strip None values for comparison."""
    if isinstance(obj, dict):
        return {
            k: _sort_keys_recursive(v) for k, v in sorted(obj.items()) if v is not None
        }
    if isinstance(obj, list):
        return [_sort_keys_recursive(item) for item in obj]
    return obj


def _normalise_for_comparison(data: dict) -> dict:
    """Normalise a provider dict for comparison.

    - Strips distanceMiles (search-context, not stored in DB)
    - Converts int fee values to float (DB stores as Decimal -> float)
    - Converts int staff percentages to float
    - Converts int session hours to float
    - Adds default empty arrays for fields the DB populates when absent
    - Strips bbox fields not stored in fixtures (bboxGeoType, bboxGeoCode)
    - Migrates ofsted.rating -> ofsted.legacyRating and removes ofsted.reportUrl
    """
    d = _strip_distance_miles(data)
    _floatify_provider(d)
    _add_db_defaults(d)
    _normalize_phone_field(d)
    _migrate_ofsted_fields(d)
    # Remove bbox-related fields that fixtures don't have but export omits anyway
    d.pop("bboxGeoType", None)
    d.pop("bboxGeoCode", None)
    # Strip top-level null values — export omits them
    d = {k: v for k, v in d.items() if v is not None}
    return d


def _normalize_phone_field(d: dict) -> None:
    if "phone" in d and d["phone"] is not None:
        d["phone"] = re.sub(r"[^0-9+]", "", d["phone"])
        if d["phone"].startswith("+44"):
            d["phone"] = "0" + d["phone"][3:]
        elif d["phone"].startswith("44") and len(d["phone"]) > 10:
            d["phone"] = "0" + d["phone"][2:]


def _migrate_ofsted_fields(d: dict) -> None:
    """Migrate fixture ofsted fields to match the new export schema.

    - rating -> legacyRating
    - Adds framework='legacy' when legacyRating is present
    - Removes reportUrl (derivable from URN)
    """
    ofsted = d.get("ofsted")
    if not ofsted:
        return
    if "rating" in ofsted:
        ofsted["legacyRating"] = ofsted.pop("rating")
        ofsted["framework"] = "legacy"
    ofsted.pop("reportUrl", None)


def _add_db_defaults(d: dict) -> None:
    """Add default values for fields that the DB populates when absent in JSON."""
    for ct in d.get("careTypes", []):
        if "eligibleInstitutions" not in ct:
            ct["eligibleInstitutions"] = []
        if "eligibleOther" not in ct:
            ct["eligibleOther"] = []


def _floatify_provider(d: dict) -> None:
    """In-place convert numeric values that the DB returns as float."""
    # Staff percentages
    staff = d.get("staff", {})
    for key in ("graduatePercentage", "turnoverPercentage"):
        if key in staff and isinstance(staff[key], int):
            staff[key] = float(staff[key])

    for ct in d.get("careTypes", []):
        # Session hours
        sh = ct.get("sessionHours", {})
        for key in ("morning", "afternoon", "fullDay"):
            if key in sh and isinstance(sh[key], int):
                sh[key] = float(sh[key])

        # Fees — nested dicts or flat keys
        fees = ct.get("fees", {})
        for fee_key, fee_val in fees.items():
            if isinstance(fee_val, dict):
                for k, v in fee_val.items():
                    if isinstance(v, int):
                        fee_val[k] = float(v)
            elif isinstance(fee_val, int):
                fees[fee_key] = float(fee_val)

        # Additional charges
        for charge in ct.get("additionalCharges", []):
            if isinstance(charge.get("cost"), int):
                charge["cost"] = float(charge["cost"])


@pytest.fixture()
def db_resource():
    """Return a BsilPostgresResource connected to the bsil_test database.

    The Makefile passes POSTGRES_DB=bsil_test so tests own the entire DB
    and can freely truncate, load, and commit without affecting main data.
    """
    return _get_resource()


def test_round_trip(db_resource):
    """Load fixtures into draft, publish to published, export back to JSON, compare."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir)

        with db_resource.get_connection() as conn:
            load_fixtures_to_published(conn, TEST_FIXTURE_IDS, FIXTURES_DIR)
            with conn.cursor() as cur:
                count = export_providers_to_dir(cur, output_dir)

        assert count == len(TEST_FIXTURE_IDS)

        for fixture_id in TEST_FIXTURE_IDS:
            # Read original fixture
            original_file = FIXTURES_DIR / f"{fixture_id}.json"
            original = json.loads(original_file.read_text())

            # Read exported file
            exported_file = output_dir / "providers" / f"{fixture_id}.json"
            assert exported_file.exists(), f"Missing exported file for {fixture_id}"
            exported = json.loads(exported_file.read_text())

            # Normalise and compare (order-independent)
            expected = _sort_keys_recursive(_normalise_for_comparison(original))
            actual = _sort_keys_recursive(exported)
            assert actual == expected, (
                f"Round-trip mismatch for {fixture_id}:\n"
                f"Expected: {json.dumps(expected, indent=2)}\n"
                f"Got:      {json.dumps(actual, indent=2)}"
            )


def _parse_provider_id(raw_id: str) -> int:
    return int(raw_id[1:])


def test_metadata_flag(db_resource):
    """Verify include_metadata gates _metadata in export output."""
    with db_resource.get_connection() as conn:
        load_fixtures_to_published(conn, TEST_FIXTURE_IDS, FIXTURES_DIR)

        # Set metadata on one provider
        test_id = _parse_provider_id(TEST_FIXTURE_IDS[0])
        sample_meta = {
            "provider_id": "ofsted:EY123456",
            "sources": ["la_scrape", "ofsted"],
            "linkage": {"ofsted": {"match_method": "urn_exact"}},
            "provider_sources": [{"source": "la_scrape", "sourceId": "E09000022:abc"}],
        }
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE published.providers SET metadata = %s::jsonb WHERE id = %s",
                (json.dumps(sample_meta), test_id),
            )
        conn.commit()

        # Export with metadata OFF — no _metadata key
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            with conn.cursor() as cur:
                export_providers_to_dir(cur, output_dir, include_metadata=False)
            exported = json.loads(
                (output_dir / "providers" / f"{TEST_FIXTURE_IDS[0]}.json").read_text()
            )
            assert "_metadata" not in exported

        # Export with metadata ON — _metadata key present
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            with conn.cursor() as cur:
                export_providers_to_dir(cur, output_dir, include_metadata=True)
            exported = json.loads(
                (output_dir / "providers" / f"{TEST_FIXTURE_IDS[0]}.json").read_text()
            )
            assert "_metadata" in exported
            assert exported["_metadata"]["provider_id"] == "ofsted:EY123456"
            assert "linkage" in exported["_metadata"]
            assert "provider_sources" in exported["_metadata"]
