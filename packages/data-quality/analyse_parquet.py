import re
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

from data_types import OpeningHours, CareType, Provider
from validation import (
    MissingField,
    FailedCheck,
    ValidationResult,
    validate_opening_hours,
    validate_care_type,
    validate_provider,
    group_care_type,
)


DATA_ROOT = Path(__file__).parent / "data"

# Region codes for regional beta name -> lad25cd
BETA_REGION_CODES = {
    "Bristol": "E06000023",
    "Bath and North East Somerset": "E06000022",
    "South Gloucestershire": "E06000025",
}

_BETA_LAT_BOUNDS = (51.0, 52.0)
_BETA_LNG_BOUNDS = (-3.0, -2.0)

pd.set_option("display.max_columns", None)
pd.set_option("display.max_rows", None)
pd.set_option("display.max_colwidth", None)
pd.set_option("display.expand_frame_repr", False)


# ---------------------------------------------------------------------------
# Version helpers
# ---------------------------------------------------------------------------


def _get_current_version_numbers() -> list[int]:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    version_numbers = []
    for path in DATA_ROOT.iterdir():
        if path.is_dir():
            m = re.fullmatch(r"v(\d+)", path.name)
            if m:
                version_numbers.append(int(m.group(1)))
    return version_numbers


def latest_version_dir() -> Path:
    versions = _get_current_version_numbers()
    if not versions:
        raise FileNotFoundError(f"No versioned data directories found in {DATA_ROOT}")
    return DATA_ROOT / f"v{max(versions)}"


def next_version_dir() -> Path:
    versions = _get_current_version_numbers()
    return DATA_ROOT / f"v{(max(versions) + 1) if versions else 0}"


# ---------------------------------------------------------------------------
# Load parquets into dataclass hierarchy
# ---------------------------------------------------------------------------


def _val(row, col):
    """Return None for NaN/NaT, otherwise the value."""
    v = row.get(col)
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


def load_data(
    parquet_dir: Path,
    verbose: bool = True,
    lad25cd: str | None = None,
) -> tuple[Provider, ...]:
    providers_df = pd.read_parquet(parquet_dir / "providers.parquet")
    care_types_df = pd.read_parquet(parquet_dir / "care_types.parquet")
    opening_hours_df = pd.read_parquet(parquet_dir / "opening_hours.parquet")

    filter_codes = {lad25cd} if lad25cd else set(BETA_REGION_CODES.values())
    providers_df = providers_df[providers_df["lad25cd"].isin(filter_codes)]

    # Index care types and opening hours for fast lookup
    ct_by_provider: dict[int, list] = defaultdict(list)
    for row in care_types_df.itertuples(index=False):
        ct_by_provider[row.provider_id].append(row)

    oh_by_care_type: dict[int, list] = defaultdict(list)
    for row in opening_hours_df.itertuples(index=False):
        oh_by_care_type[row.care_type_id].append(row)

    providers = []
    for row in providers_df.itertuples(index=False):
        provider_id = row.id

        care_types = []
        for ct in ct_by_provider.get(provider_id, []):
            oh_slots = []
            for oh in oh_by_care_type.get(ct.id, []):
                oh_slots.append(
                    OpeningHours(
                        monday=oh.monday,
                        tuesday=oh.tuesday,
                        wednesday=oh.wednesday,
                        thursday=oh.thursday,
                        friday=oh.friday,
                        saturday=oh.saturday,
                        sunday=oh.sunday,
                        open=str(oh.open) if oh.open is not None else None,
                        close=str(oh.close) if oh.close is not None else None,
                    )
                )
            care_types.append(
                CareType(
                    provider_id=str(provider_id),
                    care_type=ct.care_type if hasattr(ct, "care_type") else None,
                    opening_hours=tuple(oh_slots),
                    operating_weeks_per_year=_val(
                        ct._asdict(), "operating_weeks_per_year"
                    ),
                    eligible_min_months=_val(ct._asdict(), "eligible_min_months"),
                    eligible_min_years=_val(ct._asdict(), "eligible_min_years"),
                    eligible_max_years=_val(ct._asdict(), "eligible_max_years"),
                    ofsted_register_combination=_val(
                        ct._asdict(), "ofsted_register_combination"
                    ),
                )
            )

        row_d = row._asdict()
        providers.append(
            Provider(
                provider_id=str(provider_id),
                name=_val(row_d, "name"),
                institution_type=_val(row_d, "institution_type"),
                lad25cd=_val(row_d, "lad25cd"),
                postcode=_val(row_d, "postcode"),
                address_line1=_val(row_d, "address_line1"),
                address_line2=_val(row_d, "address_line2"),
                city=_val(row_d, "city"),
                latitude=_val(row_d, "latitude"),
                longitude=_val(row_d, "longitude"),
                phone=_val(row_d, "phone"),
                email=_val(row_d, "email"),
                website=_val(row_d, "website"),
                fis_url=_val(row_d, "fis_url"),
                ofsted_legacy_rating=_val(row_d, "ofsted_legacy_rating"),
                ofsted_inspection_date=_val(row_d, "ofsted_inspection_date"),
                ofsted_framework=_val(row_d, "ofsted_framework"),
                ofsted_safeguarding_met=_val(row_d, "ofsted_safeguarding_met"),
                registered_places=_val(row_d, "registered_places"),
                care_types=tuple(care_types),
            )
        )

    return tuple(providers)


# ---------------------------------------------------------------------------
# Error collection and stats
# ---------------------------------------------------------------------------


def collect_results(providers: tuple[Provider, ...]) -> list[ValidationResult]:
    results: list[ValidationResult] = []

    website_counts: dict[str, int] = defaultdict(int)
    fis_url_counts: dict[str, int] = defaultdict(int)
    phone_counts: dict[str, int] = defaultdict(int)
    email_counts: dict[str, int] = defaultdict(int)
    latlon_counts: dict[tuple[float, float], int] = defaultdict(int)
    for p in providers:
        if p.website is not None:
            website_counts[p.website] += 1
        if p.fis_url is not None:
            fis_url_counts[p.fis_url] += 1
        if p.phone is not None:
            phone_counts[p.phone] += 1
        if p.email is not None:
            email_counts[p.email] += 1
        if (
            p.latitude is not None
            and p.longitude is not None
            and p.institution_type != "childminder"
        ):
            latlon_counts[(p.latitude, p.longitude)] += 1

    for p in providers:
        results.extend(validate_provider(p))
        if p.website is not None and website_counts[p.website] > 5:
            results.append(
                FailedCheck(
                    "website used <= 5 times",
                    f"shared by {website_counts[p.website]} providers",
                )
            )
        if p.fis_url is not None and fis_url_counts[p.fis_url] > 1:
            results.append(
                FailedCheck(
                    "fis_url is unique",
                    f"shared by {fis_url_counts[p.fis_url]} providers",
                )
            )
        if p.phone is not None and phone_counts[p.phone] > 5:
            results.append(
                FailedCheck(
                    "phone used <= 5 times",
                    f"shared by {phone_counts[p.phone]} providers",
                )
            )
        if p.email is not None and email_counts[p.email] > 5:
            results.append(
                FailedCheck(
                    "email used <= 5 times",
                    f"shared by {email_counts[p.email]} providers",
                )
            )
        if (
            p.latitude is not None
            and p.longitude is not None
            and p.institution_type != "childminder"
        ):
            if latlon_counts[(p.latitude, p.longitude)] > 3:
                results.append(
                    FailedCheck(
                        "geolocation used <= 3 times",
                        f"lat/lng shared by {latlon_counts[(p.latitude, p.longitude)]} providers",
                    )
                )
        if p.lad25cd in set(BETA_REGION_CODES.values()):
            if p.latitude is not None and not (
                _BETA_LAT_BOUNDS[0] <= p.latitude <= _BETA_LAT_BOUNDS[1]
            ):
                results.append(
                    FailedCheck("beta region latitude 51–52", f"lat={p.latitude}")
                )
            if p.longitude is not None and not (
                _BETA_LNG_BOUNDS[0] <= p.longitude <= _BETA_LNG_BOUNDS[1]
            ):
                results.append(
                    FailedCheck("beta region longitude -3 to -2", f"lng={p.longitude}")
                )
        for ct in p.care_types:
            results.extend(validate_care_type(ct))
            for oh in ct.opening_hours:
                results.extend(validate_opening_hours(oh))
    return results


# Maps each field/check name to the number of entities it applies to.
_PROVIDER_FIELDS = [
    "non-cm: name",
    "institution_type",
    "lad25cd",
    "non-cm: postcode",
    "non-cm: address_line1",
    "non-cm: address_line2",
    "non-cm: city",
    "non-cm: latitude",
    "non-cm: longitude",
    "phone",
    "email",
    "ofsted_legacy_rating",
    "ofsted_inspection_date",
    "ofsted_framework",
    "registered_places",
]
_CARE_TYPE_COVERAGE_ONLY_FIELDS = ["has at least one opening hours slot"]
_CARE_TYPE_FIELDS = [
    "operating_weeks_per_year",
    "eligible_min_months",
    "eligible_min_years",
    "eligible_max_years",
]
_OH_FIELDS = ["open", "close"]

_PROVIDER_CHECKS = [
    "non-cm: has address",
    "non-cm: has lat lon",
    "non-cm: has contact details",
    "has at least one care type",
    "no duplicate care types",
    "ofsted_safeguarding_met set when school inspection",
    "website is not FIS",
    "website used <= 5 times",
    "fis_url is unique",
    "phone used <= 5 times",
    "email used <= 5 times",
    "institution_type matches care_type",
    "geolocation used <= 3 times",
    "beta region latitude 51–52",
    "beta region longitude -3 to -2",
    "lad25cd",
    "non-cm: name",
    "non-cm: postcode",
    "non-cm: address_line1",
    "non-cm: city",
    "phone",
    "email",
    "website",
    "fis_url",
    "ofsted_legacy_rating",
    "ofsted_inspection_date",
    "ofsted_framework",
    "registered_places",
]
_CARE_TYPE_CHECKS = [
    "care_type valid value",
    "eligible_min_years <= eligible_max_years",
    "eligible min age < eligible max age",
    "club eligible_min_years >= 4",
    "nursery eligible_max_years <= 5",
    "childminder has ofsted_register_combination",
    "childminder eligible_max_years matches ofsted",
    "childminder eligible_min_age matches ofsted",
    "breakfast club open 06:00–08:30",
    "breakfast club close 08:00–10:00",
    "after school club open 14:00–17:00",
    "after school club close 15:00–19:00",
    "holiday club open 07:00–10:00",
    "holiday club close 14:00–19:00",
    "operating_weeks_per_year",
]
_OH_CHECKS = [
    "duration >= 45 mins",
    "duration <= 12 hours",
    "at least one day selected",
    "open",
    "close",
]


def _count_totals(providers: tuple[Provider, ...]) -> dict[str, int]:
    n_providers = len(providers)
    n_non_cm = sum(1 for p in providers if p.institution_type != "childminder")
    all_care_types = [ct for p in providers for ct in p.care_types]
    n_care_types = len(all_care_types)
    n_oh = sum(len(ct.opening_hours) for ct in all_care_types)

    n_club_or_holiday = sum(
        1
        for ct in all_care_types
        if group_care_type(ct.care_type)
        in {"breakfast_club", "after_school_club", "holiday_club"}
    )
    n_nursery = sum(1 for ct in all_care_types if ct.care_type == "private_nursery")
    n_childminder = sum(1 for ct in all_care_types if ct.care_type == "childminder")
    n_childminder_with_register = sum(
        1
        for ct in all_care_types
        if ct.care_type == "childminder" and ct.ofsted_register_combination is not None
    )

    # Opening hour slots for club types only
    n_breakfast_oh = sum(
        len(ct.opening_hours)
        for ct in all_care_types
        if group_care_type(ct.care_type) == "breakfast_club"
    )
    n_after_school_oh = sum(
        len(ct.opening_hours)
        for ct in all_care_types
        if ct.care_type == "after_school_club"
    )
    n_holiday_oh = sum(
        len(ct.opening_hours) for ct in all_care_types if ct.care_type == "holiday_club"
    )

    n_school_inspection = sum(
        1
        for p in providers
        if p.ofsted_framework in {"report_card", "legacy_transition"}
    )

    totals: dict[str, int] = {}
    for f in _PROVIDER_FIELDS:
        totals[f] = n_non_cm if f.startswith("non-cm: ") else n_providers
    for f in _CARE_TYPE_FIELDS:
        totals[f] = n_care_types
    for f in _CARE_TYPE_COVERAGE_ONLY_FIELDS:
        totals[f] = n_care_types
    for f in _OH_FIELDS:
        totals[f] = n_oh
    totals["non-cm: has address"] = n_non_cm
    totals["non-cm: has lat lon"] = n_non_cm
    totals["non-cm: has contact details"] = n_non_cm
    totals["has at least one care type"] = n_providers
    totals["no duplicate care types"] = n_providers
    totals["website is not FIS"] = n_providers
    totals["website used <= 5 times"] = sum(
        1 for p in providers if p.website is not None
    )
    totals["fis_url is unique"] = sum(1 for p in providers if p.fis_url is not None)
    totals["phone used <= 5 times"] = sum(1 for p in providers if p.phone is not None)
    totals["email used <= 5 times"] = sum(1 for p in providers if p.email is not None)
    totals["institution_type matches care_type"] = n_providers
    totals["geolocation used <= 3 times"] = sum(
        1
        for p in providers
        if p.latitude is not None
        and p.longitude is not None
        and p.institution_type != "childminder"
    )
    _beta_codes = set(BETA_REGION_CODES.values())
    totals["beta region latitude 51–52"] = sum(
        1 for p in providers if p.latitude is not None and p.lad25cd in _beta_codes
    )
    totals["beta region longitude -3 to -2"] = sum(
        1 for p in providers if p.longitude is not None and p.lad25cd in _beta_codes
    )
    totals["ofsted_safeguarding_met set when school inspection"] = n_school_inspection
    totals["eligible_min_years <= eligible_max_years"] = n_care_types
    totals["eligible min age < eligible max age"] = n_care_types
    totals["club eligible_min_years >= 4"] = n_club_or_holiday
    totals["nursery eligible_max_years <= 5"] = n_nursery
    totals["childminder has ofsted_register_combination"] = n_childminder
    totals["childminder eligible_max_years matches ofsted"] = (
        n_childminder_with_register
    )
    totals["childminder eligible_min_age matches ofsted"] = n_childminder_with_register
    totals["breakfast club open 06:00–08:30"] = n_breakfast_oh
    totals["breakfast club close 08:00–10:00"] = n_breakfast_oh
    totals["after school club open 14:00–17:00"] = n_after_school_oh
    totals["after school club close 15:00–19:00"] = n_after_school_oh
    totals["holiday club open 07:00–10:00"] = n_holiday_oh
    totals["holiday club close 14:00–19:00"] = n_holiday_oh
    for c in _OH_CHECKS:
        if c not in totals:
            totals[c] = n_oh
    totals["website"] = sum(1 for p in providers if p.website is not None)
    totals["fis_url"] = sum(1 for p in providers if p.fis_url is not None)
    return totals


# Stats types:
#   field coverage:   field  -> (present, coverage_pct)
#   row checks:       check  -> (passing, pass_pct)
CoverageStats = dict[str, tuple[int, float]]
CheckStats = dict[str, tuple[int, float]]


def compute_stats(
    providers: tuple[Provider, ...],
) -> tuple[CoverageStats, CheckStats]:
    results = collect_results(providers)
    totals = _count_totals(providers)

    missing: dict[str, int] = defaultdict(int)
    failed: dict[str, int] = defaultdict(int)

    for r in results:
        if isinstance(r, MissingField):
            missing[r.field] += 1
        elif isinstance(r, FailedCheck):
            failed[r.check] += 1

    all_coverage_fields = (
        _PROVIDER_FIELDS
        + _CARE_TYPE_FIELDS
        + _OH_FIELDS
        + _CARE_TYPE_COVERAGE_ONLY_FIELDS
    )
    all_checks = _PROVIDER_CHECKS + _CARE_TYPE_CHECKS + _OH_CHECKS

    coverage: CoverageStats = {}
    for field in all_coverage_fields:
        total = totals.get(field, 0)
        if total == 0:
            continue
        present = total - missing.get(field, 0)
        coverage[field] = (present, present / total * 100)

    checks: CheckStats = {}
    for check in all_checks:
        total = totals.get(check, 0)
        if total == 0:
            continue
        passing = total - failed.get(check, 0)
        checks[check] = (passing, passing / total * 100)

    return coverage, checks


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def print_validation_report(
    providers: tuple[Provider, ...],
    verbose: bool = True,
) -> tuple[CoverageStats, CheckStats]:
    coverage, checks = compute_stats(providers)
    totals = _count_totals(providers)

    def _print_coverage_table() -> None:
        print("\n# Field coverage (% non-null):")
        print(f"{'field':<40} {'present':>8} {'coverage':>10}")
        print("-" * 61)
        for level, fields in [
            ("provider", _PROVIDER_FIELDS),
            ("care type", _CARE_TYPE_FIELDS + _CARE_TYPE_COVERAGE_ONLY_FIELDS),
            ("opening hours", _OH_FIELDS),
        ]:
            section = {f: coverage[f] for f in fields if f in coverage}
            if not section:
                continue
            print(f"-- {level.title()} Fields --")
            for field, (present, pct) in sorted(
                section.items(), key=lambda x: x[1][1], reverse=True
            ):
                print(f"{field:<40} {present:>8,} {pct:>9.1f}%")
        print("-" * 61)
        all_present = sum(n for n, _ in coverage.values())
        all_possible = sum(totals[f] for f in coverage)
        print(
            f"{'TOTAL':<40} {all_present:>8,} {all_present / all_possible * 100:>9.1f}%"
        )

    def _print_checks_table() -> None:
        print("\n# Validation & checks (% passing):")
        print(f"{'item':<50} {'passing':>8} {'rate':>11}")
        print("-" * 72)
        for item, (n, pct) in sorted(
            checks.items(), key=lambda x: x[1][1], reverse=True
        ):
            print(f"{item:<50} {n:>8,} {pct:>10.1f}%")
        print("-" * 72)
        total_passing = sum(n for n, _ in checks.values())
        total_applicable = sum(totals[c] for c in checks)
        print(
            f"{'TOTAL':<50} {total_passing:>8,} {total_passing / total_applicable * 100:>10.1f}%"
        )

    if verbose:
        _print_coverage_table()
        _print_checks_table()

    return coverage, checks


# ---------------------------------------------------------------------------
# Multi-version comparison
# ---------------------------------------------------------------------------


def _make_row(widths: list[int]):
    def _row(cells: list[str]) -> str:
        return "| " + " | ".join(c.ljust(w) for c, w in zip(cells, widths)) + " |"

    return _row


def _stat_total(d: dict[str, tuple[int, float]]) -> tuple[int, int, float] | None:
    if not d:
        return None
    num = sum(n for n, _ in d.values())
    denom = round(sum(n / (pct / 100) for n, pct in d.values() if pct > 0))
    return (num, denom, num / denom * 100) if denom > 0 else None


def _collect_versions(
    versions: list[int],
    lad25cd: str | None,
) -> tuple[
    dict[str, CoverageStats],
    dict[str, CheckStats],
    dict[str, CheckStats],
    dict[str, int],
]:
    per_cov: dict[str, CoverageStats] = {}
    per_chk_cm: dict[str, CheckStats] = {}
    per_chk_noncm: dict[str, CheckStats] = {}
    per_services: dict[str, int] = {}
    for v in versions:
        label = f"v{v}"
        providers = load_data(DATA_ROOT / label, verbose=False, lad25cd=lad25cd)
        cov, _ = compute_stats(providers)
        cm_providers = tuple(
            p for p in providers if p.institution_type == "childminder"
        )
        noncm_providers = tuple(
            p for p in providers if p.institution_type != "childminder"
        )
        _, chk_cm = compute_stats(cm_providers)
        _, chk_noncm = compute_stats(noncm_providers)
        per_cov[label] = cov
        per_chk_cm[label] = chk_cm
        per_chk_noncm[label] = chk_noncm
        per_services[label] = sum(len(p.care_types) for p in providers)
    return per_cov, per_chk_cm, per_chk_noncm, per_services


def _print_summary_table(title: str, versions: list[int], lad25cd: str | None) -> None:
    per_cov, per_chk_cm, per_chk_noncm, per_services = _collect_versions(
        versions, lad25cd
    )
    cols = [
        "Version",
        "Notes",
        "Services",
        "Coverage (%)",
        "Non-CM Val (%)",
        "CM Val (%)",
        "Score",
    ]
    widths = [10, 20, 10, 13, 15, 12, 10]
    row = _make_row(widths)
    print(f"### {title}")
    print(row(cols))
    print("| " + " | ".join("-" * w for w in widths) + " |")
    for lbl in [f"v{v}" for v in versions]:
        cov_total = _stat_total(per_cov[lbl])
        noncm_total = _stat_total(per_chk_noncm[lbl])
        cm_total = _stat_total(per_chk_cm[lbl])
        services = per_services[lbl]
        cov_pct = cov_total[2] if cov_total else None
        noncm_pct = noncm_total[2] if noncm_total else None
        cm_pct = cm_total[2] if cm_total else None
        score_vals = [x for x in [cov_pct, noncm_pct, cm_pct] if x is not None]
        score = sum(score_vals) / len(score_vals) if len(score_vals) == 3 else None
        print(
            row(
                [
                    lbl,
                    "",
                    f"{services:,}",
                    f"{cov_pct:.1f}" if cov_pct is not None else "N/A",
                    f"{noncm_pct:.1f}" if noncm_pct is not None else "N/A",
                    f"{cm_pct:.1f}" if cm_pct is not None else "N/A",
                    f"{score:.1f}" if score is not None else "N/A",
                ]
            )
        )


def _print_region_table(latest_dir: Path, latest_label: str) -> None:
    cols = [
        "Region",
        "Services",
        "Coverage (%)",
        "Non-CM Val (%)",
        "CM Val (%)",
        "Score",
    ]
    widths = [30, 10, 13, 15, 12, 10]
    row = _make_row(widths)
    print(f"\n\n### By Region ({latest_label})")
    print(row(cols))
    print("| " + " | ".join("-" * w for w in widths) + " |")
    table_rows = []
    for region_name, code in BETA_REGION_CODES.items():
        providers = load_data(latest_dir, verbose=False, lad25cd=code)
        cov, _ = compute_stats(providers)
        cm_providers = tuple(
            p for p in providers if p.institution_type == "childminder"
        )
        noncm_providers = tuple(
            p for p in providers if p.institution_type != "childminder"
        )
        _, chk_cm = compute_stats(cm_providers)
        _, chk_noncm = compute_stats(noncm_providers)
        services = sum(len(p.care_types) for p in providers)
        cov_pct = _stat_total(cov)
        cov_pct = cov_pct[2] if cov_pct else None
        noncm_pct = _stat_total(chk_noncm)
        noncm_pct = noncm_pct[2] if noncm_pct else None
        cm_pct = _stat_total(chk_cm)
        cm_pct = cm_pct[2] if cm_pct else None
        score_vals = [x for x in [cov_pct, noncm_pct, cm_pct] if x is not None]
        score = sum(score_vals) / len(score_vals) if len(score_vals) == 3 else None
        table_rows.append(
            (
                score or 0,
                row(
                    [
                        region_name,
                        f"{services:,}",
                        f"{cov_pct:.1f}" if cov_pct is not None else "N/A",
                        f"{noncm_pct:.1f}" if noncm_pct is not None else "N/A",
                        f"{cm_pct:.1f}" if cm_pct is not None else "N/A",
                        f"{score:.1f}" if score is not None else "N/A",
                    ]
                ),
            )
        )
    for _, r in sorted(table_rows, key=lambda x: x[0], reverse=True):
        print(r)


def run_all_versions() -> None:
    versions = sorted(_get_current_version_numbers())
    if not versions:
        raise FileNotFoundError(f"No versioned data directories found in {DATA_ROOT}")
    latest_label = f"v{max(versions)}"
    latest_dir = DATA_ROOT / latest_label
    _print_summary_table("By Version", versions, lad25cd=None)
    _print_region_table(latest_dir, latest_label)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) > 1:
        version = sys.argv[1]
        parquet_dir = DATA_ROOT / version
        lad25cd = None
        if len(sys.argv) > 2:
            region_arg = sys.argv[2].lower()
            matched = {
                k: v for k, v in BETA_REGION_CODES.items() if region_arg in k.lower()
            }
            if not matched:
                print(
                    f"Unknown region '{sys.argv[2]}'. Known regions: {', '.join(BETA_REGION_CODES)}",
                    file=sys.stderr,
                )
                sys.exit(1)
            if len(matched) > 1:
                print(
                    f"Ambiguous region '{sys.argv[2]}'. Matches: {', '.join(matched)}",
                    file=sys.stderr,
                )
                sys.exit(1)
            region_name, lad25cd = next(iter(matched.items()))
            print(f"Filtering to region: {region_name} ({lad25cd})")
        print(f"Using data from {parquet_dir}")
        providers = load_data(parquet_dir, lad25cd=lad25cd)
        print_validation_report(providers)
    else:
        run_all_versions()
