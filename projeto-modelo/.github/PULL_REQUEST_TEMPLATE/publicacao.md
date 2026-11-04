<!-- PR dev -> main. Título: chore(publicacao): AAAA-MM-DD. Corpo pronto antes do push: editar depois roda o CI de novo. -->

## O que muda para quem usa
<!-- Cole o docs/publicacao-pendente.md. -->

## Tarefas
<!-- T3, T5, T8 (feitas na dev). -->

## Garantia
- Bateria completa: `EXIGIR_TUDO=1 scripts/testar-como-o-ci.sh` verde, sem PULADO (registro: `registros/baterias/<arquivo>`)
- Revisões de segurança do diff: `registros/revisoes/<arquivo>`
- Índice dos registros: sha256 `<hash>`

## Migrations
<!-- Lista na ordem de aplicação, ou "nenhuma". Aplicadas depois do CI verde e antes do merge. -->

## Como voltar
- Código: `git revert -m 1 <merge>` por PR (fix/ -> dev -> main)
- Banco: <desfazer das migrations na ordem inversa, ou "nada a desfazer">
- Tag antes da publicação: `antes-da-publicacao-AAAA-MM-DD`
