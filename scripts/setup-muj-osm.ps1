# Existing local Docker Desktop Linux containers only. Additive draft import, never publish.
[CmdletBinding()]
param([string]$OsmPath)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
function Invoke-Compose {
    param([string[]]$ComposeArgs)
    & docker compose @ComposeArgs
    if ($LASTEXITCODE -ne 0) { throw 'MUJ setup stopped. Existing data and partial progress retained; inspect the error and rerun.' }
}
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    $sourceMount = @()
    $sourceArgs = @()
    if ($OsmPath) {
        $resolved = (Resolve-Path -LiteralPath $OsmPath).Path
        if ((Get-FileHash -LiteralPath $resolved -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'd4b902b01fe944acb3161026679dabbab4898d6952bee22d7019f15fd15748de') {
            throw 'This is not the pinned attached MUJ OSM export. Nothing changed. Convert and review changed sources separately.'
        }
        $sourceMount = @('--volume', "${resolved}:/input/muj.osm:ro")
        $sourceArgs = @('--source', '/input/muj.osm')
    }
    Invoke-Compose -ComposeArgs @('build', 'api', 'frontend')
    Invoke-Compose -ComposeArgs @('stop', 'api', 'frontend', 'import-worker')
    Invoke-Compose -ComposeArgs @('up', '-d', '--wait', 'db')
    Invoke-Compose -ComposeArgs @('run', '--rm', '--no-deps', 'api', 'alembic', 'upgrade', 'head')
    Invoke-Compose -ComposeArgs @('up', '-d', '--wait', '--no-build', 'api', 'frontend', 'import-worker')
    # Keep a TTY for getpass, no credentials in argv/env/files/logs. Read-only original mount.
    Invoke-Compose -ComposeArgs (@('run', '--rm', '--no-deps') + $sourceMount + @('api', 'python', '-m', 'app.cli.muj') + $sourceArgs)
} finally { Pop-Location }
