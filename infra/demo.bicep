// The demo Alice: a second Alice for client demos (Stefan's decision, 5 Oct 2026), deployed by deploy/azure-setup.ps1 -Step demo.
// Same image, same environment, registry, identity and Key Vault as live Alice, but its OWN database (alice_demo on the same
// PostgreSQL server) and its own data folder on the share, so it can never see live data and live Alice never sees demo data.
// ALICE_DEMO_INSTANCE=1 turns on the Client demo page, the demo banner and the demo notice on every connector answer, and keeps
// Stefan's own apps (Health, Trading, Mileage) out. Both apps scale to zero when idle (open the demo a couple of minutes early).
targetScope = 'resourceGroup'

param location string = 'uksouth'
param prefix string = 'alice'
@description('Container image (the live one, so the demo always runs the current release).')
param image string
param pgAdminLogin string = 'aliceadmin'
@secure()
param pgAdminPassword string
param ownerName string = 'Stefan'
param ownerObjectId string
param allowedUserObjectIds array = []
@description('Client ID of the "Alice web sign-in" app registration (shared with live; the script adds the demo address to it).')
param webAuthClientId string
param keyVaultSecretNames object = {}
param extAppId string
param extAllowedUsers string
param extCallers string

var suffix = take(uniqueString(resourceGroup().id), 6)
resource env 'Microsoft.App/managedEnvironments@2024-03-01' existing = { name: '${prefix}-env' }
resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' existing = { name: '${prefix}-identity' }
resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = { name: '${prefix}${suffix}acr' }
resource kv 'Microsoft.KeyVault/vaults@2023-07-01' existing = { name: '${prefix}-kv-${suffix}' }
resource pg 'Microsoft.DBforPostgreSQL/flexibleServers@2022-12-01' existing = { name: '${prefix}-pg-${suffix}' }

// its own database on the same server, and its own connection string in Key Vault
resource demoDb 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2022-12-01' = {
  parent: pg
  name: 'alice_demo'
  properties: { charset: 'UTF8', collation: 'en_US.utf8' }
}
resource demoDbUrl 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: kv
  name: 'database-url-demo'
  properties: { value: 'host=${pg.properties.fullyQualifiedDomainName} port=5432 dbname=alice_demo user=${pgAdminLogin} password=${pgAdminPassword} sslmode=require' }
}

var webName = '${prefix}-demo-web'
var mcpName = '${prefix}-demo-mcp'
var webFqdn = '${webName}.${env.properties.defaultDomain}'
var mcpFqdn = '${mcpName}.${env.properties.defaultDomain}'
var kvUri = kv.properties.vaultUri
var keySecretNames = [for k in items(keyVaultSecretNames): { name: toLower(replace(k.key, '_', '-')), env: k.key, kv: k.value }]
var secrets = concat(
  [{ name: 'database-url', keyVaultUrl: '${kvUri}secrets/database-url-demo', identity: identity.id }],
  map(keySecretNames, s => { name: s.name, keyVaultUrl: '${kvUri}secrets/${s.kv}', identity: identity.id })
)
var commonEnv = concat(
  [
    { name: 'ALICE_DATABASE_URL', secretRef: 'database-url' }
    { name: 'ALICE_DEMO_INSTANCE', value: '1' }
    { name: 'AISUBSTRATE_DATA_DIR', value: '/mnt/alice/demo/data' }
    { name: 'ALICE_DOCUMENT_LIBRARY', value: '/mnt/alice/demo/Documents' }
    { name: 'ALICE_OWNER_NAME', value: ownerName }
    { name: 'ALICE_AUDIT_STDOUT', value: '1' }
  ],
  map(keySecretNames, s => { name: s.env, secretRef: s.name })
)
var volumes = [{ name: 'alice', storageType: 'AzureFile', storageName: 'alice-files', mountOptions: 'uid=10001,gid=10001,dir_mode=0770,file_mode=0660' }]
var mounts = [{ volumeName: 'alice', mountPath: '/mnt/alice' }]
var registries = [{ server: acr.properties.loginServer, identity: identity.id }]
var scaleToZero = { minReplicas: 0, maxReplicas: 1, rules: [{ name: 'http', http: { metadata: { concurrentRequests: '50' } } }] }

resource web 'Microsoft.App/containerApps@2024-03-01' = {
  name: webName
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${identity.id}': {} } }
  properties: {
    environmentId: env.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: { external: true, targetPort: 8000, transport: 'auto', allowInsecure: false }
      registries: registries
      secrets: concat(secrets, [{ name: 'web-auth-secret', keyVaultUrl: '${kvUri}secrets/web-auth-secret', identity: identity.id }])
    }
    template: {
      containers: [{
        name: 'web'
        image: image
        resources: { cpu: json('0.5'), memory: '1Gi' }
        env: concat(commonEnv, [
          { name: 'ALICE_ROLE', value: 'web' }
          { name: 'ALICE_TRUST_EASYAUTH', value: '1' }
          { name: 'ALICE_NO_SCHEDULER', value: '1' }
          { name: 'SUBSTRATE_ALLOWED_HOSTS', value: webFqdn }
        ])
        volumeMounts: mounts
      }]
      scale: scaleToZero
      volumes: volumes
    }
  }
  dependsOn: [demoDbUrl, demoDb]
}

// The same sign-in as live Alice: only you get in.
resource webAuth 'Microsoft.App/containerApps/authConfigs@2024-03-01' = {
  parent: web
  name: 'current'
  properties: {
    platform: { enabled: true }
    globalValidation: { unauthenticatedClientAction: 'RedirectToLoginPage', redirectToProvider: 'azureactivedirectory', excludedPaths: ['/healthz', '/signed-out'] }
    identityProviders: {
      azureActiveDirectory: {
        enabled: true
        registration: { clientId: webAuthClientId, clientSecretSettingName: 'web-auth-secret', openIdIssuer: '${environment().authentication.loginEndpoint}${tenant().tenantId}/v2.0' }
        validation: { allowedAudiences: [webAuthClientId, 'api://${webAuthClientId}'], defaultAuthorizationPolicy: { allowedPrincipals: { identities: union([ownerObjectId], allowedUserObjectIds) } } }
        login: { loginParameters: ['domain_hint=organizations'] }
      }
    }
    login: { preserveUrlFragmentsForLogins: true, cookieExpiration: { convention: 'FixedTime', timeToExpiration: '08:00:00' } }
  }
}

// The connector endpoint Copilot reads: same Alice API app registration and allowed users as live, its own address.
resource mcp 'Microsoft.App/containerApps@2024-03-01' = {
  name: mcpName
  location: location
  identity: { type: 'UserAssigned', userAssignedIdentities: { '${identity.id}': {} } }
  properties: {
    environmentId: env.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: { external: true, targetPort: 8002, transport: 'auto', allowInsecure: false }
      registries: registries
      secrets: secrets
    }
    template: {
      containers: [{
        name: 'mcp'
        image: image
        resources: { cpu: json('0.5'), memory: '1Gi' }
        env: concat(commonEnv, [
          { name: 'ALICE_ROLE', value: 'mcp' }
          { name: 'ALICE_EXT_TENANT_ID', value: tenant().tenantId }
          { name: 'ALICE_EXT_APP_ID', value: extAppId }
          { name: 'ALICE_EXT_ALLOWED_USERS', value: extAllowedUsers }
          { name: 'ALICE_EXT_CALLERS', value: extCallers }
          { name: 'ALICE_EXT_BASE_URL', value: 'https://${mcpFqdn}' }
          { name: 'ALICE_EXT_ALLOWED_HOSTS', value: mcpFqdn }
          { name: 'ALICE_EXT_HOST', value: '0.0.0.0' }
          { name: 'ALICE_EXT_PORT', value: '8002' }
          { name: 'ALICE_NO_SCHEDULER', value: '1' }
        ])
        volumeMounts: mounts
      }]
      scale: scaleToZero
      volumes: volumes
    }
  }
  dependsOn: [demoDbUrl, demoDb]
}

output demoWebUrl string = 'https://${webFqdn}'
output demoMcpUrl string = 'https://${mcpFqdn}'
