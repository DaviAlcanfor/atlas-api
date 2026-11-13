# 016 - História expandida por períodos
Status: in progress (fases 1 e 2 feitas; falta conteúdo curado do Brasil) (revisado em 2026-11-13) | Contrato: v1.2 | Web: atlas-web/specs/016-history-expanded.md | Executor: Opus

## Por quê
5 eventos no Brasil é pouco. Precisa de períodos + dezenas de eventos com detalhe, para todos os países, sem inventar fatos.

## Dados (duas camadas)
1. **Automática (todos os 196)**: Wikidata.
   - Períodos: itens com P31 "período histórico" (Q11514315) e P17/P1001 = país, ou a cadeia de `polities` com predecessores (já na API).
   - Eventos: itens com P17 = país e P31 em {guerra, batalha, revolução, golpe, tratado, eleição geral, independência, constituição},
     com data (P585 ou P580/P582) e ≥ 10 sitelinks (filtro de notabilidade). Título = rótulo pt-BR; resumo = descrição pt-BR;
     `long_summary` = extrato da Wikipedia pt (REST `page/summary`, CC BY-SA 4.0: atribuir e linkar) buscado no ETL, não ao vivo.
   - Marcados `reviewed: false`.
2. **Curada (países com conteúdo, começando pelo Brasil)**: `content/polities/<id>.yaml` ganha `periods:` e mais eventos, escritos pelo
   agente a partir de fontes citadas (Wikipedia pt/en, Britannica), cada evento com `source_ids`; `reviewed: true` só depois da revisão humana.
   Meta Brasil: 7 períodos, ≥ 40 eventos. Curado vence automático quando os dois têm o mesmo evento (casar por Q-id).

## Contract delta (v1.2)
```
Period      { id, title, year_start, year_end: int|null, summary, event_count }
EventDetail = Event + { long_summary: string|null, people: [{ id, name }], image: Image|null, wikipedia_url: string|null, reviewed: bool }
GET /v1/countries/{iso2}/history             -> { periods: Period[], sources: Source[] }
GET /v1/countries/{iso2}/history/{period_id} -> { period: Period, events: EventDetail[] }
`timeline` do CountryDetail (v1.0) continua: os eventos curados, como hoje.
```
Evento sem período (automático) cai num período sintético por século.

## Fase 1 (2026-11-12): resumo em texto corrido, CR-004
Pedido do dono: "falta o resumo da história do país". Fonte: artigo "História de X" da Wikipédia em português, achado pelo Wikidata
P2184 (sem adivinhar título); sem ele, a seção "História" do artigo do país.
- Docs lidas em 2026-11-12: mediawiki.org/wiki/Extension:TextExtracts (`prop=extracts&explaintext=1`, um artigo inteiro por
  requisição), API:Etiquette (User-Agent com contato, requisições em série), Termos de Uso da Wikimedia §7 e CC BY-SA 4.0
  (reuso exige atribuição com título + link e indicação de alteração; o texto condensado segue sob a mesma licença).
- Condensação mecânica, nunca gerada: resumo = primeiros parágrafos da introdução (até 1100 caracteres, corte no fim de frase);
  período = cada seção de nível 2 que não é material de referência (nível 3 quando o nível 2 dá menos de 3, ex.: Japão), título
  como está, anos tirados do título quando houver, texto = primeiros parágrafos (até 650).
- `python -m etl wikipedia-history [ISO2...]` -> `data_out/history.json`; migração 0011 (`country_history`, `history_periods`);
  `GET /v1/countries/{iso2}/history`; testes em `tests/test_history.py`.

## Fase 2 (2026-11-13): marcos do Wikidata, CR-004 adendo 2
`python -m etl wikidata-events [ISO2...]` -> `data_out/events.json`; migração 0013 (`history_events`); `CountryHistory.events`;
`Period.event_count` passa a contar. Tipos (Q-ids conferidos no Wikidata): guerra, guerra civil, guerra de libertação, batalha,
revolução, golpe, golpe militar, declaração de independência, constituição, eleição geral, crise política, anexação, tratado, genocídio.
País = o próprio OU antecessor direto (P1366 = país; dois níveis já trazem Califado Almóada para Portugal). >= 10 edições da
Wikipédia, 40 mais citados por país. Três passos de consulta (por tipo no mundo, antecessores por país, detalhes em lote): tudo que
partia do país estourava o tempo do WDQS. Anos: o WDQS usa ano astronômico (0000 = 1 a.C.); convertido para a regra sem ano 0.

- [x] fase 1: ETL da Wikipédia, migração 0011, endpoint, testes, CR-004
- [x] fase 2: eventos do Wikidata por país (migração 0013, `events`, `event_count`), testes, CR-004 adendo 2
- [x] SPARQL de eventos e períodos testado em BR, JP, DE, EG, AT (contagens aqui)
- [x] extratos da Wikipedia no ETL (com atribuição); tabelas `periods`, `events` ampliada; endpoints; testes
- [ ] conteúdo curado do Brasil (rascunho para revisão)
