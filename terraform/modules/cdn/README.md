# Module: cdn

Creates a CloudFront distribution serving the frontend from two S3 origins:

- **`/` (default)** — React SPA from `vite-build-outputs` via OAC
- **`/data/*`** — Provider JSON, postcodes, tiles, and SIS schema from `provider-data` via OAC

Attaches the global WAFv2 WebACL from the [security](../security/) module. Optionally adds HTTP basic auth via Lambda@Edge.

## Resources

| Resource | Notes |
|---|---|
| `aws_cloudfront_distribution` | Two S3 origins, WAF attached, SPA error handling |
| `aws_lambda_function` (conditional) | Lambda@Edge basic auth — only when `basic_auth_enabled = true` |
| `aws_iam_role` (conditional) | Execution role for Lambda@Edge |
| `aws_route53_record` (conditional) | A alias record for custom domain — only when `domain_name` is set |

## Distribution configuration

- **Default origin** — `vite-build-outputs` bucket via OAC (SigV4 signed)
- **Default root object** — `index.html`
- **`/data/*` origin** — `provider-data` bucket via OAC (SigV4 signed)
- **Viewer protocol policy** — `redirect-to-https` on all behaviours
- **Allowed methods** — `GET`, `HEAD` only
- **Price class** — `PriceClass_100` (EU + North America)
- **SPA routing** — 403 and 404 responses from S3 are rewritten to `200 /index.html` so the client-side router handles all paths

## URL structure

| Path | Served from |
|---|---|
| `/` | `vite-build-outputs/index.html` |
| `/providers`, `/support`, etc. | `vite-build-outputs/index.html` (SPA routing) |
| `/data/providers/*.json` | `provider-data/data/providers/` |
| `/data/outward.json` | `provider-data/data/outward.json` |
| `/data/inward/*.json` | `provider-data/data/inward/` |
| `/data/sis_schema.json` | `provider-data/data/sis_schema.json` |
| `/data/tiles/providers.pmtiles` | `provider-data/data/tiles/providers.pmtiles` |
| `/api/spatial-query` | API Gateway → Lambda (not in this module) |

## Cache strategy

Three asset classes with different caching needs:

| Asset class | S3 `Cache-Control` | CloudFront TTL | Browser behaviour | Why |
|---|---|---|---|---|
| **Vite hashed assets** (`/assets/*`) | `max-age=31536000, immutable` | Respects S3 header (1 year) | Cached indefinitely | Filenames contain content hashes — a new build produces new URLs, so stale cache entries are never requested |
| **`index.html`** | `no-cache, no-store, must-revalidate` | Respects S3 header (always revalidate) | Always fetches fresh | SPA entry point — must always resolve to the latest build so that `<script>` tags point to current hashed assets |
| **`/data/*`** (provider JSON, postcodes, tiles, SIS schema) | `no-cache` | `default_ttl=60`, `max_ttl=300` | Always revalidates with origin | Mutable files at stable URLs — updated on each data pipeline run. `no-cache` forces browser revalidation; short edge TTL limits stale window between deploys |
| **`/api/*`** | N/A (Lambda origin) | `TTL=0` (pass-through) | Not cached | Dynamic spatial queries — every request hits Lambda |

### How invalidation works

`make cdn/invalidate` creates a CloudFront invalidation for `/data/*`, clearing the edge cache. This is called automatically by both `cdn/push-provider-data` and `prod/deploy-bsil` after uploading new data to S3.

Invalidation only affects the **CloudFront edge cache** — it cannot clear data already stored in a user's browser cache. This is why the S3 `Cache-Control` header matters:

- `no-cache` tells browsers to revalidate with the server on every request (CloudFront responds with `304 Not Modified` when the data hasn't changed, so this is efficient)
- Without a `Cache-Control` header, browsers fall back to heuristic caching and may serve stale data even after a CloudFront invalidation
- `max-age=31536000, immutable` is safe for Vite assets because the content hash in the filename guarantees the URL changes when the content changes — old URLs are simply never requested again

### Deploy sequence

`prod/deploy-bsil` runs in this order:

1. `sis/preprocess` — build spatial index
2. `cdn/push-provider-data-no-invalidate` — sync data to S3 (with `Cache-Control: no-cache`)
3. `frontend/upload` — sync Vite build to S3 (hashed assets immutable, `index.html` no-cache)
4. `sis/deploy` — update Lambda
5. `cdn/invalidate` + `frontend/invalidate` — clear edge caches for both distributions

Invalidation runs **last** so that both S3 origins have the new content before the edge cache is cleared. If invalidation ran before the upload completed, a cache miss during the window could re-cache the old data.

### Frontend dependency on `index.html` caching

The React app includes a deploy-freshness mechanism (`src/hooks/useDeployFreshness.ts`) that detects new deploys by periodically fetching `index.html` and comparing its ETag to a baseline captured at page load. When the ETag changes, the app auto-reloads to pick up new code and data.

This depends on two properties of the infrastructure:

1. **`index.html` must always revalidate** — the `no-cache, no-store, must-revalidate` Cache-Control header ensures that each fetch hits CloudFront (which revalidates against S3). If this were changed to a long `max-age`, the freshness check would never see a new ETag, and users on stale tabs would never reload.

2. **CloudFront must forward S3 ETags** — the default cache behavior uses `forwarded_values` (not a managed cache policy), which preserves ETags from S3. If this were migrated to a managed cache policy that strips ETags, the hook would fall back to comparing the full HTML body — still functional but less efficient.

Changing either of these behaviours will break the auto-reload mechanism. See the hook's source for full documentation.

## Inputs

| Name | Type | Default | Description |
|---|---|---|---|
| `project` | `string` | - | Project name used in tags |
| `environment` | `string` | - | Environment name (`dev`, `preprod`, `prod`) |
| `vite_bucket_id` | `string` | - | S3 bucket name from [storage](../storage/) |
| `vite_bucket_arn` | `string` | - | S3 bucket ARN from [storage](../storage/) |
| `oac_id` | `string` | - | OAC ID for vite-build-outputs from [storage](../storage/) |
| `provider_data_bucket_id` | `string` | - | S3 bucket name from [storage](../storage/) |
| `provider_data_oac_id` | `string` | - | OAC ID for provider-data from [storage](../storage/) |
| `waf_cloudfront_arn` | `string` | - | us-east-1 WAF ARN from [security](../security/) |
| `price_class` | `string` | `"PriceClass_100"` | CloudFront price class |
| `domain_name` | `string` | `""` | Custom domain (e.g. `bsil.10ds.cabinetoffice.gov.uk`) |
| `certificate_arn` | `string` | `""` | ACM certificate ARN in us-east-1 — required when `domain_name` is set |
| `route53_zone_id` | `string` | `""` | Route53 hosted zone ID — required when `domain_name` is set |
| `basic_auth_enabled` | `bool` | `false` | Enable Lambda@Edge basic auth |
| `basic_auth_ssm_user_param` | `string` | `""` | SSM path for basic auth username (us-east-1 SecureString) |
| `basic_auth_ssm_pass_param` | `string` | `""` | SSM path for basic auth password (us-east-1 SecureString) |
| `api_gateway_id` | `string` | `""` | REST API ID of the API Gateway to expose at `/api/*`. Leave empty to skip. |
| `api_gateway_stage` | `string` | `""` | API Gateway stage name (e.g. `prod`). |
| `api_key_ssm_param` | `string` | `""` | SSM SecureString path for the API Gateway key. Required when `api_gateway_id` is set. |
| `name_suffix` | `string` | `""` | Optional suffix appended to CloudFront Function names to disambiguate multiple distributions in the same environment (e.g. `childcare`). |

## Outputs

| Name | Description |
|---|---|
| `cloudfront_domain` | Distribution domain name (e.g. `d1234.cloudfront.net`) |
| `cloudfront_distribution_id` | Distribution ID |
| `cloudfront_distribution_arn` | Distribution ARN — feed back into [storage](../storage/) to activate OAC bucket policies |

## Dependencies

| Input | Source module |
|---|---|
| `vite_bucket_id`, `vite_bucket_arn`, `oac_id`, `provider_data_bucket_id`, `provider_data_oac_id` | [storage](../storage/) |
| `waf_cloudfront_arn` | [security](../security/) |
| `certificate_arn` | [dns](../dns/) |
| `route53_zone_id` | [dns](../dns/) |

## After apply

Pass `cloudfront_distribution_arn` back into the [storage](../storage/) module to create the bucket policies that restrict S3 access to this distribution only. See [storage README](../storage/README.md#two-pass-deployment).
