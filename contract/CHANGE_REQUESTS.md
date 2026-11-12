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
