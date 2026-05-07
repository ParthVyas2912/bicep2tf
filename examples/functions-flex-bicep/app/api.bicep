param name string
@description('Primary location for all resources & Flex Consumption Function App')
param location string = resourceGroup().location
param tags object = {}
param applicationInsightsName string = ''
param appServicePlanId string
param appSettings object = {}
param runtimeName string 
param runtimeVersion string 
param serviceName string = 'qsp-api'
param storageAccountName string
param deploymentStorageContainerName string
param virtualNetworkSubnetId string = ''
param instanceMemoryMB int = 2048
param maximumInstanceCount int = 100
param identityId string = ''
param identityClientId string = ''
param enableBlob bool = true
param enableQueue bool = false
param enableTable bool = false
param enableFile bool = false

@allowed(['SystemAssigned', 'UserAssigned'])
param identityType string = 'UserAssigned'

var applicationInsightsIdentity = 'ClientId=${identityClientId};Authorization=AAD'
var kind = 'functionapp,linux'

// Create base application settings as array
var baseAppSettingsArray = [
  {
    name: 'AzureWebJobsStorage__credential'
    value: 'managedidentity'
  }
  {
    name: 'AzureWebJobsStorage__clientId'
    value: identityClientId
  }
  {
    name: 'AzureWebJobsStorage__accountName'
    value: storageAccountName
  }
  {
    name: 'APPLICATIONINSIGHTS_AUTHENTICATION_STRING'
    value: applicationInsightsIdentity
  }
  {
    name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
    value: !empty(applicationInsightsName) ? applicationInsights.properties.ConnectionString : ''
  }
]

// Dynamically build storage endpoint settings based on feature flags
var storageEndpointSettings = concat(
  enableBlob ? [{
    name: 'AzureWebJobsStorage__blobServiceUri'
    value: stg.properties.primaryEndpoints.blob
  }] : [],
  enableQueue ? [{
    name: 'AzureWebJobsStorage__queueServiceUri'
    value: stg.properties.primaryEndpoints.queue
  }] : [],
  enableTable ? [{
    name: 'AzureWebJobsStorage__tableServiceUri'
    value: stg.properties.primaryEndpoints.table
  }] : [],
  enableFile ? [{
    name: 'AzureWebJobsStorage__fileServiceUri'
    value: stg.properties.primaryEndpoints.file
  }] : []
)

// Convert custom appSettings object to array
var customAppSettingsArray = [for item in items(appSettings): {
  name: item.key
  value: item.value
}]

// Merge all app settings arrays
var allAppSettingsArray = concat(
  customAppSettingsArray,
  storageEndpointSettings,
  baseAppSettingsArray
)

resource stg 'Microsoft.Storage/storageAccounts@2022-09-01' existing = {
  name: storageAccountName
}

resource applicationInsights 'Microsoft.Insights/components@2020-02-02' existing = if (!empty(applicationInsightsName)) {
  name: applicationInsightsName
}

// Create a Flex Consumption Function App to host the API
module api 'br/public:avm/res/web/site:0.15.1' = {
  name: '${serviceName}-flex-consumption'
  params: {
    kind: kind
    name: name
    location: location
    tags: union(tags, { 'azd-service-name': serviceName })
    serverFarmResourceId: appServicePlanId
    managedIdentities: {
      systemAssigned: identityType == 'SystemAssigned'
      userAssignedResourceIds: [
        '${identityId}'
      ]
    }
    functionAppConfig: {
      deployment: {
        storage: {
          type: 'blobContainer'
          value: '${stg.properties.primaryEndpoints.blob}${deploymentStorageContainerName}'
          authentication: {
            type: identityType == 'SystemAssigned' ? 'SystemAssignedIdentity' : 'UserAssignedIdentity'
            userAssignedIdentityResourceId: identityType == 'UserAssigned' ? identityId : null
          }
        }
      }
      scaleAndConcurrency: {
        instanceMemoryMB: instanceMemoryMB
        maximumInstanceCount: maximumInstanceCount
      }
      runtime: {
        name: runtimeName
        version: runtimeVersion
      }
    }
    virtualNetworkSubnetId: virtualNetworkSubnetId
    siteConfig: {
      minTlsVersion: '1.2'
      appSettings: allAppSettingsArray
      cors: {
        allowedOrigins: [
          'https://portal.azure.com'
          'https://ms.portal.azure.com'
        ]
        supportCredentials: false
      }
    }
  }
}

output SERVICE_API_NAME string = api.outputs.name
output SERVICE_API_URI string = api.outputs.defaultHostname
output SERVICE_API_RESOURCE_ID string = api.outputs.resourceId
