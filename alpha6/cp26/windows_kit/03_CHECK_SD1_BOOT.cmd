@echo off
cd /d "%~dp0"
echo R36OS Alpha6 CP26 - inspect selected BOOT card (read only)
where py >nul 2>&1
if %errorlevel% equ 0 (py -3 tools\cp26_deploy.py status --package "%~dp0") else (python tools\cp26_deploy.py status --package "%~dp0")
echo.
pause