#requires -Version 7.4
# Portable parser/diagnostic and mocked-command tests; NO Windows ACL execution.
$ErrorActionPreference = 'Stop'
$ScnsRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
function Read-ScnsAst([string]$Name) {
    $Tokens = $null; $Errors = $null
    $Ast = [System.Management.Automation.Language.Parser]::ParseFile((Join-Path $PSScriptRoot $Name), [ref]$Tokens, [ref]$Errors)
    if ($Errors.Count) { throw "PowerShell parse errors in $Name" }
    return $Ast
}
$Protect = Read-ScnsAst 'protect.ps1'
$Scns = Read-ScnsAst 'scns.ps1'
$null = Read-ScnsAst 'acl.test.ps1'
$DecoderBody = $Scns.Find({ param($Node) $Node -is [System.Management.Automation.Language.IfStatementAst] -and $Node.Clauses[0].Item1.Extent.Text -eq '$Action -eq ''DecoderDiagnostic''' }, $true).Clauses[0].Item2
if (-not $DecoderBody -or $DecoderBody.Extent.StartOffset -gt $Scns.Find({ param($Node) $Node -is [System.Management.Automation.Language.ForEachStatementAst] }, $true).Extent.StartOffset) { throw 'Decoder diagnostic must precede dependency/tool checks.' }
if ($DecoderBody.Extent.Text -notmatch 'backend/.venv/Scripts/python.exe' -or $DecoderBody.Extent.Text -notmatch 'decoderdiagnostic --state') { throw 'Diagnostic must use installed interpreter and dedicated action.' }
$DecoderCommands = $DecoderBody.FindAll({ param($Node) $Node -is [System.Management.Automation.Language.CommandAst] }, $true)
if (@($DecoderCommands | Where-Object { $_.GetCommandName() -in @('uv','npm','node','icacls','protect','Setup','Start-Process') }).Count) { throw 'Diagnostic must not install/build/grant/reconfigure or need PG tools.' }
# Prevent the provider-wide/ownership/auditing path from returning.
$Calls = $Protect.FindAll({ param($Node) $Node -is [System.Management.Automation.Language.CommandAst] }, $true)
if (@($Calls | Where-Object { $_.GetCommandName() -in @('Set-Acl','Get-Acl') }).Count) { throw 'ACL provider calls are forbidden.' }
$Members = $Protect.FindAll({ param($Node) $Node -is [System.Management.Automation.Language.InvokeMemberExpressionAst] }, $true)
if (@($Members | Where-Object { $_.Member.Value -in @('SetOwner','SetGroup','GetAuditRules','SetAuditRule','AddAuditRule') }).Count) { throw 'Owner/group/audit mutation is forbidden.' }
$Sections = $Protect.FindAll({ param($Node) $Node -is [System.Management.Automation.Language.MemberExpressionAst] -and $Node.Expression -is [System.Management.Automation.Language.TypeExpressionAst] -and $Node.Expression.TypeName.FullName -eq 'System.Security.AccessControl.AccessControlSections' }, $true)
if (-not $Sections.Count -or @($Sections | Where-Object { $_.Member.Value -notin @('Access','Owner') }).Count) { throw 'Only DACL/owner reads are allowed.' }
$Writes = @($Members | Where-Object { $_.Member.Value -eq 'SetAccessControl' })
if ($Writes.Count -ne 1 -or $Writes[0].Expression.TypeName.FullName -ne 'System.IO.FileSystemAclExtensions') { throw 'Must persist directly through the DACL-only .NET path.' }
$Diagnostic = $Protect.Find({ param($Node) $Node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $Node.Name -eq 'Get-ScnsAclDiagnostic' }, $true)
Set-Item Function:Get-ScnsAclDiagnostic $Diagnostic.Body.GetScriptBlock()
$Private = 'password=synthetic-must-not-print C:\private\example'
$Cause = [System.ComponentModel.Win32Exception]::new(1314, $Private)
$Record = Get-ScnsAclDiagnostic -Exception ([System.Exception]::new($Private, $Cause)) -Stage 'persist-dacl'
if ($Record.windows_error -ne 1314 -or $Record.stage -ne 'persist-dacl' -or ($Record | ConvertTo-Json -Compress).Contains($Private)) { throw 'Sanitized native-code diagnostics failed.' }
$Record = Get-ScnsAclDiagnostic -Exception ([System.UnauthorizedAccessException]::new($Private)) -Stage 'read-owner'
if ($Record.windows_error -ne 5 -or $Record.hresult -ne '0x80070005') { throw 'HRESULT error-code diagnostics failed.' }
$SetupBody = $Scns.Find({ param($Node) $Node -is [System.Management.Automation.Language.IfStatementAst] -and $Node.Clauses[0].Item1.Extent.Text -eq '$Action -eq ''Setup''' }, $true).Clauses[0].Item2
if ($SetupBody.FindAll({ param($Node) $Node -is [System.Management.Automation.Language.ReturnStatementAst] -or $Node -is [System.Management.Automation.Language.ExitStatementAst] }, $true).Count) { throw 'Setup must continue to native security gates; no successful early exit.' }
$Setup = [scriptblock]::Create(($SetupBody.Statements | ForEach-Object { $_.Extent.Text }) -join [Environment]::NewLine)
function Assert-ScnsThrows([scriptblock]$Block, [string]$Message) {
    $Caught = $null
    try { & $Block } catch { $Caught = $_ }
    if (-not $Caught -or -not $Caught.Exception.Message.Contains($Message)) { throw 'Expected safe refusal was missing.' }
}
$Fixture = Join-Path ([System.IO.Path]::GetTempPath()) ('scns-script-contract-' + [guid]::NewGuid().ToString('N'))
$ScnsRoot = $Fixture
$script:UvCalls = @(); $script:NpmCalls = @(); $script:UvExit = 0
function uv { $script:UvCalls += ,@($args); $global:LASTEXITCODE = $script:UvExit }
function npm { $script:NpmCalls += ,@($args); $global:LASTEXITCODE = 0 }
try {
    foreach ($Name in @('backend/.venv/Scripts/python.exe','node_modules/vite/bin/vite.js','frontend/dist/index.html')) {
        $File = Join-Path $Fixture $Name
        $null = [System.IO.Directory]::CreateDirectory((Split-Path $File -Parent))
        [System.IO.File]::WriteAllText($File, 'Synthetic test fixture, never executed')
    }
    $Action = 'Setup'; $ReuseDependencies = $true
    & $Setup
    if ($script:UvCalls.Count -ne 1 -or ($script:UvCalls[0] -join ' ') -ne 'sync --project backend --frozen --check --python 3.12' -or $script:NpmCalls.Count) { throw 'Reuse must only check dependencies; no installation/build.' }
    $script:UvExit = 1
    Assert-ScnsThrows $Setup 'does not match the frozen lock'
    if ($script:NpmCalls.Count) { throw 'Lock mismatch must not reinstall.' }
    $script:UvExit = 0
    Remove-Item -LiteralPath (Join-Path $Fixture 'frontend/dist/index.html')
    Assert-ScnsThrows $Setup 'Existing dependency/build output missing'
    $script:UvCalls = @(); $script:NpmCalls = @(); $ReuseDependencies = $false
    & $Setup
    if ($script:UvCalls.Count -ne 2 -or ($script:UvCalls[0] -join ' ') -ne 'python install 3.12' -or ($script:UvCalls[1] -join ' ') -ne 'sync --project backend --frozen --python 3.12' -or $script:NpmCalls.Count -ne 2 -or ($script:NpmCalls[0] -join ' ') -ne 'ci --no-audit --no-fund' -or ($script:NpmCalls[1] -join ' ') -ne 'run build --workspace frontend') { throw 'Normal frozen Setup behavior changed.' }
} finally {
    # Only the uniquely created synthetic fixture. Never native State/data.
    Remove-Item -LiteralPath $Fixture -Recurse -Force
}
Write-Host 'Portable script contracts passed: syntax, DACL-only calls, sanitized errors, reuse/mismatch/missing outputs and normal setup. Not Windows ACL verification.'
