param([switch]$Clean)
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Python = Join-Path $Root '.venv\Scripts\python.exe'
$Out = Join-Path $Root 'packaging\backend'
if (-not (Test-Path $Python)) { throw 'Python venv not found. Run the local launcher first.' }
if ($Clean -and (Test-Path $Out)) { Remove-Item -LiteralPath $Out -Recurse -Force }
New-Item -ItemType Directory -Path $Out -Force | Out-Null
Push-Location $Root
try {
  & $Python -m pip install pyinstaller
  if ($LASTEXITCODE -ne 0) { throw 'PyInstaller installation failed.' }
  & $Python -m PyInstaller --noconfirm --clean --onefile --name labtime-api --distpath $Out --workpath (Join-Path $Root 'packaging\build') --specpath (Join-Path $Root 'packaging') --paths (Join-Path $Root 'backend') --collect-all fastapi --collect-all uvicorn --collect-all sqlalchemy --collect-all aiosqlite --collect-all pydantic --collect-all pydantic_settings --collect-all cv2 --collect-all jwt --collect-all pwdlib --collect-all cryptography --collect-all multipart --add-data "$Root\backend\app;app" (Join-Path $Root 'backend\packaging_entry.py')
  if ($LASTEXITCODE -ne 0) { throw 'Backend packaging failed.' }
} finally { Pop-Location }
