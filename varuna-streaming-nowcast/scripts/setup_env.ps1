# One-shot environment setup for Windows / PowerShell.
# Run from anywhere:  .\scripts\setup_env.ps1
$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\.."

py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu
.\.venv\Scripts\python.exe -m pip install -e .

Write-Host ""
Write-Host "Setup complete. Activate the environment with:"
Write-Host "    .\.venv\Scripts\Activate.ps1"
