---
name: commit-curto
description: Escrever a mensagem de commit no padrão do método, curta e em português. Use em todo commit (git commit), em "escreve o commit", "mensagem de commit", e antes de qualquer commit feito pela sessão ou pelo modo noturno.
---

# Commit curto

Mensagem curta, exata, em português do Brasil. Diz o porquê; o diff já diz o quê.

## Assunto (sempre)

- `tipo(escopo): descrição`. Escopo opcional, minúsculo (`relatorio`, `painel`, `api`).
- Tipos: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `build`, `ci`, `chore`, `style`, `revert`.
  Quebra de compatibilidade: `!` antes dos dois-pontos (`feat(api)!: ...`).
- Verbo no presente, como o histórico: "adiciona", "corrige", "remove", "fecha", "explica". Nunca "adicionado",
  "adicionando", "foi adicionado".
- Até 50 caracteres quando der; nunca mais de 72. Sem ponto final. Minúscula depois dos dois-pontos.

## Corpo (só se precisar)

- Pule quando o assunto basta.
- Use só para: porquê que não é óbvio, quebra de compatibilidade, migration, segurança, revert. Nesses casos o corpo é
  obrigatório.
- Linha em branco depois do assunto. Linhas até 72 caracteres. Frases curtas, sem enfeite; listas com `-`.
- Tarefa e issue no fim: `Tarefa: T7`, `Closes #42`.

## Nunca

- Autoria de IA: `Co-Authored-By` de IA, "Generated with", "gerado pelo Claude". O hook `.githooks/commit-msg` recusa.
- "Este commit", "agora", "atualmente", "conforme pedido", emoji, nome de arquivo que o escopo já diz.
- Dado pessoal, segredo, nome de cliente.

## Exemplos

- ❌ `feat: Adicionado um novo botão para baixar o relatório mensal em formato CSV.`
- ✅ `feat(relatorio): adiciona download em CSV`
- ✅
  ```
  fix(relatorio): corrige total do mês com fuso

  Pedidos depois das 21h caíam no dia seguinte em UTC.

  Tarefa: T7
  ```
- ✅
  ```
  feat(api)!: renomeia /pedidos para /compras

  BREAKING CHANGE: cliente em /pedidos migra até 2026-12-01; depois disso a rota devolve 410.
  ```

Antes de commitar, confira: o assunto passa no padrão? Tem corpo onde é obrigatório? Nenhuma linha de IA?
