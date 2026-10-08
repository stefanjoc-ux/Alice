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
  users    (run on its own) people and roles: adds the app roles Alice.Owner, Alice.Admin and Alice.Member to the "Alice web
           sign-in" app registration (and the "Alice connector sign-in" one if it exists), sets "Assignment required" on the web
           sign-in's enterprise application, and assigns you (and the accounts in -AlsoAllow) the Owner role. It does NOT switch
           Alice over: until you run -Step users -UseAppRoles on and then -Step apps, Entra still lets in only the accounts it does
           today (allowedPrincipals), so nobody is locked out. Adding a person afterwards = assigning them a role in Entra
           (Enterprise applications > Alice web sign-in > Users and groups); they start with the default Member profile.
             -Step users                      roles, Assignment required, you as Owner (safe to run again)
             -Step users -UseAppRoles on      remember the switch; then -Step apps puts it live (off = back to allowedPrincipals)
  recover  (run on its own, in a NEW resource group from a fresh clone; docs/restore.md part C) loads a nightly off-site copy
           into this new, empty Alice before its apps start: -Step recover -RecoverFrom <offsite account> [-RecoverCopy yyyy/mm/dd]
  check    (run on its own; READ-ONLY, changes nothing) lists what each step has set up in the resource group (sign-in,
           apps, connector, demo, Copilot, mail, backups: the vault and its retention, the lock, the off-site account and its
           retention, the nightly job and its last run, the drill; app roles) and flags anything missing or different.
  -DatabaseHost <server address>  (any step; remembered) after a point-in-time restore into a new server (docs/restore.md part B),
           so redeploys keep database-url pointing at it. -DatabaseHost '' goes back to this template's own server.
The setup state (what every step set up and every later step keeps) lives IN AZURE: the blob alice-setup/azure-state.json in
Alice's own storage account (deploy/azure_state.py). Every step reads it first and writes it back whenever it saves; each saved
version is also kept under alice-setup/history/. deploy\azure-state.json is only a cache of it. If the Azure copy is missing or
older than the newest deployment, it is rebuilt from what is deployed first, and you are shown what was rebuilt. If the local
file differs from the Azure copy, the step stops: delete or rename the local file to use the Azure copy, or add -UseLocalState
to use the local file deliberately (it then replaces the Azure copy).
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
  [switch]$UseLocalState,             # use deploy\azure-state.json even though it differs from the Azure copy (it then replaces it)
  [ValidateSet('all', 'infra', 'secrets', 'image', 'files', 'migrate', 'signin', 'apps', 'github', 'connector', 'demo', 'copilot', 'mail', 'backup', 'recover', 'users', 'check')][string]$Step = 'all'
)
$ErrorActionPreference = 'Stop'
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
function Want($name) { return (($Step -eq 'all' -and $name -notin @('connector', 'demo', 'copilot', 'mail', 'backup', 'recover', 'users')) -or $Step -eq $name) }
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
$Tenant = AzCli account show --query tenantId -o tsv
if ($Step -eq 'check') {
  Say "Check (read-only): what each step has set up in $ResourceGroup"
  & $StatePy $StateHelper check --resource-group $ResourceGroup --file $StateFile --who "$Me" | Out-Host
  if ($LASTEXITCODE -ne 0) { throw 'The check could not finish (see above). Nothing was changed.' }
  return
}
Sync-State
$State = Load-State
if ($PSBoundParameters.ContainsKey('DatabaseHost')) { Set-Prop $State 'databaseHost' $DatabaseHost.Trim(); Save-State $State }   # '' clears it
Write-Host "Subscription $SubscriptionId, tenant $Tenant, resource group $ResourceGroup ($Location), you: $Me"

function Deploy($stage, $extra) {
  $kv = $State.keyVault
  $pw = if ($kv -and (Kv-Has $kv 'pg-admin-password')) { Kv-Get $kv 'pg-admin-password' } elseif ($State.pendingPassword) { $State.pendingPassword } else { New-Password }
  if (-not $kv) { Set-Prop $State 'pendingPassword' $pw; Save-State $State }   # kept only until it is in Key Vault
  $values = @{ stage = $stage; pgAdminPassword = $pw; deployerObjectId = $Me; ownerObjectId = $Me; location = $Location }
  # Backups (-Step backup) are remembered, so every step that redeploys keeps them exactly as they are
  foreach ($k in 'pgBackupRetentionDays', 'filesBackupDays', 'offsiteKeepDays', 'offsiteSoftDeleteDays') { if ($State.$k) { $values[$k] = [int]$State.$k } }
  if ($State.pgGeoBackup) { $values['pgGeoRedundantBackup'] = $true }
  if ($State.databaseHost) { $values['databaseHost'] = "$($State.databaseHost)" }
  if ($State.useAppRoles) { $values['useAppRoles'] = $true }     # -Step users -UseAppRoles on: kept by every later step
  if ($State.backup) {
    $values['backup'] = $true; $values['backupNotify'] = "$($State.backupNotify)"
    $values['lockResourceGroup'] = -not $State.noLock; $values['offsiteImmutabilityLocked'] = [bool]$State.offsiteImmutabilityLocked
  }
  foreach ($k in $extra.Keys) { $values[$k] = $extra[$k] }
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
  # Fixed IDs, so running this again changes nothing and the roles never get new IDs (Alice reads the role NAMES).
  $roles = @(
    @{ id = '388aff1f-7b8b-4bcf-bde1-0df23a400f6e'; value = 'Alice.Owner'; displayName = 'Alice Owner'; description = 'Everything in Alice, including everyone''s items. The owner (ownerObjectId) is always an Owner.' },
    @{ id = '5fc72aad-c175-48b3-89ef-0d7f38675c1c'; value = 'Alice.Admin'; displayName = 'Alice Admin'; description = 'Their permission profile, plus Users and permissions, Rules and Rule packs. Never Health, Trading, Mileage or Backups.' },
    @{ id = '63e492a6-c40b-4485-b412-3ed386f849d6'; value = 'Alice.Member'; displayName = 'Alice Member'; description = 'Their permission profile only (by default: Chat and their own saved chats).' }
  )
  function Add-Roles($appId, $label) {
    $have = @(AzCli ad app show --id $appId --query 'appRoles' -o json | ConvertFrom-Json)
    $merged = @($have | Where-Object { $_.value -notin $roles.value })      # any other roles on the app are kept
    foreach ($r in $roles) {
      $merged += [pscustomobject]@{ allowedMemberTypes = @('User'); description = $r.description; displayName = $r.displayName
                                    id = $r.id; isEnabled = $true; value = $r.value }
    }
    $tmp = New-TemporaryFile
    try { [IO.File]::WriteAllText($tmp, (ConvertTo-Json -InputObject @($merged) -Depth 5 -Compress)); AzCli ad app update --id $appId --app-roles "@$tmp" | Out-Null }
    finally { Remove-Item $tmp -ErrorAction SilentlyContinue }
    Write-Host "$label`: roles Alice.Owner, Alice.Admin, Alice.Member"
  }
  Add-Roles $State.webAuthClientId 'Alice web sign-in'
  if ($State.connectorClientId) { Add-Roles $State.connectorClientId 'Alice connector sign-in' }
  # The web sign-in's enterprise application (service principal)
  $sp = AzTry ad sp show --id $State.webAuthClientId --query id -o tsv
  if (-not $sp) { $sp = Retry 'Creating the web sign-in service principal' { AzCli ad sp create --id $State.webAuthClientId --query id -o tsv } }
  # You (and the accounts you allowed before) as Owner, first, so nobody who gets in today is locked out by Assignment required or the switch.
  $owners = @($Me) + @($State.alsoAllow | Where-Object { $_ }) | Select-Object -Unique
  foreach ($o in $owners) {
    $has = AzCli rest --method GET --url "https://graph.microsoft.com/v1.0/servicePrincipals/$sp/appRoleAssignedTo" `
             --query "length(value[?principalId=='$o' && appRoleId=='$($roles[0].id)'])" -o tsv
    if ([int]$has -gt 0) { Write-Host "Already an Owner: $o"; continue }
    $body = @{ principalId = $o; resourceId = $sp; appRoleId = $roles[0].id } | ConvertTo-Json -Compress
    $tmp = New-TemporaryFile
    try {
      [IO.File]::WriteAllText($tmp, $body)
      Retry "Assigning $o as Owner" { AzCli rest --method POST --url "https://graph.microsoft.com/v1.0/servicePrincipals/$sp/appRoleAssignedTo" --headers 'Content-Type=application/json' --body "@$tmp" --output none | Out-Null }
    } finally { Remove-Item $tmp -ErrorAction SilentlyContinue }
    Write-Host "Assigned Owner: $o"
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
  $users = (@($Me) + @($State.alsoAllow | Where-Object { $_ }) | Select-Object -Unique) -join ','
  $values = @{ image = (Image-Ref); pgAdminPassword = (Kv-Get $State.keyVault 'pg-admin-password'); ownerObjectId = $Me; location = $Location
               allowedUserObjectIds = @($State.alsoAllow | Where-Object { $_ }); webAuthClientId = $State.webAuthClientId; keyVaultSecretNames = (Key-Names)
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
  $uris = @(AzCli ad app show --id $State.webAuthClientId --query 'web.redirectUris' -o json | ConvertFrom-Json)
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
Say 'Done'
