# Política de segurança

## Versões suportadas

Só a branch `main` recebe correção de segurança. Quem usa uma cópia antiga deve atualizar a partir da `main`.

## Como reportar uma falha

**Não abra issue pública.** Use o formulário privado do GitHub:

1. Abra a aba **Security** do repositório.
2. Clique em **Report a vulnerability**
   (<https://github.com/fezarosa-dev/OptimusClaude/security/advisories/new>).

Inclua:

- o que acontece e qual o impacto;
- os passos para reproduzir (comando, arquivo, sistema operacional);
- a versão do Python e do Claude Code;
- uma sugestão de correção, se tiver.

Não inclua segredo real, chave ou dado pessoal no relato.

## Prazos

- Confirmação de recebimento em até **7 dias**.
- Avaliação (se é falha, gravidade e plano) em até **30 dias**.

## Divulgação coordenada

Pedimos que você não divulgue a falha até existir correção na `main`. Combinamos a data juntos e damos o crédito a
quem reportou, se quiser.

## Escopo

É falha de segurança:

- hook ou instalador gravando fora de onde deveriam (por exemplo, fora de `~/.claude` e `~/painel-da-sessao`);
- vazamento de segredo por script, log, painel ou notificação;
- guarda do modo noturno que possa ser contornada (push, escrita na `main`);
- mescla de `settings.json` que apaga ou perde dado do usuário.

Não é falha deste projeto:

- comportamento de ferramentas de terceiros (Claude Code, plugins, RTK, gitleaks e outras): reporte aos projetos delas;
- ajuste que o usuário fez de propósito em suas permissões.

## Boas práticas para quem usa

- Rode `python3 install.py --dry-run` e leia o que seria copiado antes de instalar.
- O modo noturno usa `--dangerously-skip-permissions` e roda **sem supervisão**. Revise a `dev` de manhã, antes de
  qualquer PR para a `main`.
- Use um tópico do ntfy com sufixo aleatório e trate-o como público: a notificação leva só o assunto, nunca segredo.
- Mantenha o gitleaks ativo e nunca coloque `.env` ou chaves no repositório.

Mais detalhes em [docs/seguranca.md](docs/seguranca.md).
