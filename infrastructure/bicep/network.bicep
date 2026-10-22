targetScope = 'resourceGroup'

param vnetName string
param vnetAddressPrefix string
param subnetName string
param subnetAddressPrefix string
param location string
param tags object = {}

resource nsg 'Microsoft.Network/networkSecurityGroups@2023-09-01' = {
  name: '${subnetName}-nsg'
  location: location
  tags: tags
  properties: {
    securityRules: []
  }
}

resource vnet 'Microsoft.Network/virtualNetworks@2023-09-01' = {
  name: vnetName
  location: location
  tags: tags
  properties: {
    addressSpace: {
      addressPrefixes: [
        vnetAddressPrefix
      ]
    }
    subnets: [
      {
        name: subnetName
        properties: {
          addressPrefix: subnetAddressPrefix
          networkSecurityGroup: {
            id: nsg.id
          }
        }
      }
    ]
  }
}

resource privateDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: 'privatelink.blob.${environment().suffixes.storage}'
  location: 'global'
  tags: tags
}

resource privateDnsZoneLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: privateDnsZone
  name: '${vnetName}-link'
  location: 'global'
  tags: tags
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: vnet.id
    }
  }
}
//Azure Private Dns zones for monitoring
var monitorDnsZones = [
      'privatelink.monitor.azure.com'
      'privatelink.oms.opinsights.azure.com'
      'privatelink.ods.opinsights.azure.com'
      'privatelink.agentsvc.azure-automation.net'
    ]

// Create the 4 dns zone needed for the monitoring data link
resource monitorPrivateDnsZones 'Microsoft.Network/privateDnsZones@2020-06-01' = [
    for zoneName in monitorDnsZones :{
        name: zoneName
        location: 'global'
        tags: tags
        }
    ]

// Link each DNS zones to the existing VNet
resource monitorPrivateDnsZoneLinks 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = [
    for (zoneName, i) in monitorDnsZones: {
        parent: monitorPrivateDnsZones[i]
        name: '${vnetName}-link'
        location: 'global'
        properties: {
            registrationEnabled: false
            virtualNetwork: {
                id: vnet.id
                }
            }
        }
    ]

output subnetId string = '${vnet.id}/subnets/${subnetName}'
output privateDnsZoneId string = privateDnsZone.id
