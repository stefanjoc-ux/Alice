<#
Alice on Azure: build everything in the Tuduma subscription, step by step. Safe to run again: each step picks up
where things are. Run from the repo folder (D:\AISubstrate) in PowerShell, after `az login` to the Tuduma tenant.

  .\deploy\azure-setup.ps1 -SubscriptionId <id> -ExtAppId <Alice API app id> -ExtCallers "<copilot app id>=Microsoft Copilot:copilot"

Steps (all by default, or one with -Step):
  infra    resource group, private network, PostgreSQL, Key Vault, registry, file share, Container Apps environment
  secrets  asks for each API key (hidden as you type) and stores it in Key Vault; Enter skips one
  image    builds the container image IN AZURE (no Docker needed on the PC) and tags it with the git commit
  files    copies Documents\ and data\images\ to the file share, and data\substrate.db for the migration (quit Alice first)
  migrate  dry run of the database copy, then (after you confirm) the real copy into PostgreSQL
  signin   creates the "Alice web sign-in" app registration (only you can sign in) and stores its secret in Key Vault
  apps     starts alice-web and alice-mcp
  github   lets the GitHub pipeline deploy (OIDC, no stored secrets) and prints the repo variables to set
  connector  (run on its own) the Claude connector: an "Alice connector sign-in" app registration, its secret and a
           signing key in Key Vault, then alice-mcp updated so Claude can sign in through Alice
  demo     (run on its own) the demo Alice for client demos: alice-demo-web and alice-demo-mcp on the live image, with their
           own database (alice_demo) and data folder; same sign-in (only you) and the same Alice API app for Copilot
  copilot  (run on its own) Alice as an agent in Microsoft 365 Copilot: prepares the Alice API app for Copilot's Entra single
           sign-on (Teams' redirect address, the Application ID URI from the Developer Portal registration, the Microsoft token
           store pre-authorised), lets Copilot's token store call alice-mcp (and alice-demo-mcp), then builds the app packages
           in dist\ to upload in Teams. First register the sign-on in the Teams Developer Portal (see CLAUDE.md), then:
             -Step copilot -CopilotAudience <Application ID URI> -CopilotAuthId <auth config ID>
             [-CopilotDemoAudience <URI> -CopilotDemoAuthId <ID>] [-AlsoAllow you@yourdomain]
  mail     (run on its own) lets Alice email (held decisions go to their owner): -Step mail -MailFrom alice@yourdomain
           gives Alice's managed identity the Microsoft Graph permission Mail.Send (no password or secret) and sets the
           sending mailbox on alice-web and alice-mcp. The mailbox must exist (a shared mailbox needs no licence).
  backup   (run on its own) backups: Azure Backup for the file share (daily snapshots, kept 30 days), a CanNotDelete lock on
           the resource group, PostgreSQL backups kept 35 days, and the nightly off-site copy (the alice-backup job at 02:00 UK
           time: database and files to a separate storage account in UK West, unchangeable for 35 days). Takes the first
           off-site copy straight away. Remembered: every later step keeps backups on.
             -Step backup [-BackupNotify you@yourdomain] [-FilesBackupDays 30] [-OffsiteKeepDays 35] [-OffsiteSoftDeleteDays 35]
                          [-PgBackupDays 35] [-NoLock] [-LockImmutability] [-PgGeoBackup]
           Lift the lock deliberately: az lock delete --name alice-do-not-delete --resource-group <rg>, then -Step backup -NoLock.
           Also sets up the restore drill: its own resource group (<rg>-drill, throwaway resources only), identity and the
           alice-drill job (Admin > Backups > Run a restore drill now, or the Restore drill workflow).
  localmodel  (run on its own) Temple's local model: a small open model (default qwen3:4b, served by Ollama) in Alice's own
           Container Apps environment, INTERNAL INGRESS ONLY (no public address), with its own file share for the downloaded
           model. Alice then offers Local under Agents > Temple's model for screening and categories (the sharing check,
           categories, tags and keeping them tidy); choosing it is still yours, on that page. Remembered: every later step keeps it.
             -Step localmodel -LocalModel on [-LocalModelName qwen3:4b]
             -Step localmodel -LocalModel off      Alice stops using it, and it is scaled to zero (no charge while idle)
  users    (run on its own) people and roles: adds the app roles Alice.Owner, Alice.Admin and Alice.Member to the "Alice web
           sign-in" app registration (and the "Alice connector sign-in" one if it exists), sets "Assignment required" on the web
           sign-in's enterprise application, and assigns the roles on BOTH apps (the connector's sign-in too, so the owner's
           Claude and ChatGPT calls run as the owner, not as whichever account happened to be assigned). ENTRA DECIDES THE OWNER: anyone with Alice.Owner is an owner
           of Alice (full access, including Health, Trading, Mileage and Backups). This step assigns Alice.Owner to the owner
           (ownerObjectId, below) and Alice.Admin to the admins (-AdminObjectIds, remembered; you, if you are not the owner, and a
           previous owner) and takes Alice.Owner away from those admins, never from the owner, so there is always an Owner. Other
           accounts in -AlsoAllow get Alice.Member, so nobody who gets in today is locked out by the switch. It does NOT switch
           Alice over: until you run -Step users -UseAppRoles on and then -Step apps, Entra still lets in only the accounts it does
           today (allowedPrincipals), so nobody is locked out. Adding a person afterwards = assigning them a role in Entra
           (Enterprise applications > Alice web sign-in > Users and groups); they start with the default Member profile.
             -Step users                      roles, Assignment required, you as Owner (safe to run again)
             -Step users -UseAppRoles on      remember the switch; then -Step apps puts it live (off = back to allowedPrincipals)
  -OwnerObjectId <object ID or user@domain>  (any step; remembered in the setup state as ownerObjectId) the account that owns
           Alice: -Step users gives it Alice.Owner, and until app roles are on (-UseAppRoles on) it is the bootstrap fallback,
           ALICE_OWNER_OBJECT_ID on the apps (put live with -Step apps). Not set = the account running this script (as before).
           Changing it keeps the previous owner as an admin (Alice.Admin, still allowed to sign in), never a second Owner.
  -AdminObjectIds <ids or user@domain, comma separated>  (-Step users; remembered as adminObjectIds) accounts given Alice.Admin.
  recover  (run on its own, in a NEW resource group from a fresh clone; docs/restore.md part C) loads a nightly off-site copy
           into this new, empty Alice before its apps start: -Step recover -RecoverFrom <offsite account> [-RecoverCopy yyyy/mm/dd]
  check    (run on its own; READ-ONLY, changes nothing) lists what each step has set up in the resource group (sign-in,
           apps, connector, demo, Copilot, mail, backups: the vault and its retention, the lock, the off-site account and its
           retention, the nightly job and its last run, the drill; app roles) and flags anything missing or different.
  -DatabaseHost <server address>  (any step; remembered) after a point-in-time restore into a new server (docs/restore.md part B),
           so redeploys keep database-url pointing at it. -DatabaseHost '' goes back to this template's own server.
           Every deployment of main.bicep names the database: when databaseHost is not set it is set to the address of the
           resource group's own server (read from Azure), and the step stops if that cannot be read. Only the first -Step
           infra, before any server exists, deploys without one.
The setup state (what every step set up and every later step keeps) lives IN AZURE: the blob alice-setup/azure-state.json in
Alice's own storage account (deploy/azure_state.py). Every step reads it first and writes it back whenever it saves; each saved
version is also kept under alice-setup/history/. deploy\azure-state.json is only a cache of it. If the Azure copy is missing or
older than the newest deployment, it is rebuilt from what is deployed first, and you are shown what was rebuilt. If the local
file differs from the Azure copy, the step stops: delete or rename the local file to use the Azure copy, or add -UseLocalState
to use the local file deliberately (it then replaces the Azure copy).
Every step but check is recorded in the setup history (who, when, step, the settings given, result; never a key or password):
in the setup state in Azure and on the file share (setup/setup-history.json), shown on Alice's Admin › What's new page.
Nothing here reads .env: keys are typed in once and live only in Key Vault.
#>
param(
  [Parameter(Mandatory = $true)][string]$SubscriptionId,
  [string]$ResourceGroup = 'alice-rg',
  [string]$Location = 'uksouth',
  [string]$ExtAppId = '',
  [string]$ExtCallers = '',
  [string]$ExtAllowedUsers = '',
  [string]$GitHubRepo = '',
  [string]$AlsoAllow = '',      # other accounts allowed to sign in, comma separated (e.g. stefan@yourdomain); remembered
  [string]$CustomDomain = '',
  [string]$GitHubSubject = '',  # the exact OIDC subject GitHub presents, if it uses owner and repo IDs (shown in a failed deploy log)   # e.g. alice.northants.it, after binding it once with a managed certificate; remembered
  [string]$CopilotAudience = '',      # Application ID URI(s) from the Developer Portal Entra SSO registration(s), comma separated
  [string]$CopilotAuthId = '',        # its auth config ID (live Alice)
  [string]$CopilotDemoAudience = '',
  [string]$CopilotDemoAuthId = '',    # the demo Alice's registration
  [string]$MailFrom = '',             # -Step mail: the mailbox Alice sends from
  [string]$BackupNotify = '',         # -Step backup: who is emailed when a nightly backup fails (default: you); remembered
  [int]$FilesBackupDays = 0,          # -Step backup: days of file share snapshots kept (default 30); remembered
  [int]$OffsiteKeepDays = 0,          # -Step backup: days each off-site copy is unchangeable, then removed (default 35); remembered
  [int]$OffsiteSoftDeleteDays = 0,    # -Step backup: days a deleted off-site copy stays recoverable (default 35); remembered
  [int]$PgBackupDays = 0,             # -Step backup: days of database backups (7-35, default 35); remembered
  [switch]$NoLock,                    # -Step backup: no CanNotDelete lock on the resource group (it is on unless you say so)
  [switch]$LockImmutability,          # -Step backup: lock the off-site immutability policy for good (asks you to confirm)
  [switch]$PgGeoBackup,               # -Step backup: geo-redundant database backups (only if the server was created with them)
  [string]$RecoverFrom = '',          # -Step recover: the off-site storage account holding the copies
  [string]$RecoverCopy = '',          # -Step recover: which night (yyyy/mm/dd); default the newest copy
  [string]$DatabaseHost = '',         # after a point-in-time restore: the server Alice uses (remembered; '' = the template's own)
  [ValidateSet('', 'on', 'off')][string]$UseAppRoles = '',   # -Step users: switch who gets in to Entra app roles (on) or back (off); remembered
  [string]$OwnerObjectId = '',        # the owner of Alice (object ID, or user@domain); remembered as ownerObjectId; default: you
  [string]$AdminObjectIds = '',       # -Step users: accounts given Alice.Admin (comma separated); remembered as adminObjectIds
  [ValidateSet('', 'on', 'off')][string]$LocalModel = '',   # -Step localmodel: Temple's local model on or off; remembered
  [string]$LocalModelName = '',       # -Step localmodel: the Ollama model tag (default qwen3:4b); remembered
  [switch]$UseLocalState,             # use deploy\azure-state.json even though it differs from the Azure copy (it then replaces it)
  [ValidateSet('all', 'infra', 'secrets', 'image', 'files', 'migrate', 'signin', 'apps', 'github', 'connector', 'demo', 'copilot', 'mail', 'backup', 'recover', 'users', 'localmodel', 'check')][string]$Step = 'all'
)
$ErrorActionPreference = 'Stop'
$ScriptParams = @{}; foreach ($k in $PSBoundParameters.Keys) { $ScriptParams[$k] = $PSBoundParameters[$k] }   # for the setup history (Record-Step)
$Root = Split-Path -Parent $PSScriptRoot
$Template = Join-Path $Root 'infra\main.bicep'
$StateFile = Join-Path $PSScriptRoot 'azure-state.json'     # a cache: the setup state lives in Azure (azure_state.py)
$StateHelper = Join-Path $PSScriptRoot 'azure_state.py'
function Find-Python {
  # The PC's .venv, else Python on the PATH (Cloud Shell has python3). Each is tried, so the Windows Store stub is skipped.
  foreach ($c in @((Join-Path $Root '.venv\Scripts\python.exe'), (Join-Path $Root '.venv/bin/python'), 'python3', 'python', 'py')) {
    if (-not ((Test-Path $c) -or (Get-Command $c -ErrorAction SilentlyContinue))) { continue }
    $ErrorActionPreference = 'Continue'
    & $c -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { return $c }
  }
  throw 'Python 3.8 or later is needed for the setup state (deploy\azure_state.py). On the PC: python.org, or run from the folder with .venv. Cloud Shell has it.'
}
$StatePy = Find-Python

function Say($text) { Write-Host "`n== $text" -ForegroundColor Cyan }
function AzCli { $out = & az @args; if ($LASTEXITCODE -ne 0) { throw "az $($args -join ' ') failed" }; return $out }   # not named Az: PowerShell names ignore case, so it would call itself
function AzTry { $ErrorActionPreference = 'Continue'; & az @args 2>$null }   # may fail (e.g. "does it exist?"): Windows PowerShell 5.1 otherwise turns az's error text into a stop
function Want($name) { return (($Step -eq 'all' -and $name -notin @('connector', 'demo', 'copilot', 'mail', 'backup', 'recover', 'users', 'localmodel')) -or $Step -eq $name) }
function Public-Url { if ($State.customDomain) { return "https://$($State.customDomain)" } else { return "$($State.webUrl)" } }
function Audiences { return (@($State.extAudiences | Where-Object { $_ }) -join ',') }   # Copilot's SSO audiences, kept on every redeploy
function Add-AlsoAllow {
  $also = @($State.alsoAllow | Where-Object { $_ })
  foreach ($u in ($AlsoAllow -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ })) {
    $oid = if ($u -match '^[0-9a-fA-F-]{36}$') { $u } else { AzCli ad user show --id $u --query id -o tsv }
    if ($oid -and $also -notcontains $oid) { $also += $oid; Write-Host "Also allowed to sign in: $u ($oid)" }
  }
  Set-Prop $State 'alsoAllow' $also
  return ,$also
}
function Load-State { if (Test-Path $StateFile) { return Get-Content $StateFile -Raw | ConvertFrom-Json } else { return [pscustomobject]@{} } }
function Sync-State {
  # The Azure copy first: read it (rebuilt from what is deployed if missing or behind), refuse a local file that differs.
  $a = @('load', '--resource-group', $ResourceGroup, '--file', $StateFile, '--who', "$Me")
  if ($UseLocalState) { $a += '--use-local' }
  & $StatePy $StateHelper @a | Out-Host
  if ($LASTEXITCODE -ne 0) { throw 'Stopped before changing anything: the setup state could not be settled (see above).' }
}
function Save-State($s) {
  # Locally (the cache), then the Azure copy, with its ETag so another run's save is never overwritten.
  $s | ConvertTo-Json -Depth 5 | Set-Content $StateFile -Encoding UTF8
  & $StatePy $StateHelper save --resource-group $ResourceGroup --file $StateFile --who "$Me" --step $Step | Out-Host
  if ($LASTEXITCODE -ne 0) { throw 'The setup state could not be saved to Azure (see above). Run -Step check to see what is set up.' }
  $fresh = Get-Content $StateFile -Raw | ConvertFrom-Json
  if ($fresh._azure) { Set-Prop $s '_azure' $fresh._azure }
}
function Record-Step($result, $err) {
  # The setup history (Stefan, 9 Oct 2026): one line per step that changes Azure (who, when, step, settings, result), kept in the
  # setup state in Azure and copied to the file share for Admin › What's new. azure_state.py records only the settings it knows
  # by name and never a value that looks like a key or password. Best effort: it never changes the step's own outcome.
  $a = @('history', '--resource-group', $ResourceGroup, '--file', $StateFile, '--who', "$Me", '--who-name', "$MeName", '--step', $Step, '--result', $result)
  foreach ($k in $ScriptParams.Keys) {
    if ($k -in @('SubscriptionId', 'Step')) { continue }
    $v = $ScriptParams[$k]
    if ($v -is [System.Management.Automation.SwitchParameter]) { $v = [bool]$v }
    $a += @('--param', "$k=$v")
  }
  if ($err) { $a += @('--error', ("$err" -split "`n")[0]) }
  $ErrorActionPreference = 'Continue'
  & $StatePy $StateHelper @a 2>$null | Out-Host
}
function Json-Array($lines) {
  # A JSON array from az as a real array of its items, in Windows PowerShell 5.1 too (its ConvertFrom-Json returns the whole
  # array as ONE object, so @(... | ConvertFrom-Json) is an array holding an array)
  $items = @()
  foreach ($x in (((@($lines) -join "`n").Trim()) | ConvertFrom-Json)) { $items += $x }
  return ,$items
}
function Set-Prop($obj, $name, $value) { $obj | Add-Member -NotePropertyName $name -NotePropertyValue $value -Force }
function New-Password { -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 32 | ForEach-Object { [char]$_ }) }
function Kv-Has($kv, $name) { AzTry keyvault secret show --vault-name $kv --name $name --query id -o tsv | Out-Null; return ($LASTEXITCODE -eq 0) }
function Kv-Set($kv, $name, $value) {
  $tmp = New-TemporaryFile
  try {
    [IO.File]::WriteAllText($tmp, $value)
    for ($i = 0; $i -lt 12; $i++) {            # Key Vault role assignments can take a minute to apply
      AzTry keyvault secret set --vault-name $kv --name $name --file $tmp --encoding utf-8 --output none
      if ($LASTEXITCODE -eq 0) { return }
      Start-Sleep -Seconds 10
    }
    throw "Could not write secret $name to Key Vault $kv."
  } finally { Remove-Item $tmp -Force -ErrorAction SilentlyContinue }
}
function Kv-Get($kv, $name) { return (AzCli keyvault secret show --vault-name $kv --name $name --query value -o tsv) }

AzCli account set --subscription $SubscriptionId | Out-Null
$Me = AzCli ad signed-in-user show --query id -o tsv
$MeName = AzTry ad signed-in-user show --query userPrincipalName -o tsv
$Tenant = AzCli account show --query tenantId -o tsv
if ($Step -eq 'check') {
  Say "Check (read-only): what each step has set up in $ResourceGroup"
  & $StatePy $StateHelper check --resource-group $ResourceGroup --file $StateFile --who "$Me" | Out-Host
  if ($LASTEXITCODE -ne 0) { throw 'The check could not finish (see above). Nothing was changed.' }
  return
}
Sync-State
$State = Load-State
$StateReady = $true
# A step that stops with an error is recorded in the setup history too (then stops as before)
trap { if ($StateReady -and -not $script:Recorded) { $script:Recorded = $true; Record-Step 'failed' "$($_.Exception.Message)" }; break }
if ($PSBoundParameters.ContainsKey('DatabaseHost')) { Set-Prop $State 'databaseHost' $DatabaseHost.Trim(); Save-State $State }   # '' clears it

# The owner of Alice: a setting in the setup state (ownerObjectId), never simply whoever runs this script. -OwnerObjectId sets
# it; only when it was never set does it default to you. Entra decides who is an owner (Alice.Owner); ownerObjectId is who
# -Step users gives that role, and the bootstrap fallback while app roles are off. A previous owner becomes an admin.
function Resolve-User($u) {
  $u = "$u".Trim()
  $id = AzTry ad user show --id $u --query id -o tsv
  if (-not $id) { throw "No account '$u' in tenant $Tenant (give its object ID, or its sign-in name user@domain). Nothing was changed." }
  return "$id".Trim().ToLower()
}
function Owner { return "$($State.ownerObjectId)".Trim().ToLower() }
function Admins { return @($State.adminObjectIds | Where-Object { $_ } | ForEach-Object { "$_".ToLower() } | Where-Object { $_ -ne (Owner) } | Select-Object -Unique) }
function Add-Admin($oid) {
  $oid = "$oid".Trim().ToLower()
  if (-not $oid -or $oid -eq (Owner)) { return }
  $have = @($State.adminObjectIds | Where-Object { $_ } | ForEach-Object { "$_".ToLower() })
  if ($have -notcontains $oid) { Set-Prop $State 'adminObjectIds' @($have + $oid); Write-Host "Admin of Alice (Alice.Admin, not an Owner): $oid" }
}
function Sign-In-Others($given) {
  # Everyone besides the owner who may sign in while Entra's allowedPrincipals decides: -AlsoAllow and the admins
  $all = @($given) + @($State.alsoAllow) + @(Admins) | Where-Object { $_ } | ForEach-Object { "$_".Trim().ToLower() }
  return ,@($all | Where-Object { $_ -ne (Owner) } | Select-Object -Unique)
}
if ($OwnerObjectId) {
  $new = Resolve-User $OwnerObjectId
  $old = Owner
  if ($old -ne $new) {
    Set-Prop $State 'ownerObjectId' $new
    Set-Prop $State 'adminObjectIds' @($State.adminObjectIds | Where-Object { $_ -and "$_".ToLower() -ne $new })    # the owner is never also an admin
    if ($old) { Add-Admin $old }
    Save-State $State
    Write-Host "Owner of Alice: $new (was $(if ($old) { $old } else { 'not set' })). Remembered. -Step users gives it Alice.Owner; -Step apps puts the fallback live." -ForegroundColor Green
  }
} elseif (-not (Owner)) {
  Set-Prop $State 'ownerObjectId' "$Me".Trim().ToLower(); Save-State $State
  Write-Host "Owner of Alice was not set: you ($Me), remembered. Change it with -OwnerObjectId." -ForegroundColor Yellow
}
Write-Host "Owner of Alice: $(Owner)$(if (@(Admins).Count) { '; admins: ' + ((Admins) -join ', ') })"
Write-Host "Subscription $SubscriptionId, tenant $Tenant, resource group $ResourceGroup ($Location), you: $Me"

function Ensure-DatabaseHost {
  # main.bicep is never deployed with an empty databaseHost once a database server exists: not set = the address of the
  # resource group's own server (the one Alice uses), read from Azure; the step stops if it cannot be read.
  if ("$($State.databaseHost)".Trim()) { return }
  & $StatePy $StateHelper database-host --resource-group $ResourceGroup --file $StateFile | Out-Host
  if ($LASTEXITCODE -ne 0) { throw 'Stopped before deploying: the database server Alice uses is not known (see above). Nothing was changed.' }
  $h = "$((Load-State).databaseHost)".Trim()
  if ($h) { Set-Prop $State 'databaseHost' $h; Save-State $State }
}

function Deploy($stage, $extra) {
  Ensure-DatabaseHost
  $kv = $State.keyVault
  $pw = if ($kv -and (Kv-Has $kv 'pg-admin-password')) { Kv-Get $kv 'pg-admin-password' } elseif ($State.pendingPassword) { $State.pendingPassword } else { New-Password }
  if (-not $kv) { Set-Prop $State 'pendingPassword' $pw; Save-State $State }   # kept only until it is in Key Vault
  $values = @{ stage = $stage; pgAdminPassword = $pw; deployerObjectId = $Me; ownerObjectId = (Owner); location = $Location }
  # Backups (-Step backup) are remembered, so every step that redeploys keeps them exactly as they are
  foreach ($k in 'pgBackupRetentionDays', 'filesBackupDays', 'offsiteKeepDays', 'offsiteSoftDeleteDays') { if ($State.$k) { $values[$k] = [int]$State.$k } }
  if ($State.pgGeoBackup) { $values['pgGeoRedundantBackup'] = $true }
  if ($State.databaseHost) { $values['databaseHost'] = "$($State.databaseHost)" }
  if ($State.useAppRoles) { $values['useAppRoles'] = $true }     # -Step users -UseAppRoles on: kept by every later step
  # Temple's local model (-Step localmodel): kept by every later step; switched off = parked at zero replicas
  if ($State.localModel) { $values['localModel'] = $true }
  elseif ($State.localModelParked) { $values['localModelParked'] = $true }
  if ($State.localModelName) { $values['localModelName'] = "$($State.localModelName)" }
  if ($State.backup) {
    $values['backup'] = $true; $values['backupNotify'] = "$($State.backupNotify)"
    $values['lockResourceGroup'] = -not $State.noLock; $values['offsiteImmutabilityLocked'] = [bool]$State.offsiteImmutabilityLocked
  }
  foreach ($k in $extra.Keys) { $values[$k] = $extra[$k] }
  # Whoever deploys, the owner is ownerObjectId, and the admins keep signing in (allowedPrincipals) and reaching alice-mcp
  if ($values.ContainsKey('allowedUserObjectIds')) { $values['allowedUserObjectIds'] = Sign-In-Others $values['allowedUserObjectIds'] }
  if ($values.ContainsKey('extAllowedUsers') -and -not $ExtAllowedUsers) {
    $values['extAllowedUsers'] = (@((Owner)) + @("$($values['extAllowedUsers'])" -split ',') + @(Admins) | ForEach-Object { "$_".Trim().ToLower() } | Where-Object { $_ } | Select-Object -Unique) -join ','
  }
  $doc = @{ '$schema' = 'https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#'; contentVersion = '1.0.0.0'; parameters = @{} }
  foreach ($k in $values.Keys) { $doc.parameters[$k] = @{ value = $values[$k] } }
  $pfile = New-TemporaryFile                     # a parameters file: no quoting problems, and the password is not on the command line
  try {
    [IO.File]::WriteAllText($pfile, ($doc | ConvertTo-Json -Depth 6))
    $out = AzCli deployment group create -g $ResourceGroup -f $Template -n ('alice-' + $stage) --parameters ('@' + $pfile) --query properties.outputs -o json | ConvertFrom-Json
  } finally { Remove-Item $pfile -Force -ErrorAction SilentlyContinue }
  foreach ($p in 'acrName', 'acrLoginServer', 'keyVaultName', 'storageAccount', 'shareName', 'environmentDomain', 'webUrl', 'mcpUrl', 'postgresServer', 'offsiteAccount', 'backupVault') {
    if ($out.$p) { Set-Prop $State $p $out.$p.value }
  }
  Set-Prop $State 'keyVault' $State.keyVaultName
  if (-not (Kv-Has $State.keyVault 'pg-admin-password')) { Kv-Set $State.keyVault 'pg-admin-password' $pw }
  if ($State.pendingPassword) { $State.PSObject.Properties.Remove('pendingPassword') }
  Save-State $State
  if ($State.postgresServer) { Ensure-DatabaseHost }     # the first -Step infra has just created the server: name it now
}

function Grant-MailSend($principalId, $label) {
  # Microsoft Graph application permission Mail.Send for a managed identity (no password or secret)
  $graphSp = AzCli ad sp show --id '00000003-0000-0000-c000-000000000000' --query id -o tsv
  $mailSend = 'b633e1c5-b582-4048-a93e-9f11b44c7e96'
  $have = AzCli rest --method GET --uri "https://graph.microsoft.com/v1.0/servicePrincipals/$principalId/appRoleAssignments" -o json | ConvertFrom-Json
  if (@($have.value) | Where-Object { $_.appRoleId -eq $mailSend -and $_.resourceId -eq $graphSp }) { Write-Host "$label already has Mail.Send."; return }
  $tmp = New-TemporaryFile
  try {
    [IO.File]::WriteAllText($tmp, (ConvertTo-Json -InputObject @{ principalId = $principalId; resourceId = $graphSp; appRoleId = $mailSend } -Compress))
    AzCli rest --method POST --uri "https://graph.microsoft.com/v1.0/servicePrincipals/$principalId/appRoleAssignments" --headers 'Content-Type=application/json' --body "@$tmp" | Out-Null
  } finally { Remove-Item $tmp -Force -ErrorAction SilentlyContinue }
  Write-Host "$label can now send mail (Microsoft Graph Mail.Send)."
}

function Image-Ref {
  # A freshly built image (from -Step image) goes out once; otherwise keep the image that is LIVE now, so re-running a
  # step never rolls back a version the pipeline deployed and you promoted.
  if ($State.imageFresh -and $State.image) { return $State.image }
  $live = AzTry containerapp revision list -n alice-web -g $ResourceGroup --query 'max_by([?properties.active], &properties.trafficWeight).properties.template.containers[0].image' -o tsv
  if ($live) { return "$live".Trim() }
  if (-not $State.image) { throw 'No image yet: run -Step image first.' }
  return $State.image
}
function Key-Names {
  $map = @{}
  foreach ($k in @('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'XAI_API_KEY', 'ELEVENLABS_API_KEY', 'ALICE_TWELVEDATA_KEY')) {
    $n = $k.ToLower().Replace('_', '-')
    if (Kv-Has $State.keyVault $n) { $map[$k] = $n }
  }
  return $map
}

if (Want 'infra') {
  Say 'Infrastructure (about 10-15 minutes the first time)'
  foreach ($ns in @('Microsoft.App', 'Microsoft.DBforPostgreSQL', 'Microsoft.ContainerRegistry', 'Microsoft.KeyVault',
                    'Microsoft.OperationalInsights', 'Microsoft.Storage', 'Microsoft.Network', 'Microsoft.ManagedIdentity')) {
    AzCli provider register --namespace $ns --wait --output none | Out-Null      # once per subscription; quick if already done
  }
  AzCli group create -n $ResourceGroup -l $Location --output none | Out-Null
  Deploy 'infra' @{}
  Write-Host "Registry $($State.acrName), Key Vault $($State.keyVault), database $($State.postgresServer), file share $($State.storageAccount)/$($State.shareName)"
}

if (Want 'secrets') {
  Say 'API keys into Key Vault (typed, never saved on disk; Enter skips)'
  foreach ($k in @('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'XAI_API_KEY', 'ELEVENLABS_API_KEY', 'ALICE_TWELVEDATA_KEY')) {
    $n = $k.ToLower().Replace('_', '-')
    if (Kv-Has $State.keyVault $n) { Write-Host "$k already stored."; continue }
    $sec = Read-Host -AsSecureString "Paste $k"
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec))
    if ($plain) { Kv-Set $State.keyVault $n $plain; Write-Host "$k stored." } else { Write-Host "$k skipped." }
    $plain = $null
  }
}

if (Want 'image') {
  Say 'Container image (built in Azure Container Registry)'
  Push-Location $Root
  try {
    # Build from the COMMITTED code only (git archive): .env, data\ and Documents\ are never committed, so they can never
    # be uploaded. (az acr build's own .dockerignore handling ignores rules ending in "/", so it uploaded data\ once.)
    $tag = (& git rev-parse --short HEAD).Trim()
    if (& git status --porcelain --untracked-files=no) { Write-Host 'Note: uncommitted edits are NOT in this image; commit and run this step again to include them.' -ForegroundColor Yellow }
    $src = Join-Path ([IO.Path]::GetTempPath()) ('alice-src-' + $tag); $zip = $src + '.zip'
    Remove-Item $src, $zip -Recurse -Force -ErrorAction SilentlyContinue
    & git archive --format=zip -o $zip HEAD; if ($LASTEXITCODE -ne 0) { throw 'git archive failed.' }
    Expand-Archive -Path $zip -DestinationPath $src
    try {
      Write-Host "Building in Azure from commit $tag (about 5-10 minutes; the log is not streamed: az crashes printing it on the Windows console)..."
      $status = AzCli acr build --registry $State.acrName --image ("alice:" + $tag) --file Dockerfile --build-arg ("ALICE_VERSION=" + $tag) --build-arg ("ALICE_BUILT=" + (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")) $src --no-logs --query status -o tsv
    } finally { Remove-Item $src, $zip -Recurse -Force -ErrorAction SilentlyContinue }
    if ("$status".Trim() -ne 'Succeeded') {
      Write-Host "The build did not succeed ($status). See its log with:  az acr task list-runs -r $($State.acrName) --top 1 -o table   then   az acr task logs -r $($State.acrName) --run-id <RUN ID>" -ForegroundColor Yellow
      throw 'Image build failed.'
    }
    Set-Prop $State 'image' ($State.acrLoginServer + '/alice:' + $tag); Set-Prop $State 'imageFresh' $true; Save-State $State
    Write-Host "Image $($State.image)"
  } finally { Pop-Location }
}

if (Want 'files') {
  Say 'Documents, images and the database copy to the file share'
  $running = $false
  try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 3 http://127.0.0.1:8000/ | Out-Null; $running = $true } catch { }
  if ($running) { throw 'Alice is still running on this PC. Quit it from the tray (Quit (stops servers)) so the database is not changing, then run this step again.' }
  $key = AzCli storage account keys list -g $ResourceGroup -n $State.storageAccount --query '[0].value' -o tsv
  $common = @('--account-name', $State.storageAccount, '--account-key', $key, '--output', 'none')
  foreach ($d in @('Documents', 'data', 'data/images', 'migrate')) { AzTry storage directory create --share-name $State.shareName --name $d @common | Out-Null }
  if (Test-Path (Join-Path $Root 'Documents')) { AzCli storage file upload-batch --destination $State.shareName --destination-path Documents --source (Join-Path $Root 'Documents') @common | Out-Null; Write-Host 'Documents copied.' }
  if (Test-Path (Join-Path $Root 'data\images')) { AzCli storage file upload-batch --destination $State.shareName --destination-path data/images --source (Join-Path $Root 'data\images') @common | Out-Null; Write-Host 'Generated images copied.' }
  AzCli storage file upload --share-name $State.shareName --path migrate/substrate.db --source (Join-Path $Root 'data\substrate.db') @common | Out-Null
  Write-Host 'Database copy uploaded for the migration (it is not used by the apps; delete it from the share after cut-over).'
}

function Run-Job($name) {
  $exec = AzCli containerapp job start -n $name -g $ResourceGroup --query name -o tsv
  Write-Host "Started $name ($exec). Waiting..."
  for ($i = 0; $i -lt 120; $i++) {
    Start-Sleep -Seconds 10
    $st = AzCli containerapp job execution show -n $name -g $ResourceGroup --job-execution-name $exec --query properties.status -o tsv
    if ($st -in @('Succeeded', 'Failed', 'Stopped')) { break }
  }
  Write-Host "$name finished: $st"
  # No log fetch here: 'az containerapp job logs show' hangs once the job's container has gone. The job's exit status is
  # the answer (the migration exits non-zero on any mismatch). To read the log: portal > $name > Execution history > Console logs.
  if ($st -ne 'Succeeded') { Write-Host "Log: Azure portal > Container Apps jobs > $name > Execution history > $exec > Console logs" -ForegroundColor Yellow }
  return "$st"
}

if (Want 'migrate') {
  Say 'Database migration: dry run first'
  Deploy 'migrate' @{ image = (Image-Ref) }
  $st = Run-Job 'alice-migrate-check'
  if ($st -ne 'Succeeded') { throw 'The dry run did not succeed. Nothing was copied. Check the log above (or the job in the portal).' }
  Write-Host 'Dry run passed: every table matched (it fails on any difference). Nothing has been copied yet.' -ForegroundColor Green
  $ok = Read-Host 'Type yes to copy for real'
  if ($ok -ne 'yes') { Write-Host 'Stopped before copying. Run -Step migrate again when ready.'; return }
  $st = Run-Job 'alice-migrate-apply'
  if ($st -ne 'Succeeded') { throw 'The copy did not succeed; the transaction was rolled back. Check the log.' }
}

if (Want 'signin') {
  Say 'Web sign-in (Entra): only you'
  if (-not $State.environmentDomain) { throw 'Run -Step infra first.' }
  $redirect = 'https://alice-web.' + $State.environmentDomain + '/.auth/login/aad/callback'
  if (-not $State.webAuthClientId) {
    $app = AzCli ad app create --display-name 'Alice web sign-in' --sign-in-audience AzureADMyOrg --web-redirect-uris $redirect --enable-id-token-issuance true --query appId -o tsv
    AzTry ad sp create --id $app --output none
    Set-Prop $State 'webAuthClientId' $app; Save-State $State
  }
  $secret = AzCli ad app credential reset --id $State.webAuthClientId --display-name 'container-apps-sign-in' --years 1 --append --query password -o tsv
  Kv-Set $State.keyVault 'web-auth-secret' $secret
  $secret = $null
  Write-Host "App registration $($State.webAuthClientId); its secret is in Key Vault (renew yearly: run -Step signin again)."
}

if (Want 'apps') {
  Say 'Apps: alice-web and alice-mcp'
  if (-not $State.webAuthClientId) { throw 'Run -Step signin first: the web app must never start without sign-in.' }
  # Remembered between runs, so a later -Step apps keeps them without retyping
  if ($ExtAppId) { Set-Prop $State 'extAppId' $ExtAppId }
  if ($ExtCallers) { Set-Prop $State 'extCallers' $ExtCallers }
  if (-not $State.extAppId -or -not $State.extCallers) { throw 'Give -ExtAppId (the Alice API app registration) and -ExtCallers (e.g. "<copilot app id>=Microsoft Copilot:copilot"), the same values as ALICE_EXT_APP_ID and ALICE_EXT_CALLERS on the PC.' }
  $also = Add-AlsoAllow
  if ($CustomDomain) { Set-Prop $State 'customDomain' $CustomDomain.Trim().ToLower() }
  $certId = ''
  if ($State.customDomain) {
    $envName = AzCli containerapp env list -g $ResourceGroup --query '[0].name' -o tsv
    $certId = AzCli containerapp env certificate list -g $ResourceGroup -n $envName --managed-certificates-only --query "[?properties.subjectName=='$($State.customDomain)'].id | [0]" -o tsv
    if (-not $certId) { throw "No managed certificate for $($State.customDomain) yet: bind it once first (az containerapp hostname bind ...)." }
    $redirects = @("$($State.webUrl)/.auth/login/aad/callback", "https://$($State.customDomain)/.auth/login/aad/callback")
    if ($State.demoWebUrl) { $redirects += "$($State.demoWebUrl)/.auth/login/aad/callback" }     # keep the demo Alice's sign-in working
    AzCli ad app update --id $State.webAuthClientId --web-redirect-uris @redirects | Out-Null
  }
  Save-State $State
  $users = if ($ExtAllowedUsers) { $ExtAllowedUsers } else { (@($Me) + $also | Select-Object -Unique) -join ',' }
  Deploy 'apps' @{ image = (Image-Ref); webAuthClientId = $State.webAuthClientId; keyVaultSecretNames = (Key-Names)
                   extAppId = $State.extAppId; extAllowedUsers = $users; extCallers = $State.extCallers; extAudiences = (Audiences); mailFrom = "$($State.mailFrom)"; publicUrl = (Public-Url)
                   allowedUserObjectIds = $also; customDomain = "$($State.customDomain)"; customDomainCertificateId = "$certId"
                   connectorClientId = "$($State.connectorClientId)" }
  if ($State.imageFresh) { $State.PSObject.Properties.Remove('imageFresh'); Save-State $State }
  if ($State.customDomain) { Write-Host "Also at: https://$($State.customDomain)" }
  Write-Host "Web:  $($State.webUrl)"
  Write-Host "MCP:  $($State.mcpUrl)/mcp   (the Base URL for Copilot's sign-on registration; then -Step copilot)"
}

if (Want 'users') {
  Say 'People and roles: Alice.Owner, Alice.Admin, Alice.Member'
  if (-not $State.webAuthClientId) { throw 'Run -Step signin first (the web sign-in app registration).' }
  function Retry($what, [scriptblock]$do) {
    for ($i = 1; $i -le 12; $i++) { try { return (& $do) } catch { if ($i -eq 12) { throw "$what failed: $_" }; Start-Sleep -Seconds 10 } }
  }
  # The roles' JSON is built by deploy\azure_state.py (app-roles), not by PowerShell: Windows PowerShell 5.1 does not unroll a
  # JSON array from ConvertFrom-Json, so the app's current roles came back wrapped in another array and Graph refused the
  # update ("StartArray ... PrimitiveValue expected"). The helper keeps the app's other roles, keeps the ID an Alice role
  # already has (else a fixed one), sends only the fields Graph accepts, every one a single value except allowedMemberTypes.
  $roles = @([ordered]@{ value = 'Alice.Owner'; id = '' }, [ordered]@{ value = 'Alice.Admin'; id = '' }, [ordered]@{ value = 'Alice.Member'; id = '' })
  function Add-Roles($appId, $label) {
    $existing = New-TemporaryFile; $send = New-TemporaryFile
    try {
      [IO.File]::WriteAllText($existing, ((AzCli ad app show --id $appId --query 'appRoles' -o json) -join "`n"))
      & $StatePy $StateHelper app-roles --existing $existing --out $send | Out-Host
      if ($LASTEXITCODE -ne 0) { throw "Could not work out the app roles for $label (see above). Nothing was changed." }
      try { AzCli ad app update --id $appId --app-roles "@$send" | Out-Null }
      catch {
        Write-Host "The app roles sent to $label ($appId) were:" -ForegroundColor Yellow
        Write-Host ([IO.File]::ReadAllText($send))
        throw
      }
    } finally { Remove-Item $existing, $send -ErrorAction SilentlyContinue }
    Write-Host "$label`: roles Alice.Owner, Alice.Admin, Alice.Member"
  }
  Add-Roles $State.webAuthClientId 'Alice web sign-in'
  foreach ($r in $roles) {        # the IDs the web sign-in app really has (an existing role keeps its own)
    $r.id = "$(AzCli ad app show --id $State.webAuthClientId --query "appRoles[?value=='$($r.value)'].id | [0]" -o tsv)".Trim()
    if (-not $r.id) { throw "The web sign-in app has no $($r.value) role after the update. Nothing was assigned." }
  }
  if ($State.connectorClientId) { Add-Roles $State.connectorClientId 'Alice connector sign-in' }
  # The web sign-in's enterprise application (service principal)
  $sp = AzTry ad sp show --id $State.webAuthClientId --query id -o tsv
  if (-not $sp) { $sp = Retry 'Creating the web sign-in service principal' { AzCli ad sp create --id $State.webAuthClientId --query id -o tsv } }
  # Entra decides who is an owner. Alice.Owner for the owner (ownerObjectId) FIRST; then Alice.Admin for the admins (you, if you
  # are not the owner, -AdminObjectIds, a previous owner), taking Alice.Owner away from them; Alice.Member for anyone else in
  # -AlsoAllow, so nobody who gets in today is locked out by Assignment required or the switch. The owner's own Alice.Owner is
  # never removed, so there is always at least one Owner.
  foreach ($a in ($AdminObjectIds -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ })) { Add-Admin (Resolve-User $a) }
  Add-Admin $Me
  Save-State $State
  if (-not (Owner)) { throw 'No owner of Alice set: give -OwnerObjectId. Nothing was assigned.' }
  # The same assignments on every app a person signs in to Alice through: the web sign-in and, when it exists, the connector
  # sign-in (Claude and ChatGPT). Lesson (10 Oct 2026): the connector app had only the admin account assigned, so the owner's
  # connector calls signed in as the admin account. Each app has its own role IDs (an existing role keeps its own).
  function Assign-People($appId, $spId, $label) {
    $ids = @{}
    foreach ($r in $roles) {
      $ids[$r.value] = "$(AzCli ad app show --id $appId --query "appRoles[?value=='$($r.value)'].id | [0]" -o tsv)".Trim()
      if (-not $ids[$r.value]) { throw "$label has no $($r.value) role after the update. Nothing was assigned there." }
    }
    $assignedUrl = "https://graph.microsoft.com/v1.0/servicePrincipals/$spId/appRoleAssignedTo"
    function Assignments { return @((AzCli rest --method GET --url $assignedUrl -o json | ConvertFrom-Json).value) }
    function Assign($o, $role, $why) {
      if (@(Assignments | Where-Object { $_.principalId -eq $o -and $_.appRoleId -eq $ids[$role] }).Count) { Write-Host "$label`: already $role`: $o ($why)"; return }
      $tmp = New-TemporaryFile
      try {
        [IO.File]::WriteAllText($tmp, (@{ principalId = $o; resourceId = $spId; appRoleId = $ids[$role] } | ConvertTo-Json -Compress))
        Retry "Assigning $o $role on $label" { AzCli rest --method POST --url $assignedUrl --headers 'Content-Type=application/json' --body "@$tmp" --output none | Out-Null }
      } finally { Remove-Item $tmp -ErrorAction SilentlyContinue }
      Write-Host "$label`: assigned $role`: $o ($why)"
    }
    Assign (Owner) 'Alice.Owner' 'the owner of Alice'
    if (-not @(Assignments | Where-Object { $_.principalId -eq (Owner) -and $_.appRoleId -eq $ids['Alice.Owner'] }).Count) { throw "The owner does not hold Alice.Owner on $label yet: nothing else was changed there. Run -Step users again in a minute." }
    foreach ($o in (Admins)) {
      Assign $o 'Alice.Admin' 'admin'
      foreach ($x in @(Assignments | Where-Object { $_.principalId -eq $o -and $_.appRoleId -eq $ids['Alice.Owner'] })) {
        Retry "Taking Alice.Owner from $o on $label" { AzCli rest --method DELETE --url "$assignedUrl/$($x.id)" --output none | Out-Null }
        Write-Host "$label`: Alice.Owner taken away from $o (an admin, not an owner)."
      }
    }
    foreach ($o in (Sign-In-Others @())) { if ((Admins) -notcontains $o) { Assign $o 'Alice.Member' 'allowed to sign in: raise it in Entra if needed' } }
    $others = @(Assignments | Where-Object { $_.appRoleId -eq $ids['Alice.Owner'] -and $_.principalId -ne (Owner) } | ForEach-Object { $_.principalId })
    if ($others) { Write-Host "$label`: also owners, assigned in Entra (anyone with Alice.Owner is an owner of Alice): $($others -join ', ')" -ForegroundColor Yellow }
  }
  Assign-People $State.webAuthClientId $sp 'Alice web sign-in'
  if ($State.connectorClientId) {
    $csp = AzTry ad sp show --id $State.connectorClientId --query id -o tsv
    if (-not $csp) { $csp = Retry 'Creating the connector sign-in service principal' { AzCli ad sp create --id $State.connectorClientId --query id -o tsv } }
    Assign-People $State.connectorClientId $csp 'Alice connector sign-in'
  }
  # Assignment required on the web sign-in's enterprise application: Entra itself refuses anyone without a role.
  Retry 'Setting Assignment required' { AzCli ad sp update --id $State.webAuthClientId --set appRoleAssignmentRequired=true | Out-Null }
  Write-Host 'Alice web sign-in: Assignment required (Entra refuses anyone without an Alice role).'
  if ($UseAppRoles) {
    Set-Prop $State 'useAppRoles' ($UseAppRoles -eq 'on'); Save-State $State
    if ($UseAppRoles -eq 'on') { Write-Host 'Remembered: app roles decide who gets in. Now run -Step apps to put it live.' -ForegroundColor Green }
    else { Write-Host 'Remembered: back to allowedPrincipals (only you and -AlsoAllow). Now run -Step apps to put it live.' -ForegroundColor Green }
  } elseif (-not $State.useAppRoles) {
    Write-Host 'Not switched yet: Entra still lets in only the accounts it does today. When ready: -Step users -UseAppRoles on, then -Step apps.' -ForegroundColor Yellow
  }
  Write-Host 'Add a person: Entra admin centre > Enterprise applications > Alice web sign-in > Users and groups > Add user/group > a role.'
  Write-Host 'They start with the default Member profile (Chat and their own saved chats); change it on Admin > Users and permissions.'
}

if (Want 'connector') {
  Say 'Claude connector: Alice signs Claude in (through your Entra tenant)'
  if (-not $State.mcpUrl -or -not $State.extAppId) { throw 'Run -Step apps first (it remembers the Alice API app and the MCP address).' }
  function Retry($what, [scriptblock]$do) {
    for ($i = 1; $i -le 12; $i++) { try { return (& $do) } catch { if ($i -eq 12) { throw "$what failed: $_" }; Start-Sleep -Seconds 10 } }
  }
  $callback = "$($State.mcpUrl)/auth/callback"
  if (-not $State.connectorClientId) {
    $cid = AzCli ad app create --display-name 'Alice connector sign-in' --sign-in-audience AzureADMyOrg --web-redirect-uris $callback --query appId -o tsv
    Set-Prop $State 'connectorClientId' $cid; Save-State $State
  }
  $cid = $State.connectorClientId
  AzCli ad app update --id $cid --web-redirect-uris $callback | Out-Null
  if (-not (AzTry ad sp show --id $cid --query id -o tsv)) { Retry 'Creating the connector service principal' { AzCli ad sp create --id $cid --output none | Out-Null } }
  # It may ask for exactly one thing: Alice's own scope (plus sign-in basics), consented once for the tenant.
  $scopeId = AzCli ad app show --id $State.extAppId --query "api.oauth2PermissionScopes[?value=='access_as_user'].id | [0]" -o tsv
  if (-not $scopeId) { throw 'The Alice API app has no access_as_user scope.' }
  $graph = '00000003-0000-0000-c000-000000000000'
  $access = @(@{ resourceAppId = $State.extAppId; resourceAccess = @(@{ id = $scopeId; type = 'Scope' }) },
              @{ resourceAppId = $graph; resourceAccess = @(@{ id = '37f7f235-527c-4136-accd-4a02d197296e'; type = 'Scope' }, @{ id = '7427e0e9-2fba-42fe-b0c0-848c9e6a8182'; type = 'Scope' }) })   # openid, offline_access
  $tmp = New-TemporaryFile
  try { [IO.File]::WriteAllText($tmp, (ConvertTo-Json -InputObject $access -Depth 5 -Compress)); AzCli ad app update --id $cid --required-resource-accesses "@$tmp" | Out-Null }
  finally { Remove-Item $tmp -ErrorAction SilentlyContinue }
  Retry 'Granting consent for the tenant' { AzCli ad app permission admin-consent --id $cid --output none | Out-Null }
  if (-not (Kv-Has $State.keyVault 'connector-secret')) {
    $secret = AzCli ad app credential reset --id $cid --append --display-name 'alice-connector' --years 2 --query password -o tsv
    Kv-Set $State.keyVault 'connector-secret' $secret; $secret = $null
  }
  if (-not (Kv-Has $State.keyVault 'connector-key')) {
    $bytes = New-Object byte[] 48; [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    Kv-Set $State.keyVault 'connector-key' ([Convert]::ToBase64String($bytes)); $bytes = $null
  }
  Write-Host "Connector app $cid; its secret and signing key are in Key Vault (renew the secret every 2 years: delete connector-secret and run this step)."
  Write-Host 'Now updating alice-mcp...'
  $users = (@($Me) + @($State.alsoAllow | Where-Object { $_ }) | Select-Object -Unique) -join ','
  $certId = ''
  if ($State.customDomain) {
    $envName = AzCli containerapp env list -g $ResourceGroup --query '[0].name' -o tsv
    $certId = AzCli containerapp env certificate list -g $ResourceGroup -n $envName --managed-certificates-only --query "[?properties.subjectName=='$($State.customDomain)'].id | [0]" -o tsv
  }
  Deploy 'apps' @{ image = (Image-Ref); webAuthClientId = $State.webAuthClientId; keyVaultSecretNames = (Key-Names)
                   extAppId = $State.extAppId; extAllowedUsers = $users; extCallers = $State.extCallers; extAudiences = (Audiences); mailFrom = "$($State.mailFrom)"; publicUrl = (Public-Url)
                   allowedUserObjectIds = @($State.alsoAllow | Where-Object { $_ }); customDomain = "$($State.customDomain)"; customDomainCertificateId = "$certId"
                   connectorClientId = $cid }
  Write-Host ''
  Write-Host 'In Claude: Settings > Connectors > Add custom connector' -ForegroundColor Green
  Write-Host "  Name: Alice     URL: $($State.mcpUrl)/mcp     (leave the OAuth fields empty)" -ForegroundColor Green
}

function Deploy-Demo {
  $users = (@((Owner), $Me) + @(Sign-In-Others @()) | Where-Object { $_ } | Select-Object -Unique) -join ','
  $values = @{ image = (Image-Ref); pgAdminPassword = (Kv-Get $State.keyVault 'pg-admin-password'); ownerObjectId = (Owner); location = $Location
               allowedUserObjectIds = (Sign-In-Others @()); webAuthClientId = $State.webAuthClientId; keyVaultSecretNames = (Key-Names)
               extAppId = $State.extAppId; extAllowedUsers = $users; extCallers = $State.extCallers; extAudiences = (Audiences) }
  $doc = @{ '$schema' = 'https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#'; contentVersion = '1.0.0.0'; parameters = @{} }
  foreach ($k in $values.Keys) { $doc.parameters[$k] = @{ value = $values[$k] } }
  $pfile = New-TemporaryFile
  try {
    [IO.File]::WriteAllText($pfile, ($doc | ConvertTo-Json -Depth 6))
    $out = AzCli deployment group create -g $ResourceGroup -f (Join-Path $Root 'infra\demo.bicep') -n 'alice-demo' --parameters ('@' + $pfile) --query properties.outputs -o json | ConvertFrom-Json
  } finally { Remove-Item $pfile -Force -ErrorAction SilentlyContinue }
  Set-Prop $State 'demoWebUrl' $out.demoWebUrl.value; Set-Prop $State 'demoMcpUrl' $out.demoMcpUrl.value; Save-State $State
}

if (Want 'demo') {
  Say 'The demo Alice (client demos): its own database and apps, nothing shared with live data'
  if (-not $State.webAuthClientId -or -not $State.extAppId -or -not $State.extCallers) { throw 'Run -Step apps first (it remembers the sign-in and the Alice API app).' }
  # its own folders on the share (data and Documents), next to live's but never the same
  $key = AzCli storage account keys list -g $ResourceGroup -n $State.storageAccount --query '[0].value' -o tsv
  foreach ($d in @('demo', 'demo/data', 'demo/data/images', 'demo/Documents')) {
    AzTry storage directory create --share-name $State.shareName --name $d --account-name $State.storageAccount --account-key $key --output none | Out-Null
  }
  # the same sign-in app (only you): add the demo's callback to its addresses, keeping live's
  $demoWeb = 'https://alice-demo-web.' + $State.environmentDomain
  $uris = Json-Array (AzCli ad app show --id $State.webAuthClientId --query 'web.redirectUris' -o json)
  $cb = "$demoWeb/.auth/login/aad/callback"
  if ($uris -notcontains $cb) { $uris += $cb; AzCli ad app update --id $State.webAuthClientId --web-redirect-uris @uris | Out-Null; Write-Host 'Demo address added to the sign-in app.' }
  Deploy-Demo
  Write-Host ''
  Write-Host "Demo Alice:      $($State.demoWebUrl)/admin/demo" -ForegroundColor Green
  Write-Host "Copilot address: $($State.demoMcpUrl)/mcp   (for Copilot: register it in the Teams Developer Portal, then -Step copilot -CopilotDemoAudience ... -CopilotDemoAuthId ...)" -ForegroundColor Green
  Write-Host 'Both scale to zero when idle: open the demo a couple of minutes before you present.'
}

if (Want 'copilot') {
  Say 'Microsoft 365 Copilot: Alice as an agent (Entra single sign-on)'
  if (-not $State.mcpUrl -or -not $State.extAppId -or -not $State.extCallers) { throw 'Run -Step apps first (it remembers the Alice API app and the MCP address).' }
  $tokenStore = 'ab3be6b7-f5df-413d-ac2d-abf1e3fd9c0b'          # Microsoft's Enterprise token store: Copilot gets your token through it
  $aud = @($State.extAudiences | Where-Object { $_ })
  foreach ($a in (($CopilotAudience, $CopilotDemoAudience) -join ',' -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ })) {
    if ($a -notmatch '^api://\S+$') { throw "'$a' is not an Application ID URI (it starts api://). Copy it from the Developer Portal registration." }
    if ($aud -notcontains $a) { $aud += $a }
  }
  if (-not $aud) { throw 'Give -CopilotAudience: the Application ID URI the Teams Developer Portal showed after the Entra SSO registration.' }
  Set-Prop $State 'extAudiences' $aud
  if ($CopilotAuthId) { Set-Prop $State 'copilotAuthId' $CopilotAuthId.Trim() }
  if ($CopilotDemoAuthId) { Set-Prop $State 'copilotDemoAuthId' $CopilotDemoAuthId.Trim() }
  $also = Add-AlsoAllow
  Save-State $State

  # 1. The Alice API app: Teams' consent redirect, the new Application ID URI(s), the token store pre-authorised for access_as_user
  $app = AzCli ad app show --id $State.extAppId -o json | ConvertFrom-Json
  $uris = @($app.identifierUris | Where-Object { $_ })
  $newUris = @($aud | Where-Object { $uris -notcontains $_ })
  if ($newUris) { AzCli ad app update --id $State.extAppId --identifier-uris @($uris + $newUris) | Out-Null; Write-Host "Application ID URI added: $($newUris -join ', ')" }
  $redirect = 'https://teams.microsoft.com/api/platform/v1.0/oAuthConsentRedirect'
  $redirects = @($app.web.redirectUris | Where-Object { $_ })
  if ($redirects -notcontains $redirect) { AzCli ad app update --id $State.extAppId --web-redirect-uris @($redirects + $redirect) | Out-Null; Write-Host 'Teams consent redirect added.' }
  $scope = @($app.api.oauth2PermissionScopes | Where-Object { $_.value -eq 'access_as_user' })[0]
  if (-not $scope) { throw 'The Alice API app has no access_as_user scope.' }
  $pre = @($app.api.preAuthorizedApplications | Where-Object { $_ })
  if (-not ($pre | Where-Object { $_.appId -eq $tokenStore })) {
    $api = $app.api
    $api.preAuthorizedApplications = @($pre + [pscustomobject]@{ appId = $tokenStore; delegatedPermissionIds = @($scope.id) })
    $tmp = New-TemporaryFile
    try {   # the whole api object goes back, so the scope and anything else in it are kept
      [IO.File]::WriteAllText($tmp, (ConvertTo-Json -InputObject @{ api = $api } -Depth 8 -Compress))
      AzCli rest --method PATCH --uri "https://graph.microsoft.com/v1.0/applications/$($app.id)" --headers 'Content-Type=application/json' --body "@$tmp" | Out-Null
    } finally { Remove-Item $tmp -Force -ErrorAction SilentlyContinue }
    Write-Host 'Microsoft token store pre-authorised for access_as_user.'
  }

  # 2. alice-mcp (and the demo's) accept Copilot: the token store as a caller, the new audiences
  if ($State.extCallers -notmatch [regex]::Escape($tokenStore)) {
    Set-Prop $State 'extCallers' ($State.extCallers.TrimEnd(';') + ";$tokenStore=Microsoft Copilot:copilot"); Save-State $State
  }
  Write-Host 'Updating alice-mcp (do not run this while a test-and-deploy run is in progress)...'
  $users = (@($Me) + $also | Select-Object -Unique) -join ','
  $certId = ''
  if ($State.customDomain) {
    $envName = AzCli containerapp env list -g $ResourceGroup --query '[0].name' -o tsv
    $certId = AzCli containerapp env certificate list -g $ResourceGroup -n $envName --managed-certificates-only --query "[?properties.subjectName=='$($State.customDomain)'].id | [0]" -o tsv
  }
  Deploy 'apps' @{ image = (Image-Ref); webAuthClientId = $State.webAuthClientId; keyVaultSecretNames = (Key-Names)
                   extAppId = $State.extAppId; extAllowedUsers = $users; extCallers = $State.extCallers; extAudiences = (Audiences); mailFrom = "$($State.mailFrom)"; publicUrl = (Public-Url)
                   allowedUserObjectIds = $also; customDomain = "$($State.customDomain)"; customDomainCertificateId = "$certId"
                   connectorClientId = "$($State.connectorClientId)" }
  if ($State.demoMcpUrl) { Write-Host 'Updating the demo Alice...'; Deploy-Demo }

  # 3. The app packages to upload in Teams
  $py = Join-Path $Root '.venv\Scripts\python.exe'
  if (-not (Test-Path $py)) { $py = 'python' }
  $dist = Join-Path $Root 'dist'
  $built = @()
  if ($State.copilotAuthId) {
    & $py (Join-Path $Root 'copilot_package.py') --url "$($State.mcpUrl)/mcp" --auth-id $State.copilotAuthId --out (Join-Path $dist 'Alice-Copilot.zip')
    if ($LASTEXITCODE -ne 0) { throw 'Building the Alice package failed (see above).' }; $built += 'Alice-Copilot.zip'
  }
  if ($State.copilotDemoAuthId -and $State.demoMcpUrl) {
    & $py (Join-Path $Root 'copilot_package.py') --url "$($State.demoMcpUrl)/mcp" --auth-id $State.copilotDemoAuthId --demo --out (Join-Path $dist 'Alice-demo-Copilot.zip')
    if ($LASTEXITCODE -ne 0) { throw 'Building the demo package failed (see above).' }; $built += 'Alice-demo-Copilot.zip'
  }
  Write-Host ''
  if ($built) {
    Write-Host "Packages in $dist : $($built -join ', ')" -ForegroundColor Green
    Write-Host 'In Teams: Apps > Manage your apps > Upload an app > Upload a custom app, pick the zip, then Add.' -ForegroundColor Green
    Write-Host 'Then in Microsoft 365 Copilot (signed in with your work account) choose Alice under Agents.' -ForegroundColor Green
  } else { Write-Host 'No package built: give -CopilotAuthId (and -CopilotDemoAuthId for the demo).' -ForegroundColor Yellow }
}

if (Want 'mail') {
  Say 'Email: Alice sends from a mailbox in your tenant (held decisions go to their owner)'
  if (-not $State.webAuthClientId -or -not $State.extAppId) { throw 'Run -Step apps first.' }
  if ($MailFrom) { Set-Prop $State 'mailFrom' $MailFrom.Trim() }
  if (-not ($State.mailFrom -match '^[^@\s]+@[^@\s]+\.[^@\s]+$')) { throw 'Give -MailFrom: the mailbox Alice sends from, e.g. alice@yourdomain (a shared mailbox is fine).' }
  if (-not (AzTry ad user show --id $State.mailFrom --query id -o tsv)) { Write-Host "Note: $($State.mailFrom) was not found as a user; make sure the mailbox (or shared mailbox) exists before Alice sends." -ForegroundColor Yellow }
  $mi = AzCli identity show -g $ResourceGroup -n 'alice-identity' -o json | ConvertFrom-Json
  Grant-MailSend $mi.principalId "Alice's managed identity"
  $drillMi = AzTry identity show -g $ResourceGroup -n 'alice-drill-identity' --query principalId -o tsv
  if ($drillMi) { Grant-MailSend "$drillMi".Trim() "The restore drill's identity" }
  Save-State $State
  Write-Host 'Updating alice-web and alice-mcp (do not run this while a test-and-deploy run is in progress)...'
  $also = @($State.alsoAllow | Where-Object { $_ })
  $users = (@($Me) + $also | Select-Object -Unique) -join ','
  $certId = ''
  if ($State.customDomain) {
    $envName = AzCli containerapp env list -g $ResourceGroup --query '[0].name' -o tsv
    $certId = AzCli containerapp env certificate list -g $ResourceGroup -n $envName --managed-certificates-only --query "[?properties.subjectName=='$($State.customDomain)'].id | [0]" -o tsv
  }
  Deploy 'apps' @{ image = (Image-Ref); webAuthClientId = $State.webAuthClientId; keyVaultSecretNames = (Key-Names)
                   extAppId = $State.extAppId; extAllowedUsers = $users; extCallers = $State.extCallers; extAudiences = (Audiences); mailFrom = "$($State.mailFrom)"; publicUrl = (Public-Url)
                   allowedUserObjectIds = $also; customDomain = "$($State.customDomain)"; customDomainCertificateId = "$certId"
                   connectorClientId = "$($State.connectorClientId)" }
  Write-Host ''
  Write-Host "Alice sends from $($State.mailFrom). Held decisions are emailed to their owner (Actions > Decisions)." -ForegroundColor Green
  Write-Host 'Recommended: limit the permission to that one mailbox (Exchange Online PowerShell, once):' -ForegroundColor Green
  Write-Host "  New-ApplicationAccessPolicy -AppId $($mi.clientId) -PolicyScopeGroupId <a mail-enabled security group holding $($State.mailFrom)> -AccessRight RestrictAccess -Description 'Alice sends only as her own mailbox'"
}

if (Want 'backup') {
  Say 'Backups: file share snapshots, the resource group lock, database backups for 35 days and the nightly off-site copy'
  if (-not $State.webAuthClientId -or -not $State.extAppId -or -not $State.extCallers) { throw 'Run -Step apps first.' }
  AzCli provider register --namespace Microsoft.RecoveryServices --wait --output none | Out-Null
  if ($FilesBackupDays) { if ($FilesBackupDays -lt 1 -or $FilesBackupDays -gt 200) { throw '-FilesBackupDays must be 1 to 200.' }; Set-Prop $State 'filesBackupDays' $FilesBackupDays }
  if ($OffsiteKeepDays) { if ($OffsiteKeepDays -lt 1 -or $OffsiteKeepDays -gt 365) { throw '-OffsiteKeepDays must be 1 to 365.' }; Set-Prop $State 'offsiteKeepDays' $OffsiteKeepDays }
  if ($OffsiteSoftDeleteDays) { if ($OffsiteSoftDeleteDays -lt 1 -or $OffsiteSoftDeleteDays -gt 365) { throw '-OffsiteSoftDeleteDays must be 1 to 365.' }; Set-Prop $State 'offsiteSoftDeleteDays' $OffsiteSoftDeleteDays }
  if ($PgBackupDays) { if ($PgBackupDays -lt 7 -or $PgBackupDays -gt 35) { throw '-PgBackupDays must be 7 to 35 (Azure''s limits).' }; Set-Prop $State 'pgBackupRetentionDays' $PgBackupDays }
  if ($PgGeoBackup) {
    # Azure only lets you choose geo-redundant backups when a server is CREATED; an existing server cannot switch it on.
    $geo = AzCli postgres flexible-server show -g $ResourceGroup -n $State.postgresServer --query backup.geoRedundantBackup -o tsv
    if ("$geo".Trim() -ne 'Enabled') { throw "The database server $($State.postgresServer) was created without geo-redundant backups, and Azure cannot switch them on afterwards. It needs a new server (a point-in-time restore into a new server with geo-redundant backup on, then Alice moved to it): a planned change, not this step. Nothing was changed." }
    Set-Prop $State 'pgGeoBackup' $true
  }
  if ($BackupNotify) { Set-Prop $State 'backupNotify' $BackupNotify.Trim() }
  if (-not $State.backupNotify) {
    $mail = AzTry ad signed-in-user show --query mail -o tsv
    if (-not "$mail".Trim()) { $mail = AzTry ad signed-in-user show --query userPrincipalName -o tsv }
    Set-Prop $State 'backupNotify' "$mail".Trim()
  }
  if (-not ($State.backupNotify -match '^[^@\s]+@[^@\s]+\.[^@\s]+$')) { throw 'Give -BackupNotify: the address to email when a nightly backup fails.' }
  Set-Prop $State 'noLock' ([bool]$NoLock)
  Set-Prop $State 'backup' $true
  Save-State $State
  if (-not $State.mailFrom) { Write-Host 'Note: email is not set up yet (-Step mail), so a failed backup shows on Home and the Backup page but is not emailed.' -ForegroundColor Yellow }
  # The restore drill's own resource group: throwaway resources only, never this one, and no lock on it
  AzCli group create -n "$ResourceGroup-drill" -l $Location --tags purpose=alice-restore-drill --output none | Out-Null
  Write-Host 'Deploying (do not run this while a test-and-deploy run is in progress)...'
  $also = @($State.alsoAllow | Where-Object { $_ })
  $users = (@($Me) + $also | Select-Object -Unique) -join ','
  $certId = ''
  if ($State.customDomain) {
    $envName = AzCli containerapp env list -g $ResourceGroup --query '[0].name' -o tsv
    $certId = AzCli containerapp env certificate list -g $ResourceGroup -n $envName --managed-certificates-only --query "[?properties.subjectName=='$($State.customDomain)'].id | [0]" -o tsv
  }
  Deploy 'apps' @{ image = (Image-Ref); webAuthClientId = $State.webAuthClientId; keyVaultSecretNames = (Key-Names)
                   extAppId = $State.extAppId; extAllowedUsers = $users; extCallers = $State.extCallers; extAudiences = (Audiences); mailFrom = "$($State.mailFrom)"; publicUrl = (Public-Url)
                   allowedUserObjectIds = $also; customDomain = "$($State.customDomain)"; customDomainCertificateId = "$certId"
                   connectorClientId = "$($State.connectorClientId)" }
  if ($LockImmutability -and -not $State.offsiteImmutabilityLocked) {
    Write-Host "Locking the immutability policy is permanent: no one (you included) can then shorten it or delete a copy before it is $(if ($State.offsiteKeepDays) { $State.offsiteKeepDays } else { 35 }) days old, and the off-site account cannot be deleted while it holds copies." -ForegroundColor Yellow
    $ok = Read-Host 'Type LOCK to lock it for good'
    if ($ok -eq 'LOCK') {
      $etag = AzCli storage container immutability-policy show -g $ResourceGroup --account-name $State.offsiteAccount -c alice-offsite --query etag -o tsv
      AzCli storage container immutability-policy lock -g $ResourceGroup --account-name $State.offsiteAccount -c alice-offsite --if-match "$etag".Trim() --output none | Out-Null
      Set-Prop $State 'offsiteImmutabilityLocked' $true; Save-State $State
      Write-Host 'Immutability policy locked. (The Backup page shows it as locked after the next setup step.)'
    } else { Write-Host 'Not locked.' }
  }
  if ($State.mailFrom) {
    $drillMi = AzTry identity show -g $ResourceGroup -n 'alice-drill-identity' --query principalId -o tsv
    if ($drillMi) { Grant-MailSend "$drillMi".Trim() "The restore drill's identity" }
  }
  Write-Host 'Taking the first off-site copy now (a few minutes)...'
  $st = Run-Job 'alice-backup'
  if ($st -eq 'Succeeded') { Write-Host 'First off-site copy done.' -ForegroundColor Green } else { Write-Host 'The first off-site copy did not succeed: see the Backup page in Alice and the job''s log (above).' -ForegroundColor Yellow }
  Write-Host ''
  Write-Host "File share snapshots: vault $($State.backupVault), daily, kept $(if ($State.filesBackupDays) { $State.filesBackupDays } else { 30 }) days" -ForegroundColor Green
  Write-Host "Database backups: kept $(if ($State.pgBackupRetentionDays) { $State.pgBackupRetentionDays } else { 35 }) days (point-in-time restore)" -ForegroundColor Green
  Write-Host "Off-site copy: storage account $($State.offsiteAccount) (UK West), every night at 02:00 UK time; failures emailed to $($State.backupNotify)" -ForegroundColor Green
  if ($State.noLock) { Write-Host 'Resource group lock: off (-NoLock).' -ForegroundColor Yellow }
  else { Write-Host "Resource group lock: alice-do-not-delete. To lift it deliberately: az lock delete --name alice-do-not-delete --resource-group $ResourceGroup   then -Step backup -NoLock" -ForegroundColor Green }
  Write-Host "Restore drill: resource group $ResourceGroup-drill (throwaway resources only). Start one from the Backup page, or the Restore drill workflow." -ForegroundColor Green
  Write-Host "Backup page: $(Public-Url)/admin/backup"
}

if (Want 'localmodel') {
  Say "Temple's local model: screening and categories inside Alice's own environment (internal ingress only)"
  if (-not $State.webAuthClientId -or -not $State.extAppId -or -not $State.extCallers) { throw 'Run -Step apps first.' }
  if (-not $LocalModel) { throw 'Say -LocalModel on or -LocalModel off.' }
  if ($LocalModelName) {
    if ($LocalModelName -notmatch '^[a-z0-9][a-z0-9._-]*(:[a-z0-9._-]+)?$') { throw '-LocalModelName must be an Ollama model tag such as qwen3:4b.' }
    Set-Prop $State 'localModelName' $LocalModelName
  }
  if (-not $State.localModelName) { Set-Prop $State 'localModelName' 'qwen3:4b' }
  if ($LocalModel -eq 'on') { Set-Prop $State 'localModel' $true; Set-Prop $State 'localModelParked' $false }
  else { $was = [bool]$State.localModel -or [bool]$State.localModelParked; Set-Prop $State 'localModel' $false; Set-Prop $State 'localModelParked' $was }
  Save-State $State
  Write-Host 'Deploying (do not run this while a test-and-deploy run is in progress)...'
  $also = @($State.alsoAllow | Where-Object { $_ })
  $users = (@($Me) + $also | Select-Object -Unique) -join ','
  $certId = ''
  if ($State.customDomain) {
    $envName = AzCli containerapp env list -g $ResourceGroup --query '[0].name' -o tsv
    $certId = AzCli containerapp env certificate list -g $ResourceGroup -n $envName --managed-certificates-only --query "[?properties.subjectName=='$($State.customDomain)'].id | [0]" -o tsv
  }
  Deploy 'apps' @{ image = (Image-Ref); webAuthClientId = $State.webAuthClientId; keyVaultSecretNames = (Key-Names)
                   extAppId = $State.extAppId; extAllowedUsers = $users; extCallers = $State.extCallers; extAudiences = (Audiences); mailFrom = "$($State.mailFrom)"; publicUrl = (Public-Url)
                   allowedUserObjectIds = $also; customDomain = "$($State.customDomain)"; customDomainCertificateId = "$certId"
                   connectorClientId = "$($State.connectorClientId)" }
  if ($State.localModel) {
    Write-Host ''
    Write-Host "Local model: alice-local-model, serving $($State.localModelName), internal ingress only. It downloads the model when it first starts (a few minutes)." -ForegroundColor Green
    Write-Host "In Alice: Agents > Temple's model for screening and categories > Run the evaluation, then choose Local if you are happy with the scores." -ForegroundColor Green
  } else {
    Write-Host 'Local model switched off: Alice no longer uses it (anything set to Local goes back to waiting until you choose Cloud), and it is scaled to zero.' -ForegroundColor Green
    Write-Host 'In Alice: Agents > Temple''s model for screening and categories > Cloud.' -ForegroundColor Yellow
  }
}

if (Want 'recover') {
  Say 'Recovery: load a nightly off-site copy into this NEW, EMPTY Alice (docs/restore.md part C)'
  if ($State.backup) { throw "-Step recover only runs in a new resource group: $ResourceGroup has backups switched on, so it is a live Alice. Use a fresh clone and a new -ResourceGroup." }
  if (-not $State.keyVault -or -not $State.image) { throw 'Run -Step infra, -Step secrets and -Step image for this new resource group first.' }
  if ($State.webUrl) { Write-Host 'Note: the apps already ran here, so the database may hold tables; the restore refuses a database that is not empty.' -ForegroundColor Yellow }
  if (-not $RecoverFrom) { throw 'Give -RecoverFrom: the off-site storage account (its name ends in offsite).' }
  $acct = $RecoverFrom.Trim().ToLower()
  $acctId = AzCli storage account list --query "[?name=='$acct'].id | [0]" -o tsv
  if (-not $acctId) { throw "No storage account $acct in this subscription." }
  $prefix = if ($RecoverCopy) { $RecoverCopy.Trim().Trim('/') + '/' } else { '' }
  $names = @(AzCli storage blob list --account-name $acct -c alice-offsite --auth-mode login --prefix $prefix --query "[?ends_with(name,'-manifest.json')].name" -o tsv)
  $manifest = ($names | Where-Object { $_ } | Sort-Object | Select-Object -Last 1)
  if (-not $manifest) { throw "No off-site copy found in $acct/alice-offsite$(if ($prefix) { " under $prefix" })." }
  Write-Host "Restoring the copy $manifest"
  $mi = AzCli identity show -g $ResourceGroup -n 'alice-identity' --query principalId -o tsv
  $has = AzTry role assignment list --assignee "$mi".Trim() --role 'Storage Blob Data Reader' --scope $acctId --query '[0].id' -o tsv
  if (-not $has) { AzCli role assignment create --assignee-object-id "$mi".Trim() --assignee-principal-type ServicePrincipal --role 'Storage Blob Data Reader' --scope $acctId --output none | Out-Null; Start-Sleep -Seconds 60 }
  Deploy 'migrate' @{ image = (Image-Ref); recoverFrom = @{ account = $acct; container = 'alice-offsite'; manifest = "$manifest" } }
  $st = Run-Job 'alice-recover'
  if ($st -ne 'Succeeded') { throw 'The recovery did not succeed. Nothing was switched on. Read the job''s log (portal > alice-recover > Execution history), fix the cause and run this step again on a NEW resource group.' }
  Write-Host 'Recovered: the database and files are loaded, and the counts match the copy.' -ForegroundColor Green
  Write-Host 'Next: -Step signin, then -Step apps -ExtAppId <Alice API app id> -ExtCallers "<as before>", then -Step backup.' -ForegroundColor Green
}

if (Want 'github') {
  Say 'GitHub pipeline sign-in (OIDC)'
  if (-not $GitHubRepo) { Write-Host 'Skipped: give -GitHubRepo owner/name.'; return }
  # Each part is checked first and retried (new Entra objects take a minute to appear everywhere), so this is safe to run again.
  function Retry($what, [scriptblock]$do) {
    for ($i = 1; $i -le 12; $i++) { try { return (& $do) } catch { if ($i -eq 12) { throw "$what failed: $_" }; Start-Sleep -Seconds 10 } }
  }
  if (-not $State.githubClientId) {
    $app = AzCli ad app create --display-name 'Alice GitHub deploy' --sign-in-audience AzureADMyOrg --query appId -o tsv
    Set-Prop $State 'githubClientId' $app; Save-State $State
  }
  $app = $State.githubClientId
  $sp = AzTry ad sp show --id $app --query id -o tsv
  if (-not $sp) { $sp = Retry 'Creating the GitHub service principal' { AzCli ad sp create --id $app --query id -o tsv } }
  # The deploy job runs in the "production" environment, and GitHub names the repo by owner and repo ID as well as name,
  # e.g. repo:stefanjoc-ux@336622755/Alice@1403454494:environment:production (the deploy log shows the exact subject).
  $subjects = @(@('github-main', "repo:${GitHubRepo}:ref:refs/heads/main"), @('github-production', "repo:${GitHubRepo}:environment:production"))
  if ($GitHubSubject) { $subjects += ,@('github-production-ids', $GitHubSubject) }
  $existing = @(AzTry ad app federated-credential list --id $app --query '[].subject' -o tsv)
  foreach ($fc in $subjects) {
    if ($existing -contains $fc[1]) { continue }
    $fed = @{ name = $fc[0]; issuer = 'https://token.actions.githubusercontent.com'; subject = $fc[1]; audiences = @('api://AzureADTokenExchange') } | ConvertTo-Json -Compress
    $tmp = New-TemporaryFile; [IO.File]::WriteAllText($tmp, $fed)
    try { Retry "Adding the GitHub sign-in record $($fc[0])" { AzCli ad app federated-credential create --id $app --parameters "@$tmp" --output none | Out-Null } } finally { Remove-Item $tmp -ErrorAction SilentlyContinue }
  }
  $rg = AzCli group show -n $ResourceGroup --query id -o tsv
  $acr = AzCli acr show -n $State.acrName --query id -o tsv
  foreach ($ra in @(@('Contributor', $rg), @('AcrPush', $acr))) {
    $has = AzTry role assignment list --assignee $sp --role $ra[0] --scope $ra[1] --query '[0].id' -o tsv
    if (-not $has) { Retry "Giving the pipeline $($ra[0])" { AzCli role assignment create --assignee-object-id $sp --assignee-principal-type ServicePrincipal --role $ra[0] --scope $ra[1] --output none | Out-Null } }
  }
  Write-Host "Set these as repository VARIABLES (Settings > Secrets and variables > Actions > Variables) in $GitHubRepo :"
  Write-Host "  AZURE_CLIENT_ID       = $($State.githubClientId)"
  Write-Host "  AZURE_TENANT_ID       = $Tenant"
  Write-Host "  AZURE_SUBSCRIPTION_ID = $SubscriptionId"
  Write-Host "  AZURE_RESOURCE_GROUP  = $ResourceGroup"
  Write-Host "  ACR_NAME              = $($State.acrName)"
}

Save-State $State      # the Azure copy is up to date at the end of every step
$script:Recorded = $true; Record-Step 'ok' ''
Say 'Done'
