// ============================================================================
// User-Assigned Managed Identity for MCP OAuth
// Used as Federated Identity Credential for the Entra App (no client secrets)
// ============================================================================

@description('Name of the user-assigned managed identity')
param identityName string

@description('Azure region for the identity')
param location string = resourceGroup().location

@description('Tags to apply to the resource')
param tags object = {}

// ============================================================================
// User-Assigned Managed Identity Resource
// ============================================================================

resource userAssignedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-07-31-preview' = {
  name: identityName
  location: location
  tags: tags
}

// ============================================================================
// Outputs
// ============================================================================

output identityId string = userAssignedIdentity.id
output identityName string = userAssignedIdentity.name
output identityPrincipalId string = userAssignedIdentity.properties.principalId
output identityClientId string = userAssignedIdentity.properties.clientId
