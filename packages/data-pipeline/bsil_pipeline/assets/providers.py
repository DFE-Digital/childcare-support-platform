"""Dagster asset building draft.providers — coalesces care_offerings into
unique providers using union-find on shared keys.

One row per unique physical provider.  Grouping keys:
  1. (source, source_id) — same source entity with multiple care types
  2. ofsted_urn           — links LA scrape to Ofsted records
  3. school_urn           — links LA scrape to school census / free breakfast

A junction table draft.provider_sources maps every care_offering row back to
its resolved provider for full traceability.
"""

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher

from dagster import asset, AssetExecutionContext, MetadataValue

from bsil_pipeline.assets.provider_linkage import normalise_name
from bsil_pipeline.automation import PIPELINE_CONDITION
from bsil_pipeline.resources.postgres import BsilPostgresResource

# ---------- Constants ----------

BATCH_SIZE = 1000
NAME_SIMILARITY_THRESHOLD = 0.96

# Source priority for field resolution (lower index = higher priority)
_SCHOOL_PRIORITY = ["school_census", "la_scrape", "ofsted", "tiney", "free_breakfast"]
_NON_SCHOOL_PRIORITY = ["la_scrape", "ofsted", "tiney", "free_breakfast"]

# phase_type → institution_type
_PHASE_TYPE_MAP = {
    "State-funded primary": "school_primary",
    "State-funded secondary": "school_secondary",
    "State-funded nursery": "school_nursery",
    "State-funded special school": "school_special",
    "Independent school": "school_independent",
    "Pupil referral unit": "school_special",
    "Non-maintained special school": "school_special",
}

# (ofsted_provider_type, ofsted_provider_subtype) → institution_type
_OFSTED_INSTITUTION_MAP = {
    ("Childminder", None): "childminder",
    ("Childminder without domestic premises", None): "childminder",
    ("Home childcarer", None): "childminder",
    ("Childcare on domestic premises", None): "childminder",
    ("Childcare on non-domestic premises", "Full day care"): "nursery",
    ("Childcare on non-domestic premises", "Sessional day care"): "nursery",
    (
        "Childcare on non-domestic premises",
        "Out-of-school day care",
    ): "out_of_school_club",
    ("Childcare on non-domestic premises", None): "nursery",
}

# GIAS phase_of_education → institution_type (fallback when school_census missing)
_GIAS_PHASE_MAP = {
    "Primary": "school_primary",
    "Secondary": "school_secondary",
    "Nursery": "school_nursery",
    "Middle deemed primary": "school_primary",
    "Middle deemed secondary": "school_secondary",
    "All-through": "school_secondary",
}

# GIAS establishment_type_group → institution_type (for "Not applicable" phase)
_GIAS_TYPE_GROUP_MAP = {
    "Special schools": "school_special",
    "Independent schools": "school_independent",
}

# Name-based institution_type heuristics for LA-only providers with no
# school_urn or Ofsted link. Patterns tested in order; first match wins.
_NAME_SCHOOL_PATTERNS = [
    (
        re.compile(r"primary|infant|junior|first school", re.IGNORECASE),
        "school_primary",
    ),
    (re.compile(r"secondary|high school|grammar", re.IGNORECASE), "school_secondary"),
    (
        re.compile(r"independent|prep\b|preparatory", re.IGNORECASE),
        "school_independent",
    ),
    (re.compile(r"special\b|deaf", re.IGNORECASE), "school_special"),
]

# care_type → institution_type (for LA-only providers with no Ofsted/school link)
_CARE_TYPE_INSTITUTION_MAP = {
    "childminder": "childminder",
    "private_nursery": "nursery",
    "after_school_club": "out_of_school_club",
    "breakfast_club": "out_of_school_club",
    "holiday_club": "out_of_school_club",
}

# ---------- SQL ----------

DROP_SOURCES_SQL = "DROP TABLE IF EXISTS draft.provider_sources"
DROP_PROVIDERS_SQL = "DROP TABLE IF EXISTS draft.providers CASCADE"

CREATE_PROVIDERS_SQL = """
CREATE TABLE draft.providers (
    provider_id     TEXT PRIMARY KEY,
    provider_name   TEXT,
    postcode        TEXT,
    lad25cd         TEXT,
    ofsted_urn      TEXT,
    school_urn      TEXT,
    institution_type TEXT,
    care_types      TEXT[],
    excluded        BOOLEAN NOT NULL DEFAULT false,
    metadata        JSONB NOT NULL DEFAULT '{}'
)
"""

CREATE_SOURCES_SQL = """
CREATE TABLE draft.provider_sources (
    provider_id      TEXT NOT NULL,
    care_offering_id BIGINT NOT NULL,
    source           TEXT NOT NULL,
    source_id        TEXT NOT NULL,
    PRIMARY KEY (provider_id, care_offering_id)
)
"""

INSERT_PROVIDER_SQL = """
INSERT INTO draft.providers (
    provider_id, provider_name, postcode, lad25cd,
    ofsted_urn, school_urn, institution_type, care_types,
    excluded, metadata
) VALUES (
    %(provider_id)s, %(provider_name)s, %(postcode)s, %(lad25cd)s,
    %(ofsted_urn)s, %(school_urn)s, %(institution_type)s, %(care_types)s,
    %(excluded)s, %(metadata)s
)
"""

INSERT_SOURCE_SQL = """
INSERT INTO draft.provider_sources (
    provider_id, care_offering_id, source, source_id
) VALUES (
    %(provider_id)s, %(care_offering_id)s, %(source)s, %(source_id)s
)
"""

LOAD_OFFERINGS_SQL = """
SELECT id, source, source_id, lad25cd, care_type,
       provider_name, postcode, ofsted_urn, school_urn,
       phase_type, ofsted_provider_type, ofsted_provider_subtype
FROM draft.care_offerings
"""

LOAD_GIAS_SQL = """
SELECT urn, phase_of_education, establishment_type_group
FROM dfe.gias_schools
WHERE establishment_status = 'Open'
"""


# ---------- Data structures ----------


@dataclass(slots=True)
class Offering:
    id: int
    source: str
    source_id: str
    lad25cd: str | None
    care_type: str | None
    provider_name: str | None
    postcode: str | None
    ofsted_urn: str | None
    school_urn: str | None
    phase_type: str | None
    ofsted_provider_type: str | None
    ofsted_provider_subtype: str | None


class UnionFind:
    """Disjoint-set with path halving and union by rank."""

    __slots__ = ("parent", "rank")

    def __init__(self, n: int) -> None:
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]  # path halving
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1


# ---------- Helpers ----------


def _resolve_field(
    offerings: list[Offering],
    field: str,
    priority: list[str],
) -> tuple[str | None, str | None]:
    """Pick the first non-null value for `field` according to source priority.

    Returns (value, winning_source) — both None when no source has a value.
    """
    by_source: dict[str, str | None] = {}
    for o in offerings:
        val = getattr(o, field)
        if val is not None and o.source not in by_source:
            by_source[o.source] = val
    for src in priority:
        if src in by_source:
            return by_source[src], src
    return None, None


def _resolve_institution_type(
    members: list[Offering],
    care_types: list[str],
    has_school: bool,
    school_urns: list[str],
    gias_lookup: dict[str, tuple[str | None, str | None]],
) -> str:
    """Derive institution_type from the best available source.

    Priority: school phase_type > GIAS phase > Ofsted registration type
              > SBN name heuristic > LA care_type inference.
    """
    # 1. School phase_type (highest priority — describes the institution itself)
    if has_school:
        for o in members:
            if o.phase_type:
                mapped = _PHASE_TYPE_MAP.get(o.phase_type)
                if mapped:
                    return mapped

        # 1b. GIAS fallback — covers schools missing from school_census
        for urn in school_urns:
            if urn in gias_lookup:
                phase, type_group = gias_lookup[urn]
                if phase:
                    mapped = _GIAS_PHASE_MAP.get(phase)
                    if mapped:
                        return mapped
                    # "Not applicable" phase — use establishment_type_group
                    if type_group:
                        mapped = _GIAS_TYPE_GROUP_MAP.get(type_group)
                        if mapped:
                            return mapped

    # 2. Ofsted registration type
    for o in members:
        if o.ofsted_provider_type:
            mapped = _OFSTED_INSTITUTION_MAP.get(
                (o.ofsted_provider_type, o.ofsted_provider_subtype)
            )
            if mapped is None:
                mapped = _OFSTED_INSTITUTION_MAP.get((o.ofsted_provider_type, None))
            if mapped:
                return mapped

    # 2.5 Name-based heuristic for LA-only providers without school link
    if not has_school:
        for o in members:
            if o.provider_name:
                for pattern, inst_type in _NAME_SCHOOL_PATTERNS:
                    if pattern.search(o.provider_name):
                        return inst_type
                break  # only check one name

    # 3. Infer from care_type (LA-only providers)
    for ct in care_types:
        mapped = _CARE_TYPE_INSTITUTION_MAP.get(ct)
        if mapped:
            return mapped

    return "unknown"


def _flush_providers(conn, batch: list[dict]) -> None:
    if not batch:
        return
    with conn.cursor() as cur:
        for row in batch:
            cur.execute(INSERT_PROVIDER_SQL, row)
    conn.commit()


def _flush_sources(conn, batch: list[dict]) -> None:
    if not batch:
        return
    with conn.cursor() as cur:
        for row in batch:
            cur.execute(INSERT_SOURCE_SQL, row)
    conn.commit()


# ---------- Dagster asset ----------


@asset(
    group_name="draft", deps=["care_offerings"], automation_condition=PIPELINE_CONDITION
)
def providers(context: AssetExecutionContext, bsil_postgres: BsilPostgresResource):
    """Build draft.providers — coalesce care_offerings into unique providers
    using union-find on ofsted_urn and school_urn keys.
    """

    with bsil_postgres.get_connection() as conn:
        # ---- Phase 1: Load all care_offerings ----
        context.log.info("Phase 1: loading care_offerings")
        offerings: list[Offering] = []

        by_source_id: dict[tuple[str, str], list[int]] = defaultdict(list)
        by_ofsted_urn: dict[str, list[int]] = defaultdict(list)
        by_school_urn: dict[str, list[int]] = defaultdict(list)
        by_postcode: dict[str, list[int]] = defaultdict(list)

        with conn.cursor("providers_load_cursor", withhold=True) as cur:
            cur.execute(LOAD_OFFERINGS_SQL)
            for row in cur:
                idx = len(offerings)
                o = Offering(
                    id=row[0],
                    source=row[1],
                    source_id=row[2],
                    lad25cd=row[3],
                    care_type=row[4],
                    provider_name=row[5],
                    postcode=row[6],
                    ofsted_urn=row[7],
                    school_urn=row[8],
                    phase_type=row[9],
                    ofsted_provider_type=row[10],
                    ofsted_provider_subtype=row[11],
                )
                offerings.append(o)

                by_source_id[(o.source, o.source_id)].append(idx)
                if o.ofsted_urn and o.ofsted_urn != o.school_urn:
                    by_ofsted_urn[o.ofsted_urn].append(idx)
                if o.school_urn:
                    by_school_urn[o.school_urn].append(idx)
                if o.postcode:
                    by_postcode[o.postcode].append(idx)

        n = len(offerings)
        suspect_urn_count = sum(
            1 for o in offerings if o.ofsted_urn and o.ofsted_urn == o.school_urn
        )
        context.log.info(
            f"Loaded {n} care_offerings "
            f"({suspect_urn_count} with suspect ofsted_urn=school_urn, "
            f"excluded from ofsted index)"
        )

        # Load GIAS for institution_type fallback
        gias_lookup: dict[str, tuple[str | None, str | None]] = {}
        with conn.cursor() as cur:
            cur.execute(LOAD_GIAS_SQL)
            for urn, phase, type_group in cur:
                gias_lookup[urn] = (phase, type_group)
        context.log.info(f"Loaded {len(gias_lookup)} GIAS school records")

        # ---- Phase 2: Union-find ----
        context.log.info("Phase 2: union-find grouping")
        uf = UnionFind(n)

        # Pass 1: same (source, source_id)
        for indices in by_source_id.values():
            for i in range(1, len(indices)):
                uf.union(indices[0], indices[i])

        # Pass 2: same ofsted_urn
        for indices in by_ofsted_urn.values():
            for i in range(1, len(indices)):
                uf.union(indices[0], indices[i])

        # Pass 3: same school_urn
        for indices in by_school_urn.values():
            for i in range(1, len(indices)):
                uf.union(indices[0], indices[i])

        # Pass 4: same postcode + similar normalised name
        name_merge_count = 0
        for indices in by_postcode.values():
            if len(indices) < 2:
                continue
            normed = [(i, normalise_name(offerings[i].provider_name)) for i in indices]
            normed = [(i, nm) for i, nm in normed if nm]
            for a_pos in range(len(normed)):
                for b_pos in range(a_pos + 1, len(normed)):
                    i_a, name_a = normed[a_pos]
                    i_b, name_b = normed[b_pos]
                    if uf.find(i_a) == uf.find(i_b):
                        continue
                    if (
                        SequenceMatcher(None, name_a, name_b).ratio()
                        >= NAME_SIMILARITY_THRESHOLD
                    ):
                        uf.union(i_a, i_b)
                        name_merge_count += 1

        context.log.info(f"Pass 4: {name_merge_count} name+postcode merges")

        # ---- Phase 3: Extract connected components ----
        context.log.info("Phase 3: extracting components")
        components: dict[int, list[int]] = defaultdict(list)
        for i in range(n):
            components[uf.find(i)].append(i)

        num_providers = len(components)
        context.log.info(f"Found {num_providers} unique providers")

        # ---- Phase 4: Resolve fields + write ----
        context.log.info("Phase 4: resolving fields and writing tables")

        # Fresh tables
        with conn.cursor() as cur:
            cur.execute(DROP_SOURCES_SQL)
            cur.execute(DROP_PROVIDERS_SQL)
            cur.execute(CREATE_PROVIDERS_SQL)
            cur.execute(CREATE_SOURCES_SQL)
            conn.commit()

        provider_batch: list[dict] = []
        source_batch: list[dict] = []
        bridge_count = 0
        excluded_count = 0
        redacted_cm_count = 0

        for member_indices in components.values():
            members = [offerings[i] for i in member_indices]

            # Collect URNs across component
            ofsted_urns = sorted(
                {
                    o.ofsted_urn
                    for o in members
                    if o.ofsted_urn and o.ofsted_urn != o.school_urn
                }
            )
            school_urns = sorted({o.school_urn for o in members if o.school_urn})

            # Provider ID
            if ofsted_urns:
                provider_id = f"ofsted:{ofsted_urns[0]}"
            elif school_urns:
                provider_id = f"school:{school_urns[0]}"
            else:
                # LA standalone — use first member's source_id
                provider_id = f"la:{members[0].source_id}"

            # Aggregate care_types early — needed for name priority decision
            care_types = sorted({o.care_type for o in members if o.care_type})

            # Field resolution priority depends on school linkage
            has_school = bool(school_urns)
            priority = _SCHOOL_PRIORITY if has_school else _NON_SCHOOL_PRIORITY

            # For multi-care-type non-school providers, prefer Ofsted's operator
            # name over the LA's care-offering name
            name_priority = priority
            if not has_school and len(care_types) > 1:
                name_priority = ["ofsted", "la_scrape", "free_breakfast"]

            provider_name, name_source = _resolve_field(
                members, "provider_name", name_priority
            )
            postcode, postcode_source = _resolve_field(members, "postcode", priority)
            lad25cd, lad25cd_source = _resolve_field(members, "lad25cd", priority)

            field_sources = {}
            if name_source:
                field_sources["provider_name"] = name_source
            if postcode_source:
                field_sources["postcode"] = postcode_source
            if lad25cd_source:
                field_sources["lad25cd"] = lad25cd_source
            metadata = {"field_sources": field_sources} if field_sources else {}

            # Aggregate arrays
            sources = sorted({o.source for o in members})

            institution_type = _resolve_institution_type(
                members, care_types, has_school, school_urns, gias_lookup
            )

            excluded = (
                provider_id.startswith("la:") and "childminder" not in care_types
            ) or institution_type == "school_secondary"
            redacted_childminder = (
                provider_name is None
                and "childminder" in care_types
                and sources == ["ofsted"]
            )

            if ofsted_urns and school_urns:
                bridge_count += 1
            if excluded:
                excluded_count += 1
            if redacted_childminder:
                redacted_cm_count += 1

            metadata["sources"] = sources
            metadata["offering_count"] = len(members)
            if redacted_childminder:
                metadata["redacted_childminder"] = True

            provider_batch.append(
                {
                    "provider_id": provider_id,
                    "provider_name": provider_name,
                    "postcode": postcode,
                    "lad25cd": lad25cd,
                    "ofsted_urn": ofsted_urns[0] if ofsted_urns else None,
                    "school_urn": school_urns[0] if school_urns else None,
                    "institution_type": institution_type,
                    "care_types": care_types,
                    "excluded": excluded,
                    "metadata": json.dumps(metadata),
                }
            )

            for o in members:
                source_batch.append(
                    {
                        "provider_id": provider_id,
                        "care_offering_id": o.id,
                        "source": o.source,
                        "source_id": o.source_id,
                    }
                )

            if len(provider_batch) >= BATCH_SIZE:
                _flush_providers(conn, provider_batch)
                provider_batch.clear()
            if len(source_batch) >= BATCH_SIZE:
                _flush_sources(conn, source_batch)
                source_batch.clear()

        # Flush remaining
        _flush_providers(conn, provider_batch)
        _flush_sources(conn, source_batch)

        context.log.info(
            f"Wrote {num_providers} providers, "
            f"{n} provider_sources rows, "
            f"{bridge_count} bridge providers (both URNs), "
            f"{excluded_count} excluded (la: with no ofsted/school linkage, non-childminder), "
            f"{redacted_cm_count} redacted childminders, "
            f"{name_merge_count} name+postcode merges, "
            f"{suspect_urn_count} suspect ofsted_urns skipped"
        )

    return {
        "total_offerings": MetadataValue.int(n),
        "unique_providers": MetadataValue.int(num_providers),
        "bridge_providers": MetadataValue.int(bridge_count),
        "excluded_providers": MetadataValue.int(excluded_count),
        "redacted_childminders": MetadataValue.int(redacted_cm_count),
        "name_postcode_merges": MetadataValue.int(name_merge_count),
        "suspect_ofsted_urns_skipped": MetadataValue.int(suspect_urn_count),
    }
