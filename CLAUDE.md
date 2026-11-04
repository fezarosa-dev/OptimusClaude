# OptimusClaude: instruções para o Claude

Este é o repositório do OptimusClaude, um kit de método para o Claude Code. Quem abriu esta pasta quer, quase sempre,
**instalar** o kit (parte A) ou **desenvolver** o próprio kit (parte B). Responda em português do Brasil.

## A. Se pedirem para instalar

Vale para "instala", "instala o OptimusClaude", "configura isso pra mim" e pedidos parecidos. Siga este roteiro, na
ordem, sem pular passo.

1. **Diga em duas linhas o que vai acontecer:** `claude/` será copiado para `~/.claude` (regras, agentes, skills, hooks,
   workflows) e `painel/` para `~/painel-da-sessao`. Nada é apagado: arquivo diferente que já existia vai antes para
   `~/.claude/backups/optimusclaude-<data>/`.
2. **Confira os pré-requisitos:** `python3 --version` (precisa de 3.9 ou mais novo; no Windows, `py -3 --version`) e
   `git --version`. Se faltar, diga como instalar e pare até a pessoa resolver.
3. **Simule:** rode `python3 install.py --dry-run` (Windows: `py -3 install.py --dry-run`). Resuma em poucas linhas o que
   vai mudar: quantos arquivos serão copiados ou substituídos, se o `settings.json` será criado, o que será instalado
   (caveman, Serena, ccc, semgrep, plugins) e o que já está ok.
4. **Pergunte antes de seguir:** se pode instalar e, se já existe `~/.claude/settings.json`, se ele deve ser mesclado com
   o exemplo (`--mesclar-settings`: mostra o diff e pede `s/N`; o que é da pessoa vence). Nunca sobrescreva nem mescle o
   `settings.json` sem perguntar.
5. **Instale:** `python3 install.py`, com as opções escolhidas (`--mesclar-settings`, `--sem-plugins`, `--sem-skills`). Se a mescla
   pedir `[s/N]`, mostre o diff à pessoa e deixe ela responder.
6. **Resolva o "Falta fazer":** leia a seção `Falta fazer` do fim da saída e trate um item por vez: explique o que é,
   mostre o comando sugerido e pergunte antes de rodar. Nunca instale nada do sistema (gerenciador de pacotes, `winget`,
   `curl | sh`) sem perguntar. Depois, rode `python3 install.py` de novo para conferir.
7. **Explique os próximos passos:**
   - abrir uma sessão nova do Claude Code, para carregar a configuração;
   - opcional: avisos no celular com o ntfy (`NTFY_TOPICO` e `NTFY_TOPICO_PERGUNTA` no `env` do
     `~/.claude/settings.json`; veja `docs/instalacao.md`);
   - começar um projeto a partir do `projeto-modelo/` (veja `docs/comecar-um-projeto.md`);
   - ligar o painel com `/painel`, dentro do projeto.
8. **Nunca:** pôr segredo, token ou nome de tópico real em arquivo do repositório; rodar com `sudo` sem perguntar;
   apagar o backup; editar `~/.claude` à mão no lugar do instalador.

Windows nativo: `powershell -ExecutionPolicy Bypass -File .\install.ps1 --dry-run` faz o mesmo que o passo 3. Para o
painel completo, recomende o WSL (`docs/instalacao.md`).

## B. Se for desenvolver neste repositório

- **Branch a partir da `dev`** atualizada: `feat/`, `fix/`, `docs/` ou `ci/`. A `main` só recebe PR vindo da `dev`.
- **Commit no padrão** `tipo(escopo): descrição`, em português, sem autoria de IA. Ligue o hook uma vez por clone:
  `git config core.hooksPath .githooks`.
- **Só biblioteca padrão do Python 3.9+** nos scripts. Nada de dependência nova sem justificativa.
- **O repositório é a fonte.** Não edite `~/.claude` nem `~/painel-da-sessao` direto: mude aqui e instale com
  `python3 install.py`.
- **Teste a parte que mudou:**

  ```bash
  python3 -m unittest test_install                                              # install.py
  python3 -m unittest discover -s claude/hooks                                  # hooks
  python3 -m unittest discover -s claude/scripts                                # scripts de apoio
  cd painel && python3 testar.py                                                # painel (--tudo roda todos)
  cd projeto-modelo && python3 -I -m unittest discover -s scripts -p 'test_*.py'   # projeto modelo
  ```

- **O `projeto-modelo/` tem `TASKS.md`:** o hook `so_subagente_edita.py` nega a sessão principal editando código lá
  dentro. Delegue a um subagente.
- **Documentação:** o README e os `docs/` descrevem só o que existe no código. Mudou comando, flag ou caminho: atualize
  o texto no mesmo commit.
