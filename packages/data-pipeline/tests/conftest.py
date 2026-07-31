"""Shared test helpers for loading fixture data through the draft->publish pipeline."""

import json
from pathlib import Path

from bsil_pipeline.assets.fixtures import create_draft_tables, load_fixture_provider
from bsil_pipeline.assets.publish import _table_exists


def _run_publish_sql(conn):
    """Run the publish SQL to copy draft -> published.

    Simplified version of publish_providers that skips archiving and
    optional draft tables (linkage, provider_sources) that fixtures don't use.
    """
    with conn.cursor() as cur:
        # Truncate published tables in reverse dependency order
        cur.execute("TRUNCATE published.opening_hours CASCADE")
        cur.execute("TRUNCATE published.care_type_notes CASCADE")
        cur.execute("TRUNCATE published.waiting_list_entries CASCADE")
        cur.execute("TRUNCATE published.additional_charges CASCADE")
        cur.execute("TRUNCATE published.fee_rates CASCADE")
        cur.execute("TRUNCATE published.care_types CASCADE")
        cur.execute("TRUNCATE published.providers CASCADE")
        cur.execute("TRUNCATE published.bounding_boxes CASCADE")

        # 1. Providers
        cur.execute(
            """
            INSERT INTO published.providers (
                id, name,
                address_line1, address_line2, city, postcode,
                latitude, longitude,
                bbox_geo_type, bbox_geo_code,
                phone, email, website, fis_url,
                ofsted_legacy_rating, ofsted_inspection_date,
                ofsted_framework, ofsted_safeguarding_met,
                ofsted_achievement, ofsted_curriculum_and_teaching,
                ofsted_behaviour_attitudes_routines, ofsted_childrens_welfare_wellbeing,
                ofsted_attendance_and_behaviour, ofsted_personal_development_wellbeing,
                ofsted_inclusion, ofsted_leadership_and_governance,
                ofsted_early_years, ofsted_sixth_form,
                ofsted_legacy_quality_of_education, ofsted_legacy_behaviour_and_attitudes,
                ofsted_legacy_personal_development, ofsted_legacy_leadership_and_management,
                ofsted_legacy_early_years, ofsted_legacy_sixth_form,
                ofsted_ccr_met, ofsted_vcr_met, ofsted_oosc_met,
                registered_places,
                staff_graduate_percentage, staff_turnover_percentage,
                has_garden, has_kitchen,
                institution_type, lad25cd,
                metadata
            )
            SELECT
                p.bigint_id, p.provider_name,
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
                p.registered_places,
                p.staff_graduate_percentage, p.staff_turnover_percentage,
                p.has_garden, p.has_kitchen,
                p.institution_type, p.lad25cd,
                COALESCE(p.metadata, '{}'::jsonb)
                  || jsonb_build_object('provider_id', p.provider_id)
            FROM draft.providers p
            WHERE p.excluded = false
              AND p.bigint_id IS NOT NULL
              AND p.lad25cd LIKE 'E%%'
            """
        )

        # 2. Care types
        cur.execute(
            """
            INSERT INTO published.care_types (
                provider_id, care_type,
                operating_weeks_per_year,
                session_hours_morning, session_hours_afternoon, session_hours_full_day,
                eligible_min_months, eligible_min_years, eligible_max_years,
                eligible_attendees_only, eligible_institutions, eligible_other,
                funded_hours_accepted,
                min_commitment_amount, min_commitment_unit, min_commitment_duration,
                no_minimum_commitment,
                metadata
            )
            SELECT
                p.bigint_id, ct.care_type,
                ct.operating_weeks_per_year,
                ct.session_hours_morning, ct.session_hours_afternoon, ct.session_hours_full_day,
                ct.eligible_min_months, ct.eligible_min_years, ct.eligible_max_years,
                ct.eligible_attendees_only, ct.eligible_institutions, ct.eligible_other,
                ct.funded_hours_accepted,
                ct.min_commitment_amount, ct.min_commitment_unit, ct.min_commitment_duration,
                ct.no_minimum_commitment,
                COALESCE(ct.metadata, '{}'::jsonb)
            FROM draft.care_types ct
            JOIN draft.providers p ON ct.provider_id = p.provider_id
            WHERE p.excluded = false
              AND p.bigint_id IS NOT NULL
              AND p.lad25cd LIKE 'E%%'
            ORDER BY ct.id
            """
        )

        # 2b. Opening hours
        cur.execute(
            """
            INSERT INTO published.opening_hours (
                care_type_id, monday, tuesday, wednesday, thursday,
                friday, saturday, sunday, open, close
            )
            SELECT
                pub_ct.id, oh.monday, oh.tuesday, oh.wednesday,
                oh.thursday, oh.friday, oh.saturday, oh.sunday,
                oh.open, oh.close
            FROM draft.opening_hours oh
            JOIN draft.care_types dct ON oh.care_type_id = dct.id
            JOIN draft.providers p ON dct.provider_id = p.provider_id
            JOIN published.care_types pub_ct
                ON pub_ct.provider_id = p.bigint_id
               AND pub_ct.care_type = dct.care_type
            WHERE p.excluded = false
              AND p.bigint_id IS NOT NULL
              AND p.lad25cd LIKE 'E%%'
            ORDER BY oh.id
            """
        )

        # 3. Fee rates
        cur.execute(
            """
            INSERT INTO published.fee_rates (
                care_type_id, age_band,
                morning_session, afternoon_session, full_day,
                per_session, per_hour, per_day,
                metadata
            )
            SELECT
                pub_ct.id, fr.age_band,
                fr.morning_session, fr.afternoon_session, fr.full_day,
                fr.per_session, fr.per_hour, fr.per_day,
                COALESCE(fr.metadata, '{}'::jsonb)
            FROM draft.fee_rates fr
            JOIN draft.care_types dct ON fr.care_type_id = dct.id
            JOIN draft.providers p ON dct.provider_id = p.provider_id
            JOIN published.care_types pub_ct
                ON pub_ct.provider_id = p.bigint_id
               AND pub_ct.care_type = dct.care_type
            WHERE p.excluded = false
              AND p.bigint_id IS NOT NULL
              AND p.lad25cd LIKE 'E%%'
            ORDER BY fr.id
            """
        )

        # 4. Additional charges
        if _table_exists(cur, "draft", "additional_charges"):
            cur.execute(
                """
                INSERT INTO published.additional_charges
                    (care_type_id, item, cost, unit, description)
                SELECT pub_ct.id, ac.item, ac.cost, ac.unit, ac.description
                FROM draft.additional_charges ac
                JOIN draft.care_types dct ON ac.care_type_id = dct.id
                JOIN draft.providers p ON dct.provider_id = p.provider_id
                JOIN published.care_types pub_ct
                    ON pub_ct.provider_id = p.bigint_id
                   AND pub_ct.care_type = dct.care_type
                WHERE p.excluded = false
                  AND p.bigint_id IS NOT NULL
                  AND p.lad25cd LIKE 'E%%'
                ORDER BY ac.id
                """
            )

        # 5. Waiting list entries
        if _table_exists(cur, "draft", "waiting_list_entries"):
            cur.execute(
                """
                INSERT INTO published.waiting_list_entries
                    (care_type_id, age_band, weeks, months)
                SELECT pub_ct.id, wl.age_band, wl.weeks, wl.months
                FROM draft.waiting_list_entries wl
                JOIN draft.care_types dct ON wl.care_type_id = dct.id
                JOIN draft.providers p ON dct.provider_id = p.provider_id
                JOIN published.care_types pub_ct
                    ON pub_ct.provider_id = p.bigint_id
                   AND pub_ct.care_type = dct.care_type
                WHERE p.excluded = false
                  AND p.bigint_id IS NOT NULL
                  AND p.lad25cd LIKE 'E%%'
                ORDER BY wl.id
                """
            )

        # 6. Care type notes
        if _table_exists(cur, "draft", "care_type_notes"):
            cur.execute(
                """
                INSERT INTO published.care_type_notes
                    (care_type_id, note_type, description)
                SELECT pub_ct.id, cn.note_type, cn.description
                FROM draft.care_type_notes cn
                JOIN draft.care_types dct ON cn.care_type_id = dct.id
                JOIN draft.providers p ON dct.provider_id = p.provider_id
                JOIN published.care_types pub_ct
                    ON pub_ct.provider_id = p.bigint_id
                   AND pub_ct.care_type = dct.care_type
                WHERE p.excluded = false
                  AND p.bigint_id IS NOT NULL
                  AND p.lad25cd LIKE 'E%%'
                ORDER BY cn.id
                """
            )

    conn.commit()


def load_fixtures_to_published(conn, fixture_ids: list[str], fixtures_dir: Path):
    """Load fixture JSONs into draft tables, then publish to published.

    Shared helper for test_export_round_trip and test_spatial_index.
    """
    counts = {
        "providers": 0,
        "care_types": 0,
        "fee_rates": 0,
        "additional_charges": 0,
        "waiting_list_entries": 0,
        "care_type_notes": 0,
    }

    with conn.cursor() as cur:
        create_draft_tables(cur)

        for fixture_id in fixture_ids:
            fixture_file = fixtures_dir / f"{fixture_id}.json"
            data = json.loads(fixture_file.read_text())
            load_fixture_provider(cur, data, counts)

    conn.commit()

    _run_publish_sql(conn)

    return counts
