# Padrões de arquitetura

Padrões que nasceram num sistema real de vários agentes de IA e valem fora dele. Nenhum é obrigatório; cada um tem o
problema que resolve. Escreva no `CLAUDE.md` do projeto os que você adotar.

## Monorepo com unidades autocontidas

Todas as unidades (serviços, agentes, apps) no mesmo repositório, cada uma na sua pasta, como irmãs.

- **O nome da pasta é a identidade em todo lugar:** pasta, registro no banco e nome do app no deploy. Um nome só.
- **Cada unidade é autocontida:** próprio manifesto, Dockerfile, README e testes. Sobe, cai e volta sem tocar nas outras.
- **Nada específico de uma unidade entra no código compartilhado.** Código sobe para o compartilhado quando o **segundo**
  usuário precisa dele, não antes.
- **Uma unidade não importa da outra.** Se precisa do trabalho da outra, isso é uma mensagem na fila, não um import.
- Unidade nova se cria copiando a que já funciona, e uma guarda (teste) reprova a que vier sem o que toda unidade precisa
  (documento do que faz e **do que não faz**, registro no catálogo).

## Uma fonte única de conhecimento

Regras de domínio moram num lugar só (uma pasta `conhecimento/`, por exemplo). Não existe "manual antigo": documento que
descreve um estado que não existe mais é armadilha; corrija ou apague. Conflito: o conhecimento manda no domínio, o
`CLAUDE.md` manda na engenharia. Regra de domínio muda no conhecimento primeiro, e no código no mesmo commit.

## Migrations versionadas: banco = repositório

- Toda mudança de schema é migration versionada. Nunca pelo console sem a migration.
- A definição que vale de uma função é a da migration mais recente. Leia antes de mudar.
- Migration aplicada não se edita; conserto é migration nova.
- Toda migration de acesso tem o desfazer escrito e ensaiado.
- O CI confere que o banco de produção tem as migrations do repositório (só a versão), e um banco novo montado do
  repositório passa em todos os testes SQL.

## Fila no Postgres antes de um broker

Para volume de escritório, uma tabela de jobs com `FOR UPDATE SKIP LOCKED` resolve: prioridade, tentativas com backoff,
disponível-em, e a execução registrada. Sem Redis, sem Kafka: broker é componente a mais sem problema a resolver.

- O worker fala com a fila **só por funções do banco** (pegar, concluir, falhar, repassar). Nada de SQL de fila à mão:
  concorrência, retentativa e backoff ficam num lugar só. Precisa de comportamento novo? Mude a função.
- Repasse entre unidades cria um job para a outra e a aresta "quem passou trabalho a quem". O mapa do sistema é lido
  desses dados, nunca desenhado à mão: diagrama que não vem dos dados envelhece e mente.

## Idempotência

Todo job pode rodar duas vezes (retentativa, falha no meio, reprocessamento). Use chave de idempotência sempre que houver
um identificador natural, e confira o estado antes de agir. Operação em massa: em lotes, retomável, registrando o que já
passou, com prévia antes do real.

## Tudo o que decide vira evento, com o porquê

Cada decisão do sistema grava um evento (nível, o quê, por quê), sem dado pessoal. Sem isso não há depuração, auditoria
nem confiança de quem usa. Log de auditoria é infraestrutura: só de acréscimo, guardado. Na dúvida, o sistema não
adivinha: separa o caso com o motivo para uma pessoa olhar.

## Ambiente local só com dados fictícios

O projeto inteiro sobe na máquina com um comando, com banco local, serviços e um seed inventado. Uma trava recusa
configuração que aponte para produção. Assim a IA e as pessoas testam de verdade sem que um byte de produção venha para a
máquina.

## Painel web instalável

Web primeiro, instalável (PWA ou empacotado depois), sem versão paralela para manter: evite API que só exista num
navegador, mantenha o estado no servidor e não assuma que a janela é uma aba. Toda tela nasce com o teste dela.

## Resista a construir o palco antes do músico

A plataforma emerge do primeiro caso em produção, não o precede. Cada decisão pergunta: isto serve a vários casos, ou só ao
primeiro? Se só ao primeiro, mora na pasta dele.
