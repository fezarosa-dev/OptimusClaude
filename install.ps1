<#
Embrulho: confere o Python (3.9 ou mais novo) e chama install.py (que faz o trabalho).
Uso: powershell -ExecutionPolicy Bypass -File .\install.ps1 [--dry-run] [--so-checar] [--sem-plugins] [--mesclar-settings]
#>
$py = $null; $pyArgs = @()
$candidatos = @(@('python'), @('python3'), @('py', '-3'))
foreach ($c in $candidatos) {
  $cmd = Get-Command $c[0] -ErrorAction SilentlyContinue
  if (-not $cmd) { continue }
  $extra = @($c | Select-Object -Skip 1)
  # o python.exe de WindowsApps é só um atalho para a Microsoft Store: confere que roda e que é 3.9+
  $ok = & $cmd.Source @extra -c 'import sys; print(int(sys.version_info >= (3, 9)))' 2>$null
  if ($ok -eq '1') { $py = $cmd.Source; $pyArgs = $extra; break }
}
if (-not $py) {
  Write-Host "Python 3.9 ou mais novo não encontrado."
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    $r = Read-Host "Instalar com 'winget install Python.Python.3.12' agora? [s/N]"
    if ($r -match '^[sS]') {
      winget install Python.Python.3.12
      Write-Host "Feche e abra o PowerShell (para atualizar o PATH) e rode install.ps1 de novo."
    }
  } else { Write-Host "Instale o Python 3.9+ em https://www.python.org/downloads/ e rode install.ps1 de novo." }
  exit 1
}
& $py @pyArgs (Join-Path $PSScriptRoot 'install.py') @args
exit $LASTEXITCODE
