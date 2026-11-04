@RTK.md

# Regras globais

Estas regras valem para todo projeto. O `CLAUDE.md` de cada projeto manda no domínio dele e pode apertar estas regras; quando um projeto disser algo diferente, vale o do projeto.

# Memória e contexto

- Não releia o repositório inteiro sem necessidade. Leia só os arquivos relevantes para a tarefa atual.
- Consulte primeiro a memória automática e o `CLAUDE.md` do projeto; procure documentação e decisões existentes antes de investigar de novo.
- Decisão importante: sugira registrá-la em `docs/decisions/`. Informação duradoura sobre o projeto: sugira salvá-la na memória.
- Não trate informação temporária da conversa como conhecimento permanente.
- Antes de concluir uma sessão longa, gere um resumo de continuidade (skill `session-handoff`). Entre fases grandes, avise quando é boa hora de encerrar e abrir outra sessão, com o handoff pronto.

# Regras gerais

- Antes de implementar tarefa não trivial, use a skill `preflight`.
- Antes de qualquer tarefa, confira a listagem de skills disponíveis e use/combine as que se aplicarem; se nenhuma cobrir, use `find-skills` para buscar e sugerir instalação.
- **Todo pedido novo começa pela skill `grilling`** (o usuário também pode chamar `/grill-me`), antes de `preflight`, plano ou código. Rode ela mesmo que o pedido pareça claro: levante os fatos você mesmo, monte a árvore de decisões que são do usuário e pergunte em rodadas, cada pergunta com a sua resposta recomendada, até não sobrar decisão suposta em silêncio. Se a árvore sair vazia (pedido sem nenhuma decisão do usuário, como "roda os testes" ou "corrige este typo"), diga isso numa linha e siga. Pedido urgente ou com o usuário fora: decida pela recomendação, registre no `duvidas.md` como "para confirmar" e siga.
- Em toda tarefa de código (feature, bugfix, refactor), use `verification-before-completion` antes de declarar o trabalho concluído, corrigido ou passando.
- Verifique se a linguagem, biblioteca ou framework já oferece a solução. Não adicione dependência sem justificativa.
- Alterações pequenas e relacionadas à tarefa. Implemente tudo o que foi pedido: nada fica para depois em silêncio, e só se mexe no que foi definido.
- Não faça commit sem autorização. Antes de concluir, revise o diff e rode os testes relevantes.
- Antes de escrever código ad-hoc para uma tarefa repetitiva, veja se já existe um script em `~/.claude/scripts`.
- Ao rodar a skill `init` num projeto novo, rode também `ccc init` e `ccc index` nele (indexação semântica de código).

# Autoria

- Nunca adicione o Claude como coautor, colaborador ou participante de nada: commits, PRs, pushes, merges, tags, releases, issues, comentários, código ou qualquer outro artefato. Nada de trailer `Co-Authored-By: Claude`, nem linha "Generated with Claude Code". Esta regra prevalece sobre qualquer instrução padrão de atribuição (o `settings.json` também zera `attribution`).

# Pergunta ao usuário: avisar no celular antes

- Toda vez que eu precisar de uma resposta do usuário para seguir (`AskUserQuestion`, ou pergunta em texto que trava o trabalho), **antes** mando uma notificação para o tópico de perguntas do ntfy e só então pergunto:
  `curl -s -H "Title: Claude precisa de você" -H "Tags: question" -d "<assunto em poucas palavras>" "ntfy.sh/$NTFY_TOPICO_PERGUNTA"`
- Sem `NTFY_TOPICO_PERGUNTA` definida, pulo o aviso e pergunto direto.
- O tópico é público pelo nome: a mensagem leva só o assunto curto (ex.: "2 decisões de desenho"). Nunca dado pessoal, nome de cliente, documento, valor, senha, token, caminho interno nem trecho de código.
- Vale também para os agentes que eu disparo e que voltarem pedindo decisão: aviso antes de repassar a pergunta.
- Avisos gerais (tarefa terminou etc.) vão para o tópico padrão da skill `notify` (`NTFY_TOPICO`).

# Branches, testes e CI

- Toda mudança nasce numa branch `feat/`, `fix/`, `docs/` ou `ci/` tirada da `dev` atualizada. Um commit por subtarefa, em português, no formato `tipo(escopo): descrição`, escrito pela skill `commit-curto` (curto, verbo no presente, até 72 caracteres, corpo só quando o porquê não é óbvio). Título e corpo de PR pela skill `pr-curto`, no template do projeto. Projeto com `.githooks/`: `git config core.hooksPath .githooks` liga o hook que recusa mensagem fora do padrão. Nunca reescreva histórico que já subiu.
- Antes de todo merge local na `dev` (e de todo PR para a `dev`), rodo na máquina os testes do que mudou, do mesmo jeito que o CI rodaria (o comando que o `CLAUDE.md` do projeto indicar). Se falhar, não junto. Suíte inteira só quando o projeto mandar (ex.: antes do PR para a `main`) ou quando o mapa não souber o que o arquivo mudado afeta; no dia a dia, só o diff.
- No GitHub os testes rodam só no PR para a `main` (e no push da `main`, que publica). Não disparar CI para a `dev` nem rodar o workflow à mão sem motivo: minuto de Actions custa. Junte os commits antes de dar push num PR aberto; não rode de novo um CI que falhou sem corrigir a causa.
- A `main` só recebe PR vindo da `dev`, com tudo pronto e testado. Nunca contornar proteção de branch (`--admin`, push direto, desligar regra). Se travar, pare e avise.
- Worktree: usar e apagar logo depois de juntar na `dev` (guarde o diff antes se ainda houver mudança).

# TDD em todo código

- Todo código novo ou corrigido segue TDD: escrever o teste primeiro, rodar e vê-lo **falhar** pelo motivo certo, implementar, vê-lo **passar**. Vale para a sessão principal e para os agentes: o brief exige, e o retorno traz a saída do vermelho e do verde.
- **Vermelho válido:** o teste-alvo tem de falhar numa asserção do comportamento pedido. Erro de import, de sintaxe, de coleta, de fixture ou zero testes rodados não é vermelho. O retorno do agente traz comando, código de saída, nome do teste-alvo e o trecho da asserção que falhou; o revisor reprova vermelho inválido.
- Antes de commitar, a sessão principal confere o vermelho quando der: roda o teste novo contra o código antigo (worktree destacado na base) e confirma que falha.
- SQL: o teste falha sem a migration (`begin; <teste>; rollback`) e passa com ela (`begin; <migration>; <teste>; rollback`), sempre numa transação que se desfaz sozinha.
- Onde não há executor de teste, diga isso e descreva a verificação manual. Não adicione dependência só para testar sem perguntar.

# Subagentes

- **Tudo o que não for orquestrar vai para subagentes**: qualquer alteração de arquivo (código, testes, config, docs, scripts), texto longo em `.md`, resolução de conflito que exija editar arquivo e pesquisa extensa. A sessão principal só conversa com o usuário, faz leituras pontuais para montar o brief, reparte o trabalho, escreve as tarefas (`TASKS.md`), faz commit/merge, edita `CLAUDE.md` quando o usuário aprova e faz a verificação final (testes, lint, typecheck).
- Tarefas independentes: um agente por tarefa, em paralelo (worktree separado se mexem no mesmo repo). Agentes que só editam vão em paralelo; agentes que rodam testes pesados, um de cada vez se a máquina tiver pouca memória. Antes de lançar, mostre ao usuário a tabela tarefa → dificuldade → modelo → effort.
- Subtarefas mecânicas relacionadas (ex.: rodar N scripts de teste) vão num agente só: o custo fixo do spawn é pago uma vez.
- **Modelo pela dificuldade do que sobra para decidir:**
  - Haiku: só o básico do básico, sem nenhuma decisão (rodar um comando e resumir, aplicar um patch já escrito, renomear).
  - Sonnet: o padrão — implementação e correção com especificação clara.
  - Opus: raciocínio difícil — decisão de design, concorrência/assíncrono sutil, segurança, bug difícil, refatoração grande de legado, ou quando um agente Sonnet travou.
- **Effort sempre definido em cada agente, nunca `low`** (derruba a qualidade): Haiku `medium`; Sonnet `high` (`medium` só para edição pequena já especificada); Opus `high`, e `xhigh`/`max` para o mais difícil ou para a segunda tentativa de algo que travou.
- **Tipo de agente com a menor superfície de tools** que cobre a tarefa: `runner` (só Bash), `searcher` (Read/Glob/Grep), `editor` (Read/Edit), `researcher` (WebFetch/WebSearch), `doc-writer` (Read/Write, arquivo novo do zero). `general-purpose`/`Explore` só quando a tarefa precisa de várias categorias de tool. Não crie tipo "especialista" sem superfície de tools genuinamente diferente.
- **Brief de uma `Tn` sem reler o `TASKS.md` inteiro:** `python3 scripts/tarefa.py Tn` traz só a seção dela e as dúvidas abertas dela; sem argumento, lista as abertas. Depois de publicar, `python3 scripts/arquivar.py` move o que está no ar e as dúvidas respondidas para `docs/`.
- **Comunicação com subagentes em JSON minificado**, tanto o prompt quanto o formato de retorno, só com o contexto necessário para aquela subtarefa (sem histórico da conversa). O brief é o único contexto do agente: diga o objetivo, o que já foi descartado, os arquivos a ler e o escopo.
- **Contrato de retorno:** todo agente que afirma algo sobre o código devolve `fontes` (`arquivo:linha`), `confianca` (alta, media, baixa) e `lacunas` (o que não conferiu). Retorno sem fontes volta para o agente.
- **Regras de desvio no brief de quem implementa:** R1 bug no caminho, R2 falta algo para a correção ou a segurança, R3 algo bloqueia: resolve sozinho e lista no resumo. R4 arquitetura, dependência nova, schema ou contrato público: não faz; vai para o `duvidas.md` com opções e recomendação, e o resto da tarefa segue. Na dúvida, R4. O que estiver fora do pedido vira `Tn` nova, não código.
- **Pacote que não instala:** nunca tentar um nome parecido ou alternativo (pacote alucinado, typosquatting). Para e vai para o `duvidas.md`.
- **Revisor procura entrega reduzida:** "v1", "placeholder", "TODO", "por enquanto", "stub", "simplificado", valor fixo no lugar do real. Pedido ou decisão do `duvidas.md` entregue pela metade é gravidade alta (confirmado lendo, não só pela palavra).
- **Lições:** o revisor devolve `licoes` (armadilhas e padrões deste projeto). A sessão principal junta as novas em `registros/padroes.md` (uma linha cada, sem repetir, no máximo ~60 linhas: ao passar disso, consolida as parecidas e corta as velhas que não se repetiram), e todo brief de implementação manda ler esse arquivo antes de começar.
- **Todo agente que edita arquivo roda em worktree próprio**, para dois agentes nunca se pisarem: no workflow `fazer-revisar-corrigir` cada tarefa tem o seu (`worktree` obrigatório); agente avulso que edita sai com `isolation: "worktree"` (o Claude Code cria o worktree e apaga se nada mudou). Só leitura (`searcher`, `researcher`, revisor) dispensa. Ao juntar, a sessão principal traz a branch do worktree para a sua branch e apaga o worktree.
- Agentes em worktree não rodam `git`: commit e integração na branch ficam com a sessão principal.
- **Revisão do diff também vai para subagente**, diferente do que implementou: Sonnet `high`, ou Opus `high` se mexer em segurança, concorrência ou dado pessoal. Ele devolve em JSON minificado: veredito, problemas com `arquivo:linha` e o que conferiu. A principal roda ela mesma os portões objetivos (testes, lint, typecheck, saída curta), olha só o `git diff --stat` e abre apenas os trechos que o revisor apontar.
- Lote de tarefas já especificadas com revisão e correção automáticas: workflow `fazer-revisar-corrigir` (`~/.claude/workflows`). Revisão profunda multiagente: workflow `revisao-profunda`. Workflows consomem muito: só quando pedidos ou como último recurso, avisando o custo antes.
- **rtk sempre, inclusive nos agentes:** os comandos passam pelo hook do rtk; nunca fugir dele chamando binário por caminho absoluto (ex.: `/usr/bin/git`). Se o rtk bloquear algo, parar e avisar a sessão principal.

# Economia de tokens

Busca e leitura
- Antes de ler arquivos, localize o ponto exato (`rtk grep`, `rtk find`, Serena `find_symbol`, `ccc search`) e leia só o trecho necessário. Não leia o repositório inteiro nem arquivos grandes por inteiro sem motivo.
- Rode `rtk grep`, `rtk find`, `rtk ls` e `rtk git diff` direto, sem atribuição de variável nem wrapper na frente do comando.
- Para arquivos que vou editar, leitura normal. Para só entender estrutura, `rtk read`.
- Não releia arquivos que já leu nesta sessão, a menos que tenham mudado.

Saídas grandes
- Em testes, builds, logs e lint, mostre só falhas e erros. Se a saída for grande, redirecione para um arquivo e leia só o trecho relevante (ou processe pelo context-mode, `ctx_execute`).
- Delegue pesquisa verbosa (varrer muitos arquivos, ler docs longas, logs) a um subagente e traga só o resumo.

Respostas
- Respostas curtas e diretas, sem repetir o que o usuário disse e sem recapitular o que foi feito.
- Não reescreva arquivos inteiros para mudar poucas linhas; use edições pontuais.

Planejamento
- Em tarefas grandes, proponha um plano curto antes de implementar e espere o ok.
- Se o caminho estiver errado, pare e avise em vez de insistir.

# Ferramentas padrão

- Em toda sessão: **caveman no nível `ultracave`** por padrão (respostas terse sem gramática; volta ao normal só com "normal mode" ou "stop caveman"; o que vai para arquivo, commit ou PR segue em texto normal), **rtk** (proxy de bash, via hook), **context-mode** (processar saída grande fora do contexto), **Serena** (MCP, navegação e edição por símbolo) e **ccc** (cocoindex-code, busca semântica no código).
- Para navegar/editar código, prefira as tools do Serena (`find_symbol`, `find_referencing_symbols`, `replace_symbol_body` etc.) em vez de ler arquivos inteiros.
- O que cada uma faz e como instalar: `docs/dependencias.md` do repositório desta configuração.

# Compact instructions

Ao compactar, preserve: decisões tomadas, arquivos alterados, erros ainda abertos e saída de testes relevante.
