# Testes e qualidade

## TDD em todo código

1. Escreva o teste.
2. Rode e veja **falhar pelo motivo certo** (não por erro de sintaxe ou import errado).
3. Implemente.
4. Veja **passar**.

Vale para código novo e para correção, na sessão principal e nos agentes: o brief exige, e o retorno traz o trecho do
vermelho e do verde.

**A sessão principal confere o vermelho** antes de commitar: roda o teste novo contra o código antigo, num worktree
destacado na base, e confirma que falha. Teste que passaria sem a mudança não prova nada.

**Teste de segurança é teste como outro qualquer:** toda regra de acesso nova vem com o caso que prova que quem não pode
é recusado.

### SQL

O teste falha sem a migration e passa com ela, sempre numa transação que se desfaz sozinha:

```sql
begin;                       -- com ponto e vírgula, senão o resto roda fora da transação
-- <migration> (só no verde)
do $$ begin
  -- casos
  raise exception 'TESTE OK';  -- desfaz tudo; só esta mensagem é verde
end $$;
```

- Roda pela API, não só no `psql` (nada de `\gset`, `\set`, `:variavel`).
- Não supõe banco vazio nem o seed: confere só o que o próprio teste criou.
- Acesso por perfil: `set local role ...` e as credenciais de cada caso (anônimo, sem permissão, outra equipe, id de
  outra pessoa).

### Sem executor de teste

Onde não há como rodar (script sem interpretador na máquina, tela sem runner), diga isso e descreva a verificação manual.
Não adicione dependência só para testar sem combinar antes.

## Testar como o CI, na máquina, só do diff

`scripts/testar-como-o-ci.sh` (no `projeto-modelo/`) roda na máquina **o que o CI rodaria para o que mudou**, pelo mesmo
mapa que o CI usa (`scripts/o_que_testar.py`: caminho → verificações). Caminho que o mapa não conhece roda tudo.

| Comando | Quando |
|---|---|
| `scripts/testar-como-o-ci.sh` | Antes de todo merge na `dev`: o diff contra a `dev`, mais o não commitado e os arquivos novos |
| `ARQUIVOS=lista.txt scripts/testar-como-o-ci.sh` | Depois de um conserto: só os arquivos do conserto |
| `EXIGIR_TUDO=1 scripts/testar-como-o-ci.sh` | Antes do PR para a `main`: tudo, e `PULADO` também reprova |
| `SO_DECIDIR=1 scripts/testar-como-o-ci.sh` | Ver o que rodaria, sem rodar |

- A bateria **não para na primeira falha**: roda todos os passos e marca `OK`, `FALHOU` ou `PULADO` (programa que falta).
- **Bateria só do que falhou:** com o conserto feito, rode só o que ele tocou (`ARQUIVOS=`) mais o próprio teste que caiu.
  A rede de segurança é o `EXIGIR_TUDO=1` antes do PR.
- **O CI no GitHub roda só no PR para a `main` e no push da `main`.** Minuto de CI custa; a `dev` é testada na máquina.

Para adaptar: acrescente em `VERIFICACOES` os comandos da sua linguagem (ver [linguagens.md](linguagens.md)) e diga no
`MAPA` quais caminhos ligam cada uma. O CI chama o mesmo script, então máquina e CI não divergem.

## Testes de tela

- Tela, rota ou função nova do site nasce com o teste de tela dela (Playwright).
- No dia a dia (merge na `dev`, fim de tarefa): **só os specs ligados ao diff**.
- **Site completo só antes do PR para a `main`**, dentro do `EXIGIR_TUDO=1`.
- Nunca dois runs de tela ao mesmo tempo contra o mesmo banco local; teste que depende da hora congela o relógio.

## Limite de memória

Muitos agentes testando ao mesmo tempo travam a máquina. Ponha um teto na soma do que a sessão roda, para você continuar
usando o computador:

- **Comandos de teste numa fatia do systemd com teto** (Linux):
  ```bash
  systemctl --user set-property --runtime claudetrabalho.slice MemoryHigh=5400M MemoryMax=6G
  systemd-run --user --scope -q --slice=claudetrabalho.slice -p MemoryMax=1536M -- <comando de teste>
  ```
  Nunca ponha teto no processo do próprio Claude ou no contêiner onde ele roda: estourar mata a sessão inteira.
- **Workers:** Playwright com poucos navegadores (ex.: `E2E_WORKERS=4`; o padrão costuma ser metade dos núcleos);
  vitest `--maxWorkers=2`; pytest sem paralelismo.
- **Contêineres só quando precisa:** sobe antes da bateria, desce no fim; teto por contêiner com `docker update --memory`.
- Agente que só edita: paralelo à vontade. Agente que testa: um por vez durante uma bateria.

## Registros de garantia

Prova de diligência: o que rodou, quando, sobre qual commit, o que achou e como foi corrigido. Ficam em `registros/` (modelo
completo no `projeto-modelo/registros/README.md`):

| O quê | Quem grava |
|---|---|
| `registros/baterias/*.md`: resumo de cada rodada (commit, hash da árvore, passos, duração, sha256 do log, que fica fora do repositório) | a bateria, sozinha |
| `registros/revisoes/*.md`: relatório de cada revisão | `scripts/registros/salvar_revisao.py <tipo> <arquivo>` (recusa segredo e dado pessoal) |
| `registros/correcoes.md`: cada achado corrigido, com commit e o teste que prova | à mão |
| `registros/INDICE.md`: sha256 de cada arquivo | `scripts/registros/indice.py`, na `dev` |

Registro nunca se apaga. Nas rodadas finais antes de publicar, cada etapa vira registro assim que termina, não só no fim.
O registro mostra diligência; não promete que não há falha.

## Qualidade além dos testes

- **Revisão por quem não fez**, só no diff, com o que conferiu escrito.
- **Linters e verificação de tipos** fazem parte do mapa, não de um passo à parte.
- **Garantia com dado real:** em sistema que decide sobre documento, revisão de código não basta; meça o acerto com uma
  amostra real, no ambiente onde o dado pode estar, gravando só os números.
