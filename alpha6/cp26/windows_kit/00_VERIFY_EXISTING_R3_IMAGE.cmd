@echo off
cd /d "%~dp0"
echo R36OS Alpha6 CP26 - READ ONLY full image SHA256 (does NOT copy IMG)
set "R3IMG=F:\r36\R36OS-Alpha5R3-Standalone-Box64-20260925-075306.img"
if not "%~1"=="" set "R3IMG=%~1"
echo Checking: "%R3IMG%"
where py >nul 2>&1
if %errorlevel% equ 0 (py -3 tools\check_original_img.py "%R3IMG%") else (python tools\check_original_img.py "%R3IMG%")
echo.
pause