#requires -Version 7.4
param([Parameter(Mandatory)][string]$Path, [string]$ReadOnlySid, [switch]$Recurse)
$ErrorActionPreference = 'Stop'
$Identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
$Acl = [System.Security.AccessControl.DirectorySecurity]::new()
$Acl.SetOwner($Identity)
$Acl.SetAccessRuleProtection($true, $false)
foreach ($Sid in @($Identity, [System.Security.Principal.SecurityIdentifier]::new('S-1-5-18'))) {
    $Rule = [System.Security.AccessControl.FileSystemAccessRule]::new($Sid, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
    $Acl.AddAccessRule($Rule)
}
if ($ReadOnlySid) {
    $Sid = [System.Security.Principal.SecurityIdentifier]::new($ReadOnlySid)
    $Acl.AddAccessRule([System.Security.AccessControl.FileSystemAccessRule]::new($Sid, 'ReadAndExecute', 'ContainerInherit,ObjectInherit', 'None', 'Allow'))
}
Set-Acl -LiteralPath $Path -AclObject $Acl
if ($Recurse) {
    Get-ChildItem -LiteralPath $Path -Recurse -Force | ForEach-Object {
        if ($_.LinkType) { throw 'Unexpected link in isolated decoder profile.' }
        # Restore inheritance from the protected, read-only-to-AppContainer root.
        & icacls $_.FullName /reset /Q | Out-Null
        if ($LASTEXITCODE) { throw 'Cannot secure decoder profile child.' }
    }
}
$Actual = Get-Acl -LiteralPath $Path
if (-not $Actual.AreAccessRulesProtected) { throw 'Private directory ACL is not protected.' }
foreach ($Rule in $Actual.Access) {
    $Sid = $Rule.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value
    if ($Sid -notin @($Identity.Value,'S-1-5-18',$ReadOnlySid) -or $Rule.AccessControlType -ne 'Allow') { throw 'Unexpected private-directory access rule.' }
}
