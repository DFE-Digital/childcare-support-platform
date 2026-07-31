#!/usr/bin/env python3
"""Exploratory analysis: LA → School Census linkage potential.

Runs SQL queries against the live database to quantify join potential
across three strategies (URN exact, postcode fallback, name similarity).

This is analysis only — no new tables or assets are created.

Usage:
    BSIL_DB_USER=bsil BSIL_DB_PASSWORD=bsil_local python scripts/school_census_linkage_analysis.py
"""

from __future__ import annotations

import os
import sys

import psycopg


def get_connection() -> psycopg.Connection:
    """Create a database connection from env vars."""
    return psycopg.connect(
        host=os.environ.get("BSIL_DB_HOST", "localhost"),
        port=int(os.environ.get("BSIL_DB_PORT", "5432")),
        user=os.environ["BSIL_DB_USER"],
        password=os.environ["BSIL_DB_PASSWORD"],
        dbname=os.environ.get("BSIL_DB_NAME", "bsil"),
        autocommit=True,
    )


def run_query(conn: psycopg.Connection, label: str, sql: str) -> list[tuple]:
    """Run a query and print results."""
    print(f"\n{'=' * 70}")
    print(f"  {label}")
    print(f"{'=' * 70}\n")
    with conn.cursor() as cur:
        cur.execute(sql)
        columns = [desc[0] for desc in cur.description]
        rows = cur.fetchall()

    # Print as table
    col_widths = [
        max(len(str(col)), max((len(str(r[i])) for r in rows), default=0))
        for i, col in enumerate(columns)
    ]

    header = "  ".join(f"{col:<{col_widths[i]}}" for i, col in enumerate(columns))
    print(header)
    print("  ".join("-" * w for w in col_widths))
    for row in rows:
        print("  ".join(f"{str(v):<{col_widths[i]}}" for i, v in enumerate(row)))

    print(f"\n  ({len(rows)} row{'s' if len(rows) != 1 else ''})")
    return rows


def main() -> None:
    conn = get_connection()

    print("\n" + "#" * 70)
    print("#  LA → School Census Linkage Potential — Exploratory Analysis")
    print("#" * 70)

    # ── Query 1: Baseline — school-related LA providers ──
    run_query(
        conn,
        "Q1: School-related LA providers by classification",
        """
        SELECT unnest(classification) AS care_type, count(*) AS n
        FROM la.extract_results
        WHERE classification && ARRAY['school_based_nursery','breakfast_club',
                                       'after_school_club','holiday_club']
        GROUP BY 1 ORDER BY 2 DESC
    """,
    )

    # ── Query 2a: URN overlap — LA URNs in school_census vs ofsted ──
    run_query(
        conn,
        "Q2a: LA URNs that match school_census (vs ofsted.inspections)",
        """
        SELECT
            count(*) AS la_providers_with_school_urn,
            count(*) FILTER (WHERE oi.provider_urn IS NOT NULL) AS also_in_ofsted
        FROM la.extract_results e
        CROSS JOIN LATERAL (
            SELECT e.extracted_data->>'ofsted_urn' AS urn
        ) x
        JOIN dfe.school_census sc ON sc.urn = x.urn
        LEFT JOIN ofsted.inspections oi ON oi.provider_urn = x.urn
        WHERE x.urn IS NOT NULL AND x.urn != ''
    """,
    )

    # ── Query 2b: Coverage breakdown for school-classified providers ──
    run_query(
        conn,
        "Q2b: URN coverage for school-classified LA providers",
        """
        SELECT
            count(*) AS total,
            count(*) FILTER (
                WHERE x.urn IS NULL OR x.urn = ''
            ) AS no_urn,
            count(*) FILTER (
                WHERE x.urn IS NOT NULL AND x.urn != ''
            ) AS has_urn,
            count(*) FILTER (WHERE sc.urn IS NOT NULL) AS urn_in_school_census,
            count(*) FILTER (WHERE oi.provider_urn IS NOT NULL) AS urn_in_ofsted,
            count(*) FILTER (
                WHERE x.urn IS NOT NULL AND x.urn != ''
                  AND sc.urn IS NULL AND oi.provider_urn IS NULL
            ) AS urn_in_neither
        FROM la.extract_results e
        CROSS JOIN LATERAL (
            SELECT e.extracted_data->>'ofsted_urn' AS urn
        ) x
        LEFT JOIN dfe.school_census sc ON sc.urn = x.urn
        LEFT JOIN ofsted.inspections oi ON oi.provider_urn = x.urn
        WHERE e.classification && ARRAY['school_based_nursery','breakfast_club',
                                         'after_school_club','holiday_club']
    """,
    )

    # ── Query 3: Postcode overlap — fallback for providers without URN match ──
    run_query(
        conn,
        "Q3: Postcode fallback for unmatched school-classified providers",
        """
        WITH school_providers AS (
            SELECT e.lad25cd, e.provider_id,
                   e.extracted_data->>'ofsted_urn' AS urn,
                   upper(regexp_replace(
                       coalesce(e.extracted_data->>'postcode', ''), '\\s+', ' ', 'g'
                   )) AS la_postcode,
                   e.extracted_data->>'provider_name' AS la_name
            FROM la.extract_results e
            WHERE e.classification && ARRAY['school_based_nursery','breakfast_club',
                                             'after_school_club','holiday_club']
        )
        SELECT
            count(DISTINCT (sp.lad25cd, sp.provider_id)) AS total_school_providers,
            count(DISTINCT (sp.lad25cd, sp.provider_id))
                FILTER (WHERE sc_urn.urn IS NOT NULL) AS matched_by_urn,
            count(DISTINCT (sp.lad25cd, sp.provider_id))
                FILTER (WHERE sc_urn.urn IS NULL
                    AND sc_pc.urn IS NOT NULL) AS postcode_candidates,
            count(DISTINCT (sp.lad25cd, sp.provider_id))
                FILTER (WHERE sc_urn.urn IS NULL
                    AND sc_pc.urn IS NULL) AS no_match
        FROM school_providers sp
        LEFT JOIN dfe.school_census sc_urn ON sc_urn.urn = sp.urn
        LEFT JOIN dfe.school_census sc_pc
            ON upper(regexp_replace(sc_pc.school_postcode, '\\s+', ' ', 'g')) = sp.la_postcode
            AND sp.la_postcode != ''
            AND sc_urn.urn IS NULL
    """,
    )

    # ── Query 4: School census address enrichment via Ofsted ──
    run_query(
        conn,
        "Q4: School census address enrichment via Ofsted records",
        """
        SELECT
            count(*) AS total_schools,
            count(DISTINCT oi.provider_urn) FILTER (
                WHERE oi.provider_urn IS NOT NULL
            ) AS has_ofsted_record,
            count(DISTINCT oi.provider_urn) FILTER (
                WHERE oi.provider_urn IS NOT NULL
                  AND coalesce(
                      nullif(oi.provider_postcode, 'REDACTED'),
                      sr.provider_postcode
                  ) IS NOT NULL
            ) AS has_ofsted_address
        FROM dfe.school_census sc
        LEFT JOIN ofsted.inspections oi ON oi.provider_urn = sc.urn
        LEFT JOIN ofsted.scrape_results sr ON sr.provider_urn = sc.urn
    """,
    )

    # ── Query 5: Name similarity sample ──
    run_query(
        conn,
        "Q5: Name similarity sample (postcode-matched, no URN)",
        """
        WITH candidates AS (
            SELECT DISTINCT ON (e.provider_id)
                   e.extracted_data->>'provider_name' AS la_name,
                   sc.school_name,
                   upper(regexp_replace(
                       coalesce(e.extracted_data->>'postcode', ''), '\\s+', ' ', 'g'
                   )) AS postcode,
                   (SELECT unnest(e.classification)
                    INTERSECT
                    SELECT unnest(ARRAY['school_based_nursery','breakfast_club',
                                        'after_school_club','holiday_club'])
                    LIMIT 1) AS care_type
            FROM la.extract_results e
            JOIN dfe.school_census sc
                ON upper(regexp_replace(sc.school_postcode, '\\s+', ' ', 'g'))
                 = upper(regexp_replace(
                     coalesce(e.extracted_data->>'postcode', ''), '\\s+', ' ', 'g'))
            WHERE e.classification && ARRAY['school_based_nursery','breakfast_club',
                                             'after_school_club','holiday_club']
              AND (e.extracted_data->>'ofsted_urn' IS NULL
                   OR e.extracted_data->>'ofsted_urn' = '')
              AND e.extracted_data->>'postcode' IS NOT NULL
              AND e.extracted_data->>'postcode' != ''
        )
        SELECT la_name, school_name, postcode, care_type
        FROM candidates
        LIMIT 20
    """,
    )

    conn.close()

    print(f"\n{'#' * 70}")
    print("#  Analysis complete")
    print(f"{'#' * 70}\n")


if __name__ == "__main__":
    main()
