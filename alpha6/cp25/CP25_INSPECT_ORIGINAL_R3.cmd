@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
echo R36OS CP25 - READ-ONLY original R3 image inspector
echo Does NOT select/format/write any SD card or make boot files.
echo.
set "R3IMAGE=%~1"
if not defined R3IMAGE (
  set /p "R3IMAGE=Enter full path of your ORIGINAL R3 .img file: "
)
if not defined R3IMAGE (
  echo No image selected. Aborting.
  pause
  exit /b 2
)
if not exist "%R3IMAGE%" (
  echo Image file does not exist.
  pause
  exit /b 2
)
where py >nul 2>&1
if not errorlevel 1 (
  py -3 "%~dp0cp25_readonly_r3_inspect.py" "%R3IMAGE%"
) else (
  where python >nul 2>&1
  if errorlevel 1 (
    echo Python 3 not found. CP11 extractor used Python 3 as well.
    pause
    exit /b 3
  )
  python "%~dp0cp25_readonly_r3_inspect.py" "%R3IMAGE%"
)
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo Inspect CP25_RESULTS_* next to this BAT and upload the JSON report.
  echo WARNING: This has not established independent recovery.
) else (
  echo Read-only inspection failed. No source image bytes were changed.
)
pause
exit /b %RC%