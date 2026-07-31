#!/bin/sh
set -e

# Start SIS query server in background (if .sis file exists)
if [ -f "${SIS_FILEPATH:-/app/data/app/spatial_index.sis}" ]; then
    SIS_API_TYPE=http \
    SIS_BBOX_INFLATION="${SIS_BBOX_INFLATION:-1}" \
    SIS_RESULT_LIMIT="${SIS_RESULT_LIMIT:-500}" \
    SIS_FILEPATH="${SIS_FILEPATH:-/app/data/app/spatial_index.sis}" \
    SIS_PORT=3001 \
    RUST_LOG="${RUST_LOG:-info}" \
    sis-query &
fi

# Start Dash app in background
cd /app/data-app
gunicorn app:server --bind 127.0.0.1:8050 --workers 2 &

# Start nginx in foreground
nginx -g 'daemon off;'
