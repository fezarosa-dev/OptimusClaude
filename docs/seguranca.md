# Segurança

O princípio: **quem decide o acesso é o servidor e o banco, nunca a tela nem o modelo de IA.** Esconder um botão é
cortesia; a recusa de verdade acontece no servidor. A versão completa, para colar no projeto, é o
`projeto-modelo/BOAS-PRATICAS.md`.

## Segredos

- No repositório, só o `.env.example` com os **nomes** das variáveis. `.env`, chaves e certificados no `.gitignore` (o do
  `projeto-modelo/` já vem pronto).
- Chave que passa por cima do controle de acesso (service role, admin key) só no servidor. Nunca em log, chat, print,
  banco ou arquivo da sessão.
- O gitleaks roda na bateria e no CI, na pasta e no histórico.
- Segredo que vazou num commit é segredo trocado: apagar do histórico não basta.
- Notificação para canal público (ntfy e afins) leva só o assunto em poucas palavras. Escolha um tópico difícil de
  adivinhar e trate-o como público.

## Menor privilégio

- Cada credencial com o menor alcance possível; trocada quando alguém sai.
- Cada agente de IA com as ferramentas mínimas: lista fechada de tabelas, ações e sites.
- Token do CI só de leitura por padrão; só o job que publica pede escrita.
- Permissão por chave num catálogo, conferida no servidor; nunca por papel ou e-mail "na mão".
- Autor tirado da sessão autenticada, nunca de um parâmetro do cliente.

## IA como usuário não confiável

- A barreira é o código e o banco, nunca o prompt.
- Texto de fora (documento, mensagem, página, nome de arquivo) é dado, não instrução: entre delimitadores com código
  aleatório por chamada.
- Ação com efeito só por catálogo fechado, com confirmação de quem pode e nova conferência na hora de executar.
- Nada de segredo no contexto do modelo; dado pessoal só o necessário.

## Dado pessoal

- Nunca em log, evento, mensagem de erro, commit, branch, título de PR ou notificação.
- **LGPD (ou a lei do seu país) acima de "nada é apagado":** o padrão pode ser inativar com histórico, mas dado pessoal
  cuja finalidade terminou é eliminado, ficando o registro sem o dado. O que tem obrigação legal de guarda fica inativo,
  em acesso restrito.
- Mínimo necessário: cada tela e cada agente leem só o que precisam.

## Nenhum dado de produção na máquina

- O ambiente local roda só com dado fictício (seed inventado). Mais dado = mais seed.
- Consulta à produção devolve só números, estados, horários, ids e códigos; para cruzar valores, compare no próprio
  banco e devolva só a contagem.
- O que passa pela conversa fica no histórico local da sessão. Dado real só com pedido expresso e confirmação de quem
  responde por ele.
- Trabalho que precisa ler dado real (medir acerto, reprocessar) roda onde o dado já está e grava só números.

## Revisões de segurança antes de publicar

Antes do PR `dev → main`, sobre o diff `main...dev`:

| Ferramenta | O que pega | Custo |
|---|---|---|
| `/security-review` | Revisão de segurança das mudanças pendentes | licença |
| Claude Security (modo "scan changes") | Varredura com agentes e verificação por painel | licença, alto: avise antes |
| `semgrep` (`uvx semgrep --config auto`) | Padrões conhecidos de vulnerabilidade | só máquina |
| `gitleaks` | Segredo no código e no histórico | só máquina |
| `insecure-defaults:audit` | Segredo de fallback, credencial padrão, fail-open, debug ligado | licença |
| Auditoria de dependências (`pip-audit`, `npm audit`, `osv-scanner`, `trivy`) | Versão com vulnerabilidade conhecida | só máquina |

- O que gasta licença roda **só no diff**; o que gasta só máquina pode rodar no repositório inteiro.
- **Nenhuma ferramenta corrige sozinha.** Cada achado vira tarefa: teste que falha, correção, revisão, bateria.
- Cada relatório é salvo em `registros/revisoes/` (o `salvar_revisao.py` recusa relatório com segredo ou dado pessoal).
- Achado em código de outra pessoa vai para ela; não corrija sem combinar.

## A `main` protegida

- Só entra por PR; o PR só sai da `dev`; o check `tudo-verde` tem de estar verde.
- Proteção vale também para administradores: sem push direto, force-push, `--admin` ou desligar a regra.
- Se algo travar, pare e avise. Nunca contorne.
- No CI, nada vindo do PR (título, corpo, nome de branch) entra direto num `run:`: passa por variável de ambiente.
- Actions fixadas por SHA; binários baixados com versão fixa e checksum conferido.
- Dependências com versão fixa (lockfile, constraints); nenhuma nova sem justificativa no PR.

## Incidente e saída de pessoa

- **Saída de pessoa:** desativar a conta, revisar acessos, trocar os segredos que ela viu.
- **Suspeita de vazamento:** avisar o responsável, revogar e trocar o que vazou, avaliar a comunicação à autoridade de
  proteção de dados.
