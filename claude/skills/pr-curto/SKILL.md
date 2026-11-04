---
name: pr-curto
description: Escrever título e corpo de pull request curtos, no template certo do projeto. Use em todo "abre o PR", "gh pr create", "descrição do PR", e na skill publicar.
---

# PR curto

## 1. Escolha o template

Procure em `.github/PULL_REQUEST_TEMPLATE/` (e `.github/pull_request_template.md`):

| Caso | Template |
|---|---|
| PR da `dev` para a `main` (publicação) | `publicacao.md` |
| Correção que precisa ir rápido | `correcao-urgente.md` |
| Todo o resto | `padrao.md` (ou o `pull_request_template.md`) |

Sem template no projeto: use as seções do `padrao.md` deste método (O quê, Por quê, Como testei, Riscos).

## 2. Título

O mesmo padrão do commit (skill `commit-curto`): `tipo(escopo): descrição`, até 72 caracteres, presente, sem ponto.
Publicação: `chore(publicacao): AAAA-MM-DD`.

## 3. Corpo

- Preencha cada seção do template; apague os comentários `<!-- -->` e a seção que não se aplica (não deixe vazia).
- Curto: frases curtas, sem enfeite, sem repetir o título. Cada fato uma vez.
- Nada inventado: comandos, testes e registros são os que rodaram de verdade (cole o comando, não diga "testei").
- Nunca: autoria de IA ("Generated with", Co-Authored-By de IA), dado pessoal, segredo, nome de cliente.

## 4. Abrir

- Título e corpo **prontos antes** do `gh pr create`: editar depois dispara outra rodada de CI.
- `gh pr create --base <base> --head <branch> --title "<título>" --body-file <arquivo>` (arquivo temporário, evita
  problema de aspas).
- Nunca abra PR de publicação sem o usuário pedir.
