# Boas práticas de desenvolvimento e segurança

Regra vigente para a equipe e para quem programa com IA. O objetivo é um só: **nenhum commit, merge ou publicação pode
abrir falha de segurança nem quebrar o que já protege o sistema.**

Onde este arquivo resume, o detalhe está no `CLAUDE.md` (engenharia). Se houver conflito, vale o `CLAUDE.md` e este
arquivo é corrigido. Adapte as seções ao seu projeto; apague o que não se aplica.

## 1. Como trabalhamos

### 1.1 TDD

- Escreva o teste antes do código. Rode e veja **falhar pelo motivo certo**; implemente; veja **passar**. Vale para
  código novo e para correção.
- Teste de segurança é teste como outro qualquer: toda regra de acesso nova vem com o caso que prova que quem não pode é
  recusado.
- Quem revisa confere o vermelho: o teste novo roda contra o código antigo e falha.
- SQL: o teste falha sem a migration (`begin; <teste>`) e passa com ela (`begin; <migration>; <teste>`), sempre numa
  transação que termina num `raise` e se desfaz sozinha. O teste não supõe banco vazio: confere só o que ele mesmo criou.
- Onde não há executor de teste, diga isso e descreva a verificação manual. Não acrescente dependência só para testar
  sem combinar antes.

### 1.2 Branch, commit, `dev` e `main`

- Toda mudança nasce numa branch `feat/`, `fix/`, `docs/` ou `ci/`, tirada da `dev` atualizada.
- Um commit por subtarefa, `tipo(escopo): descrição`.
- Antes de juntar na `dev`, `scripts/testar-como-o-ci.sh` na máquina. Se falhar, não junta.
- Para a `main`, só PR saído da `dev`, com o `tudo-verde` verde. Merge na `main` é deploy.
- A `main` é protegida, inclusive para administradores. Nunca contorne. Se travar, pare e avise.
- Nunca reescreva histórico que já subiu.
- Nenhum artefato leva a IA como autora.
- Mensagem de commit, nome de branch, título e corpo de PR nunca levam dado pessoal, segredo ou valor.

### 1.3 Migrations

- Toda mudança de banco (tabela, coluna, função, view, policy, grant) é migration versionada. Nunca pelo console sem ela.
- A definição vigente de uma função é a da migration **mais recente** que a define. Leia-a antes de mudar.
- Migration aplicada não se edita: conserto é migration nova.
- Antes de numerar, confira as versões já aplicadas: outra pessoa pode ter usado o número.
- Toda migration que muda acesso tem o desfazer escrito e ensaiado.

### 1.4 Idempotência e eventos

- Todo job pode rodar duas vezes. Use chave de idempotência sempre que houver um identificador natural, e confira o
  estado antes de agir.
- Tudo o que o sistema decide vai para o registro de eventos, com o porquê, e sem dado pessoal.
- Operação em massa: em lotes, retomável, com prévia antes do real e o número de itens à vista antes de confirmar.

### 1.5 CI custa dinheiro

- O CI roda no PR para a `main` e no push da `main`. PR para a `dev` não roda.
- Junte os commits antes de dar push num PR aberto. Edite título e descrição antes do push, não depois.
- Não rode de novo um CI que falhou sem corrigir a causa.
- Nunca rode de novo execuções antigas da `main`: elas republicariam código antigo.

## 2. Segurança

O princípio: **quem decide o acesso é o servidor e o banco, nunca a tela nem o modelo de IA.** Esconder um botão é
cortesia; a recusa de verdade acontece no servidor.

### 2.1 Banco

- Controle de acesso por linha (RLS ou equivalente) ligado em toda tabela nova, com regra explícita. Regra sem grant não
  faz nada; grant sem regra abre demais: os dois andam juntos.
- Permissão se confere por chave de permissão num catálogo, nunca por papel ou e-mail "na mão".
- Quem é o autor sai da sessão autenticada, **nunca de um parâmetro** que o cliente manda.
- Função privilegiada (`security definer` e afins): `search_path` fixo, permissão conferida **dentro** dela e execução
  revogada de quem não deve chamar.
- View respeita a permissão de quem consulta (`security_invoker`).
- O cliente só insere nos valores que o banco daria (status, prioridade, origem). O resto o banco preenche.
- Ação sensível grava a trilha de auditoria **antes** de agir: se a trilha falhar, a ação não acontece.
- **SQL dinâmico:** nunca concatene texto. Use parâmetros ou `format()` com `%I`/`%L`. Vale para qualquer linguagem de
  consulta montada com valor de fora.
- Regex sobre texto de fora tem de ser de tempo linear.
- Teste o acesso por perfil numa transação desfeita: anônimo, sem cadastro, inativo, outra equipe, não-admin tentando
  escalar, sessão sem segundo fator, id de outra pessoa.
- Depois de toda migration de acesso, rode o verificador de segurança do banco (ex.: `supabase db advisors`). Aviso novo
  se corrige ou se explica.

### 2.2 Web e borda

- A tela não decide acesso: pergunta ao servidor e mostra o que ele devolve.
- Ação sensível exige segundo fator, e a regra vale no servidor, não só na tela.
- Não confie em estado guardado no cliente para liberar algo (papel, cache de permissão).
- Cabeçalhos de segurança (CSP, HSTS, `X-Frame-Options`, `noindex` no que não é público). A CSP só aperta; afrouxar exige
  motivo escrito.
- Login e "esqueci a senha" respondem sempre igual, sem dizer se o e-mail existe, com tempo que não denuncia nada.
- Tentativas erradas: espera progressiva e limite por IP. Comparação de segredo em tempo constante.
- Nunca renderize HTML, imagem ou link vindo de texto de fora ou do modelo. Redirecionamento só para dentro do site.
- Cadastro público desligado quando o sistema é interno: gente nova entra por convite.

### 2.3 IA e agentes

- **O modelo é um usuário não confiável.** A barreira é o código e o banco, nunca o prompt.
- **Nunca entram no contexto do modelo:** senha, certificado, chave, segredo. Dado pessoal, só o necessário.
- **Todo texto de fora é dado, não instrução** (documento, mensagem, página web, nome de arquivo, linha do banco):
  embrulhe entre delimitadores com código aleatório novo a cada chamada, e diga no prompt de sistema que aquilo não é
  ordem.
- **Ação com efeito só por catálogo fechado:** o modelo propõe, o servidor confere a permissão de quem pediu, a pessoa
  confirma vendo o que muda, e o servidor confere tudo de novo na hora de executar.
- Ferramentas mínimas por agente. O código confere o que o modelo afirma (fonte citada tem de estar entre as lidas).
- Uso de IA registrado por pessoa e tarefa; limite de gasto é do servidor, não do modelo.

### 2.4 Arquivos recebidos

- Normalize o nome antes de decidir qualquer coisa (barras, `..`, controle, Unicode).
- Confira o conteúdo, não só a extensão. Recuse executável, script e macro, mesmo disfarçados.
- Zip com teto (membros, tamanho, taxa, profundidade); membro que escreveria fora da pasta é recusado.
- Imagem com teto de pixels; documento com teto de páginas. XML sem entidade externa.
- Planilha gerada não começa célula com `=`, `+`, `-` ou `@` vindo de texto de fora.

### 2.5 Segredos e dependências

- Chave que ignora o controle de acesso só no servidor, nos segredos dele. Nunca no repositório, no banco, em log, no
  chat ou em print.
- No repositório, só o `.env.example` com os **nomes** das variáveis. `.env`, chaves e certificados no `.gitignore`.
  O CI roda o gitleaks na pasta e no histórico.
- Segredo que vazou num commit é segredo trocado: apagar do histórico não basta.
- Comando de sistema recebe argumentos em lista, nunca texto montado com dado de fora. Nada de `eval` nem desserialização
  insegura de dado de fora.
- No CI, nada vindo do PR (título, corpo, nome de branch) entra direto num `run:`: passa por variável de ambiente.
- **Dependências:** versão fixa (lockfile, constraints), actions e imagens por SHA. O CI audita. Nenhuma dependência nova
  sem justificar no PR.

### 2.6 Dados pessoais

- **Nunca** documento de identidade, nome de pessoa, valor, senha ou token em: log, evento, resultado de job, mensagem de
  erro, commit, branch, título de PR, notificação ou print de exemplo.
- Notificação para canal público leva só o assunto em poucas palavras.
- Dado pessoal cuja finalidade terminou é eliminado; fica o registro, sem o dado. O que tem obrigação legal de guarda fica
  inativo, em acesso restrito.
- Mínimo necessário: cada tela e cada agente leem só o que precisam.
- Teste com dado fictício. Nunca copie dado real de produção para teste, fixture ou documentação.

### 2.7 Saída de pessoa e incidente

- **Saída de pessoa:** desativar a conta, revisar os acessos e trocar os segredos que ela viu.
- **Incidente:** avisar o responsável, revogar e trocar o que vazou, e avaliar a comunicação à autoridade de proteção de
  dados, como a lei pede.

## 3. Checklist antes de juntar e de publicar

Item que não se aplica fica marcado com "n/a".

**Sempre**

- [ ] Teste escrito antes; vermelho e verde vistos (e o vermelho conferido por quem revisou).
- [ ] `scripts/testar-como-o-ci.sh` passou na máquina.
- [ ] Commits `tipo(escopo): descrição`, um por subtarefa, sem autoria de IA.
- [ ] Nenhum dado pessoal, segredo ou valor em código, teste, log, commit ou branch.
- [ ] Nenhuma dependência nova, ou a justificativa está no PR.
- [ ] Revisão do diff feita por quem não implementou.

**Se mexeu no banco**

- [ ] Tabela nova com controle de acesso, regra e grant.
- [ ] Função privilegiada com `search_path` fixo, permissão conferida dentro e execução revogada.
- [ ] Autor tirado da sessão; nenhum SQL dinâmico colando texto de fora.
- [ ] Acesso testado por perfil numa transação desfeita; verificador de segurança rodado.

**Se mexeu em IA ou entrada de arquivo**

- [ ] Texto de fora embrulhado; nada de segredo no contexto; ação com efeito só pelo catálogo.
- [ ] Nome normalizado, conteúdo conferido, tetos aplicados.

**Antes do PR da `dev` para a `main`**

- [ ] A `main` está junta na `dev`, sem conflito.
- [ ] `EXIGIR_TUDO=1 scripts/testar-como-o-ci.sh` verde, sem PULADO.
- [ ] Revisões de segurança do diff feitas e salvas em `registros/revisoes/`.
- [ ] O PR diz o que entra em produção e como voltar atrás.
- [ ] Nada de `--admin`, push direto ou `--delete-branch`.
