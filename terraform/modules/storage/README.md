# Module: storage

Creates two private S3 buckets (provider-data, vite-build-outputs) with versioning, SSE-S3 encryption, and public-access blocking. Creates a CloudFront Origin Access Control (OAC) for each bucket, used by the [cdn](../cdn/) module.

## Resources

| Resource | Name pattern | Notes |
|---|---|---|
| `aws_s3_bucket` (×2) | `{project}-{env}-provider-data` | Provider JSON, postcodes, tiles, sis_schema — served at `/data/*` |
| | `{project}-{env}-vite-build-outputs` | React SPA build — served at `/` |
| `aws_s3_bucket_versioning` (×2) | - | Enabled on all buckets |
| `aws_s3_bucket_server_side_encryption_configuration` (×2) | - | AES256 / SSE-S3 |
| `aws_s3_bucket_public_access_block` (×2) | - | All four block flags enabled |
| `aws_cloudfront_origin_access_control` | `{project}-{env}-vite-oac` | OAC for vite-build-outputs |
| `aws_cloudfront_origin_access_control` | `{project}-{env}-provider-data-oac` | OAC for provider-data |
| `aws_s3_bucket_policy` (×2, conditional) | - | Only created when `cloudfront_distribution_arns` is non-empty |

## What goes in each bucket

### `provider-data`

Populated by the deploy GitHub Action (which syncs from the `source-data` bucket). Files are stored under a `data/` prefix to match the `/data/*` CloudFront path pattern:

```
data/
├── providers/           # provider JSON files (as providers.tar.gz)
├── inward/              # postcode inward lookup files (as inward.tar.gz)
├── outward.json
├── spatial_index.parquet
├── sis_schema.json
└── tiles/
    └── providers.pmtiles
```

### `vite-build-outputs`

Populated by `make frontend/deploy env=<env>`. Contains the Vite React SPA build artifacts served from `/`.

## Inputs

| Name | Type | Default | Description |
|---|---|---|---|
| `project` | `string` | - | Project name used in bucket names and tags |
| `environment` | `string` | - | Environment name (`dev`, `preprod`, `prod`) |
| `cloudfront_distribution_arns` | `list(string)` | `[]` | ARNs of all CloudFront distributions allowed to read from the S3 buckets. Leave empty on first apply; add each distribution ARN after its cdn module is deployed. |

## Outputs

| Name | Description |
|---|---|
| `provider_data_bucket_id` | ID (name) of the `provider-data` bucket |
| `provider_data_bucket_arn` | ARN of the `provider-data` bucket |
| `provider_data_oac_id` | OAC ID for the provider-data bucket (pass to [cdn](../cdn/)) |
| `vite_bucket_id` | ID (name) of the `vite-build-outputs` bucket |
| `vite_bucket_arn` | ARN of the `vite-build-outputs` bucket |
| `oac_id` | OAC ID for the vite-build-outputs bucket (pass to [cdn](../cdn/)) |

## Two-pass deployment

There is a circular dependency between `storage` (which holds the OAC resources) and `cdn` (which provides the distribution ARN needed for the bucket policies). This is resolved with a two-pass apply:

```
Pass 1:  apply storage  (cloudfront_distribution_arns = [])    → no bucket policies created
         apply cdn                                             → outputs distribution ARN
Pass 2:  apply storage  (cloudfront_distribution_arns = [ARN]) → bucket policies created for both buckets
```

The `cloudfront_distribution_arns` list is set directly in [live/{env}/storage/terragrunt.hcl](../../live/dev/storage/terragrunt.hcl) — a Terragrunt dependency block is intentionally omitted to avoid a cycle.

Each time a new cdn module is deployed (e.g. `cdn-childcare`), add its ARN to the list and re-apply storage:

```
make tg/output env=prod module=cdn-childcare   # → note cloudfront_distribution_arn
# add ARN to cloudfront_distribution_arns in live/prod/storage/terragrunt.hcl
make tg/apply env=prod module=storage
```

## Used by

- [cdn](../cdn/) — `vite_bucket_id`, `vite_bucket_arn`, `oac_id`, `provider_data_bucket_id`, `provider_data_oac_id`
