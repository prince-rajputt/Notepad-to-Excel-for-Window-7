<#
.SYNOPSIS
    Builds WordToExcelHindiSync.exe using PyInstaller.
#>

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "Installing/upgrading dependencies..."
python -m pip install -r requirements.txt

Write-Host "Cleaning previous build artifacts..."
Remove-Item -Recurse -Force -ErrorAction SilentlyContinue build, dist, WordToExcelHindiSync.spec

Write-Host "Building WordToExcelHindiSync.exe..."
python -m PyInstaller `
    --name "WordToExcelHindiSync" `
    --windowed `
    --onefile `
    --noupx `
    --collect-all customtkinter `
    --exclude-module PIL.AvifImagePlugin `
    --exclude-module PIL._avif `
    main.py

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed with exit code $LASTEXITCODE"
}

Write-Host "Build complete: dist\WordToExcelHindiSync.exe"
