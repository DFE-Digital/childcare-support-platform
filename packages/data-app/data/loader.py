from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

DATA_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "exported_data"
    / "parquet"
    / "published"
)
if not DATA_DIR.exists():
    DATA_DIR = Path("/app/data/published")

PROVIDER_JSON_DIR = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "exported_data"
    / "app"
    / "providers"
)
if not PROVIDER_JSON_DIR.exists():
    PROVIDER_JSON_DIR = Path("/app/data/app/providers")

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
BOUNDARIES_PATH = Path("/app/data/la_boundaries.geojson")
if not BOUNDARIES_PATH.exists():
    BOUNDARIES_PATH = _PROJECT_ROOT / "exported_data" / "la_boundaries.geojson"
if not BOUNDARIES_PATH.exists():
    # Generate from source GeoPackage using the pipeline's core logic.
    # We can't import the module directly (it has dagster top-level imports),
    # so we load just the generate_la_boundaries function via importlib.
    _source_dir = _PROJECT_ROOT / "source_data"
    _asset_file = (
        _PROJECT_ROOT
        / "packages"
        / "data-pipeline"
        / "bsil_pipeline"
        / "assets"
        / "la_boundaries.py"
    )
    if (_source_dir / "boundary-line").exists() and _asset_file.exists():
        import importlib.util
        import logging
        import types

        # Provide a stub dagster module so the asset file's top-level import
        # succeeds without installing dagster in the data-app venv.
        _dagster_stub = types.ModuleType("dagster")
        _dagster_stub.asset = lambda **kw: (lambda fn: fn)
        _dagster_stub.AssetExecutionContext = None
        _dagster_stub.Config = type("Config", (), {})
        _dagster_stub.MetadataValue = None
        import sys

        sys.modules.setdefault("dagster", _dagster_stub)

        spec = importlib.util.spec_from_file_location(
            "la_boundaries_asset", _asset_file
        )
        _mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_mod)

        _log = logging.getLogger("la_boundaries")
        _log.setLevel(logging.INFO)
        _log.addHandler(logging.StreamHandler())
        _mod.generate_la_boundaries(_source_dir, BOUNDARIES_PATH, _log)

# Fields checked for presence/absence in the field bars panel.
# Ordered to match the Prisma schema (prisma/schema.prisma).
# Internal fields (id, metadata, provider_id, care_type_id) are excluded.
PRESENCE_FIELDS: dict[str, list[str]] = {
    "provider": [
        "name",
        "address_line1",
        "address_line2",
        "city",
        "postcode",
        "latitude",
        "longitude",
        "bbox_geo_code",
        "bbox_geo_type",
        "phone",
        "email",
        "website",
        "has_garden",
        "has_kitchen",
        "ofsted_legacy_rating",
        "ofsted_legacy_behaviour_and_attitudes",
        "ofsted_legacy_early_years",
        "ofsted_legacy_leadership_and_management",
        "ofsted_legacy_personal_development",
        "ofsted_legacy_quality_of_education",
        "ofsted_legacy_sixth_form",
        "ofsted_inspection_date",
        "ofsted_framework",
        "ofsted_safeguarding_met",
        "ofsted_ccr_met",
        "ofsted_vcr_met",
        "ofsted_oosc_met",
        "ofsted_achievement",
        "ofsted_attendance_and_behaviour",
        "ofsted_behaviour_attitudes_routines",
        "ofsted_childrens_welfare_wellbeing",
        "ofsted_curriculum_and_teaching",
        "ofsted_early_years",
        "ofsted_inclusion",
        "ofsted_leadership_and_governance",
        "ofsted_personal_development_wellbeing",
        "ofsted_sixth_form",
        "registered_places",
        "staff_graduate_percentage",
        "staff_turnover_percentage",
        "institution_type",
        "lad25cd",
        "is_insufficient",
    ],
    "care_type": [
        "care_type",
        "opening_hour_open",
        "opening_hour_close",
        "operating_weeks_per_year",
        "session_hours_morning",
        "session_hours_afternoon",
        "session_hours_full_day",
        "eligible_min_months",
        "eligible_min_years",
        "eligible_max_years",
        "eligible_attendees_only",
        "eligible_institutions",
        "eligible_other",
        "funded_hours_accepted",
        "min_commitment_amount",
        "min_commitment_duration",
        "min_commitment_unit",
        "no_minimum_commitment",
    ],
    "fee_rate": [
        "morning_session",
        "afternoon_session",
        "full_day",
        "per_session",
        "per_hour",
        "per_day",
        "age_band",
    ],
}

# Map DataFrame column names to metadata.field_sources keys where they differ.
FIELD_SOURCE_KEY_MAP: dict[str, str] = {
    "name": "provider_name",
}

# Default source labels for fields that are computed, not sourced.
DEFAULT_FIELD_SOURCE: dict[str, str] = {
    "institution_type": "derived",
}


def parse_field_sources(metadata) -> dict[str, str]:
    """Extract field_sources dict from a metadata JSON value."""
    if not metadata:
        return {}
    try:
        parsed = json.loads(metadata) if isinstance(metadata, str) else metadata
        return parsed.get("field_sources", {})
    except (json.JSONDecodeError, TypeError):
        return {}


def normalise_field_source(raw: str) -> str:
    """Normalise a raw field_sources value for display.

    Strips per-provider numeric IDs but preserves semantic qualifiers.
    """
    if raw.startswith("la_scrape:"):
        return "la_scrape"
    if raw.startswith("la_extract:"):
        # la_extract:{source_id}:{field_key} — keep only the last segment
        parts = raw.split(":")
        return f"la_extract:{parts[-1]}"
    return raw


# Colour map for field source categories in the field bars chart.
FIELD_SOURCE_COLORS: dict[str, str] = {
    # LA scrape (greens)
    "la_scrape": "#2ca02c",
    # LA extract enrichment (green variants)
    "la_extract:age_range": "#4daf4a",
    "la_extract:age_range_catered_for": "#66c266",
    "la_extract:daily_session_times": "#33a02c",
    "la_extract:opening_times_sessions": "#5cb85c",
    "la_extract:opening_hours_raw": "#7ec87e",
    "la_extract:number_of_weeks_opens": "#2d882d",
    "la_extract:availability": "#3e9f3e",
    "la_extract:term_time_info": "#50b650",
    "la_extract:session_types_raw": "#62cd62",
    "la_extract:registered_for_funding": "#28a428",
    "la_extract:funded_info": "#3bbb3b",
    "la_extract:funded_2yr": "#4ed24e",
    "la_extract:fees_structured": "#1e8c1e",
    "la_extract:fees_raw": "#35a335",
    "la_extract:costs": "#4cba4c",
    # Ofsted (blues)
    "ofsted": "#1f77b4",
    "ofsted:register_combinations": "#4a9fd4",
    # GIAS (orange)
    "gias": "#ff7f0e",
    # School (purples)
    "school_census": "#9467bd",
    "school_census:youngest_pupil_age": "#b07ed8",
    "school_inspections": "#7b4fad",
    "school_default:maintained_nursery_class": "#c89fe0",
    # Geocoding (cyans)
    "os.ofsted_places": "#17becf",
    "os.la_places": "#4dd2df",
    "bbox:os.ofsted_places": "#84e5ef",
    "bbox:os.la_places": "#a0edf5",
    # Other
    "free_breakfast": "#bcbd22",
    "derived": "#8c8c8c",
    "unknown": "#c7c7c7",
    "absent": "#d62728",
}


# Source tier colour map (matches coverage.ipynb)
SOURCE_TIER_COLORS = {
    "LA + Ofsted + School": "#2ca02c",
    "LA + Ofsted": "#98df8a",
    "LA only": "#ffbb78",
    "Ofsted + School": "#aec7e8",
    "Ofsted only": "#ff9896",
    "Other": "#c7c7c7",
    "No data": "#d62728",
}

LA_NAME_LOOKUP: dict[str, str] = {}


def _load_la_names() -> dict[str, str]:
    """Build lad25cd -> LA name lookup from the la parquet or boundary GeoJSON."""
    la_path = DATA_DIR.parent / "la" / "family_information_services.parquet"
    if la_path.exists():
        la_df = pd.read_parquet(la_path, columns=["lad25cd", "lad25nm"])
        return dict(zip(la_df["lad25cd"], la_df["lad25nm"]))
    # Fallback: extract names from boundary GeoJSON
    boundaries = load_boundaries()
    if boundaries:
        return {
            f["properties"]["LAD25CD"]: f["properties"]["LAD25NM"]
            for f in boundaries["features"]
            if "LAD25CD" in f["properties"]
        }
    return {}


def _find_parquet(name: str) -> Path:
    """Find a parquet file in DATA_DIR."""
    path = DATA_DIR / name
    if path.exists():
        return path
    raise FileNotFoundError(f"Cannot find {name} in {DATA_DIR}")


def load_providers() -> pd.DataFrame:
    path = _find_parquet("providers.parquet")
    df = pd.read_parquet(path)
    for col in ("institution_type", "lad25cd"):
        if col not in df.columns:
            df[col] = None
    return df


def _extract_sources(metadata: str | None) -> list[str]:
    """Extract the sources list from a provider's metadata JSON."""
    if not metadata:
        return []
    try:
        parsed = json.loads(metadata) if isinstance(metadata, str) else metadata
        return parsed.get("sources", [])
    except (json.JSONDecodeError, TypeError):
        return []


def load_care_types() -> pd.DataFrame:
    return pd.read_parquet(_find_parquet("care_types.parquet"))


def load_fee_rates() -> pd.DataFrame:
    return pd.read_parquet(_find_parquet("fee_rates.parquet"))


def load_boundaries() -> dict | None:
    if BOUNDARIES_PATH.exists():
        with open(BOUNDARIES_PATH) as f:
            return json.load(f)
    return None


def _classify_source_tier(sources: list[str]) -> str:
    """Classify a provider's source tier from its sources list."""
    if not sources:
        return "Other"
    s = set(sources)
    has_la = "la_scrape" in s
    has_ofsted = "ofsted" in s
    has_school = "school_census" in s
    if has_la and has_ofsted and has_school:
        return "LA + Ofsted + School"
    if has_la and has_ofsted:
        return "LA + Ofsted"
    if has_la:
        return "LA only"
    if has_ofsted and has_school:
        return "Ofsted + School"
    if has_ofsted:
        return "Ofsted only"
    return "Other"


def compute_la_source_tiers(providers: pd.DataFrame) -> pd.DataFrame:
    """Compute source tier per LA from providers metadata.sources.

    Returns a DataFrame with columns: lad25cd, source_tier, providers, la_name.
    """
    df = providers[providers["lad25cd"].notna()].copy()
    df["_sources"] = df["metadata"].apply(_extract_sources)

    # Per-LA: aggregate by checking if any provider has each source
    def _la_tier(group):
        sources_all: set[str] = set()
        for src_list in group["_sources"]:
            sources_all.update(src_list)
        return _classify_source_tier(list(sources_all))

    la_tiers = (
        df.groupby("lad25cd")
        .apply(_la_tier, include_groups=False)
        .reset_index(name="source_tier")
    )
    la_counts = df.groupby("lad25cd").size().reset_index(name="providers")
    result = la_tiers.merge(la_counts, on="lad25cd")

    if not LA_NAME_LOOKUP:
        LA_NAME_LOOKUP.update(_load_la_names())
    result["la_name"] = result["lad25cd"].map(LA_NAME_LOOKUP).fillna(result["lad25cd"])

    return result


def build_provider_summary(
    providers: pd.DataFrame, care_types: pd.DataFrame
) -> pd.DataFrame:
    """Join care types onto providers as a comma-separated summary column."""
    ct_summary = (
        care_types.groupby("provider_id")["care_type"]
        .apply(lambda x: ", ".join(sorted(x.unique())))
        .reset_index()
        .rename(columns={"care_type": "care_types_summary"})
    )
    merged = providers.merge(
        ct_summary, left_on="id", right_on="provider_id", how="left"
    )
    merged["care_types_summary"] = merged["care_types_summary"].fillna("")

    if not LA_NAME_LOOKUP:
        LA_NAME_LOOKUP.update(_load_la_names())
    if LA_NAME_LOOKUP:
        merged["la_name"] = merged["lad25cd"].map(LA_NAME_LOOKUP).fillna("")
    else:
        merged["la_name"] = ""

    return merged


def compute_field_sources(
    providers: pd.DataFrame,
    care_types: pd.DataFrame,
    fee_rates: pd.DataFrame,
) -> pd.DataFrame:
    """Compute per-field source breakdown as % of providers.

    Returns a long-form DataFrame with columns: field, source, count, pct.
    Each field has one row per source that contributed values, plus an
    ``absent`` row for providers where the field is null.
    """
    n = len(providers)
    if n == 0:
        return pd.DataFrame(columns=["field", "source", "count", "pct"])

    rows: list[dict] = []

    def _add_field(label: str, source_counts: dict[str, int]):
        present_total = sum(source_counts.values())
        for src, cnt in sorted(source_counts.items()):
            rows.append(
                {
                    "field": label,
                    "source": src,
                    "count": cnt,
                    "pct": round(100 * cnt / n, 1),
                }
            )
        absent = n - present_total
        if absent > 0:
            rows.append(
                {
                    "field": label,
                    "source": "absent",
                    "count": absent,
                    "pct": round(100 * absent / n, 1),
                }
            )

    # --- Provider-level fields ---
    prov_fs = providers["metadata"].apply(parse_field_sources)

    for field in PRESENCE_FIELDS["provider"]:
        if field not in providers.columns:
            continue
        mask = providers[field].notna()
        if field == "latitude":
            mask = mask & (providers[field] != 0)
        fs_key = FIELD_SOURCE_KEY_MAP.get(field, field)
        default_src = DEFAULT_FIELD_SOURCE.get(field, "unknown")
        sources = prov_fs[mask].apply(
            lambda fs, k=fs_key, d=default_src: normalise_field_source(fs.get(k, d))
        )
        _add_field(f"provider.{field}", sources.value_counts().to_dict())

    # --- Care-type fields (per-provider: first source wins) ---
    ct_has_meta = "metadata" in care_types.columns
    ct_fs = (
        care_types["metadata"].apply(parse_field_sources)
        if ct_has_meta
        else pd.Series([{}] * len(care_types), index=care_types.index)
    )
    for field in PRESENCE_FIELDS["care_type"]:
        if field not in care_types.columns:
            continue
        mask = care_types[field].notna()
        ct_present = care_types.loc[mask, ["provider_id"]].copy()
        ct_present["_source"] = ct_fs[mask].apply(
            lambda fs, k=field: normalise_field_source(fs.get(k, "unknown"))
        )
        per_provider = ct_present.drop_duplicates(subset="provider_id", keep="first")
        _add_field(
            f"care_type.{field}", per_provider["_source"].value_counts().to_dict()
        )

    # --- Fee-rate fields (linked via care_types; source key is "fee_data") ---
    if not fee_rates.empty:
        fr_with_provider = fee_rates.merge(
            care_types[["id", "provider_id"]].rename(columns={"id": "care_type_id"}),
            on="care_type_id",
            how="left",
        )
        fr_has_meta = "metadata" in fr_with_provider.columns
        fr_fs = (
            fr_with_provider["metadata"].apply(parse_field_sources)
            if fr_has_meta
            else pd.Series([{}] * len(fr_with_provider), index=fr_with_provider.index)
        )
        for field in PRESENCE_FIELDS["fee_rate"]:
            if field not in fr_with_provider.columns:
                continue
            mask = fr_with_provider[field].notna()
            fr_present = fr_with_provider.loc[mask, ["provider_id"]].copy()
            fr_present["_source"] = fr_fs[mask].apply(
                lambda fs, k=field: normalise_field_source(
                    fs.get("fee_data", fs.get(k, "unknown"))
                )
            )
            per_provider = fr_present.drop_duplicates(
                subset="provider_id", keep="first"
            )
            _add_field(
                f"fee_rate.{field}", per_provider["_source"].value_counts().to_dict()
            )
    else:
        for field in PRESENCE_FIELDS["fee_rate"]:
            rows.append(
                {
                    "field": f"fee_rate.{field}",
                    "source": "absent",
                    "count": n,
                    "pct": 100.0,
                }
            )

    return pd.DataFrame(rows)
