---
name: aplicar-migration
description: Escrever, testar com rollback e aplicar uma migration no PostgreSQL do projeto (exemplo com a CLI do Supabase). Use sempre que for mudar tabela, coluna, função, view, política de acesso ou grant -- mesmo que o pedido não diga "migration", só "cria uma coluna", "deixa a tela inserir X", "muda a função Y".
---

# Aplicar uma migration

> Exemplo para PostgreSQL com a CLI do Supabase. Outro banco ou outra ferramenta (Flyway, Alembic, Prisma, sqitch):
> mantenha os passos e troque os comandos. Preencha `<pasta-das-migrations>` e `<pasta-dos-testes-sql>`.

O banco de produção é um só. **Nada se aplica sem antes passar por uma transação que se desfaz sozinha.**

## 1. Ler antes de escrever

- A definição que vale de uma função, view ou política é a da migration **mais recente** que a define:
  `grep -ln "nome_da_coisa" <pasta-das-migrations> | sort | tail -1`. Recrie a partir dela, nunca de uma versão antiga
  (senão desfaz em silêncio o que uma migration posterior pôs).
- Antes de numerar: `git fetch` e a última versão aplicada em produção (só o número). Outra pessoa pode ter usado a sua.
  Use minuto não redondo (`...213700`), para não colidir com quem numera pela hora cheia.

## 2. Escrever o arquivo

`<pasta-das-migrations>/AAAAMMDDHHMMSS_o_que_faz.sql`, com versão maior que a última. Cabeçalho com data, o porquê e a
**ordem de publicação** quando o código depende dela ("esta migration ANTES do serviço novo"). Idempotente sempre que der
(`if not exists`, `create or replace`, `drop policy if exists`).

Junto, o desfazer: `<pasta-do-desfazer>/<versão>_desfazer.sql`, que volta o schema ao que era.

Regras de acesso da casa: `BOAS-PRATICAS.md`, seção 2.1.

## 3. Testar com rollback (TDD)

Os casos vão em `<pasta-dos-testes-sql>/<versão>_<o_que_faz>.sql` (o CI roda todos contra um banco novo com todas as
migrations). O teste roda **pela API** (nada de `\gset`, `\set`, `:variavel` do psql) e **não supõe banco vazio**: confere
só o que ele mesmo criou.

Vermelho: o teste sem a migration falha. Verde: com a migration, passa.

```sql
begin;   -- com ponto e vírgula: sem ele o resto roda fora da transação e grava

-- (o SQL inteiro da migration, colado aqui, para o verde; sem ele, para o vermelho)

do $$
begin
  -- casos: o que deve passar passa, o que deve ser recusado é recusado
  -- acesso por perfil: set local role authenticated; set local request.jwt.claims = '{"sub":"..."}';
  raise exception 'TESTE OK';   -- desfaz tudo; só "TESTE OK" é verde
end $$;
```

Primeiro num banco descartável na máquina (docker), depois o ensaio em produção, que se desfaz sozinho:

```bash
npx --yes supabase@<versão-fixa> db query --linked -f "<scratchpad>/ensaio.sql"
```

Só segue se a saída terminar em `TESTE OK`. Várias migrations na leva: um ensaio único com todas na ordem e todos os
testes, terminando no `raise`. O ensaio trava as tabelas por um instante: rode fora do horário de uso.

## 4. Aplicar e registrar

Só na publicação, depois do CI do PR verde e antes do merge (skill `publicar`):

```bash
npx --yes supabase@<versão-fixa> db query --linked -f <pasta-das-migrations>/<arquivo>.sql
npx --yes supabase@<versão-fixa> migration repair --status applied <versão> --linked
npx --yes supabase@<versão-fixa> db advisors --linked --type security
```

- O verificador de segurança não pode trazer aviso novo ligado ao que você criou.
- **Migration aplicada não se edita:** conserto é migration nova.
- A CLI vai em versão fixa; subir a versão é decisão, num commit próprio.

## 5. Se a escrita for bloqueada

Não contorne. Entregue o SQL pronto para quem tem a permissão rodar, e registre no `duvidas.md`.

## 6. Depois

Compare o schema de produção com um banco montado do repositório (funções, políticas, views, índices, grants): têm de
contar a mesma história. Consulta à produção devolve só schema, números e estados, nunca dado.
