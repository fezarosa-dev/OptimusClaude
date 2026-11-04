# Como contribuir

Obrigado por querer ajudar. Este guia é curto de propósito. Ao participar, você aceita o
[Código de Conduta](CODE_OF_CONDUCT.md).

## Reportar um bug

1. Procure uma [issue](https://github.com/fezarosa-dev/OptimusClaude/issues) igual antes de abrir outra.
2. Abra uma issue pelo formulário de bug. Diga o que aconteceu, o que esperava e como reproduzir.
3. Informe o sistema e a versão do Claude Code (`claude --version`). A saída de `python3 install.py --so-checar` ajuda;
   tire dado pessoal antes de colar.

Falha de segurança **não** vai em issue pública: veja o [SECURITY.md](SECURITY.md).

## Propor uma ideia

Abra uma issue pelo formulário de ideia **antes** de fazer um PR grande. Descreva o problema, a proposta e as
alternativas. Assim ninguém perde tempo com algo que não cabe no kit. PR pequeno (typo, link, texto) pode ir direto.

## Ambiente de desenvolvimento

```bash
git clone https://github.com/fezarosa-dev/OptimusClaude.git
cd OptimusClaude
git config core.hooksPath .githooks   # liga o hook que confere a mensagem de commit
python3 install.py --dry-run          # mostra o que o instalador faria, sem mudar nada
```

Precisa de Python 3.9 ou mais novo e de git. Nada mais.

## Fluxo de branch

- Crie a branch a partir da `dev`, com o prefixo do tipo: `feat/...`, `fix/...`, `docs/...` ou `ci/...`.
- Abra o PR **para a `dev`**.
- A `main` só recebe PR vindo da `dev`. Nunca abra PR de feature direto para a `main`.

## Mensagem de commit

Padrão: `tipo(escopo): descrição`. O escopo é opcional; `!` antes dos dois-pontos marca quebra de compatibilidade.

Tipos: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `build`, `ci`, `chore`, `style`, `revert`.

```text
feat(noite): guarda contra push na main
fix(install): não perde chave ao mesclar settings
docs: explica o modo noturno
refactor(painel)!: renomeia a rota de estado
```

O hook `.githooks/commit-msg` recusa:

- assunto fora do padrão `tipo(escopo): descrição`;
- assunto com mais de 72 caracteres ou terminado em ponto;
- falta de linha em branco entre o assunto e o corpo;
- autoria de IA (`Co-Authored-By` de IA, "Generated with").

Merge, revert, `fixup!` e `squash!` gerados pelo git passam.

## Pull request

Abra o PR pelo [template](.github/pull_request_template.md): o quê, por quê, como testou e riscos. O título segue o
mesmo padrão do commit. Frases curtas, sem enfeite.

## Testes

Rode as suítes que o seu diff toca, a partir da raiz do repositório:

```bash
python3 -m unittest discover -s claude/hooks                         # hooks do Claude Code
python3 -m unittest discover -s claude/scripts -p 'test_*.py'        # scripts em claude/scripts
python3 -m unittest test_install                                     # instalador
(cd painel && python3 testar.py)                                     # painel
(cd projeto-modelo && python3 -I -m unittest discover -s scripts -p 'test_*.py')   # projeto-modelo
```

Mexeu em comportamento? Escreva o teste primeiro (TDD) e **veja-o falhar pelo motivo certo** antes de corrigir: o
vermelho precisa ser válido, ou seja, falhar porque a funcionalidade falta, não por erro de digitação ou de importação.
Depois faça passar e rode a suíte inteira da área.

## Regras do projeto

- Só a biblioteca padrão do Python 3.9+. Dependência nova só com justificativa escrita no PR.
- Sem autoria de IA em commit, PR, issue ou código.
- Textos, comentários e mensagens em português do Brasil, com acentuação.
- Mudanças pequenas e ligadas ao assunto do PR.
- Nunca inclua segredo, chave ou dado pessoal em commit, issue ou log colado.

## Licença das contribuições

Ao enviar uma contribuição, você concorda que ela seja distribuída sob a [licença MIT](LICENSE) do projeto.
