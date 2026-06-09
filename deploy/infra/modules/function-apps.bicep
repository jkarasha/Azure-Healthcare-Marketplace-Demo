// Function Apps Module for Healthcare MCP Servers
// Hosts MCP servers in VNet-integrated Function Apps

@description('Azure region for resources')
param location string

@description('Base name for resources')
param baseName string

@description('Resource ID of the Function App subnet for VNet integration')
param functionSubnetId string

@description('Resource ID of the Storage Account for Function Apps (for reference)')
#disable-next-line no-unused-params
param storageAccountId string

@description('Storage Account name')
param storageAccountName string

@description('Application Insights Instrumentation Key')
param appInsightsInstrumentationKey string = ''

@description('Application Insights Connection String')
param appInsightsConnectionString string = ''

@description('ACR login server for pulling container images')
param acrLoginServer string

@description('Resource ID of the APIM subnet to allow traffic from')
param apimSubnetId string = ''

@description('Log Analytics Workspace resource ID for diagnostic settings')
param logAnalyticsId string = ''

@description('Tags to apply to resources')
param tags object = {}

@description('FHIR Server URL from Azure Health Data Services')
param fhirServerUrl string = ''

@description('Cosmos DB endpoint for RAG and audit trail operations')
param cosmosDbEndpoint string = ''

@description('Azure AI Services endpoint for embeddings')
param aiServicesEndpoint string = ''

// Get storage account reference
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}

// App Service Plan for Function Apps (Elastic Premium for VNet integration)
resource appServicePlan 'Microsoft.Web/serverfarms@2023-12-01' = {
  name: '${baseName}-asp'
  location: location
  tags: tags
  kind: 'elastic'
  sku: {
    name: 'EP1'
    tier: 'ElasticPremium'
    family: 'EP'
  }
  properties: {
    reserved: true // Linux
    maximumElasticWorkerCount: 20
  }
}

// MCP Server configurations (consolidated)
// 3 servers: reference-data (NPI+ICD10+CMS), clinical-research (FHIR+PubMed+Trials), cosmos-rag
var mcpServers = [
  {
    name: 'mcp-reference-data'
    displayName: 'Reference Data MCP Server (NPI + ICD-10 + CMS)'
    extraSettings: []
  }
  {
    name: 'mcp-clinical-research'
    displayName: 'Clinical Research MCP Server (FHIR + PubMed + Trials)'
    extraSettings: [
      {
        name: 'FHIR_SERVER_URL'
        value: fhirServerUrl
      }
      {
        name: 'NCBI_API_KEY'
        value: ''
      }
    ]
  }
  {
    name: 'cosmos-rag'
    displayName: 'Cosmos DB RAG & Audit MCP Server'
    extraSettings: [
      {
        name: 'COSMOS_DB_ENDPOINT'
        value: cosmosDbEndpoint
      }
      {
        name: 'COSMOS_DB_DATABASE'
        value: 'healthcare-mcp'
      }
      {
        name: 'AZURE_AI_SERVICES_ENDPOINT'
        value: aiServicesEndpoint
      }
      {
        name: 'EMBEDDING_DEPLOYMENT_NAME'
        value: 'text-embedding-3-large'
      }
      {
        name: 'EMBEDDING_DIMENSIONS'
        value: '3072'
      }
    ]
  }
]

// Create Function Apps for each MCP server
resource functionApps 'Microsoft.Web/sites@2023-12-01' = [for server in mcpServers: {
  name: '${baseName}-${server.name}-func'
  location: location
  tags: union(tags, {
    'hidden-link: /app-insights-resource-id': appInsightsConnectionString
    mcpServer: server.name
    'azd-service-name': server.name
  })
  kind: 'functionapp,linux,container'
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    virtualNetworkSubnetId: functionSubnetId
    publicNetworkAccess: 'Enabled'
    siteConfig: {
      // Placeholder image — azd replaces this during `azd deploy` with the
      // actual ACR image tag built from the per-service Dockerfile.
      linuxFxVersion: 'DOCKER|mcr.microsoft.com/azure-functions/python:4-python3.11'
      acrUseManagedIdentityCreds: true
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      http20Enabled: true
      vnetRouteAllEnabled: true
      // Separate SCM restrictions from main site
      scmIpSecurityRestrictionsUseMain: false
      // Main site: Only allow traffic from APIM subnet
      ipSecurityRestrictions: !empty(apimSubnetId) ? [
        {
          name: 'AllowAPIM'
          description: 'Allow traffic from APIM subnet only'
          action: 'Allow'
          priority: 100
          vnetSubnetResourceId: apimSubnetId
        }
        {
          name: 'DenyAll'
          description: 'Deny all other traffic'
          action: 'Deny'
          priority: 2147483647
          ipAddress: 'Any'
        }
      ] : []
      // SCM site: Allow public access for azd deployment
      scmIpSecurityRestrictions: [
        {
          name: 'AllowAll'
          description: 'Allow deployment from anywhere (azd, GitHub Actions, etc.)'
          action: 'Allow'
          priority: 100
          ipAddress: 'Any'
        }
      ]
      appSettings: union([
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'AzureWebJobsStorage'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccountName};EndpointSuffix=${environment().suffixes.storage};AccountKey=${storageAccount.listKeys().keys[0].value}'
        }
        {
          name: 'APPINSIGHTS_INSTRUMENTATIONKEY'
          value: appInsightsInstrumentationKey
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsightsConnectionString
        }
        {
          name: 'MCP_SERVER_NAME'
          value: server.name
        }
        {
          name: 'MCP_PROTOCOL_VERSION'
          value: '2025-06-18'
        }
        {
          name: 'DOCKER_REGISTRY_SERVER_URL'
          value: 'https://${acrLoginServer}'
        }
        {
          name: 'WEBSITES_ENABLE_APP_SERVICE_STORAGE'
          value: 'false'
        }
        {
          name: 'WEBSITE_VNET_ROUTE_ALL'
          value: '1'
        }
        {
          name: 'WEBSITE_DNS_SERVER'
          value: '168.63.129.16'
        }
      ], server.extraSettings)
      cors: {
        allowedOrigins: [
          'https://portal.azure.com'
        ]
        supportCredentials: false
      }
    }
  }
}]

// ============================================================================
// Diagnostic Settings - Send Function App logs to Log Analytics
// Linux Elastic Premium only supports FunctionAppLogs category
// App Insights SDK (configured via app settings) captures HTTP/request telemetry
// ============================================================================

resource functionAppDiagnostics 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = [for (server, i) in mcpServers: if (!empty(logAnalyticsId)) {
  name: '${server.name}-audit-diagnostics'
  scope: functionApps[i]
  properties: {
    workspaceId: logAnalyticsId
    logs: [
      {
        category: 'FunctionAppLogs'
        enabled: true
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
  }
}]

// Output function app details
output functionAppIds array = [for (server, i) in mcpServers: functionApps[i].id]
output functionAppNames array = [for (server, i) in mcpServers: functionApps[i].name]
output functionAppHostnames array = [for (server, i) in mcpServers: functionApps[i].properties.defaultHostName]
output functionAppPrincipalIds array = [for (server, i) in mcpServers: functionApps[i].identity.principalId]
output appServicePlanId string = appServicePlan.id

// Output for APIM backend configuration - Function Apps expose MCP endpoints at root level
output mcpServerEndpoints array = [for (server, i) in mcpServers: {
  name: server.name
  displayName: server.displayName
  backendUrl: 'https://${functionApps[i].properties.defaultHostName}'
}]
