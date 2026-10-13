@echo off
REM ============================================================
REM  Windows 7 SP1 64-bit build for Taaza News Excel Sync
REM
REM  Produces:
REM    dist-win7\TaazaNewsExcelSync.exe
REM    TaazaNewsExcelSync_Portable.zip
REM    installer_output_win7\TaazaNewsExcelSync_Win7_Setup.exe
REM
REM  Requirements on THIS (build) machine:
REM    - Python 3.8.10 (64-bit) installed at F:\PyWin7Build\Python38
REM      (download: https://www.python.org/ftp/python/3.8.10/python-3.8.10-amd64.exe)
REM    - Inno Setup 6 (ISCC.exe) for the installer step
REM    - win7_prereqs\vc_redist.x64.exe present (official Microsoft
REM      download: https://aka.ms/vs/17/release/vc_redist.x64.exe)
REM
REM  See WINDOWS_7_SETUP.md for full details. Does NOT touch your normal
REM  Python 3.13 environment, requirements.txt, or dist\ folder.
REM ============================================================
setlocal enabledelayedexpansion
cd /d "%~dp0"

set PYWIN7=F:\PyWin7Build\Python38\python.exe
set ISCC="C:\Users\%USERNAME%\AppData\Local\Programs\Inno Setup 6\ISCC.exe"

if not exist "%PYWIN7%" (
    echo ERROR: Python 3.8.10 not found at %PYWIN7%
    echo Install it first - see WINDOWS_7_SETUP.md
    exit /b 1
)

echo === [1/6] Creating/refreshing venv-win7 ===
if not exist "venv-win7\Scripts\python.exe" (
    "%PYWIN7%" -m venv venv-win7
)

echo === [2/6] Installing pinned Windows 7 dependencies ===
venv-win7\Scripts\python.exe -m pip install --upgrade pip
venv-win7\Scripts\python.exe -m pip install -r requirements-win7.txt
if errorlevel 1 exit /b 1

echo === [3/6] Cleaning previous Windows 7 build artifacts ===
if exist build-win7 rmdir /s /q build-win7
if exist dist-win7 rmdir /s /q dist-win7

echo === [4/6] Running PyInstaller (Python 3.8 / PyInstaller 5.13.2) ===
venv-win7\Scripts\python.exe -m PyInstaller ^
    --name "TaazaNewsExcelSync" ^
    --windowed ^
    --onefile ^
    --noupx ^
    --icon "assets\app_icon.ico" ^
    --collect-all customtkinter ^
    --exclude-module PIL.AvifImagePlugin ^
    --exclude-module PIL._avif ^
    --distpath dist-win7 ^
    --workpath build-win7 ^
    --specpath . ^
    main.py
if errorlevel 1 exit /b 1
echo Build complete: dist-win7\TaazaNewsExcelSync.exe

echo === [5/6] Building portable ZIP ===
if exist portable_staging rmdir /s /q portable_staging
mkdir portable_staging
copy /y dist-win7\TaazaNewsExcelSync.exe portable_staging\ >nul
copy /y README_PORTABLE.txt portable_staging\ >nul 2>nul
if exist TaazaNewsExcelSync_Portable.zip del TaazaNewsExcelSync_Portable.zip
powershell -NoProfile -Command "Compress-Archive -Path 'portable_staging\*' -DestinationPath 'TaazaNewsExcelSync_Portable.zip' -CompressionLevel Optimal"
rmdir /s /q portable_staging
echo Portable package: TaazaNewsExcelSync_Portable.zip

echo === [6/6] Building installer (Inno Setup) ===
if not exist win7_prereqs\vc_redist.x64.exe (
    echo WARNING: win7_prereqs\vc_redist.x64.exe not found - download it from
    echo   https://aka.ms/vs/17/release/vc_redist.x64.exe
    echo and place it there before running the installer step.
    exit /b 1
)
%ISCC% installer_win7.iss
if errorlevel 1 exit /b 1

echo.
echo ============================================================
echo  BUILD COMPLETE
echo    EXE:       dist-win7\TaazaNewsExcelSync.exe
echo    Portable:  TaazaNewsExcelSync_Portable.zip
echo    Installer: installer_output_win7\TaazaNewsExcelSync_Win7_Setup.exe
echo ============================================================
endlocal
