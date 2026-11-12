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
| Seed ids | `content/polities/*.yaml` (loaded by `import-content`) |
| Caching headers, ETag, X-Data-Version | Phase 4 (not implemented yet) |

## Implementation choices on ambiguous points

- `year` bounds: values outside `meta.year_min..year_max` return 422 (the contract says 422 for
  invalid parameter and 404 for unknown id/year; "unknown year" is read as: exact snapshot year
  missing in `/snapshots/{year}/links` -> 404).
- `CountrySummary.has_content` = the country has a summary or at least one event.
- `CountryDetail.population.year` is always null for now: REST Countries gives no population year.
- `Language.code` is the BCP-47 code from REST Countries; `memberships` lists the names of the
  organisations whose flag is true (`un`, `nato`, ...), sorted.
- `SearchItem.id` is the polity id for both kinds; for `kind: country` use `iso2` to call `/countries/{iso2}`.
- `Language`/`Currency` entries without a code (dialects, language groups) are omitted: the contract requires a code and we never invent one.
- `/snapshots*` are empty (404 for nearest/links) until the Phase 3 import.
- `CountryDetail.population.source_id` is `wikidata`; `flag_url` points to flagcdn.com (public-domain flags).

## v1.1 (CR-002 proposal, implemented locally, NOT in CONTRACT.md yet)

| Piece | Code / data |
|---|---|
| `capital_coords` (005) | v1.2/019: every current capital from the `capitals` table (was: one item from `country_facts`) |
| `regime_id`, `regime` (004) | Wikidata P122 -> `content/regimes.yaml` rules (ETL `etl/wikidata/pipeline.py`) -> `country_facts.regime_id/regime` (migration 0003) |
| `GlossaryTerm`, `/v1/glossary*` (004) | `content/glossary.yaml` -> `glossary_terms` (import-content); `routers/glossary.py`; `queries.list_glossary` |
| `clues` (003) | Wikidata P1622/P474/P78/P395, P37->P282 -> `country_facts` clue columns (migration 0004) |
| `Leader`, `/countries/{iso2}/leaders` (006) | `python -m etl wikidata-leaders` -> `data_out/leaders.json` -> `leaders` (import-facts, migration 0005) |
| `Person`, `/countries/{iso2}/people` (007) | `python -m etl pantheon` -> `data_out/pantheon.json` -> `people` + `meta.people_method` (import-facts, migration 0006) |

Order to load: `alembic upgrade head`, `import-content` (glossary first: `regime_id` is a FK), then `import-facts`
(reads `wikidata.json` and, when present, `leaders.json` and `pantheon.json`).

Implementation choices:
- `regime`: Wikidata label wins whenever `regime_id` is set (user decision 2026-11-11: overrides the unverified seed); else the old `polities.regime`.
- `regimes.yaml`: first rule whose Q-ids are all present wins; explicit `regime_id: null` rules for contradictory
  Wikidata sets (AE: constitutional + absolute; GE/TN: semi + presidential). Q179164 "Estado unitário" etc. are
  ignored (structure, not form of government) and listed by the ETL as "unmapped".
- Scalar clues: preferred rank, else the single normal value; several = null (logged). TLD only: a single
  2-letter ASCII ccTLD beats IDN/brand TLDs (`.jp` over `.日本`). Wikidata left-hand traffic is Q11920728
  (spec 003 said Q13196750, which does not exist).
- `scripts`: ancestors (P279/P282) of the official languages' P282 values that have an ISO 15924 code;
  Braille, Deseret, Shavian and composite codes (Jpan, Hrkt, Kore) dropped.
- Glossary `examples`: regime = same `regime_id`; region = `region` contains the label (split on " / ");
  membership = in `memberships`; max 8, by country name. Glossary sources are stored inline (JSONB), not in `sources`.
- Leaders: same office for both roles -> one `head_of_state` item. Party = the P102 statement valid at the term
  start, one candidate only. Photo only when Commons gives LicenseShortName AND Artist, and the person has one P18.
- People: Pantheon `bplace_country` (English) matched to ISO2 via Wikidata English labels/aliases + `NAME_FIXES`.
  `/people` answers 503 if the Pantheon file was never imported (so "no data" is not confused with "no people").
- ETag: fixed in v1.2 / spec 019 (import-facts now changes `data_version`, see below).

## v1.2 part A (CR-003 proposal, implemented locally, NOT in CONTRACT.md yet)

| Piece | Code / data |
|---|---|
| ETag after import-facts (019) | `importer.set_version`: `data_version` = hash(`meta.content_version` + `meta.facts_version`); import-facts hashes the bytes of every `data_out/*.json` it read |
| Denmark (019) | `etl/wikidata/pipeline.py` `STATE` adds Q35 (ISO DK) + memberships from Q756617; `content/polities/dinamarca.yaml` |
| several capitals (019) | ETL `capitals` list -> `capitals` table (migration 0007) -> `CountrySummary.capital_coords` (all with coordinates) |
| image bucket (019) | `etl/wikidata/leaders.mirror_images` (leaders + Pantheon), only with `IMAGE_BUCKET_URL` + `SUPABASE_SERVICE_KEY` |
| `languages_spoken` (017) | `python -m etl wikidata-languages` -> `data_out/languages.json` -> `country_languages` (migration 0008); `content/language_families.yaml` |
| `/countries/{iso2}/profile` (015) | `etl worldbank` + `etl undp` -> `indicators`, `indicator_defs`, `indicator_stats`, `indicator_latest`; Wikidata P140/P172 + P1107 -> `compositions` (migration 0009) |
| `/countries/{iso2}/economy`, `/economy/compare` (009) | same `indicators` table; `queries.ECONOMY_IDS` |
| `/currencies/{code}`, `/history` (009) | `python -m etl fx` -> `data_out/fx.json` -> `fx_rates` + `currency_stats` (migration 0010); cross rates in SQL (self-join on date) |

Load order unchanged: `alembic upgrade head`, `import-content`, `import-facts` (now also reads `languages.json`,
`worldbank.json`, `undp.json`, `fx.json` when present). ETL order: `wikidata` -> `wikidata-leaders`, `pantheon`,
`wikidata-languages`, `worldbank` -> `undp` (needs worldbank's ISO3 map), `fx`.

Implementation choices:
- Profile/economy: the API only knows which ids belong to which group (`queries.PROFILE_GROUPS`, `ECONOMY_IDS`);
  labels/units are rows of `indicator_defs` written by the ETL. Rank/world/regional stats are computed at import
  over each country's latest value (`indicator_latest`, `indicator_stats`), never at request time.
- `composition.year`: the most recent `year` among the listed shares (religion and ethnicity may differ).
- Currency `name`/`symbol` come from the countries' Wikidata P38 (`country_facts.currencies`); a code no country uses
  is 404 even if it has rates (legacy ECB codes such as GRD).
