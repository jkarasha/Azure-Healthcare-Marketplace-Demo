// ============================================================================
// APIM MCP OAuth Configuration Module
// Configures a unified MCP API with OAuth protection and routing to Function Apps
// ============================================================================

@description('Name of the API Management service')
param apimServiceName string

@description('Client ID of the MCP Entra application')
param mcpAppId string

@description('Tenant ID of the MCP Entra application')
param mcpAppTenantId string

@description('Base name for function apps')
param functionAppBaseName string

// ============================================================================
// Reference existing APIM service and Function Apps
// ============================================================================

resource apimService 'Microsoft.ApiManagement/service@2023-09-01-preview' existing = {
  name: apimServiceName
}

var mcpServers = [
  {
    name: 'reference-data'
    backendId: 'reference-data-backend'
    funcAppName: '${functionAppBaseName}-mcp-reference-data-func'
    functionKeyName: 'reference-data-function-key'
  }
  {
    name: 'clinical-research'
    backendId: 'clinical-research-backend'
    funcAppName: '${functionAppBaseName}-mcp-clinical-research-func'
    functionKeyName: 'clinical-research-function-key'
  }
  {
    name: 'cosmos-rag'
    backendId: 'cosmos-rag-backend'
    funcAppName: '${functionAppBaseName}-cosmos-rag-func'
    functionKeyName: 'cosmos-rag-function-key'
  }
]

resource functionApps 'Microsoft.Web/sites@2023-12-01' existing = [for server in mcpServers: {
  name: server.funcAppName
}]

// ============================================================================
// Named Values for OAuth Configuration
// ============================================================================

resource mcpTenantIdNamedValue 'Microsoft.ApiManagement/service/namedValues@2023-09-01-preview' = {
  parent: apimService
  name: 'McpTenantId'
  properties: {
    displayName: 'McpTenantId'
    value: mcpAppTenantId
    secret: false
  }
}

resource mcpClientIdNamedValue 'Microsoft.ApiManagement/service/namedValues@2023-09-01-preview' = {
  parent: apimService
  name: 'McpClientId'
  properties: {
    displayName: 'McpClientId'
    value: mcpAppId
    secret: false
  }
}

resource apimGatewayUrlNamedValue 'Microsoft.ApiManagement/service/namedValues@2023-09-01-preview' = {
  parent: apimService
  name: 'APIMGatewayURL'
  properties: {
    displayName: 'APIMGatewayURL'
    value: apimService.properties.gatewayUrl
    secret: false
  }
}

// ============================================================================
// Protected Resource Metadata API (RFC 9728)
// Exposes:
// - /.well-known/oauth-protected-resource/{resource-path} (wildcard only)
// Root PRM removed to prevent passthrough clients from entering OAuth mode.
// ============================================================================

resource prmApi 'Microsoft.ApiManagement/service/apis@2023-09-01-preview' = {
  parent: apimService
  name: 'mcp-prm'
  properties: {
    displayName: 'MCP Protected Resource Metadata'
    description: 'OAuth discovery endpoints per RFC 9728'
    path: ''
    protocols: ['https']
    subscriptionRequired: false
  }
}

// NOTE: Root PRM operation (/.well-known/oauth-protected-resource) intentionally removed.
// It caused ALL clients (including passthrough /mcp-pt/) to discover OAuth metadata and
// enter OAuth mode even when only subscription-key auth is needed.
// The path-based wildcard (/.well-known/oauth-protected-resource/*) is sufficient for
// OAuth clients accessing /mcp/{server}/mcp paths per RFC 9728.

resource prmPathOperation 'Microsoft.ApiManagement/service/apis/operations@2023-09-01-preview' = {
  parent: prmApi
  name: 'oauth-protected-resource-path'
  properties: {
    displayName: 'Protected Resource Metadata (Path)'
    method: 'GET'
    urlTemplate: '/.well-known/oauth-protected-resource/*'
    description: 'Path-based OAuth discovery endpoint (RFC 9728 Section 3.1)'
  }
}

resource prmPathPolicy 'Microsoft.ApiManagement/service/apis/operations/policies@2023-09-01-preview' = {
  parent: prmPathOperation
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: loadTextContent('../policies/mcp-path-prm.policy.xml')
  }
  dependsOn: [apimGatewayUrlNamedValue, mcpTenantIdNamedValue, mcpClientIdNamedValue]
}

// ============================================================================
// Function Host Keys - Stored as APIM Named Values (Secret)
// ============================================================================

resource functionKeyNamedValues 'Microsoft.ApiManagement/service/namedValues@2023-09-01-preview' = [for (server, i) in mcpServers: {
  parent: apimService
  name: server.functionKeyName
  properties: {
    displayName: server.functionKeyName
    secret: true
    value: listKeys('${functionApps[i].id}/host/default', functionApps[i].apiVersion).functionKeys.default
  }
}]

// ============================================================================
// Backend Definitions - One per MCP server
// (routePrefix is "" so Function endpoints are at /mcp, /.well-known/mcp, /health)
// ============================================================================

resource mcpBackends 'Microsoft.ApiManagement/service/backends@2023-09-01-preview' = [for (server, i) in mcpServers: {
  parent: apimService
  name: server.backendId
  properties: {
    title: '${server.name} MCP Backend'
    description: 'Backend for MCP server: ${server.name}'
    url: 'https://${functionApps[i].properties.defaultHostName}'
    protocol: 'http'
    tls: {
      validateCertificateChain: true
      validateCertificateName: true
    }
  }
}]

// ============================================================================
// Unified MCP API
// All MCP servers accessible under /mcp/{server}/...
// Uses name 'mcp-oauth' to match existing API and enable updates
// ============================================================================

resource mcpApi 'Microsoft.ApiManagement/service/apis@2023-09-01-preview' = {
  parent: apimService
  name: 'mcp-oauth'
  properties: {
    displayName: 'Healthcare MCP Servers (OAuth)'
    description: 'Unified API for Healthcare MCP servers with OAuth protection'
    path: 'mcp'
    protocols: ['https']
    subscriptionRequired: false
  }
}

// ============================================================================
// PRM Discovery Endpoints (RFC 9728)
// ============================================================================

resource prmServerOperations 'Microsoft.ApiManagement/service/apis/operations@2023-09-01-preview' = [for server in mcpServers: {
  parent: mcpApi
  name: '${server.name}-prm'
  properties: {
    displayName: '${server.name} - Protected Resource Metadata'
    method: 'GET'
    urlTemplate: '/${server.name}/.well-known/oauth-protected-resource'
    description: 'OAuth discovery endpoint for MCP server (RFC 9728)'
  }
}]

resource prmServerPolicies 'Microsoft.ApiManagement/service/apis/operations/policies@2023-09-01-preview' = [for (server, i) in mcpServers: {
  parent: prmServerOperations[i]
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: loadTextContent('../policies/mcp-server-prm.policy.xml')
  }
  dependsOn: [apimGatewayUrlNamedValue, mcpTenantIdNamedValue, mcpClientIdNamedValue]
}]

resource prmEndpointOperations 'Microsoft.ApiManagement/service/apis/operations@2023-09-01-preview' = [for server in mcpServers: {
  parent: mcpApi
  name: '${server.name}-endpoint-prm'
  properties: {
    displayName: '${server.name} MCP - Protected Resource Metadata'
    method: 'GET'
    urlTemplate: '/${server.name}/mcp/.well-known/oauth-protected-resource'
    description: 'OAuth discovery at MCP endpoint path (RFC 9728)'
  }
}]

resource prmEndpointPolicies 'Microsoft.ApiManagement/service/apis/operations/policies@2023-09-01-preview' = [for (server, i) in mcpServers: {
  parent: prmEndpointOperations[i]
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: loadTextContent('../policies/mcp-endpoint-prm.policy.xml')
  }
  dependsOn: [apimGatewayUrlNamedValue, mcpTenantIdNamedValue, mcpClientIdNamedValue]
}]

// ============================================================================
// MCP Operations
// ============================================================================

resource mcpPostOperations 'Microsoft.ApiManagement/service/apis/operations@2023-09-01-preview' = [for server in mcpServers: {
  parent: mcpApi
  name: '${server.name}-mcp-post'
  properties: {
    displayName: '${server.name} - POST /mcp'
    method: 'POST'
    urlTemplate: '/${server.name}/mcp'
    description: 'MCP message endpoint'
  }
}]

resource mcpGetOperations 'Microsoft.ApiManagement/service/apis/operations@2023-09-01-preview' = [for server in mcpServers: {
  parent: mcpApi
  name: '${server.name}-mcp-get'
  properties: {
    displayName: '${server.name} - GET /mcp'
    method: 'GET'
    urlTemplate: '/${server.name}/mcp'
    description: 'MCP info endpoint'
  }
}]

resource wellKnownOperations 'Microsoft.ApiManagement/service/apis/operations@2023-09-01-preview' = [for server in mcpServers: {
  parent: mcpApi
  name: '${server.name}-wellknown-get'
  properties: {
    displayName: '${server.name} - GET /.well-known/mcp'
    method: 'GET'
    urlTemplate: '/${server.name}/.well-known/mcp'
    description: 'MCP discovery endpoint'
  }
}]

resource healthOperations 'Microsoft.ApiManagement/service/apis/operations@2023-09-01-preview' = [for server in mcpServers: {
  parent: mcpApi
  name: '${server.name}-health'
  properties: {
    displayName: '${server.name} - Health Check'
    method: 'GET'
    urlTemplate: '/${server.name}/health'
    description: 'Health check endpoint'
  }
}]

// Policies (OAuth + backend routing + function key)
resource mcpPostPolicies 'Microsoft.ApiManagement/service/apis/operations/policies@2023-09-01-preview' = [for (server, i) in mcpServers: {
  parent: mcpPostOperations[i]
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: replace(replace(replace('''
<policies>
  <inbound>
    <base />
    <validate-azure-ad-token tenant-id="{{McpTenantId}}" failed-validation-httpcode="401" failed-validation-error-message="Unauthorized">
      <audiences><audience>{{McpClientId}}</audience></audiences>
    </validate-azure-ad-token>
    <set-backend-service backend-id="__BACKEND_ID__" />
    <set-header name="x-functions-key" exists-action="override"><value>{{__KEY_NAME__}}</value></set-header>
    <rewrite-uri template="/mcp" copy-unmatched-params="false" />
  </inbound>
  <backend><base /></backend>
  <outbound><base /></outbound>
  <on-error>
    <choose>
      <when condition="@(context.LastError != null)">
        <return-response>
          <set-status code="401" reason="Unauthorized" />
          <set-header name="WWW-Authenticate" exists-action="override">
            <value>Bearer error="invalid_token", resource_metadata="{{APIMGatewayURL}}/.well-known/oauth-protected-resource/mcp/__SERVER_NAME__/mcp"</value>
          </set-header>
          <set-header name="Content-Type" exists-action="override"><value>application/json</value></set-header>
          <set-body>{"jsonrpc":"2.0","error":{"code":-32001,"message":"Authentication required. Please authenticate using OAuth 2.0."},"id":null}</set-body>
        </return-response>
      </when>
    </choose>
  </on-error>
</policies>
''', '__BACKEND_ID__', server.backendId), '__KEY_NAME__', server.functionKeyName), '__SERVER_NAME__', server.name)
  }
  dependsOn: [functionKeyNamedValues, mcpBackends, mcpTenantIdNamedValue, mcpClientIdNamedValue, apimGatewayUrlNamedValue]
}]

resource mcpGetPolicies 'Microsoft.ApiManagement/service/apis/operations/policies@2023-09-01-preview' = [for (server, i) in mcpServers: {
  parent: mcpGetOperations[i]
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: replace(replace(replace('''
<policies>
  <inbound>
    <base />
    <validate-azure-ad-token tenant-id="{{McpTenantId}}" failed-validation-httpcode="401" failed-validation-error-message="Unauthorized">
      <audiences><audience>{{McpClientId}}</audience></audiences>
    </validate-azure-ad-token>
    <set-backend-service backend-id="__BACKEND_ID__" />
    <set-header name="x-functions-key" exists-action="override"><value>{{__KEY_NAME__}}</value></set-header>
    <rewrite-uri template="/mcp" copy-unmatched-params="false" />
  </inbound>
  <backend><base /></backend>
  <outbound><base /></outbound>
  <on-error>
    <choose>
      <when condition="@(context.LastError != null)">
        <return-response>
          <set-status code="401" reason="Unauthorized" />
          <set-header name="WWW-Authenticate" exists-action="override">
            <value>Bearer error="invalid_token", resource_metadata="{{APIMGatewayURL}}/.well-known/oauth-protected-resource/mcp/__SERVER_NAME__/mcp"</value>
          </set-header>
          <set-header name="Content-Type" exists-action="override"><value>application/json</value></set-header>
          <set-body>{"jsonrpc":"2.0","error":{"code":-32001,"message":"Authentication required. Please authenticate using OAuth 2.0."},"id":null}</set-body>
        </return-response>
      </when>
    </choose>
  </on-error>
</policies>
''', '__BACKEND_ID__', server.backendId), '__KEY_NAME__', server.functionKeyName), '__SERVER_NAME__', server.name)
  }
  dependsOn: [functionKeyNamedValues, mcpBackends, mcpTenantIdNamedValue, mcpClientIdNamedValue, apimGatewayUrlNamedValue]
}]

resource wellKnownPolicies 'Microsoft.ApiManagement/service/apis/operations/policies@2023-09-01-preview' = [for (server, i) in mcpServers: {
  parent: wellKnownOperations[i]
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: replace(replace('''
<policies>
  <inbound>
    <base />
    <validate-azure-ad-token tenant-id="{{McpTenantId}}" failed-validation-httpcode="401" failed-validation-error-message="Unauthorized">
      <audiences><audience>{{McpClientId}}</audience></audiences>
    </validate-azure-ad-token>
    <set-backend-service backend-id="__BACKEND_ID__" />
    <set-header name="x-functions-key" exists-action="override"><value>{{__KEY_NAME__}}</value></set-header>
    <rewrite-uri template="/.well-known/mcp" copy-unmatched-params="false" />
  </inbound>
  <backend><base /></backend>
  <outbound><base /></outbound>
  <on-error><base /></on-error>
</policies>
''', '__BACKEND_ID__', server.backendId), '__KEY_NAME__', server.functionKeyName)
  }
  dependsOn: [functionKeyNamedValues, mcpBackends, mcpTenantIdNamedValue, mcpClientIdNamedValue]
}]

resource healthPolicies 'Microsoft.ApiManagement/service/apis/operations/policies@2023-09-01-preview' = [for (server, i) in mcpServers: {
  parent: healthOperations[i]
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: replace(replace('''
<policies>
  <inbound>
    <base />
    <validate-azure-ad-token tenant-id="{{McpTenantId}}" failed-validation-httpcode="401" failed-validation-error-message="Unauthorized">
      <audiences><audience>{{McpClientId}}</audience></audiences>
    </validate-azure-ad-token>
    <set-backend-service backend-id="__BACKEND_ID__" />
    <set-header name="x-functions-key" exists-action="override"><value>{{__KEY_NAME__}}</value></set-header>
    <rewrite-uri template="/health" copy-unmatched-params="false" />
  </inbound>
  <backend><base /></backend>
  <outbound><base /></outbound>
  <on-error><base /></on-error>
</policies>
''', '__BACKEND_ID__', server.backendId), '__KEY_NAME__', server.functionKeyName)
  }
  dependsOn: [functionKeyNamedValues, mcpBackends, mcpTenantIdNamedValue, mcpClientIdNamedValue]
}]

// ============================================================================
// Outputs
// ============================================================================

output prmEndpoint string = '${apimService.properties.gatewayUrl}/.well-known/oauth-protected-resource'
output mcpApiId string = mcpApi.id
output mcpApiName string = mcpApi.name
output mcpApiPath string = mcpApi.properties.path
