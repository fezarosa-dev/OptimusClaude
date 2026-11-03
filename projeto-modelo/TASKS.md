# Tarefas

Todo pedido vira uma tarefa `Tn`, com as palavras de quem pediu. O estado é atualizado a cada entrega, para saber o que
falta sem precisar auditar.

Estados: `aprovada` (registrada, esperando disparo) → `em andamento` → `feita na dev` (com o merge) → `no ar` (com o PR).
"Pode colocar" = registrar aqui, não executar. Depois de mandada disparar, a tarefa não volta a pedir licença a cada
etapa: quando a dependência cai, a próxima etapa segue.

Achar uma tarefa: `grep -nE '^#{2,3} T[0-9]' TASKS.md`.

---

## Em andamento

### T2 · Exportar o relatório mensal em CSV (exemplo)

- **Origem:** pedido de AAAA-MM-DD: "preciso baixar o relatório do mês em planilha".
- **Fazer:** botão "Baixar CSV" na tela do relatório; o servidor gera o arquivo com as mesmas colunas da tela.
- **Evidência:** `web/src/relatorio.tsx:40` monta a tabela; não há rota de exportação.
- **Conferir:** teste da rota (CSV com cabeçalho e uma linha por item; célula vinda de texto de fora não começa com `=`)
  e teste de tela do botão.
- **Agente:** Sonnet `high` (implementação com TDD, sem decisão aberta). Revisor: Sonnet `medium`.
- **Estado:** em andamento, branch `feat/relatorio-csv`.

## Feitas

### T1 · Ligar a bateria local e o CI (exemplo)

- **Origem:** começo do projeto.
- **Fazer:** `scripts/testar-como-o-ci.sh`, o mapa `scripts/o_que_testar.py` e o `.github/workflows/testes.yml`.
- **Estado:** feita na `dev` (merge `<sha>`), no ar (PR #1).
