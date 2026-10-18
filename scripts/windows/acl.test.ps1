#requires -Version 7.4
param([Parameter(Mandatory)][string]$Root)
# Actual Windows regression, restricted to a newly created synthetic fixture.
$ErrorActionPreference = 'Stop'
if (-not $IsWindows) { throw 'Actual Windows is required.' }
$Current = [System.Security.Principal.WindowsIdentity]::GetCurrent()
if ([System.Security.Principal.WindowsPrincipal]::new($Current).IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Run the ACL regression as an ordinary non-elevated owner.' }
$Sid = $Current.User.Value
$Decoder = 'S-1-15-2-111-222-333-444-555-666-777'
$Fixture = Join-Path $Root ('synthetic ACL fixture ' + [guid]::NewGuid().ToString('N'))
$null = [System.IO.Directory]::CreateDirectory($Fixture)
$Item = [System.IO.DirectoryInfo]::new($Fixture)
$Sections = [System.Security.AccessControl.AccessControlSections]::Access -bor [System.Security.AccessControl.AccessControlSections]::Owner -bor [System.Security.AccessControl.AccessControlSections]::Group
$Before = [System.IO.FileSystemAclExtensions]::GetAccessControl($Item, $Sections)
$Owner = $Before.GetOwner([System.Security.Principal.SecurityIdentifier]).Value
$Group = $Before.GetGroup([System.Security.Principal.SecurityIdentifier]).Value
$File = Join-Path $Fixture 'existing synthetic receipt.txt'
[System.IO.File]::WriteAllText($File, 'Synthetic retained bytes only; no credentials')
$Hash = (Get-FileHash -LiteralPath $File -Algorithm SHA256).Hash
function Protect-ScnsFixture([bool]$WithDecoder) {
    $Arguments = @('-NoProfile','-File',(Join-Path $PSScriptRoot 'protect.ps1'),'-Path',$Fixture)
    if ($WithDecoder) { $Arguments += @('-ReadOnlySid',$Decoder,'-Recurse') }
    & pwsh @Arguments
    if ($LASTEXITCODE) { throw 'Non-elevated fixture protection failed.' }
}
function Assert-ScnsFixture([bool]$WithDecoder) {
    $After = [System.IO.FileSystemAclExtensions]::GetAccessControl($Item, $Sections)
    if (-not $After.AreAccessRulesProtected -or $After.GetOwner([System.Security.Principal.SecurityIdentifier]).Value -ne $Owner -or $After.GetGroup([System.Security.Principal.SecurityIdentifier]).Value -ne $Group) { throw 'Protected inheritance or retained ownership/group failed.' }
    $Expected = @($Sid,'S-1-5-18'); if ($WithDecoder) { $Expected += $Decoder }
    $Rules = @($After.GetAccessRules($true, $true, [System.Security.Principal.SecurityIdentifier]))
    if ($Rules.Count -ne $Expected.Count) { throw 'Unexpected root permission count.' }
    foreach ($Rule in $Rules) {
        if ($Rule.IdentityReference.Value -notin $Expected -or $Rule.AccessControlType -ne 'Allow') { throw 'Unexpected root access.' }
        $Rights = [System.Security.AccessControl.FileSystemRights]::FullControl
        if ($Rule.IdentityReference.Value -eq $Decoder) { $Rights = [System.Security.AccessControl.FileSystemRights]::ReadAndExecute -bor [System.Security.AccessControl.FileSystemRights]::Synchronize }
        if ([int]$Rule.FileSystemRights -ne [int]$Rights) { throw 'Root rights differ.' }
    }
    if ((Get-FileHash -LiteralPath $File -Algorithm SHA256).Hash -ne $Hash) { throw 'Existing fixture bytes changed.' }
}
# Previously failed on the already-protected second call (Setup main+exclusive).
Protect-ScnsFixture $false; Assert-ScnsFixture $false
Protect-ScnsFixture $false; Assert-ScnsFixture $false
$Child = Join-Path $Fixture 'nested profile'
$null = [System.IO.Directory]::CreateDirectory($Child)
$ChildFile = Join-Path $Child 'existing synthetic profile.dat'
[System.IO.File]::WriteAllText($ChildFile, 'Synthetic profile bytes')
$ChildItem = [System.IO.FileInfo]::new($ChildFile)
$ChildAcl = [System.IO.FileSystemAclExtensions]::GetAccessControl($ChildItem, [System.Security.AccessControl.AccessControlSections]::Access)
$ChildAcl.SetAccessRuleProtection($true, $false)
foreach ($PrivateSid in @($Sid, 'S-1-5-18')) {
    $ChildAcl.AddAccessRule([System.Security.AccessControl.FileSystemAccessRule]::new([System.Security.Principal.SecurityIdentifier]::new($PrivateSid), 'FullControl', 'Allow'))
}
[System.IO.FileSystemAclExtensions]::SetAccessControl($ChildItem, $ChildAcl)
Protect-ScnsFixture $true; Assert-ScnsFixture $true
Protect-ScnsFixture $true; Assert-ScnsFixture $true
$Inherited = [System.IO.FileSystemAclExtensions]::GetAccessControl($ChildItem, [System.Security.AccessControl.AccessControlSections]::Access)
$Rules = @($Inherited.GetAccessRules($true, $true, [System.Security.Principal.SecurityIdentifier]))
if ($Rules.Count -ne 3 -or @($Rules | Where-Object { -not $_.IsInherited -or $_.IdentityReference.Value -notin @($Sid,'S-1-5-18',$Decoder) }).Count) { throw 'Profile child DACL did not inherit narrowly.' }
if ([System.IO.File]::ReadAllText($ChildFile) -ne 'Synthetic profile bytes') { throw 'Profile contents changed.' }
Write-Host 'Actual non-elevated Windows ACL repeat/owner/SYSTEM/decoder RX/inheritance/content regression passed. No SACL accessed.'
