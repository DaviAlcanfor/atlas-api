## O que muda

<!-- Uma ou duas frases: o que mudou e por quê. -->

## Spec

<!-- Link para specs/NNN-slug.md (status: approved ou in progress). Mudança sem spec: justifique. -->
- Spec:
- Fase / tarefas marcadas no spec: sim / não

## Contrato

- [ ] Não altera `contract/CONTRACT.md`
- [ ] Altera o contrato: change request em `contract/CHANGE_REQUESTS.md` ou delta aprovado no spec (cole o id):

## Evidência visual

<!-- Só se algo visível mudou. Antes = produção; depois = build local da branch. Imagens em docs/pr/<spec>/. -->
- [ ] Não há mudança visível
- [ ] Antes / depois anexados

| Antes | Depois |
|---|---|
| | |

## Banco e dados

- [ ] Sem migração nova
- [ ] Migração nova é aditiva (a versão antiga roda enquanto a nova sobe)
- [ ] Exige reimportação: `import-content` / `import-facts` / outro comando (liste)

## Testes e qualidade

- [ ] `make test` passa (banco local, porta do `ATLAS_DB_PORT`)
- [ ] `make lint` passa
- [ ] `make typecheck` passa
- [ ] `openapi.generated.json` atualizado se a API mudou

Como testar:

1.
2.

## Riscos e reversão

<!-- O que pode dar errado em produção e como desfazer (revert, flag, reimportação). -->

## Fora do escopo

<!-- O que ficou de propósito para depois. -->
