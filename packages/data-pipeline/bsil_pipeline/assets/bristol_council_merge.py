"""Merge Bristol council directory data into Liquidlogic extract results.

Reads both extract_results sources for Bristol (E06000023):
- liquidlogic provider records (from parent.bristol.gov.uk)
- bristol_council provider records (from bristol.gov.uk council directory)

Matches them via:
1. Exact: council_fis_url in council record matches source_url of liquidlogic record
2. Fuzzy fallback: jaro-winkler name ≥ 0.92 + exact postcode match

For matched pairs: fills null fields in the liquidlogic record from the
council record (phone, email, website, area, age_range). Liquidlogic data
is never overwritten — council data only fills gaps.

Unmatched council providers are logged but NOT inserted — the council
directory is used for enrichment only, not as a primary provider source.
"""

import json
import re
from difflib import SequenceMatcher

from dagster import AssetExecutionContext, MetadataValue, asset

from bsil_pipeline.automation import PIPELINE_CONDITION
from bsil_pipeline.resources.postgres import BsilPostgresResource

LAD25CD = "E06000023"

_ENRICH_FIELDS = ("phone", "email", "website", "area", "age_range")

# Jaro-Winkler not in stdlib; use SequenceMatcher as approximation.
# Threshold 0.92 on jaro-winkler ≈ 0.85 on SequenceMatcher ratio for names.
_NAME_THRESHOLD = 0.85


def _normalise_name(name: str) -> str:
    s = name.lower().strip()
    for suffix in [
        "ltd",
        "limited",
        "nursery school",
        "day nursery",
        "nursery",
        "pre-school",
        "preschool",
        "pre school",
        "childminding",
        "childcare",
        "out of school club",
        "after school club",
        "breakfast club",
        "the",
    ]:
        s = re.sub(rf"\b{re.escape(suffix)}\b", "", s)
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _name_sim(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalise_name(a), _normalise_name(b)).ratio()


def _norm_postcode(pc: str) -> str:
    return re.sub(r"\s+", "", (pc or "").upper().strip())


def _strip_url(url: str) -> str:
    """Normalise URL for comparison: lowercase, strip protocol and trailing slash."""
    return re.sub(r"^https?://", "", url.lower().rstrip("/"))


UPDATE_SQL = """
UPDATE la.extract_results
SET extracted_data = %(extracted_data)s::jsonb,
    extracted_at   = now()
WHERE lad25cd = %(lad25cd)s
  AND provider_id = %(provider_id)s
  AND platform = 'liquidlogic'
"""


@asset(
    group_name="la",
    deps=["la_extract_results", "la_extract_results_table"],
    automation_condition=PIPELINE_CONDITION,
)
def bristol_council_merge(
    context: AssetExecutionContext, bsil_postgres: BsilPostgresResource
):
    """Enrich Bristol Liquidlogic records with council directory data."""
    with bsil_postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE la.extract_results SET draft_exclude = false"
                " WHERE lad25cd = %s AND platform IN ('bristol_council', 'liquidlogic')",
                (LAD25CD,),
            )
        conn.commit()

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT provider_id, extracted_data, classification,
                       source_classification, field_count, extraction_warnings
                FROM la.extract_results
                WHERE lad25cd = %s AND platform = 'liquidlogic'
                """,
                (LAD25CD,),
            )
            ll_rows = cur.fetchall()

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT provider_id, extracted_data, classification,
                       source_classification, field_count, extraction_warnings
                FROM la.extract_results
                WHERE lad25cd = %s AND platform = 'bristol_council'
                """,
                (LAD25CD,),
            )
            council_rows = cur.fetchall()

    context.log.info(
        f"Bristol merge: {len(ll_rows)} liquidlogic, {len(council_rows)} council rows"
    )

    if not council_rows:
        context.log.info("No council rows — nothing to merge")
        return {"merged": MetadataValue.int(0), "unmatched": MetadataValue.int(0)}

    # Index liquidlogic rows by normalised source_url and by (name, postcode)
    ll_by_fis_url: dict[str, tuple] = {}
    ll_by_name_pc: list[tuple] = []

    for row in ll_rows:
        pid, ed_raw, classification, src_classification, field_count, warnings = row
        ed = ed_raw if isinstance(ed_raw, dict) else json.loads(ed_raw or "{}")
        fis_url = _strip_url(ed.get("fis_url", ""))
        if fis_url:
            ll_by_fis_url[fis_url] = (
                pid,
                ed,
                classification,
                src_classification,
                field_count,
                warnings,
            )
        ll_by_name_pc.append(
            (pid, ed, classification, src_classification, field_count, warnings)
        )

    counts = {"exact": 0, "fuzzy": 0, "unmatched": 0, "enriched_fields": 0}

    with bsil_postgres.get_connection() as write_conn:
        for row in council_rows:
            c_pid, c_ed_raw, c_cls, c_src_cls, c_fc, c_warn = row
            c_ed = (
                c_ed_raw if isinstance(c_ed_raw, dict) else json.loads(c_ed_raw or "{}")
            )

            council_fis_url = _strip_url(c_ed.get("council_fis_url", ""))
            c_name = c_ed.get("provider_name", "")
            c_pc = _norm_postcode(c_ed.get("postcode", ""))

            matched_ll = None

            # 1. Exact match via FIS URL
            if council_fis_url and council_fis_url in ll_by_fis_url:
                matched_ll = ll_by_fis_url[council_fis_url]
                counts["exact"] += 1

            # 2. Fuzzy: name + postcode
            if matched_ll is None and c_name and c_pc:
                best_score = 0.0
                best_row = None
                for ll_row in ll_by_name_pc:
                    ll_pid, ll_ed, *_ = ll_row
                    ll_name = ll_ed.get("provider_name", "")
                    ll_pc = _norm_postcode(ll_ed.get("postcode", ""))
                    if c_pc != ll_pc:
                        continue
                    score = _name_sim(c_name, ll_name)
                    if score > best_score:
                        best_score = score
                        best_row = ll_row
                if best_score >= _NAME_THRESHOLD and best_row is not None:
                    matched_ll = best_row
                    counts["fuzzy"] += 1

            if matched_ll is not None:
                ll_pid, ll_ed, ll_cls, ll_src_cls, ll_fc, ll_warn = matched_ll
                updated_ed = dict(ll_ed)
                for field in _ENRICH_FIELDS:
                    if not updated_ed.get(field) and c_ed.get(field):
                        updated_ed[field] = c_ed[field]
                        counts["enriched_fields"] += 1

                with write_conn.cursor() as cur:
                    cur.execute(
                        UPDATE_SQL,
                        {
                            "lad25cd": LAD25CD,
                            "provider_id": ll_pid,
                            "extracted_data": json.dumps(updated_ed),
                        },
                    )
            else:
                # No match — skip. Council directory is enrichment-only.
                counts["unmatched"] += 1

        write_conn.commit()

    with bsil_postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE la.extract_results SET draft_exclude = true"
                " WHERE lad25cd = %s AND platform = 'bristol_council'",
                (LAD25CD,),
            )
        conn.commit()

    context.log.info(
        f"Bristol merge complete: {counts['exact']} exact matches, "
        f"{counts['fuzzy']} fuzzy matches, {counts['unmatched']} unmatched (skipped), "
        f"{counts['enriched_fields']} fields enriched"
    )

    return {
        "exact_matches": MetadataValue.int(counts["exact"]),
        "fuzzy_matches": MetadataValue.int(counts["fuzzy"]),
        "unmatched": MetadataValue.int(counts["unmatched"]),
        "enriched_fields": MetadataValue.int(counts["enriched_fields"]),
    }
