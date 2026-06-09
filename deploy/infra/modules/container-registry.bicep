// Azure Container Registry module
// Used by azd to push dockerized MCP server images

@description('Azure region for the container registry')
param location string

@description('Globally unique container registry name')
@minLength(5)
@maxLength(50)
param registryName string

@description('Container Registry SKU')
@allowed([
  'Basic'
  'Standard'
  'Premium'
])
param skuName string = 'Basic'

@description('Enable admin user on the container registry')
param adminUserEnabled bool = false

@description('Enable public network access for the container registry')
@allowed([
  'Enabled'
  'Disabled'
])
param publicNetworkAccess string = 'Enabled'

@description('Tags to apply to the container registry')
param tags object = {}

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' = {
  name: registryName
  location: location
  tags: tags
  sku: {
    name: skuName
  }
  properties: {
    adminUserEnabled: adminUserEnabled
    publicNetworkAccess: publicNetworkAccess
    anonymousPullEnabled: false
    zoneRedundancy: 'Disabled'
  }
}

output registryId string = containerRegistry.id
output registryName string = containerRegistry.name
output registryLoginServer string = containerRegistry.properties.loginServer
