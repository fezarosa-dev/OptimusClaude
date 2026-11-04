# Painel da sessão

Painel web local que mostra o andamento de uma sessão do Claude Code: tarefas com %, agentes, workflows, shells em
segundo plano, baterias de teste, worktrees, consumo de tokens, limites de uso (5 h e semana) e as perguntas abertas, que
dá para responder pelo celular na mesma rede. Python 3 puro (só a biblioteca padrão), sem CDN, sem dependência.

Ele só **lê** o projeto e os registros da sessão. Escreve apenas na própria pasta: `respostas/`, `chave.txt`,
`config.json`, `perguntas.json` (vazio na primeira vez), `servidor.log` e `servidor.pid`.

Funciona em Linux (usa `/proc`, `ps`, `ip` e, se houver, `systemctl --user` e `docker`). Fonte que falta não derruba o
painel: o quadro correspondente fica vazio, e erro inesperado de uma fonte aparece em vermelho no topo.

## Instalar

```bash
cp -r painel ~/painel-da-sessao        # o painel roda de onde estiver; ~/painel-da-sessao é o lugar padrão
cd /caminho/do/seu/projeto
python3 ~/painel-da-sessao/ativar.py "$PWD"
```

`ativar.py` cria o `config.json` a partir do `config.example.json` na primeira vez, aponta `projeto` (raiz do git do
diretório dado), `worktrees`, `sessoes` (`~/.claude/projects/<projeto com - no lugar de / >`), `saidas`
(`/tmp/claude-<uid>/...`) e `sessao`, reinicia o servidor se algo mudou e imprime os endereços:

```
PC:      http://127.0.0.1:8765
celular: http://192.168.0.10:8765/?chave=...
```

Outros comandos, sempre de dentro da pasta do painel:

```bash
python3 iniciar.py                      # sobe em segundo plano (se já não estiver no ar) e mostra os endereços
kill $(cat servidor.pid)          # para
python3 testar.py                 # testes ligados ao que mudou (diff + não commitado + novos)
python3 testar.py --so-decidir    # só mostra quais rodariam
python3 testar.py --tudo          # todos (= python3 -m unittest discover -p 'test_*.py' -q)
```

A skill `/painel` (em `claude/skills/painel`) só roda o `ativar.py` com o diretório da sessão.

## Configuração (`config.json`)

Copie de `config.example.json` (o `ativar.py` faz isso). Os caminhos do projeto são relativos à raiz do projeto.

| chave | padrão | para quê |
|---|---|---|
| `projeto`, `sessoes`, `saidas`, `worktrees`, `sessao` | preenchidos pelo `ativar.py` | onde ler; `sessao` vazio = a sessão mais recente |
| `worktrees_relativo` | `../wt` | pasta dos worktrees, relativa ao projeto |
| `porta`, `escutar` | `8765`, `0.0.0.0` | onde o servidor escuta (`PORTA` e `ESCUTAR` no ambiente vencem) |
| `ativo_segundos` | `120` | sem sinal há mais que isso, o agente não conta como ativo |
| `leva_a_partir_de` | `1` | tarefas com número menor ficam fora (salvo se tiverem worktree) |
| `fase_final_horas` | `2` | horas somadas à previsão para revisão e publicação |
| `ramo`, `ramo_base` | `dev`, `origin/main` | ramo de integração e ramo base (worktree "na dev", linhas desde a base) |
| `arquivo_tarefas` | `TASKS.md` | lista de tarefas |
| `arquivo_duvidas` | `duvidas.md` | dúvidas abertas e avisos |
| `secao_avisos` | `## Avisar` | cabeçalho da seção de avisos dentro do arquivo de dúvidas |
| `arquivo_publicacao` | `docs/publicacao-pendente.md` | itens que esperam publicação (conta as linhas `- `) |
| `registros_baterias` | `registros/baterias` | registros `.md` de baterias passadas (base da previsão) |
| `cache` | `~/.cache` | onde ficam os logs de bateria e a trava dos testes |
| `bateria_logs` | `bateria-*.log` | nome dos logs de bateria em `cache`; o `*` é o nome do worktree |
| `bateria_comando`, `bateria_cadeia` | `testar_como_o_ci.py`, `encadear-baterias` | processos que indicam bateria rodando e fila de baterias |
| `testes_de_tela_total` | `0` | total de testes de tela, para a barra da bateria (0 = desconhecido) |
| `trava_testes` | vazio | pasta-trava dentro de `cache` (com `dono.json`); vazio = não mostra |
| `fatia_testes` | vazio | fatia do systemd (`*.slice`) dos testes, para o quadro de memória; vazio = não mostra |
| `teto_memoria_mb` | `8192` | teto de memória que o quadro do sistema usa como 100% |
| `limites` | `~/.cache/claude-limites` | onde a `statusline.py` grava os limites |

## Convenções que ele lê

Nada disso é obrigatório: sem o arquivo, o quadro fica vazio.

- **Tarefas** (`arquivo_tarefas`): um cabeçalho `## T12 · Título` ou `### T12 · Título` por tarefa (faixa:
  `### T12 a T15 · ...`) e uma linha `- **Estado:** ...`. O começo do estado decide: `registrada`/`planejada`/`proposta`
  = fila; `em andamento`/`em implementação` = andando; `esperando`/`dúvida`/`bloqueada` = bloqueada; `feita`,
  `na dev`, `na main`, `publicada`, `no ar` = concluída.
- **Branches e worktrees**: o número da tarefa sai do nome (`feat/t12-algo`, `wt/t12`). Worktree com commits à frente
  do `ramo` = andando; já com merge no `ramo`, limpo e sem workflow = concluída.
- **Dúvidas** (`arquivo_duvidas`): blocos `### D-1. Título` (ou `P-1`), com `- Situação: ...` e
  `- Opções: (a) ...; (b) ...`; o bloco com `**Resposta` está fechado. A seção que começa com `secao_avisos` vira o
  quadro de avisos.
- **Workflows**: o rótulo dos agentes leva o número da tarefa (`T12 revisar 2` = tarefa T12, etapa Revisar, rodada 2).
- **Baterias**: o log `<cache>/<bateria_logs>` com linhas `::: etapa`, `✓ 12 [...]`/`✘ 13 [...]` dos testes de tela e
  o resumo `=== resumo` seguido de `OK  nome`, `FALHOU  nome`, `PULADO  nome`.

## A % de trabalho feito

Cada tarefa tem um percentual estimado: concluída 100; bateria rodando 90; workflow em curso pela fração de agentes
terminados (até 95); branch à frente do ramo 85; começando 40; na fila ou bloqueada 0. O anel da Visão geral é a
**média** desses percentuais (a nota embaixo diz quantas estão concluídas). Um workflow conta como em curso enquanto não
gravou o `<runId>.json` final e teve sinal nas últimas 2 h, inclusive entre um passo e outro, quando nenhum agente está
vivo. O denominador da fração é o total de passos planejado no `args.tarefas` do lançamento (tarefa sem `passos` conta
1), então a % não cai quando o workflow lança um passo novo; sem `args.tarefas` (ou sem o lançamento na sessão), volta a
contar os agentes já lançados, e aí ela ainda pode cair.

## Perguntas pelo celular

A sessão do Claude mantém o `perguntas.json` desta pasta (lista; começa `[]`):

```json
[{"id": "D-3", "header": "Ordem", "pergunta": "Qual fazer primeiro?", "multiplas": false,
  "opcoes": [{"rotulo": "A", "descricao": "...", "recomendada": true}, {"rotulo": "B"}], "contexto": "opcional"}]
```

As dúvidas abertas do `arquivo_duvidas` que não estão no JSON aparecem também. Responder grava
`respostas/pendentes/<data-hora>-<id>.json` (escrita atômica, até 30 por hora). A sessão roda `python3 esperar_resposta.py` em
segundo plano: ele espera, imprime `RESPOSTA <json>` da mais antiga, move o arquivo para `respostas/entregues/` e sai.

## Segurança

- De `127.0.0.1` o painel abre sem chave. De qualquer outro endereço, só com a chave de `chave.txt` (gerada na primeira
  vez, modo 600). O link `/?chave=...` vira um cookie HttpOnly e a chave sai da URL. Sem chave: 403, sem dado nenhum.
- **A chave nunca vai para commit.** O `.gitignore` desta pasta já deixa de fora `chave.txt`, `config.json`,
  `perguntas.json`, `respostas/`, `servidor.log` e `servidor.pid`. Trocar a chave: pare o servidor, apague `chave.txt`,
  suba de novo (o celular precisa do link novo).
- É HTTP sem TLS: use só em rede local de confiança, nunca em Wi-Fi aberta. Para não abrir para a rede, use
  `"escutar": "127.0.0.1"`.
- O `Host` aceito é só 127.0.0.1, localhost, os IPs das placas de rede e o nome da máquina (contra DNS rebinding); o
  POST exige o cabeçalho `X-Painel` e a mesma origem.
- **Pergunta não leva dado sensível**: o texto do `perguntas.json` aparece no celular. Nada de senha, token, dado de
  cliente ou documento. Comandos, saídas e rótulos passam por `mascarar()` (tokens, chaves, senha em URL, cookies,
  CPF/CNPJ, e-mail, telefone), mas isso é rede de proteção, não licença.

## Limites (5 h e semana) e a statusline

A statusline do Claude Code recebe `rate_limits` (percentual usado e hora do reset das janelas de 5 h e da semana, para
assinantes), custo, contexto e duração. `statusline.py` lê esse JSON do stdin, devolve a linha de status e grava em
`~/.cache/claude-limites` (ou `$CLAUDE_LIMITES_DIR`): `sessoes/<session_id>.json` (retrato da sessão, sem transcript) e
`historico.jsonl` (uma linha quando a % ou o reset muda). O painel mostra a % e o tempo que falta de cada janela, o
ritmo e a previsão de chegar a 100% antes do reset. Para ligar, em `~/.claude/settings.json`:

```json
{"statusLine": {"type": "command", "command": "python3 ~/painel-da-sessao/statusline.py"}}
```

## O que cada aba mostra

- **Visão geral**: % de trabalho feito, fase, o que está rodando agora, workflows em curso (etapas, tarefas, agentes,
  tempo e tokens), linhas desde a base por categoria, previsão de término.
- **Rodando**: shells em segundo plano da sessão (vivos pelo `/proc`, os últimos que terminaram), bateria e agentes.
- **Perguntas**, **Tarefas**, **Agentes** (modelo, effort, último sinal e última fala), **Consumo** (tokens por origem,
  modelo e workflow, tempo de agentes e tempo real), **Baterias** e **Sistema** (worktrees, merges, memória, contêineres).
- Busca (atalho `/`), filtros por estado, tipo, modelo e workflow, e o botão **Recarregar**, que zera os caches.
