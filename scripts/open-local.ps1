$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$RuntimeDir = Join-Path $Root '.runtime'
$PidFile = Join-Path $RuntimeDir 'pids.json'
$UrlFile = Join-Path $RuntimeDir 'last-url.txt'
$url = $null

if (Test-Path -LiteralPath $PidFile) {
    try {
        $payload = Get-Content -Raw -Encoding UTF8 $PidFile | ConvertFrom-Json
        $url = $payload.frontend_url
    } catch {}
}
if (-not $url -and (Test-Path -LiteralPath $UrlFile)) {
    $url = (Get-Content -Raw -Encoding ASCII $UrlFile).Trim()
}
if (-not $url) {
    Write-Host '没有找到运行中的 LabTime 地址，请先双击“一键启动.bat”。' -ForegroundColor Yellow
    exit 1
}

try {
    $response = Invoke-WebRequest -UseBasicParsing -Uri "$url/login" -TimeoutSec 3
    if ($response.StatusCode -ne 200) { throw '页面未就绪' }
} catch {
    Write-Host "LabTime 当前没有在 $url 运行，请重新双击“一键启动.bat”。" -ForegroundColor Yellow
    exit 1
}

$explorer = Join-Path $env:WINDIR 'explorer.exe'
[System.Diagnostics.Process]::Start($explorer, $url) | Out-Null
Write-Host "已打开 $url" -ForegroundColor Green
