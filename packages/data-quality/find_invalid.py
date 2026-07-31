import sys
from collections import defaultdict
from pathlib import Path

from analyse_parquet import (
    load_data,
    latest_version_dir,
    DATA_ROOT,
    BETA_REGION_CODES,
    _BETA_LAT_BOUNDS,
    _BETA_LNG_BOUNDS,
    _PROVIDER_FIELDS,
    _CARE_TYPE_FIELDS,
    _OH_FIELDS,
    _CARE_TYPE_COVERAGE_ONLY_FIELDS,
    _PROVIDER_CHECKS,
    _CARE_TYPE_CHECKS,
    _OH_CHECKS,
)
from validation import (
    MissingField,
    FailedCheck,
    ValidationResult,
    validate_provider,
    validate_care_type,
    validate_opening_hours,
)


_COVERAGE_FIELDS = set(
    _PROVIDER_FIELDS + _CARE_TYPE_FIELDS + _OH_FIELDS + _CARE_TYPE_COVERAGE_ONLY_FIELDS
)
_CHECK_RULES = set(_PROVIDER_CHECKS + _CARE_TYPE_CHECKS + _OH_CHECKS)


def _matches(result: ValidationResult, rule: str) -> bool:
    if rule in _CHECK_RULES:
        return isinstance(result, FailedCheck) and result.check == rule
    if rule in _COVERAGE_FIELDS:
        return isinstance(result, MissingField) and result.field == rule
    # Unknown rule — match both
    if isinstance(result, MissingField):
        return result.field == rule
    if isinstance(result, FailedCheck):
        return result.check == rule
    return False


def _describe(result: ValidationResult) -> str:
    if isinstance(result, MissingField):
        return "missing"
    if isinstance(result, FailedCheck):
        return f"failed: {result.message}"
    return str(result)


def find_invalid(rule: str, parquet_dir: Path, limit: int = 20) -> None:
    providers = load_data(parquet_dir, verbose=False)

    # Pre-compute cross-provider counts (for uniqueness/geo checks)
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

    _beta_codes = set(BETA_REGION_CODES.values())
    examples: list[tuple[str, str]] = []

    for p in providers:
        p_ctx = f"provider_id={p.provider_id}  name={p.name!r}  address={p.address_line1!r} {p.address_line2!r} {p.city!r}  postcode={p.postcode!r}  website={p.website!r}  fis_url={p.fis_url!r}"

        for r in validate_provider(p):
            if _matches(r, rule):
                examples.append((p_ctx, _describe(r)))

        # Cross-provider checks
        cross: list[FailedCheck] = []
        if p.website is not None and website_counts[p.website] > 5:
            cross.append(
                FailedCheck(
                    "website used <= 5 times",
                    f"shared by {website_counts[p.website]} providers, website={p.website!r}",
                )
            )
        if p.fis_url is not None and fis_url_counts[p.fis_url] > 1:
            cross.append(
                FailedCheck(
                    "fis_url is unique",
                    f"shared by {fis_url_counts[p.fis_url]} providers, fis_url={p.fis_url!r}",
                )
            )
        if p.phone is not None and phone_counts[p.phone] > 5:
            cross.append(
                FailedCheck(
                    "phone used <= 5 times",
                    f"shared by {phone_counts[p.phone]} providers, phone={p.phone!r}",
                )
            )
        if p.email is not None and email_counts[p.email] > 5:
            cross.append(
                FailedCheck(
                    "email used <= 5 times",
                    f"shared by {email_counts[p.email]} providers, email={p.email!r}",
                )
            )
        if (
            p.latitude is not None
            and p.longitude is not None
            and p.institution_type != "childminder"
        ):
            if latlon_counts[(p.latitude, p.longitude)] > 3:
                cross.append(
                    FailedCheck(
                        "geolocation used <= 3 times",
                        f"shared by {latlon_counts[(p.latitude, p.longitude)]} providers, lat={p.latitude} lng={p.longitude}",
                    )
                )
        if p.lad25cd in _beta_codes:
            if p.latitude is not None and not (
                _BETA_LAT_BOUNDS[0] <= p.latitude <= _BETA_LAT_BOUNDS[1]
            ):
                cross.append(
                    FailedCheck("beta region latitude 51\u201352", f"lat={p.latitude}")
                )
            if p.longitude is not None and not (
                _BETA_LNG_BOUNDS[0] <= p.longitude <= _BETA_LNG_BOUNDS[1]
            ):
                cross.append(
                    FailedCheck("beta region longitude -3 to -2", f"lng={p.longitude}")
                )
        for r in cross:
            if _matches(r, rule):
                examples.append((p_ctx, _describe(r)))

        for ct in p.care_types:
            ct_ctx = f"{p_ctx}  care_type={ct.care_type!r}"
            for r in validate_care_type(ct):
                if _matches(r, rule):
                    examples.append((ct_ctx, _describe(r)))

            for oh in ct.opening_hours:
                oh_ctx = f"{ct_ctx}  open={oh.open}  close={oh.close}"
                for r in validate_opening_hours(oh):
                    if _matches(r, rule):
                        examples.append((oh_ctx, _describe(r)))

    total = len(examples)
    showing = min(limit, total)
    print(f"Rule:    {rule!r}")
    print(f"Data:    {parquet_dir}")
    print(f"Failures: {total}  (showing {showing})\n")

    if rule == "website used <= 5 times":
        groups: dict[str, list[str]] = defaultdict(list)
        for p in providers:
            if p.website is not None and website_counts[p.website] > 5:
                groups[p.website].append(
                    f"provider_id={p.provider_id}  name={p.name!r}  address={p.address_line1!r} {p.address_line2!r} {p.city!r}  postcode={p.postcode!r}"
                )
        shown_groups = 0
        for website, members in sorted(groups.items()):
            if shown_groups >= showing:
                break
            print(f"  website={website!r}  ({len(members)} providers)")
            for m in members:
                print(f"    {m}")
            print()
            shown_groups += 1
    elif rule == "geolocation used <= 3 times":
        # Group providers by shared lat/lon
        groups: dict[tuple[float, float], list[str]] = defaultdict(list)
        for p in providers:
            if p.institution_type == "childminder":
                continue
            if p.latitude is not None and p.longitude is not None:
                if latlon_counts[(p.latitude, p.longitude)] > 3:
                    groups[(p.latitude, p.longitude)].append(
                        f"provider_id={p.provider_id}  name={p.name!r}  address={p.address_line1!r} {p.address_line2!r} {p.city!r}  postcode={p.postcode!r}"
                    )
        shown_groups = 0
        for (lat, lon), members in sorted(groups.items()):
            if shown_groups >= showing:
                break
            print(f"  lat={lat}  lng={lon}  ({len(members)} providers)")
            for m in members:
                print(f"    {m}")
            print()
            shown_groups += 1
    else:
        for ctx, desc in examples[:showing]:
            print(f"  {ctx}")
            print(f"    -> {desc}")
            print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: find_invalid.py <rule> [version]", file=sys.stderr)
        sys.exit(1)

    rule = sys.argv[1]
    parquet_dir = DATA_ROOT / sys.argv[2] if len(sys.argv) > 2 else latest_version_dir()
    find_invalid(rule, parquet_dir)
