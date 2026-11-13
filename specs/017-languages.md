# 017 - Idiomas oficiais e outros falados
Status: in progress (ETL e endpoint feitos; falta importar na produção) (revisado em 2026-11-13) | Contrato: v1.2 | Web: atlas-web/specs/017-languages.md | Executor: Opus (classificação), Sonnet (endpoint)

## Dados
Wikidata (CC0):
- Oficial: P37 do país (já usado).
- Falados: P2936 ("language used") do país; e línguas com P17/P2341 ("indigenous to") = país.
- Cooficial regional: P37 de subdivisões/municípios do país (ex.: São Gabriel da Cachoeira → Nheengatu, Baniwa, Tukano; Pomerode → Pomerano).
- Classificação do `status`, em ordem: oficial (P37 do país) > cooficial (P37 de subdivisão) > língua de sinais (P31 Q34228) >
  histórica (P31 língua extinta/morta Q45762 ou "dead language", ou P576) > indígena (P2341 = país, ou família nativa das Américas/Oceania/etc.
  via tabela de famílias em `content/language_families.yaml`) > imigração (resto).
- Falantes: P1098 com qualificador de país e data quando houver. Família: P279/P31 até um item "família de línguas". Ameaça: P1999 (UNESCO).
- Casos que exigem conferência manual (registrar na spec): alemão (Hunsrik e "alemão" padrão), Talian, japonês e italiano no Brasil.

## Contract delta (v1.2)
```
CountryDetail.languages_spoken: [{ code: string|null, name, status: "official"|"co_official"|"indigenous"|"immigrant"|"sign"|"historical",
  where: string|null, speakers: { value: int, year: int|null }|null, family: string|null, endangerment: string|null, wikipedia_url: string|null }]
Ordenado por status (na ordem acima) e depois por falantes desc.
```

## Tarefas
- [x] SPARQL testado em BR, IN, US, ES, NG, BO (listar o que saiu e o que faltou)
- [x] tabela `country_languages`; import; campo; testes
