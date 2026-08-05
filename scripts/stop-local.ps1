$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$PidFile = Join-Path $Root '.runtime\pids.json'
$StopFile = Join-Path $Root '.runtime\stop.requested'

if (-not (Test-Path -LiteralPath $PidFile)) {
    Write-Host '没有找到由一键启动脚本记录的运行进程。' -ForegroundColor Yellow
    exit 0
}

$payload = Get-Content -Raw -Encoding UTF8 $PidFile | ConvertFrom-Json
$items = if ($null -ne $payload.processes) { @($payload.processes) } else { @($payload) }
$items = @($items | Where-Object { $null -ne $_ -and $null -ne $_.pid })
if ($items.Count -eq 0) {
    Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
    Write-Host '没有需要停止的 LabTime 进程。' -ForegroundColor Yellow
    exit 0
}
New-Item -ItemType File -Path $StopFile -Force | Out-Null
foreach ($item in $items) {
    $process = Get-Process -Id $item.pid -ErrorAction SilentlyContinue
    if (-not $process) {
        Write-Host "$($item.name) 已经停止。" -ForegroundColor DarkGray
        continue
    }

    $recorded = [DateTime]::Parse($item.started_at).ToUniversalTime()
    $actual = $process.StartTime.ToUniversalTime()
    if ([Math]::Abs(($actual - $recorded).TotalSeconds) -gt 2) {
        Write-Host "跳过 PID $($item.pid)：PID 已被其他进程复用。" -ForegroundColor Yellow
        continue
    }

    $taskkill = Start-Process -FilePath taskkill.exe `
        -ArgumentList @('/PID', [string]$item.pid, '/T', '/F') `
        -Wait -PassThru -WindowStyle Hidden
    if ($taskkill.ExitCode -ne 0 -and (Get-Process -Id $item.pid -ErrorAction SilentlyContinue)) {
        Write-Host "无法停止 $($item.name)（PID $($item.pid)），请关闭对应窗口后重试。" -ForegroundColor Yellow
        continue
    }
    Write-Host "已停止 $($item.name)（PID $($item.pid)）。" -ForegroundColor Green
}

Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
Write-Host 'LabTime 本地服务已停止。' -ForegroundColor Green
