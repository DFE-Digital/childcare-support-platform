# Field Discovery Methodology

## Overview

This document describes the process for discovering, extracting, and cataloguing all available fields from LA Family Information Service (FIS) provider data. The raw scrape data in `la.scrape_results` contains far more information than the scraper columns capture — the extractors systematically parse that raw content into structured records.

## Architecture

### Platform-level extractors

Extractors are organised at the **platform level**, not per-LA. All LAs on the same platform (e.g. OpenObjects KB5, Synergy, Marketplace) share the same HTML/JSON template, so one extractor handles all LAs on that platform.

```
packages/data-pipeline/bsil_pipeline/extractors/
  base.py              # BaseExtractor ABC + ExtractedProvider + shared helpers
  __init__.py          # Registry: platform_key -> ExtractorClass
  openobjects.py       # ~30 LAs
  synergy.py           # ~15 LAs
  marketplace.py       # ~20 LAs
  essex.py             # 12 LAs
  ...                  # 19 more platform extractors
```

### Greedy extraction

Each extractor captures **every** label/value pair it finds, not a predefined list. This means:

- Running across ALL providers captures the full field inventory
- Fields that only appear on certain provider types get captured automatically
- Anything that doesn't map to a canonical key goes into `extra{}`

### Canonical field keys

Fields are mapped to standard keys where possible:

| Category   | Keys                                                                        |
| ---------- | --------------------------------------------------------------------------- |
| Identity   | `provider_name`, `provider_type`                                            |
| Address    | `address_line1`..`3`, `town`, `county`, `postcode`, `latitude`, `longitude` |
| Contact    | `phone`, `phone_secondary`, `email`, `website`, `fax`                       |
| Ofsted     | `ofsted_urn`, `ofsted_rating`, `ofsted_date`, `ofsted_report_url`           |
| Capacity   | `places_total`, `places_available`, `age_from_months`, `age_to_years`       |
| Schedule   | `opening_hours_raw`, `session_types`, `term_time_only`, `weeks_per_year`    |
| Fees       | `fees_raw`, `funded_2yr`, `funded_3_4yr`, `funded_30hrs`                    |
| Facilities | `has_garden`, `has_wheelchair_access`, `facilities`                         |
| SEND       | `send_provision`, `send_experience_areas`                                   |
| Other      | `description`, `languages`, `school_pickups`                                |
| Catch-all  | `extra{}` — platform-specific fields that don't map to canonical keys       |

### Classification

Every provider gets a `classification` array mapping its source category labels to our `CareType` enum:

- `private_nursery` — day nurseries, pre-schools, playgroups, sessional care
- `school_based_nursery` — school nursery classes, maintained nurseries
- `childminder` — registered childminders
- `breakfast_club` — breakfast provision
- `after_school_club` — after-school, wraparound, out-of-school care
- `holiday_club` — holiday schemes and playschemes

The mapping is defined in `CARE_TYPE_MAPPING` in `extractors/base.py`. Original labels are preserved in `source_classification` for audit and refinement.

#### Two-tier classification: structured vs inferred

Classification uses a two-tier approach:

1. **Structured classification** (preferred): Source labels from the platform's own type fields are mapped through `CARE_TYPE_MAPPING`. This is the primary classification path used by all extractors that have structured type data (e.g. OpenObjects `provider_type`, FIS Wales card header suffix, Devon name suffix).

2. **Name-based inference** (fallback): When an extractor produces no structured classification, `infer_classification_from_name()` in `base.py` applies regex patterns to the `provider_name` to infer care type. This runs in `la_extract.py` after `extractor.extract()` and adds the `classification_inferred_from_name` warning tag to distinguish inferred from structured classifications.

The inference engine uses ordered patterns (specific multi-word patterns first, generic single-word last) to handle multi-type providers correctly (e.g. "ABC Nursery & After School Club" matches both `private_nursery` and `after_school_club`).

**Non-childcare suppression**: Labels like `"family hub"`, `"children's centre"`, `"study support"`, and `"service"` are mapped to `None` in `CARE_TYPE_MAPPING` so they are explicitly excluded from classification rather than appearing as unmapped.

#### Name-suffix parsing (Devon, FIS Wales)

Some platforms embed the provider type in the provider name using a "Name - Type" format (e.g. "Brewer, Kelly - Childminder", "Little Stars - Day Nursery"). The Devon and FIS Wales extractors split on `-` and feed the type suffix into `source_labels` for structured classification. This produces higher-quality results than name inference since the labels are explicit from the source site.

## Running Field Discovery

### Prerequisites

```bash
# Set database connection env vars
export BSIL_DB_HOST=localhost
export BSIL_DB_PORT=5432
export BSIL_DB_USER=your_user
export BSIL_DB_PASSWORD=your_password
export BSIL_DB_NAME=bsil
```

### CLI usage

```bash
cd packages/data-pipeline

# Full discovery (all platforms)
python ../../scripts/field_discovery.py --format all --output discovery_report.txt

# Single platform
python ../../scripts/field_discovery.py --platform openobjects_kb5 --format fields

# Single LA
python ../../scripts/field_discovery.py --lad E09000022 --format all

# Quick test (limit providers)
python ../../scripts/field_discovery.py --platform synergy --limit 50 --format summary
```

### Report formats

| Format           | Description                                                       |
| ---------------- | ----------------------------------------------------------------- |
| `summary`        | Compact per-platform table: LA count, provider count, field stats |
| `fields`         | Per-field coverage with counts, percentages, and sample values    |
| `classification` | Care-type mapping stats, unmapped source labels                   |
| `residual`       | Extra fields that may warrant promotion to canonical keys         |
| `all`            | All of the above                                                  |

## Verification Checklist

After running discovery, verify:

1. **`provider_name` coverage ~100%** per platform — anything less suggests a parsing bug
2. **`postcode` coverage** matches `provider_postcode` from `scrape_results` for `success` rows
3. **`classification` non-empty for >50% of providers** per platform — empty means unmapped labels need adding to `CARE_TYPE_MAPPING`
4. **`field_count` distribution** — providers with far fewer fields suggest HTML variants the extractor doesn't handle
5. **No extraction errors** — errors in the report indicate extractor bugs
6. **No council FIS emails** as provider contact — check `email` field doesn't contain shared inboxes like `fis@council.gov.uk`
7. **No invalid emails** — the `email` field should match `*@*.*` format (no names, phone numbers, or placeholders)
8. **No HTML tags** in text fields — check `extra{}` as well as canonical fields

## Iterative Refinement

The discovery process is iterative:

1. **Run discovery** → produces coverage report
2. **Review unmapped labels** → add to `CARE_TYPE_MAPPING` in `base.py`
3. **Review extra fields** → promote high-coverage fields to canonical keys in the extractor
4. **Review errors** → fix extractor bugs for HTML/JSON variants
5. **Re-run discovery** → verify improvements

## Critical QA Checks for New Extractors

These checks are **mandatory** after building any new extractor or modifying an existing one. They catch real bugs discovered in the initial extraction round.

### 1. Cross-LA Provider Assignment (Shared-Platform Scrapers)

**Bug pattern**: Scrapers that use a module-level cache (scrape once, serve multiple LAs) can broadcast ALL providers to EVERY LA unless filtered. This caused ~60,000 duplicate rows in the initial run.

**Affected scrapers**: Any scraper with `_cache: list | None = None` at module level (Devon, Essex, Surrey, FamilySupportNI, and any future shared-platform scraper).

**Check**: After running the scraper for a shared platform, query:

```sql
SELECT provider_id, count(DISTINCT lad25cd) as la_count
FROM la.scrape_results
WHERE platform = 'your_platform'
GROUP BY provider_id
HAVING count(DISTINCT lad25cd) > 1
LIMIT 10;
```

If this returns results, providers are being duplicated across LAs. The fix is to filter each provider to its correct LA in `scrape_la()` using one of:

- **`postcode_to_lad(postcode)`** — for providers with postcodes (most platforms)
- **`coords_to_lad(lat, lon, target_lads)`** — for providers with coordinates but no postcodes (e.g. Devon)

Both are in `bsil_pipeline/utils/postcode_lookup.py`, backed by the ONSPD postcode→LAD lookup file at `data/postcode_lad_lookup.csv.gz`.

### 1a. Multi-Instance Provider ID Collisions

**Bug pattern**: Some shared platforms have multiple independent instances (e.g. Synergy has 14+ separate sites: `fisonline.lancashire.gov.uk`, `caya-apps.derbyshire.gov.uk`, `fis.cornwall.gov.uk`, etc.). Each instance uses its own auto-increment ID sequence, so provider_id `"10052"` on Lancashire is a completely different provider from `"10052"` on Derbyshire. If extraction deduplicates with `DISTINCT ON (provider_id)` globally, providers from different instances collide and one is silently dropped.

**Affected platforms**: Synergy (14 instances, 7.2% collision rate = 441 providers lost before fix). Other multi-instance platforms should be checked if added in future.

**Check**: Compare per-instance unique counts against global dedup count:

```sql
SELECT
    substring(source_url from 'https?://([^/]+)') AS domain,
    count(DISTINCT provider_id) AS unique_per_instance
FROM la.scrape_results
WHERE source_url LIKE '%ynergy%' AND scrape_status = 'success'
GROUP BY domain;

-- vs global dedup:
SELECT count(*) FROM (
    SELECT DISTINCT ON (provider_id) provider_id
    FROM la.scrape_results
    WHERE source_url LIKE '%ynergy%' AND scrape_status = 'success'
) sub;
```

If the sum of per-instance counts exceeds the global dedup count, there are collisions.

**Fix**: `la_extract.py` now uses `DISTINCT ON (substring(source_url from 'https?://([^/]+)'), provider_id)` to scope deduplication by source domain. This is safe for single-instance shared platforms too (all rows share one domain, so the behaviour is unchanged).

**Distinguishing single-instance vs multi-instance shared platforms**:

- **Single-instance** (Devon, Essex, Surrey, FamilySupportNI, Marketplace): One website serves multiple LAs. Provider IDs are globally unique. Domain-scoped dedup is equivalent to global dedup.
- **Multi-instance** (Synergy): Multiple independent websites, each serving a cluster of LAs. Provider IDs are only unique within each instance. Domain-scoped dedup is essential.

### 2. Label/Value Extraction Mismatch

**Bug pattern**: `extract_dt_dd()` returns labels like `"email:"` (with trailing colon) but the extractor's `_LABEL_MAP` has `"email"` (without colon). Results: canonical fields show near-zero coverage while the same data appears at 80%+ in `extra{}`.

**Check**: In the field discovery report, compare canonical field coverage with extra field coverage. If an extra field name matches a canonical key (e.g. `"email:"` in extra vs `email` canonical at 0.5%), there's a label mismatch.

**Prevention**: All shared helpers (`extract_dt_dd()`, `extract_strong_text_pairs()`, `extract_labelled_spans()`, `_extract_eyo_pairs()`) now strip trailing colons and produce colon-free lowercase labels. If you write custom label extraction, always strip colons.

### 3. HTML Tags in Text Fields

**Bug pattern**: Some platforms store HTML in JSON fields or dd values. Direct storage produces `extracted_data` values like `"<p>Description here</p>"`.

**Affected platforms**: Blackpool (Contensis HTML in JSON), Essex (HTML in Website/Description fields), OpenObjects (rare).

**Check**: After extraction, query for HTML tags in text fields:

```sql
SELECT lad25cd, provider_id,
       extracted_data->>'description' as desc
FROM la.extract_results
WHERE extracted_data->>'description' LIKE '%<%'
LIMIT 10;
```

**Fix**: Use `strip_html_tags()` from `extractors/base.py` for any field that might contain HTML.

### 4. Council Address vs Provider Address

**Bug pattern**: Some detail pages display the council's own address (e.g. "County Hall, EX2 4QD") rather than the provider's address. If the extractor naively extracts the address from the page, ALL providers get the same council address.

**Check**: Look for suspicious address uniformity:

```sql
SELECT extracted_data->>'postcode' as pc, count(*) as cnt
FROM la.extract_results
WHERE platform = 'your_platform'
GROUP BY 1
ORDER BY cnt DESC
LIMIT 5;
```

If the top postcode has hundreds of providers, it's probably a council address. Cross-reference with the council's own postcode.

**Example**: Devon detail pages show "Devon County Council, County Hall, EX2 4QD" — the extractor must skip these and rely on lat/lon from the JSON metadata instead.

### 5. Classification Coverage

**Bug pattern**: New provider type labels appear that aren't in `CARE_TYPE_MAPPING`, leaving providers unclassified.

**Check**: Run `--format classification` and review:

```
UNMAPPED SOURCE LABELS:
  "Holiday Activity"          1,234 providers  → add to CARE_TYPE_MAPPING
  "Out of school provision"     567 providers  → add to CARE_TYPE_MAPPING
```

**Action**: Add all high-frequency unmapped labels to `CARE_TYPE_MAPPING` in `extractors/base.py`. Common patterns:

- Platform-specific synonyms (e.g. "sessional day care" = "private_nursery")
- Welsh language labels (e.g. "meithrinfa dydd" = "private_nursery")
- Compound labels (e.g. "breakfast or after school club" = "after_school_club")
- Truncated labels from fixed-width database fields
- Non-childcare labels that should be explicitly suppressed (map to `None`)

### 5a. Name-Inference Accuracy

**Bug pattern**: The name-based inference fallback (`infer_classification_from_name`) can produce false positives when provider names contain ambiguous keywords. For example, "Academy" in a business name that isn't a school, or "Nursery" in a garden centre name.

**Check**: After extraction, sample inferred classifications per platform:

```sql
SELECT platform,
       extracted_data->>'provider_name' AS name,
       classification
FROM la.extract_results
WHERE 'classification_inferred_from_name' = ANY(extraction_warnings)
ORDER BY random()
LIMIT 20;
```

Spot-check 20 providers per platform to verify the inference is correct.

**Check**: Compare inference rate across platforms. Platforms with structured type data should have near-zero inference:

```sql
SELECT platform,
       count(*) FILTER (WHERE 'classification_inferred_from_name' = ANY(extraction_warnings)) AS inferred,
       count(*) FILTER (WHERE classification != '{}' AND NOT ('classification_inferred_from_name' = ANY(extraction_warnings))) AS structured,
       count(*) FILTER (WHERE classification = '{}') AS unclassified,
       count(*) AS total
FROM la.extract_results
GROUP BY platform
ORDER BY platform;
```

If a platform with known type fields shows high inference rates, the extractor is likely not extracting type labels correctly — investigate the extractor rather than relying on inference.

**Important**: Name inference is a **fallback**, not a replacement for structured classification. When building new extractors, always look for structured type fields first (API fields, HTML labels, card headers, category tags). Only rely on inference for platforms that genuinely have no type metadata.

### 5b. Name-Suffix Extraction

**Bug pattern**: Platforms like Devon and FIS Wales use "Name - Type" format in provider names. If the extractor doesn't split this, the type suffix is lost and the provider falls back to name inference (which is less precise since it uses generic patterns rather than the explicit label).

**Check**: For platforms where provider names contain `-`, verify the type suffix is being extracted:

```sql
SELECT extracted_data->>'provider_name' AS name,
       source_classification,
       classification
FROM la.extract_results
WHERE platform = 'devon'
  AND extracted_data->>'provider_name' LIKE '% - %'
LIMIT 10;
```

The `source_classification` should contain the type suffix (e.g. `["Childminder"]`), not be empty.

**Action**: If a new platform uses this naming pattern, add `rsplit(" - ", 1)` parsing in the extractor (see `devon.py` or `fis_wales.py` for the pattern). Don't modify `provider_name` — keep the full string for display and feed only the type suffix into `source_labels`.

### 6. Multiple Type Labels → Classification

**Bug pattern**: Some platforms have multiple fields contributing provider type labels (e.g. Marketplace has both `"main service type"` and `"childcare type"`). If only one is used for classification, the type coverage is incomplete.

**Check**: Compare `source_classification` coverage in the report. If one platform shows many providers with empty classification but the extra fields contain type-like labels, the extractor is missing a type source.

**Fix**: Collect type labels from ALL relevant fields. See the Marketplace extractor for an example using `_TYPE_LABELS` set to match against multiple dt labels.

### 7. Phone/Email Deduplication

**Bug pattern**: Some platforms concatenate contact info. Known patterns:

- Duplicated numbers: `"01234 567890 01234 567890"` (OpenObjects)
- Numbers with label suffixes: `"01234 567890 Fax: 01234 567891"` (OpenObjects)
- Trailing dots: `"01onal 234567."` (Liquidlogic)

**Check**: Spot-check phone fields for suspiciously long numbers or repeated patterns:

```sql
SELECT extracted_data->>'phone', count(*)
FROM la.extract_results
WHERE length(extracted_data->>'phone') > 15
GROUP BY 1 ORDER BY 2 DESC LIMIT 10;
```

**Fix**: The OpenObjects extractor strips labelled suffixes (Fax:, Mobile:, Tel:) before dedup, then checks if the first half equals the second half. Liquidlogic strips trailing dots.

### 8. Postcode Pollution

**Bug pattern**: Some platforms append navigational text to postcodes (e.g. "AB12 3CD Get directions to this provider").

**Check**: Look for postcodes longer than 8 characters:

```sql
SELECT extracted_data->>'postcode'
FROM la.extract_results
WHERE length(extracted_data->>'postcode') > 8
LIMIT 10;
```

**Fix**: Use `extract_postcode()` from `base.py` to re-extract just the postcode pattern from polluted strings.

### 9. Residual Label Map Gaps

**Bug pattern**: High-frequency labels in `extra{}` that should map to canonical keys. This happens when different platforms use different labels for the same field (e.g. `"e-mail"` vs `"email"`, `"telephone number"` vs `"telephone"`).

**Check**: Query for the most common extra keys per platform:

```sql
SELECT platform,
       key AS extra_key,
       count(*) AS cnt
FROM la.extract_results,
     jsonb_each_text(extracted_data->'extra') AS kv(key, value)
GROUP BY platform, key
ORDER BY cnt DESC
LIMIT 30;
```

**Fix**: Add the missing labels to the extractor's `_LABEL_MAP` dict. Common missed variants:

- `"e-mail"` / `"email address"` / `"contact email"` → `email`
- `"telephone number"` / `"contact telephone"` → `phone`
- `"web site"` / `"web address"` → `website`
- `"age ranges"` / `"available to age groups"` / `"age groups"` → `age_range`
- `"description"` (in JSON extractors that map by key rather than label)

### 10. Provider Name Contamination

**Bug pattern**: Page titles or portal names stored as `provider_name` instead of the actual provider name. OpenObjects KB5 pages have `<h1>` containing the portal name (e.g. "Cambridgeshire Online") rather than the provider name for some page types.

**Check**: Look for the most common provider names per platform:

```sql
SELECT platform,
       extracted_data->>'provider_name' AS name,
       count(*) AS cnt
FROM la.extract_results
GROUP BY platform, name
ORDER BY cnt DESC
LIMIT 20;
```

If a single name appears hundreds of times, it's likely a portal/page title, not a provider name.

**Fix**: The OpenObjects extractor uses two-layer portal name detection:

1. **Dynamic detection** (preferred): Read `<meta name="application-name" content="...">` from the HTML. This meta tag is present on all KB5 pages and contains the exact portal name. The extractor's `_detect_portal_name()` function reads this tag and passes it to `_is_portal_name()` for filtering.

2. **Hardcoded fallback**: The `_PORTAL_NAMES` set in `openobjects.py` contains known portal names as a safety net. This catches cases where the meta tag is missing.

The dynamic approach was added after discovering that 8 portals (Glosfamilies Directory, Wokingham Directory, Suffolk InfoLink, etc.) were missing from the hardcoded set, causing 10,196 providers to have portal names stored instead of real provider names. The `<meta name="application-name">` tag reliably identifies all current and future KB5 portal names without needing to maintain the hardcoded set.

**Impact of contamination on classification**: Portal names like "Glosfamilies Directory" contain no childcare keywords, so the name inference engine can't classify these providers. Fixing the contamination recovered ~1,480 additional classifications from names like "Berwick Rascals Day Nursery" → `private_nursery`.

**When adding new KB5 portals**: No action needed — the dynamic detection will automatically handle them. The hardcoded `_PORTAL_NAMES` set is only a fallback for edge cases.

### 11. Council Email Filtering

**Bug pattern**: Council FIS shared inboxes (e.g. `fis@nelincs.gov.uk`, `familysupportni@hscni.net`) stored as provider email. This happens when:

- The detail page doesn't have provider contact info and the council's own "Contact us" email is on the page
- NE Lincs: 941/1,072 providers had the council FIS email because Cloudflare-decoded email was the council's
- FamilySupportNI: shared inbox on all detail pages

**Check**:

```sql
SELECT extracted_data->>'email' AS email, count(*) AS cnt
FROM la.extract_results
WHERE extracted_data->>'email' IS NOT NULL
GROUP BY 1
ORDER BY cnt DESC
LIMIT 20;
```

If one email appears for hundreds of providers, it's a council inbox.

**Fix**: Use `is_council_email()` from `base.py` to detect shared inboxes. Move to `extra.council_email` rather than discarding entirely, so the information is preserved but not used as provider contact.

### 12. Malformed Email Validation

**Bug pattern**: Non-email strings stored in the `email` field. Seen in:

- FIS Wales: person names (e.g. `"grace roberts"`) extracted from envelope icon text
- Synergy: phone numbers and placeholders (e.g. `"Contact details withheld"`) in the email field

**Check**:

```sql
SELECT extracted_data->>'email' AS email
FROM la.extract_results
WHERE extracted_data->>'email' IS NOT NULL
  AND extracted_data->>'email' NOT LIKE '%@%.%'
LIMIT 20;
```

**Fix**: Use `validate_email()` from `base.py` which checks the `*@*.*` pattern. Move invalid values to `extra.invalid_email` for audit.

### 13. Outer-Only Postcodes (Northern Ireland)

**Bug pattern**: NI postcodes often appear as outer code only (e.g. `BT28` without the inner code like `BT28 1AA`). These are valid but partial — they identify the postcode district but not the specific delivery point.

**Check**: Look for short postcodes in NI:

```sql
SELECT extracted_data->>'postcode' AS pc, count(*)
FROM la.extract_results
WHERE platform = 'familysupportni'
  AND extracted_data->>'postcode' ~ '^BT\d{1,2}$'
GROUP BY 1 ORDER BY 2 DESC;
```

**Treatment**: Accept as-is but flag in `extraction_warnings` so downstream processing knows these are partial. The warning format is: `"outer-only postcode: BT28 (no inner code)"`.

## New Extractor Checklist

When adding a new extractor, complete this checklist:

- [ ] **Read raw data samples**: Query `la.scrape_results` for 3-5 rows, inspect `raw_html`/`raw_json` structure
- [ ] **Build extractor**: Create `extractors/{platform}.py` with greedy extraction
- [ ] **Register**: Add to `extractors/__init__.py` registry
- [ ] **Run field discovery**: `python scripts/field_discovery.py --platform {platform} --format all`
- [ ] **Check provider_name**: Should be ~100% for success rows
- [ ] **Check postcode**: Should match `provider_postcode` from scrape_results
- [ ] **Check for cross-LA duplication**: If shared-platform scraper, verify no duplicate provider_ids across LAs
- [ ] **Check canonical vs extra**: Are high-coverage extra fields that should be canonical?
- [ ] **Check for HTML in text**: Query for `<%` in description and other text fields
- [ ] **Check classification**: Are there unmapped source labels? Add to `CARE_TYPE_MAPPING`
- [ ] **Check inference rate**: If >50% of classified providers have `classification_inferred_from_name`, the extractor is likely missing structured type fields — investigate before relying on inference
- [ ] **Check name-suffix pattern**: If provider names contain `-`, the suffix is likely a type label — add `rsplit` parsing
- [ ] **Check for council address contamination**: Is the top postcode suspiciously common?
- [ ] **Run extraction via Dagster**: `dagster asset materialize --select la_extract_results --partition {platform}`

## Running Full Extraction via Dagster

Once extractors are validated, run the full extraction through Dagster:

```bash
# Trigger extraction for a single platform
dagster asset materialize --select la_extract_results --partition openobjects_kb5

# Or use the Dagster UI to trigger backfills per partition
```

Results are stored in `la.extract_results` with the same primary key as `la.scrape_results`.

## Residual Analysis

After full extraction, run residual analysis to check for data left behind:

**JSON platforms** (exhaustive): Compare keys in `raw_json` against keys in `extracted_data`. Any unmapped key is a residual.

**HTML platforms** (sampled): Re-parse HTML, find all structural label/value pairs, check which labels produced content not in `extracted_data`.

The `--format residual` flag on the CLI does this automatically, suggesting actions per residual field:

- **PROMOTE**: High-value field that should become a canonical key
- **REVIEW**: Moderate coverage, worth investigating
- **SKIP**: Cosmetic/navigational content
- **keep in extra**: Low coverage, fine to leave in `extra{}`

### Per-Platform Extra Key Frequency (SQL)

After extraction, use this query to identify the most common extra keys per platform that may indicate label map gaps:

```sql
SELECT platform,
       key AS extra_key,
       count(*) AS cnt,
       round(100.0 * count(*) / platform_total.total, 1) AS pct
FROM la.extract_results er,
     jsonb_each_text(er.extracted_data->'extra') AS kv(key, value),
     LATERAL (
       SELECT count(*) AS total
       FROM la.extract_results er2
       WHERE er2.platform = er.platform
     ) platform_total
GROUP BY platform, key, platform_total.total
HAVING count(*) > 10
ORDER BY platform, cnt DESC;
```

Review any extra key with >10% coverage — it likely warrants either promotion to a canonical key or addition to the extractor's `_LABEL_MAP`.
