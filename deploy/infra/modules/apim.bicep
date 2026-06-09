// Azure API Management Standard v2 Module
// Configured for private VNet integration with backend Function Apps

@description('Azure region for APIM')
param location string

@description('Name of the API Management instance')
param apimName string

@description('Publisher email address')
param publisherEmail string

@description('Publisher organization name')
param publisherName string

@description('SKU of the API Management instance - Standard v2 required for Foundry agents')
@allowed([
  'StandardV2'
  'Premium'
])
param skuName string = 'StandardV2'

@description('Capacity of the API Management instance')
@minValue(1)
@maxValue(10)
param skuCapacity int = 1

@description('Resource ID of the VNet (reserved for future VNet peering)')
#disable-next-line no-unused-params
param vnetId string

@description('Resource ID of the APIM subnet for VNet integration')
param apimSubnetId string

@description('Enable public network access')
param publicNetworkAccess string = 'Enabled'

@description('Application Insights resource ID')
param appInsightsId string = ''

@description('Application Insights Instrumentation Key')
param appInsightsInstrumentationKey string = ''

@description('Log Analytics Workspace resource ID for diagnostic settings')
param logAnalyticsId string = ''

@description('Tags to apply to resources')
param tags object = {}

resource apim 'Microsoft.ApiManagement/service@2023-09-01-preview' = {
  name: apimName
  location: location
  tags: tags
  sku: {
    name: skuName
    capacity: skuCapacity
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    publisherEmail: publisherEmail
    publisherName: publisherName
    publicNetworkAccess: publicNetworkAccess
    virtualNetworkType: 'External'
    virtualNetworkConfiguration: {
      subnetResourceId: apimSubnetId
    }
    apiVersionConstraint: {
      minApiVersion: '2021-08-01'
    }
    customProperties: {
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Ciphers.TLS_ECDHE_RSA_WITH_AES_256_CBC_SHA': 'false'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Ciphers.TLS_ECDHE_RSA_WITH_AES_128_CBC_SHA': 'false'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Ciphers.TLS_RSA_WITH_AES_128_GCM_SHA256': 'false'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Ciphers.TLS_RSA_WITH_AES_256_CBC_SHA256': 'false'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Ciphers.TLS_RSA_WITH_AES_128_CBC_SHA256': 'false'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Ciphers.TLS_RSA_WITH_AES_256_CBC_SHA': 'false'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Ciphers.TLS_RSA_WITH_AES_128_CBC_SHA': 'false'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Ciphers.TripleDes168': 'false'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Protocols.Tls10': 'false'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Protocols.Tls11': 'false'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Protocols.Ssl30': 'false'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Backend.Protocols.Tls10': 'false'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Backend.Protocols.Tls11': 'false'
      'Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Backend.Protocols.Ssl30': 'false'
    }
  }
}

// Named values for MCP server configuration
resource namedValueMcpVersion 'Microsoft.ApiManagement/service/namedValues@2023-09-01-preview' = {
  parent: apim
  name: 'mcp-protocol-version'
  properties: {
    displayName: 'mcp-protocol-version'
    value: '2025-06-18'
  }
}

// ============================================================================
// NOTE: API definitions, operations, and policies are managed in apim-mcp-oauth.bicep
// This module only creates the APIM service and base product configuration.
// The OAuth module adds proper token validation and function key authentication
// ============================================================================

// ============================================================================
// Application Insights Logger for APIM
// Enables request/response telemetry and audit traceability
// ============================================================================

resource apimLogger 'Microsoft.ApiManagement/service/loggers@2023-09-01-preview' = if (!empty(appInsightsInstrumentationKey)) {
  parent: apim
  name: 'appinsights-logger'
  properties: {
    loggerType: 'applicationInsights'
    description: 'Application Insights logger for audit traceability'
    credentials: {
      instrumentationKey: appInsightsInstrumentationKey
    }
    resourceId: appInsightsId
  }
}

// Enable Application Insights diagnostics on all APIM APIs
resource apimDiagnosticsAppInsights 'Microsoft.ApiManagement/service/diagnostics@2023-09-01-preview' = if (!empty(appInsightsInstrumentationKey)) {
  parent: apim
  name: 'applicationinsights'
  properties: {
    alwaysLog: 'allErrors'
    loggerId: apimLogger.id
    logClientIp: true
    httpCorrelationProtocol: 'W3C'
    verbosity: 'information'
    operationNameFormat: 'Url'
    sampling: {
      samplingType: 'fixed'
      percentage: 100
    }
    frontend: {
      request: {
        headers: ['Authorization', 'Content-Type', 'X-Forwarded-For']
        body: { bytes: 8192 }
      }
      response: {
        headers: ['Content-Type', 'WWW-Authenticate']
        body: { bytes: 8192 }
      }
    }
    backend: {
      request: {
        headers: ['Content-Type']
        body: { bytes: 8192 }
      }
      response: {
        headers: ['Content-Type']
        body: { bytes: 8192 }
      }
    }
  }
}

// ============================================================================
// Diagnostic Settings - Send APIM platform logs to Log Analytics
// Provides audit trail for gateway events, management operations, and WebSocket logs
// ============================================================================

resource apimDiagnosticSettings 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = if (!empty(logAnalyticsId)) {
  name: 'apim-audit-diagnostics'
  scope: apim
  properties: {
    workspaceId: logAnalyticsId
    logs: [
      {
        categoryGroup: 'audit'
        enabled: true
      }
      {
        categoryGroup: 'allLogs'
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
}

output apimId string = apim.id
output apimName string = apim.name
output apimGatewayUrl string = apim.properties.gatewayUrl
output apimManagementUrl string = apim.properties.managementApiUrl
output apimPrincipalId string = apim.identity.principalId
