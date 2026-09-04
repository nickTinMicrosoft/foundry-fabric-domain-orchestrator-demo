$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    throw "Create .venv and install requirements.txt before starting the demo."
}

& ".\.venv\Scripts\python.exe" -m streamlit run app.py `
    --server.headless true `
    --browser.gatherUsageStats false
