#requires -Version 7.4
[CmdletBinding()]
param(
    [Parameter(Position=0,Mandatory)][ValidateSet('Preflight','Setup','Backup','Restore','Start','Stop','Verify','Test')][string]$Action,
    [string]$State = (Join-Path $env:LOCALAPPDATA 'SCNS\native'),
    [string]$Bundle,
    [string]$PgBin,
    [switch]$NewTarget
)
$ErrorActionPreference = 'Stop'
if (-not $IsWindows -or -not [Environment]::Is64BitProcess) { throw 'Use native 64-bit Windows 11 PowerShell 7.4+. No WSL.' }
$ScnsRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location -LiteralPath $ScnsRoot
foreach ($Tool in @('uv','node','npm')) {
    if (-not (Get-Command $Tool -ErrorAction SilentlyContinue)) { throw "Missing $Tool. Read docs/operations/native-windows.md installation steps." }
}
if ($Action -eq 'Setup') {
    & uv python install 3.12
    if ($LASTEXITCODE) { throw 'Managed Python installation failed; no data changed.' }
    & uv sync --project backend --frozen --python 3.12
    if ($LASTEXITCODE) { throw 'Frozen Python installation failed.' }
    & npm ci --no-audit --no-fund
    if ($LASTEXITCODE) { throw 'Frozen npm installation failed.' }
    & npm run build --workspace frontend
    if ($LASTEXITCODE) { throw 'Frontend build failed.' }
}
$ScnsArgs = @('--directory','backend','run','--frozen','--no-sync','python','../scripts/windows/native.py',$Action.ToLowerInvariant(),'--state',$State)
if ($Bundle) { $ScnsArgs += @('--bundle',$Bundle) }
if ($PgBin) { $ScnsArgs += @('--pg-bin',$PgBin) }
if ($NewTarget) { $ScnsArgs += '--new-target' }
& uv @ScnsArgs
if ($LASTEXITCODE) { throw "Native $Action stopped (exit $LASTEXITCODE). Preserve both copies; see recovery instructions." }
