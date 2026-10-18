@echo off
cd /d "%~dp0"
echo R36OS Alpha6 CP26 - BOOT-only test installer
where py >nul 2>&1
if %errorlevel% equ 0 (py -3 tools\cp26_deploy.py install --package "%~dp0") else (python tools\cp26_deploy.py install --package "%~dp0")
echo.
pause