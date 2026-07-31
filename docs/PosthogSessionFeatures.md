# PostHog Session Features Dataset

## Overview

`exported_data/posthog_sessions.parquet` contains one row per browsing session with ~80 aggregated feature columns. It is produced by the `posthog_sessions` Dagster asset from raw events in `posthog.events`.

**Privacy:** The session ID is used only for grouping during aggregation and is excluded from the output. The date column is date-only (no time). Geographic granularity is LAD-level. No provider IDs, child names, postcodes, or other PII are present.

**Regeneration:** `make data/posthog-sync` (pulls latest events then regenerates the Parquet).

---

## Column Reference

### Session metadata

| Column                 | Type   | Description                                                              |
| ---------------------- | ------ | ------------------------------------------------------------------------ |
| `session_date`         | date   | Date of the session's first event                                        |
| `session_duration_s`   | float  | Seconds between first and last event in session                          |
| `event_count_form`     | int    | Total events on /support or /costs pages                                 |
| `event_count_provider` | int    | Total events on /providers page                                          |
| `event_count_other`    | int    | Events on all other pages (home, landing)                                |
| `device_type`          | string | "Mobile", "Desktop", or "Tablet" (constant per session)                  |
| `referrer_domain`      | string | Domain that referred the user (e.g. "beststartinlife.gov.uk", "$direct") |

**Frontend source:** PostHog SDK attaches `$device_type`, `$referring_domain`, and `$pathname` to every event automatically.

---

### Form steps

| Column                         | Type        | Description                                                       |
| ------------------------------ | ----------- | ----------------------------------------------------------------- |
| `steps_completed_support`      | int         | Number of form steps completed on the support (entitlements) form |
| `steps_completed_costs`        | int         | Number of form steps completed on the costs form                  |
| `distinct_steps_support`       | int         | Number of distinct step types completed for support               |
| `distinct_steps_costs`         | int         | Number of distinct step types completed for costs                 |
| `furthest_step_support`        | string/null | Deepest step reached in the support form                          |
| `furthest_step_costs`          | string/null | Deepest step reached in the costs form                            |
| `reached_entitlements_results` | int         | Number of times user reaches the entitlements results page        |
| `reached_costs_results`        | int         | Number of times user reaches the costs results page               |

**Frontend source:** Each form step completion fires `step_completed` with `form` ("support"/"costs") and `step` (the step name). Reaching the results page fires `schemes_eligible`.

**Step ordering:** postcode → partner → immigration → working → benefits → children → childcare

**Why counts > 1:** Users can go back and redo steps, or complete the form multiple times in one session (e.g. trying different scenarios).

---

### Geography

| Column              | Type        | Description                                                     |
| ------------------- | ----------- | --------------------------------------------------------------- |
| `lad_codes`         | string      | JSON array of all distinct LAD codes entered across the session |
| `lad_mode`          | string/null | Most frequently occurring LAD code                              |
| `lad_count`         | int         | Number of distinct LAD codes                                    |
| `iod_decile_min`    | int/null    | Lowest IoD decile seen (1 = most deprived)                      |
| `iod_decile_max`    | int/null    | Highest IoD decile seen (10 = least deprived)                   |
| `iod_decile_mean`   | float/null  | Mean across all events carrying IoD                             |
| `iod_decile_median` | float/null  | Median                                                          |
| `iod_deciles`       | string      | JSON array of all distinct decile values                        |

**Frontend source:** When the user enters a postcode, the app looks up the LAD code and IoD decile from local JSON data files. These are emitted on the `step_completed` (postcode step) and `provider_search` events as `lad25cd` and `iod_decile`.

**IoD (Index of Deprivation):** England-only, 2025 release. Decile 1 = most deprived 10% of LSOAs, decile 10 = least deprived. Null for Scottish/Welsh/NI postcodes.

---

### Demographics

Each binary demographic field produces three columns using the **true/false/pct** pattern:

| Suffix   | Meaning                                                    |
| -------- | ---------------------------------------------------------- |
| `_true`  | Number of step events where the field was true             |
| `_false` | Number of step events where the field was false            |
| `_pct`   | Proportion true: `true / (true + false)`. Null if no data. |

| Field prefix        | Source step | What it captures                                                            |
| ------------------- | ----------- | --------------------------------------------------------------------------- |
| `has_partner`       | partner     | Whether user lives with a partner                                           |
| `settled_in_uk`     | immigration | Whether user has settled status (british/irish/settled vs pre-settled/NRPF) |
| `working`           | working     | Whether either parent is in employment                                      |
| `is_studying`       | working     | Whether user is currently studying                                          |
| `receives_benefits` | benefits    | Whether user receives any qualifying benefit                                |

**Frontend source:** Each fires on `step_completed` as a boolean property. The raw immigration/benefit categories are coarsened to binary for privacy.

**Why counts > 1:** Users redo steps or complete both forms, so a session may have e.g. `has_partner_true=2, has_partner_false=1` if they tried "yes" twice and "no" once.

---

### Child data

| Column                 | Type | Description                                          |
| ---------------------- | ---- | ---------------------------------------------------- |
| `child_count_1`        | int  | Children step events reporting 1 child               |
| `child_count_2`        | int  | Children step events reporting 2 children            |
| `child_count_3plus`    | int  | Children step events reporting 3+ children           |
| `youngest_band_0_4`    | int  | Children step events where youngest child is under 5 |
| `youngest_band_5_plus` | int  | Children step events where youngest child is 5+      |

**Frontend source:** `child_count` is emitted on `step_completed` (children step), capped at 3 (meaning 3 or more). `youngest_band` is computed from birth month/year as "0-4" (under 60 months) or "5+" (60+ months).

---

### Care types sought

| Column                             | Type | Description                                           |
| ---------------------------------- | ---- | ----------------------------------------------------- |
| `care_sought_childminder`          | int  | Childcare step events where user selected childminder |
| `care_sought_private_nursery`      | int  | Selected private nursery                              |
| `care_sought_school_based_nursery` | int  | Selected school-based nursery                         |

**Frontend source:** Emitted on `step_completed` (childcare step) as `care_types_sought` array. The form UI currently only offers these 3 care types as options.

---

### Schemes eligible

| Column                   | Type | Description                                       |
| ------------------------ | ---- | ------------------------------------------------- |
| `scheme_15h_2yr`         | int  | Results events including 15 hours for 2-year-olds |
| `scheme_15h_universal`   | int  | 15 hours universal entitlement                    |
| `scheme_30h_working`     | int  | 30 hours for working families                     |
| `scheme_childcare_grant` | int  | Childcare Grant (students)                        |
| `scheme_free_breakfast`  | int  | Free breakfast clubs                              |
| `scheme_haf`             | int  | Holiday Activities and Food programme             |
| `scheme_learner_support` | int  | Learner support                                   |
| `scheme_tfc`             | int  | Tax-Free Childcare                                |
| `scheme_uc_childcare`    | int  | Universal Credit childcare element                |
| `scheme_wraparound`      | int  | Wraparound childcare                              |

**Frontend source:** Emitted on `schemes_eligible` as `schemes` array. The eligibility calculator determines which schemes the user qualifies for based on their form answers. Each column counts how many results-page visits included that scheme.

---

### Provider search

| Column                       | Type       | Description                                             |
| ---------------------------- | ---------- | ------------------------------------------------------- |
| `provider_searches`          | int        | Number of postcode searches on the provider page        |
| `provider_search_lads`       | string     | JSON array of LADs searched (from provider search only) |
| `provider_search_iod_min`    | int/null   | Min IoD from provider searches                          |
| `provider_search_iod_max`    | int/null   | Max                                                     |
| `provider_search_iod_mean`   | float/null | Mean                                                    |
| `provider_search_iod_median` | float/null | Median                                                  |

**Frontend source:** `provider_search` event fires when user submits a postcode on the provider search page. Carries `lad25cd` and `iod_decile` from the searched postcode.

---

### Provider filters

| Column                                      | Type | Description                                    |
| ------------------------------------------- | ---- | ---------------------------------------------- |
| `provider_filters_changed`                  | int  | Total filter/sort change events                |
| `provider_filter_care_childminder`          | int  | Filter events including childminder            |
| `provider_filter_care_private_nursery`      | int  | Including private nursery                      |
| `provider_filter_care_school_based_nursery` | int  | Including school-based nursery                 |
| `provider_filter_care_after_school_club`    | int  | Including after school club                    |
| `provider_filter_care_breakfast_club`       | int  | Including breakfast club                       |
| `provider_filter_care_holiday_club`         | int  | Including holiday club                         |
| `provider_filter_funded_hours_true`         | int  | Filter events with funded-hours-only enabled   |
| `provider_filter_funded_hours_false`        | int  | With funded-hours-only disabled                |
| `provider_sort_distance`                    | int  | Filter events using distance sort              |
| `provider_sort_best_ofsted`                 | int  | Using Ofsted rating sort                       |
| `provider_child_band_0_4`                   | int  | Filter events with under-5 child filter active |
| `provider_child_band_5_plus`                | int  | With 5+ child filter active                    |

**Frontend source:** `provider_filter_changed` fires on every filter/sort change with a full state snapshot: `care_types` (array), `funded_hours_only` (bool), `sort_by` (string), `child_age_bands` (array).

---

### Provider detail views

| Column                              | Type | Description                               |
| ----------------------------------- | ---- | ----------------------------------------- |
| `provider_details_viewed`           | int  | Total provider detail modals opened       |
| `provider_detail_dist_band_lt1`     | int  | Details viewed for providers <1 mile away |
| `provider_detail_dist_band_1_3`     | int  | 1–3 miles                                 |
| `provider_detail_dist_band_3_5`     | int  | 3–5 miles                                 |
| `provider_detail_dist_band_5_10`    | int  | 5–10 miles                                |
| `provider_detail_dist_band_10_plus` | int  | 10+ miles                                 |
| `provider_detail_dist_band_unknown` | int  | Distance unknown                          |

**Frontend source:** `provider_detail_viewed` fires when user opens a provider modal. Carries `distance_band` only (no care types — see privacy design in Posthog.md).

---

### Provider shortlisting

| Column                                    | Type | Description                                      |
| ----------------------------------------- | ---- | ------------------------------------------------ |
| `provider_shortlist_interactions`         | int  | Total shortlist add/remove actions               |
| `provider_shortlist_childminder`          | int  | Shortlist events where mask included childminder |
| `provider_shortlist_private_nursery`      | int  | Included private nursery                         |
| `provider_shortlist_school_based_nursery` | int  | Included school-based nursery                    |
| `provider_shortlist_after_school_club`    | int  | Included after school club                       |
| `provider_shortlist_breakfast_club`       | int  | Included breakfast club                          |
| `provider_shortlist_holiday_club`         | int  | Included holiday club                            |

**Frontend source:** `provider_shortlisted` fires on each add/remove. Carries `shortlist_care_types` — a deduplicated set of care types across ALL currently-shortlisted providers (not just the one toggled).

---

### Provider map interaction

| Column                      | Type     | Description                                |
| --------------------------- | -------- | ------------------------------------------ |
| `provider_zoom_ins`         | int      | Zoom-in events (debounced, 5s settle time) |
| `provider_zoom_outs`        | int      | Zoom-out events                            |
| `provider_zoom_keyboard`    | int      | Zoom events triggered by keyboard (+/-)    |
| `provider_zoom_button`      | int      | Zoom events triggered by UI buttons        |
| `provider_zoom_to_la`       | int      | "Show me" LA boundary zoom clicks          |
| `provider_show_more_clicks` | int      | "Show more" pagination clicks              |
| `provider_max_page`         | int/null | Highest page number reached                |

**Frontend source:** Zoom events are debounced (only emitted after 5 seconds at a stable zoom level). `provider_show_more` fires each time the user loads the next 20 results. `provider_zoom_to_la` fires when they click to see all providers in the LA.

---

### Page navigation

| Column              | Type | Description                          |
| ------------------- | ---- | ------------------------------------ |
| `pages_distinct`    | int  | Number of distinct URL paths visited |
| `pageviews_total`   | int  | Total page view events               |
| `visited_support`   | bool | Visited any /support page            |
| `visited_costs`     | bool | Visited any /costs page              |
| `visited_providers` | bool | Visited any /providers page          |
| `visited_home`      | bool | Visited the homepage (/)             |

**Frontend source:** PostHog SDK fires `$pageview` with `$pathname` on each navigation.
