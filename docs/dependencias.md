# Dependências

O que esta configuração usa, para que serve no fluxo, como instalar e se é obrigatória. O `install.sh` checa tudo isto e instala o que tem instalador seguro (`uv tool`, `npm -g`, `claude plugin`); o resto ele lista no fim, com o comando.

Legenda: **obrigatória** = as regras do `CLAUDE.md` contam com ela; **recomendada** = parte do fluxo fica capenga sem ela; **opcional** = só para quem usa aquilo.

## Ferramentas de linha de comando

| Ferramenta | Para que serve no fluxo | Como instalar | |
|---|---|---|---|
| Claude Code (`claude`) | A base de tudo | https://docs.claude.com/claude-code | obrigatória |
| git | Branches, worktrees, diff para revisão | gerenciador de pacotes do sistema | obrigatória |
| Node.js (`node`, `npm`) | Roda o context-mode e o caveman | https://nodejs.org, ou fnm/nvm | obrigatória |
| Python 3 | Painel da sessão, statusline, scripts em `~/.claude/scripts` (só biblioteca padrão) | gerenciador de pacotes do sistema | obrigatória |
| uv / uvx | Instala Serena, ccc e semgrep como ferramentas isoladas | `curl -LsSf https://astral.sh/uv/install.sh \| sh` | obrigatória |
| rtk (Rust Token Killer) | Proxy de bash: o hook reescreve `git status` em `rtk git status` e corta a saída que entra no contexto. O `CLAUDE.md` importa o `RTK.md` | https://github.com/rtk-ai/rtk (script de instalação ou `cargo`); depois `rtk init -g` para o hook, ou use o bloco `hooks` do `settings.example.json` | obrigatória |
| caveman (`@caveman-ai/cli`) | Respostas curtas (skill `caveman`), compressão da saída de comandos (`caveman shrink`, `caveman retrieve`) e MCP de recuperação | `npm i -g @caveman-ai/cli`, depois `caveman hooks install claude` (os hooks dele vão para o `settings.json` com caminho absoluto da sua máquina, por isso não estão no exemplo) | obrigatória |
| Serena (`serena-agent`) | MCP de navegação e edição por símbolo (`find_symbol`, `replace_symbol_body`), no lugar de ler arquivo inteiro | `uv tool install serena-agent` e `claude mcp add -s user serena -- serena start-mcp-server --context claude-code --project-from-cwd` | obrigatória |
| ccc (`cocoindex-code`) | Busca semântica no código (`ccc search`); `ccc init` e `ccc index` em cada projeto novo | `uv tool install cocoindex-code` | obrigatória |
| gh | PRs, CI e issues pelo terminal | https://cli.github.com | recomendada |
| jq | `install.sh --mesclar-settings` e a checagem do hook do rtk | gerenciador de pacotes do sistema | recomendada |
| curl | Avisos pelo ntfy.sh (skill `notify` e aviso antes de pergunta) | gerenciador de pacotes do sistema | recomendada |
| gitleaks | Varredura de segredos antes de commit/PR | https://github.com/gitleaks/gitleaks | recomendada |
| semgrep | Análise estática (skill `semgrep`, revisão de segurança) | `uv tool install semgrep` | opcional |
| App ntfy (celular) | Receber os avisos | Android/iOS; inscreva-se nos tópicos de `NTFY_TOPICO` e `NTFY_TOPICO_PERGUNTA` | recomendada |

## MCPs

| MCP | Para que serve | Como ligar | |
|---|---|---|---|
| serena | Símbolos do código (ver acima) | `claude mcp add` (o `install.sh` faz) | obrigatória |
| context-mode | Roda comandos e processa saída grande num sandbox; só o resultado entra no contexto (`ctx_execute`, `ctx_batch_execute`, `ctx_search`) | vem com o plugin `context-mode@context-mode` | obrigatória |
| caveman | Recupera o original de saídas comprimidas | `caveman mcp` (veja `caveman help tools`) | opcional |

## Plugins do Claude Code

Os marketplaces estão em `extraKnownMarketplaces` do `settings.example.json`; o `install.sh` roda `claude plugin marketplace add` e `claude plugin install` para cada um.

| Plugin | Marketplace (`claude plugin marketplace add`) | Para que serve | |
|---|---|---|---|
| `superpowers` | `anthropics/claude-plugins-official` | Skills de processo: `test-driven-development`, `verification-before-completion`, `systematic-debugging`, `writing-plans`, `using-git-worktrees`, `requesting-code-review`, `brainstorming` | obrigatória |
| `context-mode` | `mksglu/context-mode` | Ver MCPs | obrigatória |
| `ponytail` | `DietrichGebert/ponytail` | Modo "dev sênior preguiçoso": a menor mudança completa | recomendada |
| `claude-security` | `anthropics/claude-plugins-official` | Varredura de segurança do código e do diff | recomendada |
| `security-guidance` | `anthropics/claude-plugins-official` | Orientação de segurança enquanto edita | recomendada |
| `insecure-defaults` | `trailofbits/skills` | Auditoria de padrões inseguros (segredo de fallback, fail-open, cripto fraca) | recomendada |
| `code-simplifier` | `anthropics/claude-plugins-official` | Agente que simplifica o código recém-mexido | opcional |
| `claude-code-setup` | `anthropics/claude-plugins-official` | Recomenda automações (hooks, skills) para o projeto | opcional |
| `skill-creator` | `anthropics/claude-plugins-official` | Criar e medir skills | opcional |
| `pyright-lsp`, `typescript-lsp` | `anthropics/claude-plugins-official` | LSP de Python e TypeScript | opcional (conforme a linguagem) |
| `watermarks-remover` | `guillaumemeyer/watermarks-remover` | Limpa marcas de texto gerado (Unicode invisível) em texto para leitor | opcional |
| `brag` | `latent-spaces/brag` | Registro do trabalho feito | opcional |

Para stack específica, acrescente o plugin dela (ex.: `vercel@claude-plugins-official`, `cloudflare@cloudflare` com o marketplace `cloudflare/skills`).

## O que este repositório traz (feito pelo autor)

| Item | Onde fica depois de instalar |
|---|---|
| `CLAUDE.md`, `RTK.md` (regras globais) | `~/.claude/` |
| Agentes `runner`, `searcher`, `editor`, `researcher`, `doc-writer` (menor superfície de tools) | `~/.claude/agents/` |
| Workflows `fazer-revisar-corrigir` e `revisao-profunda` | `~/.claude/workflows/` |
| Skills `notify`, `painel`, `preflight`, `session-handoff`, `snote` | `~/.claude/skills/` |
| Comando `/stop` | `~/.claude/commands/` |
| Scripts `install_skills.py` (instala pacote de skills de um repositório git), `plugin_audit.py` (custo fixo em tokens dos plugins ligados), `vault_search.py` (busca no vault Obsidian, usado pelo `/snote`) | `~/.claude/scripts/` |
| Statusline avulsa (contexto, limites 5 h/semana, branch, modelo, tokens) | `~/.claude/statusline/statusline.py`; o exemplo usa a do painel (`~/painel-da-sessao/statusline.py`). Para a avulsa: `"command": "python3 \"$HOME/.claude/statusline/statusline.py\""` |
| Painel da sessão | `~/painel-da-sessao` |

Variáveis de ambiente (no `env` do `settings.json`): `NTFY_TOPICO` (avisos gerais), `NTFY_TOPICO_PERGUNTA` (aviso antes de pergunta que trava), `OBSIDIAN_VAULT` (só para `/snote`). Tópico do ntfy é público pelo nome: use sufixo aleatório (`python3 -c 'import secrets; print(secrets.token_hex(4))'`).

## Skills de terceiros (não vêm neste repositório)

Instale pela fonte de cada uma. Para pacotes de skills soltas (sem marketplace), `python3 ~/.claude/scripts/install_skills.py <dono/repo>` clona e liga em `~/.claude/skills`; para buscar, a skill `find-skills` (`npx skills find <assunto>`).

| Skill(s) | Fonte | Uso no fluxo | |
|---|---|---|---|
| `caveman`, `ultracave`, `megacave`, `caveman-*`, `investigate-first`, `lean-build`, `migration`, `safe-refactor`, `surgical-patch`, `verify-and-stop` | pacote do caveman (`@caveman-ai/cli`: `caveman skills install`) | Respostas terse; disciplinas de investigar antes, patch cirúrgico, refatoração segura, verificar e parar | obrigatória (`caveman`) |
| `ccc` | cocoindex-code | Como usar a busca semântica | obrigatória |
| `find-skills` | ecossistema `skills` (`npx skills`) | Achar skill que cubra a tarefa | recomendada |
| `test-driven-development`, `verification-before-completion` e demais de processo | plugin `superpowers` (acima) | TDD e verificação antes de declarar pronto | obrigatória |
| `code-ultrareview` | coroboros (MIT) | Revisão do diff em oito eixos | opcional |
| `firecrawl*` | https://github.com/firecrawl/skills e `firecrawl/firecrawl-workflows` | Pesquisa e extração da web | opcional |
| `llm-council` | skill pública "LLM Council" (cinco conselheiros + revisão anônima) | Decisão difícil sem perguntar ao usuário | opcional |
| `semgrep` | Semgrep | Regras e varredura estática | opcional |
| `humanizer-pt-br` | mackswendhell (MIT) | Tirar cara de IA de texto em português | opcional |
| `seo` | `addyosmani/web-quality-skills` | Qualidade web | opcional |

As skills de design de interface e animação (`emil-design-eng`, `animate`, `review-animations`, `shadcn`, `web-design-guidelines` etc.) são de terceiros e opcionais; instale as da sua stack.

## Mods de interface (do repositório)

`claude/mods/` (`status-bar` e `painel-agentes`) são plugins locais deste repositório, não dependência externa: o `install.sh` copia para `~/.claude/mods`, registra o marketplace local `optimus-mods` e instala os dois. Veja `claude/mods/README.md`.
