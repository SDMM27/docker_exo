# Crée .env et les fichiers de secrets (ignorés par git). Windows PowerShell.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
New-Item -ItemType Directory -Force secrets, backups | Out-Null
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
function New-Secret { -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 24 | ForEach-Object { [char]$_ }) }
foreach ($n in "db_password", "grafana_admin_password") {
  $f = Join-Path (Get-Location) "secrets/$n.txt"
  if (-not (Test-Path $f)) { [IO.File]::WriteAllText($f, (New-Secret)) }   # UTF-8 sans BOM, sans retour à la ligne
}
Write-Host "OK : .env et secrets/*.txt prêts (mot de passe Grafana : secrets/grafana_admin_password.txt)"
