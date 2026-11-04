---
name: publicar
description: Levar o que está na dev até a produção -- bateria completa na máquina, revisões de segurança do diff, PR dev -> main, CI, migrations, merge, e conferir que chegou. Use quando pedirem "publica", "sobe", "manda pra main", "abre o PR para a main".
---

# Publicar

Merge na `main` é deploy. Por isso a publicação tem uma ordem só, e **quem publica é o merge, não o PR**.

Só comece com um pedido explícito de publicar. "Manda para a main" dito antes, com integração em andamento, espera a
integração terminar: todas as branches juntas na `dev`, conflitos resolvidos, testes verdes.

## A ordem

1. **A `main` junta na `dev`** (`git fetch && git merge origin/main` na `dev`), se ela andou. Conflito se resolve na
   `dev`, com bateria do que o conflito tocou.
2. **Bateria completa na máquina, sem nada pulado:** `EXIGIR_TUDO=1 python3 scripts/testar_como_o_ci.py` na `dev`. Qualquer
   `PULADO` reprova: instale o que faltar. O PR não pode ser o primeiro lugar onde um teste roda.
3. **Revisões de segurança, só no diff** `origin/main...dev`:
   - `/security-review`;
   - Claude Security em modo "scan changes" (avise o custo antes);
   - `semgrep` na máquina (`uvx semgrep --config auto` nos arquivos do diff);
   - `insecure-defaults:audit` nos arquivos de configuração tocados;
   - a revisão profunda (`Workflow({name:'revisao-profunda', args:{base:'origin/main'}})`) só se pedirem: avise o custo.

   Achado confirmado bloqueia: vira tarefa, correção numa `fix/` a partir da `dev` (TDD), bateria do conserto, merge, e
   volta ao passo 2 só com o que o conserto tocou. Cada relatório vai para `registros/revisoes/` com
   `python3 scripts/registros/salvar_revisao.py <tipo> <arquivo>`; cada correção, para `registros/correcoes.md`.
4. **Registros na `dev`:** `gitleaks dir registros --no-banner --redact` (limpo), `python3 scripts/registros/indice.py`,
   `git add registros/ && git commit -m "chore(registros): índice"`. Antes do PR: registro commitado depois dispara o CI de
   novo.
5. **Volta pronta:** cada migration da leva tem o desfazer escrito e ensaiado; anote a última versão de migration que já
   está em produção (só o número).
6. **PR:** `git push origin dev` e `gh pr create --base main --head dev`, com título e corpo **prontos antes** (editar o
   PR depois dispara outra rodada de CI). Título `chore(publicacao): AAAA-MM-DD` e corpo pelo template `.github/PULL_REQUEST_TEMPLATE/publicacao.md` (skill `pr-curto`): o `docs/publicacao-pendente.md`, a garantia, as migrations e "como voltar". Confira que o título passa no padrão de commit. Sem nenhuma linha
   de autoria de IA. Se já houver PR `dev → main` aberto por outra pessoa, pergunte antes de dar push nele.
7. **CI:** `gh pr checks <n> --watch`. Tudo verde, menos o que depende das migrations (se houver um check assim). Falhou:
   `gh run view <id> --log-failed`, corrija pela `fix/` → `dev` → push. Nunca reexecute sem corrigir a causa.
8. **Migrations em produção**, na ordem da versão, com a skill `aplicar-migration` (ensaio que se desfaz, aplicar,
   registrar, verificador de segurança). Migration em produção sem o CI do PR verde não vale; merge sem a migration que o
   código exige também não.
9. **Tags e merge:**
   ```bash
   D=$(date +%Y%m%d-%H%M); git fetch origin
   git tag -a "antes-da-publicacao-$D" origin/main -m "main antes da publicação de $D (PR #<n>)"
   git push origin "antes-da-publicacao-$D"
   gh pr merge <n> --merge      # NUNCA --admin, NUNCA --delete-branch (apagaria a dev)
   ```
   Quem mescla é quem pediu a publicação (ou a sessão, se a pessoa autorizou o processo todo).
10. **Marcar o que foi testado:** no commit do merge, uma tag anotada com o sha256 do índice dos registros:
    ```bash
    sha=$(gh pr view <n> --json mergeCommit -q .mergeCommit.oid)
    git tag -a "testado-$(date +%F)" "$sha" -m "registros/INDICE.md sha256 $(git show "$sha":registros/INDICE.md | sha256sum | cut -d' ' -f1)"
    git push origin "testado-$(date +%F)"
    ```
11. **Conferir que chegou:** skill `conferir-producao`, em rodadas, por um tempo. Quebrou: correção pelo mesmo caminho
    (`fix/` → `dev` → PR) ou `git revert -m 1 <merge>` também por PR, mais o desfazer das migrations na ordem inversa.
12. **Ao fim:** `python3 scripts/arquivar.py` (tarefas no ar e dúvidas respondidas saem para `docs/`, num commit `chore(tarefas): arquiva o que foi publicado` pela `dev`); `docs/publicacao-pendente.md` recomeça vazio; diga em duas linhas o que foi publicado (PR, commit), o
    que depende de alguém, e como voltar (a tag `antes-da-publicacao-*`).

## Nunca

- `--admin`, push direto na `main`, force-push, desligar a proteção. Se travar, pare e registre no `duvidas.md`.
- Reexecutar rodadas antigas da `main` (republicariam código antigo).
- `-c user.name=...` no commit: commite com o usuário do git configurado na máquina.
