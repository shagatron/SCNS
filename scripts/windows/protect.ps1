#requires -Version 7.4
param([Parameter(Mandatory)][string]$Path, [string]$ReadOnlySid, [switch]$Recurse)
$ErrorActionPreference = 'Stop'

function Get-ScnsAclDiagnostic {
    param([System.Exception]$Exception, [string]$Stage)
    $Cause = $Exception.GetBaseException()
    $HResult = [long]$Cause.HResult -band 0xffffffffL
    $WindowsError = $null
    if ($Cause -is [System.ComponentModel.Win32Exception]) { $WindowsError = $Cause.NativeErrorCode }
    elseif ($Cause -is [System.Security.AccessControl.PrivilegeNotHeldException]) { $WindowsError = 1314 }
    elseif (($HResult -band 0xffff0000L) -eq 0x80070000L) { $WindowsError = $HResult -band 0xffffL }
    # Never serialize exception messages, paths, accounts or arbitrary tool output.
    return [ordered]@{ stage = $Stage; windows_error = $WindowsError; hresult = ('0x{0:X8}' -f $HResult) }
}

function Assert-ScnsDirectoryDacl {
    param([System.IO.FileSystemInfo]$Item, [hashtable]$Expected, [bool]$Protected)
    # Explicit Access section: never read the SACL, even during verification.
    $Actual = [System.IO.FileSystemAclExtensions]::GetAccessControl($Item, [System.Security.AccessControl.AccessControlSections]::Access)
    if ($Actual.AreAccessRulesProtected -ne $Protected) { throw 'Unexpected DACL inheritance state.' }
    $Found = @{}
    foreach ($Rule in $Actual.GetAccessRules($true, $true, [System.Security.Principal.SecurityIdentifier])) {
        $Sid = $Rule.IdentityReference.Value
        if (-not $Expected.ContainsKey($Sid) -or $Rule.AccessControlType -ne 'Allow' -or
            [int]$Rule.FileSystemRights -ne $Expected[$Sid] -or $Rule.PropagationFlags -ne 'None') {
            throw 'Unexpected DACL identity, rights or propagation.'
        }
        if ($Item -is [System.IO.DirectoryInfo] -and $Rule.InheritanceFlags -ne 'ContainerInherit,ObjectInherit') {
            throw 'Directory permissions must inherit to both files and directories.'
        }
        $Found[$Sid] = $true
    }
    if ($Found.Count -ne $Expected.Count) { throw 'Required DACL permission is missing.' }
}

$Stage = 'validate-directory'
try {
    $Directory = Get-Item -LiteralPath $Path -Force
    if ($Directory -isnot [System.IO.DirectoryInfo] -or ($Directory.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) {
        throw 'Expected a normal existing directory.'
    }
    $Identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
    $Expected = @{ $Identity.Value = [int][System.Security.AccessControl.FileSystemRights]::FullControl; 'S-1-5-18' = [int][System.Security.AccessControl.FileSystemRights]::FullControl }
    if ($ReadOnlySid) {
        if ($ReadOnlySid -notmatch '^S-1-15-2-\d+(?:-\d+)+$') { throw 'Expected an AppContainer SID only.' }
        $DecoderSid = [System.Security.Principal.SecurityIdentifier]::new($ReadOnlySid)
        $Expected[$DecoderSid.Value] = [int]([System.Security.AccessControl.FileSystemRights]::ReadAndExecute -bor [System.Security.AccessControl.FileSystemRights]::Synchronize)
    }
    $Stage = 'read-owner'
    $Before = [System.IO.FileSystemAclExtensions]::GetAccessControl($Directory, [System.Security.AccessControl.AccessControlSections]::Owner)
    $Owner = $Before.GetOwner([System.Security.Principal.SecurityIdentifier]).Value
    if ($Owner -notin @($Identity.Value, 'S-1-5-18')) { throw 'Directory ownership differs; no ownership changes attempted.' }
    $Children = @()
    if ($Recurse) {
        $Stage = 'enumerate-profile'
        $Children = @(Get-ChildItem -LiteralPath $Path -Recurse -Force)
        if (@($Children | Where-Object { $_.Attributes -band [System.IO.FileAttributes]::ReparsePoint }).Count) { throw 'Unexpected link in isolated decoder profile.' }
    }
    $Stage = 'build-dacl'
    $Acl = [System.Security.AccessControl.DirectorySecurity]::new()
    # Modify Access only. No SetOwner, group or audit setters. .NET persists only
    # changed sections; PowerShell Set-Acl instead first attempts ALL sections.
    $Acl.SetAccessRuleProtection($true, $false)
    foreach ($Sid in $Expected.Keys) {
        $Rule = [System.Security.AccessControl.FileSystemAccessRule]::new([System.Security.Principal.SecurityIdentifier]::new($Sid), [System.Security.AccessControl.FileSystemRights]$Expected[$Sid], 'ContainerInherit,ObjectInherit', 'None', 'Allow')
        $Acl.AddAccessRule($Rule)
    }
    $Stage = 'persist-dacl'
    [System.IO.FileSystemAclExtensions]::SetAccessControl($Directory, $Acl)
    foreach ($Child in $Children) {
        $Stage = 'reset-child-dacl'
        # icacls /reset changes discretionary inheritance only, not owner/SACL.
        & icacls $Child.FullName /reset /Q 2>&1 | Out-Null
        if ($LASTEXITCODE) { throw 'DACL inheritance reset failed; raw tool output withheld.' }
        $Stage = 'verify-child-dacl'
        Assert-ScnsDirectoryDacl -Item $Child -Expected $Expected -Protected $false
    }
    $Stage = 'verify-root-dacl'
    Assert-ScnsDirectoryDacl -Item $Directory -Expected $Expected -Protected $true
    $Stage = 'verify-owner'
    $After = [System.IO.FileSystemAclExtensions]::GetAccessControl($Directory, [System.Security.AccessControl.AccessControlSections]::Owner)
    if ($After.GetOwner([System.Security.Principal.SecurityIdentifier]).Value -ne $Owner) { throw 'Directory owner changed unexpectedly.' }
} catch {
    [Console]::Error.WriteLine('SCNS_ACL_ERROR ' + ((Get-ScnsAclDiagnostic -Exception $_.Exception -Stage $Stage) | ConvertTo-Json -Compress))
    exit 1
}
