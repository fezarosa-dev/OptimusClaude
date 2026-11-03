---
name: notify
description: Envia notificação push para o celular do usuário via ntfy.sh sempre que ele pedir para ser avisado/notificado sobre algo (ex. "me avise quando terminar", "notifique quando mudar").
---

# Notificar o usuário via ntfy.sh

Use esta skill sempre que o usuário pedir para ser avisado, notificado ou alertado sobre algo — uma tarefa que vai terminar, uma mudança de estado, um evento futuro, etc. Normalmente combinado com a skill `/loop` para checagens periódicas.

## Como enviar

```bash
curl -s -H "Title: <título curto>" -H "Tags: <tag opcional>" -d "<mensagem>" "ntfy.sh/${NTFY_TOPICO:?defina NTFY_TOPICO}"
```

Tags úteis do ntfy (viram emoji no app): `warning`, `tada`, `package`, `white_check_mark`, `rotating_light`, `hourglass`.

## Tópico do usuário

O tópico padrão vem da variável de ambiente `NTFY_TOPICO` (definida no `env` do `~/.claude/settings.json` ou no shell). O usuário instala o app ntfy (Android/iOS) e se inscreve nesse tópico.

Se `NTFY_TOPICO` não estiver definida, não invente um tópico: avise o usuário e sugira criar um com sufixo aleatório (`python3 -c 'import secrets; print("claude-notify-" + secrets.token_hex(4))'`) e guardá-lo em `NTFY_TOPICO`.

Só use um tópico separado quando o pedido for sobre um assunto recorrente e distinto que já tem tópico próprio, ou quando o usuário pedir notificações separadas por assunto. Tópico novo sempre com sufixo aleatório: tópicos do ntfy.sh são públicos pelo nome, então o sufixo evita que outra pessoa adivinhe o nome e receba as notificações.

## O que nunca vai na mensagem

O tópico é público pelo nome. A mensagem leva só o assunto curto ("Testes terminaram", "Build falhou"). Nunca dado pessoal, nome de cliente, documento, valor, senha, token, caminho interno nem trecho de código.

## Preferência

Prefira o ntfy.sh à ferramenta `PushNotification` nativa do Claude Code — aquela só dispara quando a sessão está inativa, o que a torna pouco confiável para avisos durante uma conversa ativa. Não ofereça `PushNotification` como alternativa a menos que o usuário peça.

## Quando combinar com /loop

Se o pedido envolve esperar por uma condição futura (ex: "me avise quando X acontecer"), use a skill `/loop` em modo dinâmico para reagendar checagens, e dispare a notificação a cada checagem relevante (ou só na mudança de estado, conforme o usuário pedir).
