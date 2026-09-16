@echo off
setlocal
title Forge Studio - Video Editor ^& Content Hashing System

cd /d "%~dp0"

echo ================================================================
echo   FORGE STUDIO - Video Editor ^& Content Hashing Engine
echo ================================================================
echo.

rem ------------------------------------------------------------------
rem  1. Find a Python that actually has the required packages.
rem     Bare "python" is unreliable: it may resolve to a fresh install
rem     with nothing in it, which used to make the hashing engine load
rem     as "unavailable" and silently skip hashing.
rem ------------------------------------------------------------------
set "PROBE=import fastapi, uvicorn, tqdm, multipart"
set "PYEXE="

if not defined PYEXE (py -3.13 -c "%PROBE%" >nul 2>&1 && set "PYEXE=py -3.13")
if not defined PYEXE (py -3.12 -c "%PROBE%" >nul 2>&1 && set "PYEXE=py -3.12")
if not defined PYEXE (py -3.11 -c "%PROBE%" >nul 2>&1 && set "PYEXE=py -3.11")
if not defined PYEXE (py -3.10 -c "%PROBE%" >nul 2>&1 && set "PYEXE=py -3.10")
if not defined PYEXE (python -c "%PROBE%" >nul 2>&1 && set "PYEXE=python")
if not defined PYEXE (python3 -c "%PROBE%" >nul 2>&1 && set "PYEXE=python3")

if not defined PYEXE (
  echo [!] No Python with the required packages was found.
  echo     Installing them now - this needs an internet connection...
  echo.
  py -3 -m pip install -r requirements.txt
  if errorlevel 1 (
    echo.
    echo [ERR] Automatic install failed.
    echo       Install Python 3.11 or newer, then run this once:
    echo           pip install -r requirements.txt
    echo.
    pause
    exit /b 1
  )
  set "PYEXE=py -3"
)

echo [OK] Interpreter: %PYEXE%

rem ------------------------------------------------------------------
rem  2. FFmpeg is required for every render and every hash.
rem ------------------------------------------------------------------
where ffmpeg >nul 2>&1
if errorlevel 1 (
  echo [!] FFmpeg was not found on your PATH.
  echo     Rendering and hashing will fail until you install it:
  echo         winget install Gyan.FFmpeg
  echo.
) else (
  echo [OK] FFmpeg found
)

rem ------------------------------------------------------------------
rem  3. Launch the server in its own window so its logs stay visible,
rem     then open the studio in the browser.
rem ------------------------------------------------------------------
echo.
echo [..] Starting server, browser opening at http://localhost:8000
echo.

start "Forge Studio Server" cmd /k "%PYEXE% -m app.main"

timeout /t 4 /nobreak >nul
start "" http://localhost:8000

echo Server is running in the "Forge Studio Server" window.
echo Close that window to stop the studio.
echo.
pause
