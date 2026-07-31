"""Pull PostHog events into Postgres via the Events API.

This is an interim solution for low-volume, on-demand use. The target
architecture is:

  1. PostHog Batch Export writes daily Parquet files to S3
  2. A Dagster asset reads Parquet from S3 and loads into Postgres

That approach avoids public DB exposure, handles bulk transfer efficiently,
supports schema evolution via Parquet, and decouples from PostHog API rate
limits. It requires a persistent Dagster cluster with a scheduled sensor.
"""

import json
import os
import time
from datetime import datetime, timedelta, timezone

import requests
from dagster import asset, AssetExecutionContext, MetadataValue

from bsil_pipeline.resources.postgres import BsilPostgresResource

_POSTHOG_HOST = "https://eu.posthog.com"
_PAGE_SIZE = 1000
_RATE_LIMIT_SLEEP = 1.0
_DEFAULT_LOOKBACK_DAYS = 30

_INSERT_SQL = """
INSERT INTO posthog.events (uuid, event, properties, timestamp, distinct_id, session_id)
VALUES (%(uuid)s, %(event)s, %(properties)s, %(timestamp)s, %(distinct_id)s, %(session_id)s)
ON CONFLICT (uuid) DO NOTHING
"""


def _get_config():
    api_key = os.environ.get("POSTHOG_API_KEY", "")
    project_id = os.environ.get("POSTHOG_PROJECT_ID", "")
    if not api_key:
        raise ValueError("POSTHOG_API_KEY environment variable is required")
    if not project_id:
        raise ValueError("POSTHOG_PROJECT_ID environment variable is required")
    return api_key, project_id


def _fetch_page(
    session: requests.Session,
    project_id: str,
    after: str,
    before: str | None = None,
    url: str | None = None,
):
    """Fetch one page of events.

    Uses `url` for cursor-based pagination if provided, otherwise constructs
    a request with after/before params. The PostHog Events API returns events
    newest-first and requires `before` to paginate backwards through time.
    """
    if url is None:
        url = f"{_POSTHOG_HOST}/api/projects/{project_id}/events/"
        params: dict[str, str] = {"after": after, "limit": str(_PAGE_SIZE)}
        if before:
            params["before"] = before
    else:
        params = None

    resp = session.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


@asset(
    group_name="posthog",
    deps=["posthog_events_table"],
)
def posthog_events(
    context: AssetExecutionContext,
    bsil_postgres: BsilPostgresResource,
):
    """Pull events from PostHog Events API into posthog.events table.

    Incremental: uses MAX(timestamp) from existing rows as the cursor.
    Idempotent: ON CONFLICT (uuid) DO NOTHING prevents duplicates.
    """
    api_key, project_id = _get_config()

    with bsil_postgres.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT MAX(timestamp) FROM posthog.events")
            row = cur.fetchone()
            last_ts = row[0] if row and row[0] else None

    if last_ts is None:
        after = (
            datetime.now(timezone.utc) - timedelta(days=_DEFAULT_LOOKBACK_DAYS)
        ).isoformat()
        context.log.info(
            f"No existing events — pulling last {_DEFAULT_LOOKBACK_DAYS} days"
        )  # noqa: G004
    else:
        after = last_ts.isoformat()
        context.log.info(f"Incremental pull from {after}")  # noqa: G004

    session = requests.Session()
    session.headers.update(
        {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
    )

    total_inserted = 0
    pages_fetched = 0
    min_ts = None
    max_ts = None
    before_cursor = datetime.now(timezone.utc).isoformat()

    while True:
        data = _fetch_page(session, project_id, after, before=before_cursor)
        results = data.get("results", [])
        pages_fetched += 1

        if not results:
            break

        batch = []
        page_oldest_ts = None
        for event in results:
            properties = event.get("properties", {})
            ts = event.get("timestamp")
            row = {
                "uuid": event["id"],
                "event": event["event"],
                "properties": properties
                if isinstance(properties, str)
                else json.dumps(properties),
                "timestamp": ts,
                "distinct_id": event.get("distinct_id"),
                "session_id": properties.get("$session_id")
                if isinstance(properties, dict)
                else None,
            }
            batch.append(row)

            if ts:
                if min_ts is None or ts < min_ts:
                    min_ts = ts
                if max_ts is None or ts > max_ts:
                    max_ts = ts
                if page_oldest_ts is None or ts < page_oldest_ts:
                    page_oldest_ts = ts

        with bsil_postgres.get_connection() as conn:
            with conn.cursor() as cur:
                for row in batch:
                    cur.execute(_INSERT_SQL, row)
            conn.commit()

        total_inserted += len(batch)
        context.log.info(
            f"  Page {pages_fetched}: {len(results)} events fetched, "  # noqa: G004
            f"{len(batch)} inserted"
        )

        if not page_oldest_ts:
            break

        before_cursor = page_oldest_ts
        time.sleep(_RATE_LIMIT_SLEEP)

    context.log.info(
        f"Done: {total_inserted} events inserted across {pages_fetched} pages"  # noqa: G004
    )
    if min_ts and max_ts:
        context.log.info(f"Date range: {min_ts} to {max_ts}")  # noqa: G004

    return {
        "events_inserted": MetadataValue.int(total_inserted),
        "pages_fetched": MetadataValue.int(pages_fetched),
        "date_range_start": MetadataValue.text(min_ts or "none"),
        "date_range_end": MetadataValue.text(max_ts or "none"),
    }
