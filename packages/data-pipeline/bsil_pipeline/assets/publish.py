"""Dagster assets for promoting draft data to the published schema and cleanup.

publish_providers: copies draft → published with stable bigint IDs.
clean_schemas: drops archived_* and draft schemas.
"""

from datetime import datetime

from dagster import asset, AssetExecutionContext, MetadataValue

from bsil_pipeline.automation import PIPELINE_CONDITION
from bsil_pipeline.resources.postgres import BsilPostgresResource

BETA_LA_CODES = frozenset(
    [
        "E06000022",  # Bath and North East Somerset
        "E06000023",  # Bristol, City of
        "E06000025",  # South Gloucestershire
    ]
)


def _la_filter(run_tags: dict[str, str]) -> tuple[str, list[str]]:
    """Build the LA filter clause for publish queries.

    When BETA=true in run tags, restricts to BETA_LA_CODES.
    Otherwise uses the default England-wide filter.
    """
    if run_tags.get("BETA", "").lower() == "true":
        codes = sorted(BETA_LA_CODES)
        placeholders = ", ".join(["%s"] * len(codes))
        return f"p.lad25cd IN ({placeholders})", codes
    return "p.lad25cd LIKE 'E%%'", []


def _schema_exists(cur, schema_name):
    cur.execute(
        "SELECT EXISTS ("
        "  SELECT 1 FROM information_schema.schemata"
        "  WHERE schema_name = %s"
        ")",
        (schema_name,),
    )
    return cur.fetchone()[0]


def _table_exists(cur, schema_name, table_name):
    cur.execute(
        "SELECT EXISTS ("
        "  SELECT 1 FROM information_schema.tables"
        "  WHERE table_schema = %s AND table_name = %s"
        ")",
        (schema_name, table_name),
    )
    return cur.fetchone()[0]


def _table_has_rows(cur, schema_name, table_name):
    if not _table_exists(cur, schema_name, table_name):
        return False
    cur.execute(f'SELECT EXISTS (SELECT 1 FROM "{schema_name}"."{table_name}")')  # nosec B608
    return cur.fetchone()[0]


def _pick_archive_name(cur):
    """Pick the next archived_YYMMDD_N name."""
    today = datetime.now().strftime("%y%m%d")
    prefix = f"archived_{today}_"

    cur.execute(
        "SELECT schema_name FROM information_schema.schemata "
        "WHERE schema_name LIKE %s ORDER BY schema_name",
        (f"archived_{today}_%",),
    )
    existing = [row[0] for row in cur.fetchall()]

    n = 1
    while f"{prefix}{n}" in existing:
        n += 1
    return f"{prefix}{n}"


def _get_tables(cur, schema_name):
    """Get all table names in a schema (excluding _prisma_migrations)."""
    cur.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = %s AND table_type = 'BASE TABLE' "
        "ORDER BY table_name",
        (schema_name,),
    )
    return [row[0] for row in cur.fetchall()]


def _get_fk_constraints(cur, schema_name):
    """Get FK constraint definitions for recreating them."""
    cur.execute(
        """
        SELECT
            tc.table_name,
            tc.constraint_name,
            kcu.column_name,
            ccu.table_name AS ref_table,
            ccu.column_name AS ref_column,
            rc.delete_rule,
            rc.update_rule
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
            ON tc.constraint_name = kcu.constraint_name
           AND tc.table_schema = kcu.table_schema
        JOIN information_schema.referential_constraints rc
            ON tc.constraint_name = rc.constraint_name
           AND tc.table_schema = rc.constraint_schema
        JOIN information_schema.constraint_column_usage ccu
            ON rc.unique_constraint_name = ccu.constraint_name
           AND rc.unique_constraint_schema = ccu.constraint_schema
        WHERE tc.table_schema = %s
          AND tc.constraint_type = 'FOREIGN KEY'
        ORDER BY tc.table_name, tc.constraint_name
        """,
        (schema_name,),
    )
    return cur.fetchall()


def _action_sql(rule):
    """Map information_schema action rules to SQL clauses."""
    mapping = {
        "CASCADE": "CASCADE",
        "SET NULL": "SET NULL",
        "SET DEFAULT": "SET DEFAULT",
        "RESTRICT": "RESTRICT",
        "NO ACTION": "NO ACTION",
    }
    return mapping.get(rule, "NO ACTION")


def _fix_serial_columns(cur, archive_schema):
    """Ensure all published integer PK columns have a working sequence default.

    After CREATE TABLE ... (LIKE ... INCLUDING ALL), serial column defaults may
    reference sequences in the archived schema, or be missing entirely (if the
    archived table already had a broken default from a prior cycle). This
    function finds any published integer PK column without a proper
    published-schema sequence and creates one.
    """
    cur.execute(
        """
        SELECT
            c.relname AS table_name,
            a.attname AS col_name,
            CASE t.typname
                WHEN 'int8' THEN 'bigserial'
                WHEN 'int4' THEN 'serial'
                WHEN 'int2' THEN 'smallserial'
            END AS serial_type
        FROM pg_attribute a
        JOIN pg_class c ON a.attrelid = c.oid
        JOIN pg_namespace n ON c.relnamespace = n.oid
        JOIN pg_type t ON a.atttypid = t.oid
        -- Only primary key columns
        JOIN pg_index i ON i.indrelid = c.oid AND i.indisprimary
            AND a.attnum = ANY(i.indkey)
        LEFT JOIN pg_attrdef d
            ON d.adrelid = a.attrelid AND d.adnum = a.attnum
        WHERE n.nspname = 'published'
          AND a.attnum > 0
          AND NOT a.attisdropped
          AND t.typname IN ('int2', 'int4', 'int8')
          AND a.attidentity = ''
          -- No default, or default references a non-published sequence
          AND (
              d.adbin IS NULL
              OR pg_get_expr(d.adbin, d.adrelid) NOT LIKE '%%published.%%'
          )
        """,
    )
    for table_name, col_name, serial_type in cur.fetchall():
        seq_name = f"{table_name}_{col_name}_seq"
        # Drop any stale default before creating the new sequence
        cur.execute(
            f'ALTER TABLE "published"."{table_name}" '  # nosec B608
            f'ALTER COLUMN "{col_name}" DROP DEFAULT'
        )
        cur.execute(
            f'DROP SEQUENCE IF EXISTS "published"."{seq_name}"'  # nosec B608
        )
        cur.execute(
            f'CREATE SEQUENCE "published"."{seq_name}" '  # nosec B608
            f"AS {'bigint' if serial_type == 'bigserial' else 'integer'}"
        )
        cur.execute(
            f'ALTER TABLE "published"."{table_name}" '  # nosec B608
            f'ALTER COLUMN "{col_name}" '
            f"SET DEFAULT nextval('published.\"{seq_name}\"')"
        )
        cur.execute(
            f'ALTER SEQUENCE "published"."{seq_name}" '  # nosec B608
            f'OWNED BY "published"."{table_name}"."{col_name}"'
        )


@asset(
    group_name="publish",
    deps=["provider_details", "care_types", "fee_rates"],
    automation_condition=PIPELINE_CONDITION,
)
def publish_providers(
    context: AssetExecutionContext, bsil_postgres: BsilPostgresResource
):
    """Copy draft data into the published schema with stable bigint IDs.

    Archives existing published data before replacing it.
    """
    counts = {
        "providers": 0,
        "care_types": 0,
        "fee_rates": 0,
        "additional_charges": 0,
        "waiting_list_entries": 0,
        "care_type_notes": 0,
        "bounding_boxes": 0,
    }

    with bsil_postgres.get_connection() as conn:
        with conn.cursor() as cur:
            # Verify published schema exists (created by Prisma migrate)
            if not _schema_exists(cur, "published"):
                raise RuntimeError(
                    "published schema does not exist. Run 'make data/migrate' first."
                )

            # Verify draft schema has data
            if not _table_has_rows(cur, "draft", "providers"):
                raise RuntimeError(
                    "draft.providers is empty or missing. Run 'make data/draft' first."
                )

            # Verify bigint_id column exists
            cur.execute(
                "SELECT EXISTS ("
                "  SELECT 1 FROM information_schema.columns"
                "  WHERE table_schema = 'draft' AND table_name = 'providers'"
                "    AND column_name = 'bigint_id'"
                ")"
            )
            if not cur.fetchone()[0]:
                raise RuntimeError(
                    "draft.providers.bigint_id column missing. "
                    "Re-run 'make data/draft' to compute blake2b IDs."
                )

            # --- Archive phase ---
            has_data = _table_has_rows(cur, "published", "providers")

            if has_data:
                archive_name = _pick_archive_name(cur)
                context.log.info(f"Archiving published → {archive_name}")

                # Rename published → archived
                cur.execute(f'ALTER SCHEMA "published" RENAME TO "{archive_name}"')

                # Recreate published schema
                cur.execute('CREATE SCHEMA "published"')

                # Clone table structures from archived
                tables = _get_tables(cur, archive_name)
                for table in tables:
                    cur.execute(
                        f'CREATE TABLE "published"."{table}" '
                        f'(LIKE "{archive_name}"."{table}" INCLUDING ALL)'
                    )

                # Recreate FK constraints
                fks = _get_fk_constraints(cur, archive_name)
                for (
                    table_name,
                    constraint_name,
                    column_name,
                    ref_table,
                    ref_column,
                    delete_rule,
                    update_rule,
                ) in fks:
                    cur.execute(
                        f'ALTER TABLE "published"."{table_name}" '
                        f'ADD CONSTRAINT "{constraint_name}" '
                        f'FOREIGN KEY ("{column_name}") '
                        f'REFERENCES "published"."{ref_table}"("{ref_column}") '
                        f"ON DELETE {_action_sql(delete_rule)} "
                        f"ON UPDATE {_action_sql(update_rule)}"
                    )

                # Copy _prisma_migrations rows
                if _table_exists(cur, archive_name, "_prisma_migrations"):
                    cur.execute(
                        f'INSERT INTO "published"."_prisma_migrations" '  # nosec B608
                        f'SELECT * FROM "{archive_name}"."_prisma_migrations"'
                    )

                conn.commit()
                context.log.info(
                    f"Archived to {archive_name}, "
                    f"recreated published with {len(tables)} tables"
                )
            else:
                context.log.info("published schema is empty, skipping archive")

            # Ensure all serial/bigserial PK columns have working sequence
            # defaults. Runs unconditionally because a prior failed publish
            # may have left tables with broken defaults even when published
            # is now empty (archive committed but copy phase failed).
            _fix_serial_columns(cur, "published")

            # --- Copy phase ---
            la_clause, la_params = _la_filter(context.run.tags)
            context.log.info(
                f"LA filter: beta={len(la_params)} codes {la_params}"
                if la_params
                else "LA filter: all England"
            )
            context.log.info("Copying draft → published")

            # 1. Providers (with linkage + provider_sources metadata)
            has_linkage = _table_exists(cur, "draft", "linkage")
            has_provider_sources = _table_exists(cur, "draft", "provider_sources")

            linkage_join = ""
            linkage_field = "'{}'::jsonb"
            if has_linkage:
                linkage_join = (
                    "LEFT JOIN draft.linkage l "
                    "ON l.provider_id = p.provider_id AND l.lad25cd = p.lad25cd"
                )
                linkage_field = "COALESCE(l.metadata, '{}'::jsonb)"

            ps_join = ""
            ps_field = "'[]'::jsonb"
            if has_provider_sources:
                ps_join = (
                    "LEFT JOIN ("
                    "  SELECT provider_id,"
                    "    jsonb_agg(jsonb_build_object("
                    "      'source', source, 'sourceId', source_id"
                    "    )) AS sources"
                    "  FROM draft.provider_sources"
                    "  GROUP BY provider_id"
                    ") ps_agg ON ps_agg.provider_id = p.provider_id"
                )
                ps_field = "COALESCE(ps_agg.sources, '[]'::jsonb)"

            cur.execute(
                f"""
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
                    cma_agency, cma_qa_grading, cma_inspection_date,
                    registered_places,
                    staff_graduate_percentage, staff_turnover_percentage,
                    has_garden, has_kitchen,
                    institution_type, lad25cd,
                    is_insufficient,
                    metadata
                )
                SELECT
                    p.bigint_id, p.provider_name,
                    CASE WHEN p.metadata->'sources' @> '"tiney"'::jsonb
                         THEN NULL ELSE p.address_line1 END AS address_line1,
                    CASE WHEN p.metadata->'sources' @> '"tiney"'::jsonb
                         THEN NULL ELSE p.address_line2 END AS address_line2,
                    CASE WHEN p.metadata->'sources' @> '"tiney"'::jsonb
                         THEN NULL ELSE p.city END AS city,
                    CASE WHEN p.metadata->'sources' @> '"tiney"'::jsonb
                         THEN regexp_replace(p.postcode, '\\s*\\d[A-Z]{{2}}$', '')
                         ELSE p.postcode END AS postcode,
                    CASE WHEN p.metadata->'sources' @> '"tiney"'::jsonb
                         THEN NULL ELSE p.latitude END AS latitude,
                    CASE WHEN p.metadata->'sources' @> '"tiney"'::jsonb
                         THEN NULL ELSE p.longitude END AS longitude,
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
                    p.institution_type, p.lad25cd,
                    CASE WHEN (
                        (p.provider_name IS NULL OR p.provider_name = 'REDACTED' OR p.provider_name = '')
                        AND p.postcode IS NULL
                        AND p.phone IS NULL
                        AND p.email IS NULL
                        AND p.website IS NULL
                        AND p.fis_url IS NULL
                        AND (p.latitude IS NULL OR p.longitude IS NULL)
                    ) THEN true ELSE false END,
                    COALESCE(p.metadata, '{{}}'::jsonb)
                      || jsonb_build_object('provider_id', p.provider_id)
                      || jsonb_build_object('linkage', {linkage_field})
                      || jsonb_build_object('provider_sources', {ps_field})
                FROM draft.providers p
                {linkage_join}
                {ps_join}
                WHERE p.excluded = false
                  AND p.bigint_id IS NOT NULL
                  AND {la_clause}
                  AND (
                    p.institution_type = 'school_primary'
                    OR EXISTS (SELECT 1 FROM draft.care_types ct2 WHERE ct2.provider_id = p.provider_id)
                  )
                """,  # nosec B608
                la_params,
            )
            counts["providers"] = cur.rowcount
            context.log.info(f"  providers: {counts['providers']}")

            # 2. Care types (with metadata)
            cur.execute(
                f"""
                INSERT INTO published.care_types (
                    provider_id, care_type,
                    operating_weeks_per_year,
                    session_hours_morning, session_hours_afternoon, session_hours_full_day,
                    eligible_min_months, eligible_min_years, eligible_max_years,
                    ofsted_register_combination,
                    eligible_attendees_only, eligible_institutions, eligible_other,
                    funded_hours_accepted,
                    min_commitment_amount, min_commitment_unit, min_commitment_duration,
                    no_minimum_commitment,
                    website, fis_url,
                    metadata
                )
                SELECT
                    p.bigint_id, ct.care_type,
                    ct.operating_weeks_per_year,
                    ct.session_hours_morning, ct.session_hours_afternoon, ct.session_hours_full_day,
                    ct.eligible_min_months, ct.eligible_min_years, ct.eligible_max_years,
                    ct.ofsted_register_combination,
                    ct.eligible_attendees_only, ct.eligible_institutions, ct.eligible_other,
                    ct.funded_hours_accepted,
                    ct.min_commitment_amount, ct.min_commitment_unit, ct.min_commitment_duration,
                    ct.no_minimum_commitment,
                    ct.website, ct.fis_url,
                    COALESCE(ct.metadata, '{{}}'::jsonb)
                FROM draft.care_types ct
                JOIN draft.providers p ON ct.provider_id = p.provider_id
                WHERE p.excluded = false
                  AND p.bigint_id IS NOT NULL
                  AND {la_clause}
                ORDER BY ct.id
                """,  # nosec B608
                la_params,
            )
            counts["care_types"] = cur.rowcount
            context.log.info(f"  care_types: {counts['care_types']}")

            # 2b. Opening hours
            cur.execute(
                f"""
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
                  AND {la_clause}
                ORDER BY oh.id
                """,  # nosec B608
                la_params,
            )
            counts["opening_hours"] = cur.rowcount
            context.log.info(f"  opening_hours: {counts['opening_hours']}")

            # 3. Fee rates (with metadata) — join through care_types to map
            # draft IDs to published IDs by matching on (provider_id, care_type)
            cur.execute(
                f"""
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
                    COALESCE(fr.metadata, '{{}}'::jsonb)
                FROM draft.fee_rates fr
                JOIN draft.care_types dct ON fr.care_type_id = dct.id
                JOIN draft.providers p ON dct.provider_id = p.provider_id
                JOIN published.care_types pub_ct
                    ON pub_ct.provider_id = p.bigint_id
                   AND pub_ct.care_type = dct.care_type
                WHERE p.excluded = false
                  AND p.bigint_id IS NOT NULL
                  AND {la_clause}
                ORDER BY fr.id
                """,  # nosec B608
                la_params,
            )
            counts["fee_rates"] = cur.rowcount
            context.log.info(f"  fee_rates: {counts['fee_rates']}")

            # 4. Additional charges
            if _table_exists(cur, "draft", "additional_charges"):
                cur.execute(
                    f"""
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
                      AND {la_clause}
                    ORDER BY ac.id
                    """,  # nosec B608
                    la_params,
                )
                counts["additional_charges"] = cur.rowcount
                context.log.info(
                    f"  additional_charges: {counts['additional_charges']}"
                )

            # 5. Waiting list entries
            if _table_exists(cur, "draft", "waiting_list_entries"):
                cur.execute(
                    f"""
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
                      AND {la_clause}
                    ORDER BY wl.id
                    """,  # nosec B608
                    la_params,
                )
                counts["waiting_list_entries"] = cur.rowcount
                context.log.info(
                    f"  waiting_list_entries: {counts['waiting_list_entries']}"
                )

            # 6. Care type notes
            if _table_exists(cur, "draft", "care_type_notes"):
                cur.execute(
                    f"""
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
                      AND {la_clause}
                    ORDER BY cn.id
                    """,  # nosec B608
                    la_params,
                )
                counts["care_type_notes"] = cur.rowcount
                context.log.info(f"  care_type_notes: {counts['care_type_notes']}")

            # 7. Bounding boxes
            if _table_exists(cur, "draft", "bounding_boxes"):
                cur.execute(
                    """
                    INSERT INTO published.bounding_boxes
                        (geo_type, geo_code, geo_name,
                         bbox_north, bbox_south, bbox_east, bbox_west)
                    SELECT geo_type, geo_code, geo_name,
                           bbox_north, bbox_south, bbox_east, bbox_west
                    FROM draft.bounding_boxes
                    """
                )
                counts["bounding_boxes"] = cur.rowcount
                context.log.info(f"  bounding_boxes: {counts['bounding_boxes']}")

            conn.commit()

    context.log.info(f"Publish complete: {counts}")
    return {k: MetadataValue.int(v) for k, v in counts.items()}


@asset(group_name="publish")
def clean_schemas(context: AssetExecutionContext, bsil_postgres: BsilPostgresResource):
    """Drop all archived_* and draft schemas."""
    dropped = []

    with bsil_postgres.get_connection() as conn:
        with conn.cursor() as cur:
            # Find archived schemas
            cur.execute(
                "SELECT schema_name FROM information_schema.schemata "
                "WHERE schema_name LIKE 'archived_%' "
                "ORDER BY schema_name"
            )
            archived = [row[0] for row in cur.fetchall()]

            for schema in archived:
                context.log.info(f"Dropping schema: {schema}")
                cur.execute(f'DROP SCHEMA "{schema}" CASCADE')
                dropped.append(schema)

            # Drop draft
            if _schema_exists(cur, "draft"):
                context.log.info("Dropping schema: draft")
                cur.execute("DROP SCHEMA draft CASCADE")
                dropped.append("draft")

            conn.commit()

    context.log.info(f"Dropped {len(dropped)} schemas: {dropped}")
    return {"schemas_dropped": MetadataValue.int(len(dropped))}
