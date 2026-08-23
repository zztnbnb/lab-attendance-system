@echo off
setlocal
cd /d "D:\codexproject\实验室打卡系统"
title LabTime 实验室打卡系统
echo LabTime 正在启动，请保持此窗口开启。
echo 浏览器会在服务就绪后自动打开；停止服务请运行“一键停止.bat”。
echo.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "D:\codexproject\实验室打卡系统\scripts\start-local.ps1"
set "LABTIME_EXIT_CODE=%ERRORLEVEL%"
echo.
if not "%LABTIME_EXIT_CODE%"=="0" echo 启动失败，退出码：%LABTIME_EXIT_CODE%。请查看上方错误或 .runtime\launcher.log。
echo 按任意键关闭此窗口。
pause >nul
endlocal
exit /b %LABTIME_EXIT_CODE%
