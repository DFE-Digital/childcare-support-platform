# @bsil/app

Public-facing React SPA for beststartinlife.gov.uk. Provides a childcare provider search (map + list), eligibility checker, and cost calculator.

## Stack

React 19, Vite, Tailwind CSS, MapLibre GL, React Router

## Key directories

| Directory         | Contents                                                                 |
| ----------------- | ------------------------------------------------------------------------ |
| `src/pages/`      | Route pages: Home, ProviderSearch, SupportForm/Results, CostForm/Results |
| `src/components/` | Reusable UI components                                                   |
| `src/hooks/`      | Custom React hooks                                                       |
| `src/context/`    | React context providers                                                  |
| `src/lib/`        | SIS binary protocol client                                               |
| `src/data/`       | Static JSON data                                                         |
| `src/utils/`      | Utility functions                                                        |
| `src/types/`      | TypeScript type definitions                                              |

## Dependencies

- **`@bsil/calculator`** (workspace dependency) for entitlement eligibility and cost calculations
- The SIS binary protocol is documented in [`packages/spatial-index-service/README.md`](../spatial-index-service/README.md)

## Development

```bash
make app/up       # Docker Compose: Vite dev server on :5173 + SIS on :3001
npm run dev -w @bsil/app   # Vite alone (no SIS)
```

## Build

```bash
npm run build -w @bsil/app   # static files in dist/
```

## Test

```bash
make app/test                # or: npm test -w @bsil/app
```

Vitest + jsdom + React Testing Library.
