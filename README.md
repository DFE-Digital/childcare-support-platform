# childcare-support-platform

Childcare cost checker and provider directory for [beststartinlife.gov.uk](https://beststartinlife.gov.uk). Helps parents find local childcare providers, check eligibility for government-funded entitlements, and estimate costs.

This repository contains the code for the Childcare Support Platform SPA, Spatial Index Service and components for the provider data-pipline

## Monorepo structure

| Package                                                                      | Language           | Description                                                            |
| ---------------------------------------------------------------------------- | ------------------ | ---------------------------------------------------------------------- |
| [`packages/app`](packages/app/README.md)                                     | TypeScript / React | Public-facing SPA — provider search, cost checker, map                 |
| [`packages/calculator`](packages/calculator/README.md)                       | TypeScript         | Entitlement eligibility + cost calculation engine                      |
| [`packages/spatial-index-service`](packages/spatial-index-service/README.md) | Rust               | Spatial query server (R-tree index, binary protocol)                   |
| [`packages/data-pipeline`](packages/data-pipeline/README.md)                 | Python             | Dagster pipeline — ingests Ofsted/DfE/LA data, publishes provider JSON |
| [`packages/data-app`](packages/data-app/README.md)                           | Python (Dash)      | Internal data quality dashboard                                        |
| [`packages/schemas`](packages/schemas/README.md)                             | TypeScript         | Generated Zod validators from Prisma schema                            |

Key root-level files: `Makefile`, `Dockerfile`, `docker-compose.yml`, `prisma/schema.prisma`.

## CI/CD

**GitHub Actions workflows** (`.github/workflows/`):

| Workflow                 | Trigger        | What it does                                                                                                        |
| ------------------------ | -------------- | ------------------------------------------------------------------------------------------------------------------- |
| `deploy-application.yml` | Manual trigger | Runs the `build-infrastructure` and `build-spa-sis` actions to provision environment changes and produce application artifacts |

**Warning** The SPA and Spatial index search are not deployed automatically. Due to infrastructural limitations, workflows do not currently have the required permissions to automatically upload the artifacts. Currently, these steps must me completed manually.

## Pre-commit hooks

It is also recommended to run:

```
ln ./scripts/run-tf-checks.sh .git/hooks/pre-commit
```

This will enable a pre-commit hook which runs a terraform fmt and terraform validate against any commit containing terraform changes

## Prerequisites

*If using [mise](https://mise.jdx.dev/) (recommended) simply run `mise install` (Docker must be installed separately)*

- **Node.js** (version in `.nvmrc`, currently 24.x) via nvm
- **Rust** 1.86+ (for `sis/build` and `sis/test` only — deployment uses Docker)
- **Python 3.11+** and **uv** (for the data pipeline)
- **Docker** + Docker Compose

## Getting started

```bash
cp .env.example .env       # fill in POSTGRES_PASSWORD, etc.
make node-setup            # installs nvm, Node, npm dependencies
make pre-commit-setup      # installs pre-commit hooks + linters
```

## Make targets

### Setup

| Target                  | Description                                                  |
| ----------------------- | ------------------------------------------------------------ |
| `make node-setup`       | Install Node (via nvm) + npm dependencies + pre-commit hooks |
| `make pre-commit-setup` | Install pre-commit hooks + linter tools                      |

### App (dev compose: frontend :5173 + SIS :3001)

| Target             | Description                                        |
| ------------------ | -------------------------------------------------- |
| `make app/up`      | Start frontend + spatial-index-service via compose |
| `make app/down`    | Stop app services                                  |
| `make app/restart` | Restart app services                               |
| `make app/logs`    | Open Dozzle log viewer                             |
| `make app/dash-up` | Run data-app (Dash) locally outside Docker         |

### Production (standalone container, :8080 — local testing only)

These targets build a self-contained Docker image that bundles the Vite SPA, Dash data app, Rust SIS binaries, and baked-in parquet data. They are **for local integration testing only** and are not part of the BSIL cloud deployment.

| Target            | Description                                              |
| ----------------- | -------------------------------------------------------- |
| `make prod/build` | Build production Docker image **(fetches data from S3)** |
| `make prod/up`    | Build + run production container locally on :8080        |
| `make prod/down`  | Stop + remove production container                       |

### Data pipeline (compose: Postgres, Dagster, Prisma)

| Target              | Description                                              |
| ------------------- | -------------------------------------------------------- |
| `make data/up`      | Start pipeline services + run tests                      |
| `make data/down`    | Stop pipeline services                                   |
| `make data/rebuild` | Force-recreate all pipeline containers                   |
| `make data/wipe`    | Tear down everything including volumes (destructive)     |
| `make data/psql`    | Open psql shell to local Postgres                        |
| `make data/dagster` | Open Dagster UI in browser                               |
| `make data/migrate` | Run Prisma migrations                                    |
| `make data/prisma`  | Diff schema, generate migration, regenerate client + Zod |
| `make data/jupyter` | Start Jupyter Lab                                        |

### Data operations (require `data/up` running)

| Target                                   | Description                                                                     |
| ---------------------------------------- | ------------------------------------------------------------------------------- |
| `make data/complete METADATA=true/false` | **Full pipeline** — loads sources, daemon cascades all downstream automatically |
| `make data/load-sources`                 | Ingest Ofsted/DfE/SCEYP source data                                             |
| `make data/scrape-ofsted`                | Scrape Ofsted report pages                                                      |
| `make data/scrape-la`                    | Scrape all LA FIS sites (or `partition=bath_ne_somerset` for one)               |
| `make data/extract-la`                   | Extract structured fields from scraped HTML/JSON                                |
| `make data/geocode-ofsted`               | Geocode Ofsted provider addresses                                               |
| `make data/geocode-la`                   | Geocode LA-scraped provider addresses                                           |
| `make data/draft`                        | Build draft provider records                                                    |
| `make data/draft-fixtures`               | Load placeholder fixture data to draft                                          |
| `make data/publish`                      | Publish draft to published schema + validate + spatial index                    |
| `make data/clean`                        | Drop and recreate draft/source schemas (destructive)                            |
| `make data/export-app`                   | Export published data to `exported_data/app/` for the BSIL deployment           |
| `make data/export-parquet`               | Export all tables to parquet for backup                                         |
| `make data/restore-parquet`              | Restore tables from parquet backups                                             |
| `make data/asset name=<asset>`           | Materialize a single Dagster asset by name                                      |
| `make data/push-exported env=<env>`      | Upload exported data to BSIL source-data bucket (deploy action syncs to live)   |
| `make data/push-source`                  | Upload `source_data/` to the raw S3 bucket                                      |
| `make data/fetch-source`                 | Download `source_data/` from the raw S3 bucket                                  |

### Testing

| Target                 | Description                                                   |
| ---------------------- | ------------------------------------------------------------- |
| `make test`            | Run all local tests (app + calculator + SIS)                  |
| `make app/test`        | Run app Vitest suite                                          |
| `make calculator/test` | Run calculator Vitest suite                                   |
| `make sis/test`        | Run SIS Rust tests (`cargo test`)                             |
| `make data/test`       | Run pipeline pytest + Zod validation (needs running Postgres) |

### Teardown

| Target           | Description                                            |
| ---------------- | ------------------------------------------------------ |
| `make down`      | Stop everything (app + data + prod)                    |
| `make data/wipe` | Tear down compose + delete volumes **WILL DESTROY DB** |