---
name: snote
description: "Use quando o usuário digitar /snote (com ou sem título após o comando). Salva um resumo do que foi conversado/decidido na sessão atual como uma nota nova no vault Obsidian do usuário (o 'segundo cérebro'). Não usar para pedidos genéricos de anotação fora do comando /snote."
---

# /snote — salvar sessão no Obsidian

Vault: o caminho na variável de ambiente `OBSIDIAN_VAULT` (ex.: `~/Vault`). Se ela não estiver definida, pergunte ao usuário onde fica o vault e sugira guardá-lo em `OBSIDIAN_VAULT` no `env` do `~/.claude/settings.json`. Siga a skill `obsidian-markdown` para a sintaxe, se estiver instalada.

## Passos

1. **Resuma a sessão**, não copie a conversa inteira: do que se tratou, o que foi decidido/feito, e qualquer conclusão útil para consulta futura. 1-2 frases de resumo + o corpo com o conteúdo relevante.
2. **Título**: se o usuário passou um título depois de `/snote` (`$ARGUMENTS`), use-o. Senão, gere um título curto (poucas palavras, no mesmo estilo dos títulos já existentes no vault).
3. **Tags**: 1-3 tags de tópico, minúsculas, sem acento, sem `#` no frontmatter (só a lista).
4. **Notas relacionadas**: rode `python3 ~/.claude/scripts/vault_search.py --vault "$OBSIDIAN_VAULT" search "<palavras-chave do tópico>"` (e opcionalmente `related`/`by-tag`) para achar notas existentes sobre o mesmo assunto e linkar com `[[Nome da nota]]` na seção "Notas relacionadas". Não precisa editar a nota antiga — o backlink é automático no Obsidian.
5. **Escreva o arquivo** em `$OBSIDIAN_VAULT/<Título>.md`, seguindo `Templates/Nota.md` do vault se existir, ou esta estrutura:

```markdown
---
title: "<título>"
date: <YYYY-MM-DD>
tags:
  - tag1
  - tag2
aliases:
  - 
---

# <título>

## Resumo

<1-2 frases>

## Conteúdo

<corpo>

## Notas relacionadas

[[Nota relacionada 1]]
[[Nota relacionada 2]]
```

6. Se já existir um arquivo com o mesmo nome no vault, não sobrescreva: acrescente a data ao nome (`<Título> <YYYY-MM-DD>.md`) ou pergunte ao usuário.
7. Confirme ao usuário com o caminho do arquivo criado, em uma linha.

Não crie a nota se não houve nada de conteúdo relevante na sessão (conversa vazia/trivial) — avise o usuário em vez de gerar uma nota vazia. Nunca grave segredo, token ou dado pessoal de terceiros na nota.
