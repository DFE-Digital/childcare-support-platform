# childcare-support-platform
This repository contains the code for the Childcare Support Platform SPA and components for the provider data-pipline

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

## Prerequisites

- **Node.js** (version in `.nvmrc`, currently 24.x) via nvm
- **Docker** + Docker Compose
- **Rust** 1.86+ (for `sis/build` and `sis/test` only — deployment uses Docker)
- **Python 3.11+** and **uv** (for the data pipeline)
- **AWS CLI** (for S3 data and deployment)
