// Healthcare MCP Infrastructure - Main Orchestration
// Private network configuration with APIM Standard v2, Function Apps, and AI Foundry
// Based on foundry-samples/16-private-network-standard-agent-apim-setup-preview
targetScope = 'resourceGroup'

// ============================================================================
// PARAMETERS
// ============================================================================

@description('Azure region for all resources')
@allowed([
  'australiaeast'
  'eastus'
  'eastus2'
  'francecentral'
  'japaneast'
  'norwayeast'
  'southindia'
  'swedencentral'
  'uksouth'
  'westus'
  'westus3'
])
param location string

@description('Base name for all resources (will be used as prefix)')
@minLength(3)
@maxLength(15)
param baseName string

@description('Publisher email for APIM')
param apimPublisherEmail string

@description('Publisher name for APIM')
param apimPublisherName string = 'Healthcare MCP Platform'

@description('APIM SKU - Standard v2 required for Foundry agents')
@allowed([
  'StandardV2'
  'Premium'
])
param apimSku string = 'StandardV2'

@description('VNet address space')
param vnetAddressPrefix string = '192.168.0.0/16'

@description('Enable public network access for dependent resources')
param enablePublicAccess bool = false

@description('Enable private endpoint for AHDS FHIR service (currently disabled by default due AHDS Private Link instability)')
param enableFhirPrivateEndpoint bool = false

@description('Enable Cosmos DB public network access in addition to private endpoint access (recommended for local development only)')
param enableCosmosPublicAccess bool = true

@description('Azure Container Registry SKU for dockerized MCP server images')
@allowed([
  'Basic'
  'Standard'
  'Premium'
])
param containerRegistrySku string = 'Basic'

@description('Enable admin user on Azure Container Registry')
param containerRegistryAdminUserEnabled bool = false

@description('Model deployments for AI Foundry')
param modelDeployments array = [
  {
    name: 'gpt-4o'
    model: 'gpt-4o'
    version: '2024-08-06'
    capacity: 10
  }
  {
    name: 'gpt-5.4-mini'
    model: 'gpt-5.4-mini'
    sku: 'GlobalStandard'
    capacity: 10
  }
  {
    name: 'text-embedding-3-large'
    model: 'text-embedding-3-large'
    version: '1'
    capacity: 10
  }
]

@description('Tags to apply to all resources')
param tags object = {
  project: 'healthcare-mcp'
  environment: 'production'
  managedBy: 'bicep'
}

@description('Display name for the MCP Entra application')
param mcpEntraAppDisplayName string = 'Healthcare MCP API'

@description('Unique name for the MCP Entra application')
param mcpEntraAppUniqueName string = ''

@description('Optional: Override region for Cosmos DB if primary region has capacity issues')
@allowed([
  ''
  'australiaeast'
  'brazilsouth'
  'canadacentral'
  'centralus'
  'eastasia'
  'eastus'
  'eastus2'
  'francecentral'
  'germanywestcentral'
  'japaneast'
  'koreacentral'
  'northcentralus'
  'northeurope'
  'norwayeast'
  'southcentralus'
  'southeastasia'
  'swedencentral'
  'switzerlandnorth'
  'uksouth'
  'westcentralus'
  'westeurope'
  'westus'
  'westus2'
  'westus3'
])
param cosmosDbLocation string = ''

// ============================================================================
// VARIABLES
// ============================================================================

var uniqueSuffix = uniqueString(resourceGroup().id)
var publicNetworkAccess = enablePublicAccess ? 'Enabled' : 'Disabled'
var mcpAppUniqueName = empty(mcpEntraAppUniqueName) ? 'healthcare-mcp-${uniqueSuffix}' : mcpEntraAppUniqueName
var acrBaseName = toLower(replace(baseName, '-', ''))
var containerRegistryName = take('${acrBaseName}acr${uniqueSuffix}', 50)

// ============================================================================
// MODULES
// ============================================================================

// 1. Virtual Network with subnets
module vnet 'modules/vnet.bicep' = {
  name: 'vnet-deployment'
  params: {
    location: location
    vnetName: '${baseName}-vnet'
    vnetAddressPrefix: vnetAddressPrefix
    // Subnet prefixes are derived from vnetAddressPrefix using defaults in vnet module
    tags: tags
  }
}

// 2. Dependent Resources (Storage, Cosmos DB, App Insights)
module dependentResources 'modules/dependent-resources.bicep' = {
  name: 'dependent-resources-deployment'
  params: {
    location: location
    baseName: baseName
    cosmosDbLocation: empty(cosmosDbLocation) ? location : cosmosDbLocation
    publicNetworkAccess: publicNetworkAccess
    enableCosmosPublicAccess: enableCosmosPublicAccess
    tags: tags
  }
}

// 3. Azure Container Registry for dockerized MCP server images
module containerRegistry 'modules/container-registry.bicep' = {
  name: 'container-registry-deployment'
  params: {
    location: location
    registryName: containerRegistryName
    skuName: containerRegistrySku
    adminUserEnabled: containerRegistryAdminUserEnabled
    publicNetworkAccess: 'Enabled'
    tags: tags
  }
}

// 4. AI Foundry (AI Services Account + Project + Capability Host)
module aiFoundry 'modules/ai-foundry.bicep' = {
  name: 'ai-foundry-deployment'
  params: {
    location: location
    aiServicesName: '${baseName}-aiservices-${uniqueSuffix}'
    aiProjectName: '${baseName}-project-${uniqueSuffix}'
    agentSubnetId: vnet.outputs.agentSubnetId
    enableNetworkInjection: false
    publicNetworkAccess: publicNetworkAccess
    modelDeployments: modelDeployments
    // Connection dependency names (for outputs only — connections created in main.bicep)
    cosmosDbName: dependentResources.outputs.cosmosDbName
    storageAccountName: dependentResources.outputs.storageAccountName
    aiSearchName: dependentResources.outputs.aiSearchName
    tags: tags
  }
}

// 5. Azure Health Data Services (FHIR R4)
// Workspace name: max 24 chars, alphanumeric only, no reserved words ("healthcare","fhir","azure","microsoft")
// Use uniqueSuffix to build a compliant name (baseName may contain "healthcare" which is reserved)
var ahdsWorkspaceName = 'mcphds${uniqueSuffix}'
module healthDataServices 'modules/health-data-services.bicep' = {
  name: 'health-data-services-deployment'
  params: {
    location: location
    workspaceName: ahdsWorkspaceName
    fhirServiceName: 'mcp'
    // AHDS workspace requires public access Enabled during PE creation —
    // its Private Link Service returns InvalidResponse when publicNetworkAccess is Disabled.
    // The private endpoint still provides private connectivity; network rules restrict traffic.
    publicNetworkAccess: 'Enabled'
    tags: tags
  }
}

// 6. Function Apps for MCP Servers (container-based deployment)
module functionApps 'modules/function-apps.bicep' = {
  name: 'function-apps-deployment'
  params: {
    location: location
    baseName: baseName
    functionSubnetId: vnet.outputs.functionSubnetId
    apimSubnetId: vnet.outputs.apimSubnetId
    storageAccountId: dependentResources.outputs.storageAccountId
    storageAccountName: dependentResources.outputs.storageAccountName
    appInsightsInstrumentationKey: dependentResources.outputs.appInsightsInstrumentationKey
    appInsightsConnectionString: dependentResources.outputs.appInsightsConnectionString
    logAnalyticsId: dependentResources.outputs.logAnalyticsId
    fhirServerUrl: healthDataServices.outputs.fhirServerUrl
    acrLoginServer: containerRegistry.outputs.registryLoginServer
    cosmosDbEndpoint: dependentResources.outputs.cosmosDbEndpoint
    aiServicesEndpoint: aiFoundry.outputs.aiServicesEndpoint
    tags: tags
  }
}

// 7. API Management Standard v2
module apim 'modules/apim.bicep' = {
  name: 'apim-deployment'
  params: {
    location: location
    apimName: '${baseName}-apim-${uniqueSuffix}'
    publisherEmail: apimPublisherEmail
    publisherName: apimPublisherName
    skuName: apimSku
    vnetId: vnet.outputs.vnetId
    apimSubnetId: vnet.outputs.apimSubnetId
    appInsightsId: dependentResources.outputs.appInsightsId
    appInsightsInstrumentationKey: dependentResources.outputs.appInsightsInstrumentationKey
    logAnalyticsId: dependentResources.outputs.logAnalyticsId
    publicNetworkAccess: enablePublicAccess ? 'Enabled' : 'Enabled' // APIM needs external access for gateway
    tags: tags
  }
  dependsOn: [functionApps] // Ensure Function Apps exist before configuring backends
}

// 8. User-Assigned Managed Identity for MCP OAuth
module mcpUserIdentity 'modules/mcp-user-identity.bicep' = {
  name: 'mcp-user-identity-deployment'
  params: {
    identityName: '${baseName}-mcp-identity-${uniqueSuffix}'
    location: location
    tags: tags
  }
}

// 9. MCP Entra App Registration with Federated Identity Credential
module mcpEntraApp 'modules/mcp-entra-app.bicep' = {
  name: 'mcp-entra-app-deployment'
  params: {
    mcpAppUniqueName: mcpAppUniqueName
    mcpAppDisplayName: mcpEntraAppDisplayName
    userAssignedIdentityPrincipalId: mcpUserIdentity.outputs.identityPrincipalId
    apimGatewayUrl: apim.outputs.apimGatewayUrl
  }
}

// 10. APIM MCP OAuth Configuration (PRM endpoint + token validation)
module apimMcpOAuth 'modules/apim-mcp-oauth.bicep' = {
  name: 'apim-mcp-oauth-deployment'
  params: {
    apimServiceName: apim.outputs.apimName
    mcpAppId: mcpEntraApp.outputs.mcpAppId
    mcpAppTenantId: mcpEntraApp.outputs.mcpAppTenantId
    functionAppBaseName: baseName
  }
  dependsOn: [functionApps] // Ensure Function Apps exist for host key retrieval
}

// 10b. APIM MCP Passthrough (Lightweight debug - no OAuth, subscription key only)
module apimMcpPassthrough 'modules/apim-mcp-passthrough.bicep' = {
  name: 'apim-mcp-passthrough-deployment'
  params: {
    apimServiceName: apim.outputs.apimName
    functionAppBaseName: baseName
  }
  dependsOn: [functionApps]
}

// 10c. APIM Azure OpenAI v1 API (portal-captured configuration)
module apimAoaiV1 'modules/apim-aoai-v1.bicep' = {
  name: 'apim-aoai-v1-deployment'
  params: {
    apimServiceName: apim.outputs.apimName
    aiServicesName: aiFoundry.outputs.aiServicesName
  }
}

// 11. Private Endpoints for all services
// NOTE: FHIR private endpoint is opt-in only — AHDS Private Link can return
// InvalidResponseFromPrivateLinkService depending on subscription/region.
module privateEndpoints 'modules/private-endpoints.bicep' = {
  name: 'private-endpoints-deployment'
  params: {
    location: location
    vnetId: vnet.outputs.vnetId
    peSubnetId: vnet.outputs.peSubnetId
    aiServicesId: aiFoundry.outputs.aiServicesId
    aiSearchId: dependentResources.outputs.aiSearchId
    storageAccountId: dependentResources.outputs.storageAccountId
    cosmosDbId: dependentResources.outputs.cosmosDbId
    apimId: apim.outputs.apimId
    healthDataServicesWorkspaceId: enableFhirPrivateEndpoint ? healthDataServices.outputs.workspaceId : ''
    keyVaultId: dependentResources.outputs.keyVaultId
    uniqueSuffix: uniqueSuffix
    tags: tags
  }
}

// ============================================================================
// ROLE ASSIGNMENTS
// ============================================================================

// Storage Blob Data Contributor for AI Services
resource aiServicesStorageRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, aiServicesResourceName, 'storage-blob-contributor-v2')
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
    ) // Storage Blob Data Contributor
    principalId: aiFoundry.outputs.aiServicesPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Cognitive Services OpenAI User for APIM
resource apimOpenAIRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, '${baseName}-apim-v2', 'cognitive-services-openai-user-v2')
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'
    ) // Cognitive Services OpenAI User
    principalId: apim.outputs.apimPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// FHIR Data Contributor for Function Apps (allows MCP servers to access FHIR data)
// Assign to all MCP Function Apps for flexibility.
var mcpServerNames = [
  'mcp-reference-data'
  'mcp-clinical-research'
  'cosmos-rag'
]
var mcpServerCount = length(mcpServerNames)

resource containerRegistryResource 'Microsoft.ContainerRegistry/registries@2023-11-01-preview' existing = {
  name: containerRegistryName
}

resource fhirDataContributorRoles 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for i in range(0, mcpServerCount): {
    name: guid(resourceGroup().id, 'func-${i}-v3', 'fhir-data-contributor')
    scope: resourceGroup()
    properties: {
      roleDefinitionId: subscriptionResourceId(
        'Microsoft.Authorization/roleDefinitions',
        '5a1fc7df-4bf1-4951-a576-89034ee01acd'
      ) // FHIR Data Contributor
      principalId: functionApps.outputs.functionAppPrincipalIds[i]
      principalType: 'ServicePrincipal'
    }
  }
]

// AcrPull for Function Apps (required when MCP servers are deployed as container images)
resource acrPullRoles 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for i in range(0, mcpServerCount): {
    name: guid(resourceGroup().id, containerRegistryName, 'func-${i}-v3', 'acr-pull')
    scope: containerRegistryResource
    properties: {
      roleDefinitionId: subscriptionResourceId(
        'Microsoft.Authorization/roleDefinitions',
        '7f951dda-4ed3-4680-a7ca-43fe172d538d'
      ) // AcrPull
      principalId: functionApps.outputs.functionAppPrincipalIds[i]
      principalType: 'ServicePrincipal'
    }
  }
]

// Cosmos DB Built-in Data Contributor for Function Apps (allows MCP servers to read/write Cosmos DB)
// Role ID: 00000000-0000-0000-0000-000000000002 is the Cosmos DB Built-in Data Contributor
// We use the ARM role 'DocumentDB Account Contributor' (5bd9cd88-fe45-4216-938b-f97437e15450) at RG scope
// and additionally the Cosmos DB data-plane RBAC via SQL Role Assignment
resource cosmosDbDataContributorRoles 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for i in range(0, mcpServerCount): {
    name: guid(resourceGroup().id, 'func-${i}-v3', 'cosmos-data-contributor')
    scope: resourceGroup()
    properties: {
      roleDefinitionId: subscriptionResourceId(
        'Microsoft.Authorization/roleDefinitions',
        '5bd9cd88-fe45-4216-938b-f97437e15450'
      ) // DocumentDB Account Contributor
      principalId: functionApps.outputs.functionAppPrincipalIds[i]
      principalType: 'ServicePrincipal'
    }
  }
]

// --- AI Foundry Project Role Assignments ---

// Storage Blob Data Contributor for AI Project principal
resource projectStorageBlobRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, aiProjectResourceName, 'storage-blob-contributor-v2')
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
    ) // Storage Blob Data Contributor
    principalId: aiFoundry.outputs.aiProjectPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Cosmos DB Account Reader for AI Project principal (required for capability host)
resource projectCosmosReaderRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, aiProjectResourceName, 'cosmos-account-reader-v2')
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      'fbdf93bf-df7d-467e-a4d2-9458aa1360c8'
    ) // Cosmos DB Account Reader
    principalId: aiFoundry.outputs.aiProjectPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// DocumentDB Account Contributor for AI Project principal
resource projectCosmosContributorRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, aiProjectResourceName, 'cosmos-contributor-v2')
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '5bd9cd88-fe45-4216-938b-f97437e15450'
    ) // DocumentDB Account Contributor
    principalId: aiFoundry.outputs.aiProjectPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Search Index Data Contributor for AI Project principal (if AI Search deployed)
resource projectSearchRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, aiProjectResourceName, 'search-index-contributor-v2')
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '8ebe5a00-799e-43f5-93ac-243d3dce84a7'
    ) // Search Index Data Contributor
    principalId: aiFoundry.outputs.aiProjectPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Search Service Contributor for AI Project principal (if AI Search deployed)
resource projectSearchServiceRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(resourceGroup().id, aiProjectResourceName, 'search-service-contributor-v2')
  scope: resourceGroup()
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
    ) // Search Service Contributor
    principalId: aiFoundry.outputs.aiProjectPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Compile-time resource names (must not use module outputs for the 'name' property)
var aiServicesResourceName = '${baseName}-aiservices-${uniqueSuffix}'
var aiProjectResourceName = '${baseName}-project-${uniqueSuffix}'
var capabilityHostResourceName = 'caphost-agents'

// Connection resource names — must match the names used in dependent-resources.bicep
var cosmosDbResourceName = '${baseName}-cosmos-${uniqueSuffix}'
var storageBaseName = replace(baseName, '-', '')
var storageSuffix = 'st${uniqueString(resourceGroup().id)}'
var storageResourceName = take('${storageBaseName}${storageSuffix}', 24)
var aiSearchResourceName = toLower('${replace(baseName, '-', '')}search${uniqueSuffix}')

// ============================================================================
// EXISTING RESOURCE REFERENCES — for connections and capability host
// Using parent property with existing references per Bicep best practices.
// Ref: foundry-samples/41-standard-agent-setup
// ============================================================================

#disable-next-line BCP081
resource aiServicesExisting 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: aiServicesResourceName
}

#disable-next-line BCP081
resource aiProjectExisting 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' existing = {
  name: aiProjectResourceName
  parent: aiServicesExisting
}

// ============================================================================
// PROJECT CONNECTIONS — created AFTER role assignments, BEFORE capability host
// Following foundry-samples/15-private-network-standard-agent-setup pattern:
// connections are child resources of the project. The capability host references
// them by name, so they must exist first.
// Uses parent property with existing references per Bicep best practices.
// ============================================================================

// Cosmos DB connection — thread storage for agents
#disable-next-line BCP081
resource cosmosConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = {
  name: cosmosDbResourceName
  parent: aiProjectExisting
  properties: {
    category: 'CosmosDB'
    target: dependentResources.outputs.cosmosDbEndpoint
    authType: 'AAD'
    metadata: {
      ApiType: 'Azure'
      ResourceId: dependentResources.outputs.cosmosDbId
      location: dependentResources.outputs.cosmosDbLocation
    }
  }
  dependsOn: [
    aiFoundry
    projectCosmosReaderRole
    projectCosmosContributorRole
  ]
}

// Azure Storage connection — file storage for agents
#disable-next-line BCP081
resource storageConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = {
  name: storageResourceName
  parent: aiProjectExisting
  properties: {
    category: 'AzureStorageAccount'
    target: dependentResources.outputs.storageBlobEndpoint
    authType: 'AAD'
    metadata: {
      ApiType: 'Azure'
      ResourceId: dependentResources.outputs.storageAccountId
      location: location
    }
  }
  dependsOn: [
    aiFoundry
    projectStorageBlobRole
    aiServicesStorageRole
  ]
}

// AI Search connection — vector store for agents
#disable-next-line BCP081
resource searchConnection 'Microsoft.CognitiveServices/accounts/projects/connections@2025-04-01-preview' = {
  name: aiSearchResourceName
  parent: aiProjectExisting
  properties: {
    category: 'CognitiveSearch'
    target: 'https://${aiSearchResourceName}.search.windows.net'
    authType: 'AAD'
    metadata: {
      ApiType: 'Azure'
      ResourceId: dependentResources.outputs.aiSearchId
      location: location
    }
  }
  dependsOn: [
    aiFoundry
    projectSearchRole
    projectSearchServiceRole
  ]
}

// ============================================================================
// CAPABILITY HOSTS — deployed AFTER connections and role assignments
// Uses dedicated module following foundry-samples canonical pattern.
// Account-level capability host must exist before the project-level one.
// The project capability host references connections by name and requires the
// project principal to have Storage, Cosmos DB, and Search RBAC permissions.
// Ref: foundry-samples/41-standard-agent-setup/modules-standard/add-project-capability-host.bicep
// ============================================================================

module addProjectCapabilityHost 'modules/add-project-capability-host.bicep' = {
  name: 'capabilityHost-configuration-deployment'
  params: {
    accountName: aiServicesResourceName
    projectName: aiProjectResourceName
    projectCapHost: capabilityHostResourceName
    cosmosDBConnection: cosmosDbResourceName
    azureStorageConnection: storageResourceName
    aiSearchConnection: aiSearchResourceName
  }
  dependsOn: [
    aiFoundry
    dependentResources
    privateEndpoints           // PEs must exist first — caphost needs private connectivity to backing resources
    cosmosConnection
    storageConnection
    searchConnection
    projectCosmosReaderRole
    projectCosmosContributorRole
    projectStorageBlobRole
    aiServicesStorageRole
    projectSearchRole
    projectSearchServiceRole
  ]
}

// ============================================================================
// OUTPUTS
// ============================================================================

// Network
output vnetId string = vnet.outputs.vnetId
output vnetName string = vnet.outputs.vnetName
output agentSubnetId string = vnet.outputs.agentSubnetId
output peSubnetId string = vnet.outputs.peSubnetId
output apimSubnetId string = vnet.outputs.apimSubnetId
output functionSubnetId string = vnet.outputs.functionSubnetId

// APIM
output apimId string = apim.outputs.apimId
output apimName string = apim.outputs.apimName
output apimGatewayUrl string = apim.outputs.apimGatewayUrl
output apimManagementUrl string = apim.outputs.apimManagementUrl

// Azure Container Registry
output containerRegistryId string = containerRegistry.outputs.registryId
output containerRegistryName string = containerRegistry.outputs.registryName
output containerRegistryLoginServer string = containerRegistry.outputs.registryLoginServer

// MCP OAuth Configuration
output mcpClientId string = mcpEntraApp.outputs.mcpAppId
output mcpTenantId string = mcpEntraApp.outputs.mcpAppTenantId
output mcpPrmEndpoint string = apimMcpOAuth.outputs.prmEndpoint
output mcpIdentityId string = mcpUserIdentity.outputs.identityId
output mcpIdentityClientId string = mcpUserIdentity.outputs.identityClientId

// MCP Passthrough (Debug)
output mcpPassthroughApiPath string = apimMcpPassthrough.outputs.passthroughApiPath

// Azure OpenAI v1 API via APIM
output aoaiV1ApiPath string = apimAoaiV1.outputs.aoaiV1ApiPath
output aoaiV1ApiEndpoint string = '${apim.outputs.apimGatewayUrl}/${apimAoaiV1.outputs.aoaiV1ApiPath}'

// AI Foundry
output aiServicesId string = aiFoundry.outputs.aiServicesId
output aiServicesName string = aiFoundry.outputs.aiServicesName
output aiServicesEndpoint string = aiFoundry.outputs.aiServicesEndpoint
output aiProjectId string = aiFoundry.outputs.aiProjectId
output aiProjectName string = aiFoundry.outputs.aiProjectName
output aiProjectWorkspaceId string = aiFoundry.outputs.aiProjectWorkspaceId
output capabilityHostName string = aiFoundry.outputs.capabilityHostName

// Function Apps
output functionAppNames array = functionApps.outputs.functionAppNames
output mcpServerEndpoints array = functionApps.outputs.mcpServerEndpoints

// Azure Health Data Services
output fhirServiceId string = healthDataServices.outputs.fhirServiceId
output fhirServerUrl string = healthDataServices.outputs.fhirServerUrl
output ahdsWorkspaceName string = healthDataServices.outputs.workspaceName

// Dependent Resources
output storageAccountId string = dependentResources.outputs.storageAccountId
output storageAccountName string = dependentResources.outputs.storageAccountName
output cosmosDbId string = dependentResources.outputs.cosmosDbId
output cosmosDbEndpoint string = dependentResources.outputs.cosmosDbEndpoint
output appInsightsId string = dependentResources.outputs.appInsightsId
output appInsightsConnectionString string = dependentResources.outputs.appInsightsConnectionString

// ============================================================================
// AZD-SPECIFIC OUTPUTS
// These outputs are used by Azure Developer CLI for service discovery
// Format: SERVICE_<service-name-upper>_<property>
// ============================================================================

// APIM Gateway URL for MCP endpoints
output SERVICE_APIM_GATEWAY_URL string = apim.outputs.apimGatewayUrl

// AI Services endpoint
output SERVICE_AI_SERVICES_ENDPOINT string = aiFoundry.outputs.aiServicesEndpoint

// Resource Group name (for azd)
output AZURE_RESOURCE_GROUP string = resourceGroup().name

// Azure Container Registry outputs for azd dockerized service deployment
output AZURE_CONTAINER_REGISTRY_NAME string = containerRegistry.outputs.registryName
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = containerRegistry.outputs.registryLoginServer

// Function App resource names for azd-based container deployment
// Output names must match: SERVICE_<service-name-with-underscores>_RESOURCE_NAME
output SERVICE_MCP_REFERENCE_DATA_RESOURCE_NAME string = functionApps.outputs.functionAppNames[0]
output SERVICE_MCP_CLINICAL_RESEARCH_RESOURCE_NAME string = functionApps.outputs.functionAppNames[1]
output SERVICE_COSMOS_RAG_RESOURCE_NAME string = functionApps.outputs.functionAppNames[2]
