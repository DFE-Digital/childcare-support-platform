## Overview

Tools for analysing data quality of childcare provider data exported from the pipeline. Validates individual fields and
cross-field rules against the regional beta dataset (Bristol, Bath and North East Somerset, South Gloucestershire).

### Scripts

- **`run_pipeline.py`** — runs the Dagster pipeline locally and copies the resulting parquet files into a new versioned
  `data/vN/` directory. Allows comparison against previous versions. Consider this a "snapshot" of the database at a
  point in time.
- **`analyse_parquet.py`** — loads provider, care type, and opening hours parquet files, merges them, and runs field and
  row validation. Can target a specific version or compare all versions side-by-side.

### Implementation

- **`data_types.py`** — dataclasses for `Provider`, `CareType`, and `OpeningHours`.
- **`validation.py`** — field validation (postcode format, lat/lng bounds, email, phone, Ofsted rating, opening times,
  age ranges, etc.) and cross-field checks (opening duration, breakfast/after-school club time windows, age range
  consistency, contact details present).

## Setup

From `packages/data-quality`:

```
uv sync
```

## Run pipeline and capture new version

Requires a running Dagster instance at `localhost:3000`.

```
uv run python run_pipeline.py
```

This runs the pipeline and copies the output into the next `data/vN/` directory, where N is the next available version.

## Run analysis

Compare all versions side-by-side:

```
uv run python analyse_parquet.py
```

Analyse a specific version:

```
uv run python analyse_parquet.py v0
```

## Data versions and performance

CM = Childminder

### By Version

| Version | Notes                                       | Services | Coverage (%) | Non-CM Val (%) | CM Val (%) | Score |
| ------- | ------------------------------------------- | -------- | ------------ | -------------- | ---------- | ----- |
| v1      | Updated data sources (March 26)             | 1,282    | 73.4         | 90.4           | 79.5       | 81.1  |
| v2      | Initial custom Bath and NE Somerset scraper | 1,406    | 72.6         | 91.3           | 81.0       | 81.6  |
| v3      | Bath and NE Somerset websites and times     | 1,406    | 73.4         | 91.4           | 81.3       | 82.0  |
| v4      | Inclusion of CM from only LA scraping       | 1,414    | 73.3         | 91.4           | 81.6       | 82.1  |
| v5      | New data source: Ofsted consented addresses | 1,414    | 73.3         | 91.4           | 81.6       | 82.1  |
| v6      | Improved Bristol LA scraping                | 1,423    | 74.3         | 91.7           | 84.2       | 83.4  |
| v7      | Added custom South Gloucestershire scraper  | 1,435    | 74.7         | 92.0           | 82.0       | 82.9  |
| v8      | More efficient Bath NES scrape              | 1,427    | 74.7         | 91.9           | 82.2       | 83.0  |
| v9      | Separate website and FIS URL                | 1,425    | 74.7         | 92.5           | 84.3       | 83.8  |
| v10     | Edge cases in geocoding, hours, care types  | 1,416    | 70.8         | 94.2           | 94.7       | 86.6  |
| v11     | Edge cases in address parsing and age range | 1,418    | 71.9         | 95.4           | 94.9       | 87.4  |
| v12     | Remove school providers with no care types  | 1,418    | 69.7         | 95.2           | 95.3       | 86.7  |
| v13     | Ofsted register info for cm age rules       | 1,418    | 74.1         | 94.6           | 99.0       | 89.2  |
| v14     | Provider/care type enrichment fixes         | 1,418    | 69.5         | 96.1           | 99.1       | 88.2  |
| v15     | Tighten validation; default weeks           | 1,418    | 70.8         | 98.4           | 99.6       | 89.6  |
| v16     | Baseline from v15-ch-2 parquet restore      | 1,406    | 69.1         | 98.2           | 99.8       | 89.0  |
| v17     | Bristol Council enrichment + contact filter | 1,416    | 70.9         | 98.4           | 99.6       | 89.6  |
| v18     | Bristol Council enrichment; bugfix          | 1,415    | 70.9         | 98.4           | 99.6       | 89.6  |
| v19     | Load full consented addresses for CM        | 1,388    | 71.3         | 98.3           | 99.6       | 89.7  |

### By Region (v19)

| Region                       | Services | Coverage (%) | Non-CM Val (%) | CM Val (%) | Score |
| ---------------------------- | -------- | ------------ | -------------- | ---------- | ----- |
| Bath and North East Somerset | 375      | 72.0         | 99.0           | 99.6       | 90.2  |
| South Gloucestershire        | 374      | 70.4         | 98.7           | 99.9       | 89.7  |
| Bristol                      | 639      | 71.6         | 97.4           | 99.4       | 89.5  |

## Validation rules

### Providers

- Name must be present and at least 2 characters long (not required for childminders, whose names are redacted)
- Local authority district code must be present and in the correct format
- Address (line 1, line 2, city, postcode) must be present and valid (not required for childminders, whose addresses are
  redacted)
- City field must not contain digits (indicates address bleed from address line 1)
- Latitude and longitude must be present (not required for childminders)
- Latitude and longitude must be within the beta region bounds (51–52°N, 3–2°W) for providers in the three beta LAs
- Lat/lng must be unique across all providers
- Phone number, if provided, must be in a valid UK format
- Email address, if provided, must be in a valid format
- Website, if provided, must be a valid URL
- FIS (Family Information Service) URL, if provided, must be a valid URL
- Ofsted rating must be present and one of: Outstanding, Good, Requires Improvement, Inadequate
- Ofsted inspection date must be present, not in the future, and no more than 7 years ago
- Ofsted inspection framework must be present and one of: legacy, legacy_transition, report_card
- Safeguarding outcome must be recorded for providers inspected under the report card or legacy transition frameworks
- Number of registered places must be present and between 1 and 500; childminders must have no more than 6
- Non-childminder providers must have both address line 1 and postcode
- Non-childminder providers must have at least one contact detail (phone, email, or website)
- Phone number must be unique across all providers
- Email address must be unique across all providers
- Website must be unique across all providers
- FIS URL must be unique across all providers
- Institution type must be consistent with care types (childminder institutions must only have childminder care types,
  and non-childminder institutions must not have childminder care types)
- Must have at least one care type
- Cannot have duplicate care types
- Website and FIS URL must not be the same

### Care types

- Care type must be one of: private nursery, school-based nursery, childminder, breakfast club, free breakfast club,
  after-school club, or holiday club
- Number of operating weeks per year must be present and between 1 and 52
  - Holiday clubs must operate no more than 17 weeks per year
  - School-based nurseries, breakfast clubs, and after-school clubs must operate no more than 40 weeks per year
- Minimum eligible age (years), maximum eligible age (years), and minimum eligible age (months) must all be present
- Must have at least one opening hours slot
- Minimum eligible age must be less than maximum eligible age
- Breakfast clubs, after-school clubs, and holiday clubs must accept children aged 4 or older
- School-based nurseries must accept children aged 2 or older
- Private nurseries and school-based nurseries must not accept children older than 5
- Childminders must not accept children younger than 9 months or older than 14
- Breakfast club opening times must be between 06:00–08:30, closing times between 08:00–10:00
- After-school club opening times must be between 14:00–17:00, closing times between 15:00–19:00
- Holiday club opening times must be between 07:00–10:00, closing times between 14:00–19:00

### Opening hours

- Opening time must be present, valid, and between 05:30 and 17:30
- Closing time must be present, valid, and between 07:30 and 19:00
- Session must last at least 1 hour and no more than 12 hours
- At least one day of the week must be selected
