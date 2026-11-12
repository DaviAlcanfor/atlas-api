# 011 — Vídeos de história
Status: draft | Contrato: v1.2 | Web: atlas-web/specs/011-history-videos.md

## Dados
Curadoria manual em `content/videos.yaml` (iso2 → [{ youtube_id, title, channel, lang }]), revisada pelo dono.
Por quê: busca automática na YouTube Data API traz muito vídeo ruim, a cota é ~100 buscas/dia e os termos pedem atualizar
dados guardados a cada 30 dias. Opcional: script que busca candidatos e gera rascunho de YAML para aprovação.

## Contract delta
`CountryDetail += videos: [{ youtube_id, title, channel, lang }]`

## Design
- `import-content` lê o YAML; validação `^[A-Za-z0-9_-]{11}$` no `youtube_id`; tabela `videos`.

## Tarefas
- [ ] YAML + import + campo + testes; primeiros vídeos para os 5 países com conteúdo
