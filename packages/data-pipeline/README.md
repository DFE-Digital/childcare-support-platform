# bsil-pipeline

Dagster data pipeline for ingesting, processing, and exporting childcare provider data.

## Stack

Python 3.11+, Dagster, psycopg3, BeautifulSoup, PyArrow, Shapely

## Running

`make data/up` starts Postgres + Dagster + Prisma migrations inside Docker Compose. `make data/dagster` opens the Dagster UI at `:3000`. All `make data/*` targets execute Dagster jobs inside the `dagster-user-code` container.

## Testing

```bash
make data/test   # pytest + Zod schema validation against a bsil_test database
```

## Dagster jobs and Make targets

The pipeline processes data through a sequence of stages. Each Dagster job groups related assets and is triggered by a corresponding Make target.

### Full pipeline (automated)

```bash
make data/complete METADATA=true   # Single command — loads sources, then daemon cascades everything else
```

`METADATA=true` includes debug metadata in the export (use `METADATA=false` for production).

This triggers `load_source_data` with the `CASCADE=true` tag. The Dagster daemon then cascades all downstream assets automatically via declarative automation: scrape → extract → geocode → draft → publish → export. The `BETA` flag (which restricts to beta LAs) is controlled by the `pipeline_automation` sensor definition in `definitions.py` — to switch to full-England, change `"BETA": "true"` to `"BETA": "false"` in the sensor's `run_tags` and redeploy.

Monitor progress at http://localhost:3000. When complete: `make app/up`.

### Individual stage targets

These run individual stages without triggering the cascade (no `CASCADE` tag). Useful for re-running a single step or debugging.

| Make target                          | Dagster job             | What it does                                                                                                                                                                                       |
| ------------------------------------ | ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `make data/load-sources`             | `load_source_data`      | Creates schema tables + ingests Ofsted inspections, school inspections, GIAS schools, school census, FBC schools, FIS CSV, OS bounding boxes, postcode lookup, LA boundaries                       |
| `make data/scrape-ofsted BETA=true`  | `scrape_ofsted_reports` | Scrapes Ofsted report pages for additional provider details. `BETA=true` for beta LAs only                                                                                                         |
| `make data/scrape-la BETA=true`      | `scrape_la_providers`   | Scrapes Local Authority FIS directories (~20 scrapers). `BETA=true` for beta LAs only, `BETA=false` for all. Single-platform partition: `make data/scrape-la BETA=true partition=bath_ne_somerset` |
| `make data/extract-la BETA=true`     | `extract_la_providers`  | Extracts structured fields from scraped LA HTML/JSON. `BETA` is required. Supports partitioning like scrape-la                                                                                     |
| `make data/geocode-ofsted BETA=true` | `geocode_ofsted_places` | Geocodes Ofsted provider addresses via OS Places API. `BETA=true` for beta LAs only                                                                                                                |
| `make data/geocode-la`               | `geocode_la_places`     | Geocodes LA-scraped provider addresses via OS Places API                                                                                                                                           |
| `make data/draft`                    | `build_draft`           | Builds draft provider records: linkage, care offerings, providers, provider details, care types, fee rates                                                                                         |
| `make data/draft-fixtures`           | `draft_provider_data`   | Loads placeholder fixture data into draft schema                                                                                                                                                   |
| `make data/publish BETA=true`        | `publish_data`          | Copies draft to published schema, runs Zod validation, generates spatial index parquet. `BETA` is required                                                                                         |
| `make data/clean`                    | `clean_data`            | Drops and recreates draft/source schemas (destructive)                                                                                                                                             |
| `make data/export-app BETA=true`     | `export_app_data`       | Exports published data to JSON + spatial index + postcode autocomplete + vector tiles. `BETA` is required                                                                                          |
| `make data/export-parquet`           | `export_parquet_data`   | Exports all source/draft/published tables to parquet for backup                                                                                                                                    |
| `make data/restore-parquet`          | `restore_parquet_data`  | Restores tables from parquet backups + recreates schema tables                                                                                                                                     |

### Manual pipeline sequence (equivalent to `data/complete`)

```
make data/load-sources                # 1. Ingest source data
make data/scrape-ofsted BETA=true     # 2. Scrape Ofsted reports
make data/scrape-la BETA=true         # 3. Scrape LA directories
make data/extract-la BETA=true        # 4. Extract structured fields
make data/geocode-ofsted BETA=true    # 5. Geocode addresses
make data/geocode-la
make data/draft                       # 6. Build draft providers
make data/publish BETA=true           # 7. Publish + validate + spatial index
make data/export-app BETA=true METADATA=false  # 8. Export for the frontend
make data/push-exported env=prod      # 9. Upload to source-data bucket
```

### Other Make targets

| Target                              | Description                                                              |
| ----------------------------------- | ------------------------------------------------------------------------ |
| `make data/up`                      | Start all pipeline services (Postgres, Dagster, Prisma) + run tests      |
| `make data/down`                    | Stop pipeline services                                                   |
| `make data/rebuild`                 | Force-recreate all containers                                            |
| `make data/wipe`                    | Tear down everything including volumes (destructive)                     |
| `make data/psql`                    | Open psql shell to local Postgres                                        |
| `make data/dagster`                 | Open Dagster UI in browser                                               |
| `make data/migrate`                 | Run Prisma migrations                                                    |
| `make data/prisma`                  | Diff schema, generate migration, regenerate Prisma client + Zod schemas  |
| `make data/jupyter`                 | Start Jupyter Lab                                                        |
| `make data/push-exported env=<env>` | Upload exported data to source-data bucket (deploy action syncs to live) |
| `make data/push-source`             | Upload `source_data/` to `ten-ds-raw-data` S3 bucket                     |
| `make data/fetch-source`            | Download `source_data/` from `ten-ds-raw-data` S3 bucket                 |
| `make data/test`                    | Run pytest + Zod validation (creates `bsil_test` DB if needed)           |

## `source_data/` (input)

Reference data files mounted into the dagster-user-code container. All files are downloaded manually — none are in version control. See [`source_data/README.md`](../../source_data/README.md) for download instructions and file details.

Key files: Ofsted inspections (ODS), Ofsted school inspections (CSV), GIAS establishments (CSV), school census (CSV), free breakfast club schools (XLSX), family information services CSV, ONS Postcode Directory, OS CodePoint with Polygons, OS Boundary-Line.

## `exported_data/` (output)

Generated by the export jobs. Not checked into git — fetched from S3 for production builds (`make fetch-data`).

| Path                          | Generated by          | Consumed by                | Description                                    |
| ----------------------------- | --------------------- | -------------------------- | ---------------------------------------------- |
| `app/providers/*.json`        | `export_app_data`     | Frontend (static fetch)    | One JSON file per published provider           |
| `app/inward/*.json`           | `export_app_data`     | Frontend (postcode lookup) | Postcode inward-code to provider mapping       |
| `app/outward.json`            | `export_app_data`     | Frontend (autocomplete)    | List of valid outward postcode codes           |
| `app/spatial_index.parquet`   | `publish_data`        | SIS preprocessing          | Provider coordinates + sort columns for R-tree |
| `app/spatial_index.sis`       | SIS preprocess step   | SIS query server           | Compiled spatial index (rkyv serialized)       |
| `app/sis_schema.json`         | SIS preprocess step   | Frontend                   | Binary response schema for SIS client          |
| `app/tiles/providers.pmtiles` | `export_app_data`     | Frontend (map)             | PMTiles vector tiles for provider map markers  |
| `app/la_boundaries.geojson`   | `export_app_data`     | Frontend (map)             | LA boundary polygons                           |
| `app/validation_report.json`  | `publish_data`        | Internal                   | Zod validation summary report                  |
| `parquet/*.parquet`           | `export_parquet_data` | `restore_parquet_data`     | Table backups for all schemas                  |

## Data fixtures

`data/placeholder-providers/` contains test provider JSON files used by the export round-trip test and calculator cost tests.
