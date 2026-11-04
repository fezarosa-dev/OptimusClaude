# <Nome do projeto>

> Leia este arquivo antes de qualquer coisa. Ele diz o que este projeto é e, principalmente, o que ele **não** é.
> Antes de escrever, mudar ou revisar código, leia também o [`BOAS-PRATICAS.md`](BOAS-PRATICAS.md): como trabalhamos e
> as regras de segurança que toda mudança segue. Se um pedido contrariar uma regra de lá, pare e pergunte antes.
>
> Preencha cada `<...>` e apague as linhas de instrução em itálico. Seção que não se aplica: apague, não deixe vazia.

## 1. O que estamos construindo

_Uma ou duas frases: o problema, para quem, e o resultado esperado._

<O que é.>

**O que este projeto NÃO é:** _a lista das confusões prováveis. Escrever o que não é economiza mais discussão do que
escrever o que é._

- <Não é ...>
- <Não é ...>

_A pergunta que toda decisão de código deve fazer (ex.: "isto serve à plataforma, ou só ao primeiro caso?")._

## 2. A fonte única

_Onde mora a verdade do domínio (regras de negócio, glossário, decisões). Um lugar só. Documento que descreve um estado
que não existe mais não é referência, é armadilha: corrija ou apague._

- `<pasta-do-conhecimento>/`: <o que tem lá>.
- Conflito: **`<pasta-do-conhecimento>/` manda no domínio; este arquivo manda na engenharia.**

## 3. Onde as coisas moram

| O quê | Onde |
|---|---|
| Repositório | `<dono>/<repositorio>` |
| Banco | <serviço, projeto, região, schema> |
| Produção | <onde roda: servidor, nuvem, app> |
| Painel / site | <onde publica> |
| Segredos | <cofre de segredos da plataforma>. Nunca no repositório, nunca no banco |

## 4. Como o repositório é organizado

_A árvore de pastas de primeiro nível, com uma linha cada._

```
<pasta>/        <o que é>
<pasta>/        <o que é>
docs/           referência e histórico (não é regra vigente)
registros/      registros de garantia (baterias, revisões, correções)
scripts/        testar_como_o_ci.py, o_que_testar.py, registros/
```

### Regras da estrutura

- _Ex.: cada unidade (serviço, agente, app) é autocontida: sobe, cai e volta sem tocar nas outras._
- _Ex.: nada específico de uma unidade entra no código compartilhado; código sobe para o compartilhado quando o
  **segundo** usuário precisa dele, não antes._
- _Ex.: uma unidade não importa da outra; acoplamento passa por fila ou API._

### Migrations

_Se houver banco:_ toda mudança de schema é migration versionada em `<pasta-das-migrations>/`. Nunca altere o banco pelo
console sem gerar a migration: banco e repositório contam a mesma história. A definição que vale de uma função é a da
migration **mais recente** que a define. Como aplicar: skill `aplicar-migration`.

## 5. Fluxo de trabalho: branch, `dev`, PR e publicação

**Merge na `main` é deploy.** O caminho é um só: `feat/ fix/ docs/ ci/` → `dev` → PR `dev → main` → CI (`tudo-verde`) →
merge → produção.

- **A `main` é protegida, inclusive para administradores:** só entra por PR, e o PR só pode sair da `dev` (o job
  `origem-da-main` reprova os outros); o `tudo-verde` tem de estar verde; sem push direto, force-push ou `--admin`. Se algo
  travar, pare e avise.
- **Toda mudança nasce numa branch** `feat/`, `fix/`, `docs/` ou `ci/`, tirada da `dev` atualizada. Um commit por
  subtarefa, `tipo(escopo): descrição` em <idioma>. Nunca reescreva histórico que já subiu.
- **Juntar na `dev`:** antes, `python3 scripts/testar_como_o_ci.py` na máquina (o mesmo mapa do CI, só o que o diff toca). Se
  falhar, não junta. `git pull` antes, `merge --no-ff`, `git push` logo depois.
- **Publicar:** skill `publicar`. Antes do PR, `EXIGIR_TUDO=1 python3 scripts/testar_como_o_ci.py` na `dev`, **sem nada
  PULADO**, e as revisões de segurança do diff. Migrations depois do CI verde e antes do merge. Nesse PR, **nunca**
  `--delete-branch` (apagaria a `dev`). Quem decide o merge é quem pediu a publicação.
- **O CI roda só no PR para a `main` e no push da `main`.** PR para a `dev` não roda: minuto de CI custa. Atualize título e
  descrição do PR antes do push, nunca depois (editar dispara outra rodada).

## 6. Ambiente local

_Como subir o projeto inteiro na máquina, com um comando, e só com dados fictícios._

- Subir: `<comando>`. Descer: `<comando>`.
- **Nenhum dado de produção entra no local.** Consulta à produção devolve só números, estados, horários e códigos.
  Mais dado = mais seed inventado.
- Tela nova nasce com o teste de tela dela (<Playwright/...>), registrado em `<arquivo-de-rotas>`.
- Limite de memória dos testes: <ex.: comandos de teste numa fatia systemd de N GB; testes de tela com N workers>.

## 7. Regras da casa

- **Idioma:** <português do Brasil> em nome de tabela, coluna, rota, mensagem de log e commit.
- **Idempotência não é opcional:** todo job pode rodar duas vezes. Use chave de idempotência sempre que houver
  identificador natural.
- **Tudo o que o sistema decide vai para um registro de eventos, com o porquê** (e sem dado pessoal).
- **Nenhum artefato leva a IA como autora:** sem `Co-Authored-By`, sem "Generated with".
- **Arquivos de estado na raiz:** `TASKS.md` (cada pedido vira Tn), `duvidas.md` (o que espera decisão),
  `docs/publicacao-pendente.md` (o que muda na próxima publicação, para quem usa), `registros/` (garantia).

## 8. Contexto que não está nos documentos

_Incidentes e lições que explicam regras estranhas. Uma regra sem o porquê é removida pelo próximo que não a entender._

- <O que aconteceu, quando, e a regra que ficou.>
