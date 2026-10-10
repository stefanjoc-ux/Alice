// Backups for Alice (8 Oct 2026). A module of main.bicep, deployed when its parameter `backup` is true, which
// azure-setup.ps1 -Step backup switches on (and every later step keeps on). It adds:
//   1. Azure Backup for the file share: a Recovery Services vault and a daily policy (snapshots kept filesRetentionDays),
//      so one file or folder can be restored.
//   2. A CanNotDelete lock on the resource group (lockResourceGroup, on by default). Lifting it is deliberate:
//      az lock delete --name alice-do-not-delete --resource-group <rg>   (then run -Step backup -NoLock so it is not put back)
//   3. The nightly off-site copy: a SEPARATE storage account in UK West (Entra only, no account keys, two layers of
//      encryption at rest), its container keeping each copy unchangeable for offsiteKeepDays (time-based immutability) with
//      soft delete behind it, and the Container Apps job alice-backup that writes to it at 02:00 UK time with Alice's
//      managed identity. The job reads the file share through a READ-ONLY mount.
//   4. Reader for Alice's identity on the vault and the database server, so the Backup page can show their state.
//   5. The restore drill: its own identity (Contributor on the drill resource group ONLY, read on the off-site copies,
//      write on the drill-reports container only, pull on the registry), the alice-drill job (manual: the Backup page's
//      button and the Restore drill workflow start it) and a custom role that lets Alice's identity start that one job.
// Nothing here reads or changes live data.
targetScope = 'resourceGroup'

param location string
param offsiteLocation string = 'ukwest'
param prefix string
param environmentName string
param identityName string
param storageAccountName string
param shareName string
param pgServerName string
param vaultName string
param offsiteName string
param offsiteContainer string = 'alice-offsite'
param image string
param registries array
param secrets array
param env array
@minValue(1)
@maxValue(200)
param filesRetentionDays int = 30
@description('When the daily file share snapshot is taken, UK time (HH:MM).')
param filesBackupTime string = '01:00'
@minValue(1)
@maxValue(365)
param offsiteKeepDays int = 35
@minValue(1)
@maxValue(365)
param offsiteSoftDeleteDays int = 35
@description('True once the immutability policy has been locked (azure-setup -Step backup -LockImmutability): a locked policy is never redeployed.')
param immutabilityLocked bool = false
param lockResourceGroup bool = true
@description('Object ID of the person running the deployment: gets read access to the off-site copies, for restores from Cloud Shell.')
param deployerObjectId string
param acrName string
@description('The restore drill\'s own resource group (created by azure-setup.ps1 -Step backup): throwaway resources only.')
param drillResourceGroup string
param webAuthClientId string
param ownerObjectId string
param ownerName string
param mailFrom string = ''
param publicUrl string = ''
param backupNotify string = ''

// Built-in role IDs, exactly as Microsoft publishes them (tests/test_infra_roles.py checks every one against its list).
var roles = {
  reader: 'acdd72a7-3385-48ef-bd42-f606fba81ae7'
  blobContributor: 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
  blobReader: '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1'
}

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = { name: identityName }
resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' existing = { name: storageAccountName }
resource pg 'Microsoft.DBforPostgreSQL/flexibleServers@2022-12-01' existing = { name: pgServerName }
resource cae 'Microsoft.App/managedEnvironments@2024-03-01' existing = { name: environmentName }
resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = { name: acrName }

// ---------------- 1. Azure Backup for the file share ----------------
resource vault 'Microsoft.RecoveryServices/vaults@2023-04-01' = {
  name: vaultName
  location: location
  sku: { name: 'RS0', tier: 'Standard' }
  properties: { publicNetworkAccess: 'Enabled' }
}

var filesTime = '2020-01-01T${filesBackupTime}:00Z'
resource filesPolicy 'Microsoft.RecoveryServices/vaults/backupPolicies@2023-04-01' = {
  parent: vault
  name: 'alice-files-daily'
  properties: {
    backupManagementType: 'AzureStorage'
    workLoadType: 'AzureFileShare'
    timeZone: 'GMT Standard Time'
    schedulePolicy: { schedulePolicyType: 'SimpleSchedulePolicy', scheduleRunFrequency: 'Daily', scheduleRunTimes: [filesTime] }
    retentionPolicy: {
      retentionPolicyType: 'LongTermRetentionPolicy'
      dailySchedule: { retentionTimes: [filesTime], retentionDuration: { count: filesRetentionDays, durationType: 'Days' } }
    }
  }
}

var containerName = 'storagecontainer;Storage;${resourceGroup().name};${storageAccountName}'
// The fabric 'Azure' has no Bicep types, so these two are named in full (as in Microsoft's own file share backup template).
resource filesContainer 'Microsoft.RecoveryServices/vaults/backupFabrics/protectionContainers@2023-04-01' = {
  name: '${vaultName}/Azure/${containerName}'
  properties: { backupManagementType: 'AzureStorage', containerType: 'StorageContainer', sourceResourceId: storage.id }
  dependsOn: [vault]
}

resource filesProtected 'Microsoft.RecoveryServices/vaults/backupFabrics/protectionContainers/protectedItems@2023-04-01' = {
  parent: filesContainer
  name: 'AzureFileShare;${shareName}'
  properties: { protectedItemType: 'AzureFileShareProtectedItem', sourceResourceId: storage.id, policyId: filesPolicy.id }
}

// ---------------- 2. Nothing in the resource group can be deleted until the lock is lifted ----------------
resource rgLock 'Microsoft.Authorization/locks@2020-05-01' = if (lockResourceGroup) {
  name: 'alice-do-not-delete'
  properties: {
    level: 'CanNotDelete'
    notes: 'Alice: protects the database, file share, vault and apps from deletion. Lift deliberately: az lock delete --name alice-do-not-delete --resource-group ${resourceGroup().name}, then azure-setup.ps1 -Step backup -NoLock so it is not put back.'
  }
}

// ---------------- 3. The off-site copy: another UK region, unchangeable for offsiteKeepDays ----------------
resource offsite 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: offsiteName
  location: offsiteLocation
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Cool'
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false               // Entra (managed identity, your sign-in) only: no account keys, no SAS
    defaultToOAuthAuthentication: true
    supportsHttpsTrafficOnly: true
    publicNetworkAccess: 'Enabled'
    encryption: {
      keySource: 'Microsoft.Storage'
      requireInfrastructureEncryption: true   // a second layer of encryption at rest
      services: { blob: { enabled: true, keyType: 'Account' }, file: { enabled: true, keyType: 'Account' } }
    }
  }
}

resource offsiteBlobs 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: offsite
  name: 'default'
  properties: {
    deleteRetentionPolicy: { enabled: true, days: offsiteSoftDeleteDays }
    containerDeleteRetentionPolicy: { enabled: true, days: offsiteSoftDeleteDays }
  }
}

resource offsiteBox 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: offsiteBlobs
  name: offsiteContainer
  properties: { publicAccess: 'None' }
}

// Write once, read many: a copy cannot be changed or deleted until it is offsiteKeepDays old. Unlocked by default (an
// owner can still remove the policy); -LockImmutability locks it for good (retention can then only be lengthened).
resource offsiteImmutable 'Microsoft.Storage/storageAccounts/blobServices/containers/immutabilityPolicies@2023-01-01' = if (!immutabilityLocked) {
  parent: offsiteBox
  name: 'default'
  properties: { immutabilityPeriodSinceCreationInDays: offsiteKeepDays, allowProtectedAppendWrites: false }
}

// Copies older than the keep period are removed the day after they stop being immutable (soft delete still holds them).
resource offsiteLifecycle 'Microsoft.Storage/storageAccounts/managementPolicies@2023-01-01' = {
  parent: offsite
  name: 'default'
  properties: {
    policy: {
      rules: [{
        name: 'remove-after-keep-period'
        enabled: true
        type: 'Lifecycle'
        definition: {
          filters: { blobTypes: ['blockBlob'], prefixMatch: ['${offsiteContainer}/'] }
          actions: { baseBlob: { delete: { daysAfterCreationGreaterThan: offsiteKeepDays + 1 } } }
        }
      }, {
        name: 'remove-old-drill-reports'
        enabled: true
        type: 'Lifecycle'
        definition: {
          filters: { blobTypes: ['blockBlob'], prefixMatch: ['drill-reports/'] }
          actions: { baseBlob: { delete: { daysAfterCreationGreaterThan: 400 } } }
        }
      }]
    }
  }
  dependsOn: [offsiteBox, drillReports]
}

resource identityWritesOffsite 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(offsite.id, identity.id, roles.blobContributor)
  scope: offsite
  properties: { roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.blobContributor), principalId: identity.properties.principalId, principalType: 'ServicePrincipal' }
}

resource deployerReadsOffsite 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(offsite.id, deployerObjectId, roles.blobReader)
  scope: offsite
  properties: { roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.blobReader), principalId: deployerObjectId, principalType: 'User' }
}

// ---------------- 4. The Backup page reads backup state (Reader on these two resources only) ----------------
resource identityReadsVault 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(vault.id, identity.id, roles.reader)
  scope: vault
  properties: { roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.reader), principalId: identity.properties.principalId, principalType: 'ServicePrincipal' }
}

resource identityReadsDatabase 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(pg.id, identity.id, roles.reader)
  scope: pg
  properties: { roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.reader), principalId: identity.properties.principalId, principalType: 'ServicePrincipal' }
}

// ---------------- the job: 02:00 UK time (UTC schedule at 01:00 and 02:00; backup.py keeps the one at 02:00 UK) ----------------
resource filesReadOnly 'Microsoft.App/managedEnvironments/storages@2024-03-01' = {
  parent: cae
  name: 'alice-files-ro'
  properties: {
    azureFile: { accountName: storage.name, accountKey: storage.listKeys().keys[0].value, shareName: shareName, accessMode: 'ReadOnly' }
  }
}

resource backupJob 'Microsoft.App/jobs@2024-03-01' = {
  name: '${prefix}-backup'
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${identity.id}': {} } }
  properties: {
    environmentId: cae.id
    workloadProfileName: 'Consumption'
    configuration: {
      triggerType: 'Schedule'
      replicaTimeout: 10800
      replicaRetryLimit: 0
      scheduleTriggerConfig: { cronExpression: '0 1,2 * * *', parallelism: 1, replicaCompletionCount: 1 }
      registries: registries
      secrets: secrets
    }
    template: {
      containers: [{
        name: 'backup'
        image: image
        resources: { cpu: json('1.0'), memory: '2Gi' }
        env: concat(env, [
          { name: 'ALICE_ROLE', value: 'backup' }
          // Alice's own folder for this job is local and thrown away: the live share is only ever read (/mnt/alice-ro)
          { name: 'AISUBSTRATE_DATA_DIR', value: '/tmp/alice-backup' }
          { name: 'ALICE_BACKUP_SOURCE', value: '/mnt/alice-ro' }
          { name: 'ALICE_NO_SCHEDULER', value: '1' }
        ])
        volumeMounts: [{ volumeName: 'alice-ro', mountPath: '/mnt/alice-ro' }]
      }]
      volumes: [{ name: 'alice-ro', storageType: 'AzureFile', storageName: filesReadOnly.name, mountOptions: 'uid=10001,gid=10001,dir_mode=0550,file_mode=0440' }]
    }
  }
  dependsOn: [identityWritesOffsite, offsiteBox]
}

// ---------------- 5. The restore drill ----------------
resource drillReports 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  parent: offsiteBlobs
  name: 'drill-reports'
  properties: { publicAccess: 'None' }
}

resource drillIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${prefix}-drill-identity'
  location: location
}

var acrPull = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
resource drillReadsCopies 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(offsite.id, drillIdentity.id, roles.blobReader)
  scope: offsite
  properties: { roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.blobReader), principalId: drillIdentity.properties.principalId, principalType: 'ServicePrincipal' }
}

resource drillWritesReports 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(drillReports.id, drillIdentity.id, roles.blobContributor)
  scope: drillReports
  properties: { roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roles.blobContributor), principalId: drillIdentity.properties.principalId, principalType: 'ServicePrincipal' }
}

// The temporary Alice runs as this identity, so the drill must be allowed to assign it (to that app, in the drill group).
var identityOperator = 'f1a07417-d97a-45cb-824c-7a7467783830'
resource drillAssignsItself 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(drillIdentity.id, drillIdentity.id, identityOperator)
  scope: drillIdentity
  properties: { roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', identityOperator), principalId: drillIdentity.properties.principalId, principalType: 'ServicePrincipal' }
}

resource drillPullsImage 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acr.id, drillIdentity.id, acrPull)
  scope: acr
  properties: { roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', acrPull), principalId: drillIdentity.properties.principalId, principalType: 'ServicePrincipal' }
}

module drillAccess 'drill-access.bicep' = {
  name: 'alice-drill-access'
  scope: resourceGroup(drillResourceGroup)
  params: { principalId: drillIdentity.properties.principalId }
}

resource drillJob 'Microsoft.App/jobs@2024-03-01' = {
  name: '${prefix}-drill'
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${drillIdentity.id}': {} } }
  properties: {
    environmentId: cae.id
    workloadProfileName: 'Consumption'
    configuration: {
      triggerType: 'Manual'
      replicaTimeout: 10800
      replicaRetryLimit: 0
      manualTriggerConfig: { parallelism: 1, replicaCompletionCount: 1 }
      registries: [{ server: acr.properties.loginServer, identity: drillIdentity.id }]
    }
    template: {
      containers: [{
        name: 'drill'
        image: image
        resources: { cpu: json('0.5'), memory: '1Gi' }
        // No database address and no API keys: the drill never touches Alice's live database or share.
        env: [
          { name: 'ALICE_ROLE', value: 'drill' }
          { name: 'AISUBSTRATE_DATA_DIR', value: '/tmp/alice-drill' }
          { name: 'ALICE_NO_SCHEDULER', value: '1' }
          { name: 'ALICE_DRILL_SUBSCRIPTION', value: subscription().subscriptionId }
          { name: 'ALICE_DRILL_RG', value: drillResourceGroup }
          { name: 'ALICE_DRILL_LIVE_RG', value: resourceGroup().name }
          { name: 'ALICE_DRILL_LOCATION', value: location }
          { name: 'ALICE_BACKUP_ACCOUNT', value: offsite.name }
          { name: 'ALICE_BACKUP_CONTAINER', value: offsiteContainer }
          { name: 'ALICE_DRILL_REPORTS', value: drillReports.name }
          { name: 'ALICE_FILES_ACCOUNT', value: storage.name }
          { name: 'ALICE_DRILL_IDENTITY_ID', value: drillIdentity.id }
          { name: 'ALICE_IDENTITY_CLIENT_ID', value: drillIdentity.properties.clientId }
          { name: 'ALICE_ACR_SERVER', value: acr.properties.loginServer }
          { name: 'ALICE_DRILL_IMAGE', value: image }
          { name: 'ALICE_DRILL_AUTH_CLIENT_ID', value: webAuthClientId }
          { name: 'ALICE_TENANT_ID', value: tenant().tenantId }
          { name: 'ALICE_OWNER_OBJECT_ID', value: ownerObjectId }
          { name: 'ALICE_OWNER_NAME', value: ownerName }
          { name: 'ALICE_BACKUP_NOTIFY', value: backupNotify }
          { name: 'ALICE_MAIL_FROM', value: mailFrom }
          { name: 'ALICE_PUBLIC_URL', value: publicUrl }
          { name: 'ALICE_DRILL_RTO_HOURS', value: '4' }
        ]
      }]
    }
  }
  dependsOn: [drillPullsImage, drillReadsCopies, drillWritesReports, drillAccess, drillAssignsItself]
}

// Alice's own identity may start this one job (the Backup page's button) and see its runs; nothing else.
resource drillStarter 'Microsoft.Authorization/roleDefinitions@2022-04-01' = {
  name: guid(resourceGroup().id, 'alice-drill-starter')
  properties: {
    roleName: 'Alice restore drill starter (${resourceGroup().name})'
    description: 'Start the alice-drill job and read its runs. Nothing else.'
    type: 'CustomRole'
    permissions: [{ actions: ['Microsoft.App/jobs/read', 'Microsoft.App/jobs/start/action', 'Microsoft.App/jobs/executions/read'], notActions: [] }]
    assignableScopes: [resourceGroup().id]
  }
}

resource identityStartsDrill 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(drillJob.id, identity.id, 'alice-drill-starter')
  scope: drillJob
  properties: { roleDefinitionId: drillStarter.id, principalId: identity.properties.principalId, principalType: 'ServicePrincipal' }
}

output vaultId string = vault.id
output drillIdentityPrincipalId string = drillIdentity.properties.principalId
output offsiteAccount string = offsite.name
output offsiteContainer string = offsiteContainer
output backupJob string = backupJob.name
