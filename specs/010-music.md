# 010 — Música
Status: draft | Contrato: v1.2 | Web: atlas-web/specs/010-music.md

## Dados
"Mais popular" exige dado de audiência, e as fontes de audiência têm termos restritivos. Por isso duas partes:
| Parte | Fonte | Licença/termos (a confirmar) |
|---|---|---|
| Nasceram aqui | Wikidata: gêneros com P495 (país de origem) = país | CC0 |
| Mais ouvidos | Last.fm `geo.getTopArtists?country=` + `artist.getTopTags` | chave grátis, uso não comercial; **ler limites de armazenamento** |
Descartados: Spotify (termos do desenvolvedor vetam esse uso/armazenamento), charts oficiais (sem API aberta).
Viés: Last.fm é forte em Europa/Américas; países com poucos usuários terão listas fracas.

## Contract delta
```
GET /v1/countries/{iso2}/music -> { origin_genres: [{ id, name, wikipedia_url }],
                                    popular: { artists: [{ name, url }], genres: [{ name, share }], date, source }|null }
```

## Design
- Gêneros de origem: query nova na pipeline do Wikidata; tabela `genres` + n:n.
- Last.fm: depende dos termos. Se permitirem guardar: ETL periódico como o de notícias. Se não: busca ao vivo com cache TTL.
  Chave em env `LASTFM_API_KEY` (nunca no front, nunca no git).

## Tarefas
- [ ] ler termos Last.fm; decidir cache vs. job; citar aqui
- [ ] gêneros P495; endpoint; testes
