@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0SETUP_STATA_RUNNER.ps1" %*
exit /b %errorlevel%
