# Development stage
FROM node:20-alpine AS development
WORKDIR /app

COPY package.json package-lock.json ./
COPY packages/app/package.json ./packages/app/
COPY packages/calculator/package.json ./packages/calculator/
RUN npm ci

COPY packages/calculator ./packages/calculator
COPY packages/app ./packages/app

CMD ["npm", "run", "dev", "-w", "@bsil/app", "--", "--host"]

# Build stage (Debian, not Alpine — test stage needs glibc SIS binaries from sis-builder)
FROM node:20-slim AS builder
WORKDIR /app

COPY package.json package-lock.json ./
COPY packages/app/package.json ./packages/app/
COPY packages/calculator/package.json ./packages/calculator/
RUN npm ci

COPY packages/calculator ./packages/calculator
COPY packages/app ./packages/app

# Vite feature flags — baked into the static JS build
ENV VITE_FEATURE_SORT_DAILY=true
ENV VITE_FEATURE_SORT_ANNUAL=true
ENV VITE_FEATURE_NO_BIG_KID_ESTIMATES=true
ENV VITE_FEATURE_NO_PROVIDER_ESTIMATES=true
ENV VITE_FEATURE_NO_ADDITIONAL_CHARGES=true

RUN npm run build -w @bsil/calculator && npm run build -w @bsil/app

# SIS (Spatial Index Service) build stage
FROM rust:1.98-slim AS sis-builder
WORKDIR /app

COPY packages/spatial-index-service/Cargo.toml packages/spatial-index-service/Cargo.lock packages/spatial-index-service/rust-toolchain.toml ./
COPY packages/spatial-index-service/src/ src/

# BuildKit mount caches persist the cargo registry and incremental build artifacts
# across image rebuilds, even when the layer cache is cold (e.g. CI, Cargo.lock update).
# Binaries are copied to /usr/local/bin/ within the same RUN so they exist in the image
# layer — the cache-mounted /app/target directory is not visible to other stages.
RUN --mount=type=cache,target=/usr/local/cargo/registry \
    --mount=type=cache,target=/app/target \
    cargo build --release && \
    cp target/release/sis-preprocess target/release/sis-query target/release/sis-geometry /usr/local/bin/

# Lambda build stage — static musl binary for AWS Lambda (x86_64-unknown-linux-musl).
# Only used by `make sis/lambda-bundle`; not referenced by the production build.
FROM rust:1.98-slim AS lambda-builder
WORKDIR /app

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    apt-get install -y --no-install-recommends musl-tools && \
    rustup target add x86_64-unknown-linux-musl

COPY packages/spatial-index-service/Cargo.toml packages/spatial-index-service/Cargo.lock packages/spatial-index-service/rust-toolchain.toml ./
COPY packages/spatial-index-service/src/ src/

RUN --mount=type=cache,target=/usr/local/cargo/registry \
    --mount=type=cache,target=/app/target \
    cargo build --release --target x86_64-unknown-linux-musl --bin sis-query && \
    cp target/x86_64-unknown-linux-musl/release/sis-query /usr/local/bin/sis-query-lambda

# Test stage — gate production on tests passing
FROM builder AS test
COPY --from=sis-builder /usr/local/bin/sis-geometry /usr/local/bin/
COPY --from=sis-builder /usr/local/bin/sis-preprocess /usr/local/bin/
COPY packages/spatial-index-service/testdata/ /app/packages/spatial-index-service/testdata/
COPY packages/data-pipeline/data/placeholder-providers/ /app/packages/data-pipeline/data/placeholder-providers/
COPY .docker-data/app/lad/ /app/.docker-data/app/lad/
COPY .docker-data/app/lad/ /app/exported_data/app/lad/
COPY .docker-data/app/inward/ /app/exported_data/app/inward/
ENV SIS_GEOMETRY_BIN=/usr/local/bin/sis-geometry
ENV SIS_PREPROCESS_BIN=/usr/local/bin/sis-preprocess

# TODO: Uncomment these once we have an answer from No. 10 on how these should run
# RUN npm test -w @bsil/app
# RUN npm test -w @bsil/calculator

# Production stage
FROM python:3.12-slim AS production

# Install nginx
RUN apt-get update && \
    apt-get install -y --no-install-recommends nginx && \
    rm -rf /var/lib/apt/lists/*

# Copy nginx config (overwrite Debian default)
COPY nginx.conf /etc/nginx/nginx.conf

# Copy React SPA build
COPY --from=test /app/packages/app/dist /usr/share/nginx/html/dash/beststartinlife

# Install Python dependencies for Dash app
COPY packages/data-app/requirements.txt /app/data-app/requirements.txt
RUN pip install --no-cache-dir -r /app/data-app/requirements.txt

# Copy Dash app
COPY packages/data-app/ /app/data-app/

# Bake parquet data into image (production is self-contained).
# The glob pattern ensures the build doesn't fail if the directory is empty.
COPY .docker-data/parquet/published/*.parque[t] /app/data/published/
COPY .docker-data/parquet/la/*.parque[t] /app/data/la/

# Copy provider JSON files if available
COPY .docker-data/app/ /app/data/app/

# Copy SIS binaries from Rust build stage
COPY --from=sis-builder /usr/local/bin/sis-preprocess /usr/local/bin/
COPY --from=sis-builder /usr/local/bin/sis-query /usr/local/bin/

# Generate .sis index + schema from parquet (matched pair with sis-query)
RUN if [ -f /app/data/app/spatial_index.parquet ]; then \
      SIS_FILEPATH=/app/data/app/spatial_index.sis \
      SIS_SCHEMA_JSON_PATH=/app/data/app/sis_schema.json \
      sis-preprocess /app/data/app/spatial_index.parquet; \
    fi

# Copy boundary GeoJSON if available (generated by la_boundaries Dagster asset)
COPY .docker-data/la_boundaries.geojso[n] /app/data/

# Copy entrypoint
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

WORKDIR /app
EXPOSE 8080

CMD ["/app/entrypoint.sh"]
