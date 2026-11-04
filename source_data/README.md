# Source Data Files

Reference data files used by Dagster pipeline jobs. These are mounted into the
dagster-user-code container at `/opt/dagster/app/source_data/` via docker-compose.

All files must be downloaded manually — none are checked into version control.
They are stored in S3 and synced locally via Make commands.

## Workflows

### Accessing data

```
make data/fetch-source
```

Syncs all source files from S3 into `source_data/`. Run this to get up-to-date source data before running the pipeline.

### Updating data

1. Download the new or updated source file(s) into `source_data/`
2. Update this README to reflect any filename or schema changes
3. Upload to Azure
    1. Go to the Azure Portal
    2. Find the `storage` resource group for the environment you want to update
    3. Go to the storage account within there
    4. Upload the source_data/ folder contents into the `clean-data` container

## Files

### family_information_services.csv

|                 |                                                                              |
| --------------- | ---------------------------------------------------------------------------- |
| **Used by**     | `family_information_services` asset                                          |
| **Dagster job** | `load_source_data` (`make data/load-sources`)                                |
| **Loads into**  | `la.family_information_services`                                             |
| **Source**      | Maintained manually — this CSV is the single source of truth for LA FIS URLs |

Columns: `LAD25CD`, `LAD25NM`, `fis_url`, `childcare_types`, `notes`.

### spc_school_level_underlying_data_2025.csv

|                 |                                                                                                                                                                                       |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Used by**     | `school_census` asset                                                                                                                                                                 |
| **Dagster job** | `load_source_data` (`make data/load-sources`)                                                                                                                                         |
| **Loads into**  | `dfe.school_census`                                                                                                                                                                   |
| **Source**      | [School Pupils and their Characteristics — Explore Education Statistics](https://explore-education-statistics.service.gov.uk/find-statistics/school-pupils-and-their-characteristics) |
| **URL**         | https://content.explore-education-statistics.service.gov.uk/api/releases/63491b17-2037-4533-b719-d3656aaf6ed5/files/3dc88c32-da52-4aff-b6d0-0126de016844
| **Encoding**    | `cp1252`                                                                                                                                                                              |

Download the "School level underlying data" CSV from the latest release. All
columns are loaded as TEXT (verbose DfE headers are snake_cased automatically).

### gias_establishments.csv

|                 |                                                                                                       |
| --------------- | ----------------------------------------------------------------------------------------------------- |
| **Used by**     | `gias_schools` asset                                                                                  |
| **Dagster job** | `load_source_data` (`make data/load-sources`)                                                         |
| **Loads into**  | `dfe.gias_schools`                                                                                    |
| **Source**      | [Get Information About Schools — Downloads](https://get-information-schools.service.gov.uk/Downloads) |
| **Encoding**    | `utf-8-sig` (falls back to `cp1252`)                                                                  |

Download the **Establishment fields** CSV and rename to `gias_establishments.csv`.
May download as a zip containing a single file.
The original file has 120+ columns; only a whitelist of 13 columns is loaded
(URN, name, address, postcode, easting/northing, type, phase, status).

### Free_breakfast_clubs_-_schools_on_the_scheme_020226.xlsx

|                 |                                                                                                                                                         |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Used by**     | `free_breakfast_club_schools` asset                                                                                                                     |
| **Dagster job** | `load_source_data` (`make data/load-sources`)                                                                                                           |
| **Loads into**  | `dfe.free_breakfast_club_schools`                                                                                                                       |
| **Source**      | [DfE — Free breakfast clubs: schools on the programme](https://www.gov.uk/government/publications/breakfast-clubs-early-adopters-schools-in-the-scheme) |

Download the Excel spreadsheet listing all schools on the free breakfast club
scheme. The filename encodes the publication date (`020226` = 02/02/2026).
Columns loaded: `urn`, `school_name`, `type` (Mainstream / Special_AP),
`establishment_type_group`, `gor_name` (Government Office Region), `la_name`.

The `urn` column matches URNs in `dfe.gias_schools` and `dfe.school_census`.

### Management_information_-_state-funded_schools_-_latest_inspections_as_at_28_Feb_2026.csv

|                 |                                                                                                                                                                                                  |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Used by**     | `ofsted_school_inspections` asset                                                                                                                                                                |
| **Dagster job** | `load_source_data` (`make data/load-sources`)                                                                                                                                                    |
| **Loads into**  | `ofsted.school_inspections`                                                                                                                                                                      |
| **Source**      | [Ofsted — State-funded school inspections and outcomes](https://www.gov.uk/government/statistical-data-sets/monthly-management-information-ofsteds-school-inspections-outcomes) |
| **Encoding**    | `cp1252`                                                                                                                                                                                         |

Download the "Management information - state-funded schools - latest inspections" CSV from the MI page.
The filename encodes the reporting date. Contains both legacy OEIF grades (1-4) and new report-card
named grades (Exceptional / Strong standard / Expected standard / Needs
attention / Urgent improvement). A whitelist of columns is loaded — school URN,
report-card grades, and OEIF overall effectiveness / sub-judgements.

### Consented_addresses_for_childminders_and_domestic_childcare_as_at_31_March_2026.csv

|                 |                                                                                                                                                                                       |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Used by**     | `ofsted_consented_addresses` asset                                                                                                                                                    |
| **Dagster job** | `load_source_data` (`make data/load-sources`)                                                                                                                                         |
| **Loads into**  | `ofsted.consented_addresses`                                                                                                                                                          |
| **Source**      | [Ofsted — Consented addresses for childminders and domestic childcare](https://www.gov.uk/government/publications/consented-addresses-for-childminders-and-domestic-childcare)        |
| **Encoding**    | `latin-1`                                                                                                                                                                             |

Consented home addresses for ~7,500 childminders and domestic childcare providers
who have agreed to have their address published. Used as a fallback address source
for providers whose address fields are REDACTED in `ofsted.inspections`.

The first 3 rows are metadata; column headers are on row 4. Columns loaded:
`provider_urn` (EY... format, joins to `ofsted.inspections`), `provider_type`,
`register_combo`, `eyr_flag`, `ccr_flag`, `vcr_flag`, `provider_name`,
`address_line_1`–`address_line_3`, `town`, `postcode`,
`parliamentary_constituency`, `local_authority`, `region`, `ofsted_region`.

### Management*information*-\_childcare_providers_and_inspections_as_at_31_December_2025.ods

|                 |                                                                                                                                                                                       |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Used by**     | `ofsted_inspections` asset                                                                                                                                                            |
| **Dagster job** | `load_source_data` (`make data/load-sources`)                                                                                                                                         |
| **Loads into**  | `ofsted.inspections`                                                                                                                                                                  |
| **Source**      | [Ofsted — Childcare providers and inspections management information](https://www.gov.uk/government/statistical-data-sets/childcare-providers-and-inspections-management-information) |

Download the ODS spreadsheet "Management information - childcare providers and inspections".
The asset reads sheet `D1_Most_recent_inspections` and streams rows into Postgres.

### ONSPD_FEB_2026_UK.csv

|                 |                                                                                                               |
| --------------- | ------------------------------------------------------------------------------------------------------------- |
| **Used by**     | `postcode_lookup` asset                                                                                       |
| **Dagster job** | `load_source_data` (`make data/load-sources`)                                                                 |
| **Outputs**     | `data/postcode_lad_lookup.csv.gz`                                                                             |
| **Source**      | [ONS Postcode Directory](https://geoportal.statistics.gov.uk/datasets/3080229224424c9cb53c0b48f5a64d27/about) |

Download the full ONSPD zip, extract, and place the `ONSPD_MMM_YYYY_UK.csv` file directly in `source_data/` renamed to
match the current filename (e.g. `ONSPD_FEB_2026_UK.csv`). Update the hardcoded path in
`bsil_pipeline/assets/postcode_lookup.py` when upgrading to a newer release.
Columns used: `pcds`, `doterm`, `lad25cd`, `lat`, `long`. Terminated postcodes are filtered out.

### codepoint-poly/ (directory)

|                 |                                                                                                   |
| --------------- | ------------------------------------------------------------------------------------------------- |
| **Used by**     | `bbox_lookup` asset                                                                               |
| **Dagster job** | `load_source_data` (`make data/load-sources`)                                                     |
| **Outputs**     | `data/bbox_lookup.sqlite` (postcode + district bounding boxes)                                    |
| **Source**      | [OS OpenData — CodePoint with Polygons](https://osdatahub.os.uk/downloads/open/CodePointPolygons) |

Requires sign up?
Download and extract the CodePoint with Polygons zip. Contains 120 zipped
shapefiles with per-postcode polygons. Coordinates are converted from
EPSG:27700 (British National Grid) to EPSG:4326 (WGS84).

### Local_Authority_Districts_DEC_2025_Boundaries_UK_BFC_*.geojson

|                 |                                                                                                                                      |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| **Used by**     | `la_boundaries` asset                                                                                                                |
| **Dagster job** | `load_source_data` (`make data/load-sources`)                                                                                        |
| **Outputs**     | `output/la_boundaries.geojson` (simplified LA boundaries for frontend map)                                                           |
| **Source**      | [ONS Open Geography Portal — LAD Boundaries UK BFC](https://geoportal.statistics.gov.uk/datasets/local-authority-districts-december-2025-boundaries-uk-bfc) |

Download the GeoJSON version of "Local Authority Districts (December 2025) Boundaries UK BFC"
(Full Clipped to Mean High Water). Place the file in `source_data/` — the asset globs for
`Local_Authority_Districts*BFC*.geojson`. The file is ~267 MB (full detail); the asset
simplifies to ~2 MB for the frontend.

Already in WGS84 (EPSG:4326). Properties used: `LAD25CD`, `LAD25NM`.

### File_1_IoD2025_Index_of_Multiple_Deprivation.xlsx

|                 |                                                                                                                                                                  |
| --------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Used by**     | `iod_2025` asset                                                                                                                                                 |
| **Dagster job** | `load_source_data` (`make data/load-sources`)                                                                                                                    |
| **Loads into**  | `mhclg.iod_2025`                                                                                                                                                 |
| **Source**      | [MHCLG — English Indices of Deprivation 2025](https://www.gov.uk/government/statistics/english-indices-of-deprivation-2025)                                      |

Download "File 1" (Index of Multiple Deprivation) XLSX from the IoD 2025 release.
The asset reads sheet `IMD25` (33,755 rows — one per LSOA in England).
Columns loaded: `LSOA code (2021)`, `LSOA name (2021)`,
`Local Authority District code (2024)`, `Local Authority District name (2024)`,
`Index of Multiple Deprivation (IMD) Rank`, `Index of Multiple Deprivation (IMD) Decile`.

### tiney-childminder-feed.csv

|                 |                                                    |
| --------------- | -------------------------------------------------- |
| **Used by**     | `tiney_childminders` asset                         |
| **Dagster job** | `load_source_data` (`make data/load-sources`)      |
| **Loads into**  | `tiney.childminders`                               |
| **Source**      | Provided directly by Tiney (childminder agency)    |

CSV feed of Tiney CMA-registered childminders. Contains provider details,
contact info, fee rates, opening hours, and CMA quality assurance gradings.
All rows are loaded (including `tiney_lifecycle_status = 'new'`); filtering
to `open` providers happens downstream in the `care_offerings` asset.

Columns: `ofsted_urn` (TY-prefixed, e.g. `TY0224005`), `provider_name`,
`address_line_1`, `address_city`, `postcode`, `uk_region`,
`local_authority_name`, `website_url`, `ofsted_register_combination`,
`tiney_registration_type`, `tiney_registration_date`, `age_range`,
`last_inspection_date`, `last_inspection_type`, `cma_qa_grading`,
`registered_places`, `operating_weeks_per_year`, `minimum_commitment`,
`opening_hours`, `placement_type`, `funded_hours_accepted`,
`hourly_rate_gbp`, `daily_rate_gbp`, `additional_charges`,
`tiney_lifecycle_status`.

### boundary-line/ (directory)

|                 |                                                                                    |
| --------------- | ---------------------------------------------------------------------------------- |
| **Used by**     | `bbox_lookup` asset                                                                |
| **Dagster job** | `load_source_data` (`make data/load-sources`)                                      |
| **Outputs**     | `data/bbox_lookup.sqlite` (LA + county bounding boxes)                             |
| **Source**      | [OS OpenData — Boundary-Line](https://osdatahub.os.uk/downloads/open/BoundaryLine) |

Download and extract the Boundary-Line GeoPackage. The `bbox_lookup` asset reads
district/unitary authority and county layers for bounding boxes.
Searches recursively for any .gpkg file, so place `bdline_gb.gpkg`
from the download in `source_data/boundary-line/`.
Coordinates are converted from EPSG:27700 to EPSG:4326.

Note: `la_boundaries` no longer uses this file — it reads the ONS BFC GeoJSON above instead.

---

## Manually converted values

Some source files contain LA codes that have been manually updated to match the
LAD 2025 code scheme. If these files are re-downloaded from their upstream
sources, the old codes will return and must be converted again.

| Old code (LAD23) | New code (LAD25) | LA name | Files affected |
|------------------|------------------|---------|----------------|
| E08000016 | E08000038 | Barnsley | `family_information_services.csv`, `estimates_by_la_age_by_provtype.csv` |
| E08000019 | E08000039 | Sheffield | `family_information_services.csv`, `estimates_by_la_age_by_provtype.csv` |

**Reason**: The 2023→2025 ONS LAD reorganisation renumbered these two authorities.
The pipeline uses LAD25 codes throughout; ONSPD (Feb 2026) already uses `lad25cd`.