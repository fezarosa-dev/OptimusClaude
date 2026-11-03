# Estilo

## Commits

[Conventional Commits](https://www.conventionalcommits.org/), com a descrição no idioma do projeto (o padrão daqui é
português do Brasil; troque no `CLAUDE.md` do projeto):

```
tipo(escopo): descrição curta do que muda (T12)
```

- **Tipos:** `feat`, `fix`, `docs`, `ci`, `refactor`, `test`, `perf`, `chore`. Merge na `dev`: `chore(merge): <branch> na dev`.
- **Escopo:** a área (`banco`, `painel`, `api`, `ci`, `tasks`, `registros`).
- **Um commit por subtarefa:** histórico legível e volta atrás a qualquer ponto.
- Cite a tarefa no fim quando houver.
- Commits que ainda não subiram podem ser reescritos; os que já estão na `dev` ou na `main`, nunca.
- Commite com o usuário do git da máquina; nunca `-c user.name=...` assinando como outra pessoa.

## Sem coautoria de IA

Nenhum artefato leva a IA como autora, coautora ou participante: commit, PR, merge, tag, release, issue, comentário,
código ou documento. Nada de `Co-Authored-By`, nada de "Generated with". O `CLAUDE.md` global instalado por este
repositório já diz isso ao Claude.

## Branches

`feat/`, `fix/`, `docs/`, `ci/` + um nome curto (`fix/login-tempo-constante`). Saem da `dev` atualizada; entram nela por
`merge --no-ff`. Nome de branch, título e corpo de PR nunca levam dado pessoal, segredo ou valor.

## Código

- **Nomes no idioma do projeto**, inclusive tabela, coluna, rota e mensagem de log. Termos técnicos consagrados (`id`,
  `status`, `hash`) podem ficar.
- **Comentário só para o porquê** que o código não mostra, em uma linha. O quê, o código já diz.
- **Mudanças pequenas e ligadas à tarefa.** Nada de refatorar o vizinho, reformatar o arquivo ou "melhorar" o que não foi
  pedido.
- **Edição pontual:** nunca reescrever um arquivo inteiro para mudar poucas linhas.
- **Antes de escrever, procure:** o projeto já tem? A linguagem ou a biblioteca já oferecem? (skill `preflight`).
- **Nenhuma dependência sem motivo.** Para poucas linhas, escreva as linhas. Dependência nova se justifica no PR.
- Atalho com limite conhecido leva o comentário `shortcut: <o limite>, <quando trocar>`.

## Documentos

- Frases curtas, diretas, no idioma do projeto, com acentos.
- Toda regra com o porquê ao lado: regra sem porquê é apagada pelo próximo que não a entender.
- Documento que descreve um estado que não existe mais se corrige ou se apaga.
- Não crie documento que ninguém pediu. Os arquivos de estado (`TASKS.md`, `duvidas.md`, `publicacao-pendente.md`,
  `registros/`) são a exceção: são o método.
