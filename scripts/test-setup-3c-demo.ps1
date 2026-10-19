# Exercise the real PowerShell entrypoint with a mocked Docker process; never touches data.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$global:ScnsDemoTestCalls = [System.Collections.Generic.List[string]]::new()
$global:ScnsDemoTestFailMigration = $false
function global:docker {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]] $DockerArgs)
    $global:ScnsDemoTestCalls.Add(($DockerArgs -join '|'))
    $global:LASTEXITCODE = 0
    if ($global:ScnsDemoTestFailMigration -and ($DockerArgs -join '|') -match 'alembic\|upgrade\|head') {
        $global:LASTEXITCODE = 1
    }
}
try {
    $before = (Get-Location).Path
    & (Join-Path $PSScriptRoot 'setup-3c-demo.ps1')
    if ($global:ScnsDemoTestCalls.Count -ne 6 -or $global:ScnsDemoTestCalls[0] -ne 'compose|build|api|frontend' -or
        $global:ScnsDemoTestCalls[5] -ne 'compose|run|--rm|--no-deps|api|python|-m|app.cli.indoor_demo') {
        throw 'Compose argument binding or complete interactive workflow failed.'
    }
    if ((Get-Location).Path -ne $before) { throw 'Working directory not restored.' }
    $global:ScnsDemoTestCalls.Clear()
    $global:ScnsDemoTestFailMigration = $true
    $failed = $false
    try { & (Join-Path $PSScriptRoot 'setup-3c-demo.ps1') } catch { $failed = $true }
    if (-not $failed -or $global:ScnsDemoTestCalls.Count -ne 4 -or (Get-Location).Path -ne $before) {
        throw 'Migration failure must stop before app startup/helper and restore working directory.'
    }
    Write-Output 'PASS: PowerShell syntax/argument binding/interactive command; failed migration halts safely; working directory restored.'
} finally {
    Remove-Item Function:\docker
    Remove-Variable ScnsDemoTestCalls, ScnsDemoTestFailMigration -Scope Global
}
