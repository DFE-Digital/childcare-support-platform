#!/bin/sh
set -e

PARQUET=/app/data/app/spatial_index.parquet
SIS_FILE="${SIS_FILEPATH:-/app/data/app/spatial_index.sis}"

if [ -f "$PARQUET" ]; then
  echo "Running sis-preprocess..."
  SIS_SCHEMA_JSON_PATH=/app/data/app/sis_schema.json \
    sis-preprocess "$PARQUET"
fi

if [ ! -f "$SIS_FILE" ]; then
  echo "No SIS index at $SIS_FILE — run the data pipeline to generate spatial_index.parquet first."
  echo "Sleeping to avoid restart loop."
  exec sleep infinity
fi

exec sis-query
