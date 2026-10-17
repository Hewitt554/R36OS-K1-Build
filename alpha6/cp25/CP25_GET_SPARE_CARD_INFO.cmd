@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
echo R36OS CP25 - READ-ONLY card identification
 echo No formatting, flashing, partition changes, boot.ini edits or saveenv.
echo.
where powershell >nul 2>&1
if errorlevel 1 (
  echo Windows PowerShell not found. No action taken.
  pause
  exit /b 2
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0cp25_list_disks_readonly.ps1"
set "RC=%ERRORLEVEL%"
if "%RC%"=="0" (
  echo The report is in CP25_CARD_RESULTS in this folder.
  echo The card inventory is informational ONLY. It does not certify safe flashing.
) else (
  echo Inventory failed, no devices changed.
)
pause
exit /b %RC%