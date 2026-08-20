param(
    [switch]$SkipInstall,
    [switch]$NoBrowser,
    [switch]$CheckOnly,
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 5173
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$BackendDir = Join-Path $Root 'backend'
$FrontendDir = Join-Path $Root 'frontend'
$RuntimeDir = Join-Path $Root '.runtime'
$PidFile = Join-Path $RuntimeDir 'pids.json'
$StopFile = Join-Path $RuntimeDir 'stop.requested'
$UrlFile = Join-Path $RuntimeDir 'last-url.txt'
$LogFile = Join-Path $RuntimeDir 'launcher.log'
$VenvPython = Join-Path $Root '.venv\Scripts\python.exe'
$Processes = [System.Collections.Generic.List[object]]::new()
$OwnsPidFile = $false
$FrontendUrl = $null
$BackendUrl = $null
$TranscriptStarted = $false

function Write-Step([string]$Message) {
    Write-Host "`n==> $Message" -ForegroundColor Cyan
}

function Write-Ok([string]$Message) {
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Test-Python312([string]$Path) {
    if (-not $Path -or -not (Test-Path -LiteralPath $Path)) { return $false }
    try {
        $result = @(& $Path -c "import sys; print(int(sys.version_info >= (3, 12)))" 2>$null)
        return $LASTEXITCODE -eq 0 -and $result[-1] -eq '1'
    } catch { return $false }
}

function Find-Python {
    $candidates = [System.Collections.Generic.List[string]]::new()
    if ($env:LABTIME_PYTHON) { $candidates.Add($env:LABTIME_PYTHON) }
    if (Test-Path -LiteralPath $VenvPython) { $candidates.Add($VenvPython) }

    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) {
        try {
            $launcherPython = @(& $launcher.Source -3.12 -c "import sys; print(sys.executable)" 2>$null)
            if ($LASTEXITCODE -eq 0 -and $launcherPython) { $candidates.Add($launcherPython[-1]) }
        } catch {}
    }

    $command = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($command) { $candidates.Add($command.Source) }

    $codexPattern = Join-Path $env:USERPROFILE '.cache\codex-runtimes\*\dependencies\python\python.exe'
    Get-ChildItem -Path $codexPattern -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        ForEach-Object { $candidates.Add($_.FullName) }

    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if (Test-Python312 $candidate) { return (Resolve-Path $candidate).Path }
    }
    throw '未找到 Python 3.12 或更高版本。请安装 Python 3.12，并重新双击启动脚本。'
}

function Test-BackendDependencies([string]$Python) {
    & $Python -c "import fastapi, uvicorn, sqlalchemy, cv2, cryptography" 2>$null
    return $LASTEXITCODE -eq 0
}

function Install-Backend([string]$BootstrapPython) {
    Write-Step '创建 Python 虚拟环境并安装后端依赖（仅首次运行）'
    if (-not (Test-Path -LiteralPath $VenvPython)) {
        & $BootstrapPython -m venv (Join-Path $Root '.venv')
        if ($LASTEXITCODE -ne 0) { throw '创建 Python 虚拟环境失败。' }
    }
    Push-Location $BackendDir
    try {
        & $VenvPython -m pip install -e '.[dev]'
        if ($LASTEXITCODE -ne 0) { throw '后端依赖安装失败，请检查网络连接。' }
    } finally { Pop-Location }
    return $VenvPython
}

function Install-Frontend {
    Write-Step '安装前端依赖（仅首次运行）'
    Push-Location $FrontendDir
    try {
        $pnpm = Get-Command pnpm.cmd -ErrorAction SilentlyContinue
        if (-not $pnpm) { $pnpm = Get-Command pnpm -ErrorAction SilentlyContinue }
        if ($pnpm) {
            & $pnpm.Source install
        } else {
            $corepack = Get-Command corepack.cmd -ErrorAction SilentlyContinue
            if (-not $corepack) { $corepack = Get-Command corepack -ErrorAction SilentlyContinue }
            if ($corepack) {
                & $corepack.Source pnpm install
            } else {
                $npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
                if (-not $npm) { throw '未找到 pnpm、Corepack 或 npm，请先安装 Node.js 20 或更高版本。' }
                & $npm.Source install
            }
        }
        if ($LASTEXITCODE -ne 0) { throw '前端依赖安装失败，请检查网络连接。' }
    } finally { Pop-Location }
}

function Test-Port([int]$Port) {
    $client = [System.Net.Sockets.TcpClient]::new()
    try {
        $async = $client.BeginConnect('127.0.0.1', $Port, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne(250)) { return $false }
        $client.EndConnect($async)
        return $true
    } catch { return $false }
    finally { $client.Dispose() }
}

function Find-FreePort([int]$Preferred) {
    foreach ($port in $Preferred..($Preferred + 100)) {
        if (-not (Test-Port $port)) { return $port }
    }
    throw "从端口 $Preferred 开始未找到可用端口。"
}

function Start-ServiceProcess(
    [string]$Name,
    [string]$File,
    [string]$Arguments,
    [string]$WorkingDirectory,
    [hashtable]$Environment = @{}
) {
    $info = [System.Diagnostics.ProcessStartInfo]::new()
    $info.FileName = $File
    $info.Arguments = $Arguments
    $info.WorkingDirectory = $WorkingDirectory
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    foreach ($entry in $Environment.GetEnumerator()) {
        $info.EnvironmentVariables[$entry.Key] = [string]$entry.Value
    }

    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $info
    if (-not $process.Start()) { throw "无法启动 $Name。" }
    $script:Processes.Add([pscustomobject]@{
        Name = $Name
        Process = $process
        Pid = $process.Id
        StartedAt = [DateTime]::UtcNow.ToString('o')
    })
    Write-Ok "$Name 已启动，PID $($process.Id)"
}

function Wait-Url([string]$Url, [int]$Seconds = 30) {
    $deadline = [DateTime]::UtcNow.AddSeconds($Seconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) { return $true }
        } catch {}
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Open-SystemPage([string]$Url) {
    Set-Content -LiteralPath $UrlFile -Value $Url -Encoding ASCII
    try {
        $explorer = Join-Path $env:WINDIR 'explorer.exe'
        [System.Diagnostics.Process]::Start($explorer, $Url) | Out-Null
        Write-Ok "已请求浏览器打开：$Url"
        return $true
    } catch {
        try {
            $handler = Join-Path $env:WINDIR 'System32\rundll32.exe'
            [System.Diagnostics.Process]::Start($handler, "url.dll,FileProtocolHandler $Url") | Out-Null
            Write-Ok "已请求浏览器打开：$Url"
            return $true
        } catch {
            Write-Host "[警告] 无法自动打开浏览器，请手动复制此地址：$Url" -ForegroundColor Yellow
            return $false
        }
    }
}

function Save-Pids {
    $items = @($script:Processes | ForEach-Object {
        [pscustomobject]@{ name = $_.Name; pid = $_.Pid; started_at = $_.StartedAt }
    })
    $payload = [pscustomobject]@{
        frontend_url = $script:FrontendUrl
        backend_url = $script:BackendUrl
        processes = $items
    }
    ConvertTo-Json -InputObject $payload -Depth 4 | Set-Content -LiteralPath $PidFile -Encoding UTF8
    $script:OwnsPidFile = $true
}

function Stop-StartedProcesses {
    foreach ($item in $script:Processes) {
        try {
            if (-not $item.Process.HasExited) {
                & taskkill.exe /PID $item.Pid /T /F 2>$null | Out-Null
            }
        } catch {}
    }
    if ($script:OwnsPidFile) {
        Remove-Item -LiteralPath $PidFile -Force -ErrorAction SilentlyContinue
    }
    Remove-Item -LiteralPath $StopFile -Force -ErrorAction SilentlyContinue
}

try {
    Write-Host 'LabTime 实验室打卡系统' -ForegroundColor White
    Write-Host "项目目录：$Root" -ForegroundColor DarkGray
    New-Item -ItemType Directory -Path $RuntimeDir -Force | Out-Null
    Remove-Item -LiteralPath $StopFile -Force -ErrorAction SilentlyContinue
    try {
        Start-Transcript -Path $LogFile -Append | Out-Null
        $TranscriptStarted = $true
        Write-Host "启动日志：$LogFile" -ForegroundColor DarkGray
    } catch {}

    Write-Step '检查运行环境'
    $python = Find-Python
    Write-Ok "Python：$python"

    $nodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue
    if (-not $nodeCommand) { throw '未找到 Node.js。请安装 Node.js 20 或更高版本。' }
    $node = $nodeCommand.Source
    $nodeVersionOutput = @(& $node -p "process.versions.node.split('.')[0]")
    $nodeMajor = [int]$nodeVersionOutput[-1]
    if ($nodeMajor -lt 20) { throw "Node.js 版本过低：需要 20+，当前为 $nodeMajor。" }
    Write-Ok "Node.js：$(& $node --version)"

    if (-not (Test-BackendDependencies $python)) {
        if ($SkipInstall -or $CheckOnly) { throw '后端依赖尚未安装。请去掉 -SkipInstall 后运行。' }
        $python = Install-Backend $python
    }
    Write-Ok '后端依赖完整'

    $viteEntry = Join-Path $FrontendDir 'node_modules\vite\bin\vite.js'
    if (-not (Test-Path -LiteralPath $viteEntry)) {
        if ($SkipInstall -or $CheckOnly) { throw '前端依赖尚未安装。请去掉 -SkipInstall 后运行。' }
        Install-Frontend
    }
    Write-Ok '前端依赖完整'

    if ($CheckOnly) {
        Write-Ok '一键启动环境检查通过'
        exit 0
    }

    if (-not (Test-Path -LiteralPath (Join-Path $Root 'models\face_detection_yunet_2023mar.onnx')) -or
        -not (Test-Path -LiteralPath (Join-Path $Root 'models\face_recognition_sface_2021dec.onnx'))) {
        Write-Host '[提示] 尚未放置 YuNet/SFace 模型。系统可以启动，但真实人脸录入和识别会返回 503。' -ForegroundColor Yellow
        Write-Host '       请阅读 models\README.md。' -ForegroundColor Yellow
    }

    Write-Step '启动服务'
    $actualBackendPort = Find-FreePort $BackendPort
    $actualFrontendPort = Find-FreePort $FrontendPort
    if ($actualBackendPort -ne $BackendPort) { Write-Host "[提示] 端口 $BackendPort 已占用，后端改用 $actualBackendPort。" -ForegroundColor Yellow }
    if ($actualFrontendPort -ne $FrontendPort) { Write-Host "[提示] 端口 $FrontendPort 已占用，前端改用 $actualFrontendPort。" -ForegroundColor Yellow }
    $BackendUrl = "http://127.0.0.1:$actualBackendPort"
    $FrontendUrl = "http://127.0.0.1:$actualFrontendPort"
    $origins = "http://localhost:$actualFrontendPort,http://127.0.0.1:$actualFrontendPort"
    Start-ServiceProcess 'FastAPI 后端' $python "-m uvicorn app.main:app --host 127.0.0.1 --port $actualBackendPort" $BackendDir @{ ALLOWED_ORIGINS = $origins }
    Start-ServiceProcess 'Vue 前端' $node "node_modules/vite/bin/vite.js --host 127.0.0.1 --port $actualFrontendPort" $FrontendDir @{ LABTIME_API_TARGET = $BackendUrl }
    Save-Pids

    Write-Step '等待页面就绪'
    $backendReady = Wait-Url "$BackendUrl/api/health" 35
    $frontendReady = Wait-Url "$FrontendUrl/login" 35
    if ($frontendReady) {
        Write-Ok "系统已启动：$FrontendUrl"
        if (-not $backendReady) { Write-Host '[警告] 后端健康检查尚未通过，请查看上方日志。' -ForegroundColor Yellow }
        Write-Host '初始开发管理员：admin / ChangeMe123!' -ForegroundColor Yellow
        if (-not $NoBrowser) {
            Open-SystemPage $FrontendUrl | Out-Null
        } else {
            Set-Content -LiteralPath $UrlFile -Value $FrontendUrl -Encoding ASCII
        }
    } else {
        Write-Host '[警告] 页面在等待时间内未就绪，请查看上方服务日志。' -ForegroundColor Yellow
    }

    Write-Host "`n保持此窗口开启。按 Ctrl+C 可停止本次启动的服务。" -ForegroundColor Cyan
    while ($true) {
        Start-Sleep -Seconds 2
        if (Test-Path -LiteralPath $StopFile) {
            Write-Host '收到一键停止请求，正在退出。' -ForegroundColor Cyan
            break
        }
        $exited = @($Processes | Where-Object { $_.Process.HasExited })
        if ($exited.Count -gt 0) {
            foreach ($item in $exited) { Write-Host "$($item.Name) 已退出，退出码 $($item.Process.ExitCode)。" -ForegroundColor Red }
            throw '服务意外退出。'
        }
    }
} catch {
    Write-Host "`n[错误] $($_.Exception.Message)" -ForegroundColor Red
    Stop-StartedProcesses
    exit 1
} finally {
    Stop-StartedProcesses
    if ($TranscriptStarted) {
        try { Stop-Transcript | Out-Null } catch {}
    }
}
