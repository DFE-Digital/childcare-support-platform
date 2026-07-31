# @bsil/calculator

Entitlement eligibility and childcare cost calculation engine. Pure TypeScript library with no framework or runtime dependencies.

## Exports

| Directory          | Contents                                         |
| ------------------ | ------------------------------------------------ |
| `src/types/`       | Family, scheme, and entitlement type definitions |
| `src/validators/`  | Zod-like validation for household data           |
| `src/entitlement/` | Scheme eligibility rules                         |
| `src/costs/`       | Cost calculation per provider and care type      |

## Consumed by

`@bsil/app` as a workspace dependency.

## Build

```bash
npm run build -w @bsil/calculator   # outputs to dist/
```

## Test

```bash
make calculator/test   # or: npm test -w @bsil/calculator
```

~430 tests using Vitest. Test fixtures live in `src/__fixtures__/families/` (family scenario JSON files used by entitlement and cost tests).
