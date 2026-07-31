import json
import os
import shutil
from datetime import time
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from dagster import asset, AssetExecutionContext, Config, Failure, MetadataValue

from bsil_pipeline.automation import PIPELINE_CONDITION
from bsil_pipeline.resources.postgres import BsilPostgresResource
from bsil_pipeline.spatial_index.schema import SPATIAL_INDEX_SCHEMA


class ExportConfig(Config):
    output_dir: str = "/opt/dagster/app/output/app"
    include_metadata: bool = (
        os.environ.get("EXPORT_INCLUDE_METADATA", "false").lower() == "true"
    )


def _decimal_or_none(v) -> float | None:
    """Convert a Decimal (or numeric) to float, or return None."""
    if v is None:
        return None
    return float(v)


def _format_time(t) -> str | None:
    """Format a TIME value as 'HH:MM' string."""
    if t is None:
        return None
    if isinstance(t, time):
        return t.strftime("%H:%M")
    # psycopg may return a string directly
    return str(t)[:5]


def _build_fees(
    fee_rows: list[tuple], col_names: list[str], include_metadata: bool = False
):
    """Reconstruct the fees dict from fee_rate rows.

    Flat-rate (age_band='all'): { "perSession": 6.5 }
    Age-banded: { "under2": { "morningSession": 55, ... }, ... }

    Returns (fees, fee_metadata) when include_metadata is True, else just fees.
    """
    fees = {}
    fee_metadata = {}
    # Map DB column names to JSON camelCase keys
    session_key_map = {
        "morning_session": "morningSession",
        "afternoon_session": "afternoonSession",
        "full_day": "fullDay",
        "per_session": "perSession",
        "per_hour": "perHour",
        "per_day": "perDay",
    }

    for row in fee_rows:
        row_dict = dict(zip(col_names, row))
        age_band = row_dict["age_band"]

        band_fees = {}
        for db_col, json_key in session_key_map.items():
            val = _decimal_or_none(row_dict.get(db_col))
            if val is not None:
                band_fees[json_key] = val

        if age_band == "all":
            # Flat-rate: merge directly into fees dict
            fees.update(band_fees)
        else:
            fees[age_band] = band_fees

        if include_metadata:
            raw = row_dict.get("metadata")
            meta = raw if isinstance(raw, dict) else {}
            if meta:
                fee_metadata[age_band] = meta

    if include_metadata:
        return fees, fee_metadata
    return fees


def _build_care_type(cur, ct_row: dict, include_metadata: bool = False) -> dict:
    """Build one care type entry from a care_types row + child tables."""
    ct_id = ct_row["id"]
    result = {"type": ct_row["care_type"]}

    # URLs (only present when different from provider-level)
    if ct_row.get("website"):
        result["website"] = ct_row["website"]
    if ct_row.get("fis_url"):
        result["fisUrl"] = ct_row["fis_url"]

    # Opening hours
    _DAY_COLS = [
        "monday",
        "tuesday",
        "wednesday",
        "thursday",
        "friday",
        "saturday",
        "sunday",
    ]
    _DAY_NUMS = {
        "monday": "1",
        "tuesday": "2",
        "wednesday": "3",
        "thursday": "4",
        "friday": "5",
        "saturday": "6",
        "sunday": "7",
    }
    cur.execute(
        """
        SELECT monday, tuesday, wednesday, thursday, friday,
               saturday, sunday, open, close
        FROM published.opening_hours
        WHERE care_type_id = %s ORDER BY id
        """,
        (ct_id,),
    )
    oh_rows = cur.fetchall()
    if oh_rows:
        result["openingHours"] = []
        for r in oh_rows:
            # r is a tuple: (mon, tue, wed, thu, fri, sat, sun, open, close)
            day_bools = dict(zip(_DAY_COLS, r[:7]))
            days = "".join(_DAY_NUMS[d] for d in _DAY_COLS if day_bools[d])
            result["openingHours"].append(
                {
                    "days": days,
                    "open": _format_time(r[7]),
                    "close": _format_time(r[8]),
                }
            )

    # Operating weeks
    if ct_row.get("operating_weeks_per_year") is not None:
        result["operatingWeeksPerYear"] = ct_row["operating_weeks_per_year"]

    # Fees
    cur.execute(
        """
        SELECT age_band, morning_session, afternoon_session, full_day,
               per_session, per_hour, per_day, metadata
        FROM published.fee_rates WHERE care_type_id = %s ORDER BY id
        """,
        (ct_id,),
    )
    fee_col_names = [desc[0] for desc in cur.description]
    fee_rows = cur.fetchall()
    if fee_rows:
        if include_metadata:
            fees, fee_meta = _build_fees(fee_rows, fee_col_names, include_metadata=True)
            result["fees"] = fees
            if fee_meta:
                result["_feeMetadata"] = fee_meta
        else:
            result["fees"] = _build_fees(fee_rows, fee_col_names)

    # Additional charges
    cur.execute(
        """
        SELECT item, cost, unit, description
        FROM published.additional_charges WHERE care_type_id = %s ORDER BY id
        """,
        (ct_id,),
    )
    charges = []
    for row in cur.fetchall():
        charges.append(
            {
                "item": row[0],
                "cost": _decimal_or_none(row[1]),
                "unit": row[2],
                "description": row[3],
            }
        )
    result["additionalCharges"] = charges

    # Session hours
    sh_morning = _decimal_or_none(ct_row.get("session_hours_morning"))
    sh_afternoon = _decimal_or_none(ct_row.get("session_hours_afternoon"))
    sh_full_day = _decimal_or_none(ct_row.get("session_hours_full_day"))
    if sh_morning is not None or sh_afternoon is not None or sh_full_day is not None:
        session_hours = {}
        if sh_morning is not None:
            session_hours["morning"] = sh_morning
        if sh_afternoon is not None:
            session_hours["afternoon"] = sh_afternoon
        if sh_full_day is not None:
            session_hours["fullDay"] = sh_full_day
        result["sessionHours"] = session_hours

    # Eligible age range
    age_range = {}
    if ct_row.get("eligible_min_months") is not None:
        age_range["minMonths"] = ct_row["eligible_min_months"]
    if ct_row.get("eligible_min_years") is not None:
        age_range["minYears"] = ct_row["eligible_min_years"]
    if ct_row.get("eligible_max_years") is not None:
        age_range["maxYears"] = ct_row["eligible_max_years"]
    if age_range:
        result["eligibleAgeRange"] = age_range

    # Eligible attendees only
    result["eligibleAttendeesOnly"] = ct_row.get("eligible_attendees_only", False)

    # Eligible institutions
    institutions = ct_row.get("eligible_institutions") or []
    result["eligibleInstitutions"] = list(institutions)

    # Eligible other
    other = ct_row.get("eligible_other") or []
    result["eligibleOther"] = list(other)

    # Funded hours accepted
    if ct_row.get("funded_hours_accepted") is not None:
        result["fundedHoursAccepted"] = ct_row["funded_hours_accepted"]

    # Waiting list
    cur.execute(
        """
        SELECT age_band, weeks, months
        FROM published.waiting_list_entries WHERE care_type_id = %s ORDER BY id
        """,
        (ct_id,),
    )
    wl_rows = cur.fetchall()
    if wl_rows:
        waiting_list = {}
        for row in wl_rows:
            entry = {}
            if row[1] is not None:
                entry["weeks"] = row[1]
            if row[2] is not None:
                entry["months"] = row[2]
            waiting_list[row[0]] = entry
        result["waitingList"] = waiting_list

    # Minimum commitment
    no_min = ct_row.get("no_minimum_commitment", False)
    mc_amount = ct_row.get("min_commitment_amount")
    mc_unit = ct_row.get("min_commitment_unit")
    mc_duration = ct_row.get("min_commitment_duration")

    if no_min:
        result["minimumCommitment"] = False
    elif mc_amount is not None or mc_unit is not None or mc_duration is not None:
        commitment = {}
        if mc_amount is not None:
            commitment["amount"] = mc_amount
        if mc_unit is not None:
            commitment["unitPerWeek"] = mc_unit
        if mc_duration is not None:
            commitment["duration"] = mc_duration
        result["minimumCommitment"] = commitment

    # Notes
    cur.execute(
        """
        SELECT note_type, description
        FROM published.care_type_notes WHERE care_type_id = %s ORDER BY id
        """,
        (ct_id,),
    )
    notes = []
    for row in cur.fetchall():
        notes.append({"type": row[0], "description": row[1]})
    if notes:
        result["notes"] = notes

    # Care type metadata
    if include_metadata:
        raw = ct_row.get("metadata")
        meta = raw if isinstance(raw, dict) else {}
        if meta:
            result["_metadata"] = meta

    return result


def _export_provider(cur, provider_row: dict, include_metadata: bool = False) -> dict:
    """Build the full JSON dict for one provider."""
    p = provider_row
    result = {
        "id": f"p{p['id']}",
        "name": p["name"],
        "institutionType": p.get("institution_type"),
        "lad25cd": p.get("lad25cd"),
    }

    # Address
    address = {}
    if p.get("address_line1") is not None:
        address["line1"] = p["address_line1"]
    if p.get("address_line2") is not None:
        address["line2"] = p["address_line2"]
    if p.get("city") is not None:
        address["city"] = p["city"]
    if p.get("postcode") is not None:
        address["postcode"] = p["postcode"]
    if address:
        result["address"] = address

    if p["latitude"] is not None:
        result["latitude"] = p["latitude"]
    if p["longitude"] is not None:
        result["longitude"] = p["longitude"]

    # Bounding box for providers without point coordinates
    if p["latitude"] is None and p.get("bbox_geo_type"):
        bbox = {
            "geoType": p["bbox_geo_type"],
            "geoCode": p["bbox_geo_code"],
        }
        if p.get("bbox_north") is not None:
            bbox["north"] = _decimal_or_none(p["bbox_north"])
            bbox["south"] = _decimal_or_none(p["bbox_south"])
            bbox["east"] = _decimal_or_none(p["bbox_east"])
            bbox["west"] = _decimal_or_none(p["bbox_west"])
        result["boundingBox"] = bbox

    # Contact info
    if p.get("phone") is not None:
        result["phone"] = p["phone"]
    if p.get("email") is not None:
        result["email"] = p["email"]
    if p.get("website") is not None:
        result["website"] = p["website"]
    if p.get("fis_url") is not None:
        result["fisUrl"] = p["fis_url"]

    # Ofsted
    ofsted = {}
    if p.get("ofsted_framework") is not None:
        ofsted["framework"] = p["ofsted_framework"]
    if p.get("ofsted_legacy_rating") is not None:
        ofsted["legacyRating"] = p["ofsted_legacy_rating"]
    if p.get("ofsted_inspection_date") is not None:
        ofsted["inspectionDate"] = str(p["ofsted_inspection_date"])
    if p.get("ofsted_safeguarding_met") is not None:
        ofsted["safeguardingMet"] = p["ofsted_safeguarding_met"]
    # Report-card graded properties
    _GRADE_FIELDS = [
        ("ofsted_achievement", "achievement"),
        ("ofsted_curriculum_and_teaching", "curriculumAndTeaching"),
        ("ofsted_behaviour_attitudes_routines", "behaviourAttitudesRoutines"),
        ("ofsted_childrens_welfare_wellbeing", "childrensWelfareWellbeing"),
        ("ofsted_attendance_and_behaviour", "attendanceAndBehaviour"),
        ("ofsted_personal_development_wellbeing", "personalDevelopmentWellbeing"),
        ("ofsted_inclusion", "inclusion"),
        ("ofsted_leadership_and_governance", "leadershipAndGovernance"),
        ("ofsted_early_years", "earlyYears"),
        ("ofsted_sixth_form", "sixthForm"),
    ]
    for db_col, json_key in _GRADE_FIELDS:
        val = p.get(db_col)
        if val is not None:
            ofsted[json_key] = val
    # Legacy sub-grades
    _LEGACY_SUBGRADE_FIELDS = [
        ("ofsted_legacy_quality_of_education", "qualityOfEducation"),
        ("ofsted_legacy_behaviour_and_attitudes", "behaviourAndAttitudes"),
        ("ofsted_legacy_personal_development", "personalDevelopment"),
        ("ofsted_legacy_leadership_and_management", "leadershipAndManagement"),
        ("ofsted_legacy_early_years", "earlyYears"),
        ("ofsted_legacy_sixth_form", "sixthForm"),
    ]
    legacy_subgrades = {}
    for db_col, json_key in _LEGACY_SUBGRADE_FIELDS:
        val = p.get(db_col)
        if val is not None:
            legacy_subgrades[json_key] = val
    if legacy_subgrades:
        ofsted["legacySubGrades"] = legacy_subgrades
    if p.get("ofsted_ccr_met") is not None:
        ofsted["ccrMet"] = p["ofsted_ccr_met"]
    if p.get("ofsted_vcr_met") is not None:
        ofsted["vcrMet"] = p["ofsted_vcr_met"]
    if p.get("ofsted_oosc_met") is not None:
        ofsted["ooscMet"] = p["ofsted_oosc_met"]
    if ofsted:
        result["ofsted"] = ofsted

    # CMA inspection data
    cma = {}
    if p.get("cma_agency") is not None:
        cma["agency"] = p["cma_agency"]
    if p.get("cma_qa_grading") is not None:
        cma["qaGrading"] = p["cma_qa_grading"]
    if p.get("cma_inspection_date") is not None:
        cma["inspectionDate"] = str(p["cma_inspection_date"])
    if cma:
        result["cma"] = cma

    if p.get("registered_places") is not None:
        result["registeredPlaces"] = p["registered_places"]

    # Staff
    staff = {}
    grad = _decimal_or_none(p.get("staff_graduate_percentage"))
    if grad is not None:
        staff["graduatePercentage"] = grad
    turnover = _decimal_or_none(p.get("staff_turnover_percentage"))
    if turnover is not None:
        staff["turnoverPercentage"] = turnover
    if staff:
        result["staff"] = staff

    # Facilities
    facilities = {}
    if p.get("has_garden") is not None:
        facilities["hasGarden"] = p["has_garden"]
    if p.get("has_kitchen") is not None:
        facilities["hasKitchen"] = p["has_kitchen"]
    if facilities:
        result["facilities"] = facilities

    # Care types
    cur.execute(
        """
        SELECT id, care_type,
               operating_weeks_per_year,
               session_hours_morning, session_hours_afternoon, session_hours_full_day,
               eligible_min_months, eligible_min_years, eligible_max_years,
               eligible_attendees_only, eligible_institutions, eligible_other,
               funded_hours_accepted,
               min_commitment_amount, min_commitment_unit, min_commitment_duration,
               no_minimum_commitment, website, fis_url, metadata
        FROM published.care_types WHERE provider_id = %s ORDER BY id
        """,
        (p["id"],),
    )
    ct_col_names = [desc[0] for desc in cur.description]
    ct_rows = cur.fetchall()

    care_types = []
    for ct_row_tuple in ct_rows:
        ct_row = dict(zip(ct_col_names, ct_row_tuple))
        care_types.append(
            _build_care_type(cur, ct_row, include_metadata=include_metadata)
        )

    if care_types:
        result["careTypes"] = care_types

    # Provider-level metadata
    if include_metadata:
        raw = p.get("metadata")
        meta = raw if isinstance(raw, dict) else {}
        if meta:
            result["_metadata"] = meta

    return result


def export_providers_to_dir(
    cur, output_dir: Path, include_metadata: bool = False
) -> int:
    """Export all providers from DB to JSON files. Returns provider count."""
    output_dir.mkdir(parents=True, exist_ok=True)

    providers_dir = output_dir / "providers"
    if providers_dir.exists():
        for child in providers_dir.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    else:
        providers_dir.mkdir()

    cur.execute(
        """
        SELECT p.id, p.name,
               p.address_line1, p.address_line2, p.city, p.postcode,
               p.latitude, p.longitude,
               p.bbox_geo_type, p.bbox_geo_code,
               p.phone, p.email, p.website, p.fis_url,
               p.ofsted_legacy_rating, p.ofsted_inspection_date,
               p.ofsted_framework, p.ofsted_safeguarding_met,
               p.ofsted_achievement, p.ofsted_curriculum_and_teaching,
               p.ofsted_behaviour_attitudes_routines, p.ofsted_childrens_welfare_wellbeing,
               p.ofsted_attendance_and_behaviour, p.ofsted_personal_development_wellbeing,
               p.ofsted_inclusion, p.ofsted_leadership_and_governance,
               p.ofsted_early_years, p.ofsted_sixth_form,
               p.ofsted_legacy_quality_of_education, p.ofsted_legacy_behaviour_and_attitudes,
               p.ofsted_legacy_personal_development, p.ofsted_legacy_leadership_and_management,
               p.ofsted_legacy_early_years, p.ofsted_legacy_sixth_form,
               p.ofsted_ccr_met, p.ofsted_vcr_met, p.ofsted_oosc_met,
               p.cma_agency, p.cma_qa_grading, p.cma_inspection_date,
               p.registered_places,
               p.staff_graduate_percentage, p.staff_turnover_percentage,
               p.has_garden, p.has_kitchen,
               p.institution_type, p.lad25cd, p.metadata,
               bb.bbox_north, bb.bbox_south, bb.bbox_east, bb.bbox_west
        FROM published.providers p
        LEFT JOIN published.bounding_boxes bb
            ON bb.geo_type = p.bbox_geo_type AND bb.geo_code = p.bbox_geo_code
        WHERE NOT p.is_insufficient
        ORDER BY p.id
        """
    )
    col_names = [desc[0] for desc in cur.description]
    provider_rows = cur.fetchall()

    count = 0

    for row_tuple in provider_rows:
        provider_row = dict(zip(col_names, row_tuple))
        provider_data = _export_provider(
            cur, provider_row, include_metadata=include_metadata
        )

        # Write individual provider file
        provider_file = providers_dir / f"{provider_data['id']}.json"
        provider_file.write_text(
            json.dumps(provider_data, indent=2, ensure_ascii=False) + "\n"
        )

        count += 1

    return count


@asset(
    group_name="bsil",
    deps=["publish_providers", "validate_published"],
    automation_condition=PIPELINE_CONDITION,
)
def export_providers(
    context: AssetExecutionContext,
    config: ExportConfig,
    bsil_postgres: BsilPostgresResource,
):
    """Export provider data from the DB to per-provider JSON files."""
    output_dir = Path(config.output_dir)
    metadata_tag = context.run.tags.get("METADATA")
    if metadata_tag is None:
        raise Failure("METADATA tag is required. Use METADATA=true or METADATA=false.")
    include_metadata = metadata_tag.lower() == "true"
    context.log.info(f"METADATA={metadata_tag}, include_metadata={include_metadata}")

    with bsil_postgres.get_connection() as conn:
        with conn.cursor() as cur:
            count = export_providers_to_dir(
                cur, output_dir, include_metadata=include_metadata
            )

            # Check for validation failures
            cur.execute(
                "SELECT count(*) FROM published.providers "
                "WHERE metadata->'validation'->>'pass' = 'false'"
            )
            fail_count = cur.fetchone()[0]
            if fail_count > 0:
                context.log.warning(
                    f"{fail_count} providers failed Zod validation - "  # nosec B608
                    f"inspect with: SELECT id, metadata->'validation' "
                    f"FROM published.providers "
                    f"WHERE metadata->'validation'->>'pass' = 'false'"
                )

    context.log.info(f"Exported {count} providers to {output_dir}")
    return MetadataValue.int(count)


@asset(
    group_name="bsil", deps=["spatial_index"], automation_condition=PIPELINE_CONDITION
)
def export_spatial_index(
    context: AssetExecutionContext,
    config: ExportConfig,
    bsil_postgres: BsilPostgresResource,
):
    """Export spatial index from published table to parquet file."""
    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "spatial_index.parquet"

    with bsil_postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM published.spatial_index "
                "ORDER BY provider_id, caretype_index"
            )
            col_names = [desc[0] for desc in cur.description]
            rows = cur.fetchall()

    columns = {name: [] for name in col_names}
    for row in rows:
        for name, val in zip(col_names, row):
            columns[name].append(val)

    arrays = []
    for field in SPATIAL_INDEX_SCHEMA:
        arrays.append(pa.array(columns[field.name], type=field.type))

    table = pa.table(arrays, schema=SPATIAL_INDEX_SCHEMA)
    pq.write_table(table, output_path)

    context.log.info(
        f"Wrote spatial_index.parquet: {len(table)} rows, "
        f"{output_path.stat().st_size} bytes"
    )
    return MetadataValue.int(len(table))
