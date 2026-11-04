# Changelog

Todas as mudanças relevantes deste projeto ficam aqui. O formato segue o
[Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## [Não publicado]

### Adicionado

- Arquivos de comunidade: código de conduta, guia de contribuição, política de segurança, suporte e templates de issue.
- `install.py` instala as skills de terceiros que o método usa (`grill-me`, `grilling`, `find-skills`, `playwright-cli`,
  `security-and-hardening`, `security-threat-model`, `semgrep`); `--sem-skills` pula.
- Tabela de skill por situação no `claude/CLAUDE.md`.

## [0.2.0] - 2026-11-04

Reúne tudo o que entrou no PR #2.

### Adicionado

- Skill `grilling` e a regra de começar todo pedido com perguntas, com `grill-me` como dependência.
- Hooks: ler arquivo grande por trechos, só subagente edita e aviso de contexto baixo.
- Modo noturno: roda a fila do `TASKS.md` com guarda contra push e contra a `main`.
- Skills `commit-curto` e `pr-curto`, hook `commit-msg` que recusa mensagem fora do padrão e templates de PR.
- Scripts `tarefa.py` e `arquivar.py` e o orçamento do contexto fixo.
- `install.py`, instalador único para Linux, macOS, WSL e Windows (`install.sh` e `install.ps1` só chamam o Python).
- Regras do método: vermelho válido, desvio, contrato de retorno, entrega reduzida, lições e worktree por agente.

### Mudado

- Bateria, noite e painel portados de shell para Python.
- README com as seções de hooks, modo noturno e referências aos scripts em Python.
- `install.ps1` avisa sobre o WSL.

### Corrigido

- A `dev` termina limpa no fim do modo noturno, pronta para a noite seguinte.

## [0.1.0] - 2026-11-03

### Adicionado

- Kit inicial OptimusClaude, com os testes do painel pelo diff.
- Licença MIT.
- Instalador do Windows.
- Imagem do painel.

### Corrigido

- Painel: fecha o `@media` que prendia o CSS do celular.

[Não publicado]: https://github.com/fezarosa-dev/OptimusClaude/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/fezarosa-dev/OptimusClaude/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/fezarosa-dev/OptimusClaude/releases/tag/v0.1.0
