<#
.SYNOPSIS
    Builds a proper Setup.exe installer for TXT News to Excel Sync using Inno Setup.
    Run build_exe.ps1 first to produce dist\WordToExcelHindiSync.exe.
#>

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

if (-not (Test-Path "dist\WordToExcelHindiSync.exe")) {
    throw "dist\WordToExcelHindiSync.exe not found. Run build_exe.ps1 first."
}

$isccCandidates = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
)
$iscc = $isccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
    $iscc = "ISCC.exe"  # fall back to PATH
}

Write-Host "Building installer with $iscc ..."
& $iscc "installer.iss"

if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup compilation failed with exit code $LASTEXITCODE"
}

Write-Host "Installer built: installer_output\TXT_News_Excel_Sync_Setup.exe"
