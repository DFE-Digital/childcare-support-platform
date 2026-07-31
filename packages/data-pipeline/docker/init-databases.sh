#!/bin/bash
set -e

# Create the dagster metadata database if it doesn't exist
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT 'CREATE DATABASE ${DAGSTER_PG_DB}'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '${DAGSTER_PG_DB}')\gexec
EOSQL

# Create the test database if it doesn't exist
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SELECT 'CREATE DATABASE bsil_test'
    WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'bsil_test')\gexec
EOSQL
