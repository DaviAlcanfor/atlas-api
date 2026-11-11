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
