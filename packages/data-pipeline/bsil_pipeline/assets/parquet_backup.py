import json
import shutil
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from dagster import asset, AssetExecutionContext, Config, MetadataValue
from psycopg import sql

from bsil_pipeline.automation import PIPELINE_CONDITION
from bsil_pipeline.resources.postgres import BsilPostgresResource

EXCLUDED_SCHEMAS = frozenset({"information_schema", "pg_catalog", "pg_toast", "public"})


class ParquetExportConfig(Config):
    output_dir: str = "/opt/dagster/app/output/parquet"


class ParquetRestoreConfig(Config):
    source_dir: str = "/opt/dagster/app/source_data/parquet"


def _get_user_schemas(cur) -> list[str]:
    cur.execute(
        "SELECT schema_name FROM information_schema.schemata "
        "WHERE schema_name NOT LIKE 'pg_%%' "
        "AND schema_name NOT LIKE 'archived_%%' "
        "ORDER BY schema_name"
    )
    return [row[0] for row in cur.fetchall() if row[0] not in EXCLUDED_SCHEMAS]


def _get_tables(cur, schema: str) -> list[str]:
    cur.execute(
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema = %s AND table_type = 'BASE TABLE' "
        "ORDER BY table_name",
        (schema,),
    )
    return [row[0] for row in cur.fetchall()]


def _get_column_info(cur, schema: str, table: str) -> list[dict]:
    """Get column metadata including precision/scale for numeric types."""
    cur.execute(
        "SELECT column_name, data_type, numeric_precision, numeric_scale, "
        "  character_maximum_length "
        "FROM information_schema.columns "
        "WHERE table_schema = %s AND table_name = %s "
        "ORDER BY ordinal_position",
        (schema, table),
    )
    return [
        {
            "name": row[0],
            "data_type": row[1],
            "precision": row[2],
            "scale": row[3],
            "max_length": row[4],
        }
        for row in cur.fetchall()
    ]


def _get_column_types(cur, schema: str, table: str) -> dict[str, str]:
    """Backward-compatible: returns {col_name: data_type} for pg_metadata."""
    info = _get_column_info(cur, schema, table)
    return {col["name"]: col["data_type"] for col in info}


def _needs_json_serialization(data_type: str) -> bool:
    return data_type in ("ARRAY", "jsonb", "json") or "json" in data_type.lower()


def _pg_to_arrow_type(col: dict) -> pa.DataType:
    """Map a Postgres column to an Arrow type."""
    dt = col["data_type"]
    if _needs_json_serialization(dt):
        return pa.string()
    mapping = {
        "bigint": pa.int64(),
        "integer": pa.int32(),
        "boolean": pa.bool_(),
        "text": pa.string(),
        "character varying": pa.string(),
        "double precision": pa.float64(),
        "real": pa.float32(),
        "date": pa.date32(),
        "time without time zone": pa.string(),
        "timestamp without time zone": pa.timestamp("us"),
        "timestamp with time zone": pa.timestamp("us", tz="UTC"),
    }
    if dt == "numeric":
        p = col["precision"] or 38
        s = col["scale"] or 0
        return pa.decimal128(p, s)
    return mapping.get(dt, pa.string())


def _serialize_value(val):
    if val is None:
        return None
    if isinstance(val, (list, dict)):
        return json.dumps(val, default=str)
    return json.dumps(val, default=str)


EXPORT_BATCH_SIZE = 500


def _export_table(conn, schema: str, table: str, output_dir: Path, context) -> int:
    with conn.cursor() as meta_cur:
        col_info = _get_column_info(meta_cur, schema, table)
    col_types = {c["name"]: c["data_type"] for c in col_info}
    complex_cols = {
        col for col, dtype in col_types.items() if _needs_json_serialization(dtype)
    }

    # Pre-build Arrow schema from Postgres column metadata so every batch
    # uses consistent types (avoids precision mismatches across batches).
    arrow_fields = [pa.field(c["name"], _pg_to_arrow_type(c)) for c in col_info]
    pg_metadata = {b"pg_column_types": json.dumps(col_types).encode("utf-8")}
    out_schema = pa.schema(arrow_fields, metadata=pg_metadata)

    schema_dir = output_dir / schema
    schema_dir.mkdir(parents=True, exist_ok=True)
    out_path = schema_dir / f"{table}.parquet"

    total_rows = 0
    writer = None

    with conn.cursor(name=f"export_{schema}_{table}") as cur:
        cur.execute(
            sql.SQL("SELECT * FROM {}.{}").format(
                sql.Identifier(schema), sql.Identifier(table)
            )
        )
        col_names = [desc[0] for desc in cur.description]

        while True:
            rows = cur.fetchmany(EXPORT_BATCH_SIZE)
            if not rows:
                break

            # Build columnar data for this batch
            columns: dict[str, list] = {col: [] for col in col_names}
            for row in rows:
                for col, val in zip(col_names, row):
                    if col in complex_cols:
                        columns[col].append(_serialize_value(val))
                    else:
                        columns[col].append(val)

            # Build pyarrow arrays using the pre-defined schema types
            arrays = []
            for i, col in enumerate(col_names):
                target_type = out_schema.field(i).type
                try:
                    arrays.append(pa.array(columns[col], type=target_type))
                except (pa.ArrowInvalid, pa.ArrowTypeError, OverflowError):
                    # Last resort: stringify values that don't fit their declared type
                    arrays.append(
                        pa.array(
                            [str(v) if v is not None else None for v in columns[col]],
                            type=pa.string(),
                        )
                    )

            batch_table = pa.table(dict(zip(col_names, arrays)))

            if writer is None:
                # Re-derive schema in case any column fell back to string
                final_fields = []
                for i, field in enumerate(out_schema):
                    actual = batch_table.schema.field(i)
                    if actual.type != field.type:
                        final_fields.append(actual)
                    else:
                        final_fields.append(field)
                out_schema = pa.schema(final_fields, metadata=pg_metadata)
                writer = pq.ParquetWriter(out_path, out_schema)

            # Cast batch columns to match writer schema
            cast_arrays = []
            for i, field in enumerate(writer.schema):
                col = batch_table.column(i)
                if col.type != field.type:
                    col = col.cast(field.type)
                cast_arrays.append(col)
            batch_table = pa.table(
                dict(zip(col_names, cast_arrays)),
                schema=writer.schema,
            )
            writer.write_table(batch_table)
            total_rows += len(rows)

    if writer is not None:
        writer.close()
    elif total_rows == 0:
        # Empty table — write an empty parquet with the pre-built schema
        empty_table = pa.table(
            {f.name: pa.array([], type=f.type) for f in out_schema},
            schema=out_schema,
        )
        pq.write_table(empty_table, out_path)

    context.log.info(f"  {schema}.{table}: {total_rows} rows -> {out_path}")
    return total_rows


@asset(
    group_name="backup",
    deps=["validate_published"],
    automation_condition=PIPELINE_CONDITION,
)
def export_all_parquet(
    context: AssetExecutionContext,
    config: ParquetExportConfig,
    bsil_postgres: BsilPostgresResource,
):
    """Export all user-schema tables to parquet files."""
    output_dir = Path(config.output_dir)
    if output_dir.exists():
        for child in output_dir.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    output_dir.mkdir(parents=True, exist_ok=True)

    total_tables = 0
    total_rows = 0

    with bsil_postgres.get_connection() as conn:
        with conn.cursor() as cur:
            schemas = _get_user_schemas(cur)
            context.log.info(f"Found schemas: {schemas}")
            schema_tables: dict[str, list[str]] = {}
            for schema in schemas:
                tables = _get_tables(cur, schema)
                schema_tables[schema] = tables
                context.log.info(f"Schema '{schema}': {len(tables)} tables")

        for schema, tables in schema_tables.items():
            for table in tables:
                rows = _export_table(conn, schema, table, output_dir, context)
                total_tables += 1
                total_rows += rows

    context.log.info(
        f"Export complete: {total_tables} tables, {total_rows} rows "
        f"across {len(schemas)} schemas"
    )
    return MetadataValue.text(f"{total_tables} tables, {total_rows} rows")


def _ensure_table_from_parquet(
    cur, schema: str, table: str, parquet_path: Path, context
) -> None:
    """Create a table from parquet column metadata when static DDL is unavailable.

    Used for tables with dynamic DDL (ofsted.inspections, dfe.school_census)
    whose columns are determined at data-load time from source file headers.
    The pg_column_types parquet metadata (written at export) is used to
    reconstruct column types; falls back to TEXT for unknown types.
    """
    pf = pq.ParquetFile(parquet_path)
    parquet_schema = pf.schema_arrow
    pg_meta = parquet_schema.metadata or {}
    raw = pg_meta.get(b"pg_column_types")
    if raw:
        col_types = json.loads(raw.decode("utf-8"))
    else:
        col_types = {}

    col_parts = []
    for col in parquet_schema.names:
        dtype = col_types.get(col, "text")
        if dtype == "ARRAY":
            dtype = "TEXT[]"
        col_parts.append(sql.SQL("{} {}").format(sql.Identifier(col), sql.SQL(dtype)))

    cur.execute(
        sql.SQL("CREATE TABLE IF NOT EXISTS {}.{} ({})").format(
            sql.Identifier(schema),
            sql.Identifier(table),
            sql.SQL(", ").join(col_parts),
        )
    )
    context.log.info(f"  Auto-created {schema}.{table} from parquet metadata")


RESTORE_BATCH_SIZE = 2000


def _copy_table(cur, schema: str, table: str, parquet_path: Path, context) -> int:
    """COPY data from a parquet file into a (pre-truncated) table."""
    pf = pq.ParquetFile(parquet_path)
    parquet_schema = pf.schema_arrow
    col_names = parquet_schema.names
    num_rows = pf.metadata.num_rows

    if num_rows == 0:
        context.log.info(f"  {schema}.{table}: 0 rows (empty table)")
        return 0

    # Identify columns that were serialised from ARRAY/JSON types.
    # The export writes pg_column_types metadata; ARRAY columns are stored
    # as JSON strings in parquet and must be deserialised back to Python
    # lists so psycopg COPY formats them as PG array literals ({...}).
    pg_meta = parquet_schema.metadata or {}
    raw_types = pg_meta.get(b"pg_column_types")
    col_types = json.loads(raw_types.decode("utf-8")) if raw_types else {}
    array_cols = {col for col in col_names if col_types.get(col) == "ARRAY"}

    # Bulk insert via COPY, streaming batches to avoid OOM on large tables
    col_ids = sql.SQL(", ").join(sql.Identifier(c) for c in col_names)
    copy_sql = sql.SQL("COPY {}.{} ({}) FROM STDIN").format(
        sql.Identifier(schema), sql.Identifier(table), col_ids
    )

    total_restored = 0
    with cur.copy(copy_sql) as copy:
        for batch in pf.iter_batches(batch_size=RESTORE_BATCH_SIZE):
            batch_dict = batch.to_pydict()
            batch_len = len(next(iter(batch_dict.values())))
            for row_idx in range(batch_len):
                row_values = []
                for col in col_names:
                    val = batch_dict[col][row_idx]
                    if col in array_cols and isinstance(val, str):
                        val = json.loads(val)
                    row_values.append(val)
                copy.write_row(row_values)
            total_restored += batch_len

    context.log.info(f"  {schema}.{table}: {total_restored} rows restored")
    return total_restored


def _reset_sequences(cur, schema: str, table: str):
    """Reset serial/identity sequences to max(col)+1 after data load."""
    cur.execute(
        "SELECT column_name, column_default FROM information_schema.columns "
        "WHERE table_schema = %s AND table_name = %s "
        "AND column_default LIKE 'nextval%%'",
        (schema, table),
    )
    for col_name, col_default in cur.fetchall():
        # Extract sequence name from nextval('schema.seq_name'::regclass)
        seq_expr = col_default  # e.g. nextval('"bsil"."providers_id_seq"'::regclass)
        cur.execute(
            sql.SQL(
                "SELECT setval({default}::regclass, COALESCE(MAX({col}), 0) + 1, false) "
                "FROM {schema}.{table}"
            ).format(
                default=sql.Literal(
                    seq_expr.replace("nextval(", "").split("::")[0].strip("'\"()")
                ),
                col=sql.Identifier(col_name),
                schema=sql.Identifier(schema),
                table=sql.Identifier(table),
            )
        )


@asset(
    group_name="backup",
    deps=[
        "dfe_gias_schools_table",
        "dfe_school_census_table",
        "dfe_free_breakfast_club_schools_table",
        "la_family_information_services_table",
        "la_scrape_results_table",
        "la_extract_results_table",
        "ofsted_inspections_table",
        "ofsted_school_inspections_table",
        "ofsted_scrape_results_table",
        "os_bounding_boxes_table",
        "os_la_name_lookup_table",
        "os_ofsted_places_table",
        "os_la_places_table",
    ],
)
def restore_all_parquet(
    context: AssetExecutionContext,
    config: ParquetRestoreConfig,
    bsil_postgres: BsilPostgresResource,
):
    """Restore all tables from parquet files.

    Depends on schema-table assets which create all schemas and most tables.
    Tables with dynamic DDL (ofsted.inspections, dfe.school_census) are
    auto-created from parquet metadata if they don't already exist.
    """
    source_dir = Path(config.source_dir)
    if not source_dir.exists():
        context.log.warning(
            f"Source directory {source_dir} does not exist, nothing to restore"
        )
        return MetadataValue.text("0 tables, 0 rows (no source directory)")

    total_tables = 0
    total_rows = 0

    with bsil_postgres.get_connection() as conn:
        with conn.cursor() as cur:
            # Verify published schema exists (managed by Prisma, not by us)
            db_schemas = set(_get_user_schemas(cur))
            if "published" not in db_schemas:
                raise RuntimeError(
                    "published schema not found — run 'make data/migrate' before restoring"
                )

            # Disable FK constraints during restore
            cur.execute("SET session_replication_role = 'replica'")

            # First pass: discover tables, auto-create missing ones, and
            # collect the (schema, table, parquet_path) triples for restore.
            restore_plan: list[tuple[str, str, Path]] = []

            for schema_dir in sorted(source_dir.iterdir()):
                if not schema_dir.is_dir():
                    continue
                schema = schema_dir.name

                if schema not in db_schemas:
                    context.log.warning(
                        f"Schema '{schema}' not found in database, skipping "
                        f"(schema assets should have created it)"
                    )
                    continue

                existing_tables = set(_get_tables(cur, schema))

                for parquet_file in sorted(schema_dir.glob("*.parquet")):
                    table = parquet_file.stem

                    if table not in existing_tables:
                        _ensure_table_from_parquet(
                            cur, schema, table, parquet_file, context
                        )

                    restore_plan.append((schema, table, parquet_file))

            # Truncate ALL tables in one statement so FK CASCADE doesn't
            # undo previously-restored data (e.g. published.care_types
            # referencing published.providers).
            if restore_plan:
                all_tables = sql.SQL(", ").join(
                    sql.SQL("{}.{}").format(sql.Identifier(s), sql.Identifier(t))
                    for s, t, _ in restore_plan
                )
                cur.execute(sql.SQL("TRUNCATE {} CASCADE").format(all_tables))
                context.log.info(
                    f"Truncated {len(restore_plan)} tables across all schemas"
                )

            # Second pass: COPY data into each table.
            for schema, table, parquet_file in restore_plan:
                rows = _copy_table(cur, schema, table, parquet_file, context)
                _reset_sequences(cur, schema, table)
                total_tables += 1
                total_rows += rows

            # Re-enable FK constraints
            cur.execute("SET session_replication_role = 'origin'")
            conn.commit()

    context.log.info(f"Restore complete: {total_tables} tables, {total_rows} rows")
    return MetadataValue.text(f"{total_tables} tables, {total_rows} rows")
