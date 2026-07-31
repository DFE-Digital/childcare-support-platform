# Spatial Index Service (SIS)

A Rust package producing two binaries from one crate:

- **sis-preprocess** -- CLI tool that reads `spatial_index.parquet`, builds a Hilbert R-tree, and serializes everything into a compact `.sis` file using [rkyv](https://rkyv.org/) zero-copy deserialization.
- **sis-query** -- HTTP server that loads the `.sis` file at startup and answers spatial queries with column-major binary responses.

They are a **matched pair** -- the `.sis` file is only guaranteed readable by a `sis-query` built from the same `Cargo.lock`. During deployment, `sis-preprocess` runs first, then the `.sis` file and `sis-query` binary are deployed together.

## Architecture overview

```
spatial_index.parquet
        |
  sis-preprocess
        |
   +----+----+
   |         |
 .sis file   sis_schema.json  (consumed by frontend build)
   |
 sis-query  (HTTP server, port 3001)
   |
 GET /api/spatial-query  -->  binary response
```

### Why Rust?

The parquet file contains ~100K rows of provider data. The SIS achieves:

- **~1-5ms cold start** (mmap `.sis` file + rebuild R-tree) vs ~15-50ms loading parquet with Arrow
- **Zero-copy access** to all column data via rkyv's `ArchivedVec`
- **~23KB typical response** (200 providers x ~2 rows avg x 82 bytes/row, gzip-compressed)

## Input: `spatial_index.parquet`

The parquet file is produced by the data pipeline (`packages/data-pipeline`). Its canonical schema is defined in `packages/data-pipeline/bsil_pipeline/spatial_index/schema.py` (`SPATIAL_INDEX_SCHEMA`).

### Schema

| Column                        | Arrow type | Nullable | Description                                                     |
| ----------------------------- | ---------- | -------- | --------------------------------------------------------------- |
| `provider_id`                 | int64      | no       | Unique provider identifier                                      |
| `caretype_index`              | int8       | no       | 0-based index of this care type row within the provider         |
| `care_type`                   | int8       | no       | Care type enum (0–6, or -1 for unlocated/unknown)               |
| `lat`                         | float32    | yes      | Latitude: point provider's location, or bbox NW corner lat      |
| `lon`                         | float32    | yes      | Longitude: point provider's location, or bbox NW corner lon     |
| `bbox_lat`                    | float32    | yes      | Bbox SE corner latitude (null for point/unlocated providers)    |
| `bbox_lon`                    | float32    | yes      | Bbox SE corner longitude (null for point/unlocated providers)   |
| `filter_accepts_funded_hours` | bool       | no       | Whether this care type accepts funded hours                     |
| `filter_eligible_min_months`  | int8       | yes      | Minimum eligible age in months (null = unknown)                 |
| `filter_eligible_min_years`   | int8       | yes      | Minimum eligible age in years (null = unknown)                  |
| `filter_eligible_max_years`   | int8       | yes      | Maximum eligible age in years (null = unknown)                  |
| `sort_daily_open`             | float32    | yes      | Earliest daily opening time as decimal hours (e.g. 7.5 = 07:30) |
| `sort_daily_close`            | float32    | yes      | Latest daily closing time as decimal hours                      |
| `sort_annual_opening`         | int8       | no       | Operating weeks per year (-1 = unknown)                         |
| `sort_ofsted`                 | float32    | no       | Ofsted score (0.0 = no inspection)                              |
| `sort_graduates`              | float32    | yes      | Graduate staff percentage (0–1, null = unknown)                 |
| `sort_turnover`               | float32    | yes      | Staff turnover percentage (0–1, null = unknown)                 |
| `sort_cost_all`               | float32    | yes      | Cost per hour, all ages (£, null = unknown)                     |
| `sort_cost_under2`            | float32    | yes      | Cost per hour, under-2 (null = N/A or unknown)                  |
| `sort_cost_age2`              | float32    | yes      | Cost per hour, age 2                                            |
| `sort_cost_age3to4`           | float32    | yes      | Cost per hour, age 3–4                                          |
| `sort_cost_age2plus`          | float32    | yes      | Cost per hour, age 2+                                           |
| `sort_cost_age5plus`          | float32    | yes      | Cost per hour, age 5+                                           |
| `lad_code`                    | int32      | no       | LAD code encoded as int32 (E=1,S=2,W=3,N=4 prefix + 8 digits)   |

### Row ordering

Rows **must** be sorted by `provider_id`, then `caretype_index`. The preprocessor relies on this to build provider lookup tables (contiguous row ranges per provider).

### Granularity

One row per (provider, care_type) pair. A provider offering 3 care types has 3 rows. Coordinates and provider-level fields (`lat`, `lon`, `bbox_lat`, `bbox_lon`, `sort_ofsted`, `sort_graduates`, `sort_turnover`) are repeated identically across all rows for a given provider.

### Care type enum

| Value | Care type            |
| ----- | -------------------- |
| 0     | private_nursery      |
| 1     | school_based_nursery |
| 2     | childminder          |
| 3     | breakfast_club       |
| 4     | free_breakfast_club  |
| 5     | after_school_club    |
| 6     | holiday_club         |
| -1    | unlocated / unknown  |

Defined in `packages/data-pipeline/bsil_pipeline/spatial_index/schema.py:CARE_TYPE_ENUM`.

### Null handling

Arrow nulls in the parquet are converted to sentinel values during preprocessing:

- **float32** nulls → `NaN`
- **Nullable int8** nulls → `-1`
- **bool** → `u8` (`true` = 1, `false` = 0)

These sentinels carry through to the `.sis` file and wire format unchanged.

## Preprocessing pipeline (`sis-preprocess`)

`sis-preprocess` reads the parquet and produces two output files. Here's what it does step by step:

1. **Read parquet** — loads all rows into memory, applying the null-to-sentinel mapping above
2. **Build provider lookup** — scans the sorted `provider_id` column to find contiguous row ranges: `(first_row, row_count)` per unique provider. Computes each provider's centre point:
   - **Bbox provider** (both `lat` and `bbox_lat` non-null): midpoint of NW corner `(lat, lon)` and SE corner `(bbox_lat, bbox_lon)`
   - **Point provider** (`lat` non-null, `bbox_lat` null): `(lat, lon)` directly
   - **Unlocated provider** (`lat` null): `(NaN, NaN)`
3. **Build unified R-tree AABBs** — for each located provider, emits one axis-aligned bounding box:
   - **Point provider** → degenerate AABB (min == max)
   - **Bbox provider** → full-extent AABB from the four corner coordinates
   - **Unlocated providers** are excluded from the spatial index entirely
4. **Serialize with rkyv** — writes the `SisStore` struct (all column vectors, provider lookup tables, and R-tree AABBs) as a zero-copy-deserializable `.sis` binary file
5. **Write schema JSON** — `sis_schema.json` containing:
   - `SisDataSchema`: column name/type pairs matching the binary response wire format
   - `SisBBoxInflation`: viewport inflation factor
   - `SisResultLimit`: max providers per query
   - `SisCareTypes`: care type name → enum index
   - `SisCareTypeBits`: care type name → bitmask for the `ct` query parameter

   This file is consumed at build time by the frontend (imported statically into the client).

## Crate structure

```
src/
  lib.rs                  # Module declarations
  config.rs               # Env var parsing (shared by both binaries)
  parquet.rs              # Parquet reader + provider lookup builder
  store.rs                # SisStore: rkyv-serializable container struct
  index.rs                # Hilbert R-tree build, inflation, spatial query
  query.rs                # Request pipeline + haversine + SisState (mmap loader)
  response.rs             # Column-major binary response serializer
  bin/
    sis_preprocess.rs     # CLI binary
    sis_query.rs          # HTTP server binary
tests/
  integration.rs          # End-to-end HTTP round-trip test
testdata/
  generate_fixture.py     # Creates the test parquet
  test_spatial_index.parquet
```

## Environment variables

| Variable               | Default             | Description                                                           |
| ---------------------- | ------------------- | --------------------------------------------------------------------- |
| `SIS_API_TYPE`         | `http`              | API mode (`http` or `lambda`)                                         |
| `SIS_BBOX_INFLATION`   | `1`                 | Viewport inflation factor (float; `1` = 50% per side)                 |
| `SIS_RESULT_LIMIT`     | `500`               | Max providers per population (point and bbox independently) per query |
| `SIS_FILEPATH`         | `spatial_index.sis` | Path to the `.sis` file                                               |
| `SIS_SCHEMA_JSON_PATH` | `sis_schema.json`   | Output path for schema JSON (preprocess only)                         |
| `SIS_CORS_ORIGIN`      | `*`                 | CORS allowed origin(s) — `*`, single, or comma-separated list         |
| `SIS_PORT`             | `3001`              | HTTP listen port (query server only)                                  |
| `RUST_LOG`             | `info`              | Log level filter (standard `tracing` env filter)                      |

**WARNING:** environment for `sis-preprocess` and `sis-query` **must match** because the former writes some into `sis_schema.json` which is
then read statically from the frontend into the client browser. At runtime the browser and `sis-query` both need to have the same values.

## Usage

### Preprocessing

```sh
SIS_FILEPATH=output/spatial_index.sis \
SIS_SCHEMA_JSON_PATH=output/sis_schema.json \
SIS_BBOX_INFLATION=1 \
SIS_RESULT_LIMIT=500 \
  sis-preprocess path/to/spatial_index.parquet
```

This produces two files:

1. The `.sis` binary file (rkyv-serialized store + R-tree AABBs)
2. `sis_schema.json` describing the binary response format for the frontend

### Query server

```sh
SIS_FILEPATH=output/spatial_index.sis \
SIS_API_TYPE=http \
SIS_PORT=3001 \
  sis-query
```

### Query API

```
GET /api/spatial-query
  ?pc_south=51.4&pc_west=-0.2&pc_north=51.6&pc_east=0.1
  &pc_lat=51.5&pc_lon=-0.05
  &map_south=51.3&map_west=-0.3&map_north=51.7&map_east=0.2
  &ct=0
```

| Param                                            | Description                                                                                                                   |
| ------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------- |
| `pc_south`, `pc_west`, `pc_north`, `pc_east`     | Postcode bounding box                                                                                                         |
| `pc_lat`, `pc_lon`                               | Postcode centroid (used for distance calculation)                                                                             |
| `map_south`, `map_west`, `map_north`, `map_east` | Map viewport rectangle                                                                                                        |
| `ct`                                             | Care-type bitfield (u8, default `0` = all types). Each bit enables one care type; see `SisCareTypeBits` in `sis_schema.json`. |

### Terminology

| Symbol | Name                | Definition                                                                                                                                                                                                                                                                                                                            |
| ------ | ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **P**  | Postcode centroid   | `pc_lat`/`pc_lon` — the user's postcode centre, used as the origin for distance sorting and as the centre of _R_                                                                                                                                                                                                                      |
| **V**  | Viewport            | `map_south`/`map_west`/`map_north`/`map_east` — the map rectangle currently visible to the user                                                                                                                                                                                                                                       |
| **I**  | Inflated rectangle  | _V_ expanded symmetrically by `SIS_BBOX_INFLATION` — the rectangle actually queried against the R-tree                                                                                                                                                                                                                                |
| **N**  | Result limit        | `SIS_RESULT_LIMIT` — maximum providers per population per query. Point and bbox providers are limited independently to _N_ each, then merged                                                                                                                                                                                          |
| **R**  | Completeness circle | Circle centred on _P_ whose radius equals the distance to the furthest returned **point** provider. Bbox provider distances are excluded — their max-corner haversine distances are structurally larger and not meaningful for the R-circle geometry. When _N_ is reached for points, results are only guaranteed complete within _R_ |

### Query pipeline

1. **Inflate** _V_ → _I_ (symmetric expansion by `SIS_BBOX_INFLATION`)
2. **Spatial query**: query the unified R-tree with _I_, then **split** hits into point and bbox populations
3. **Filter** each population by care-type bitfield (`ct` parameter; `0` = no filter)
4. **Compute distances** (haversine) from _P_ to each matched provider — point providers use point-to-point distance; bbox providers use max distance to the 4 rectangle corners
5. **Sort** each population ascending by distance, **truncate** each independently to _N_
6. **R-circle check** (point population only): if _N_ was hit for points and _R_ (from the furthest point provider) does not contain _V_ → **re-query** both populations with _V_ (no inflation), respond with `SIS_MAGIC_EXACT`
7. Otherwise **merge** both populations into a single globally-sorted list, respond with `SIS_MAGIC_INFLATED`
8. **Expand** providers to care-type rows, **serialize** column-major binary

### Binary response format

Content-Type: `application/octet-stream`

**Header** (8 bytes):

| Offset | Size | Type   | Value                                                                                       |
| ------ | ---- | ------ | ------------------------------------------------------------------------------------------- |
| 0      | 4    | u32 LE | `0x53495300` ("SIS\0") = inflated _I_ query, or `0x53495301` ("SIS\1") = exact _V_ re-query |
| 4      | 4    | u32 LE | Row count N                                                                                 |

**Body** -- 24 columns in schema order, tightly packed (no padding):

| Column                        | Wire type | Bytes per row |
| ----------------------------- | --------- | ------------- |
| `provider_id`                 | i64 LE    | 8             |
| `care_type`                   | i8        | 1             |
| `sort_distance`               | f32 LE    | 4             |
| `sort_daily_open`             | f32 LE    | 4             |
| `sort_daily_close`            | f32 LE    | 4             |
| `sort_annual_opening`         | i8        | 1             |
| `sort_ofsted`                 | f32 LE    | 4             |
| `sort_graduates`              | f32 LE    | 4             |
| `sort_turnover`               | f32 LE    | 4             |
| `sort_cost_all`               | f32 LE    | 4             |
| `sort_cost_under2`            | f32 LE    | 4             |
| `sort_cost_age2`              | f32 LE    | 4             |
| `sort_cost_age3to4`           | f32 LE    | 4             |
| `sort_cost_age2plus`          | f32 LE    | 4             |
| `sort_cost_age5plus`          | f32 LE    | 4             |
| `filter_accepts_funded_hours` | u8        | 1             |
| `filter_eligible_min_months`  | i8        | 1             |
| `filter_eligible_min_years`   | i8        | 1             |
| `filter_eligible_max_years`   | i8        | 1             |
| `bbox_south`                  | f32 LE    | 4             |
| `bbox_west`                   | f32 LE    | 4             |
| `bbox_north`                  | f32 LE    | 4             |
| `bbox_east`                   | f32 LE    | 4             |
| `lad_code`                    | i32 LE    | 4             |

**Total: 82 bytes per row.** Each column occupies a contiguous block of `N * size` bytes, so the frontend can create typed array views directly into the response buffer without copying.

Rows are sorted globally by ascending distance from _P_. Both point and bbox providers appear in the same sorted order.

**Bbox columns carry location data for all located providers.** The four columns
reuse lat/lon/bbox_lat/bbox_lon from the input data:

| Column       | Point provider | Bbox provider              | Unlocated |
| ------------ | -------------- | -------------------------- | --------- |
| `bbox_south` | NaN            | SE corner lat (`bbox_lat`) | NaN       |
| `bbox_west`  | point lon      | NW corner lon (`lon`)      | NaN       |
| `bbox_north` | point lat      | NW corner lat (`lat`)      | NaN       |
| `bbox_east`  | NaN            | SE corner lon (`bbox_lon`) | NaN       |

To distinguish: `isNaN(bbox_south)` → point or unlocated; non-NaN → bbox provider.
For all located providers, `bbox_north`/`bbox_west` always contain the lat/lon.

Null sentinel values: `NaN` for f32 columns, `-1` for nullable i8 columns.

## Data flow

### What's in the `.sis` file

The `SisStore` struct contains:

- **Column vectors** (one element per care-type row) -- provider_id, care_type, coordinates, filters, sort scores
- **Provider lookup tables** (one element per unique provider) -- first_row index, row_count, centre lat/lon
- **Unified R-tree input AABBs** -- arrays for all located providers (point + bbox), each with min/max x/y bounding boxes and provider index mapping

### What's rebuilt on startup

A single `StaticAABB2DIndex<f32>` Hilbert R-tree is rebuilt from the stored AABBs on startup (~1-5ms for 50K providers). All column data is accessed zero-copy from the mmap'd file.

### Provider types

- **Point providers**: single lat/lon coordinate, degenerate AABB (min == max). Lat/lon sent as `bbox_north`/`bbox_west`; `bbox_south`/`bbox_east` are NaN
- **Bbox providers**: NW corner (lat/lon) and SE corner (bbox*lat/bbox_lon), full AABB. All 4 bbox columns populated. Bbox providers are sorted and limited independently from point providers (each population truncated to \_N*), then merged into a single globally-sorted response. This prevents bbox providers (whose max-corner distances are structurally larger) from competing with nearby point providers for result slots
- **Unlocated providers**: all coordinates NaN, excluded from the R-tree (never returned in spatial queries). All 4 bbox columns NaN

All provider types share a single unified R-tree index.

## Docker

### Dev (standalone container)

```sh
docker compose up spatial-index-service
```

Requires `exported_data/app/spatial_index.sis` to exist (produced by the Dagster pipeline's `sis-preprocess` step).

### Production

The root `Dockerfile` includes a Rust build stage (`sis-builder`) that compiles both binaries. The `entrypoint.sh` starts `sis-query` in the background alongside gunicorn and nginx. Nginx proxies `/api/spatial-query` to port 3001.

## Lambda

The query server supports AWS Lambda deployment via `SIS_API_TYPE=lambda`. The same Router, handlers, and middleware serve both HTTP and Lambda modes — `lambda_http::run(app)` wraps the Axum Router as a Lambda handler.

### Prerequisites

```sh
cargo install cargo-lambda
```

### Building a Lambda bundle

```sh
make sis/lambda-bundle
```

This cross-compiles for Lambda (Linux musl), bundles the `bootstrap` binary with the `.sis` data file, and produces `packages/spatial-index-service/target/sis-lambda.zip`.

### Local testing with cargo-lambda

```sh
SIS_FILEPATH=exported_data/app/spatial_index.sis \
SIS_API_TYPE=lambda \
  cargo lambda watch --bin sis-query
```

Then query at `http://localhost:9000/api/spatial-query?...`.

### API Gateway notes

- **HTTP API / Function URLs**: work out of the box — binary responses pass through as-is.
- **REST API**: requires binary media type `application/octet-stream` configured under API settings, and `*/*` in the integration response content handling set to `CONVERT_TO_BINARY`.

#### Path prefix behaviour in `lambda_http` ≥ 0.12

`lambda_http` constructs the request URI as `/{stage}{path}` for API Gateway REST API (v1) events. For a BSIL dev environment this means Axum sees `/dev/api/spatial-query`, not `/api/spatial-query`. To handle both forms, `build_router` registers duplicate routes under a `/:stage` wildcard prefix:

```rust
.route("/api/spatial-query", get(spatial_query_handler))        // HTTP mode / Function URLs
.route("/{stage}/api/spatial-query", get(spatial_query_handler)) // REST API via lambda_http
```

If you see **404 responses from the Lambda** (even though `SIS store loaded` appears in the logs), this is the likely cause. Verify by invoking the Lambda directly — see the smoke-test section below.

### CORS

The shared router includes a CORS layer (`GET` only). The allowed origin is controlled by `SIS_CORS_ORIGIN`:

- **Unset or `*`** (default) — `Access-Control-Allow-Origin: *` (permissive, suitable for dev or behind nginx)
- **Single origin** — e.g. `SIS_CORS_ORIGIN=https://example.com`
- **Comma-separated list** — e.g. `SIS_CORS_ORIGIN=https://prod.example.com,https://staging.example.com `

Invalid values panic at startup with a clear error message.

## Development

### Prerequisites

- Rust 1.86+ (pinned in `rust-toolchain.toml`)
- Python 3.10+ with `pyarrow` (for regenerating the test fixture)

### Build

```sh
cargo build           # dev
cargo build --release # optimised
```

### Test

```sh
cargo test            # unit + integration tests
cargo test --lib      # unit tests only
```

### Cross-language parity test

The `sis-geometry` binary is a test oracle that reads JSON test vectors from stdin and writes computed results to stdout. A vitest test in `packages/app` (`spatial-parity.test.ts`) spawns it, runs the same inputs through the JS geometry functions, and asserts parity. Build it with:

```sh
cargo build --bin sis-geometry
```

Then run the parity test from the app package:

```sh
cd packages/app && npx vitest run spatial-parity
```

The test skips (does not fail) if the binary is not found.

### Regenerate test fixture

```sh
python3 testdata/generate_fixture.py
```

Creates a 13-row parquet with 9 providers covering point, bbox (including multiple overlapping bbox providers), unlocated, and multi-care-type scenarios.

## BSIL deployment testing

These steps verify the full stack after deploying to a BSIL environment. Run them in order — each layer builds on the previous one. Replace `dev` with `preprod` or `prod` as needed.

**Prerequisites**: AWS credentials for the target account (`aws sso login --profile bsil-<env>`).

### 1. Lambda direct invocation

Bypasses API Gateway and CloudFront entirely to confirm the binary loads and routes correctly.

```sh
aws lambda invoke \
  --function-name beststartinlife-dev-spatial-index \
  --cli-binary-format raw-in-base64-out \
  --payload '{
    "resource": "/{proxy+}",
    "path": "/api/spatial-query",
    "httpMethod": "GET",
    "headers": {"Accept": "*/*", "Host": "execute-api.eu-west-2.amazonaws.com"},
    "multiValueHeaders": {},
    "queryStringParameters": {
      "pc_south":"51.4","pc_west":"-0.2","pc_north":"51.6","pc_east":"0.1",
      "pc_lat":"51.5","pc_lon":"-0.05",
      "map_south":"51.4","map_west":"-0.2","map_north":"51.6","map_east":"0.1",
      "ct":"0"
    },
    "multiValueQueryStringParameters": null,
    "pathParameters": {"proxy": "api/spatial-query"},
    "stageVariables": null,
    "requestContext": {
      "resourceId": "test", "resourcePath": "/{proxy+}", "httpMethod": "GET",
      "requestId": "test", "stage": "dev",
      "identity": {"sourceIp": "1.2.3.4", "userAgent": "test"},
      "apiId": "test"
    },
    "body": null,
    "isBase64Encoded": false
  }' \
  /tmp/sis_out.json && python3 -c "
import json, base64
d = json.load(open('/tmp/sis_out.json'))
print('Status:', d.get('statusCode'))
if d.get('isBase64Encoded'):
    b = base64.b64decode(d['body'])
    magic = b[:4].hex()
    rows  = int.from_bytes(b[4:8], 'little')
    print(f'Binary: {len(b)} bytes, magic={magic}, rows={rows}')
else:
    print('Body:', d.get('body','')[:200])
"
```

**Expected:** `Status: 200`, `magic=53495300` or `53495301`, `rows > 0`.

If you see `Status: 404` with an empty body: the `lambda_http` path-prefix routes are missing — see the [path prefix behaviour](#path-prefix-behaviour-in-lambda_http--012) note above.

If you see `FunctionError: Unhandled` in the invoke output: the Lambda panicked at startup (most likely `spatial_index.sis` is missing from the zip bundle or the `.sis` file is incompatible with the binary — rebuild with `make sis/deploy env=dev`).

### 2. API Gateway direct call

Tests the Lambda through API Gateway with the API key, bypassing CloudFront. Reads the key from SSM so it is never stored in shell history.

```sh
API_GW_ID=$(aws apigateway get-rest-apis \
  --query "items[?name=='beststartinlife-dev-api'].id" --output text)

API_KEY=$(aws ssm get-parameter \
  --name "/beststartinlife/dev/api-key" \
  --with-decryption --query "Parameter.Value" --output text)

curl -si \
  "https://$API_GW_ID.execute-api.eu-west-2.amazonaws.com/dev/api/spatial-query\
?pc_south=51.4&pc_west=-0.2&pc_north=51.6&pc_east=0.1\
&pc_lat=51.5&pc_lon=-0.05\
&map_south=51.4&map_west=-0.2&map_north=51.6&map_east=0.1&ct=0" \
  -H "x-api-key: $API_KEY" --max-time 15 | head -6
```

**Expected:** `HTTP/2 200`, `content-type: application/octet-stream`.

`HTTP/2 403` with `{"message":"Forbidden"}`: the API key is wrong or not linked to the usage plan. Check `make tg/apply env=dev module=compute` was re-run after any Terraform changes.

`HTTP/2 404` with empty body: Lambda routing issue — see step 1.

### 3. CloudFront end-to-end

Tests the full production path, including the `inject_api_key` CloudFront Function and the `/api/*` cache behaviour.

```sh
curl -si \
  "https://bsil.10ds.cabinetoffice.gov.uk/api/spatial-query\
?pc_south=51.4&pc_west=-0.2&pc_north=51.6&pc_east=0.1\
&pc_lat=51.5&pc_lon=-0.05\
&map_south=51.4&map_west=-0.2&map_north=51.6&map_east=0.1&ct=0" \
  -u "$(aws ssm get-parameter --name /beststartinlife/dev/basic-auth/user --with-decryption --query Parameter.Value --output text):$(aws ssm get-parameter --name /beststartinlife/dev/basic-auth/pass --with-decryption --query Parameter.Value --output text)" \
  --max-time 15 | head -8
```

**Expected:** `HTTP/2 200`, `content-type: application/octet-stream`, `server` header absent (CloudFront does not forward it).

`HTTP/2 200` with `content-type: text/html` and `server: AmazonS3`: the request fell through to S3. The `/api/*` cache behaviour is missing — re-apply the CDN: `make tg/apply env=dev module=cdn`. Also check `x-cache: Error from cloudfront` in the response, which means CloudFront received an error from API Gateway and served the SPA error page instead.

### 4. CloudWatch Logs

Lambda logs are in `/aws/lambda/beststartinlife-<env>-spatial-index`. Tail them while running the tests above:

```sh
aws logs tail /aws/lambda/beststartinlife-dev-spatial-index --since 10m --format short --follow
```

A healthy cold start looks like:

```
INIT_START Runtime Version: provided:al2023.vX ...
INFO sis_query: Loading SIS store filepath=spatial_index.sis
INFO spatial_index_service::query: SIS store loaded providers=83681 rows=84720 aabbs=76143
START RequestId: ...
END RequestId: ...
REPORT ... Duration: 20ms ... Init Duration: 70ms
```

Subsequent warm requests should show `Duration: 1–5 ms` with no intermediate log lines (the query handler has no instrumentation at INFO level by default).

If `SIS store loaded` never appears the Lambda is still running the placeholder `bootstrap` stub — deploy the real binary with `make sis/deploy env=<env>`.

### Failure mode summary

| Symptom                                                           | Root cause                                                                   | Fix                                                          |
| ----------------------------------------------------------------- | ---------------------------------------------------------------------------- | ------------------------------------------------------------ |
| `FunctionError: Unhandled` on invoke                              | Placeholder bootstrap, missing `.sis`, or incompatible rkyv version          | `make sis/deploy env=<env>`                                  |
| Lambda returns `404`, empty body                                  | `lambda_http` stage-prefix routes missing from `build_router`                | Add `/:stage/*` routes; redeploy                             |
| API Gateway `403 Forbidden`                                       | API key not injected or wrong value                                          | `make tg/apply env=<env> module=cdn` to re-bake key from SSM |
| CloudFront returns `text/html` from S3                            | `/api/*` cache behaviour missing from distribution                           | `make tg/apply env=<env> module=cdn`                         |
| CloudFront returns `text/html` + `x-cache: Error from cloudfront` | Lambda returning 4xx/5xx, converted to SPA fallback by custom error response | Diagnose with steps 1–2 above                                |
