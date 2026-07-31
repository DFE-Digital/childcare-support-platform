"""Bristol wraparound childcare directory — scrape + match report.

Scrapes the Bristol Council wraparound directory (111 schools, ~12 listing
pages + detail pages for postcodes) and matches against published Bristol
primary schools to produce a classification enrichment report.

Output: exported_data/bristol_wraparound_matches.csv
"""

import csv
import re
from difflib import SequenceMatcher
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dagster import AssetExecutionContext, MetadataValue, asset

from bsil_pipeline.automation import PIPELINE_CONDITION
from bsil_pipeline.resources.postgres import BsilPostgresResource

LAD25CD = "E06000023"
BASE_URL = (
    "https://www.bristol.gov.uk/residents/schools-learning-and-early-years"
    "/wraparound-childcare/find-wraparound-childcare"
)
PAGE_SIZE = 10
REQUEST_TIMEOUT = 20
OUTPUT_PATH = Path("/opt/dagster/app/output/bristol_wraparound_matches.csv")

_USER_AGENT = "BSIL-DataPipeline/1.0 (research; best-start-in-life)"
_POSTCODE_RE = re.compile(r"[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}", re.IGNORECASE)

_ABBREVIATIONS = {
    "c.e.": "church of england",
    "ce": "church of england",
    "cevc": "church of england",
    "cofe": "church of england",
    "c of e": "church of england",
    "r.c.": "roman catholic",
    "rc": "roman catholic",
    "va": "",
    "vc": "",
}

_STRIP_WORDS = {
    "primary",
    "school",
    "academy",
    "infant",
    "infants",
    "junior",
    "nursery",
    "community",
    "voluntary",
    "aided",
    "church",
    "of",
    "england",
    "catholic",
    "roman",
    "the",
    "and",
    "&",
}

_TRUST_NAMES = [
    "e-act",
    "e act",
    "oasis academy",
    "oasis",
]


def _core_name(name: str) -> str:
    """Extract core distinctive name by stripping all institutional noise."""
    s = name.lower().strip()
    s = re.sub(r"[''`]", "'", s)
    s = re.sub(r"\s*\(.*?\)\s*", " ", s)
    s = re.sub(r",?\s*\b(bristol|clifton|bedminster|southville)\b\s*$", "", s)

    for abbr, expansion in _ABBREVIATIONS.items():
        s = re.sub(rf"\b{re.escape(abbr)}\b", expansion, s)

    for trust in _TRUST_NAMES:
        s = re.sub(rf"\b{re.escape(trust)}\b", "", s)

    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\binfants\b", "infant", s)

    tokens = [t for t in s.split() if t not in _STRIP_WORDS]
    return " ".join(sorted(tokens))


def _core_similarity(a: str, b: str) -> float:
    """Compare two school names after aggressive normalisation."""
    core_a = _core_name(a)
    core_b = _core_name(b)
    if core_a == core_b:
        return 1.0
    return SequenceMatcher(None, core_a, core_b).ratio()


def _norm_postcode(pc: str | None) -> str:
    return re.sub(r"\s+", "", (pc or "").upper().strip())


def _parse_spaces(text: str) -> int | None:
    """Parse space value: integer or None for unknown/not offered."""
    text = text.strip().lower()
    m = re.search(r"(\d+)", text)
    if m:
        return int(m.group(1))
    return None


def _scrape_listing(session: requests.Session, logger) -> list[dict]:
    """Scrape all listing pages, return list of {name, detail_url, before, after}."""
    entries = []
    offset = 0

    while True:
        url = BASE_URL if offset == 0 else f"{BASE_URL}?start={offset}"
        resp = session.get(url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Count all school links on this page (including "does not offer")
        all_links_on_page = 0
        page_entries = []
        for h2 in soup.find_all("h2"):
            link = h2.find("a", href=True)
            if not link or "wraparound-childcare-provider" not in link.get("href", ""):
                continue

            all_links_on_page += 1
            name = link.get_text(strip=True)
            detail_url = link["href"]
            if not detail_url.startswith("http"):
                detail_url = "https://www.bristol.gov.uk" + detail_url

            before_spaces = None
            after_spaces = None
            does_not_offer = False

            sibling = h2.find_next_sibling()
            while sibling and sibling.name != "h2":
                text = sibling.get_text(strip=True).lower()
                if "does not currently offer" in text:
                    does_not_offer = True
                    break
                if "before school" in text:
                    before_spaces = _parse_spaces(text)
                elif "after school" in text:
                    after_spaces = _parse_spaces(text)
                sibling = sibling.find_next_sibling()

            if does_not_offer:
                continue

            page_entries.append(
                {
                    "name": name,
                    "detail_url": detail_url,
                    "before_spaces": before_spaces,
                    "after_spaces": after_spaces,
                }
            )

        entries.extend(page_entries)
        logger.info(
            f"  Listing page offset={offset}: {len(page_entries)} entries "
            f"({all_links_on_page} total on page)"
        )

        if all_links_on_page < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    return entries


def _scrape_detail_postcode(session: requests.Session, detail_url: str) -> str | None:
    """Fetch a detail page and extract the postcode."""
    try:
        resp = session.get(detail_url, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
    except Exception:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    text = soup.get_text()
    m = _POSTCODE_RE.search(text)
    return m.group(0).upper() if m else None


def _match_school(
    entry: dict,
    published_schools: list[dict],
) -> tuple[dict | None, str, float]:
    """Match a wraparound entry to a published school.

    Returns (matched_school, match_method, confidence) or (None, "", 0.0).
    """
    w_name = entry["name"]
    w_pc = _norm_postcode(entry.get("postcode"))

    # Pass 1: exact name + postcode
    for school in published_schools:
        if (
            school["name"].lower().strip() == w_name.lower().strip()
            and _norm_postcode(school["postcode"]) == w_pc
            and w_pc
        ):
            return school, "exact_name_postcode", 1.0

    # Pass 2: exact name only (postcodes differ slightly)
    for school in published_schools:
        if school["name"].lower().strip() == w_name.lower().strip():
            return school, "exact_name", 0.95

    # Pass 3: core name match + postcode (handles trust reordering, abbreviations)
    w_core = _core_name(w_name)
    for school in published_schools:
        s_pc = _norm_postcode(school["postcode"])
        if w_pc and s_pc and w_pc != s_pc:
            continue
        if _core_name(school["name"]) == w_core:
            return school, "core_name_postcode", 0.92

    # Pass 4: core similarity + postcode (fuzzy on remaining core)
    best_score = 0.0
    best_school = None
    for school in published_schools:
        s_pc = _norm_postcode(school["postcode"])
        if w_pc and s_pc and w_pc != s_pc:
            continue
        score = _core_similarity(w_name, school["name"])
        if score > best_score:
            best_score = score
            best_school = school

    if best_score >= 0.75 and best_school is not None:
        return best_school, "core_similarity", round(best_score, 3)

    # Pass 5: sole school at this postcode (handles renames)
    if w_pc:
        pc_matches = [
            s for s in published_schools if _norm_postcode(s["postcode"]) == w_pc
        ]
        if len(pc_matches) == 1:
            return pc_matches[0], "sole_postcode_match", 0.85

    return None, "", 0.0


@asset(
    group_name="la",
    deps=["gias_schools"],
    automation_condition=PIPELINE_CONDITION,
)
def bristol_wraparound_matches(
    context: AssetExecutionContext,
    bsil_postgres: BsilPostgresResource,
):
    """Scrape Bristol wraparound directory and produce match report CSV."""
    session = requests.Session()
    session.headers.update({"User-Agent": _USER_AGENT})

    context.log.info("Scraping wraparound listing pages...")
    entries = _scrape_listing(session, context.log)
    context.log.info(f"Found {len(entries)} schools offering wraparound")

    context.log.info("Fetching detail pages for postcodes...")
    for i, entry in enumerate(entries):
        pc = _scrape_detail_postcode(session, entry["detail_url"])
        entry["postcode"] = pc
        if (i + 1) % 20 == 0:
            context.log.info(f"  {i + 1}/{len(entries)} detail pages fetched")

    context.log.info("Loading Bristol schools from GIAS...")
    with bsil_postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT urn, establishment_name, postcode FROM dfe.gias_schools"
                " WHERE postcode LIKE 'BS%%'"
                " AND phase_of_education IN ('Primary', 'All through')"
                " AND establishment_status = 'Open'",
            )
            published_schools = [
                {"id": row[0], "name": row[1], "postcode": row[2]}
                for row in cur.fetchall()
            ]

    context.log.info(f"Loaded {len(published_schools)} GIAS schools")

    context.log.info("Matching...")
    rows = []
    matched_count = 0
    for entry in entries:
        school, method, confidence = _match_school(entry, published_schools)
        rows.append(
            {
                "wraparound_name": entry["name"],
                "wraparound_postcode": entry.get("postcode", ""),
                "matched_name": school["name"] if school else "",
                "matched_provider_id": school["id"] if school else "",
                "matched_postcode": school["postcode"] if school else "",
                "match_method": method,
                "confidence": confidence,
                "before_spaces": entry["before_spaces"]
                if entry["before_spaces"] is not None
                else "",
                "after_spaces": entry["after_spaces"]
                if entry["after_spaces"] is not None
                else "",
            }
        )
        if school:
            matched_count += 1

    # Write staging table for care_offerings
    with bsil_postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE SCHEMA IF NOT EXISTS draft")
            cur.execute("DROP TABLE IF EXISTS draft.bristol_wraparound")
            cur.execute("""
                CREATE TABLE draft.bristol_wraparound (
                    school_urn TEXT NOT NULL PRIMARY KEY,
                    school_name TEXT,
                    postcode TEXT,
                    before_spaces INTEGER,
                    after_spaces INTEGER,
                    match_method TEXT
                )
            """)
            staged = 0
            for row in rows:
                if not row["matched_provider_id"]:
                    continue
                before = row["before_spaces"] if row["before_spaces"] != "" else None
                after = row["after_spaces"] if row["after_spaces"] != "" else None
                if not before and not after:
                    continue
                cur.execute(
                    "INSERT INTO draft.bristol_wraparound"
                    " (school_urn, school_name, postcode,"
                    "  before_spaces, after_spaces, match_method)"
                    " VALUES (%s, %s, %s, %s, %s, %s)",
                    (
                        str(row["matched_provider_id"]),
                        row["matched_name"],
                        row["matched_postcode"],
                        before or None,
                        after or None,
                        row["match_method"],
                    ),
                )
                staged += 1
        conn.commit()

    context.log.info(
        f"Staging table: {staged} rows written to draft.bristol_wraparound"
    )

    # Write CSV for debug/review
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "wraparound_name",
                "wraparound_postcode",
                "matched_name",
                "matched_provider_id",
                "matched_postcode",
                "match_method",
                "confidence",
                "before_spaces",
                "after_spaces",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    context.log.info(
        f"Match report: {matched_count}/{len(entries)} matched, "
        f"{len(entries) - matched_count} unmatched"
    )

    return {
        "total_schools": MetadataValue.int(len(entries)),
        "matched": MetadataValue.int(matched_count),
        "unmatched": MetadataValue.int(len(entries) - matched_count),
        "staged_for_care_offerings": MetadataValue.int(staged),
    }
