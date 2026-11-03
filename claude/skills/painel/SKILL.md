---
name: painel
description: Liga o painel da sessão (tarefas, agentes, consumo, limites, perguntas pelo celular) para o projeto da sessão atual. Use quando o usuário digitar /painel ou pedir para ligar, abrir ou mostrar o painel da sessão.
---

# Painel da sessão

Painel web local em `~/painel-da-sessao` (Python 3 puro). Mostra o andamento desta sessão e deixa o usuário
responder perguntas pelo PC ou pelo celular.

## 1. Ligar

```bash
python3 ~/painel-da-sessao/ativar.py "$PWD"
```

Aponta o `config.json` para o projeto deste diretório (raiz do git, ou o próprio diretório), reinicia o servidor se
algo mudou e imprime as URLs. Mostre ao usuário as duas linhas: `PC` e `celular` (a do celular leva a chave).

## 2. Esperar as respostas

Se a espera ainda não está rodando nesta sessão, ligue em segundo plano (Bash `run_in_background`):

```bash
~/painel-da-sessao/esperar-resposta.sh
```

Quando sair com `RESPOSTA <json>`: aplique a resposta, registre onde o projeto registra decisões (ex.: `duvidas.md`),
tire a pergunta do `perguntas.json` e religue a espera. Nunca duas esperas ao mesmo tempo.

## 3. Publicar uma pergunta

Acrescente ao array de `~/painel-da-sessao/perguntas.json`, gravando atômico (arquivo temporário + `mv`):

```json
{"id":"D-37","header":"Ordem","pergunta":"Qual fazer primeiro?","multiplas":false,
 "opcoes":[{"rotulo":"A","descricao":"...","recomendada":true},{"rotulo":"B","descricao":"...","recomendada":false}],
 "contexto":"opcional"}
```

`id` (letras, números, `.`, `_`, `-`, até 40), `pergunta` e `opcoes` (1 a 12, `rotulo` único) são obrigatórios;
a recomendada vai primeiro. O painel sempre oferece "Outro" com texto.

## 4. O que cada quadro mostra

- Tarefas: `TASKS.md` do projeto. Dúvidas: `duvidas.md`. Publicação pendente: `docs/publicacao-pendente.md` (todos opcionais).
- Baterias: `~/.cache/bateria-*.log`. Worktrees: o `../wt` irmão do projeto (`git worktree list`).
- Agentes, workflows, shells em "Rodando", consumo: os `.jsonl` da sessão em `~/.claude/projects/<projeto>/`.
- Limites (5 h e semana): da statusline (`~/.cache/claude-limites`). Linhas desde a main: `git diff origin/main...dev`.

Num projeto sem `TASKS.md` ou `duvidas.md` esses quadros ficam vazios, e está tudo bem.

## 5. Recarregar e parar

- Botão **Recarregar** (topo) ou `POST /api/recarregar`: zera os caches e repega tudo.
- Parar: `kill $(cat ~/painel-da-sessao/servidor.pid)`.

## Segurança

- A chave do celular (`chave.txt`) nunca vai para commit, ntfy, PR nem arquivo de projeto.
- `perguntas.json` nunca leva dado pessoal ou de cliente, documento, senha nem token.
