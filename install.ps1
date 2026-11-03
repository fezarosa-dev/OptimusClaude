<#
Instala a configuração do Claude Code deste repositório no Windows (nativo, sem WSL).
  claude\*  -> %USERPROFILE%\.claude  (com backup do que já existe e for diferente)
O painel da sessão NÃO é instalado: ele depende de Linux (/proc, ps, ip). Para tê-lo, use o WSL (veja o README).
Depois confere (e instala, quando há instalador seguro) as dependências e os plugins.
Idempotente: rodar de novo só copia o que mudou.

Uso (no PowerShell, dentro da pasta do repositório):
  powershell -ExecutionPolicy Bypass -File .\install.ps1 [-DryRun] [-SoChecar] [-SemPlugins]
    -DryRun      mostra o que faria, sem mudar nada
    -SoChecar    não grava nada: só confere e lista o que falta e os arquivos que seriam copiados
    -SemPlugins  pula marketplaces e plugins do Claude Code
#>
param([switch]$DryRun, [switch]$SoChecar, [switch]$SemPlugins, [switch]$Help)

if ($Help) { Get-Help $PSCommandPath -Full | Out-String | Write-Output; exit 0 }
if ($SoChecar) { $DryRun = $true }
$ErrorActionPreference = 'Stop'

$Raiz = $PSScriptRoot
$ClaudeDir = if ($env:CLAUDE_CONFIG_DIR) { $env:CLAUDE_CONFIG_DIR } else { Join-Path $HOME '.claude' }
$Backup = Join-Path $ClaudeDir ("backups\optimusclaude-" + (Get-Date -Format 'yyyyMMdd-HHmmss'))
$Falta = New-Object System.Collections.Generic.List[string]
$script:Feito = 0

function Say($t) { Write-Host $t }
function Tem($bin) { [bool](Get-Command $bin -ErrorAction SilentlyContinue) }
# roda uma ação que grava; no -DryRun só descreve, no -SoChecar nem isso
function Run([string]$descricao, [scriptblock]$acao) {
  if ($SoChecar) { return $true }
  if ($DryRun) { Say "  [dry-run] $descricao"; return $true }
  try { & $acao; return $true } catch { return $false }
}

if (-not $IsWindows -and $PSVersionTable.PSEdition -eq 'Core') {
  Say "Aviso: este é o instalador do Windows. No Linux e no macOS use ./install.sh (que instala também o painel)."
}

# copia um arquivo; se o destino existe e é diferente, guarda o antigo no backup
function Copiar($src, $dst, $rel) {
  if ((Test-Path -LiteralPath $dst -PathType Leaf) -and
      ((Get-FileHash -LiteralPath $src).Hash -eq (Get-FileHash -LiteralPath $dst).Hash)) { return }
  if (Test-Path -LiteralPath $dst) {
    $bk = Join-Path $Backup $rel
    Run "backup $rel" { New-Item -ItemType Directory -Force -Path (Split-Path $bk) | Out-Null; Copy-Item -LiteralPath $dst $bk -Force } | Out-Null
  }
  Run "copiar $rel" { New-Item -ItemType Directory -Force -Path (Split-Path $dst) | Out-Null; Copy-Item -LiteralPath $src $dst -Force } | Out-Null
  Say "  $rel"
  $script:Feito++
}

Say "== Arquivos de configuração -> $ClaudeDir"
$origem = Join-Path $Raiz 'claude'
Get-ChildItem -LiteralPath $origem -Recurse -File -Force |
  Where-Object { $_.Name -ne 'settings.example.json' -and $_.Extension -ne '.pyc' -and $_.FullName -notmatch '[\\/]__pycache__[\\/]' } |
  ForEach-Object {
    $rel = $_.FullName.Substring($origem.Length + 1)
    Copiar $_.FullName (Join-Path $ClaudeDir $rel) ("claude/" + ($rel -replace '\\', '/'))
  }
Copiar (Join-Path $origem 'settings.example.json') (Join-Path $ClaudeDir 'settings.example.json') 'claude/settings.example.json'
if ($script:Feito -eq 0) { Say "  nada mudou" }
if (Test-Path $Backup) { Say "  backup do que foi substituído: $Backup" }
Say "  painel da sessão: não instalado no Windows nativo (precisa de Linux; use o WSL)"

Say "== settings.json"
$Settings = Join-Path $ClaudeDir 'settings.json'
if (-not (Test-Path $Settings)) {
  # no Windows não há painel: a linha de status usa a avulsa, e o Python se chama python
  $texto = [IO.File]::ReadAllText((Join-Path $origem 'settings.example.json'))
  $texto = $texto.Replace('python3 \"$HOME/painel-da-sessao/statusline.py\"', 'python \"$HOME/.claude/statusline/statusline.py\"')
  Run "criar settings.json" { [IO.File]::WriteAllText($Settings, $texto, (New-Object Text.UTF8Encoding($false))) } | Out-Null
  Say "  criado a partir do exemplo; troque os placeholders <...> em env"
  $Falta.Add("editar ${Settings}: NTFY_TOPICO, NTFY_TOPICO_PERGUNTA (e OBSIDIAN_VAULT, se usar /snote)")
} else {
  Say "  já existe e não foi mexido. Compare com $(Join-Path $ClaudeDir 'settings.example.json')"
}
if (Test-Path $Settings) {
  try {
    $j = Get-Content -Raw $Settings | ConvertFrom-Json
    $cmds = @($j.hooks.PreToolUse | ForEach-Object { $_.hooks } | ForEach-Object { $_.command })
    if (-not ($cmds -match 'rtk hook')) { $Falta.Add("o hook do rtk não está no settings.json (rode 'rtk init -g' ou copie o bloco hooks do exemplo)") }
  } catch { $Falta.Add("$Settings não é um JSON válido") }
}

# instala com o comando dado se a ferramenta falta e há instalador; senão anota o que falta
function Garantir($bin, $obrig, $como, [string[]]$instalar) {
  if (Tem $bin) { Say "  ok       $bin"; return }
  if (-not $SoChecar -and $instalar -and (Tem $instalar[0])) {
    Say "  instalando ${bin}: $($instalar -join ' ')"
    $ok = Run ($instalar -join ' ') { & $instalar[0] $instalar[1..($instalar.Length - 1)] *> $null; if ($LASTEXITCODE) { throw 'falhou' } }
    if ($ok -and ($DryRun -or (Tem $bin))) { return }
  }
  Say "  FALTA    $bin ($obrig)"
  $Falta.Add("$bin (${obrig}): $como")
}

Say "== Dependências (detalhes em docs/dependencias.md)"
Garantir git      obrigatória "winget install Git.Git (traz o Git Bash, que o Claude Code usa no Windows)"
Garantir node     obrigatória "winget install OpenJS.NodeJS.LTS; precisa para context-mode e caveman"
if ((Tem python) -or (Tem py)) { Say "  ok       python" } else {
  Say "  FALTA    python (obrigatória)"; $Falta.Add("python (obrigatória): winget install Python.Python.3.12; a statusline e os scripts usam")
}
Garantir uv       obrigatória "winget install astral-sh.uv"
Garantir rtk      obrigatória "veja https://github.com/rtk-ai/rtk (binário da release ou cargo); depois 'rtk init -g'"
Garantir caveman  obrigatória "npm i -g @caveman-ai/cli; depois 'caveman hooks install claude'" @('npm', 'i', '-g', '@caveman-ai/cli')
Garantir serena   obrigatória "uv tool install serena-agent" @('uv', 'tool', 'install', 'serena-agent')
Garantir ccc      obrigatória "uv tool install cocoindex-code" @('uv', 'tool', 'install', 'cocoindex-code')
Garantir gh       recomendada "winget install GitHub.cli"
Garantir jq       recomendada "winget install jqlang.jq"
Garantir gitleaks recomendada "winget install Gitleaks.Gitleaks"
Garantir semgrep  opcional    "uv tool install semgrep" @('uv', 'tool', 'install', 'semgrep')
Garantir curl     recomendada "já vem no Windows 10 e 11 (curl.exe); os avisos do ntfy usam"

Say "== Claude Code"
if (-not (Tem claude)) {
  $Falta.Add("claude (obrigatória): https://docs.claude.com/claude-code — rode este script de novo depois")
  Say "  FALTA    claude: pulando plugins e MCP"
} else {
  Say "  ok       claude"
  function LerClaude([string[]]$a) { & claude @a 2>$null | Out-String }
  if (Tem serena) {
    $mcp = @('mcp', 'add', '-s', 'user', 'serena', '--', 'serena', 'start-mcp-server', '--context', 'claude-code', '--project-from-cwd')
    & claude mcp get serena *> $null
    if ($LASTEXITCODE -eq 0) { Say "  ok       MCP serena" }
    elseif ($SoChecar -or -not (Run "claude $($mcp -join ' ')" { & claude @mcp *> $null; if ($LASTEXITCODE) { throw 'falhou' } })) {
      $Falta.Add("MCP serena: claude $($mcp -join ' ')")
    }
  }

  if (-not $SemPlugins) {
    $marketplaces = @('anthropics/claude-plugins-official', 'mksglu/context-mode', 'DietrichGebert/ponytail', 'trailofbits/skills',
                      'guillaumemeyer/watermarks-remover', 'latent-spaces/brag')
    $plugins = @('superpowers@claude-plugins-official', 'claude-code-setup@claude-plugins-official', 'skill-creator@claude-plugins-official',
                 'code-simplifier@claude-plugins-official', 'claude-security@claude-plugins-official', 'security-guidance@claude-plugins-official',
                 'pyright-lsp@claude-plugins-official', 'typescript-lsp@claude-plugins-official', 'context-mode@context-mode', 'ponytail@ponytail',
                 'insecure-defaults@trailofbits', 'watermarks-remover@watermarks-remover', 'brag@brag')
    $jaMp = LerClaude @('plugin', 'marketplace', 'list')
    $jaPl = LerClaude @('plugin', 'list')
    function Marketplace($m, $nome) {
      if ($jaMp -like "*$nome*") { Say "  ok       marketplace $nome"; return }
      if ($SoChecar -or -not (Run "claude plugin marketplace add $m" { & claude plugin marketplace add $m *> $null; if ($LASTEXITCODE) { throw 'falhou' } })) {
        $Falta.Add("marketplace: claude plugin marketplace add $m")
      }
    }
    function Plugin($p) {
      if ($jaPl -like "*$p*") { Say "  ok       plugin $p"; return }
      if ($SoChecar) { $Falta.Add("plugin: claude plugin install $p"); return }
      if (Run "claude plugin install $p" { & claude plugin install $p *> $null; if ($LASTEXITCODE) { throw 'falhou' } }) {
        if (-not $DryRun) { Say "  instalado plugin $p" }
      } else { $Falta.Add("plugin: claude plugin install $p") }
    }
    $marketplaces | ForEach-Object { Marketplace $_ $_.Split('/')[-1] }
    $plugins | ForEach-Object { Plugin $_ }
    # mods de interface do repositório (claude\mods -> ~\.claude\mods), marketplace local
    $mods = Join-Path $ClaudeDir 'mods'
    if ((Test-Path (Join-Path $mods '.claude-plugin')) -or $DryRun) {
      Marketplace $mods 'optimus-mods'
      Plugin 'status-bar@optimus-mods'
      Plugin 'painel-agentes@optimus-mods'
    }
  }
}

Say ""
if ($Falta.Count -eq 0) {
  Say "Tudo certo. Abra uma sessão nova do Claude Code para carregar a configuração."
} else {
  Say "Falta fazer ($($Falta.Count)):"
  $Falta | ForEach-Object { Say "  - $_" }
  Say "Rode o install.ps1 de novo depois: o que já está certo é pulado."
}
Say "Skills de terceiros (caveman, find-skills etc.) não vêm neste repositório: veja docs/dependencias.md."
Say "Quer o painel da sessão? Instale pelo WSL: veja a seção Windows do README."
