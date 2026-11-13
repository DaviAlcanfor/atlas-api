# 018 - Ideologias: pensadores e figuras por país
Status: in progress (fase 1 feita em 2026-11-13: catálogo, figuras, partidos, governos; marcos pendentes) | Contrato: v1.2 | Web: atlas-web/specs/018-ideologies.md | Executor: Opus

## Dados
- Correntes (catálogo fixo, `content/ideologies.yaml`): capitalismo, liberalismo, liberalismo econômico/libertarianismo, conservadorismo,
  social-democracia, socialismo, comunismo/marxismo, anarquismo, fascismo, nacionalismo, populismo, ambientalismo, democracia cristã,
  islamismo político. Cada uma vira `GlossaryTerm` com `kind: "ideology"` (texto próprio, pt-BR, neutro, com fontes; rascunho para revisão).
- Figuras: Wikidata P1142 ("political ideology") da pessoa = corrente (ou subclasse via P279), com P27 = país ou P19 no país.
  Ordenadas pelo HPI do Pantheon quando a pessoa estiver lá (spec 007), senão por sitelinks. Máx. 6 por corrente/país.
  Papel: pensador se tem P800 (obra notável) de filosofia/economia ou ocupação filósofo/economista/escritor; líder se tem P39 de chefe de
  Estado/governo/partido; senão ativista/outro. Obras: P800 (máx. 3). Resumo: descrição pt-BR do Wikidata + extrato da Wikipedia (CC BY-SA).
- Partidos: itens com P31 partido político, P17 = país, P1142 = corrente.
- Marcos no país: eventos da spec 016 ligados à corrente (P1142 do evento ou do partido envolvido), máx. 2.
- Página global (`/v1/ideologies/{id}`): fundadores = figuras com mais HPI no mundo; `governed` = períodos em que líderes da spec 006
  tinham partido com essa corrente.

## Regra de neutralidade (obrigatória, vale para todo texto gerado)
Mesmo formato e tamanho de texto para todas as correntes; nenhum adjetivo de valor; fatos com fonte (inclusive violência e repressão de
regimes de qualquer lado); controvérsias apresentadas com as posições principais e fonte de cada uma. Revisão humana antes de `reviewed: true`.

## Contract delta (v1.2)
```
GlossaryTerm.kind += "ideology"
IdeologyFigure { person_id, name, role: "thinker"|"leader"|"activist"|"other", birth_year, death_year, summary, works: string[],
                 image: Image|null, wikipedia_url }
GET /v1/countries/{iso2}/ideologies -> { items: [{ term: GlossaryTerm, figures: IdeologyFigure[], parties: [{ id, name }], milestones: Event[] }], sources }
GET /v1/ideologies/{id}             -> { term, founders: IdeologyFigure[], timeline: Event[], governed: [{ iso2, from_year, to_year }], sources }
```

## Fase 1 (2026-11-13): o que mudou em relação ao plano, por neutralidade
- Catálogo: `content/ideologies.yaml`, 14 verbetes no mesmo formato (o que defende / origem e onde governou / defensores e críticos,
  com repressão dita do mesmo jeito para qualquer lado). RASCUNHO para revisão humana.
- **Figuras: não usar P1142 da pessoa viva, nem subcorrentes via P279\*.** Testado: P279\* pôs um presidente dos EUA em fascismo e
  Frederico II em liberalismo; P1142 direto em pessoas vivas também traz rótulos contestados (mesmo com referência). Critério final:
  (a) pessoa falecida com a corrente em P1142 referenciado; (b) membro (P102) de partido cujo P1142 é a corrente, país = do partido.
  Cada figura diz por quê (`via`, `party`). Lista mundial = só (a). Subcorrentes só listadas à mão (nazismo Q7310 em fascismo).
  Limite conhecido: (b) usa a ideologia ATUAL do partido (Lincoln aparece como conservador republicano).
- `governed`: mandatos de chefes de Estado/governo (spec 006) com partido daquela corrente, juntados em trechos contínuos.
- Marcos por corrente (`milestones`, `timeline`): vazios nesta fase.
- `python -m etl wikidata-ideologies` -> `data_out/ideologies.json` (2.914 pessoas); migração 0014; endpoints; testes.

## Tarefas
- [x] catálogo + verbetes (rascunho neutro); SPARQL de figuras e partidos testado (BR, US, DE e as 14 correntes)
- [x] tabelas, import, endpoints, testes
- [ ] revisão humana dos verbetes (dono)
- [ ] marcos por corrente
