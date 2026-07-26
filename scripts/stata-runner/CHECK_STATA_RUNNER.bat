@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0CHECK_STATA_RUNNER.ps1"
exit /b %errorlevel%
