# Change requests (contract is FROZEN; nothing here is applied until the user approves)

## CR-001: news endpoints (additive, proposed 2026-11-11)

**What:** add `GET /v1/news?country=<iso2>&limit=` returning
`{ items: [{ id, published_on (date), summary, countries: string[] /* iso2 */,
sources: [{ title, url }], origin: { name, url, license } }] }`. `country` optional
(absent = world news). No write endpoints.

**Why:** the user wants a world-news page and per-country news.

**Source (verified 2026-11-11, English only):** Wikipedia "Portal:Current_events/<date>" via the
MediaWiki Action API (`action=parse&prop=wikitext`, no key). Text is CC BY-SA 4.0: stored or
modified copies must stay CC BY-SA and link back to the page. Each entry carries links to the
original outlets; those articles keep their own copyright, so we only link them.
Country filter: map each entry's wikilinks to the countries' Wikipedia titles (heuristic, not
exact: an entry mentioning Germany as a mediator also matches DE).

**Not usable from the dev machine:** GDELT DOC API answers HTTP 429 ("one every 5 seconds") to
every request from this network, so it could not be tested. Do not rely on it.

**Blocked on user decisions (these also conflict with current rules):**
1. AGENTS.md says the ONLY DB writer is `import-content`. News needs a recurring job that
   writes (or the API fetching live with an in-memory cache and no storage). Pick one.
2. Content language: the contract says pt-BR only; this source is English.
3. Contract version bump (additive: v1.2) and the front must agree.
4. AI summaries of the headlines are NOT proposed (risk of errors/bias in geopolitics).

**Status (2026-11-11):** superseded by the workspace spec `../specs/008-news.md` (outside this repo). Do not implement from this CR.

## CR-002: contract v1.1 (additive, proposed 2026-11-11) — APPROVED by the owner 2026-11-11, applied to CONTRACT.md in both repos
One bump for "phase B" (data the Wikidata ETL already reaches). Each item's details and rationale are in `specs/`:
- `CountryDetail.clues` (driving side, calling code, TLD, plate code, scripts) — `specs/003-geo-clues.md`
- `GlossaryTerm`, `GET /v1/glossary`, `GET /v1/glossary/{id}`, `regime_id` on country summary/detail — `specs/004-glossary.md`
- `CountrySummary.capital_coords: [{ name, lat, lng }]` (data already in the DB) — `specs/005-capital-coords.md`
- `Leader`, `GET /v1/countries/{iso2}/leaders?role=` (without `position`, that is v1.2) — `specs/006-leaders-spectrum.md`
- `Person`, `GET /v1/countries/{iso2}/people?domain=&limit=` — `specs/007-notable-people.md`
All additive: no existing field changes meaning, so a v1.0 client keeps working.
To apply: the user approves the specs (or a subset), copies the deltas into `contract/CONTRACT.md` as v1.1 in BOTH repos.

### CR-002 status (2026-11-11): implemented LOCALLY in this repo, not deployed
Code, migrations 0003-0006 and tests exist (see `docs/CONTRACT_NOTES.md`, section v1.1). Nothing goes to
production until the user pastes the text below into `contract/CONTRACT.md` in BOTH repos.

### Exact proposed v1.1 text (paste into CONTRACT.md)
Header: `Version: 1.1` (additive over 1.0: a 1.0 client ignores the new fields and endpoints).

One semantic note for `regime` (existing field, same type): from v1.1 it is the pt-BR label of `regime_id` when
`regime_id` is non-null (source: Wikidata P122); otherwise the old curated text, which may be null.

Add to **Conventions**:
```
- Content language: pt-BR, except data quoted from a source that has no pt-BR version: `Person.name` and
  `Person.occupation` (Pantheon, English, occupation in UPPER CASE as published). `Leader.office/name/party.name`
  are Wikidata labels in pt-BR, else pt, else en.
- Images (`image`) are thumbnails hosted by Wikimedia Commons. Each file has its own licence: the front MUST show
  `image.credit` and `image.license` next to the picture. `image` is null when the file has no clear licence + author.
```

Add to **Shared types**:
```
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
```

Change in **Shared types** (append fields):
```
CountrySummary += { regime_id: string|null /* GlossaryTerm id, kind "regime" */,
                    capital_coords: [{ name: string, lat: number, lng: number }] /* [] = unknown */ }
CountryDetail  += { regime_id: string|null,
                    clues: { driving_side: "left"|"right"|null, calling_code: string|null /* "+55" */,
                             tld: string|null /* ".br" */, plate_code: string|null /* "BR" */,
                             scripts: string[] /* pt-BR names of the writing systems of the official languages */ }|null }
                    (`clues` is null when none of its fields has data)
```

Add to **Endpoints**:
```
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
```

### Decisions the user still has to take before pasting
1. Pantheon `occupation`/`name` stay in English (no pt-BR source). Accept, or ask for a pt-BR occupation table (102 values, our own translation).
2. `Person.domain` = Pantheon's own 8 domains (spec 007 said "5 areas"; regrouping 8 -> 5 would be our invention).
3. Glossary text is an agent DRAFT (`content/glossary.yaml`, header "RASCUNHO — revisão humana pendente").
4. Images hotlink Wikimedia thumbnails (pipeline.py notes Commons asks to avoid hotlinking; flags use flagcdn for that reason). Alternative: copy the files to the web repo.

## CR-003: contract v1.2, part A (additive, proposed 2026-11-12) — specs 009, 015, 017 (+ 019, no contract change)
The owner approved specs 009/015/017/019 and "contract v1.2" in bulk (2026-11-12). Part A = data already implemented
LOCALLY in this repo (branch `feat/v1.2-data`, migrations 0007-0010, not deployed). 016 (history), 018 (ideologies),
008 (news) and 006 v1.2 (spectrum) are NOT in this CR (part B). All additive: a v1.1 client keeps working.
Coverage numbers per field are in each spec (`specs/009`, `015`, `017`, `019`).

### Exact proposed v1.2 (part A) text (paste into CONTRACT.md in BOTH repos)
Header: `Version: 1.2 (additive over 1.1; part A = CR-003: languages_spoken, profile, economy, currencies)`

Change in **Conventions** (replace the `Images` bullet):
```
- Images (`image`) are 320px thumbnails of Wikimedia Commons files, served either by Commons or by the Atlas public
  storage bucket (a copy of the same thumbnail). Each file has its own licence: the front MUST show `image.credit`
  and `image.license` next to the picture. `image` is null when the file has no clear licence + author.
```

Add to **Conventions**:
```
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
```

Add to **Shared types**:
```
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
```

Change in **Shared types** (append field):
```
CountryDetail += { languages_spoken: LanguageSpoken[] }
                  Sorted by status in the order official, co_official, indigenous, immigrant, sign, historical, then by
                  speakers desc (unknown last), then name. [] = no data. `languages` (v1.0) is unchanged.
```

Add to **Endpoints**:
```
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
```

### Notes for the web team
- Response samples (BR, JP, DE): `v12a-samples.json`, handed over by the main agent.
- `languages_spoken` can be long (Wikidata P2936 lists every language used in a country: hundreds for NG, IN).
  Show the first statuses and collapse the rest.
- Currencies outside the ECB list (ARS, NGN...): history is weekly and starts in 2024-03, so `change_5y` is null.

## CR-004: contract v1.3, history summary (additive, proposed 2026-11-12) — spec 016 stage 1
The owner asked for "o resumo da história do país" (2026-11-12). Spec 016 was approved in the v1.2 bulk approval; this CR is its
first stage. One change from the approved 016 delta: `Period.year_start` is nullable (section titles of the source articles do not
always carry years). `event_count` is 0 until stage 2 (Wikidata events). All additive: a v1.2 client keeps working.
Implemented on branch `feat/history-summary` (migration 0011, `etl wikipedia-history`, `import-facts` reads `data_out/history.json`).

### Exact proposed v1.3 text (paste into CONTRACT.md in BOTH repos)
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
