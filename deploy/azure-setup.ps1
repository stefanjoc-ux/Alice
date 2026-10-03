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
  [ValidateSet('all', 'infra', 'secrets', 'image', 'files', 'migrate', 'signin', 'apps', 'github')][string]$Step = 'all'
)
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$Template = Join-Path $Root 'infra\main.bicep'
$StateFile = Join-Path $PSScriptRoot 'azure-state.json'

function Say($text) { Write-Host "`n== $text" -ForegroundColor Cyan }
function AzCli { $out = & az @args; if ($LASTEXITCODE -ne 0) { throw "az $($args -join ' ') failed" }; return $out }   # not named Az: PowerShell names ignore case, so it would call itself
function AzTry { $ErrorActionPreference = 'Continue'; & az @args 2>$null }   # may fail (e.g. "does it exist?"): Windows PowerShell 5.1 otherwise turns az's error text into a stop
function Want($name) { return ($Step -eq 'all' -or $Step -eq $name) }
function Load-State { if (Test-Path $StateFile) { return Get-Content $StateFile -Raw | ConvertFrom-Json } else { return [pscustomobject]@{} } }
function Save-State($s) { $s | ConvertTo-Json -Depth 5 | Set-Content $StateFile -Encoding UTF8 }
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
if (-not $ExtAllowedUsers) { $ExtAllowedUsers = $Me }
$State = Load-State
Write-Host "Subscription $SubscriptionId, tenant $Tenant, resource group $ResourceGroup ($Location), you: $Me"

function Deploy($stage, $extra) {
  $kv = $State.keyVault
  $pw = if ($kv -and (Kv-Has $kv 'pg-admin-password')) { Kv-Get $kv 'pg-admin-password' } elseif ($State.pendingPassword) { $State.pendingPassword } else { New-Password }
  if (-not $kv) { Set-Prop $State 'pendingPassword' $pw; Save-State $State }   # kept only until it is in Key Vault
  $values = @{ stage = $stage; pgAdminPassword = $pw; deployerObjectId = $Me; ownerObjectId = $Me; location = $Location }
  foreach ($k in $extra.Keys) { $values[$k] = $extra[$k] }
  $doc = @{ '$schema' = 'https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#'; contentVersion = '1.0.0.0'; parameters = @{} }
  foreach ($k in $values.Keys) { $doc.parameters[$k] = @{ value = $values[$k] } }
  $pfile = New-TemporaryFile                     # a parameters file: no quoting problems, and the password is not on the command line
  try {
    [IO.File]::WriteAllText($pfile, ($doc | ConvertTo-Json -Depth 6))
    $out = AzCli deployment group create -g $ResourceGroup -f $Template -n ('alice-' + $stage) --parameters ('@' + $pfile) --query properties.outputs -o json | ConvertFrom-Json
  } finally { Remove-Item $pfile -Force -ErrorAction SilentlyContinue }
  foreach ($p in 'acrName', 'acrLoginServer', 'keyVaultName', 'storageAccount', 'shareName', 'environmentDomain', 'webUrl', 'mcpUrl', 'postgresServer') {
    if ($out.$p) { Set-Prop $State $p $out.$p.value }
  }
  Set-Prop $State 'keyVault' $State.keyVaultName
  if (-not (Kv-Has $State.keyVault 'pg-admin-password')) { Kv-Set $State.keyVault 'pg-admin-password' $pw }
  if ($State.pendingPassword) { $State.PSObject.Properties.Remove('pendingPassword') }
  Save-State $State
}

function Image-Ref { if (-not $State.image) { throw 'No image yet: run -Step image first.' }; return $State.image }
function Key-Names {
  $map = @{}
  foreach ($k in @('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'XAI_API_KEY', 'ELEVENLABS_API_KEY')) {
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
  foreach ($k in @('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'XAI_API_KEY', 'ELEVENLABS_API_KEY')) {
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
      $status = AzCli acr build --registry $State.acrName --image ("alice:" + $tag) --file Dockerfile $src --no-logs --query status -o tsv
    } finally { Remove-Item $src, $zip -Recurse -Force -ErrorAction SilentlyContinue }
    if ("$status".Trim() -ne 'Succeeded') {
      Write-Host "The build did not succeed ($status). See its log with:  az acr task list-runs -r $($State.acrName) --top 1 -o table   then   az acr task logs -r $($State.acrName) --run-id <RUN ID>" -ForegroundColor Yellow
      throw 'Image build failed.'
    }
    Set-Prop $State 'image' ($State.acrLoginServer + '/alice:' + $tag); Save-State $State
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
  if (-not $ExtAppId -or -not $ExtCallers) { throw 'Give -ExtAppId (the Alice API app registration) and -ExtCallers (e.g. "<copilot app id>=Microsoft Copilot:copilot"), the same values as ALICE_EXT_APP_ID and ALICE_EXT_CALLERS on the PC.' }
  Deploy 'apps' @{ image = (Image-Ref); webAuthClientId = $State.webAuthClientId; keyVaultSecretNames = (Key-Names)
                   extAppId = $ExtAppId; extAllowedUsers = $ExtAllowedUsers; extCallers = $ExtCallers }
  Write-Host "Web:  $($State.webUrl)"
  Write-Host "MCP:  $($State.mcpUrl)/mcp   (set this as the Copilot plugin URL, and run Test-External against it)"
}

if (Want 'github') {
  Say 'GitHub pipeline sign-in (OIDC)'
  if (-not $GitHubRepo) { Write-Host 'Skipped: give -GitHubRepo owner/name.'; return }
  if (-not $State.githubClientId) {
    $app = AzCli ad app create --display-name 'Alice GitHub deploy' --sign-in-audience AzureADMyOrg --query appId -o tsv
    $sp = AzCli ad sp create --id $app --query id -o tsv
    $fed = @{ name = 'github-main'; issuer = 'https://token.actions.githubusercontent.com'; subject = "repo:${GitHubRepo}:ref:refs/heads/main"; audiences = @('api://AzureADTokenExchange') } | ConvertTo-Json -Compress
    $tmp = New-TemporaryFile; [IO.File]::WriteAllText($tmp, $fed)
    AzCli ad app federated-credential create --id $app --parameters "@$tmp" --output none | Out-Null; Remove-Item $tmp
    $rg = AzCli group show -n $ResourceGroup --query id -o tsv
    $acr = AzCli acr show -n $State.acrName --query id -o tsv
    AzCli role assignment create --assignee-object-id $sp --assignee-principal-type ServicePrincipal --role Contributor --scope $rg --output none | Out-Null
    AzCli role assignment create --assignee-object-id $sp --assignee-principal-type ServicePrincipal --role AcrPush --scope $acr --output none | Out-Null
    Set-Prop $State 'githubClientId' $app; Save-State $State
  }
  Write-Host "Set these as repository VARIABLES (Settings > Secrets and variables > Actions > Variables) in $GitHubRepo :"
  Write-Host "  AZURE_CLIENT_ID       = $($State.githubClientId)"
  Write-Host "  AZURE_TENANT_ID       = $Tenant"
  Write-Host "  AZURE_SUBSCRIPTION_ID = $SubscriptionId"
  Write-Host "  AZURE_RESOURCE_GROUP  = $ResourceGroup"
  Write-Host "  ACR_NAME              = $($State.acrName)"
}

Say 'Done'
