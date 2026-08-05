@echo off & cd /d "%~dp0" & powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop-local.ps1" & echo. & echo Press any key to close this window... & pause >nul
