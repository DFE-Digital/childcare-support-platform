targetScope = 'resourceGroup'

param storageAccountName string
param location string
param tags object = {}
param storageAccountSku string = 'Standard_ZRS'
param workspaceName string
param subnetId string
param privateDnsZoneId string
param workflowPrincipalId string

resource law 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: workspaceName
  location: location
  tags: tags
  properties: {
    retentionInDays: 90
    sku: {
      name: 'PerGB2018'
    }
  }
}

resource sa 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  tags: tags

  sku: {
    name: storageAccountSku
  }

  kind: 'StorageV2'

  properties: {
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    allowSharedKeyAccess: false
    publicNetworkAccess: 'Disabled'
    allowBlobPublicAccess: false
    networkAcls: {
      defaultAction: 'Deny'
      bypass: 'AzureServices'
    }
  }
}

resource blob 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  name: 'default'
  parent: sa

  properties: {
    isVersioningEnabled: true

    deleteRetentionPolicy: {
      enabled: true
      days: 14
    }

    containerDeleteRetentionPolicy: {
      enabled: true
      days: 14
    }
  }
}

resource container 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  name: 'tfstate'
  parent: blob
}

resource blobDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
   name: '${storageAccountName}-blob-diag'
   scope: blob

   properties: {
     workspaceId: law.id

     logs: [
       {
         category: 'StorageRead'
         enabled: true
       }
       {
         category: 'StorageWrite'
         enabled: true
       }
       {
         category: 'StorageDelete'
         enabled: true
       }
     ]

     metrics: [
       {
         category: 'Transaction'
         enabled: true
       }
     ]
   }
 }

resource privateEndpoint 'Microsoft.Network/privateEndpoints@2023-09-01' = {
  name: '${storageAccountName}-pe'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: subnetId
    }
    privateLinkServiceConnections: [
      {
        name: '${storageAccountName}-pe-conn'
        properties: {
          privateLinkServiceId: sa.id
          groupIds: [
            'blob'
          ]
        }
      }
    ]
  }
}

resource privateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-09-01' = {
  parent: privateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'privatelink-blob-core-windows-net'
        properties: {
          privateDnsZoneId: privateDnsZoneId
        }
      }
    ]
  }
}

resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(sa.id, workflowPrincipalId, 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
  scope: sa
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalId: workflowPrincipalId
    principalType: 'ServicePrincipal'
  }
}