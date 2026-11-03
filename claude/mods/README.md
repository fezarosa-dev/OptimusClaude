# Mods de interface do Claude Code

Plugins locais (hooks em TypeScript) que mudam a interface. Não são dependência externa: vêm neste repositório.

- **status-bar**: linha de status com git, modelo/effort, contexto, limites de 5h e semanal, e tempo/tokens somando os subagentes.
- **painel-agentes**: painel lateral com os agentes em execução (missão, repositório, branch, modelo, effort, contexto).

## Como ligar

O `install.sh` copia esta pasta para `~/.claude/mods`, registra o marketplace local `optimus-mods` e instala os dois plugins. À mão:

```bash
claude plugin marketplace add ~/.claude/mods
claude plugin install status-bar@optimus-mods
claude plugin install painel-agentes@optimus-mods
```

Abra uma sessão nova depois. Os testes (`tests/`, `register.test.tsx`) exigem o runtime de mods do Claude Code; o `tsconfig.json` estende `./.claude-plugin/types/tsconfig.json`, gerado por ele (não versionado aqui).
