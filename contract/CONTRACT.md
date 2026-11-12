# Atlas API contract v1 (FROZEN)
Version: 1.1 (additive over 1.0: a 1.0 client ignores the new fields and endpoints; approved by the owner 2026-11-11, CR-002)

Status: FROZEN. Neither the API agent nor the web agent may edit this file.
If you find a problem, stop, describe it in `contract/CHANGE_REQUESTS.md`
(what, why, proposed fix) and tell the user. Do not work around it silently.

## Conventions
- Base path `/v1`. JSON, UTF-8. Read-only (GET) in v1. No auth.
- Content language: pt-BR only in v1.
- Years are signed integers with NO year 0: 1 BCE = -1, 1 CE = 1. Display -300 as "300 a.C.".
- `Precision` = "exact" | "circa" | "decade" | "century". Used wherever a year can be uncertain.
- Timestamps: ISO 8601 UTC. `null` = unknown or not applicable. Never invent values.
- Polity ids: lowercase-hyphen slugs (`ottoman-empire`). Country codes: ISO 3166-1 alpha-2, uppercase. `XK` = Kosovo (unofficial code, documented limitation).
- Errors: `application/problem+json` { type, title, status, detail }. 404 unknown id/year, 422 invalid parameter.
- Every response (except /v1/health) carries `X-Data-Version` and `ETag`, plus
  `Cache-Control: public, max-age=300, stale-while-revalidate=86400`. `If-None-Match` matching -> 304.
- CORS origins come from env `CORS_ORIGINS` (comma-separated).
- Geometry is NOT served by the API. `geometry_url` values are paths relative to the web app origin.
  Modern geometry: `/data/modern.geojson`, feature property `ISO2`.
  Historical geometry: `/data/historical/world_<year>.geojson`, feature properties
  `NAME`, `SUBJECTO`, `PARTOF`, `BORDERPRECISION` (1 approximate, 2 moderate, 3 by international law).

- Content language: pt-BR, except data quoted from a source that has no pt-BR version: `Person.name` and
  `Person.occupation` (Pantheon, English, occupation in UPPER CASE as published). `Leader.office/name/party.name`
  are Wikidata labels in pt-BR, else pt, else en.
- Images (`image`) are thumbnails hosted by Wikimedia Commons. Each file has its own licence: the front MUST show
  `image.credit` and `image.license` next to the picture. `image` is null when the file has no clear licence + author.
- v1.1: `regime` is the pt-BR label of `regime_id` when `regime_id` is non-null (source: Wikidata P122); otherwise the
  old curated text, which may be null.

## Shared types
Source      { id: string, title: string, url: string|null, license: string|null, retrieved_at: string|null }
Event       { id: string, year_start: int, year_end: int|null, precision: Precision, title: string, summary: string,
              kind: "political"|"war"|"treaty"|"cultural"|"economic"|"other", source_ids: string[] }
PolitySummary { id: string, name: string, type: "empire"|"kingdom"|"republic"|"federation"|"confederation"|"colony"|"protectorate"|"city_state"|"other",
              start_year: int, end_year: int|null, iso2: string|null }
Link        { polity_id: string, name: string, year: int,
              kind: "renamed"|"succeeded"|"split"|"merged"|"absorbed"|"conquered" }
PolityDetail = PolitySummary + { start_precision: Precision, end_precision: Precision|null,
              names: [{ name: string, from_year: int, to_year: int|null }],
              predecessors: Link[], successors: Link[], regime: string|null, summary: string|null,
              politics: { system: string|null, note: string|null, updated_at: string|null }|null,
              timeline: Event[], wikipedia: { title: string, url: string }|null, sources: Source[], updated_at: string }
CountrySummary { iso2: string, polity_id: string, name: string, capital: string|null, region: string|null,
              regime: string|null, has_content: bool, marker: { lat: number, lng: number }|null }
              (`marker` is non-null only for micro-states too small to see on the globe)
CountryDetail { iso2: string, polity_id: string, name: string, official_name: string|null, capital: string|null,
              flag_url: string|null, region: string|null, regime: string|null, summary: string|null,
              languages: [{ code: string, name: string }], currencies: [{ code: string, name: string, symbol: string|null }],
              population: { value: int, year: int|null, source_id: string }|null, area_km2: number|null,
              memberships: string[], politics: { system: string|null, note: string|null, updated_at: string|null }|null,
              timeline: Event[], sources: Source[], updated_at: string }
SnapshotInfo { year: int, geometry_url: string, feature_count: int, link_coverage: number /* 0..1 */ }

Image        { url: string, credit: string, license: string }
GlossaryTerm { id: string, kind: "regime"|"system"|"region"|"membership"|"currency"|"other", label: string,
               short: string, body: string, icon: string|null, examples: string[] /* iso2, max 8, by country name */,
               sources: Source[] }
Leader       { person_id: string /* Wikidata Q-id */, name: string, role: "head_of_state"|"head_of_government",
               office: string|null, start: string|null, end: string|null /* "YYYY-MM-DD"; end null = in office or unknown */,
               party: { id: string, name: string }|null, image: Image|null, wikipedia_url: string|null }
               (one item per term of office; when one office is both head of state and of government, e.g. a
               presidential system, it appears once as "head_of_state")
Person       { id: string /* Wikidata Q-id */, name: string, occupation: string|null,
               domain: "arts"|"business_law"|"exploration"|"humanities"|"institutions"|"public_figure"|"science_technology"|"sports"|null,
               birth_year: int|null, death_year: int|null, image: Image|null, wikipedia_url: string|null,
               rank: int /* 1 = most popular in the country */ }
v1.1 fields appended to existing types:
CountrySummary += { regime_id: string|null /* GlossaryTerm id, kind "regime" */,
                    capital_coords: [{ name: string, lat: number, lng: number }] /* [] = unknown */ }
CountryDetail  += { regime_id: string|null,
                    clues: { driving_side: "left"|"right"|null, calling_code: string|null /* "+55" */,
                             tld: string|null /* ".br" */, plate_code: string|null /* "BR" */,
                             scripts: string[] /* pt-BR names of the writing systems of the official languages */ }|null }
                    (`clues` is null when none of its fields has data)

## Endpoints
GET /v1/health                       -> { status: "ok", db: "ok"|"error" }
GET /v1/meta                         -> { data_version: string, generated_at: string, year_min: int, year_max: int,
                                          snapshot_years: int[], counts: { countries: int, polities: int, events: int } }
GET /v1/countries                    -> { items: CountrySummary[] }                 (all modern countries known to the API)
GET /v1/countries/{iso2}             -> CountryDetail                               (iso2 matches ^[A-Z]{2}$)
GET /v1/polities?year=&limit=&offset=-> { year: int|null, items: PolitySummary[], total: int }
                                        `year` optional. With `year`: only polities existing that year, `name` = name as of that year.
                                        limit default 500, max 1000.
GET /v1/polities/{id}                -> PolityDetail
GET /v1/snapshots                    -> { items: SnapshotInfo[] }
GET /v1/snapshots/nearest?year=      -> { requested_year: int, snapshot: SnapshotInfo, distance_years: int }
GET /v1/snapshots/{year}/links       -> { snapshot_year: int,
                                          links: [{ source_name: string, polity_id: string|null,
                                                    status: "curated"|"auto"|"unresolved" }] }
                                        `year` must be an exact snapshot year, else 404.
GET /v1/search?q=&limit=             -> { items: [{ kind: "country"|"polity", id: string, name: string, iso2: string|null,
                                                    start_year: int, end_year: int|null }] }
                                        q min 2 chars, accent-insensitive, prefix and substring match. limit default 10, max 25.

GET /v1/glossary                      -> { items: GlossaryTerm[] }                  (sorted by kind, then label)
GET /v1/glossary/{id}                 -> GlossaryTerm                               (404 unknown id)
GET /v1/countries/{iso2}/leaders?role=-> { items: Leader[] }
                                        `role` optional ("head_of_state"|"head_of_government", else 422).
                                        Sorted by start (unknown start last). 404 unknown country; [] = no data.
GET /v1/countries/{iso2}/people?domain=&limit=
                                     -> { items: Person[], method: string /* pt-BR, how the ranking is made + known bias */,
                                          source: Source }
                                        `domain` optional (values of Person.domain, else 422). limit default 10, max 50.
                                        Sorted by rank. 404 unknown country. Source licence is CC BY-SA 4.0 (Pantheon):
                                        the front must show the attribution in `source`.

## Seed ids (must exist, same ids in both agents' fixtures)
Modern: austria (AT), brazil (BR), germany (DE), egypt (EG), japan (JP), turkey (TR), russia (RU), serbia (RS)
Historical: ottoman-empire, austria-hungary, german-empire, weimar-republic, nazi-germany, east-germany, soviet-union, yugoslavia
