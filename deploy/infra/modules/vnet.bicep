// Healthcare MCP VNet Module
// Based on foundry-samples/16-private-network-standard-agent-apim-setup-preview

@description('Azure region for the VNet')
param location string

@description('Name of the VNet')
param vnetName string

@description('Address prefix for the VNet')
param vnetAddressPrefix string = '192.168.0.0/16'

@description('Name of the subnet for AI Agents (Container Apps Environment)')
param agentSubnetName string = 'agent-subnet'

@description('Address prefix for agent subnet')
param agentSubnetAddressPrefix string = '192.168.0.0/24'

@description('Name of the subnet for private endpoints')
param peSubnetName string = 'pe-subnet'

@description('Address prefix for private endpoint subnet')
param peSubnetAddressPrefix string = '192.168.1.0/24'

@description('Name of the subnet for APIM')
param apimSubnetName string = 'apim-subnet'

@description('Address prefix for APIM subnet')
param apimSubnetAddressPrefix string = '192.168.2.0/24'

@description('Name of the subnet for Function Apps')
param functionSubnetName string = 'function-subnet'

@description('Address prefix for Function Apps subnet')
param functionSubnetAddressPrefix string = '192.168.3.0/24'

@description('Tags to apply to resources')
param tags object = {}

// NSG for APIM subnet - required for VNet integration
// See: https://aka.ms/apimvnet
resource apimNsg 'Microsoft.Network/networkSecurityGroups@2024-01-01' = {
  name: '${vnetName}-apim-nsg'
  location: location
  tags: tags
  properties: {
    securityRules: [
      {
        name: 'AllowAPIMManagement'
        properties: {
          priority: 100
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourceAddressPrefix: 'ApiManagement'
          sourcePortRange: '*'
          destinationAddressPrefix: 'VirtualNetwork'
          destinationPortRange: '3443'
        }
      }
      {
        name: 'AllowAzureLoadBalancer'
        properties: {
          priority: 110
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourceAddressPrefix: 'AzureLoadBalancer'
          sourcePortRange: '*'
          destinationAddressPrefix: 'VirtualNetwork'
          destinationPortRange: '6390'
        }
      }
      {
        name: 'AllowHTTPS'
        properties: {
          priority: 120
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourceAddressPrefix: 'Internet'
          sourcePortRange: '*'
          destinationAddressPrefix: 'VirtualNetwork'
          destinationPortRange: '443'
        }
      }
      {
        name: 'AllowHTTP'
        properties: {
          priority: 130
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourceAddressPrefix: 'Internet'
          sourcePortRange: '*'
          destinationAddressPrefix: 'VirtualNetwork'
          destinationPortRange: '80'
        }
      }
      {
        name: 'AllowStorageOutbound'
        properties: {
          priority: 100
          direction: 'Outbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourceAddressPrefix: 'VirtualNetwork'
          sourcePortRange: '*'
          destinationAddressPrefix: 'Storage'
          destinationPortRange: '443'
        }
      }
      {
        name: 'AllowSQLOutbound'
        properties: {
          priority: 110
          direction: 'Outbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourceAddressPrefix: 'VirtualNetwork'
          sourcePortRange: '*'
          destinationAddressPrefix: 'Sql'
          destinationPortRange: '1433'
        }
      }
      {
        name: 'AllowAzureADOutbound'
        properties: {
          priority: 120
          direction: 'Outbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourceAddressPrefix: 'VirtualNetwork'
          sourcePortRange: '*'
          destinationAddressPrefix: 'AzureActiveDirectory'
          destinationPortRange: '443'
        }
      }
    ]
  }
}

resource vnet 'Microsoft.Network/virtualNetworks@2024-01-01' = {
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
        name: agentSubnetName
        properties: {
          addressPrefix: agentSubnetAddressPrefix
          delegations: [
            {
              name: 'Microsoft.App/environments'
              properties: {
                serviceName: 'Microsoft.App/environments'
              }
            }
          ]
        }
      }
      {
        name: peSubnetName
        properties: {
          addressPrefix: peSubnetAddressPrefix
          privateEndpointNetworkPolicies: 'Disabled'
        }
      }
      {
        name: apimSubnetName
        properties: {
          addressPrefix: apimSubnetAddressPrefix
          networkSecurityGroup: {
            id: apimNsg.id
          }
          // APIM Standard V2 requires delegation to Microsoft.Web/serverFarms for outbound VNet integration
          delegations: [
            {
              name: 'Microsoft.Web/serverFarms'
              properties: {
                serviceName: 'Microsoft.Web/serverFarms'
              }
            }
          ]
          serviceEndpoints: [
            {
              service: 'Microsoft.Storage'
            }
            {
              service: 'Microsoft.Sql'
            }
            {
              service: 'Microsoft.EventHub'
            }
            {
              service: 'Microsoft.KeyVault'
            }
            {
              service: 'Microsoft.Web'
            }
          ]
        }
      }
      {
        name: functionSubnetName
        properties: {
          addressPrefix: functionSubnetAddressPrefix
          delegations: [
            {
              name: 'Microsoft.Web/serverFarms'
              properties: {
                serviceName: 'Microsoft.Web/serverFarms'
              }
            }
          ]
        }
      }
    ]
  }
}

output vnetId string = vnet.id
output vnetName string = vnet.name
output agentSubnetId string = '${vnet.id}/subnets/${agentSubnetName}'
output peSubnetId string = '${vnet.id}/subnets/${peSubnetName}'
output apimSubnetId string = '${vnet.id}/subnets/${apimSubnetName}'
output functionSubnetId string = '${vnet.id}/subnets/${functionSubnetName}'
