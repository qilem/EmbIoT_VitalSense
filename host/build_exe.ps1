# Build Vita.exe using PyInstaller
# Run from the host/ directory: .\build_exe.ps1

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host "Installing dependencies..." -ForegroundColor Cyan
pip install -r requirements.txt

Write-Host "Building Vita.exe..." -ForegroundColor Cyan
pyinstaller `
    --onefile `
    --noconsole `
    --name "Vita" `
    --icon "assets\tray_icon.ico" `
    --add-data "assets;assets" `
    --add-data "dialogue;dialogue" `
    --hidden-import "PySide6.QtSvg" `
    --hidden-import "PySide6.QtMultimedia" `
    main.py

if ($LASTEXITCODE -eq 0) {
    Write-Host "Build complete: dist\Vita.exe" -ForegroundColor Green
} else {
    Write-Host "Build failed." -ForegroundColor Red
    exit 1
}
