# Fluxo de trabalho

O ciclo completo, do pedido à produção. Cada regra traz o porquê: quase todas existem por causa de um problema que já
custou caro.

## O ciclo em uma figura

```
  VOCÊ
   │  pedido, nas suas palavras
   ▼
  SESSÃO PRINCIPAL (orquestra; não escreve código)
   │  1. registra a tarefa Tn no TASKS.md
   │  2. depende de decisão sua?  sim → duvidas.md; a tarefa para ali; o resto segue
   │  3. plano curto (tarefa grande) e a tabela tarefa → dificuldade → modelo → effort
   │  4. branch feat/fix/docs/ci a partir da dev; um worktree por tarefa paralela
   ▼
  AGENTES
   │  FAZER     um agente: teste primeiro, vermelho, implementa, verde
   │  REVISAR   outro agente lê o diff e devolve JSON com problemas e gravidade
   │  CORRIGIR  se houver alta ou média; revisa de novo (até 3 rodadas)
   ▼
  SESSÃO PRINCIPAL (verificação)
   │  5. confere o vermelho: o teste novo roda contra o código antigo e falha
   │  6. um commit por subtarefa
   │  7. bateria na máquina, só do diff (scripts/testar-como-o-ci.sh)   sem verde, não junta
   │  8. git pull, merge --no-ff na dev, git push
   │  9. TASKS.md, duvidas.md, publicacao-pendente.md e registros/ em dia
   │ 10. apaga o worktree e a branch
   ▼
  dev  (acumula; nada disto está em produção)
   │
   │  você diz "publicar"
   ▼
  PUBLICAR: bateria completa (EXIGIR_TUDO=1) → revisões de segurança do diff → PR dev → main
            → CI → migrations → merge → conferir a produção
```

Três ideias seguram tudo:

1. **Tudo fica escrito.** Pedido vira tarefa, dúvida vira item, decisão vira registro, o que mudou vira texto para quem
   usa. Quem chega depois (você, um colega, uma sessão nova) lê, não adivinha.
2. **Quem faz não revisa.** Outro agente lê o diff. A sessão principal roda os testes e abre só os trechos apontados.
3. **Nada vai para produção sem pedido.** A `dev` é livre; `main` e banco de produção só com você mandando.

## 1. Do pedido à tarefa

- **Todo pedido vira uma `Tn` no `TASKS.md`**, com as suas palavras, o que fazer, a evidência (`arquivo:linha`), como
  conferir e a sugestão de modelo. Pedido executado na hora também é registrado.
- **"Pode colocar" = registrar, não executar.** Você dispara depois, tudo junto. Depois de disparada, a tarefa não volta a
  pedir licença a cada etapa: quando a dependência cai, a próxima etapa segue.
- **Implementar tudo o que foi pedido.** Nada fica "para depois" em silêncio; e nada que você não pediu entra sem
  aprovação. Ao fechar uma leva, a sessão confere a lista inteira de pedidos contra o que foi feito.
- **Análise só relata.** Pedido de "analisar" ou "avaliar" devolve relatório com números e recomendação; nada é mudado até
  você escolher.

### Dúvidas sem travar

Em vez de parar tudo para perguntar, a tarefa que depende de você para naquele ponto, o motivo vai para o `duvidas.md`
(o que travou, onde parou, opções com recomendação) e o trabalho segue com as outras. Decisão simples, a sessão toma e
registra o porquê; difícil, pode ir a um conselho de modelos (skill `llm-council`) e fica marcada "para confirmar".
Permissão (publicar, produção, apagar) é sempre sua.

Quando uma pergunta precisa mesmo de você, chega pelo celular: a skill `notify` manda um aviso curto (só o assunto, sem
dado nenhum) e a pergunta aparece na aba **Perguntas** do painel da sessão (`/painel`), com as opções; a resposta volta
para a sessão sozinha.

## 2. Plano e escolha dos agentes

- Tarefa não trivial: plano curto antes, e espera o seu ok. Tarefa grande: primeiro um **documento de desenho**
  (`docs/roteiros/`), revisado do mesmo jeito que código, uma rodada de fazer-revisar-corrigir só.
- Antes de lançar, a sessão mostra a tabela **tarefa → dificuldade → modelo → effort → por que este basta**. Detalhe em
  [agentes-e-modelos.md](agentes-e-modelos.md).

## 3. Branch e worktree

- Toda mudança nasce numa branch `feat/`, `fix/`, `docs/` ou `ci/`, tirada da `dev` atualizada (`git pull` antes de
  disparar agentes).
- Tarefas independentes que mexem no mesmo repositório rodam em paralelo, **cada uma no seu worktree**
  (`../wt/<tarefa>`). Agente em worktree não roda `git`: commit e merge ficam com a sessão principal.
- **Worktree: usa e apaga.** Logo depois de juntar na `dev`, `git worktree remove` e `git branch -d`. Mudança não
  commitada num worktree que vai sair: guarde o diff antes.

## 4. Fazer, revisar, corrigir

O centro do método. Um agente **faz** com TDD e devolve JSON (status, arquivos, trecho do vermelho, trecho do verde,
dúvidas, resumo). **Outro** agente revisa só o diff e devolve `{veredito, problemas:[{arquivo_linha, gravidade,
descricao, correcao}], conferiu}`. Se há problema `alta` ou `media`, um agente corrige (teste primeiro, quando cabe) e
outra revisão acontece.

- **No máximo 3 revisões.** Revisor sempre acha mais alguma coisa; sem limite o ciclo não acaba. O que sobra vira item
  aberto com teste, não uma quarta volta.
- `baixa` não obriga: corrige-se se for barato.
- Documentação pura não precisa de revisor.
- Para um lote de tarefas, o workflow salvo `fazer-revisar-corrigir` (em `claude/workflows/`) faz o ciclo em paralelo. Só
  use quando agentes comuns não bastam: workflow gasta muito mais.

## 5. A verificação da sessão principal

1. **Conferir o vermelho:** roda o teste novo contra o código antigo (um worktree destacado na base) e vê falhar. Teste que
   não falharia sem a mudança não prova nada.
2. **Um commit por subtarefa**, `tipo(escopo): descrição`, sem autoria de IA.
3. **Bateria na máquina, só do diff:** `scripts/testar-como-o-ci.sh` (base `dev`). Ele usa o **mesmo mapa** do CI e roda
   só o que o diff toca. Vermelho: não junta. Depois do conserto, roda só o que o conserto tocou mais o teste que caiu
   (`ARQUIVOS=<lista>`), não a bateria inteira de novo.
4. **Juntar:** `git pull` da `dev` (com merge local ainda não enviado: `git pull --rebase=merges`, nunca `--rebase` puro,
   que achata os merges), `git merge --no-ff <branch>`, `git push origin dev` logo depois.
5. **Estado em dia** num commit logo depois do merge: a tarefa no `TASKS.md`, o `duvidas.md`, o item em
   `docs/publicacao-pendente.md` (o que muda para quem usa) e o índice de `registros/`.

## 6. Registros de garantia

Toda bateria grava um resumo em `registros/baterias/` (commit, hash da árvore, passos, duração, sha256 do log, que fica
fora do repositório). Toda revisão vira relatório em `registros/revisoes/` (`salvar_revisao.py`, que recusa segredo e dado
pessoal). Todo achado corrigido entra em `registros/correcoes.md` com o commit e o teste que prova. Servem para mostrar,
com data e hash, que se testou e corrigiu. Detalhe em [testes-e-qualidade.md](testes-e-qualidade.md).

## 7. Publicação

Só com o seu pedido de publicar, e só com **tudo** pronto: todas as branches em andamento juntas na `dev`, conflitos
resolvidos, testes verdes. Nunca a `dev` parcial. A ordem (skill `publicar` do `projeto-modelo/`):

1. A `main` junta na `dev`.
2. **Bateria completa na máquina, sem nada pulado:** `EXIGIR_TUDO=1 scripts/testar-como-o-ci.sh`. Testes de tela
   completos só aqui (no dia a dia, só os do diff). O PR não pode ser o primeiro lugar onde um teste roda.
3. **Revisões de segurança do diff** `main...dev`: `/security-review`, Claude Security (modo "scan changes"), semgrep,
   `insecure-defaults:audit`. Achado confirmado bloqueia e vira correção pelo caminho normal. O que gasta licença roda só
   no diff; o que gasta só máquina (testes, gitleaks, auditoria de dependências) roda em tudo.
4. Registros commitados na `dev` **antes** do PR (commit depois dispara o CI de novo).
5. **PR `dev → main`** com título e corpo prontos antes do push (editar o PR depois cancela a rodada e abre outra). O
   corpo sai do `publicacao-pendente.md`. PR aberto por outra pessoa: não use nem edite sem combinar.
6. **CI** (só aqui e no push da `main`). Falhou: achar a causa, corrigir, push. Nunca reexecutar sem corrigir.
7. **Migrations em produção** depois do CI verde e **antes** do merge: ensaio numa transação que se desfaz, aplicar,
   registrar, verificador de segurança. Merge com código que exige migration ausente quebra a produção na hora.
8. **Merge** (`gh pr merge --merge`, nunca `--admin`, nunca `--delete-branch`), por quem pediu a publicação, ou pela
   sessão se você autorizou o processo todo.
9. **Conferir a produção** em rodadas (skill `conferir-producao`).

### Volta pronta

Antes do merge: o desfazer de cada migration escrito e ensaiado; tag `antes-da-publicacao-<data>` na `main` de antes.
Depois: tag anotada `testado-<data>` no commit publicado, com o sha256 do índice dos registros. Se quebrar: `git revert -m 1`
do merge, também por PR, e o desfazer das migrations na ordem inversa.

## 8. Ritmo de sessão

- **Sessão nova por fase.** A conversa longa relê o histórico inteiro a cada resposta. Entre fases (uma leva entrou na
  `dev`, nada rodando que dependa desta sessão), a sessão avisa que é boa hora de encerrar, com o handoff pronto (skill
  `session-handoff`: o que está feito, o que roda, como retomar).
- **Retomar após falta de memória.** Processo morto por memória não é falha do trabalho: com a memória de volta, relança,
  uma bateria por vez.
- **Outra frente no mesmo repositório.** Se algo seu quebra código ou teste de outra pessoa, avise na hora e suba a
  correção, não deixe só na máquina. Antes de numerar migration, confira o que já está aplicado.

## Lista curta (para colar numa tarefa)

- [ ] Tn no `TASKS.md`; dúvida no `duvidas.md`
- [ ] tabela de agentes mostrada; branch da `dev` atualizada; worktree se paralelo
- [ ] teste primeiro; vermelho conferido contra a base
- [ ] revisão por outro agente; alta/média corrigidas (máx. 3 rodadas)
- [ ] commit por subtarefa; bateria do diff verde
- [ ] pull, merge `--no-ff`, push; estado e registros em dia; worktree apagado
