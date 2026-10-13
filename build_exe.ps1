<#
.SYNOPSIS
    Builds TaazaNewsExcelSync.exe using PyInstaller.
#>

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "Installing/upgrading dependencies..."
python -m pip install -r requirements.txt

Write-Host "Regenerating application icon..."
python assets\make_icon.py

Write-Host "Cleaning previous build artifacts..."
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue build, dist, TaazaNewsExcelSync.spec

Write-Host "Building TaazaNewsExcelSync.exe..."
python -m PyInstaller `
    --name "TaazaNewsExcelSync" `
    --windowed `
    --onefile `
    --noupx `
    --icon "assets\app_icon.ico" `
    --collect-all customtkinter `
    --exclude-module PIL.AvifImagePlugin `
    --exclude-module PIL._avif `
    main.py

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed with exit code $LASTEXITCODE"
}

Write-Host "Build complete: dist\TaazaNewsExcelSync.exe"
