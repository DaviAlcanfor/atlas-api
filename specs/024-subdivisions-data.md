# 024 - Estados: dados e bandeira por subdivisão
Status: in progress (aprovada pelo dono em 2026-11-12: "vê o que tá pendente e já vai fazendo") | Contrato: v1.3 (CR-004) | Web: atlas-web/specs/024-subdivisions-data.md

## Dados (fase 1)
- Quais estados: os `wikidataid` dos polígonos admin-1 do web (Natural Earth), lidos de `ADMIN1_DIR` (padrão `../geo/public/data/admin1`):
  3.754 subdivisões em 240 países, a API responde exatamente pelos desenhos do globo.
- Wikidata (CC0): P300 código ISO 3166-2 (3.644), P36 capital (3.500), P2046 área normalizada em km² (3.643),
  P1082 população com ano (posição preferida, senão a data P585 mais recente; 3.377), P41 bandeira (1.740 com licença válida).
- Bandeiras: Commons, licença POR ARQUIVO (`extmetadata` `LicenseShortName` + `Artist`, mesma regra das fotos da 006); bandeira em
  domínio público/CC0 sem autor é aceita com crédito "Wikimedia Commons". Miniaturas espelhadas no Storage como as fotos.
- **Sem governador**: testado em 2026-11-12, o Wikidata está desatualizado (P6 do RJ = Witzel, afastado em 2021; a rota P1313 + P39
  traz governadores do século XIX sem data de fim). Governador errado é pior que nenhum. Fonte melhor fica para depois.
- IDH subnacional (Global Data Lab) e IBGE: fase 2, depois de ler os termos.

## Entregue (fase 1)
`python -m etl wikidata-subdivisions [ISO2...]` -> `data_out/subdivisions.json`; migração 0012 (`subdivisions`); `import-facts`;
`GET /v1/countries/{iso2}/subdivisions`; testes `tests/test_subdivisions.py`. Texto do contrato: CR-004.
