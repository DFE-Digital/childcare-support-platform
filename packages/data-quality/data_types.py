from dataclasses import dataclass


@dataclass(frozen=True)
class OpeningHours:
    monday: bool
    tuesday: bool
    wednesday: bool
    thursday: bool
    friday: bool
    saturday: bool
    sunday: bool
    open: str  # "HH:MM" or "HH:MM:SS"
    close: str  # "HH:MM" or "HH:MM:SS"


@dataclass(frozen=True)
class CareType:
    provider_id: str
    care_type: str | None
    opening_hours: tuple[OpeningHours, ...]
    operating_weeks_per_year: int | None
    eligible_min_months: int | None
    eligible_min_years: int | None
    eligible_max_years: int | None
    ofsted_register_combination: str | None


@dataclass(frozen=True)
class Provider:
    provider_id: str
    name: str | None
    institution_type: str | None
    lad25cd: str | None
    postcode: str | None
    address_line1: str | None
    address_line2: str | None
    city: str | None
    latitude: float | None
    longitude: float | None
    phone: str | None
    email: str | None
    website: str | None
    fis_url: str | None
    ofsted_legacy_rating: str | None
    ofsted_inspection_date: str | None
    ofsted_framework: str | None
    ofsted_safeguarding_met: bool | None
    registered_places: int | None
    care_types: tuple[CareType, ...]
