# Native Windows: separate-copy migration and operation

Starting point: accepted `polish/muj-homepage` at `ee683e1a61a6584147c3e39b121a8765db5e46ba`. Owner reports homepage branding, directory and routing checks passed on Windows. This report is separate from automated Linux evidence.

**Status:** native implementation and isolated Linux verification are delivered. The owner reports the focused non-elevated DACL tests passed; actual decoder execution still fails and AppContainer/Job/DPAPI/application/migration acceptance remains **unverified**. Do not retire Docker or call full native compatibility verified from Linux results. Cloud cannot access the actual Windows database/volumes. No UI, routing/API/permission/publication contract, dependency lock or schema change. No native data is created by downloading the branch or running Setup.

**Owner-reported Windows attempt at `1928d1e`:** PowerShell7.6.7, Python/dependency installation and frontend build succeeded; native PostgreSQL17.11/PostGIS3.6.2 available, listen_addresses=localhost. Setup then failed protecting the existing directory with SeSecurityPrivilege. The subsequent owner retry at `8f54b70` confirms DACL protection and both focused tests passed; it then stops at the decoder gate with opaque OSError203. Use the decoder-only diagnostic below as the current next step. These preliminary successes do not establish decoder/native application or migration acceptance.

## Compatibility and security boundary

| Component | Native approach / prerequisite |
|---|---|
| Windows | Windows 11 x64, ordinary owner account; PowerShell 7.4+. No Docker/WSL/VM for native operation. UAC only for installing/configuring PostgreSQL/services, not running SCNS. AppContainer is Windows process security, not the Windows Sandbox VM feature. |
| PostgreSQL/PostGIS | PG17 x64 tools discovered via PATH, registered installation or explicit `-PgBin`; separate local PG17 server. Stable PostGIS 3.5/3.6, target at least source patch version; no automatic major upgrade. `ANY`/dev/beta versions excluded. Require loopback-only native server. SQL extension owner remains administrator; new random service role gets application DML/schema usage/sequence rights, never SUPERUSER. Existing **application** account hashes/grants/audits remain exact; Docker SQL cluster roles are intentionally not installed over native roles. |
| Python/uv | Managed Python 3.12 x64, frozen backend lock; 3.13 also allowed by project, 3.12 used by Setup. uv0.12.19 official Windows manifest checked. `uv sync --frozen` includes existing dev dependencies for verification/preflight; no new package/lock changes. |
| Native wheels | psycopg binary bundles libpq; Shapely bundles GEOS; Pillow codecs, PDFium, Argon2/cffi, greenlet and pydantic-core have locked Windows wheels. Segno/FastAPI/Alembic/settings are portable Python. No Ghostscript, Poppler, ImageMagick, Bash, Make or external GEOS is needed. Dev pypdf/zxing remain locked. Windows-x64 frozen dry-run resolves package metadata; that does not execute/validate Windows DLLs. |
| Node/frontend | Node22.12+ or24 LTS x64, npm ci; existing compiled frontend served with loopback Vite preview/proxy using `vite.native.config.mjs`. Native middleware preserves nginx's nosniff/referrer headers, private storage/data404s and10MiB body cap (including chunked requests). Actual loopback tests cover SPA/admin entry, original logo bytes, normal body forwarding/proxy and rejection boundaries. Local development, not public production hosting. UI/assets/controls unchanged. |
| PDF/image isolation | Linux resource/UID/seccomp behavior retained. Windows decoder is created suspended in an AppContainer with zero network capabilities, only explicit read-only runtime ACLs, read-only profile DACL and exactly three bounded handles. Read-only input, bounded in-memory stdout pipe, null stderr; no DB/proxy/session/native-config environment. Before execution a Job Object enforces 1GiB process/job memory, 20s process CPU, one process, kill-on-close; parent 30s wall and24MiB output cap. Windows permits read-only OS/runtime resources/private virtual registry rather than Linux's exact syscall filter; this is a different mechanism, not a claim of syscall equivalence. Mandatory actual private-file read, profile-write, live loopback denial and token/job probes plus real PDF/PNG decode fail closed before startup. No fallback to unrestricted processing. |
| Private state/files | `%LOCALAPPDATA%\SCNS\native`, protected owner/SYSTEM DACL. Generated import files and helper receipts/directories also receive actual protected DACLs; privacy tests inspect Windows ACL identities/rights, not Unix permission bits. Separate current-user DPAPI encrypted configuration/restore intent; administrator password only hidden input, never stored. Service password generated and stored only encrypted. Original `.env` is not edited or loaded by native services; its backup/container settings are DPAPI encrypted. Backup dump/private files contain sensitive account hashes/content: keep the protected folder and original Windows account, never commit/upload/share it. |
| Workers/processes | Existing imports/floorplan workers and leases retained. Supervisor owns API/frontend/worker Job tree, readiness through actual DB and frontend proxy; Ctrl+C/Stop allows15s grace then kills only owned children. Closing terminal/reboot closes Job handles; next Start uses the same copy. Recoverable leases typically wait120s; attempt limits remain3, no forced requeue/apply. |
| Helpers | `fcntl` replaced by portable byte-range locks on Windows; receipt replacement uses write-through MoveFileEx. Source-retention temporary files are closed before rename; interrupted replacement preserves previous bytes. Native journal root follows STORAGE_ROOT. Copies of old journals/receipts are preserved, not replayed; no import/naming/publication helper is part of migration. |

Process ownership is attached **at creation** with the Windows JOB_LIST attribute, avoiding a launcher spawning an unowned child before assignment. The decoder directly launches the managed base interpreter with explicit isolated/UTF-8/no-bytecode flags and trusted venv library paths: a Windows venv redirector may create a second process, which would violate its hard one-process limit. This was checked against [official CPython launcher source](https://raw.githubusercontent.com/python/cpython/v3.12.12/PC/launcher.c). Real Windows behavior still needs the native gates. Do not store secrets in the decoder-readable Python/.venv/app directories.

## 1. First Windows step: save work and fetch this branch

Run in your existing PowerShell, not WSL. Close SCNS admin tabs, stop other helper/SQL writers and keep Docker Desktop installed. Do not paste credentials into chat or commands. This block refuses dirty work rather than resetting it:

```powershell
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath 'C:\Users\Aaditya Shah\SCNS'
function Invoke-ScnsStep {
    param([Parameter(Mandatory=$true)][scriptblock]$Action)
    & $Action
    if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE). Stop; preserve both copies." }
}
Invoke-ScnsStep { git status --short }
$ScnsDirty = git status --porcelain
if ($LASTEXITCODE -ne 0 -or $ScnsDirty) { throw 'Preserve/commit local changes before continuing. Nothing reset.' }
Invoke-ScnsStep { git fetch origin refs/heads/feat/native-windows:refs/remotes/origin/feat/native-windows }
$ScnsBranch = git branch --list feat/native-windows
if ($ScnsBranch) {
    Invoke-ScnsStep { git switch feat/native-windows }
} else {
    Invoke-ScnsStep { git switch --no-track -c feat/native-windows refs/remotes/origin/feat/native-windows }
}
Invoke-ScnsStep { git pull --ff-only origin feat/native-windows }
Invoke-ScnsStep { git merge-base --is-ancestor ee683e1a61a6584147c3e39b121a8765db5e46ba HEAD }
Invoke-ScnsStep { git rev-parse HEAD }
```

## 2. Install official native prerequisites

Inspect each `winget show` publisher/version before installation. If already installed and supported, keep that installation. Commands install applications only; do not uninstall Docker or overwrite a PostgreSQL cluster. Existing native PG servers for other projects must not be replaced. EDB interactive installer asks for a **new native PostgreSQL administrator password privately**; keep it in your password manager, not this repository/terminal history. Choose an unused native port (usually5432; Docker's existing54329 stays intact), PostgreSQL Server, command-line tools and Stack Builder, automatic Windows service. No SCNS DB/account bootstrap.

```powershell
function Install-ScnsToolIfMissing {
    param([string]$Command, [string]$Package, [string]$Version)
    if (Get-Command $Command -ErrorAction SilentlyContinue) {
        Write-Host "Existing $Command retained; verify its supported version below."
        return
    }
    $ScnsInstallArgs = @('--exact','--id',$Package,'--source','winget')
    if ($Version) { $ScnsInstallArgs += @('--version',$Version) }
    winget show @ScnsInstallArgs
    if ($LASTEXITCODE) { throw "Cannot inspect official $Package package." }
    winget install @ScnsInstallArgs --interactive
    if ($LASTEXITCODE) { throw "$Package installation failed; stop here." }
}
Install-ScnsToolIfMissing -Command pwsh -Package Microsoft.PowerShell
Install-ScnsToolIfMissing -Command node -Package OpenJS.NodeJS.LTS
Install-ScnsToolIfMissing -Command uv -Package astral-sh.uv -Version 0.12.19
$ScnsRegistered17 = Get-ChildItem 'HKLM:\SOFTWARE\PostgreSQL\Installations' -ErrorAction SilentlyContinue |
    ForEach-Object { Get-ItemProperty $_.PSPath } |
    Where-Object { $_.Version -match '^17\.' }
if (-not $ScnsRegistered17) {
    winget show --exact --id PostgreSQL.PostgreSQL.17 --source winget
    if ($LASTEXITCODE) { throw 'Cannot inspect official PostgreSQL17 installer.' }
    winget install --exact --id PostgreSQL.PostgreSQL.17 --source winget --interactive
    if ($LASTEXITCODE) { throw 'PostgreSQL installation failed; stop here.' }
} else {
    Write-Host 'Existing PG17 installation retained. Inspect instance/port before using it.'
}
```

Check each command's result; do not proceed after an installer failure/hash/signature warning. Node LTS must be22.12+ or24 (official index checked24.22.0); a future unsupported major stops preflight. Official PG17 Windows manifest17.9-1 was confirmed, not asserted to be the latest release. PowerShell docs confirm winget installation. No TLS/hash bypass/download substitutions.

Open **Stack Builder**, choose your actual **PostgreSQL17 x64 instance/port**, expand **Spatial Extensions**, choose its stable **PostGIS3.5 or3.6 x64 bundle for PG17** (at least Docker source version). Install its server extension files/dependencies. Do not create a sample/spatial SCNS database or change the Docker DB. The helper verifies actual `pg_available_extension_versions`; source `ANY` is not an installable target. **Cloud could not verify the current PostGIS installer listing**: postgis.net/download.osgeo.org were proxy403. If Stack Builder offers no supported bundle, stop and report its exact available version; do not install unofficial DLLs or force a version. For missing VC runtime DLLs use Microsoft's official x64 redistributable, never arbitrary DLL download sites.

Open a **new ordinary-owner PowerShell7** terminal after installers update PATH. Verify/discover tools; no hardcoded PostgreSQL installation directory:

```powershell
Set-Location -LiteralPath 'C:\Users\Aaditya Shah\SCNS'
$PSVersionTable.PSVersion
uv --version
node --version
node -p process.arch
Get-Service | Where-Object Name -Like 'postgresql*' | Format-Table Name,Status
$ScnsPgBins = @(
    if (Get-Command pg_restore -ErrorAction SilentlyContinue) { Split-Path (Get-Command pg_restore).Source }
    Get-ChildItem 'HKLM:\SOFTWARE\PostgreSQL\Installations' -ErrorAction SilentlyContinue |
        ForEach-Object { Join-Path (Get-ItemProperty $_.PSPath).'Base Directory' 'bin' }
) | Sort-Object -Unique
$ScnsPgBins
$ScnsPgBin = Read-Host 'Paste the listed PostgreSQL17 bin directory (not a password)'
& (Join-Path $ScnsPgBin 'pg_restore.exe') --version
$ScnsPgPort = Read-Host 'Native PostgreSQL port selected during installation (usually5432)'
if (-not $ScnsPgPort) { $ScnsPgPort = '5432' }
# -W prompts privately. Inspect only the NATIVE instance, never Docker port54329.
& (Join-Path $ScnsPgBin 'psql.exe') -h 127.0.0.1 -p $ScnsPgPort -U postgres -d postgres -W -c "SELECT version(); SHOW listen_addresses; SELECT version FROM pg_available_extension_versions WHERE name='postgis';"
```

Native PostgreSQL must listen on `localhost`/loopback only. If the **new native instance** reports `*`, configure it explicitly, then restart **only that actual native PG17 service** in Services (`services.msc`, Run as Administrator). Do not change an unrelated existing cluster. SQL password is prompted; it is never an argument:

```powershell
& (Join-Path $ScnsPgBin 'psql.exe') -h 127.0.0.1 -p $ScnsPgPort -U postgres -d postgres -W -c "ALTER SYSTEM SET listen_addresses = 'localhost';"
Start-Process services.msc -Verb RunAs
# In Services: identify the PG17 service just installed, confirm Automatic startup,
# Restart it; return here and repeat the SHOW query above.
```

Do not add LAN/firewall exemptions. A firewall prompt for the local app does not require permission for public/private networks. If corporate execution policy forbids local scripts, stop for the administrator; do not bypass it. Commands below use process-scoped RemoteSigned for trusted checked-out scripts, not a machine policy change.

## 3. Frozen setup, real native security gate, read-only source inventory

For the source Inventory/Backup commands, start **Docker Desktop** from the Windows Start menu and wait for its engine to be running. This is needed only for the transition and possible rollback. Keep the original volumes/containers; do not recreate a database or start a replacement dataset. Native Setup/Preflight/Test and subsequent native operation do not require Docker.

```powershell
Set-Location -LiteralPath 'C:\Users\Aaditya Shah\SCNS'
pwsh -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\windows\scns.ps1 Setup -PgBin $ScnsPgBin
if ($LASTEXITCODE) { throw 'Setup failed. Do not back up/restore/start a native worker yet.' }
pwsh -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\windows\scns.ps1 Preflight -PgBin $ScnsPgBin
if ($LASTEXITCODE) { throw 'Native isolation/toolchain failed. Do not bypass it.' }

# Docker is needed ONLY for source inventory/backup and possible rollback.
# Preserve but deliberately exclude any stale temporary phone Compose override.
docker compose -f compose.yaml up -d --wait --no-deps --no-build db
if ($LASTEXITCODE) { throw 'Existing Docker database failed to start.' }
docker compose -f compose.yaml exec -T db pg_isready -U scns -d scns
if ($LASTEXITCODE) { throw 'Existing Docker database is not ready.' }
pwsh -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\windows\scns.ps1 Inventory -PgBin $ScnsPgBin
if ($LASTEXITCODE) { throw 'Read-only source inventory failed; do not guess state.' }
$ScnsState = Join-Path $env:LOCALAPPDATA 'SCNS\native'
$ScnsInventory = Get-Content -LiteralPath (Join-Path $ScnsState 'docker-inventory.json') -Raw | ConvertFrom-Json
$ScnsInventory.database | Select-Object server_major,postgis,revision
$ScnsInventory.database.active_releases | ConvertTo-Json -Depth 5
$ScnsInventory.storage_mounts | Format-List
```

Setup builds frontend via npm ci and backend via frozen uv; preserves `.env`, Docker images, uploads and database. It configures decoder-only read ACLs on Python/.venv/app plus read-only private profile; this does **not** grant access to native secrets/storage/repository root. Preflight must report actual Windows isolation and PDF+PNG success. No unsupported unrestricted decoder option exists. Inventory contains actual current public release UUIDs/content/artifact checksums where present, schema, all application row hashes and source mount/config **names**, never container credential values. Each `active_releases` entry is `[campus UUID, release UUID, release content checksum, public artifact checksum or null]`; no missing artifact checksum is invented. It is preliminary while writers may run; Backup repeats after stopping writers.

### Decoder-only diagnosis after profile configuration (current next step)

**Owner-reported at `8f54b70`:** direct DACL protection and both focused Windows tests passed (2 passed in4.73s), using an ordinary token. `Setup -ReuseDependencies` confirmed the frozen environment unchanged; Python3.12.15, Node22.23.2 and PG tools17.11. Read-only decoder profile/runtime configuration completed, then the decoder gate stopped with OSError/Windows203. This proves neither successful AppContainer execution nor a particular root cause. The old exception omitted the failing operation; **do not interpret203 alone as proof of an environment-variable problem**.

Use the new **DecoderDiagnostic**, not another full Setup retry. It directly uses the installed `.venv` interpreter, derives/inspects the existing profile (does not create/configure one), and runs the same real isolation and PNG/PDF gates. It does not install dependencies, invoke Node/npm/PG tools, rebuild frontend, read native credentials, re-protect retained directories, write native state/markers/locks/config, start services or connect to a database. Only temporary synthetic canary/input files receive owner/SYSTEM DACLs; the temporary live loopback listener tests denied access, not a listening SCNS application. No runtime/profile grants or isolation relaxation occur. Developer `.env` is excluded from controller imports; the child still receives only SystemRoot and the two fixed Python switches.

In your **non-elevated PowerShell7**, run this complete block. The path is the checkout used by the preceding guide; change only that path if your checkout is elsewhere. Local Git changes/divergence stop safely; nothing is reset:

```powershell
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath 'C:\Users\Aaditya Shah\SCNS'
function Invoke-ScnsDecoderStep {
    param([Parameter(Mandatory=$true)][scriptblock]$Action)
    & $Action
    if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE). Stop and preserve existing state." }
}
$ScnsDirty = git status --porcelain
if ($LASTEXITCODE -ne 0 -or $ScnsDirty) { throw 'Preserve local Git changes; nothing reset.' }
$ScnsBranch = git branch --show-current
if ($LASTEXITCODE -ne 0 -or $ScnsBranch -ne 'feat/native-windows') { throw 'Expected feat/native-windows. Do not overwrite another checkout.' }
Invoke-ScnsDecoderStep { git fetch origin refs/heads/feat/native-windows:refs/remotes/origin/feat/native-windows }
Invoke-ScnsDecoderStep { git merge-base --is-ancestor 8f54b7051ef79468dce52e11218cea406fa5847d origin/feat/native-windows }
Invoke-ScnsDecoderStep { git pull --ff-only origin feat/native-windows }
Invoke-ScnsDecoderStep { git rev-parse HEAD }
Invoke-ScnsDecoderStep { pwsh -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\windows\scns.ps1 DecoderDiagnostic }
```

Expected diagnostic output: `SCNS_DECODER_DIAGNOSTIC` records with **begin/passed/size-available**, fixed stage/operation names, followed by either the existing **Actual native AppContainer/job/file/network probe and PDF+PNG decoding passed.** line or one **SCNS_DECODER_ERROR** JSON record plus nonzero exit. Share only those records and the final outcome. No transcript, environment dump, passwords, file payloads or raw tracebacks are needed. An absent `windows_error` means no trustworthy native code was supplied, not that an unrelated stale last-error should be attached. HRESULT and child exit status are separately identified numeric fields, not automatically treated as Win32 last-error.

The record distinguishes profile derive/folder HRESULT, token/SDDL/SetFileSecurityW canary/input protection, pipe/tempfile/NUL/handle inheritance, DuplicateHandle, attribute size/init/security capabilities/handle list, environment block, direct interpreter command, CreateProcessW, AssignProcessToJobObject, ResumeThread, WaitForSingleObject, GetExitCodeProcess and resource cleanup. Child startup/loader refusal reports its exit status without forwarding private stderr. A failed gate never starts an unrestricted child or services. If a cleanup operation also fails, its sanitized diagnostic is separate and cannot replace the original launch failure. Retry this **same DecoderDiagnostic command only after a meaningful fix**; temporary fixtures do not create duplicate native copies or replace the existing profile. Do not proceed to Start/Backup/Restore until the actual decoder gate is resolved and the separate next operation is authorized. Passing this diagnostic alone is not full native application/migration/reboot acceptance.

Optional affected regression checks use only synthetic fixtures and the installed test dependencies; no install/build/data actions. These portable/mocked checks are separate from actual decoder verification:

```powershell
Push-Location -LiteralPath .\backend
try {
    & .\.venv\Scripts\python.exe -m pytest -q tests/unit/test_windows_decoder_diagnostics.py tests/unit/test_native_windows.py::test_powershell_contracts_and_reuse_dependency_branch tests/unit/test_native_windows.py::test_decoder_diagnostic_dispatch_never_enters_state_or_toolchain_actions tests/unit/test_native_windows.py::test_decoder_diagnostic_linux_refusal_does_not_create_state tests/unit/test_native_windows.py::test_decoder_diagnostic_existing_runtime_flow_is_sanitized_and_data_free
    if ($LASTEXITCODE -ne 0) { throw 'Affected synthetic checks failed; preserve state and report the test name.' }
} finally { Pop-Location }
```

On Windows the Linux-refusal test intentionally skips. This does not rerun/reclassify the two already owner-passed DACL tests. Confirmed source corrections delivered with this diagnostic: validate insufficient-buffer sizing before allocation; stop on WAIT_FAILED instead of replacing it with exit-code inspection; clean partial SID/Job/pipe initialization, avoid deleting uninitialized attribute storage or joining a thread that never started, and preserve a primary failure through cleanup. None is asserted to be the cause or a confirmed resolution of the owner's203. Existing DACL script, AppContainer/no-network/one-process/CPU/memory/suspended-start/read-only-handle boundaries remain intact.

### Targeted retry after the SeSecurityPrivilege Setup failure

**Historical retry, already owner-run at8f54b70:** direct protection and the two tests passed. Do not repeat full Setup to diagnose the subsequent203; use DecoderDiagnostic above.

Use an **ordinary, non-elevated PowerShell7** terminal. Keep the existing partial native directory, marker, locks and any configuration/data. Do not delete it or enable privileges. No PostgreSQL/Python/Node reinstall is needed for this retry. Stop if the repository has local work; nothing below resets it.

```powershell
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath 'C:\Users\Aaditya Shah\SCNS'
function Invoke-ScnsAclStep {
    param([Parameter(Mandatory=$true)][scriptblock]$Action)
    & $Action
    if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE). Stop and preserve existing state." }
}
$ScnsDirty = git status --porcelain
if ($LASTEXITCODE -ne 0 -or $ScnsDirty) { throw 'Preserve local Git changes before continuing. Nothing reset.' }
$ScnsBranch = git branch --show-current
if ($LASTEXITCODE -ne 0 -or $ScnsBranch -ne 'feat/native-windows') { throw 'Expected feat/native-windows. Preserve the existing checkout before selecting that branch.' }
Invoke-ScnsAclStep { git fetch origin refs/heads/feat/native-windows:refs/remotes/origin/feat/native-windows }
Invoke-ScnsAclStep { git merge-base --is-ancestor 1928d1ee9bfd5ffd4279ba19bb96eefd4e81988c origin/feat/native-windows }
Invoke-ScnsAclStep { git pull --ff-only origin feat/native-windows }
Invoke-ScnsAclStep { git rev-parse HEAD }
$ScnsState = Join-Path $env:LOCALAPPDATA 'SCNS\native'
if (-not (Test-Path -LiteralPath $ScnsState -PathType Container)) { throw 'Expected the existing partial native directory. Do not create a substitute state.' }
# First repeat the exact previously failing operation, DACL-only.
Invoke-ScnsAclStep { pwsh -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\windows\protect.ps1 -Path $ScnsState }
# Only isolated script/DACL fixtures, no database or retained native data.
Invoke-ScnsAclStep { uv --directory backend run --frozen --no-sync python -m pytest -q tests/unit/test_native_windows.py::test_powershell_contracts_and_reuse_dependency_branch tests/unit/test_native_windows.py::test_actual_windows_non_elevated_repeat_and_decoder_dacl }
# Read-only frozen environment check; reuse existing frontend/dist and dependencies.
Invoke-ScnsAclStep { pwsh -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\windows\scns.ps1 Setup -ReuseDependencies }
```

Expected: direct protection exits0 without the privilege error; the two focused tests pass on your actual non-elevated Windows token, including repeated protection and synthetic decoder RX inheritance. Setup prints **Reusing installed dependencies and compiled frontend**, then still configures decoder permissions and runs the actual AppContainer/Job/file/network and PDF/PNG gates. `-ReuseDependencies` is valid only for Setup: it runs `uv sync --frozen --check` (no installation), refuses missing outputs or lock mismatch, and never skips security gates. Existing normal Setup is unchanged. PostgreSQL tools are discovered as before; if you normally pass `-PgBin`, reuse that same actual directory on the final command.

This block does not start app services, access Docker, migrate/restore data or publish. Failure preserves existing partial state. Unknown non-native contents without a valid state marker still stop safely; never remove them to silence the guard. After a successful retry you may perform read-only Inventory separately; backup/restore remain distinct explicit steps, not part of this fix.

The cause is PowerShell's FileSystem provider `Set-Acl`, which first attempts all security sections. Its fallback can retain Audit when audit-protection and the existing protected-DACL flag differ. Setup calls protection at entry and again for its lock, so the already-protected repeat is important. The replacement uses direct `.NET FileSystemAclExtensions.SetAccessControl` with **only Access modified**, and explicit Access/Owner reads. It never invokes Set-Acl, writes ownership/group, reads/writes SACLs or enables privileges. Owner/SYSTEM FullControl and protected inheritance remain mandatory; only a validated AppContainer SID may additionally receive RX. Decoder descendants retain the prior DACL-only `icacls /reset` behavior and are checked for exact effective permissions. Existing Python helpers already use `SetFileSecurityW(0x80000004)` (protected DACL only) and `GetNamedSecurityInfoW(...,5)` (owner+DACL only), not SACL operations.

Sanitized failures now emit `SCNS_ACL_ERROR` with a stable stage, numeric Windows error where available and HRESULT. The parent retains these selected fields for state/profile protection and labels runtime RX-grant failures. Exception text, paths, account names and arbitrary tool output stay withheld. Report only that diagnostic line/parent stage if another failure occurs; do not paste configuration or credentials. No Administrator workaround is prescribed.

## 4. Stop writers and take a verified backup

Close helper jobs/psql edit sessions and browser admin tabs. Do not allow another operator to write during migration. Keep existing DB running. Enter the **native** PG17 administrator host/port/user and password privately; these are used only for compatibility inspection and are not saved. Type **BACKUP SCNS** at the explicit prompt:

```powershell
pwsh -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\windows\scns.ps1 Backup -PgBin $ScnsPgBin
if ($LASTEXITCODE) { throw 'Backup incomplete. Preserve files/originals; follow recovery below.' }
$ScnsBundle = (Get-Content -LiteralPath (Join-Path $ScnsState 'last-backup.json') -Raw | ConvertFrom-Json).bundle
$ScnsBackup = Get-Content -LiteralPath (Join-Path $ScnsBundle 'manifest.json') -Raw | ConvertFrom-Json
$ScnsBackup | Select-Object format,complete
$ScnsBackup.source | Select-Object server_major,postgis,revision
$ScnsBackup.source.active_releases | ConvertTo-Json -Depth 5
```

Expected complete=true, schema0016_closures, actual current MUJ/E22 and Demo release identities (no hardcoded older release). The tool stops only existing SCNS frontend/API/import-worker, checks they are stopped, dumps the DB with normal pg_dump, checks its custom archive directory and compares all application row/sequence/active-release digests before/after. A network-disabled read-only container hashes the actual existing private mount before/after copying. Private uploads/artifacts/journals are byte-compared, repository storage/data raw/staging/exports copied separately, `.env`/container configuration encrypted with current-user DPAPI. No source account/data/schema/publication change. Docker writers stay stopped. Backup root is owner/SYSTEM-protected; retain it, never post it in chat/Git. No PostgreSQL cluster role dump overwrites native SQL roles.

## 5. Restore only to a new native copy; verify before starting writers

Enter native PG administrator credentials privately again; type **RESTORE SCNS** when shown the newly reserved name. You never need to copy a database/draft UUID. Do not supply an existing DB name:

```powershell
pwsh -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\windows\scns.ps1 Restore -PgBin $ScnsPgBin
if ($LASTEXITCODE) { throw 'Restore stopped; do not start services or replay helpers.' }
pwsh -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\windows\scns.ps1 Verify -PgBin $ScnsPgBin
if ($LASTEXITCODE) { throw 'Initial native DB/files/reference verification failed; preserve both copies.' }
Get-Content -LiteralPath (Join-Path $ScnsState 'verified-copy.json') -Raw | ConvertFrom-Json |
    Select-Object database,storage,bundle,schema
```

Restore verifies every backup hash again, source/native PG17/PostGIS compatibility and revision, durably reserves a nonce SQL role/DB/storage path **before** creation, restores transactionally into that new DB and copies to new native storage. Normal account password hashes, permissions, audit rows, graphs/drafts/versions, frozen releases/artifacts, floorplans, QR and restrictions must compare exactly, including sequence state and actual active release IDs. It checks active staged upload references, all private/repository helper file hashes, no invalid constraints. No seed/bootstrap/migration/rename/reimport/approval/publication action. Only the original source copy remains in Docker; native credentials point exclusively to the new copy. Initial Verify is intentionally strict; after legitimate native use, changes to sessions/audits/data make the old snapshot differ. That is **not** permission to restore over existing data.

Floorplan originals/sanitized PNGs and retained source bytes are database binary columns, not missing external files: the full logical dump and all-column row hashes include them. Floor/layer/source/anchor references remain enforced by restored foreign keys. Filesystem import originals and helper journals/receipts are checked separately in the private-storage copies. Nothing is reconstructed from a screenshot or reprocessed to manufacture a matching release.

## 6. One-command normal startup, stop and reboot recovery

```powershell
Set-Location -LiteralPath 'C:\Users\Aaditya Shah\SCNS'
pwsh -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\windows\scns.ps1 Start
```

The PG17 Windows service should start automatically on boot. The command checks that database/schema and real isolation first, starts FastAPI8000, compiled frontend5173, then worker, verifies actual DB readiness through the frontend proxy. Open `http://localhost:5173/`; keep the terminal open. Protected timestamped API/frontend/worker logs and running.json live in `$ScnsState`; no access logs/credentials/environment dumps. Service failure stops the owned tree, never silently leaves a half-ready app. Inspect those logs locally; do not paste unredacted private logs/configuration.

Press **Ctrl+C** in Start terminal, or from another normal PowerShell7:

```powershell
Set-Location -LiteralPath 'C:\Users\Aaditya Shah\SCNS'
pwsh -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\windows\scns.ps1 Stop
```

Stop requests the supervisor, never kills a potentially reused PID. Wait for its stopped message. Closing the terminal/rebooting kills the Job tree; data/PostgreSQL remain. Reopen and run **Start**, not Setup/Restore. Durable processing leases recover normally, at most3 attempts; no manual database status edits. Once the native copy has passed acceptance, Docker Desktop may remain closed for native operation; do not uninstall it or delete volumes. There is no Windows auto-login service storing an application password.

## 7. Isolated native verification and retained-copy acceptance

Run Test with Start stopped (test ports8001/5174 must be free). It privately prompts for native PG admin, then **TEST ISOLATED** authorizes only newly created nonce `_test` databases/private storage. Installs browser test binaries separately if missing:

```powershell
Set-Location -LiteralPath 'C:\Users\Aaditya Shah\SCNS'
node .\node_modules\playwright\cli.js install chromium
if ($LASTEXITCODE) { throw 'Browser download failed; retain normal TLS/checksums.' }
pwsh -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\windows\scns.ps1 Test -PgBin $ScnsPgBin
if ($LASTEXITCODE) { throw 'Isolated native verification failed; inspect protected check logs, do not claim native acceptance.' }
pwsh -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\windows\scns.ps1 Start -PgBin $ScnsPgBin
```

Test uses normal isolated backend unit/PostGIS tests, migration rehearsal and desktop/mobile public/admin/import/floorplan/QR/GPS/closure/indoor journeys, plus actual Windows DPAPI/DACL/AppContainer/Job tests. It owns/removes only its newly created test DBs, not native copy or Docker volumes. Some test-source MUJ metadata is simulated; it is not your actual MUJ publication. Keep named test logs/results separate from these manual **actual restored-copy** checks:

Native preview checks also run against the compiled frontend and a disposable mock API: original asset bytes, SPA/admin entry, forwarding, security headers, private-path404s and fixed/chunked upload limits. These checks do not access retained accounts or data. A Linux pass for this Node server verifies portable hosting behavior, not Windows process ownership, filesystem ACLs or decoder execution. The complete latest cloud results and failed-attempt history are in [verification evidence](../testing/verification.md).

You may run the isolated Test command before Backup/Restore to establish native compatibility first; it does not require a restored copy. A forced interruption inside a test fixture may leave additional synthetic nonce databases/roles if that fixture's cleanup cannot finish. Do not delete anything by prefix/wildcard. Preserve protected logs/temporary test records for explicit ownership review. A missing restore intent with existing native copies blocks automatic creation; recover the original State or explicitly authorize a separate copy with `-NewTarget`. Normal app Stop/reboot does not rely on test cleanup.

1. Homepage → select **Demo Campus**: synthetic disclosure, no MUJ imagery. Select existing MUJ: original dome photo/emblem/student qualification, full directory. E22 = **TMA Pai Auditorium entrance**; E05/unresolved names unchanged. Places search **books**, category **Library**, Next/Previous and Start here/Route here preserve focus and original actions.
2. Demo **Main Gate → Library**, **Shortest walking route / Metric · stored path distances**: approximately256.88m,3stored edges (UI257m/4min), absent applicable closures. Hide map: directions remain. Reload URL restores choices; indoor/floor controls and section buttons use your retained approved floor data. **Main Gate → Quiet Garden** remains contextual no-route, without a surprise page jump.
3. MUJ **University Entrance → Mapped entrance 10828149259**, metric shortest approximately513m/13edges; **Directions only / Fewest eligible traversals** approximately799m/9edges. Keep unsupported Library/cross-campus/verified step-free unavailable. Check active release UUID/checksums match the local backup report; do not reuse a previously reported release UUID. Read-only tests, no field/accessibility/institutional verification claimed.
4. Sign in with the **existing application owner** privately; original account/password and grants work, existing drafts/import/floorplan history and audit/release history visible. Sign out/in; fresh anonymous screen normal. No new account bootstrap. Review private source/artifact access under the same existing permissions. Do not mutate retained drafts or publish merely for testing; use isolated Test for write/worker cases.
5. Open `http://localhost:5173/q/00000000-0000-4000-8000-000000000000`: expect unknown-marker/manual fallback. Existing active marker links must still require confirmation. Do not create/revoke/reassign retained markers for this check; isolated Test covers lifecycle changes. For GPS, select Demo Campus and use Chrome Protocol Monitor with the exact synthetic command below, then **Use my location → Allow → I am at this landmark now**. Expect a ±5m Gate suggestion, no route before confirmation, and Library metric257m/4min afterwards. Clear the override afterwards. This is simulated-browser evidence, not a real GPS/physical gate claim. [Beginner Protocol Monitor instructions](geolocation.md#beginner-chrome-simulation-precise-coordinates-and-accuracy).

   ```json
   {"cmd":"Emulation.setGeolocationOverride","args":{"latitude":0.0002,"longitude":0.00015,"accuracy":5}}
   ```

   ```json
   {"cmd":"Emulation.clearGeolocationOverride","args":{}}
   ```

   Existing closures/restriction freshness and release refresh remain; do not alter retained closures/publications for testing. If the already published synthetic3C rooms are present, use the read-only route table in [indoor public checks](indoor-routing.md#review-and-public-route-manual-test): Ground101→Ground102 metric18m; Ground101→Upper201 shortest36m/stairs, step-free57m/lift; Ground101→ISO no-route. Do **not** replay that guide's prerequisite fixtures or publish anything to manufacture these cases. Otherwise use your retained approved floor controls and rely on isolated Test for synthetic routing coverage.
6. Stop and Start twice, including after closing terminal/reboot. Same database/storage, public release IDs/routes and account access remain. Native PG must be ready before API. Record your exact native versions, successful gates, any failures and actual local results; Linux cloud passes do not substitute for this sequence.

## Interruption recovery and Docker rollback

| State | Safe next step |
|---|---|
| Setup/preflight/decoder refused | Stop. Keep Docker/data/.env. Check the exact Windows tool/version/ACL error; do not bypass the sandbox, add network capabilities or disable limits. A failure means native processing is not validated. |
| Backup interrupted/incomplete | Original Docker source is intact, writers may remain stopped. Rerun Backup for a **new** consistent bundle; incomplete one retained/never restored. To use a previous complete bundle pass its exact protected folder with `-Bundle '...'` to Restore. |
| Restore response/config-save lost after successful application | Repeat **same Restore**, same State/Bundle. It reads the reserved target and verifies full DB/files; no duplicate restore/role/DB if it matches. |
| Partial DB/storage or role creation uncertain | Tool stops without reset/drop/merge. Preserve intent/partial copy. `Restore -NewTarget` explicitly reserves a different new copy; prior DB/storage/intents/config remain archived. It never repairs/replays over a partial or owner-edited target. |
| Source/backup mismatch or conflicting owner edit | Stop and inspect; no data overwrite. A new backup from explicitly chosen authoritative copy may be needed. Do not run Verify after normal usage and treat legitimate changes as corruption. |
| Native service exits / shutdown interrupted | Protected logs identify process failure; Start uses same config/copy after reboot. Job kill-on-close prevents orphan descendants; normal durable leases/attempt caps handle jobs. Native DB service stays intact. |

To return to **the original Docker copy**, stop native first. Both copies remain; later native changes are **not automatically synchronized back**. Choose the authoritative copy before further edits; rollback selects the earlier Docker state, not a merge. Existing Docker images are the accepted prior installation; no build/migrate/seed/reimport/helper replay:

```powershell
Set-Location -LiteralPath 'C:\Users\Aaditya Shah\SCNS'
pwsh -NoProfile -ExecutionPolicy RemoteSigned -File .\scripts\windows\scns.ps1 Stop
# Wait for the Start terminal's stopped message. Start Docker Desktop normally.
$ScnsOldPublicUrl = $env:PUBLIC_APP_URL
try {
    $env:PUBLIC_APP_URL = 'http://localhost:5173'
    docker compose -f compose.yaml up -d --wait --no-deps --no-build db
    if ($LASTEXITCODE) { throw 'Docker DB startup failed.' }
    docker compose -f compose.yaml exec -T db pg_isready -U scns -d scns
    if ($LASTEXITCODE) { throw 'Docker DB not ready; do not start API.' }
    docker compose -f compose.yaml up -d --wait --no-deps --no-build --force-recreate api
    if ($LASTEXITCODE) { throw 'Docker API readiness failed.' }
    docker compose -f compose.yaml up -d --wait --no-deps --no-build --force-recreate frontend
    if ($LASTEXITCODE) { throw 'Docker frontend failed.' }
    docker compose -f compose.yaml up -d --no-deps --no-build import-worker
    if ($LASTEXITCODE) { throw 'Docker worker failed.' }
    Invoke-RestMethod 'http://localhost:5173/api/v1/health/ready'
    Start-Process 'http://localhost:5173/'
} finally {
    $env:PUBLIC_APP_URL = $ScnsOldPublicUrl
}
```

Explicit base compose file preserves/excludes the old temporary phone override; no LAN/firewall change. Keep native copies/backups intact. Reversing later native-only data changes into Docker would be a separate verified migration, never an automatic destructive rollback.

## Official-source verification (18 October 2026)

Direct PostgreSQL/PostGIS/uv/Microsoft docs hosts were proxy403 in cloud. Verified official mirrors instead: [PostgreSQL Windows installation page](https://raw.githubusercontent.com/postgres/pgweb/master/templates/pages/download/windows.html) (EDB installer/Stack Builder/PG17); [Microsoft winget PG17.9-1 manifest](https://raw.githubusercontent.com/microsoft/winget-pkgs/master/manifests/p/PostgreSQL/PostgreSQL/17/17.9-1/PostgreSQL.PostgreSQL.17.installer.yaml); [uv installation docs](https://raw.githubusercontent.com/astral-sh/uv/main/docs/getting-started/installation.md) and [Windows0.12.19 manifest](https://raw.githubusercontent.com/microsoft/winget-pkgs/master/manifests/a/astral-sh/uv/0.12.19/astral-sh.uv.installer.yaml); [PowerShell Windows installation docs](https://raw.githubusercontent.com/MicrosoftDocs/PowerShell-Docs/main/reference/docs-conceptual/install/install-powershell-on-windows.md); [Microsoft AppContainer isolation](https://raw.githubusercontent.com/MicrosoftDocs/win32/docs/desktop-src/SecAuthZ/appcontainer-isolation.md)/[legacy-app support](https://raw.githubusercontent.com/MicrosoftDocs/win32/docs/desktop-src/SecAuthZ/appcontainer-for-legacy-applications-.md). [Official Node release index](https://nodejs.org/dist/index.json) confirms24.22.0 LTS Windows x64 MSI. No claim the blocked current PostGIS Windows package listing was verified; actual installed extension/DLL/native execution are owner-run gates. [Verification evidence](../testing/verification.md).
