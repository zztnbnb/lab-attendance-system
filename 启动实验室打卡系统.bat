@echo off
setlocal
title LabTime Launcher
echo Starting LabTime. Keep this window open.
echo The browser will open automatically when the services are ready.
echo.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -NoExit -EncodedCommand UwBlAHQALQBMAG8AYwBhAHQAaQBvAG4AIAAtAEwAaQB0AGUAcgBhAGwAUABhAHQAaAAgACcARAA6AFwAYwBvAGQAZQB4AHAAcgBvAGoAZQBjAHQAXACeW4yapFtTYmFT+3zfficAOwAgACYAIAAnAEQAOgBcAGMAbwBkAGUAeABwAHIAbwBqAGUAYwB0AFwAnluMmqRbU2JhU/t8335cAHMAYwByAGkAcAB0AHMAXABzAHQAYQByAHQALQBsAG8AYwBhAGwALgBwAHMAMQAnAA==
set "LABTIME_EXIT_CODE=%ERRORLEVEL%"
echo.
if not "%LABTIME_EXIT_CODE%"=="0" echo Startup failed. Exit code: %LABTIME_EXIT_CODE%. See .runtime\launcher.log.
echo Press any key to close this window.
pause >nul
endlocal
exit /b %LABTIME_EXIT_CODE%
