// ============================================================================
// MCP Entra App Registration with Federated Identity Credential
// Implements OAuth 2.0 for VS Code MCP client using Protected Resource Metadata
// ============================================================================

extension microsoftGraphV1

@description('Unique name for the MCP Entra application')
param mcpAppUniqueName string

@description('Display name of the MCP Entra application')
param mcpAppDisplayName string

@description('Tenant ID where the application is registered')
param tenantId string = tenant().tenantId

@description('Principal ID of the user-assigned managed identity for federated credential')
param userAssignedIdentityPrincipalId string

@description('APIM gateway URL for callback configuration')
param apimGatewayUrl string

// Entra ID login endpoint and issuer
var loginEndpoint = environment().authentication.loginEndpoint
var issuer = '${loginEndpoint}${tenantId}/v2.0'

// ============================================================================
// MCP Entra Application Registration
// ============================================================================

resource mcpEntraApp 'Microsoft.Graph/applications@v1.0' = {
  displayName: mcpAppDisplayName
  uniqueName: mcpAppUniqueName

  api: {
    oauth2PermissionScopes: [
      {
        id: guid(mcpAppUniqueName, 'user_impersonate')
        adminConsentDescription: 'Allows the application to access Healthcare MCP resources on behalf of the signed-in user'
        adminConsentDisplayName: 'Access Healthcare MCP resources'
        isEnabled: true
        type: 'User'
        userConsentDescription: 'Allows the app to access Healthcare MCP resources on your behalf'
        userConsentDisplayName: 'Access Healthcare MCP resources'
        value: 'user_impersonate'
      }
    ]
    requestedAccessTokenVersion: 2

    // Pre-authorize VS Code's client ID for seamless OAuth flow
    preAuthorizedApplications: [
      {
        // VS Code's client ID - allows VS Code to acquire tokens without additional consent
        appId: 'aebc6443-996d-45c2-90f0-388ff96faa56'
        delegatedPermissionIds: [
          guid(mcpAppUniqueName, 'user_impersonate')
        ]
      }
    ]
  }

  // Required API permissions (Microsoft Graph - User.Read for basic profile)
  requiredResourceAccess: [
    {
      resourceAppId: '00000003-0000-0000-c000-000000000000' // Microsoft Graph
      resourceAccess: [
        {
          id: 'e1fe6dd8-ba31-4d61-89e7-88639da4683d' // User.Read
          type: 'Scope'
        }
      ]
    }
  ]

  // SPA redirect URIs for OAuth callback
  spa: {
    redirectUris: [
      // VS Code redirect URIs
      'https://vscode.dev/redirect'
      'https://insiders.vscode.dev/redirect'
      // Local development
      'http://localhost'
    ]
  }

  // Web redirect for APIM callback (if needed)
  web: {
    redirectUris: [
      '${apimGatewayUrl}/auth/callback'
    ]
  }

  // Federated Identity Credential - Use Managed Identity instead of client secret
  resource federatedCredential 'federatedIdentityCredentials@v1.0' = {
    name: '${mcpEntraApp.uniqueName}/msiAsFic'
    description: 'Trust the user-assigned managed identity as a credential for the MCP app'
    audiences: [
      'api://AzureADTokenExchange'
    ]
    issuer: issuer
    subject: userAssignedIdentityPrincipalId
  }
}

// ============================================================================
// Service Principal for the Application
// ============================================================================

resource mcpServicePrincipal 'Microsoft.Graph/servicePrincipals@v1.0' = {
  appId: mcpEntraApp.appId
}

// ============================================================================
// Outputs
// ============================================================================

output mcpAppId string = mcpEntraApp.appId
output mcpAppObjectId string = mcpEntraApp.id
output mcpAppTenantId string = tenantId
output mcpScopeId string = guid(mcpAppUniqueName, 'user_impersonate')
