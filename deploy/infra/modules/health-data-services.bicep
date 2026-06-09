// Azure Health Data Services Module
// Deploys AHDS Workspace with FHIR R4 service for healthcare MCP integration

@description('Azure region for resources')
param location string

@description('Name for the AHDS workspace')
param workspaceName string

@description('Name for the FHIR service')
param fhirServiceName string

@description('Azure AD tenant ID for FHIR authentication')
param tenantId string = tenant().tenantId

@description('Enable public network access')
param publicNetworkAccess string = 'Disabled'

@description('CORS allowed origins')
param corsOrigins array = [
  'https://portal.azure.com'
]

@description('Tags to apply to resources')
param tags object = {}

// ============================================================================
// Azure Health Data Services Workspace
// ============================================================================

resource workspace 'Microsoft.HealthcareApis/workspaces@2023-11-01' = {
  name: workspaceName
  location: location
  tags: union(tags, {
    compliance: 'HIPAA'
  })
  properties: {
    publicNetworkAccess: publicNetworkAccess
  }
}

// ============================================================================
// FHIR R4 Service
// ============================================================================

resource fhirService 'Microsoft.HealthcareApis/workspaces/fhirservices@2023-11-01' = {
  parent: workspace
  name: fhirServiceName
  location: location
  kind: 'fhir-R4'
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    authenticationConfiguration: {
      authority: '${environment().authentication.loginEndpoint}${tenantId}'
      audience: 'https://${workspaceName}-${fhirServiceName}.fhir.azurehealthcareapis.com'
    }
    corsConfiguration: {
      origins: corsOrigins
      methods: ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']
      headers: ['*']
      allowCredentials: false
      maxAge: 600
    }
    publicNetworkAccess: publicNetworkAccess
  }
}

// ============================================================================
// Outputs
// ============================================================================

output workspaceId string = workspace.id
output workspaceName string = workspace.name
output fhirServiceId string = fhirService.id
output fhirServiceName string = fhirService.name
output fhirServerUrl string = 'https://${workspaceName}-${fhirServiceName}.fhir.azurehealthcareapis.com'
output fhirServicePrincipalId string = fhirService.identity.principalId
