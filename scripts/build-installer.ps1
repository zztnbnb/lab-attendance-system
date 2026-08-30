param([switch]$SkipBackend)
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (-not $SkipBackend) { & (Join-Path $PSScriptRoot 'build-backend.ps1') -Clean }
Push-Location (Join-Path $Root 'frontend')
try { & npm run build; if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' } } finally { Pop-Location }
Push-Location $Root
try { & npx electron-builder --projectDir $Root --config (Join-Path $Root 'electron-builder.yml') } finally { Pop-Location }
if ($LASTEXITCODE -ne 0) { throw 'Electron installer build failed.' }
