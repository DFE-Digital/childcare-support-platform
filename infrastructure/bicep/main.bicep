targetScope = 'subscription'

param tfResourceGroupName string
param securityResourceGroupName string
param keyVaultName string
param location string
param storageAccountName string
param tags object = {}
param storageAccountSku string = 'Standard_ZRS'
param workspaceName string
param vnetName string
param vnetAddressPrefix string
param subnetName string
param subnetAddressPrefix string
param workflowPrincipalId string
param tenantId string

output tfResourceGroupName string = tfResourceGroupName
output storageAccountName string = storageAccountName
output keyVaultName string = keyVaultName

resource tfRg 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: tfResourceGroupName
  location: location
  tags: tags
}

resource secRg 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: securityResourceGroupName
  location: location
  tags: tags
}

module network './network.bicep' = {
  name: 'networkDeployment'
  scope: resourceGroup(tfResourceGroupName)
  dependsOn: [tfRg]
  params: {
    vnetName: vnetName
    vnetAddressPrefix: vnetAddressPrefix
    subnetName: subnetName
    subnetAddressPrefix: subnetAddressPrefix
    location: location
    tags: tags
  }
}

module storage './storage.bicep' = {
  name: 'storageDeployment'
  scope: resourceGroup(tfResourceGroupName)
  dependsOn: [tfRg]
  params: {
    storageAccountName: storageAccountName
    location: location
    tags: tags
    storageAccountSku: storageAccountSku
    workspaceName: workspaceName
    subnetId: network.outputs.subnetId
    privateDnsZoneId: network.outputs.privateDnsZoneId
    workflowPrincipalId: workflowPrincipalId
  }
}

module security './security.bicep' = {
  name: 'securityDeployment'
  scope: resourceGroup(securityResourceGroupName)
  dependsOn: [secRg]
  params: {
    keyVaultName: keyVaultName
    location: location
    tags: tags
    tenantId: tenantId
  }
}
