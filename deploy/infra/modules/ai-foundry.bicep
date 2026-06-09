// Azure AI Foundry Module — Account + Project + Capability Host
// Based on foundry-samples/15-private-network-standard-agent-setup
// Uses Microsoft.CognitiveServices/accounts with allowProjectManagement
// Projects are child resources; capability host enables Agent execution

@description('Azure region for resources')
param location string

@description('Name of the AI Services account')
param aiServicesName string

@description('Name of the AI Project (child of account)')
param aiProjectName string

@description('Resource ID of the agent subnet for network injection')
param agentSubnetId string

@description('Enable agent network injection into the agent subnet')
param enableNetworkInjection bool = true

@description('Enable public network access')
param publicNetworkAccess string = 'Disabled'

@description('SKU for AI Services')
param aiServicesSku string = 'S0'

@description('Model deployments configuration')
param modelDeployments array = [
  {
    name: 'gpt-4o'
    model: 'gpt-4o'
    version: '2024-08-06'
    capacity: 10
  }
  {
    name: 'gpt-4o-mini'
    model: 'gpt-4o-mini'
    version: '2024-07-18'
    capacity: 10
  }
  {
    name: 'text-embedding-3-large'
    model: 'text-embedding-3-large'
    version: '1'
    capacity: 10
  }
]

@description('Tags to apply to resources')
param tags object = {}

// --- Connection dependency names (used for output only) ---

@description('Cosmos DB account name')
param cosmosDbName string

@description('Storage account name')
param storageAccountName string

@description('AI Search service name (optional)')
param aiSearchName string = ''

@description('Name for the project capability host')
param capabilityHostName string = 'caphost-agents'

// ============================================================================
// AI Services Account — with project management enabled
// ============================================================================

#disable-next-line BCP036
resource aiServices 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' = {
  name: aiServicesName
  location: location
  tags: tags
  kind: 'AIServices'
  sku: {
    name: aiServicesSku
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    allowProjectManagement: true
    customSubDomainName: aiServicesName
    networkAcls: {
      defaultAction: 'Deny'
      virtualNetworkRules: []
      ipRules: []
      bypass: 'AzureServices'
    }
    publicNetworkAccess: publicNetworkAccess
    networkInjections: enableNetworkInjection
      ? [
          {
            scenario: 'agent'
            subnetArmId: agentSubnetId
            useMicrosoftManagedNetwork: false
          }
        ]
      : null
    disableLocalAuth: false
  }
}

// Model Deployments — deployed sequentially to avoid conflicts
@batchSize(1)
#disable-next-line BCP081
resource deployments 'Microsoft.CognitiveServices/accounts/deployments@2025-04-01-preview' = [
  for deployment in modelDeployments: {
    parent: aiServices
    name: deployment.name
    sku: {
      name: 'Standard'
      capacity: deployment.capacity
    }
    properties: {
      model: {
        format: 'OpenAI'
        name: deployment.model
        version: deployment.version
      }
      versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
      raiPolicyName: 'Microsoft.DefaultV2'
    }
  }
]

// ============================================================================
// AI Foundry Project — child of the AI Services account
// ============================================================================

#disable-next-line BCP081
resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' = {
  parent: aiServices
  name: aiProjectName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    description: 'Healthcare MCP AI Project for agents and workflows'
    displayName: 'Healthcare MCP AI Project'
  }
}


// NOTE: Connections and capability host are deployed in main.bicep AFTER role
// assignments are created, since they require the project's managed identity
// to already have RBAC permissions.

// ============================================================================
// Outputs
// ============================================================================

output aiServicesId string = aiServices.id
output aiServicesName string = aiServices.name
#disable-next-line BCP053
output aiServicesEndpoint string = aiServices.properties.endpoint
output aiServicesPrincipalId string = aiServices.identity.principalId
output aiProjectId string = aiProject.id
output aiProjectName string = aiProject.name
output aiProjectPrincipalId string = aiProject.identity.principalId
#disable-next-line BCP053
output aiProjectWorkspaceId string = aiProject.properties.internalId
output capabilityHostName string = capabilityHostName

// Connection names for downstream role assignment modules
output cosmosDbConnectionName string = cosmosDbName
output storageConnectionName string = storageAccountName
output aiSearchConnectionName string = !empty(aiSearchName) ? aiSearchName : ''
