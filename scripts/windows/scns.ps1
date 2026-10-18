#requires -Version 7.4
[CmdletBinding()]
param(
    [Parameter(Position=0,Mandatory)][ValidateSet('Preflight','Setup','Inventory','Backup','Restore','Start','Stop','Verify','Test')][string]$Action,
    [string]$State = (Join-Path $env:LOCALAPPDATA 'SCNS\native'),
    [string]$Bundle,
    [string]$PgBin,
    [switch]$NewTarget,
    [switch]$ReuseDependencies
)
$ErrorActionPreference = 'Stop'
if ($ReuseDependencies -and $Action -ne 'Setup') { throw '-ReuseDependencies is valid only with Setup; security checks are always required.' }
if (-not $IsWindows -or -not [Environment]::Is64BitProcess) { throw 'Use native 64-bit Windows 11 PowerShell 7.4+. No WSL.' }
if ([Environment]::OSVersion.Version.Build -lt 22000) { throw 'Native support requires Windows 11 x64. Other Windows editions are not validated.' }
$ScnsRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location -LiteralPath $ScnsRoot
foreach ($Tool in @('uv','node','npm')) {
    if (-not (Get-Command $Tool -ErrorAction SilentlyContinue)) { throw "Missing $Tool. Read docs/operations/native-windows.md installation steps." }
}
$ScnsNodeVersion = [version]((& node --version).Trim().TrimStart('v'))
if ($LASTEXITCODE -or $ScnsNodeVersion.Major -notin @(22,24) -or ($ScnsNodeVersion.Major -eq 22 -and $ScnsNodeVersion.Minor -lt 12)) {
    throw 'Use Node22.12+ or24 LTS. Run: winget upgrade --exact --id OpenJS.NodeJS.LTS --source winget'
}
if ((& node -p process.arch).Trim() -ne 'x64' -or $LASTEXITCODE) { throw 'Use native Node x64.' }
$ScnsUvText = & uv --version
$ScnsUvMatch = [regex]::Match($ScnsUvText, '^uv (\d+\.\d+\.\d+)')
if ($LASTEXITCODE -or -not $ScnsUvMatch.Success -or [version]$ScnsUvMatch.Groups[1].Value -lt [version]'0.12.19') {
    throw 'Use uv0.12.19+. Run: winget upgrade --exact --id astral-sh.uv --source winget'
}
if ($Action -eq 'Setup') {
    if ($ReuseDependencies) {
        foreach ($ScnsRequired in @('backend/.venv/Scripts/python.exe','node_modules/vite/bin/vite.js','frontend/dist/index.html')) {
            if (-not (Test-Path -LiteralPath (Join-Path $ScnsRoot $ScnsRequired) -PathType Leaf)) { throw 'Existing dependency/build output missing. Stop; use normal Setup only if installation is actually needed.' }
        }
        & uv sync --project backend --frozen --check --python 3.12
        if ($LASTEXITCODE) { throw 'Existing Python environment does not match the frozen lock. Nothing installed; inspect before using normal Setup.' }
        Write-Host 'Reusing installed dependencies and compiled frontend; directory protection and real decoder gates will still run.'
    } else {
        & uv python install 3.12
        if ($LASTEXITCODE) { throw 'Managed Python installation failed; no data changed.' }
        & uv sync --project backend --frozen --python 3.12
        if ($LASTEXITCODE) { throw 'Frozen Python installation failed.' }
        & npm ci --no-audit --no-fund
        if ($LASTEXITCODE) { throw 'Frozen npm installation failed.' }
        & npm run build --workspace frontend
        if ($LASTEXITCODE) { throw 'Frontend build failed.' }
    }
}
$ScnsArgs = @('--directory','backend','run','--frozen','--no-sync','python','../scripts/windows/native.py',$Action.ToLowerInvariant(),'--state',$State)
if ($Bundle) { $ScnsArgs += @('--bundle',$Bundle) }
if ($PgBin) { $ScnsArgs += @('--pg-bin',$PgBin) }
if ($NewTarget) { $ScnsArgs += '--new-target' }
& uv @ScnsArgs
if ($LASTEXITCODE) { throw "Native $Action stopped (exit $LASTEXITCODE). Preserve both copies; see recovery instructions." }
