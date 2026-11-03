# Agentes e modelos

## Quem faz o quê

| Papel | Faz | Não faz |
|---|---|---|
| **Você** | Pede, decide, responde as dúvidas, pede a publicação | Não precisa acompanhar cada passo |
| **Sessão principal** (o melhor modelo, effort alto) | Conversa; lê só o que precisa para montar o brief; escreve `TASKS.md` e `duvidas.md`; cria worktree; commita, junta e faz push; roda testes, lint e typecheck; edita o `CLAUDE.md` quando você aprova | Não escreve código nem texto longo; não lê o diff inteiro |
| **Agente que faz** | Código, testes, configuração, documento longo, conflito que exige editar, pesquisa extensa. Devolve JSON | Não roda `git`; não sai do worktree dele |
| **Agente que revisa** | Lê o diff, tenta derrubar, devolve problemas com `arquivo:linha` e gravidade. Só lê | Não altera arquivo; nunca é o mesmo que fez |

**Por que a principal não escreve código:** o contexto dela fica para orquestrar e decidir. Um agente a mais custa pouco
perto de encher a conversa principal de diff e log, que ela relê a cada resposta.

**Por que agente não roda `git`:** só a sessão principal decide o que entra no histórico. Em ambiente com guarda, a
própria guarda bloqueia.

## Modelo e effort: pela dificuldade que sobra

Escolha pelo que **sobra de decisão** na tarefa, não pela área. Um achado já especificado ("no arquivo X, linha Y, falta
conferir a permissão; o teste esperado é Z") é fácil mesmo em código de segurança. Antes de cada agente: o **mais barato
que mantém a qualidade**, com o porquê numa linha.

| Modelo | Quando | Effort |
|---|---|---|
| **Haiku** | Sem decisão: rodar um comando e resumir, extrair de log, converter, aplicar patch já escrito, renomear | `medium` |
| **Sonnet** | O padrão: implementação com especificação clara (com TDD), revisão de diff comum, análise só de leitura | `high` para implementar; `medium` para edição pequena já especificada e para revisor de diff comum |
| **Opus** | Raciocínio difícil: desenho em aberto, concorrência sutil, causa desconhecida, refatoração grande de legado, segunda tentativa de algo que travou | `medium` se especificado; `high` com decisão aberta; `xhigh`/`max` para o mais difícil ou a 2ª tentativa |

- **Nunca `low`**: derruba a qualidade.
- Effort não muda o modelo: muda quanto ele pensa e quantas vezes confere. Tarefa bem especificada quase não ganha com
  `high`.
- Na dúvida, comece um degrau abaixo e suba se o resultado vier fraco.
- **Revisor:** Sonnet `medium` para diff comum; Opus `medium` para diff de acesso, concorrência ou dado pessoal; `high` só
  se o diff tiver decisão de desenho para julgar.
- O modelo mais caro da casa só como último recurso, quando o Opus já tentou e não convergiu.

### A tabela que se mostra antes de lançar

```
| Tarefa | Dificuldade | Modelo | Effort | Por que basta |
|---|---|---|---|---|
| T12 rota CSV | especificada, sem acesso | sonnet | high | TDD com critério claro |
| T12 revisão | diff comum | sonnet | medium | lê só o diff |
| T13 regra de acesso | desenho aberto | opus | high | decide quem vê o quê |
```

## Tipos de agente: a menor superfície de tools

Cada tool disponível pesa no contexto fixo de todo spawn. Escolha o tipo que cobre a tarefa com menos tools (estão em
`claude/agents/`):

| Tipo | Tools | Para |
|---|---|---|
| `runner` | Bash | Rodar comandos e resumir |
| `searcher` | Read, Glob, Grep | Achar onde está, quem chama |
| `editor` | Read, Edit | Edição pontual em arquivo conhecido |
| `researcher` | WebFetch, WebSearch | Documentação e comportamento de biblioteca |
| `doc-writer` | Read, Write | Arquivo novo com conteúdo já especificado |

`general-purpose` só quando a tarefa precisa mesmo de várias categorias. Não crie agente "especialista" por persona: revisão,
segurança e documentação já vêm das skills.

## O brief: JSON minificado, só o necessário

O brief é o único contexto do agente. Vai em JSON minificado, com o objetivo, o que já foi descartado, onde olhar e o
formato do retorno; sem o histórico da conversa.

```json
{"tarefa":"T12: rota que exporta o relatório em CSV. Não mude a tela.","worktree":"../wt/t12","regras":{"tdd":"teste primeiro; devolva trecho do vermelho e do verde","git":"não rode git; só dentro do worktree","rtk":"comandos pelo rtk; saída longa para arquivo","casa":"português do Brasil; nada de dado pessoal"},"retorno":{"status":"pronto|parcial|travado","arquivos":[],"vermelho":"","verde":"","duvidas":[],"resumo":""}}
```

Revisor recebe o pedido, a entrega e como ver o diff sem `git` (`diff -ruN <checkout-da-dev>/<arq> <worktree>/<arq>`), e
devolve `{"veredito":"aprovado|aprovado_com_ressalvas|reprovado","problemas":[{"arquivo_linha":"","gravidade":"alta|media|baixa","descricao":"","correcao":""}],"conferiu":[]}`.
O campo `conferiu` diz o que foi olhado, não só o que foi achado.

O que o revisor tenta derrubar: defeito de correção; segurança e acesso; dado pessoal que sobra; teste que não prova o que
diz; vermelho que não falharia sem a mudança; função que partiu de definição velha; desvio do pedido.

## Paralelo e memória

- **Agente que só edita** vai em paralelo à vontade.
- **Agente que roda teste pesado**: um por vez enquanto uma bateria roda. Muitos agentes com pytest, `npm ci`, navegadores
  e contêineres ao mesmo tempo enchem a memória e travam a máquina.
- Bateria completa, `docker build` e subir o banco local ficam com a sessão principal.
- Antes de lançar quem testa, olhe `free -h`; com swap cheio, espere. Limites de memória em
  [testes-e-qualidade.md](testes-e-qualidade.md).

## Workflows multiagente: último recurso

Os workflows salvos (`claude/workflows/fazer-revisar-corrigir.js` e `claude/workflows/revisao-profunda.js`) gastam muito
mais que agentes comuns. Use só no que não caberia num contexto: auditoria inteira, migração de centenas de arquivos,
plano difícil que precisa de vários ângulos. Edição normal e bug localizado vão por agente comum: um faz, um revisa, um
corrige se preciso. Avise o custo antes de rodar um workflow. A `revisao-profunda` roda só a pedido, e só no diff.
