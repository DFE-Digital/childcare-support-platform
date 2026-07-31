import re
from datetime import datetime, date, time, timedelta
from typing import NamedTuple

from data_types import OpeningHours, CareType, Provider


class MissingField(NamedTuple):
    field: str


class FailedCheck(NamedTuple):
    check: str
    message: str


ValidationResult = MissingField | FailedCheck


def _parse_time(value: str) -> time | None:
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(value.strip(), fmt).time()
        except ValueError:
            continue
    return None


def _as_dt(t: time) -> datetime:
    return datetime.combine(date.min, t)


# ---------------------------------------------------------------------------
# OpeningHours
# ---------------------------------------------------------------------------


def validate_opening_hours(oh: OpeningHours) -> list[ValidationResult]:
    results: list[ValidationResult] = []

    open_t = _parse_time(oh.open) if oh.open else None
    close_t = _parse_time(oh.close) if oh.close else None

    # Field: open
    if oh.open is None:
        results.append(MissingField("open"))
    elif open_t is None:
        results.append(FailedCheck("open", f"unparseable: {oh.open!r}"))
    elif not (time(5, 30) <= open_t <= time(17, 30)):
        results.append(FailedCheck("open", f"out of range: {oh.open}"))

    # Field: close
    if oh.close is None:
        results.append(MissingField("close"))
    elif close_t is None:
        results.append(FailedCheck("close", f"unparseable: {oh.close!r}"))
    elif not (time(7, 30) <= close_t <= time(19, 0)):
        results.append(FailedCheck("close", f"out of range: {oh.close}"))

    # Row: duration (cross-field: open + close)
    if open_t is not None and close_t is not None:
        duration = _as_dt(close_t) - _as_dt(open_t)
        if duration < timedelta(minutes=45):
            results.append(FailedCheck("duration >= 45 mins", f"{oh.open}–{oh.close}"))
        elif duration > timedelta(hours=12):
            results.append(FailedCheck("duration <= 12 hours", f"{oh.open}–{oh.close}"))

    # Row: at least one day selected
    if not any(
        [
            oh.monday,
            oh.tuesday,
            oh.wednesday,
            oh.thursday,
            oh.friday,
            oh.saturday,
            oh.sunday,
        ]
    ):
        results.append(FailedCheck("at least one day selected", "all days are False"))

    return results


# ---------------------------------------------------------------------------
# CareType
# ---------------------------------------------------------------------------

_VALID_CARE_TYPES = {
    "private_nursery",
    "school_based_nursery",
    "childminder",
    "breakfast_club",
    "free_breakfast_club",
    "after_school_club",
    "holiday_club",
}

# Groups of care types that share validation rules or should be aggregated together.
_CARE_TYPE_GROUPS: dict[str, set[str]] = {
    "breakfast_club": {"breakfast_club", "free_breakfast_club"},
}
_CARE_TYPE_TO_GROUP: dict[str, str] = {
    member: label for label, members in _CARE_TYPE_GROUPS.items() for member in members
}

# Max age by Ofsted register combination. Fallback 14 when no register data.
# EYR = Early Years Register (0–5), CCR = Compulsory Childcare Register (5–8),
# VCR = Voluntary Childcare Register (8–18)
_CHILDMINDER_REGISTER_MAX_YEARS: dict[str, int] = {
    "ALL": 18,
    "EYR only": 5,
    "EYR-CCR": 8,
    "CCR only": 8,
    "EYR-VCR": 18,
    "CCR-VCR": 18,
    "VCR only": 18,
}
_CHILDMINDER_REGISTER_MIN_MONTHS: dict[str, int] = {
    "ALL": 0,
    "EYR only": 0,
    "EYR-CCR": 0,
    "EYR-VCR": 0,
    "CCR only": 60,
    "CCR-VCR": 60,
    "VCR only": 96,
}


def group_care_type(care_type: str) -> str:
    """Return the group label for a care type, or the type itself if not grouped."""
    return _CARE_TYPE_TO_GROUP.get(care_type, care_type)


def validate_care_type(ct: CareType) -> list[ValidationResult]:
    results: list[ValidationResult] = []
    care_type = group_care_type(ct.care_type)

    # Aggregate: care_type valid value
    if ct.care_type is not None and ct.care_type not in _VALID_CARE_TYPES:
        results.append(
            FailedCheck("care_type valid value", f"unknown: {ct.care_type!r}")
        )

    # Field: operating_weeks_per_year
    if ct.operating_weeks_per_year is None:
        results.append(MissingField("operating_weeks_per_year"))
    elif not (1 <= ct.operating_weeks_per_year <= 52):
        results.append(
            FailedCheck(
                "operating_weeks_per_year",
                f"out of range: {ct.operating_weeks_per_year}",
            )
        )
    elif care_type == "holiday_club" and ct.operating_weeks_per_year > 17:
        results.append(
            FailedCheck(
                "operating_weeks_per_year",
                f"holiday club out of range: {ct.operating_weeks_per_year}",
            )
        )
    elif (
        care_type in {"breakfast_club", "after_school_club"}
        and ct.operating_weeks_per_year > 40
    ):
        results.append(
            FailedCheck(
                "operating_weeks_per_year",
                f"school club out of range: {ct.operating_weeks_per_year}",
            )
        )

    # Field: eligible_min_years
    if ct.eligible_min_years is None:
        results.append(MissingField("eligible_min_years"))

    # Field: eligible_max_years
    if ct.eligible_max_years is None:
        results.append(MissingField("eligible_max_years"))

    # Field: eligible_min_months
    if ct.eligible_min_months is None:
        results.append(MissingField("eligible_min_months"))

    # Field: has at least one opening hours slot
    if not ct.opening_hours:
        results.append(MissingField("has at least one opening hours slot"))

    # Row: age range (cross-field: min_years + max_years)
    if ct.eligible_min_years is not None and ct.eligible_max_years is not None:
        if ct.eligible_min_years > ct.eligible_max_years:
            results.append(
                FailedCheck(
                    "eligible_min_years <= eligible_max_years",
                    f"{ct.eligible_min_years} > {ct.eligible_max_years}",
                )
            )

    # Row: age range months (cross-field: min_months + min_years + max_years)
    if ct.eligible_min_months is not None and ct.eligible_max_years is not None:
        min_months = ct.eligible_min_months + (ct.eligible_min_years or 0) * 12
        max_months = ct.eligible_max_years * 12
        if min_months >= max_months:
            results.append(
                FailedCheck(
                    "eligible min age < eligible max age",
                    f"{min_months} months >= {max_months} months",
                )
            )

    # Row: club/holiday min age (cross-field: care_type + eligible_min_years)
    if care_type in {"breakfast_club", "after_school_club", "holiday_club"}:
        if ct.eligible_min_years is not None and ct.eligible_min_years < 4:
            results.append(
                FailedCheck(
                    "club eligible_min_years >= 4",
                    f"{ct.care_type}: eligible_min_years={ct.eligible_min_years}",
                )
            )

    # Row: nursery max age (cross-field: care_type + eligible_max_years)
    if care_type in {"private_nursery"}:
        if ct.eligible_max_years is not None and ct.eligible_max_years > 5:
            results.append(
                FailedCheck(
                    "nursery eligible_max_years <= 5",
                    f"{ct.care_type}: eligible_max_years={ct.eligible_max_years}",
                )
            )

    # Row: childminder max age (derived from Ofsted register combination)
    if care_type == "childminder":
        if ct.ofsted_register_combination is None:
            results.append(
                FailedCheck(
                    "childminder has ofsted_register_combination",
                    "ofsted_register_combination is null",
                )
            )
        else:
            if ct.eligible_max_years is not None:
                max_limit = _CHILDMINDER_REGISTER_MAX_YEARS[
                    ct.ofsted_register_combination
                ]
                if ct.eligible_max_years > max_limit:
                    results.append(
                        FailedCheck(
                            "childminder eligible_max_years matches ofsted",
                            f"{ct.care_type}: eligible_max_years={ct.eligible_max_years} (limit={max_limit})",
                        )
                    )
            if ct.eligible_min_months is not None or ct.eligible_min_years is not None:
                min_months = (ct.eligible_min_months or 0) + (
                    ct.eligible_min_years or 0
                ) * 12
                min_limit = _CHILDMINDER_REGISTER_MIN_MONTHS[
                    ct.ofsted_register_combination
                ]
                if min_months < min_limit:
                    results.append(
                        FailedCheck(
                            "childminder eligible_min_age matches ofsted",
                            f"{ct.care_type}: min_age={min_months} months (limit={min_limit})",
                        )
                    )

    # Row: club opening times (cross-field: care_type + opening_hours slots)
    if care_type == "breakfast_club":
        for oh in ct.opening_hours:
            open_t = _parse_time(oh.open) if oh.open else None
            close_t = _parse_time(oh.close) if oh.close else None
            if open_t is not None and not (time(6, 0) <= open_t <= time(8, 30)):
                results.append(
                    FailedCheck(
                        "breakfast club open 06:00–08:30",
                        f"open={oh.open}",
                    )
                )
            if close_t is not None and not (time(8, 0) <= close_t <= time(10, 0)):
                results.append(
                    FailedCheck(
                        "breakfast club close 08:00–10:00",
                        f"close={oh.close}",
                    )
                )
    elif care_type == "after_school_club":
        for oh in ct.opening_hours:
            open_t = _parse_time(oh.open) if oh.open else None
            close_t = _parse_time(oh.close) if oh.close else None
            if open_t is not None and not (time(14, 0) <= open_t <= time(17, 0)):
                results.append(
                    FailedCheck(
                        "after school club open 14:00–17:00",
                        f"open={oh.open}",
                    )
                )
            if close_t is not None and not (time(15, 0) <= close_t <= time(19, 0)):
                results.append(
                    FailedCheck(
                        "after school club close 15:00–19:00",
                        f"close={oh.close}",
                    )
                )
    elif care_type == "holiday_club":
        for oh in ct.opening_hours:
            open_t = _parse_time(oh.open) if oh.open else None
            close_t = _parse_time(oh.close) if oh.close else None
            if open_t is not None and not (time(7, 0) <= open_t <= time(10, 0)):
                results.append(
                    FailedCheck(
                        "holiday club open 07:00–10:00",
                        f"open={oh.open}",
                    )
                )
            if close_t is not None and not (time(14, 0) <= close_t <= time(19, 0)):
                results.append(
                    FailedCheck(
                        "holiday club close 14:00–19:00",
                        f"close={oh.close}",
                    )
                )

    return results


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------

_VALID_OFSTED_RATINGS = {"Outstanding", "Good", "Requires Improvement", "Inadequate"}
_VALID_OFSTED_FRAMEWORKS = {"legacy", "legacy_transition", "report_card"}
_POSTCODE_RE = re.compile(
    r"^[A-Z]{1,2}[0-9][A-Z0-9]?(?:[ ]?[0-9][A-Z]{2})?$", re.IGNORECASE
)
_PHONE_RE = re.compile(r"^0[0-9]{9,10}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_provider(p: Provider) -> list[ValidationResult]:
    results: list[ValidationResult] = []

    # Specific checks for non-childminders
    if p.institution_type != "childminder":
        results.extend(_validate_non_cm_provider(p))

    # Field: lad25cd
    if p.lad25cd is None:
        results.append(MissingField("lad25cd"))
    elif not re.match(r"^E[0-9]{8}$", p.lad25cd):
        results.append(FailedCheck("lad25cd", f"invalid format: {p.lad25cd!r}"))

    # Field: phone
    if p.phone is not None and not _PHONE_RE.match(p.phone):
        results.append(FailedCheck("phone", f"invalid format: {p.phone!r}"))

    # Field: email
    if p.email is not None and not _EMAIL_RE.match(p.email):
        results.append(FailedCheck("email", f"invalid format: {p.email!r}"))

    # Field: website (optional — only validate format when present)
    if p.website is not None and not (
        p.website.startswith("http://") or p.website.startswith("https://")
    ):
        results.append(FailedCheck("website", f"invalid format: {p.website!r}"))

    # Field: fis_url (optional — only validate format when present)
    if p.fis_url is not None and not (
        p.fis_url.startswith("http://") or p.fis_url.startswith("https://")
    ):
        results.append(FailedCheck("fis_url", f"invalid format: {p.fis_url!r}"))

    # Field: ofsted_legacy_rating
    if p.ofsted_legacy_rating is None:
        results.append(MissingField("ofsted_legacy_rating"))
    elif p.ofsted_legacy_rating not in _VALID_OFSTED_RATINGS:
        results.append(
            FailedCheck("ofsted_legacy_rating", f"unknown: {p.ofsted_legacy_rating!r}")
        )

    # Field: ofsted_inspection_date
    if p.ofsted_inspection_date is None:
        results.append(MissingField("ofsted_inspection_date"))
    else:
        try:
            d = datetime.fromisoformat(str(p.ofsted_inspection_date)).date()
            if d > date.today():
                results.append(FailedCheck("ofsted_inspection_date", "in the future"))
            elif (date.today() - d).days > 7 * 365:
                results.append(
                    FailedCheck(
                        "ofsted_inspection_date",
                        f"stale (>7 years): {p.ofsted_inspection_date}",
                    )
                )
        except (ValueError, TypeError):
            results.append(
                FailedCheck(
                    "ofsted_inspection_date",
                    f"could not parse: {p.ofsted_inspection_date!r}",
                )
            )

    # Field: ofsted_framework
    if p.ofsted_framework is None:
        results.append(MissingField("ofsted_framework"))
    elif p.ofsted_framework not in _VALID_OFSTED_FRAMEWORKS:
        results.append(
            FailedCheck("ofsted_framework", f"unknown: {p.ofsted_framework!r}")
        )

    # Aggregate: ofsted_safeguarding_met set for school inspections
    if p.ofsted_framework in {"report_card", "legacy_transition"}:
        if p.ofsted_safeguarding_met is None:
            results.append(
                FailedCheck(
                    "ofsted_safeguarding_met set when school inspection",
                    f"framework={p.ofsted_framework!r}",
                )
            )

    # Field: registered_places
    if p.registered_places is None:
        results.append(MissingField("registered_places"))
    elif not (1 <= p.registered_places <= 500):
        results.append(
            FailedCheck("registered_places", f"out of range: {p.registered_places}")
        )
    elif (
        any(
            group_care_type(ct.care_type) == "childminder"
            for ct in p.care_types
            if ct.care_type
        )
        and p.registered_places > 15
    ):
        results.append(
            FailedCheck(
                "registered_places", f"childminder out of range: {p.registered_places}"
            )
        )

    # Row: has at least one care type
    if not p.care_types:
        results.append(FailedCheck("has at least one care type", "no care types"))

    # Row: duplicate care types
    seen_care_types: set[str] = set()
    for ct in p.care_types:
        if ct.care_type is not None:
            grouped = group_care_type(ct.care_type)
            if grouped in seen_care_types:
                results.append(
                    FailedCheck(
                        "no duplicate care types", f"duplicate: {ct.care_type!r}"
                    )
                )
            seen_care_types.add(grouped)

    # Row: website != fis_url
    if p.website is not None and p.website == p.fis_url:
        results.append(FailedCheck("website is not FIS", "website and FIS url match"))

    # Row: institution_type vs care_type consistency
    if p.institution_type == "childminder":
        for ct in p.care_types:
            if ct.care_type is not None and ct.care_type != "childminder":
                results.append(
                    FailedCheck(
                        "institution_type matches care_type",
                        f"childminder institution has care_type={ct.care_type!r}",
                    )
                )
    elif p.institution_type is not None:
        for ct in p.care_types:
            if ct.care_type == "childminder":
                results.append(
                    FailedCheck(
                        "institution_type matches care_type",
                        f"{p.institution_type!r} institution has care_type='childminder'",
                    )
                )

    return results


def _validate_non_cm_provider(p: Provider) -> list[ValidationResult]:
    results: list[ValidationResult] = []

    # Field: name (non-cm only — childminders have redacted name)
    if p.name is None:
        results.append(MissingField("non-cm: name"))
    elif len(p.name.strip()) < 2:
        results.append(FailedCheck("non-cm: name", "too short"))

    # Field: postcode (non-cm only — childminders have redacted address)
    if p.postcode is None:
        results.append(MissingField("non-cm: postcode"))
    elif not _POSTCODE_RE.match(p.postcode):
        results.append(
            FailedCheck("non-cm: postcode", f"invalid format: {p.postcode!r}")
        )

    # Field: address_line1 (non-cm only — childminders have redacted address)
    if p.address_line1 is None:
        results.append(MissingField("non-cm: address_line1"))
    elif len(p.address_line1.strip()) < 2:
        results.append(FailedCheck("non-cm: address_line1", "too short"))

    # Field: address_line2 (non-cm only — childminders have redacted address)
    if p.address_line2 is None:
        results.append(MissingField("non-cm: address_line2"))

    # Field: city (non-cm only — childminders have redacted address)
    if p.city is None:
        results.append(MissingField("non-cm: city"))
    elif re.search(r"\d", p.city):
        results.append(FailedCheck("non-cm: city", f"contains digits: {p.city!r}"))

    # Row: has address (cross-field: address_line1 + postcode, non-cm only)
    if p.address_line1 is None or p.postcode is None:
        results.append(
            FailedCheck(
                "non-cm: has address",
                f"missing: {'address_line1' if p.address_line1 is None else 'postcode'}",
            )
        )

    # Field: latitude (non-cm only — childminders have redacted location)
    if p.latitude is None:
        results.append(MissingField("non-cm: latitude"))

    # Field: longitude (non-cm only — childminders have redacted location)
    if p.longitude is None:
        results.append(MissingField("non-cm: longitude"))

    # Row: has lat/lon (cross-field: latitude + longitude, non-cm only)
    if p.latitude is None or p.longitude is None:
        missing = ", ".join(
            f
            for f, v in [("latitude", p.latitude), ("longitude", p.longitude)]
            if v is None
        )
        results.append(FailedCheck("non-cm: has lat lon", f"missing: {missing}"))

    # Row: contact details (cross-field: phone + email + website, non-cm only)
    if p.phone is None and p.email is None and p.website is None:
        results.append(
            FailedCheck("non-cm: has contact details", "no phone, email, or website")
        )

    return results
