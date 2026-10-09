// Temple's local model (Stefan, 9 Oct 2026; temple_model.py): a small open model served by Ollama inside Alice's own Container
// Apps environment, for the sharing check, categories, tags and keeping them tidy. Optional and off by default: main.bicep deploys
// this only with localModel = true (azure-setup.ps1 -Step localmodel -LocalModel on).
//   - INTERNAL INGRESS ONLY: reachable from alice-web and alice-mcp in the same environment (http://<prefix>-local-model), never
//     from the internet. No secrets, no managed identity, no Key Vault, no database: it only answers what Alice sends it.
//   - Its own file share (<prefix>-models in Alice's storage account) keeps the downloaded model between restarts. It never
//     mounts Alice's own share (Documents, data), and the nightly backup does not copy it (the model can be downloaded again).
//   - One replica, always on (a cold start loads the model, which a waiting sharing check should not sit through); minReplicas 0
//     when switched off, so it costs nothing while Alice no longer calls it.
targetScope = 'resourceGroup'

param location string
param prefix string
param environmentName string
param storageAccountName string
@description('The Ollama model tag to download and serve, e.g. qwen3:4b.')
param modelName string
@description('Ollama image, pinned to an exact version.')
param image string = 'docker.io/ollama/ollama:0.11.4'
@description('1 while Alice uses it; 0 when switched off (scales to zero, no charge while idle).')
@minValue(0)
@maxValue(1)
param minReplicas int = 1
param cpu string = '4.0'
param memory string = '8Gi'

var appName = '${prefix}-local-model'
var shareName = '${prefix}-models'

resource env 'Microsoft.App/managedEnvironments@2024-03-01' existing = {
  name: environmentName
}

resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' existing = {
  name: storageAccountName
}

resource files 'Microsoft.Storage/storageAccounts/fileServices@2023-01-01' existing = {
  parent: storage
  name: 'default'
}

resource modelsShare 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-01-01' = {
  parent: files
  name: shareName
  properties: { shareQuota: 50 }
}

resource envModels 'Microsoft.App/managedEnvironments/storages@2024-03-01' = {
  parent: env
  name: 'alice-models'
  properties: {
    azureFile: { accountName: storage.name, accountKey: storage.listKeys().keys[0].value, shareName: modelsShare.name, accessMode: 'ReadWrite' }
  }
}

resource localModel 'Microsoft.App/containerApps@2024-03-01' = {
  name: appName
  location: location
  properties: {
    managedEnvironmentId: env.id
    workloadProfileName: 'Consumption'
    configuration: {
      activeRevisionsMode: 'Single'
      // internal only: no public address; reached as http://<app name> from apps in this environment
      ingress: { external: false, targetPort: 11434, transport: 'http', allowInsecure: true }
    }
    template: {
      containers: [
        {
          name: 'ollama'
          image: image
          resources: { cpu: json(cpu), memory: memory }
          env: [
            { name: 'OLLAMA_HOST', value: '0.0.0.0:11434' }
            { name: 'OLLAMA_MODELS', value: '/models' }
            { name: 'OLLAMA_KEEP_ALIVE', value: '-1' }        // keep the model loaded: no reload before each check
            { name: 'OLLAMA_NUM_PARALLEL', value: '1' }
            { name: 'ALICE_LOCAL_MODEL', value: modelName }
          ]
          // serve, wait until it answers, then download the model once (kept on the models share)
          command: ['/bin/sh', '-c']
          args: ['ollama serve & until ollama list >/dev/null 2>&1; do sleep 1; done; ollama pull "$ALICE_LOCAL_MODEL"; wait']
          volumeMounts: [{ volumeName: 'models', mountPath: '/models' }]
          probes: [
            { type: 'Startup', tcpSocket: { port: 11434 }, initialDelaySeconds: 5, periodSeconds: 5, failureThreshold: 60 }
          ]
        }
      ]
      volumes: [{ name: 'models', storageType: 'AzureFile', storageName: envModels.name }]
      scale: { minReplicas: minReplicas, maxReplicas: 1 }
    }
  }
}

output url string = 'http://${appName}'
output appName string = appName
