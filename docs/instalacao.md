# Instalação em detalhe

O resumo está no [README](../README.md#instalar-em-1-minuto). Aqui fica o que o instalador faz passo a passo, as opções,
o Windows, o WSL e o aviso no celular (ntfy).

## Pré-requisitos

- **Obrigatórios para rodar o instalador:** Python 3.9 ou mais novo e `git`.
- **Obrigatórios para o método funcionar:** [Claude Code](https://docs.claude.com/en/docs/claude-code) (`claude`),
  Node.js (`node`, `npm`), [uv](https://docs.astral.sh/uv/), `rtk`, `caveman`, Serena e `ccc`.
- **Recomendados:** `gh`, `jq`, `curl`, `gitleaks`. **Opcional:** `semgrep`.

Não precisa conferir tudo antes: o instalador diz o que falta e como instalar. Lista completa, com o porquê de cada
ferramenta: [dependencias.md](dependencias.md).

## Os comandos

```bash
git clone https://github.com/fezarosa-dev/OptimusClaude.git
cd OptimusClaude
python3 install.py --dry-run     # mostra o que faria, sem mudar nada
python3 install.py               # instala
```

O `./install.sh` faz o mesmo: confere se há `python3` 3.9 ou mais novo (e, se não houver, sugere o comando do
`apt-get`, `dnf`, `pacman`, `zypper` ou `brew`) e chama o `install.py` com as mesmas opções.

## O que o `install.py` faz, na ordem

1. **Copia os arquivos.** `claude/` vai para `~/.claude` (ou para `$CLAUDE_CONFIG_DIR`, se definida) e `painel/` vai
   para `~/painel-da-sessao`. Não copia `test_*.py`, `*.pyc` nem `__pycache__`. O `settings.example.json` é copiado com
   esse nome, nunca como `settings.json`. Arquivo igual ao que já está lá é pulado. Arquivo diferente: o antigo vai antes
   para `~/.claude/backups/optimusclaude-<data-hora>/`. Nada é apagado.
2. **Cuida do `settings.json`.** Se não existe `~/.claude/settings.json`, cria um a partir do exemplo, com
   `<placeholders>` no `env` para você trocar. Se já existe, não mexe (a não ser com `--mesclar-settings`, abaixo).
   Depois confere se o hook do `rtk` está lá e avisa se não estiver.
3. **Confere as dependências.** Para cada uma, diz `ok` ou `FALTA`. Instala sozinho só o que tem instalador seguro:
   `caveman` por `npm i -g @caveman-ai/cli`; Serena, `ccc` e `semgrep` por `uv tool install` (sem `uv`, sugere `pipx`).
   O resto (git, node, uv, rtk, gh, jq, gitleaks, curl) ele só sugere.
4. **Liga o Claude Code.** Se o `claude` está no PATH: registra o MCP da Serena (`claude mcp add -s user serena ...`),
   adiciona os marketplaces e instala os plugins (`superpowers`, `context-mode`, `ponytail`, `claude-security` e outros),
   e registra o marketplace local `optimus-mods` com os mods `status-bar` e `painel-agentes`. Sem `claude`, pula esta
   etapa e anota.
5. **Mostra o resumo.** "Tudo certo" ou a lista **Falta fazer**, um item por linha, com o comando sugerido.
6. **Mostra o orçamento de contexto.** Roda o `orcamento_contexto.py`: quantos tokens entram em toda sessão antes de você
   digitar nada (veja [Economia de tokens](economia-de-tokens.md)).

Rodar de novo é seguro: o que já está certo é pulado.

## O que ele não faz

- **Não sobrescreve um `settings.json` que já existe.** Para mesclar o exemplo no seu, use `--mesclar-settings`: objetos
  são mesclados, listas são juntadas sem duplicar (as suas primeiro), e em valor simples o seu vence. Ele mostra o diff e
  pergunta `[s/N]` antes de gravar; o anterior vai para o backup.
- **Não instala o `rtk` nem o Claude Code.** Diz onde achar.
- **Não usa `sudo`** nem instala pacote do sistema.
- **Não traz as skills de terceiros** (`caveman`, `find-skills`, `grilling` e outras): veja [dependencias.md](dependencias.md).

## Opções

| Opção | O que faz |
|---|---|
| `--dry-run` | Mostra o que faria (cópias, `settings.json`, instalações, plugins), sem gravar nada |
| `--so-checar` | Não grava nada nem tenta instalar: só confere e lista o que falta e quais arquivos seriam copiados |
| `--sem-plugins` | Pula marketplaces e plugins do Claude Code (o MCP da Serena continua) |
| `--sem-skills` | Pula as skills de terceiros que o método usa (`grill-me`, `grilling`, `find-skills`, `playwright-cli`, `security-and-hardening`, `security-threat-model`, `semgrep`), instaladas com `npx skills add` |
| `--mesclar-settings` | Mescla o exemplo no seu `~/.claude/settings.json`, com diff e confirmação |
| `--help` | Mostra a ajuda |

Abra uma sessão nova do Claude Code depois de instalar, para ela carregar a configuração.

## Depois de instalar: o `settings.json`

No `env` do `~/.claude/settings.json`, troque os placeholders:

| Variável | Para quê | Obrigatória? |
|---|---|---|
| `NTFY_TOPICO` | Avisos gerais no celular (skill `notify`, resumo do modo noturno) | não; sem ela não há aviso |
| `NTFY_TOPICO_PERGUNTA` | Aviso antes de uma pergunta que trava o trabalho | não; sem ela o Claude pergunta direto |
| `OBSIDIAN_VAULT` | Pasta do seu vault, só para o `/snote` | não |

O exemplo também traz: os quatro hooks (rtk, `ler_grande.py`, `so_subagente_edita.py`, `contexto_baixo.py`), a linha de
status do painel, `attribution` vazio e `includeCoAuthoredBy: false` (nada de coautoria de IA), `language: portuguese`,
`model: opus`, permissões que negam ler `.env`, `~/.ssh` e as credenciais do Claude, e os plugins ligados.

## Aviso no celular (ntfy)

O [ntfy](https://ntfy.sh) manda notificação para o celular por um "tópico": quem assina o tópico recebe as mensagens.

1. Instale o app ntfy no celular (Android ou iOS).
2. Crie dois nomes de tópico com sufixo aleatório:
   ```bash
   python3 -c 'import secrets; print(secrets.token_hex(4))'
   ```
   Por exemplo `meus-avisos-<sufixo>` e `minhas-perguntas-<sufixo>`.
3. Ponha os nomes em `NTFY_TOPICO` e `NTFY_TOPICO_PERGUNTA`, no `env` do `~/.claude/settings.json`, e assine os dois no app.
4. **O tópico é público pelo nome.** Quem souber o nome lê as mensagens. Por isso o sufixo aleatório, e por isso a
   mensagem leva só o assunto curto ("2 decisões de desenho"): nunca dado de cliente, senha, token, caminho interno nem
   código.

Quem manda o quê:

| Quem | Tópico | Quando |
|---|---|---|
| Regra "Pergunta ao usuário" do `claude/CLAUDE.md` | `NTFY_TOPICO_PERGUNTA` | Antes de toda pergunta que trava o trabalho (`curl ... "ntfy.sh/$NTFY_TOPICO_PERGUNTA"`) |
| Skill `notify` | `NTFY_TOPICO` | Quando você pede "me avisa quando terminar" |
| `scripts/noite.py` | `NTFY_TOPICO` | No fim do modo noturno, com o resumo |

A resposta em si não passa pelo ntfy: você responde na aba **Perguntas** do painel (pelo celular, na mesma rede) ou na
própria conversa. Veja [painel/README.md](../painel/README.md#perguntas-pelo-celular).

## No Windows

Há dois caminhos. A diferença é o painel da sessão: ele é copiado nos dois, mas a leitura de sessões usa informações do
sistema que só o Linux oferece (`/proc`, `ps`, `ip`), então no Windows nativo parte dele pode não funcionar.

| | Windows nativo (`install.ps1`) | WSL (`install.sh`) |
|---|---|---|
| Regras, agentes, skills, workflows, mods | sim | sim |
| Linha de status (contexto, limites, branch) | sim, a avulsa | sim, a do painel |
| Painel da sessão e perguntas pelo celular | sim, com aviso: a leitura de sessões depende de `/proc`, `ps` e `ip` | sim |
| Quando escolher | Você usa o Claude Code direto no Windows e não precisa do painel | Você quer o kit completo |

### Windows nativo

Abra o PowerShell:

```powershell
git clone https://github.com/fezarosa-dev/OptimusClaude.git
cd OptimusClaude
powershell -ExecutionPolicy Bypass -File .\install.ps1 --dry-run   # mostra o que faria, sem mudar nada
powershell -ExecutionPolicy Bypass -File .\install.ps1             # instala
```

O `install.ps1` procura um Python 3.9 ou mais novo (`python`, `python3` ou `py -3`; o atalho da Microsoft Store não
conta). Se não achar e houver `winget`, oferece `winget install Python.Python.3.12`. Depois chama o mesmo `install.py`,
que no Windows:

- copia `claude\` para `%USERPROFILE%\.claude` e o painel para `%USERPROFILE%\painel-da-sessao`, com o aviso sobre
  `/proc`, `ps` e `ip`;
- se criar o `settings.json`, aponta a linha de status para a avulsa (`~\.claude\statusline\statusline.py`) e chama o
  Python de `python`;
- para o que falta, só sugere o comando do `winget` (`winget install Git.Git`, `OpenJS.NodeJS.LTS`, `astral-sh.uv`,
  `GitHub.cli`, `jqlang.jq`, `Gitleaks.Gitleaks`), sem instalar.

O `-ExecutionPolicy Bypass` libera só esta execução, porque o Windows bloqueia scripts baixados por padrão. Se você já tem
Python, também dá para chamar direto: `py -3 install.py --dry-run`. As opções são as mesmas. O Claude Code no Windows usa
o Git Bash, que vem com o Git for Windows.

### WSL (kit completo)

O WSL roda um Linux de verdade dentro do Windows. É o caminho recomendado se você quer o painel.

1. No PowerShell como administrador: `wsl --install` (instala o Ubuntu) e reinicie.
2. Abra o Ubuntu pelo menu Iniciar e instale o Claude Code e as dependências dentro dele.
3. Clone o repositório **dentro do Linux** (em `~`, não em `/mnt/c/...`, que é bem mais lento) e rode `./install.sh`.
4. O painel abre no navegador do Windows em `http://127.0.0.1:8765`: o WSL repassa a porta sozinho.

## O que já foi testado

O `install.py` tem testes automáticos: `python3 -m unittest test_install` (cópia, backup, `--dry-run`, `--so-checar`,
mescla do `settings.json`). Os embrulhos e o caminho Windows ainda não foram testados num Windows de verdade, e o macOS não
foi testado. Se algo falhar, abra uma issue com a saída (veja o [SUPPORT.md](../SUPPORT.md)).
