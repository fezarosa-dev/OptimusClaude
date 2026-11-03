# Economia de tokens

Cada byte que entra na conversa é relido a cada resposta. A regra é uma só: **o que é bruto fica fora do contexto; entra só
a resposta.** As ferramentas abaixo fazem isso em camadas, e o `install.sh` deixa todas ligadas (lista e licenças em
[dependencias.md](dependencias.md)).

## As ferramentas

| Ferramenta | O que faz | Como se usa |
|---|---|---|
| **rtk** | Proxy de shell que filtra a saída dos comandos comuns (git, testes, grep, ls) | Automático, por hook: `git status` vira `rtk git status`. Nunca fuja dele chamando o binário por caminho absoluto. `rtk gain` mostra a economia |
| **caveman** / **ultracave** | Respostas curtas, sem enrolação, mantendo todo fato técnico; encolhe saída grande | `/caveman` ou `/ultracave` (skills do pacote do caveman); `caveman tools shrink -- <cmd>` para comando de saída longa que o rtk não filtra bem |
| **context-mode** | Roda o processamento num sandbox e devolve só o resultado; indexa saídas para busca depois | `ctx_execute`/`ctx_execute_file` para filtrar, contar e extrair; `ctx_batch_execute` para várias leituras de uma vez; `ctx_search` para retomar o que já foi visto |
| **Serena** | Navegação por símbolo via LSP: achar definição, quem chama, visão de um arquivo, sem ler o arquivo inteiro | `find_symbol`, `find_referencing_symbols`, `get_symbols_overview`, `replace_symbol_body` |
| **ccc** (cocoindex-code) | Busca semântica no código ("onde se trata o login?") | `ccc init && ccc index` ao começar um projeto; depois, busca pela skill `ccc` |

## Hábitos

### Busca e leitura

- Antes de ler, localize o ponto exato (grep, find, Serena, ccc) e leia só o trecho.
- Não leia o repositório inteiro nem arquivo grande por inteiro sem motivo. Não releia o que já leu, a menos que tenha mudado.
- Para editar, leitura normal (a edição precisa do texto exato). Para só entender, visão de símbolos ou `ctx_execute_file`.

### Saídas grandes

- Testes, builds, logs e lint: mostre só falhas e erros.
- Saída grande vai para arquivo; leia só o trecho que importa (ou processe com `ctx_execute_file`).
- Pesquisa verbosa (muitos arquivos, docs longas, logs) vai para um subagente, que devolve só o resumo.

### Conversa

- Curta e direta, sem repetir o pedido e sem recapitular o que foi feito.
- Edição pontual; nunca reescrever arquivo inteiro para mudar poucas linhas.
- Tarefa grande: plano curto e ok antes de implementar. Caminho errado: parar e avisar.

### Sessão

- **Sessão nova por fase**, com handoff: a conversa longa é o maior custo fixo por resposta.
- **Subagente para isolar contexto:** o log do teste fica no agente; a principal recebe o veredito.
- **Agrupe subtarefas mecânicas num agente só:** rodar N scripts num lote custa bem menos que N agentes, porque o custo
  fixo do spawn é pago uma vez.
- **Menor superfície de tools por agente** ([agentes-e-modelos.md](agentes-e-modelos.md)).
- **O que gasta licença roda só no diff** (revisões por IA, varreduras de segurança por agente); o que gasta só máquina
  (testes, linters, gitleaks) pode rodar em tudo.

## O que não fazer

- Rodar de novo um comando cuja saída foi cortada: recupere o trecho (o caveman e o context-mode guardam).
- Workflow multiagente para edição normal.
- Ligar roteamento que mande o conteúdo da sessão para um serviço de fora sem você decidir.
