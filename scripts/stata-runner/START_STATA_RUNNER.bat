@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0START_STATA_RUNNER.ps1"
exit /b %errorlevel%
