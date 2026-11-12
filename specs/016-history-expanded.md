# 016 - História expandida por períodos
Status: approved | Contrato: v1.2 | Web: atlas-web/specs/016-history-expanded.md | Executor: Opus

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

## Tarefas
- [ ] SPARQL de eventos e períodos testado em BR, JP, DE, EG, AT (contagens aqui)
- [ ] extratos da Wikipedia no ETL (com atribuição); tabelas `periods`, `events` ampliada; endpoints; testes
- [ ] conteúdo curado do Brasil (rascunho para revisão)
