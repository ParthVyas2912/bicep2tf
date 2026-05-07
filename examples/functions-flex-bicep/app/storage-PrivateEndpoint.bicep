@description('Specifies the name of the virtual network.')
param virtualNetworkName string

@description('Specifies the name of the subnet which contains the private endpoint.')
param subnetName string

@description('Specifies the name of the resource with a private endpoint.')
param resourceName string

@description('Specifies the location.')
param location string = resourceGroup().location

param tags object = {}

@description('Enable private endpoint for blob storage')
param enableBlob bool = true

@description('Enable private endpoint for queue storage')
param enableQueue bool = false

@description('Enable private endpoint for table storage')
param enableTable bool = false

resource vnet 'Microsoft.Network/virtualNetworks@2021-08-01' existing = {
  name: virtualNetworkName
}

resource subnet 'Microsoft.Network/virtualNetworks/subnets@2021-08-01' existing = {
  parent: vnet
  name: subnetName
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2022-09-01' existing = {
  name: resourceName
}

module blobPrivateEndpoint 'br/public:avm/res/network/private-endpoint:0.11.0' = if (enableBlob) {
  name: 'blob-${resourceName}-privateEndpoint'
  params: {
    name: 'pe-${resourceName}-blob'
    location: location
    tags: tags
    subnetResourceId: subnet.id
    privateLinkServiceConnections: [
      {
        name: 'pe-${resourceName}-blob'
        properties: {
          privateLinkServiceId: storageAccount.id
          groupIds: [
            'blob'
          ]
        }
      }
    ]
  }
}

module queuePrivateEndpoint 'br/public:avm/res/network/private-endpoint:0.11.0' = if (enableQueue) {
  name: 'queue-${resourceName}-privateEndpoint'
  params: {
    name: 'pe-${resourceName}-queue'
    location: location
    tags: tags
    subnetResourceId: subnet.id
    privateLinkServiceConnections: [
      {
        name: 'pe-${resourceName}-queue'
        properties: {
          privateLinkServiceId: storageAccount.id
          groupIds: [
            'queue'
          ]
        }
      }
    ]
  }
}

module tablePrivateEndpoint 'br/public:avm/res/network/private-endpoint:0.11.0' = if (enableTable) {
  name: 'table-${resourceName}-privateEndpoint'
  params: {
    name: 'pe-${resourceName}-table'
    location: location
    tags: tags
    subnetResourceId: subnet.id
    privateLinkServiceConnections: [
      {
        name: 'pe-${resourceName}-table'
        properties: {
          privateLinkServiceId: storageAccount.id
          groupIds: [
            'table'
          ]
        }
      }
    ]
  }
}
