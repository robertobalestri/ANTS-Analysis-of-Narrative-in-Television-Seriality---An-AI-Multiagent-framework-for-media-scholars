@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo   ANTS: Analysis of Narrative in Television Seriality
echo ===================================================
echo.
echo Starting ANTS application...

where python >nul 2>nul
if !errorlevel! equ 0 (
    python "%~dp0setup.py"
    goto end
)

where py >nul 2>nul
if !errorlevel! equ 0 (
    py "%~dp0setup.py"
    goto end
)

echo.
echo [-] Error: Python was not found in your PATH.
echo Please install Python 3.10+ and make sure to check "Add Python to PATH" during installation.
echo.
pause

:end
endlocal
