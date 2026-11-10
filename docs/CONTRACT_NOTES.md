# Contract notes (non-normative)

`contract/CONTRACT.md` is frozen. This file explains how the contract maps to the code and how
ambiguous points are implemented. If a note here conflicts with the contract, the contract wins:
open an entry in `contract/CHANGE_REQUESTS.md`.

## Where each contract piece lives

| Contract section | Code |
|---|---|
| Shared types (Source, Event, PolitySummary, ...) | `src/atlas_api/schemas/` (`common`, `polities`, `countries`, `snapshots`, `system`, `search`) |
| Endpoints | `src/atlas_api/routers/<resource>.py`, mounted under `/v1` in `main.py` |
| Errors (problem+json, 404/422) | `src/atlas_api/errors.py` |
| CORS_ORIGINS | `src/atlas_api/config.py` (`Settings.cors_origins`) |
| Seed ids | `src/atlas_api/fixtures/data/*.json` (Phase 0), `content/` (Phase 1) |
| Caching headers, ETag, X-Data-Version | Phase 4 (not implemented yet) |

## Implementation choices on ambiguous points

- `year` bounds: values outside `meta.year_min..year_max` return 422 (the contract says 422 for
  invalid parameter and 404 for unknown id/year; "unknown year" is read as: exact snapshot year
  missing in `/snapshots/{year}/links` -> 404).
- `CountrySummary.has_content` = the country has a summary or at least one event.
- `CountryDetail.population.year` is always null for now: REST Countries gives no population year.
- `Language.code` is the BCP-47 code from REST Countries; `memberships` lists the names of the
  organisations whose flag is true (`un`, `nato`, ...), sorted.
- Fixture values (Phase 0) are placeholders, not curated history.
