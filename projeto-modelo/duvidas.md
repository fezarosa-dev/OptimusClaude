# Dúvidas e permissões pendentes

Quando algo depende de decisão ou permissão de quem manda no projeto, a tarefa para naquele ponto, o motivo entra aqui
e o trabalho segue com outras tarefas. Quando a pessoa voltar, resolve-se tudo daqui de uma vez (ou pela aba Perguntas do
painel, pelo celular).

Formato de cada item: **o que travou**, onde parou (tarefa, branch, commit), as opções com a recomendação, e o que
acontece enquanto não houver resposta. Item resolvido ganha a linha `**Resposta (data):**`, e a decisão vai para a
tarefa no `TASKS.md`.

Decisão simples a sessão toma sozinha (com o porquê na tarefa). Decisão difícil pode ir a um conselho de modelos (skill
`llm-council`) e entra aqui como "decidido pelo conselho, para confirmar". Permissão (publicar, mexer em produção,
apagar algo) é sempre de quem manda.

---

## Permissões (ações que só acontecem com o seu OK)

### P-1. Publicar (PR da `dev` para a `main`) (exemplo)

- **Situação:** T2 está na `dev`, testada na máquina. Nada publicado.
- **Quando você pedir:** `EXIGIR_TUDO=1` na `dev`, revisões de segurança do diff, PR, CI, migrations, merge.

## Decisões

### D-1. T2: separador do CSV (exemplo)

- **Travou em:** T2, branch `feat/relatorio-csv`, commit `<sha>`.
- **Opções:** (a) vírgula, padrão do formato (recomendado); (b) ponto e vírgula, abre direto em planilha configurada para
  português.
- **Enquanto isso:** a tarefa segue com (a); trocar é uma linha.
