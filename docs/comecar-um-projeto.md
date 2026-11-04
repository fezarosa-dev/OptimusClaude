# Começar um projeto com o projeto modelo

O `projeto-modelo/` é o esqueleto que liga um projeto ao método: tarefas, dúvidas, bateria de testes, CI, registros de
garantia, hook de commit e as skills de publicação. Você copia uma vez para cada projeto novo.

## Passo a passo

```bash
cp -r ~/caminho/para/OptimusClaude/projeto-modelo/. ~/meu-projeto/
cd ~/meu-projeto
git init -b main && git config core.hooksPath .githooks       # commit fora do padrão é recusado
git add -A && git commit -m "chore: projeto a partir do modelo"
git checkout -b dev
python3 -I -m unittest discover -s scripts -p 'test_*.py'      # os scripts do modelo se testam
python3 scripts/testar_como_o_ci.py                            # a bateria, só do que mudou
ccc init && ccc index                                          # busca semântica no código
```

O que cada linha faz:

| Linha | Por quê |
|---|---|
| `cp -r .../projeto-modelo/. ~/meu-projeto/` | Copia também os arquivos ocultos (`.githooks/`, `.github/`, `.claude/`, `.gitignore`) |
| `git config core.hooksPath .githooks` | Liga o `.githooks/commit-msg`, que recusa mensagem fora de `tipo(escopo): descrição` ou com autoria de IA |
| `git checkout -b dev` | A `dev` recebe o trabalho do dia a dia; a `main` só recebe PR vindo da `dev` |
| `unittest discover -s scripts` | Confere que os scripts do modelo funcionam na sua máquina |
| `testar_como_o_ci.py` | Primeira rodada da bateria; grava o primeiro resumo em `registros/baterias/` |
| `ccc init && ccc index` | Indexa o código para a busca semântica (`ccc search`) |

## Depois

1. Preencha o `CLAUDE.md` (o que o projeto é e o que **não** é, onde as coisas moram, como subir o ambiente local) e
   ajuste o `BOAS-PRATICAS.md` (as regras de código e de segurança do projeto).
2. Acrescente as verificações da sua linguagem em `scripts/o_que_testar.py`: em `VERIFICACOES` os programas e o comando,
   no `MAPA` os caminhos que ligam cada uma. Exemplos por linguagem em [linguagens.md](linguagens.md). Máquina e CI usam o
   mesmo mapa. Para ver o que rodaria sem rodar: `SO_DECIDIR=1 python3 scripts/testar_como_o_ci.py`.
3. No `.github/workflows/testes.yml`, acrescente o setup da linguagem (com versão fixa) e fixe cada action por SHA de
   commit (o comentário no topo do arquivo mostra como).
4. No GitHub, proteja a `main`: só por PR, check `tudo-verde` obrigatório, sem bypass para administrador.
5. Apague as tarefas de exemplo do `TASKS.md` (T1, T2) e os itens de exemplo do `duvidas.md` (P-1, D-1), do
   `docs/publicacao-pendente.md` e do `registros/padroes.md`.
6. Se quiser o painel neste projeto: dentro do Claude Code, na pasta do projeto, `/painel`.

## O que vem no modelo

| Arquivo | Para que serve |
|---|---|
| `CLAUDE.md` | O que o seu projeto é e o que não é; os comandos de teste dele. O Claude lê no começo de toda sessão |
| `BOAS-PRATICAS.md` | As regras de código e de segurança do projeto |
| `TASKS.md` | A fila de tarefas `Tn`, com estado de cada uma (`aprovada` → `em andamento` → `feita na dev` → `no ar`) |
| `duvidas.md` | O que espera decisão sua: permissões (`P-n`) e decisões (`D-n`), com opções e recomendação |
| `docs/publicacao-pendente.md` | O que muda para quem usa na próxima publicação; vira o corpo do PR `dev → main` |
| `scripts/testar_como_o_ci.py` e `scripts/o_que_testar.py` | A bateria: roda na máquina o que o CI rodaria, só para o que o diff toca |
| `scripts/tarefa.py` | Brief de uma tarefa sem reler o `TASKS.md` inteiro |
| `scripts/arquivar.py` | Move tarefas no ar e dúvidas respondidas para `docs/tarefas-feitas.md` e `docs/duvidas-resolvidas.md` |
| `scripts/noite.py` e `scripts/noite_guarda.py` | O modo noturno: roda a fila do `TASKS.md` sozinho até esvaziar |
| `scripts/registros/` | `indice.py` (sha256 de cada registro), `salvar_revisao.py` (guarda relatório de revisão), `sensivel.py` (padrões de segredo e dado pessoal) |
| `registros/` | As provas: `baterias/`, `revisoes/`, `correcoes.md`, `padroes.md` e `INDICE.md` (veja `registros/README.md`) |
| `.github/workflows/testes.yml` | O CI, que roda só no PR para a `main` e no push da `main` |
| `.github/PULL_REQUEST_TEMPLATE/` | Templates de PR: `padrao`, `publicacao` (dev → main) e `correcao-urgente` |
| `.githooks/commit-msg` | Recusa commit fora do padrão ou com autoria de IA |
| `.claude/skills/` | `publicar` (da `dev` até a produção), `aplicar-migration` (mudança de banco testada com rollback) e `conferir-producao` (ver se a produção está saudável) |

## O primeiro ciclo, na prática

1. Você escreve: "preciso baixar o relatório do mês em CSV". A sessão faz as perguntas do `grilling` e registra a `T1` no
   `TASKS.md` com as suas palavras, o que fazer e como conferir.
2. Ela mostra a tabela tarefa, dificuldade, modelo e effort. Você dá o ok.
3. Cria a branch `feat/relatorio-csv` a partir da `dev`. Um agente escreve o teste, vê falhar, implementa e vê passar.
4. Outro agente revisa o diff e devolve os problemas. Um terceiro corrige o que for alto ou médio.
5. A sessão principal roda o teste novo contra o código antigo (tem de falhar), commita, roda
   `python3 scripts/testar_como_o_ci.py` e, estando verde, faz `merge --no-ff` na `dev` e push.
6. `TASKS.md` e `registros/` ficam em dia. A `T1` passa para "feita na dev". Nada foi para produção: isso só acontece
   quando você pedir para publicar.

O mesmo ciclo, contado com cada arquivo e comando: [README, Um pedido do começo ao fim](../README.md#um-pedido-do-começo-ao-fim).
