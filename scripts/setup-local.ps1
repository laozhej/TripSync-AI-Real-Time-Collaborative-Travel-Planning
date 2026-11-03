$ErrorActionPreference = 'Stop'

function Invoke-SetupStep {
    param([string]$Executable, [string[]]$Arguments)
    & $Executable @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Executable failed with exit code $LASTEXITCODE."
    }
}

$root = Split-Path -Parent $PSScriptRoot
$previousPythonPath = $env:PYTHONPATH
Push-Location $root
try {
    if (!(Test-Path -LiteralPath '.env' -PathType Leaf)) {
        Copy-Item -LiteralPath '.env.example' -Destination '.env'
        throw 'Created .env. Set DATABASE_URL for your local PostgreSQL database, then rerun this script.'
    }

    Invoke-SetupStep python @('-m', 'venv', '.venv')
    $python = Join-Path $root '.venv/Scripts/python.exe'
    Invoke-SetupStep $python @('-m', 'pip', 'install', '-r', 'backend/requirements.lock')
    Invoke-SetupStep npm.cmd @('--prefix', 'frontend', 'ci')
    $env:PYTHONPATH = Join-Path $root 'backend'
    Invoke-SetupStep $python @('-m', 'app.cli', 'init-local-key')
    Invoke-SetupStep $python @('-m', 'alembic', '-c', 'backend/alembic.ini', 'upgrade', 'head')
    Write-Host 'Install complete. See docs/ENVIRONMENT_SETUP.md to seed a new database and start the app.'
}
finally {
    $env:PYTHONPATH = $previousPythonPath
    Pop-Location
}
