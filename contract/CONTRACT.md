# Atlas API contract v1 (FROZEN)
Version: 1.2 (additive over 1.1; part A = CR-003: languages_spoken, profile, economy, currencies; approved by the owner 2026-11-12)

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
- Images (`image`) are 320px thumbnails of Wikimedia Commons files, served either by Commons or by the Atlas public
  storage bucket (a copy of the same thumbnail). Each file has its own licence: the front MUST show `image.credit`
  and `image.license` next to the picture. `image` is null when the file has no clear licence + author.
- v1.1: `regime` is the pt-BR label of `regime_id` when `regime_id` is non-null (source: Wikidata P122); otherwise the
  old curated text, which may be null.

- v1.2 numbers: `share` values are fractions 0-1 (0.65 = 65%). Currency `change_1y`, `change_5y` and
  `max_drawdown_1y` are fractions too (-0.12 = -12%); `volatility_1y` is the annualised standard deviation of the
  log returns of the last year (0.15 = 15%).
- Indicators (`id`) are World Bank WDI codes (e.g. "SP.DYN.LE00.IN") or "HDR.HDI" / "HDR.MYS" (UNDP Human
  Development Report). `label` and `unit` are pt-BR. `value` is the latest year with data for that country
  (`year`); years differ between countries and indicators. `rank` 1 = HIGHEST value among the `rank_of` countries
  that have the indicator (also for "bad" indicators such as homicides: the front decides how to read it).
  `world` = min/median/max of every country's latest value; `region_avg` = simple mean of the latest values of
  the countries with the same `region` string.
- Exchange rates: ECB euro reference rates (daily, since 1999) and, for currencies the ECB does not publish,
  fawazahmed0/exchange-api (secondary source, WEEKLY points, since 2024-03). Cross rates and statistics are
  calculated by Atlas from EUR quotes (A->B = EUR->B / EUR->A). Currency `stats` measure the value of 1 unit of
  the currency in USD (in EUR for USD itself), as of the last date with data. The front must cite the sources
  listed in `sources` / `source`.

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

LanguageSpoken { code: string|null /* ISO 639-1, else IETF tag, else ISO 639-3 */, name: string,
                 status: "official"|"co_official"|"indigenous"|"immigrant"|"sign"|"historical",
                 where: string|null /* co_official only: subdivisions or municipalities, "A, B, C e mais N" */,
                 speakers: { value: int, year: int|null }|null /* only when the source ties the count to this country */,
                 family: string|null /* pt-BR, from a curated list of established families */,
                 endangerment: "segura"|"vulnerável"|"definitivamente em perigo"|"severamente em perigo"|
                               "criticamente em perigo"|"extinta"|null /* UNESCO scale */,
                 wikipedia_url: string|null }
ProfileIndicator { id: string, label: string, unit: string, value: number, year: int, source_id: string,
                   rank: int|null, rank_of: int|null, world: { min: number, median: number, max: number }|null,
                   region_avg: number|null }
v1.2 fields appended to existing types:
CountryDetail += { languages_spoken: LanguageSpoken[] }
                  Sorted by status in the order official, co_official, indigenous, immigrant, sign, historical, then by
                  speakers desc (unknown last), then name. [] = no data. `languages` (v1.0) is unchanged.

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

GET /v1/countries/{iso2}/profile     -> { groups: [{ id: "life"|"society"|"income"|"environment", indicators: ProfileIndicator[] }],
                                          composition: { religion: [{ label: string, share: number }]|null,
                                                         ethnicity: [{ label: string, share: number }]|null,
                                                         year: int|null, source_id: string|null },
                                          sources: Source[] }
                                        Always the 4 groups, in this order; an indicator without data for the country is
                                        left out of its group. Indicators: life = SP.DYN.LE00.IN, SP.DYN.IMRT.IN,
                                        SP.DYN.TFRT.IN, HDR.HDI; society = SP.URB.TOTL.IN.ZS, SE.ADT.LITR.ZS,
                                        IT.NET.USER.ZS, VC.IHR.PSRC.P5, HDR.MYS; income = NY.GDP.PCAP.PP.CD, SI.POV.GINI,
                                        SI.POV.DDAY, SL.UEM.TOTL.ZS; environment = EN.GHG.CO2.PC.CE.AR5, EG.FEC.RNEW.ZS,
                                        AG.LND.FRST.ZS. A `composition` list (Wikidata) is null unless its shares add up to
                                        80-105%, sorted by share desc; `year` = most recent year of the listed shares.
                                        404 unknown country.
GET /v1/countries/{iso2}/economy     -> { indicators: [{ id: string, label: string, unit: string, value: number|null, year: int|null,
                                                         source_id: string, series: [{ year: int, value: number }] }],
                                          sources: Source[] }
                                        Always these 10 ids, in this order: NY.GDP.MKTP.CD, NY.GDP.PCAP.PP.CD,
                                        NY.GDP.MKTP.KD.ZG, FP.CPI.TOTL.ZG, SL.UEM.TOTL.ZS, GC.DOD.TOTL.GD.ZS,
                                        BN.CAB.XOKA.GD.ZS, FI.RES.TOTL.CD, SI.POV.GINI, PA.NUS.PPP. `value`/`year` = latest
                                        point (null and [] = no data); `series` = the points of the 20 years up to that one,
                                        ascending, gaps allowed. 404 unknown country.
GET /v1/economy/compare?countries=&ids=
                                     -> { countries: string[], indicators: [{ id: string, label: string, unit: string,
                                                         values: { [iso2: string]: { value: number, year: int }|null } }],
                                          sources: Source[] }
                                        `countries`: 2-5 ISO2, comma-separated, kept in the given order (else 422; unknown
                                        country 404). `ids` optional, comma-separated, subset of the 10 economy ids (else
                                        422); default all 10. Each value is that country's latest year (years may differ).
GET /v1/currencies/{code}            -> { code: string, name: string, symbol: string|null, countries: string[] /* iso2 */,
                                          rates: { date: string /* YYYY-MM-DD */, base: string,
                                                   items: [{ code: string, rate: number /* 1 base = rate code */ }] }|null,
                                          stats: { change_1y: number|null, change_5y: number|null,
                                                   volatility_1y: number|null, max_drawdown_1y: number|null }|null,
                                          sources: Source[] }
                                        `code` ISO 4217 (^[A-Z]{3}$, else 422). 404 when no country uses the code.
                                        `date` = last date with a rate for `code`; each item uses that currency's latest
                                        rate in the 7 days up to `date`; sorted by code. `rates` null = no rates.
GET /v1/currencies/{code}/history?vs=&from=&to=
                                     -> { base: string, vs: string[], items: [{ date: string, rates: { [code: string]: number } }],
                                          source: Source }
                                        `vs`: 1-4 ISO 4217 codes, comma-separated (default "USD,EUR" minus `code`), else 422;
                                        a code without rates (also `code`) -> 404. `from`/`to`: YYYY-MM-DD; default
                                        to = last date with data, from = to - 365 days; from > to or a window over 30 years
                                        -> 422. `rates[c]` = how many `c` for 1 `base`; a date appears when at least one vs
                                        has a rate that day (missing keys = no rate). Windows over 2 years are reduced to one
                                        point per ISO week (the last day of the week with data).
                                        `source` = exchange-api (secondary) when any point came from it, else ecb.

## Seed ids (must exist, same ids in both agents' fixtures)
Modern: austria (AT), brazil (BR), germany (DE), egypt (EG), japan (JP), turkey (TR), russia (RU), serbia (RS)
Historical: ottoman-empire, austria-hungary, german-empire, weimar-republic, nazi-germany, east-germany, soviet-union, yugoslavia

## v1.3 (CR-004 and addenda 1-4; applied 2026-11-13 under the owner's bulk approval of spec 026)
All additive: a v1.2 client keeps working. Text as approved in contract/CHANGE_REQUESTS.md.

### Base (CR-004)
Shared types:
```
Period         { id: string /* "<iso2 lower>-<n>", article order */, title: string, year_start: int|null, year_end: int|null,
                 summary: string /* paragraphs separated by a blank line */, event_count: int }
CountryHistory { summary: string|null, periods: Period[], sources: Source[] }
```
Endpoint:
```
GET /v1/countries/{iso2}/history     -> CountryHistory
                                        Condensed (never rewritten) from the pt.wikipedia article "História de X" linked by
                                        Wikidata P2184; when there is none, the "História" section of the country article.
                                        `sources[0]` = that article at the exact revision (url ?oldid=), license CC BY-SA 4.0:
                                        clients must show it next to the text. Both year fields null = the title has no years;
                                        year_start null + year_end set = "até <year_end>"; year_end null + year_start set = to present.
                                        No article = { summary: null, periods: [], sources: [] }. Unknown iso2 -> 404.
```

### CR-004 addendum (2026-11-12): subdivisions (spec 024 stage 1)
Shared types:
```
Subdivision     { wikidata_id: string /* key: the web's admin-1 polygons carry it as `wikidataid` */, code: string|null /* ISO 3166-2 */,
                  name: string, capital: string|null, area_km2: number|null, population: { value: int, year: int|null }|null,
                  flag: Image|null /* Commons, per-file credit + licence */ }
SubdivisionList { items: Subdivision[], sources: Source[] }
```
Endpoint:
```
GET /v1/countries/{iso2}/subdivisions -> SubdivisionList
                                        In the order of the web's admin-1 file. No head of government (Wikidata's are stale).
                                        Country without subdivisions -> { items: [], sources: [] }. Unknown iso2 -> 404.
```

### CR-004 addendum 2 (2026-11-13): history events (spec 016 stage 2)
Changes `CountryHistory` (additive field) and gives `Period.event_count` a value:
```
HistoryEvent   { id: string /* Wikidata Q-id */, title: string, summary: string|null, kind: EventKind /* same enum as Event */,
                 year_start: int, year_end: int|null, wikipedia_url: string|null }
CountryHistory { summary: string|null, periods: Period[], events: HistoryEvent[], sources: Source[] }
```
`events`: up to 40 notable dated events (Wikidata, >= 10 Wikipedia editions) of the country or of a DIRECT predecessor state, sorted
by (year_start, id); automatic, never human-reviewed (clients must say so). `Period.event_count` = events whose year_start falls in
the period's years (0 when the period has no years). `sources` gains `wikidata` when there are events.

### CR-004 addendum 3 (2026-11-13): political currents (spec 018)
`GlossaryKind` gains `"ideology"` (14 currents in `content/ideologies.yaml`). Two changes to the approved 018 delta, for neutrality:
`IdeologyFigure` gains `via` and `party` (WHY the person is listed), and `milestones`/`timeline` stay empty for now.
```
PartyRef          { id: string /* Wikidata Q-id */, name: string }
IdeologyFigure    { person_id, name, role: "thinker"|"leader"|"activist"|"other", birth_year: int|null, death_year: int|null,
                    summary: string|null, works: string[] /* max 3 */, image: Image|null, wikipedia_url: string|null,
                    via: "declared"|"party", party: PartyRef|null }
CountryIdeology   { term: GlossaryTerm, figures: IdeologyFigure[] /* max 6, declared first */, parties: PartyRef[] /* max 5 */,
                    milestones: Event[] }
GET /v1/countries/{iso2}/ideologies -> { items: CountryIdeology[] /* most figures first */, sources: Source[] }
GET /v1/ideologies/{id}             -> { term: GlossaryTerm, founders: IdeologyFigure[] /* declared only */, timeline: Event[],
                                         governed: [{ iso2, from_year: int, to_year: int|null }], sources: Source[] }
```
`via: "declared"` = deceased person with the current in a referenced Wikidata P1142; `"party"` = member of a party whose P1142 is
the current (clients must show the party, e.g. "filiado ao Partido X", never present it as a label on the person). `governed` =
continuous stretches in which a head of state/government (spec 006) belonged to a party of that current. Unknown id or a glossary
term that is not a current -> 404.


### CR-004 addendum 4 (2026-11-13): subdivision area codes (spec 026)
The owner asked for "o DDD dos estados de todos os países" (2026-11-13). Additive field on `Subdivision`:
```
Subdivision     += { area_codes: string[] /* telephone area codes (DDD), sorted; [] = no data */ }
```
Brazil: curated table from Anatel (content/area_codes.yaml); elsewhere Wikidata P473 where present (low coverage, ~22% of units).
`SubdivisionList.sources` includes `anatel` for BR. Also: `CountryDetail.memberships` now lists curated organizations
(content/organizations.yaml: Mercosul, BRICS, G7, G20, União Europeia, OTAN, OPEP, ASEAN, União Africana, CPLP, OCDE) besides
"ONU"; each value is the `label` of a `membership` glossary term. No type change.
