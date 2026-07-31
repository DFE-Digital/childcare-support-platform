# PostHog Analytics — Data Collection & Privacy

## Overview

This service collects anonymous usage statistics via PostHog in **cookieless mode** to understand how families interact with the childcare support checker and cost estimator. No personal information is collected or stored.

## PostHog Configuration

- **Mode:** `cookieless_mode: "always"` — no cookies, no localStorage tokens
- **Session recording:** Disabled
- **Autocapture:** Disabled (prevents accidental PII capture from DOM)
- **Transport:** Reverse-proxied through CloudFront at `/ingest` (same-origin)

## Events Emitted

### `step_completed`

Fired when a user completes each form step. Used for funnel/drop-off analysis.

| Step        | Properties                      |
| ----------- | ------------------------------- |
| Postcode    | `lad25cd`, `iod_decile`, `form` |
| Partner     | `has_partner`                   |
| Immigration | `settled_in_uk`                 |
| Working     | `working`, `is_studying`        |
| Benefits    | `receives_benefits`             |
| Children    | `child_count`, `youngest_band`  |
| Childcare   | `care_types_sought`             |

All events also carry `step` (step name) and `form` ("support" or "costs").

### `schemes_eligible`

Fired once when the user reaches the results page. Carries the full coarsened profile plus which government schemes the family is eligible for.

Properties: `lad25cd`, `iod_decile`, `has_partner`, `settled_in_uk`, `working`, `is_studying`, `receives_benefits`, `child_count`, `youngest_band`, `care_types_sought`, `schemes`, `form`.

### `provider_search`

Fired when the user submits a postcode search on the provider search page.

Properties: `lad25cd`, `iod_decile`, `care_types`, `sort_by`, `funded_hours_only`, `child_age_bands`.

### `provider_filter_changed`

Fired when any filter or sort option changes (care type, sort, funded hours, child selection).

Properties: `care_types`, `sort_by`, `funded_hours_only`, `child_age_bands`.

Always includes the full filter state snapshot (not just the changed field).

### `provider_detail_viewed`

Fired when the user opens a provider detail modal (from list or map).

Properties: `distance_band`.

### `provider_shortlisted`

Fired when the user adds or removes a provider from their shortlist.

Properties: `shortlist_care_types` (deduplicated care types across all currently-shortlisted providers).

### `provider_zoom_to_la`

Fired when the user clicks "Show me" to zoom to the full LA boundary.

Properties: `lad25cd`.

### `provider_zoom_in` / `provider_zoom_out`

Fired after a user settles at a new zoom level for 5 seconds (debounced). Only fires if net zoom changed.

Properties: `zoom_level`, `source` ("keyboard" or "button").

### `provider_show_more`

Fired when the user clicks "Show more" to load the next batch of providers.

Properties: `page` (batch number: 2, 3, 4...).

## Field Definitions & Coarsening

| Field                  | Source                            | Coarsening                                 | Values                                          |
| ---------------------- | --------------------------------- | ------------------------------------------ | ----------------------------------------------- |
| `lad25cd`              | Postcode → LAD lookup             | LAD level (not postcode)                   | ~361 LA codes                                   |
| `iod_decile`           | Postcode → LSOA → IoD 2025        | Already coarse (3,375 LSOAs per decile)    | 1–10 (England only)                             |
| `has_partner`          | "Do you live with a partner?"     | None needed (binary)                       | true/false                                      |
| `settled_in_uk`        | Immigration status                | Collapsed from 6 categories to binary      | true = british/irish/settled; false = all other |
| `working`              | Working status of either parent   | Collapsed from 4 income bands to binary    | true = any employment; false = not working      |
| `is_studying`          | "Are you studying?"               | None needed (binary)                       | true/false                                      |
| `receives_benefits`    | Qualifying benefits selection     | Collapsed from specific benefits to binary | true = any qualifying benefit                   |
| `child_count`          | Number of children entered        | Capped at 3                                | 1, 2, or 3 (meaning 3+)                         |
| `youngest_band`        | Youngest child's birth month/year | Age bands (not exact age)                  | "0-4" or "5+"                                   |
| `care_types_sought`    | Childcare selections              | Category names only                        | Array of type IDs                               |
| `schemes`              | Computed eligibility              | Scheme IDs (many-to-one from inputs)       | Array of scheme IDs                             |
| `distance_band`        | Provider's distance from postcode | Banded into 5 ranges                       | "<1mi", "1-3mi", "3-5mi", "5-10mi", "10+mi"     |
| `child_age_bands`      | Selected children's ages          | Collapsed to two bands                     | `["0-4"]`, `["5+"]`, or `["0-4", "5+"]`         |
| `shortlist_care_types` | All shortlisted providers         | Deduplicated category set                  | Array of care type IDs                          |
| `zoom_level`           | MapLibre zoom after action        | Integer                                    | Typically 8–16                                  |
| `source`               | What triggered the zoom           | Input modality                             | "keyboard" or "button"                          |
| `page`                 | Which batch of results            | Sequential page number                     | 2, 3, 4... (first page loads automatically)     |

## What Is Explicitly Excluded

The following are **never sent** to PostHog:

| Data                                     | Reason                                                                |
| ---------------------------------------- | --------------------------------------------------------------------- |
| Child names                              | Direct personal identifier                                            |
| Exact birth month/year                   | Date of birth is PII                                                  |
| Full postcode or outward code            | Too granular geographically                                           |
| Specific immigration category            | Protected characteristic; pre-settled/NRPF populations are very small |
| Specific benefits (UC, ESA, etc.)        | Reveals health conditions (ESA = disability) and financial hardship   |
| SEND/disability details                  | Protected health information                                          |
| DLA/PIP/registered blind status          | Protected health information                                          |
| Foster/care leaver status                | Child safeguarding sensitive; extremely small populations             |
| EHCP status                              | Educational SEN — small populations per area                          |
| Income thresholds/amounts                | Financial data                                                        |
| National Insurance number presence       | Links to identity                                                     |
| Provider IDs or names                    | Could reveal user's specific childcare choices                        |
| Provider care types + distance combined  | In sparse areas, care type + distance narrows to individual providers |
| Specific age bracket (16-17, 18-20, 21+) | Combined with other fields, could identify in small areas             |

## Re-identification Risk Analysis

### Geographic floor

LAD is the geographic unit (~361 districts). The smallest LAD (City of London) has ~10,000 residents. Median LAD population is ~150,000.

### Combinatorial space

Maximum combinations per LAD from the captured fields:

```
decile (10) x partner (2) x working (2) x studying (2) x
benefits (2) x child_count (3) x age_band (2) x care_types (~10) = ~9,600
```

With a median LAD population of 150,000 and ~8M UK families with children (~22,000 per average LAD), average bucket size is ~2.3 families per exact combination. However:

- Most combinations are **dense** (working, partnered, 1 child aged 0-4, nursery = extremely common)
- Sparse combinations (not working, no partner, 3+ children, 5+) lack the **identifying specifics** (which benefit, which disability, exact age) needed for re-identification
- The `schemes` field is a **lossy compression** of inputs — dozens of different input profiles produce identical scheme sets

### Residual session linkage

PostHog cookieless mode generates a `$session_id` derived from IP + User-Agent + date. This groups events within a single browsing session. An analyst with PostHog access could view all step events from one session together.

**Mitigation:** The coarsened fields are designed to be safe even when combined. The worst-case scenario (all fields visible for one session) is equivalent to: "a working couple with 2 young children in Westminster (decile 7) looking for nursery + breakfast club, eligible for 30 hours + TFC". This describes thousands of families in that LA.

### Why this is acceptable under GDPR/ICO guidance

1. **No direct identifiers** — no names, dates of birth, addresses, or account IDs
2. **No sensitive categories in specific form** — immigration, benefits, and disability are collapsed to binary flags that don't reveal the protected characteristic
3. **Geographic coarsening** — LAD level ensures minimum population of thousands per geographic bucket
4. **Legitimate interest basis** — improving a public service that helps families access childcare support
5. **Data minimisation** — only fields needed for policy/product analysis are captured
6. **No cross-session linking** — cookieless mode prevents longitudinal profiling

## Provider Search — Privacy Design

Provider search events share a PostHog session with form events. A single session may contain both `step_completed` events (with coarsened demographics: working status, partner, child count/band, benefits) and provider interaction events. The analysis below assumes worst-case: all events from one session are viewed together by an analyst.

### Why provider IDs are excluded

A provider ID combined with LAD (available from `provider_search` in the same session) directly identifies which provider the user is engaging with. For childminders serving 3–5 families, combining the provider's identity with coarsened demographics from form events could narrow to a single family. This defeats the geographic coarsening that LAD provides. Provider names are equally identifying.

### Why care types and distance are never combined on the same event

In sparse or rural LADs, "childminder within 1 mile" may match only 2–3 providers. Combined with LAD (available in the session via `provider_search`), this is functionally equivalent to emitting the provider ID. Therefore:

- **`provider_detail_viewed`** emits distance band only — "user viewed something <1mi away" is vague without knowing the provider type, matching many providers of all types at that distance.
- **`provider_shortlisted`** emits a care-type mask only — "user has childminders on their shortlist" matches dozens of providers per LAD without revealing which specific one(s) or how far away they are.
- Neither event combines these two properties. The exclusion table above (`Provider care types + distance combined`) encodes this rule.

### Why the shortlist care-type mask is safe

`shortlist_care_types` is a deduplicated set across _all_ currently-shortlisted providers, not tied to a single provider or a single action. "Someone in LAD X has at least one childminder shortlisted" describes potentially hundreds of families in that LAD. Even when only one provider is shortlisted, there are typically 50+ providers of any given care type per LAD, so the mask cannot identify which one.

### Why care_types on search/filter events is safe

On `provider_search` and `provider_filter_changed`, `care_types` represents a search preference ("I'm filtering for childminders"), not an engagement with a specific provider. Combined with LAD it means "someone in LAD X is looking for childminders" — an extremely common action that cannot narrow to an individual provider or family.

### Distance banding rationale

Five bands (`<1mi`, `1-3mi`, `3-5mi`, `5-10mi`, `10+mi`) ensure that within any single band in any LAD there are many providers. The bands are finer at short distances (where most childcare search activity occurs) to be analytically useful, while remaining too coarse to identify a specific provider without additional data (care type) that is deliberately withheld from the same event.
