# Non-interactive production start for Malstar_Toolkit (NSSM)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$backend = Join-Path $root "backend"
$python = Join-Path $backend ".venv\Scripts\python.exe"
$app = Join-Path $backend "app.py"
$envFile = Join-Path $root ".env"

if (Test-Path $envFile) {
    Get-Content $envFile | ForEach-Object {
        if ($_ -match "^\s*([^#=]+)=(.*)$") {
            [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
}

if (-not $env:FLASK_HOST) { $env:FLASK_HOST = "0.0.0.0" }
if (-not $env:PORT) { $env:PORT = "8080" }
if (-not $env:FLASK_DEBUG) { $env:FLASK_DEBUG = "false" }

Set-Location $backend
& $python $app
