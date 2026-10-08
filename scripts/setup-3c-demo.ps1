# Local Docker Desktop Linux containers only. Does not seed/reset or publish.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Invoke-Compose {
    param([string[]] $ComposeArgs)
    & docker compose @ComposeArgs
    if ($LASTEXITCODE -ne 0) {
        throw 'Compose step failed. Existing data and partial demo progress retained; fix the reported failure and rerun.'
    }
}

Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    # Build before stopping services; .env and existing named volumes stay intact.
    Invoke-Compose @('build', 'api')
    Invoke-Compose @('stop', 'api', 'import-worker')
    Invoke-Compose @('up', '-d', '--wait', 'db')
    Invoke-Compose @('run', '--rm', '--no-deps', 'api', 'alembic', 'upgrade', 'head')
    Invoke-Compose @('up', '-d', '--wait', '--no-build', 'api', 'frontend', 'import-worker')
    # Default Compose run TTY is essential for hidden getpass prompts. No passwords in argv/env/files.
    Invoke-Compose @('run', '--rm', '--no-deps', 'api', 'python', '-m', 'app.cli.indoor_demo')
} finally {
    Pop-Location
}
