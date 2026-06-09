// Private Endpoints and DNS Zones Module
// Based on foundry-samples/16-private-network-standard-agent-apim-setup-preview

@description('Azure region for resources')
param location string

@description('Resource ID of the VNet')
param vnetId string

@description('Resource ID of the private endpoint subnet')
param peSubnetId string

@description('Resource ID of the AI Services account')
param aiServicesId string = ''

@description('Resource ID of the AI Search service')
param aiSearchId string = ''

@description('Resource ID of the Storage Account')
param storageAccountId string = ''

@description('Resource ID of the Cosmos DB account')
param cosmosDbId string = ''

@description('Resource ID of the API Management service')
param apimId string = ''

@description('Resource ID of the AHDS workspace (Microsoft.HealthcareApis/workspaces)')
param healthDataServicesWorkspaceId string = ''

@description('Resource ID of the Key Vault')
param keyVaultId string = ''

@description('Resource ID of the Function App')
param functionAppId string = ''

@description('Unique suffix for resource naming')
param uniqueSuffix string = uniqueString(resourceGroup().id)

@description('Tags to apply to resources')
param tags object = {}

// Private DNS Zones - these are standard Azure private link zones
#disable-next-line no-hardcoded-env-urls
var privateDnsZones = [
  'privatelink.services.ai.azure.com'       // 0
  'privatelink.openai.azure.com'            // 1
  'privatelink.cognitiveservices.azure.com'  // 2
  'privatelink.search.windows.net'           // 3
  'privatelink.blob.${environment().suffixes.storage}' // 4
  'privatelink.documents.azure.com'          // 5
  'privatelink.azure-api.net'                // 6
  'privatelink.azurewebsites.net'            // 7
  'privatelink.fhir.azurehealthcareapis.com' // 8
  'privatelink.vaultcore.azure.net'          // 9
]

// Create Private DNS Zones
resource dnsZones 'Microsoft.Network/privateDnsZones@2024-06-01' = [for zone in privateDnsZones: {
  name: zone
  location: 'global'
  tags: tags
}]

// Link DNS Zones to VNet
resource dnsZoneVnetLinks 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2024-06-01' = [for (zone, i) in privateDnsZones: {
  parent: dnsZones[i]
  name: '${zone}-link'
  location: 'global'
  properties: {
    virtualNetwork: {
      id: vnetId
    }
    registrationEnabled: false
  }
}]

// Private Endpoint for AI Services
resource aiServicesPe 'Microsoft.Network/privateEndpoints@2024-01-01' = if (!empty(aiServicesId)) {
  name: 'pe-aiservices-${uniqueSuffix}'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: peSubnetId
    }
    privateLinkServiceConnections: [
      {
        name: 'aiservices-connection'
        properties: {
          privateLinkServiceId: aiServicesId
          groupIds: [
            'account'
          ]
        }
      }
    ]
  }
}

resource aiServicesDnsGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-01-01' = if (!empty(aiServicesId)) {
  parent: aiServicesPe
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'aiservices-config'
        properties: {
          privateDnsZoneId: dnsZones[0].id // privatelink.services.ai.azure.com
        }
      }
      {
        name: 'openai-config'
        properties: {
          privateDnsZoneId: dnsZones[1].id // privatelink.openai.azure.com
        }
      }
      {
        name: 'cognitiveservices-config'
        properties: {
          privateDnsZoneId: dnsZones[2].id // privatelink.cognitiveservices.azure.com
        }
      }
    ]
  }
}

// Private Endpoint for AI Search
resource aiSearchPe 'Microsoft.Network/privateEndpoints@2024-01-01' = if (!empty(aiSearchId)) {
  name: 'pe-aisearch-${uniqueSuffix}'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: peSubnetId
    }
    privateLinkServiceConnections: [
      {
        name: 'aisearch-connection'
        properties: {
          privateLinkServiceId: aiSearchId
          groupIds: [
            'searchService'
          ]
        }
      }
    ]
  }
}

resource aiSearchDnsGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-01-01' = if (!empty(aiSearchId)) {
  parent: aiSearchPe
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'aisearch-config'
        properties: {
          privateDnsZoneId: dnsZones[3].id // privatelink.search.windows.net
        }
      }
    ]
  }
}

// Private Endpoint for Storage Account (Blob)
resource storagePe 'Microsoft.Network/privateEndpoints@2024-01-01' = if (!empty(storageAccountId)) {
  name: 'pe-storage-${uniqueSuffix}'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: peSubnetId
    }
    privateLinkServiceConnections: [
      {
        name: 'storage-connection'
        properties: {
          privateLinkServiceId: storageAccountId
          groupIds: [
            'blob'
          ]
        }
      }
    ]
  }
}

resource storageDnsGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-01-01' = if (!empty(storageAccountId)) {
  parent: storagePe
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'storage-config'
        properties: {
          privateDnsZoneId: dnsZones[4].id // privatelink.blob.core.windows.net
        }
      }
    ]
  }
}

// Private Endpoint for Cosmos DB
resource cosmosDbPe 'Microsoft.Network/privateEndpoints@2024-01-01' = if (!empty(cosmosDbId)) {
  name: 'pe-cosmosdb-${uniqueSuffix}'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: peSubnetId
    }
    privateLinkServiceConnections: [
      {
        name: 'cosmosdb-connection'
        properties: {
          privateLinkServiceId: cosmosDbId
          groupIds: [
            'Sql'
          ]
        }
      }
    ]
  }
}

resource cosmosDbDnsGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-01-01' = if (!empty(cosmosDbId)) {
  parent: cosmosDbPe
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'cosmosdb-config'
        properties: {
          privateDnsZoneId: dnsZones[5].id // privatelink.documents.azure.com
        }
      }
    ]
  }
}

// Private Endpoint for APIM Gateway
resource apimPe 'Microsoft.Network/privateEndpoints@2024-01-01' = if (!empty(apimId)) {
  name: 'pe-apim-${uniqueSuffix}'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: peSubnetId
    }
    privateLinkServiceConnections: [
      {
        name: 'apim-connection'
        properties: {
          privateLinkServiceId: apimId
          groupIds: [
            'Gateway'
          ]
        }
      }
    ]
  }
}

resource apimDnsGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-01-01' = if (!empty(apimId)) {
  parent: apimPe
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'apim-config'
        properties: {
          privateDnsZoneId: dnsZones[6].id // privatelink.azure-api.net
        }
      }
    ]
  }
}

// Private Endpoint for Function App
resource functionAppPe 'Microsoft.Network/privateEndpoints@2024-01-01' = if (!empty(functionAppId)) {
  name: 'pe-funcapp-${uniqueSuffix}'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: peSubnetId
    }
    privateLinkServiceConnections: [
      {
        name: 'funcapp-connection'
        properties: {
          privateLinkServiceId: functionAppId
          groupIds: [
            'sites'
          ]
        }
      }
    ]
  }
}

resource functionAppDnsGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-01-01' = if (!empty(functionAppId)) {
  parent: functionAppPe
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'funcapp-config'
        properties: {
          privateDnsZoneId: dnsZones[7].id // privatelink.azurewebsites.net
        }
      }
    ]
  }
}

// Private Endpoint for FHIR Service (Azure Health Data Services)
// NOTE: Private endpoints target the AHDS workspace, not the child fhirservice.
// The 'fhir' group ID selects the FHIR sub-resource within the workspace.
resource fhirPe 'Microsoft.Network/privateEndpoints@2024-01-01' = if (!empty(healthDataServicesWorkspaceId)) {
  name: 'pe-fhir-${uniqueSuffix}'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: peSubnetId
    }
    privateLinkServiceConnections: [
      {
        name: 'fhir-connection'
        properties: {
          privateLinkServiceId: healthDataServicesWorkspaceId
          groupIds: [
            'fhir'
          ]
        }
      }
    ]
  }
}

resource fhirDnsGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-01-01' = if (!empty(healthDataServicesWorkspaceId)) {
  parent: fhirPe
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'fhir-config'
        properties: {
          privateDnsZoneId: dnsZones[8].id // privatelink.fhir.azurehealthcareapis.com
        }
      }
    ]
  }
}

output dnsZoneIds array = [for (zone, i) in privateDnsZones: dnsZones[i].id]
output aiServicesPeId string = !empty(aiServicesId) ? aiServicesPe.id : ''
output aiSearchPeId string = !empty(aiSearchId) ? aiSearchPe.id : ''
output storagePeId string = !empty(storageAccountId) ? storagePe.id : ''
output cosmosDbPeId string = !empty(cosmosDbId) ? cosmosDbPe.id : ''
output apimPeId string = !empty(apimId) ? apimPe.id : ''
output functionAppPeId string = !empty(functionAppId) ? functionAppPe.id : ''
output fhirPeId string = !empty(healthDataServicesWorkspaceId) ? fhirPe.id : ''

// Private Endpoint for Key Vault
resource keyVaultPe 'Microsoft.Network/privateEndpoints@2024-01-01' = if (!empty(keyVaultId)) {
  name: 'pe-keyvault-${uniqueSuffix}'
  location: location
  tags: tags
  properties: {
    subnet: {
      id: peSubnetId
    }
    privateLinkServiceConnections: [
      {
        name: 'keyvault-connection'
        properties: {
          privateLinkServiceId: keyVaultId
          groupIds: [
            'vault'
          ]
        }
      }
    ]
  }
}

resource keyVaultDnsGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-01-01' = if (!empty(keyVaultId)) {
  parent: keyVaultPe
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'keyvault-config'
        properties: {
          privateDnsZoneId: dnsZones[9].id // privatelink.vaultcore.azure.net
        }
      }
    ]
  }
}

output keyVaultPeId string = !empty(keyVaultId) ? keyVaultPe.id : ''
