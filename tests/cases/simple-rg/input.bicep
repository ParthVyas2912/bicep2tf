targetScope = 'subscription'

param environmentName string
param location string = 'eastus2'

resource rg 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: 'rg-${environmentName}'
  location: location
  tags: {
    'azd-env-name': environmentName
  }
}

output rgName string = rg.name
