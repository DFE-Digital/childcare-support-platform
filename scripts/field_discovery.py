#!/usr/bin/env python3
"""Field discovery CLI — runs extractors across all providers and reports coverage.

Usage:
    # All platforms
    python scripts/field_discovery.py

    # Single platform
    python scripts/field_discovery.py --platform openobjects_kb5

    # Specific LA
    python scripts/field_discovery.py --lad E09000022

    # Output formats
    python scripts/field_discovery.py --format summary     # default: compact per-platform summary
    python scripts/field_discovery.py --format fields       # per-field coverage across all LAs
    python scripts/field_discovery.py --format classification  # care-type classification report
    python scripts/field_discovery.py --format residual     # uncaptured labels / unused JSON keys
    python scripts/field_discovery.py --format all          # everything

    # Write to file
    python scripts/field_discovery.py --output report.txt

Requires BSIL_DB_* env vars (same as Dagster):
    BSIL_DB_HOST, BSIL_DB_PORT, BSIL_DB_USER, BSIL_DB_PASSWORD, BSIL_DB_NAME
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, TextIO

# Add the data-pipeline package to sys.path so we can import bsil_pipeline
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PACKAGE_DIR = os.path.join(os.path.dirname(_SCRIPT_DIR), "packages", "data-pipeline")
if _PACKAGE_DIR not in sys.path:
    sys.path.insert(0, _PACKAGE_DIR)

import psycopg  # noqa: E402

from bsil_pipeline.extractors import get_extractor, has_extractor  # noqa: E402
from bsil_pipeline.extractors.base import ExtractedProvider  # noqa: E402
from bsil_pipeline.scrapers import classify_la  # noqa: E402


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class FieldStats:
    """Accumulated stats for a single canonical field key."""

    count: int = 0
    sample_values: list[str] = field(default_factory=list)
    max_samples: int = 3

    def add(self, value: Any) -> None:
        self.count += 1
        if len(self.sample_values) < self.max_samples:
            s = str(value)[:120]
            if s not in self.sample_values:
                self.sample_values.append(s)


@dataclass
class PlatformReport:
    """Aggregated extraction report for one platform."""

    platform: str
    la_count: int = 0
    provider_count: int = 0
    extracted_count: int = 0
    error_count: int = 0
    warning_count: int = 0
    # field_key -> FieldStats (across all providers on this platform)
    field_coverage: dict[str, FieldStats] = field(default_factory=dict)
    # Per-LA field coverage: lad25cd -> field_key -> count
    la_field_counts: dict[str, dict[str, int]] = field(
        default_factory=lambda: defaultdict(lambda: Counter())
    )
    # Per-LA provider counts
    la_provider_counts: dict[str, int] = field(default_factory=lambda: Counter())
    # Classification
    classification_counts: Counter = field(default_factory=Counter)
    source_label_counts: Counter = field(default_factory=Counter)
    unclassified_labels: Counter = field(default_factory=Counter)
    # Field count distribution
    field_count_values: list[int] = field(default_factory=list)
    # Errors
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Database connection
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Core extraction logic
# ---------------------------------------------------------------------------


def run_extraction(
    conn: psycopg.Connection,
    platform_filter: str | None = None,
    lad_filter: str | None = None,
    limit: int | None = None,
) -> dict[str, PlatformReport]:
    """Run extractors across scrape_results and collect reports."""
    # Get all LAs and their platforms
    with conn.cursor() as cur:
        cur.execute(
            "SELECT lad25cd, lad25nm, fis_url FROM la.family_information_services"
        )
        all_las = cur.fetchall()

    la_platforms: dict[str, str] = {}
    for lad25cd, _lad25nm, fis_url in all_las:
        platform = classify_la(fis_url, lad25cd)
        la_platforms[lad25cd] = platform

    # Filter platforms
    if platform_filter:
        target_lads = {lad for lad, p in la_platforms.items() if p == platform_filter}
    elif lad_filter:
        target_lads = {lad_filter}
    else:
        target_lads = {lad for lad, p in la_platforms.items() if has_extractor(p)}

    if not target_lads:
        print("No matching LAs found.", file=sys.stderr)
        return {}

    # Group by platform
    platform_lads: dict[str, set[str]] = defaultdict(set)
    for lad in target_lads:
        platform = la_platforms.get(lad, "council_generic")
        if has_extractor(platform):
            platform_lads[platform].add(lad)

    reports: dict[str, PlatformReport] = {}

    for platform, lad_codes in sorted(platform_lads.items()):
        print(f"\n{'=' * 60}", file=sys.stderr)
        print(f"Platform: {platform} ({len(lad_codes)} LAs)", file=sys.stderr)
        print(f"{'=' * 60}", file=sys.stderr)

        report = PlatformReport(platform=platform, la_count=len(lad_codes))
        extractor = get_extractor(platform)

        # Fetch scrape results
        placeholders = ",".join(["%s"] * len(lad_codes))
        query = f"""
            SELECT lad25cd, provider_id, provider_name, raw_html, raw_json
            FROM la.scrape_results
            WHERE lad25cd IN ({placeholders})
              AND scrape_status IN ('success', 'partial')
        """  # nosec B608 — placeholders are %s params, not user input
        if limit:
            query += f" LIMIT {limit}"

        with conn.cursor() as cur:
            cur.execute(query, tuple(lad_codes))
            rows = cur.fetchall()

        report.provider_count = len(rows)
        print(f"  {len(rows)} providers to process", file=sys.stderr)

        for i, (lad25cd, provider_id, provider_name, raw_html, raw_json) in enumerate(
            rows
        ):
            try:
                result = extractor.extract(
                    lad25cd=lad25cd,
                    provider_id=provider_id,
                    raw_html=raw_html,
                    raw_json=raw_json,
                    provider_name=provider_name,
                )
                _accumulate_result(report, lad25cd, result)
                report.extracted_count += 1
                if result.extraction_warnings:
                    report.warning_count += 1
            except Exception as e:
                report.error_count += 1
                err_msg = f"{lad25cd}/{provider_id}: {type(e).__name__}: {e}"
                if len(report.errors) < 20:
                    report.errors.append(err_msg)

            if (i + 1) % 1000 == 0:
                print(f"  Progress: {i + 1}/{len(rows)}", file=sys.stderr)

        print(
            f"  Done: {report.extracted_count} extracted, "
            f"{report.error_count} errors, {report.warning_count} warnings",
            file=sys.stderr,
        )
        reports[platform] = report

    return reports


def _accumulate_result(
    report: PlatformReport, lad25cd: str, result: ExtractedProvider
) -> None:
    """Accumulate one extraction result into the platform report."""
    report.la_provider_counts[lad25cd] += 1
    report.field_count_values.append(result.field_count)

    # Field coverage
    for key, value in result.extracted_data.items():
        if key == "extra" and isinstance(value, dict):
            for ek, ev in value.items():
                full_key = f"extra.{ek}"
                if full_key not in report.field_coverage:
                    report.field_coverage[full_key] = FieldStats()
                report.field_coverage[full_key].add(ev)
                report.la_field_counts[lad25cd][full_key] += 1
        elif value is not None and value != "" and value != []:
            if key not in report.field_coverage:
                report.field_coverage[key] = FieldStats()
            report.field_coverage[key].add(value)
            report.la_field_counts[lad25cd][key] += 1

    # Classification
    for ct in result.classification:
        report.classification_counts[ct] += 1
    for sl in result.source_classification:
        report.source_label_counts[sl] += 1
        # Track unclassified labels
        if not result.classification:
            report.unclassified_labels[sl] += 1


# ---------------------------------------------------------------------------
# Report formatters
# ---------------------------------------------------------------------------


def print_summary(reports: dict[str, PlatformReport], out: TextIO) -> None:
    """Print compact per-platform summary."""
    out.write("\n" + "=" * 80 + "\n")
    out.write("FIELD DISCOVERY SUMMARY\n")
    out.write("=" * 80 + "\n\n")

    total_providers = 0
    total_extracted = 0
    total_errors = 0

    for platform, r in sorted(reports.items()):
        total_providers += r.provider_count
        total_extracted += r.extracted_count
        total_errors += r.error_count

        avg_fields = (
            sum(r.field_count_values) / len(r.field_count_values)
            if r.field_count_values
            else 0
        )
        min_fields = min(r.field_count_values) if r.field_count_values else 0
        max_fields = max(r.field_count_values) if r.field_count_values else 0

        out.write(
            f"  {platform:<25s}  {r.la_count:>3d} LAs  {r.provider_count:>6d} providers  "
        )
        out.write(f"fields: {avg_fields:.1f} avg ({min_fields}-{max_fields})  ")
        out.write(f"{len(r.field_coverage):>3d} unique keys")
        if r.error_count:
            out.write(f"  [{r.error_count} errors]")
        out.write("\n")

    out.write(
        f"\n  TOTAL: {total_providers} providers, {total_extracted} extracted, {total_errors} errors\n"
    )

    # Per-LA breakdown for each platform
    out.write("\n" + "-" * 80 + "\n")
    out.write("PER-LA BREAKDOWN\n")
    out.write("-" * 80 + "\n")

    for platform, r in sorted(reports.items()):
        out.write(f"\n  {platform}:\n")
        for lad, count in sorted(r.la_provider_counts.items()):
            la_fields = r.la_field_counts.get(lad, {})
            field_keys = len(la_fields)
            out.write(
                f"    {lad}: {count:>5d} providers, {field_keys:>3d} unique field keys\n"
            )


def print_fields(reports: dict[str, PlatformReport], out: TextIO) -> None:
    """Print per-field coverage across all platforms."""
    out.write("\n" + "=" * 80 + "\n")
    out.write("FIELD COVERAGE REPORT\n")
    out.write("=" * 80 + "\n")

    for platform, r in sorted(reports.items()):
        out.write(f"\n{'─' * 60}\n")
        out.write(f"Platform: {platform} ({r.extracted_count} providers)\n")
        out.write(f"{'─' * 60}\n")

        # Sort by count descending
        sorted_fields = sorted(
            r.field_coverage.items(),
            key=lambda x: x[1].count,
            reverse=True,
        )

        # Separate canonical from extra
        canonical = [(k, v) for k, v in sorted_fields if not k.startswith("extra.")]
        extra = [(k, v) for k, v in sorted_fields if k.startswith("extra.")]

        out.write("\n  CANONICAL FIELDS:\n")
        for key, stats in canonical:
            pct = (stats.count / r.extracted_count * 100) if r.extracted_count else 0
            samples = " | ".join(stats.sample_values[:3])
            out.write(
                f"    {key:<30s}  {stats.count:>6d}  ({pct:5.1f}%)  samples: {samples}\n"
            )

        if extra:
            out.write(f"\n  EXTRA FIELDS ({len(extra)} keys):\n")
            for key, stats in extra:
                pct = (
                    (stats.count / r.extracted_count * 100) if r.extracted_count else 0
                )
                samples = " | ".join(stats.sample_values[:3])
                display_key = key[len("extra.") :]
                out.write(
                    f"    {display_key:<40s}  {stats.count:>6d}  ({pct:5.1f}%)  samples: {samples}\n"
                )


def print_classification(reports: dict[str, PlatformReport], out: TextIO) -> None:
    """Print care-type classification report."""
    out.write("\n" + "=" * 80 + "\n")
    out.write("CLASSIFICATION REPORT\n")
    out.write("=" * 80 + "\n")

    # Global classification counts
    global_ct: Counter = Counter()
    global_sl: Counter = Counter()
    global_unclassified: Counter = Counter()
    for r in reports.values():
        global_ct.update(r.classification_counts)
        global_sl.update(r.source_label_counts)
        global_unclassified.update(r.unclassified_labels)

    # Per-platform
    for platform, r in sorted(reports.items()):
        out.write(f"\n{'─' * 60}\n")
        out.write(f"Platform: {platform} ({r.extracted_count} providers)\n")
        out.write(f"{'─' * 60}\n")

        if r.classification_counts:
            out.write("  Mapped care types:\n")
            for ct, count in r.classification_counts.most_common():
                out.write(f"    {ct:<30s}  {count:>6d}\n")

        if r.source_label_counts:
            out.write("  Source labels:\n")
            for sl, count in r.source_label_counts.most_common(20):
                out.write(f"    {sl:<40s}  {count:>6d}\n")
            if len(r.source_label_counts) > 20:
                out.write(f"    ... and {len(r.source_label_counts) - 20} more\n")

        if r.unclassified_labels:
            out.write("  UNMAPPED source labels (need adding to CARE_TYPE_MAPPING):\n")
            for sl, count in r.unclassified_labels.most_common(20):
                out.write(f"    {sl:<40s}  {count:>6d}\n")

    # Global summary
    out.write(f"\n{'=' * 60}\n")
    out.write("GLOBAL CARE TYPE DISTRIBUTION\n")
    out.write(f"{'=' * 60}\n")
    for ct, count in global_ct.most_common():
        out.write(f"  {ct:<30s}  {count:>6d}\n")

    if global_unclassified:
        out.write("\nTOP UNMAPPED LABELS (across all platforms):\n")
        for sl, count in global_unclassified.most_common(30):
            out.write(f"  {sl:<50s}  {count:>6d}\n")


def print_residual(reports: dict[str, PlatformReport], out: TextIO) -> None:
    """Print residual analysis — fields in extra{} that might warrant canonical keys."""
    out.write("\n" + "=" * 80 + "\n")
    out.write("RESIDUAL ANALYSIS — EXTRA FIELDS THAT MAY WARRANT CANONICAL KEYS\n")
    out.write("=" * 80 + "\n")

    for platform, r in sorted(reports.items()):
        extra_fields = {
            k: v for k, v in r.field_coverage.items() if k.startswith("extra.")
        }
        if not extra_fields:
            continue

        out.write(f"\n{'─' * 60}\n")
        out.write(
            f"Platform: {platform} ({r.extracted_count} providers, {len(extra_fields)} extra keys)\n"
        )
        out.write(f"{'─' * 60}\n")

        # Sort by frequency
        for key, stats in sorted(
            extra_fields.items(), key=lambda x: x[1].count, reverse=True
        ):
            pct = (stats.count / r.extracted_count * 100) if r.extracted_count else 0
            display_key = key[len("extra.") :]
            action = _suggest_action(display_key, pct)
            samples = " | ".join(stats.sample_values[:2])
            out.write(
                f"  {display_key:<45s} {stats.count:>5d} ({pct:5.1f}%)  {action}  [{samples}]\n"
            )

    # Errors
    has_errors = any(r.errors for r in reports.values())
    if has_errors:
        out.write(f"\n{'=' * 60}\n")
        out.write("EXTRACTION ERRORS\n")
        out.write(f"{'=' * 60}\n")
        for platform, r in sorted(reports.items()):
            if r.errors:
                out.write(f"\n  {platform}:\n")
                for err in r.errors:
                    out.write(f"    {err}\n")


def _suggest_action(label: str, pct: float) -> str:
    """Suggest whether an extra field should be promoted to canonical."""
    # Known cosmetic/nav fields
    skip_patterns = [
        "qr code",
        "back to",
        "print",
        "share",
        "bookmark",
        "map",
        "directions",
        "last updated",
        "page views",
        "ref number",
        "record id",
    ]
    for pattern in skip_patterns:
        if pattern in label.lower():
            return "SKIP (cosmetic)"

    # Known valuable fields that could be canonical
    promote_patterns = {
        "ofsted": "PROMOTE → ofsted_*",
        "age": "PROMOTE → age_from/age_to",
        "opening": "PROMOTE → opening_hours",
        "hours": "PROMOTE → opening_hours",
        "fees": "PROMOTE → fees_raw",
        "cost": "PROMOTE → fees_raw",
        "funded": "PROMOTE → funded_*",
        "free entitlement": "PROMOTE → funded_*",
        "send": "PROMOTE → send_*",
        "special": "PROMOTE → send_*",
        "vacanc": "PROMOTE → places_available",
        "places": "PROMOTE → places_total",
        "capacity": "PROMOTE → places_total",
        "facilities": "PROMOTE → facilities[]",
        "wheelchair": "PROMOTE → has_wheelchair_access",
        "garden": "PROMOTE → has_garden",
        "description": "PROMOTE → description",
        "language": "PROMOTE → languages[]",
        "pick up": "PROMOTE → school_pickups[]",
        "collection": "PROMOTE → school_pickups[]",
    }
    for pattern, suggestion in promote_patterns.items():
        if pattern in label.lower():
            return suggestion

    if pct > 50:
        return "REVIEW (high coverage)"
    elif pct > 10:
        return "REVIEW (moderate coverage)"
    else:
        return "keep in extra"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Field discovery across LA scrape data"
    )
    parser.add_argument("--platform", help="Filter to a single platform key")
    parser.add_argument("--lad", help="Filter to a single LAD code")
    parser.add_argument(
        "--limit", type=int, help="Limit providers per platform (for testing)"
    )
    parser.add_argument(
        "--format",
        choices=["summary", "fields", "classification", "residual", "all"],
        default="summary",
        help="Report format (default: summary)",
    )
    parser.add_argument("--output", "-o", help="Write report to file (default: stdout)")
    args = parser.parse_args()

    conn = get_connection()
    try:
        reports = run_extraction(
            conn,
            platform_filter=args.platform,
            lad_filter=args.lad,
            limit=args.limit,
        )
    finally:
        conn.close()

    if not reports:
        print("No reports generated.", file=sys.stderr)
        return

    out: TextIO = open(args.output, "w") if args.output else sys.stdout
    try:
        if args.format in ("summary", "all"):
            print_summary(reports, out)
        if args.format in ("fields", "all"):
            print_fields(reports, out)
        if args.format in ("classification", "all"):
            print_classification(reports, out)
        if args.format in ("residual", "all"):
            print_residual(reports, out)
    finally:
        if args.output:
            out.close()
            print(f"\nReport written to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()
