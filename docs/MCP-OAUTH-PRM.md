# MCP OAuth with Protected Resource Metadata (PRM)

This document describes the OAuth 2.0 implementation for Healthcare MCP servers using the Protected Resource Metadata (PRM) pattern as defined in [RFC 9728](https://www.rfc-editor.org/rfc/rfc9728.html).

## Overview

The PRM pattern enables MCP clients (like VS Code) to automatically discover OAuth configuration without manual setup. When VS Code connects to an HTTP MCP server, it:

1. Fetches `/.well-known/oauth-protected-resource` from the server
2. Discovers the authorization server, scopes, and token delivery method
3. Initiates OAuth flow with the user's Microsoft account
4. Attaches the access token to subsequent MCP requests

## Architecture

```
┌─────────────────┐     ┌─────────────────────────────────────────┐
│   VS Code       │     │            Azure APIM                   │
│   MCP Client    │────►│                                         │
│                 │     │  /.well-known/oauth-protected-resource  │
│                 │◄────│  (Returns OAuth discovery info)         │
└────────┬────────┘     │                                         │
         │              │  /mcp/npi/mcp                           │
         │  OAuth       │  /mcp/icd10/mcp                         │
         │  Flow        │  /mcp/cms/mcp                           │
         ▼              │  (Validates Azure AD tokens)            │
┌─────────────────┐     │                                         │
│  Microsoft      │     └─────────────────────────────────────────┘
│  Entra ID       │                        │
│  (login.ms)     │                        │ Backend routing
└─────────────────┘                        ▼
                        ┌─────────────────────────────────────────┐
                        │       Azure Function Apps               │
                        │  (NPI, ICD-10, CMS, FHIR, etc.)         │
                        └─────────────────────────────────────────┘
```

## Components

### 1. Entra ID App Registration (`mcp-entra-app.bicep`)

Creates an application registration with:
- **OAuth2 Permission Scope**: `user_impersonate` for delegated access
- **Pre-authorized Client**: VS Code's client ID (`aebc6443-996d-45c2-90f0-388ff96faa56`)
- **Federated Identity Credential**: Uses Managed Identity instead of client secrets

### 2. User-Assigned Managed Identity (`mcp-user-identity.bicep`)

A managed identity that:
- Acts as a credential for the Entra app (no secrets to manage)
- Enables secure token exchange via federated credentials

### 3. PRM Policy (`mcp-prm.policy.xml`)

APIM policy that returns Protected Resource Metadata:

```json
{
  "resource": "https://your-apim.azure-api.net",
  "authorization_servers": [
    "https://login.microsoftonline.com/{tenant}/v2.0"
  ],
  "bearer_methods_supported": ["header"],
  "scopes_supported": ["{client-id}/user_impersonate"]
}
```

### 4. API Policy (`mcp-api.policy.xml`)

APIM policy that:
- Validates Azure AD JWT tokens on all MCP requests
- Returns 401 with `WWW-Authenticate` header pointing to PRM endpoint on auth failure

## Deployment

### Prerequisites

- Azure CLI with Bicep extension
- Azure subscription with permissions to:
  - Create APIM, Function Apps, VNet
  - Register Entra ID applications
  - Create Managed Identities

### Deploy Infrastructure

```bash
# Navigate to deploy folder
cd deploy/infra

# Deploy with Azure CLI
az deployment group create \
  --resource-group your-rg \
  --template-file main.bicep \
  --parameters @main.bicepparam
```

### Required Parameters

| Parameter | Description |
|-----------|-------------|
| `baseName` | Base name for all resources |
| `location` | Azure region |
| `apimPublisherEmail` | Email for APIM publisher |
| `mcpEntraAppDisplayName` | Display name for Entra app (optional) |

### Outputs

After deployment, note these outputs:
- `mcpClientId` - Entra app client ID
- `mcpTenantId` - Azure AD tenant ID
- `mcpPrmEndpoint` - PRM discovery URL
- `apimGatewayUrl` - APIM gateway base URL

## VS Code Configuration

After deploying with PRM, the `.vscode/mcp.json` is simplified:

```json
{
  "servers": {
    "healthcare-npi-lookup": {
      "type": "http",
      "url": "https://your-apim.azure-api.net/mcp/npi/mcp"
    }
  }
}
```

No headers or subscription keys needed - VS Code handles OAuth automatically.

## Testing

### 1. Verify PRM Endpoint

```bash
curl https://your-apim.azure-api.net/mcp/.well-known/oauth-protected-resource
```

Should return:
```json
{
  "resource": "https://your-apim.azure-api.net",
  "authorization_servers": ["https://login.microsoftonline.com/xxx/v2.0"],
  "bearer_methods_supported": ["header"],
  "scopes_supported": ["xxx/user_impersonate"]
}
```

### 2. Test OAuth Flow

1. Open VS Code Command Palette (`Ctrl+Shift+P`)
2. Run `MCP: List Servers`
3. VS Code will prompt for Microsoft sign-in
4. After authentication, MCP servers should be available

### 3. Test MCP Tools

In GitHub Copilot Chat:
```
Use the healthcare-npi-lookup tool to search for cardiologists in New York
```

## Security Considerations

1. **No Client Secrets**: Uses Federated Identity Credentials instead of secrets
2. **Pre-authorized Client**: Only VS Code can acquire tokens without consent prompts
3. **Token Validation**: APIM validates JWT tokens before routing to backends
4. **User Delegation**: Access is scoped to the authenticated user's permissions

## Troubleshooting

### "Dynamic discovery not supported"
- Ensure the PRM endpoint is deployed and accessible
- Verify `subscriptionRequired: false` on the OAuth API

### 401 Unauthorized after sign-in
- Check that VS Code's client ID is pre-authorized in Entra app
- Verify the audience in token validation matches the client ID

### "Consent required" errors
- Admin consent may be needed for the organization
- Visit Azure Portal > Entra ID > App registrations > API permissions

## References

- [RFC 9728 - Protected Resource Metadata](https://www.rfc-editor.org/rfc/rfc9728.html)
- [MCP Authorization Specification](https://modelcontextprotocol.io/specification/draft/basic/authorization)
- [Azure APIM validate-azure-ad-token](https://learn.microsoft.com/azure/api-management/validate-azure-ad-token-policy)
- [Reference Implementation](https://github.com/blackchoey/remote-mcp-apim-oauth-prm)
