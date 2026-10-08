// The restore drill may build and remove throwaway resources here, in its OWN resource group, and nowhere else
// (deployed by main.bicep into that resource group; azure-setup.ps1 -Step backup creates the group first).
targetScope = 'resourceGroup'

@description('Principal ID of the restore drill\'s managed identity.')
param principalId string

var contributor = 'b24988ac-6180-42a0-ab88-20f7382dd24c'

resource drillContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, principalId, contributor)
  properties: { roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', contributor), principalId: principalId, principalType: 'ServicePrincipal' }
}
