# Linguagens e ferramentas

O fluxo não depende de linguagem: depende de ter, para cada uma, um **executor de teste**, um **linter** e (quando
existe) um **verificador de tipos**, todos rodando por linha de comando. Cada um vira uma verificação no mapa do
`scripts/o_que_testar.py` do `projeto-modelo/`, e a mesma linha roda na máquina e no CI. Como instalar cada ferramenta:
[dependencias.md](dependencias.md).

| Linguagem | Teste | Lint / tipos | Segurança e dependências | Verificação no mapa (exemplo) |
|---|---|---|---|---|
| **Python** (uv) | `pytest` | `ruff`, `mypy` ou `pyright` (opcional) | `pip-audit` | `uv run --frozen pytest -q && uvx ruff check .` |
| **TypeScript / JavaScript** (node) | `vitest` (unidade), **Playwright** (tela) | `eslint`, `tsc --noEmit` | `npm audit` | `npm ci && npm run lint && npx tsc --noEmit && npx vitest run --maxWorkers=2` |
| **SQL / PostgreSQL** | testes em transação que se desfaz, contra um banco novo no docker com todas as migrations | — | verificador do banco (ex.: `supabase db advisors --type security`) | `bash scripts/testes_sql.sh` |
| **Bash** | `bats` (opcional) ou teste em Python chamando o script | `shellcheck` | — | `git ls-files -z '*.sh' \| xargs -0 -r shellcheck` |
| **PowerShell** | `Pester` (com `pwsh`) | `PSScriptAnalyzer` | — | `pwsh -c "Invoke-ScriptAnalyzer -Recurse -Path . -EnableExit"` |
| **Deno** (ex.: Edge Functions) | `deno test` | `deno lint`, `deno check` | — | `deno lint && deno check **/*.ts && deno test` |
| **Docker** | build da imagem | `hadolint` | `trivy image` | `hadolint Dockerfile` |
| **GitHub Actions** | — | `actionlint` | ação fixada por SHA | `actionlint` |
| **Segredos e dependências** (todas) | — | — | `gitleaks`, `osv-scanner`, `trivy fs`, `semgrep` | `gitleaks git --redact . && osv-scanner -r .` |

Notas:

- **Python:** um venv por unidade, com as versões do lockfile/constraints, como o CI. `uv run --with-requirements` não
  respeita constraints: crie o venv.
- **Tela (Playwright):** poucos navegadores em paralelo; site completo só antes do PR para a `main`
  ([testes-e-qualidade.md](testes-e-qualidade.md)).
- **SQL:** sem `\gset`/`\set` (o teste roda pela API) e sem supor banco vazio. Modelo do teste e da aplicação na skill
  `aplicar-migration` do `projeto-modelo/`.
- **PowerShell sem `pwsh` na máquina:** a verificação fica `PULADO` e o `EXIGIR_TUDO=1` reprova. Instale o `pwsh` e o
  PSScriptAnalyzer na mesma versão do CI.
- **semgrep:** só na máquina, nas revisões antes de publicar; não precisa virar passo do CI.

## Acrescentar outra linguagem

1. Escolha o executor de teste, o linter e o verificador de tipos que rodam por linha de comando e saem com código ≠ 0 ao
   falhar.
2. Acrescente a verificação em `VERIFICACOES` (os programas de que precisa e o comando) e os caminhos no `MAPA` do
   `scripts/o_que_testar.py`. Um teste em `scripts/test_scripts.py` garante que todo passo do mapa existe.
3. No `.github/workflows/testes.yml`, acrescente o setup da linguagem (com versão fixa).
4. Rode `SO_DECIDIR=1 python3 scripts/testar_como_o_ci.py` para ver o mapa ligar o passo, e a bateria para ver passar.
5. **Navegação:** o Serena cobre por LSP dezenas de linguagens (Go, Rust, Java, Kotlin, C#, C/C++, Ruby, PHP, Elixir,
   Swift...). Se a sua não estiver ativa, ligue o servidor de linguagem no Serena; o `ccc` indexa qualquer texto.

Exemplos de linhas para linguagens comuns fora da tabela:

| Linguagem | Verificação |
|---|---|
| Go | `go vet ./... && go test ./...` (+ `govulncheck ./...`) |
| Rust | `cargo clippy -- -D warnings && cargo test` (+ `cargo audit`) |
| Java / Kotlin | `./gradlew check` |
| C# | `dotnet test && dotnet format --verify-no-changes` |
| Ruby | `bundle exec rspec && bundle exec rubocop` |
| PHP | `vendor/bin/phpunit && vendor/bin/phpstan analyse` |
