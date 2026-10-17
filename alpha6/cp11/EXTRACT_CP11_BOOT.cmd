@echo off
setlocal EnableExtensions DisableDelayedExpansion
if "%~1"=="" (
  echo Drag your verified original R36OS Alpha 5R3 .img onto this file.
  pause
  exit /b 2
)
if not exist "%~1" (
  echo ERROR: Image not found: "%~1"
  pause
  exit /b 2
)
rem All output paths are resolved in Python. The input image is opened rb only.
where py >nul 2>nul
if not errorlevel 1 (
  py -3 "%~dp0tools\cp11_extract_validate.py" "%~1" "%~dp0"
) else (
  where python >nul 2>nul
  if errorlevel 1 (
    echo ERROR: Python 3 not found. Use the Python setup from CP00-CP04.
    pause
    exit /b 2
  )
  python "%~dp0tools\cp11_extract_validate.py" "%~1" "%~dp0"
)
set "RC=%ERRORLEVEL%"
echo.
if "%RC%"=="0" (
  echo Done. Find the new CP11_RESULTS folder next to this launcher.
) else (
  echo CP11 did not validate the image. No source data was modified.
)
pause
exit /b %RC%