---
name: conferir-producao
description: Ver se a produção está saudável -- serviços de pé, filas andando, falhas e erros recentes, versão publicada certa. Use quando perguntarem "está funcionando?", "por que não andou?", "caiu?", antes de dizer que algo está quebrado, e depois de publicar para confirmar que chegou.
---

# Conferir a produção

> Preencha os comandos de cada passo para o seu projeto (consultas ao banco, endpoints de saúde, logs). Todas as consultas
> só leem e devolvem **números, estados, horários, ids e códigos**: nunca nome de pessoa, documento, mensagem livre ou
> conteúdo de arquivo. Consulta em arquivo no scratchpad, fora do repositório.

**Erro só conta com a data ao lado.** Antes de afirmar que algo está quebrado, mostre a última execução **bem-sucedida**
daquilo: se ela é mais nova que o erro, o erro é passado. Um erro antigo, já resolvido, lido como atual vira pendência
falsa por dias.

## 1. A versão publicada é a certa?

- O commit no ar é o da `main` (ou da branch que produção segue): `<comando: endpoint de versão, git log no servidor...>`.
- O job de publicação do CI está verde: `gh run list --branch main --limit 3`.

## 2. Cada serviço está vivo?

Por serviço: último sinal de vida (batimento, "worker de pé", healthcheck) e há quanto tempo.

```sql
-- exemplo: último evento de início e de fim por serviço
select servicao, max(criado_em) filter (where tipo = 'inicio') as ultimo_inicio,
       max(criado_em) filter (where tipo = 'fim') as ultimo_fim
from <schema>.evento group by 1;
```

## 3. Filas andando?

Quantos itens por estado, o mais velho esperando, e jobs presos em processamento além do tempo normal.

## 4. Erros recentes, com data e com o que veio depois

Últimos N erros por serviço, cada um com o horário e a última execução bem-sucedida depois dele.

## 5. Como responder

Curto, sem jargão: o que está de pé, o que falhou **e quando**, o que já se resolveu sozinho. Números (quantas execuções,
quantos erros, desde quando) em vez de adjetivos. Horários no fuso de quem lê. Nunca dado pessoal na resposta.

Depois de uma publicação: confira em rodadas, por um tempo. Se quebrou, a volta está na skill `publicar` (passo 11).
