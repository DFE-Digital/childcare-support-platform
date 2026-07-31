FROM rust:1.86-slim AS builder
WORKDIR /app

COPY Cargo.toml Cargo.lock rust-toolchain.toml ./
COPY src/ src/

# BuildKit mount caches persist the cargo registry and incremental build artifacts
# across image rebuilds, even when the layer cache is cold.
# Binaries are copied to /usr/local/bin/ within the same RUN so they exist in the
# image layer — the cache-mounted /app/target directory is not visible to other stages.
RUN --mount=type=cache,target=/usr/local/cargo/registry \
    --mount=type=cache,target=/app/target \
    cargo build --release && \
    cp target/release/sis-preprocess target/release/sis-query /usr/local/bin/

FROM debian:bookworm-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && \
    rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/bin/sis-preprocess /usr/local/bin/
COPY --from=builder /usr/local/bin/sis-query /usr/local/bin/

COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

ENV SIS_API_TYPE=http \
    SIS_BBOX_INFLATION=1 \
    SIS_RESULT_LIMIT=500 \
    SIS_FILEPATH=/app/data/app/spatial_index.sis \
    SIS_PORT=3001 \
    RUST_LOG=info

EXPOSE 3001

CMD ["/app/entrypoint.sh"]
