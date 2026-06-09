// ============================================================================
// APIM MCP Passthrough Configuration Module (Lightweight - No OAuth)
//
// PURPOSE: Establish and verify APIM → Function App backend connectivity
// before layering on OAuth/PRM complexity.
//
// Security: APIM subscription key (front-door) + Function key (backend)
// No OAuth validation, no PRM endpoints, minimal policy.
// ============================================================================

@description('Name of the API Management service')
param apimServiceName string

@description('Base name for function apps')
param functionAppBaseName string

// ============================================================================
// Reference existing APIM service
// ============================================================================

resource apimService 'Microsoft.ApiManagement/service@2023-09-01-preview' existing = {
  name: apimServiceName
}

// ============================================================================
// Server configuration array (consolidated)
// ============================================================================

var funcAppApiVersion = '2023-12-01'

var mcpServers = [
  {
    name: 'reference-data'
    backendName: 'reference-data-pt'
    funcName: '${functionAppBaseName}-mcp-reference-data-func'
    funcHostName: '${functionAppBaseName}-mcp-reference-data-func.azurewebsites.net'
    keyName: 'reference-data-pt-key'
  }
  {
    name: 'clinical-research'
    backendName: 'clinical-research-pt'
    funcName: '${functionAppBaseName}-mcp-clinical-research-func'
    funcHostName: '${functionAppBaseName}-mcp-clinical-research-func.azurewebsites.net'
    keyName: 'clinical-research-pt-key'
  }
  {
    name: 'cosmos-rag'
    backendName: 'cosmos-rag-pt'
    funcName: '${functionAppBaseName}-cosmos-rag-func'
    funcHostName: '${functionAppBaseName}-cosmos-rag-func.azurewebsites.net'
    keyName: 'cosmos-rag-pt-key'
  }
]

// ============================================================================
// Function Host Keys as Named Values
// ============================================================================

resource functionKeys 'Microsoft.ApiManagement/service/namedValues@2023-09-01-preview' = [for server in mcpServers: {
  parent: apimService
  name: server.keyName
  properties: {
    displayName: server.keyName
    secret: true
    value: listKeys(resourceId('Microsoft.Web/sites/host', server.funcName, 'default'), funcAppApiVersion).functionKeys.default
  }
}]

// ============================================================================
// Backend Definitions - one per MCP server
// ============================================================================

resource backends 'Microsoft.ApiManagement/service/backends@2023-09-01-preview' = [for server in mcpServers: {
  parent: apimService
  name: server.backendName
  properties: {
    title: '${server.name} MCP Backend (passthrough)'
    url: 'https://${server.funcHostName}'
    protocol: 'http'
    tls: {
      validateCertificateChain: true
      validateCertificateName: true
    }
  }
}]

// ============================================================================
// Passthrough API - subscription key required, no OAuth
// Path: /mcp-pt/{server}/mcp
// ============================================================================

resource passthroughApi 'Microsoft.ApiManagement/service/apis@2023-09-01-preview' = {
  parent: apimService
  name: 'mcp-passthrough'
  properties: {
    displayName: 'Healthcare MCP Servers (Passthrough - Debug)'
    description: 'Lightweight passthrough API for debugging backend connectivity. No OAuth.'
    path: 'mcp-pt'
    protocols: ['https']
    subscriptionRequired: true
    subscriptionKeyParameterNames: {
      header: 'Ocp-Apim-Subscription-Key'
      query: 'subscription-key'
    }
  }
}

// ============================================================================
// Product & Subscription for the passthrough API
// ============================================================================

resource passthroughProduct 'Microsoft.ApiManagement/service/products@2023-09-01-preview' = {
  parent: apimService
  name: 'mcp-passthrough-product'
  properties: {
    displayName: 'MCP Passthrough (Debug)'
    description: 'Debug product for testing MCP backend connectivity'
    state: 'published'
    subscriptionRequired: true
    approvalRequired: false
  }
}

resource passthroughProductApi 'Microsoft.ApiManagement/service/products/apis@2023-09-01-preview' = {
  parent: passthroughProduct
  name: 'mcp-passthrough'
  dependsOn: [passthroughApi]
}

resource passthroughSubscription 'Microsoft.ApiManagement/service/subscriptions@2023-09-01-preview' = {
  parent: apimService
  name: 'mcp-passthrough-sub'
  properties: {
    scope: passthroughProduct.id
    displayName: 'MCP Passthrough Debug Subscription'
    state: 'active'
    allowTracing: true
  }
}

// ============================================================================
// Per-Server Operations (generated)
// - POST /{server}/mcp
// - GET  /{server}/mcp
// - GET  /{server}/.well-known/mcp
// - GET  /{server}/health
// ============================================================================

resource mcpPostOps 'Microsoft.ApiManagement/service/apis/operations@2023-09-01-preview' = [for server in mcpServers: {
  parent: passthroughApi
  name: '${server.name}-post'
  properties: {
    displayName: '${server.name} - POST /mcp'
    method: 'POST'
    urlTemplate: '/${server.name}/mcp'
    description: 'MCP message endpoint'
  }
}]

resource mcpPostPolicies 'Microsoft.ApiManagement/service/apis/operations/policies@2023-09-01-preview' = [for (server, i) in mcpServers: {
  parent: mcpPostOps[i]
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: replace(replace(replace('''
<policies>
  <inbound>
    <base />
    <set-backend-service backend-id="__BACKEND_NAME__" />
    <set-header name="x-functions-key" exists-action="override"><value>{{__KEY_NAME__}}</value></set-header>
    <rewrite-uri template="/mcp" copy-unmatched-params="false" />
    <trace source="mcp-pt-__SERVER_NAME__" severity="information">
      <message>@($"__SERVER_NAME__ POST → backend: {context.Request.Url}")</message>
    </trace>
  </inbound>
  <backend><base /></backend>
  <outbound><base /></outbound>
  <on-error>
    <base />
    <return-response>
      <set-status code="502" reason="Backend Error" />
      <set-header name="Content-Type" exists-action="override"><value>application/json</value></set-header>
      <set-body>@(new JObject(new JProperty("error","__SERVER_NAME__-backend-failure"),new JProperty("detail",context.LastError?.Message),new JProperty("source",context.LastError?.Source),new JProperty("reason",context.LastError?.Reason)).ToString())</set-body>
    </return-response>
  </on-error>
</policies>
''', '__BACKEND_NAME__', server.backendName), '__KEY_NAME__', server.keyName), '__SERVER_NAME__', server.name)
  }
  dependsOn: [backends, functionKeys]
}]

resource mcpGetOps 'Microsoft.ApiManagement/service/apis/operations@2023-09-01-preview' = [for server in mcpServers: {
  parent: passthroughApi
  name: '${server.name}-get'
  properties: {
    displayName: '${server.name} - GET /mcp'
    method: 'GET'
    urlTemplate: '/${server.name}/mcp'
    description: 'MCP info endpoint'
  }
}]

resource mcpGetPolicies 'Microsoft.ApiManagement/service/apis/operations/policies@2023-09-01-preview' = [for (server, i) in mcpServers: {
  parent: mcpGetOps[i]
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: replace(replace(replace('''
<policies>
  <inbound>
    <base />
    <set-backend-service backend-id="__BACKEND_NAME__" />
    <set-header name="x-functions-key" exists-action="override"><value>{{__KEY_NAME__}}</value></set-header>
    <rewrite-uri template="/mcp" copy-unmatched-params="false" />
  </inbound>
  <backend><base /></backend>
  <outbound><base /></outbound>
  <on-error>
    <base />
    <return-response>
      <set-status code="502" reason="Backend Error" />
      <set-header name="Content-Type" exists-action="override"><value>application/json</value></set-header>
      <set-body>@(new JObject(new JProperty("error","__SERVER_NAME__-backend-failure"),new JProperty("detail",context.LastError?.Message)).ToString())</set-body>
    </return-response>
  </on-error>
</policies>
''', '__BACKEND_NAME__', server.backendName), '__KEY_NAME__', server.keyName), '__SERVER_NAME__', server.name)
  }
  dependsOn: [backends, functionKeys]
}]

resource wellKnownGetOps 'Microsoft.ApiManagement/service/apis/operations@2023-09-01-preview' = [for server in mcpServers: {
  parent: passthroughApi
  name: '${server.name}-wellknown-get'
  properties: {
    displayName: '${server.name} - GET /.well-known/mcp'
    method: 'GET'
    urlTemplate: '/${server.name}/.well-known/mcp'
    description: 'MCP discovery endpoint'
  }
}]

resource wellKnownGetPolicies 'Microsoft.ApiManagement/service/apis/operations/policies@2023-09-01-preview' = [for (server, i) in mcpServers: {
  parent: wellKnownGetOps[i]
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: replace(replace(replace('''
<policies>
  <inbound>
    <base />
    <set-backend-service backend-id="__BACKEND_NAME__" />
    <set-header name="x-functions-key" exists-action="override"><value>{{__KEY_NAME__}}</value></set-header>
    <rewrite-uri template="/.well-known/mcp" copy-unmatched-params="false" />
  </inbound>
  <backend><base /></backend>
  <outbound><base /></outbound>
  <on-error>
    <base />
    <return-response>
      <set-status code="502" reason="Backend Error" />
      <set-header name="Content-Type" exists-action="override"><value>application/json</value></set-header>
      <set-body>@(new JObject(new JProperty("error","__SERVER_NAME__-wellknown-unreachable"),new JProperty("detail",context.LastError?.Message)).ToString())</set-body>
    </return-response>
  </on-error>
</policies>
''', '__BACKEND_NAME__', server.backendName), '__KEY_NAME__', server.keyName), '__SERVER_NAME__', server.name)
  }
  dependsOn: [backends, functionKeys]
}]

resource healthGetOps 'Microsoft.ApiManagement/service/apis/operations@2023-09-01-preview' = [for server in mcpServers: {
  parent: passthroughApi
  name: '${server.name}-health'
  properties: {
    displayName: '${server.name} - Health Check'
    method: 'GET'
    urlTemplate: '/${server.name}/health'
    description: 'Health check endpoint'
  }
}]

resource healthGetPolicies 'Microsoft.ApiManagement/service/apis/operations/policies@2023-09-01-preview' = [for (server, i) in mcpServers: {
  parent: healthGetOps[i]
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: replace(replace(replace('''
<policies>
  <inbound>
    <base />
    <set-backend-service backend-id="__BACKEND_NAME__" />
    <set-header name="x-functions-key" exists-action="override"><value>{{__KEY_NAME__}}</value></set-header>
    <rewrite-uri template="/health" copy-unmatched-params="false" />
  </inbound>
  <backend><base /></backend>
  <outbound><base /></outbound>
  <on-error>
    <base />
    <return-response>
      <set-status code="502" reason="Backend Error" />
      <set-header name="Content-Type" exists-action="override"><value>application/json</value></set-header>
      <set-body>@(new JObject(new JProperty("error","__SERVER_NAME__-health-unreachable"),new JProperty("detail",context.LastError?.Message)).ToString())</set-body>
    </return-response>
  </on-error>
</policies>
''', '__BACKEND_NAME__', server.backendName), '__KEY_NAME__', server.keyName), '__SERVER_NAME__', server.name)
  }
  dependsOn: [backends, functionKeys]
}]

// ============================================================================
// Outputs
// ============================================================================

output passthroughApiId string = passthroughApi.id
output passthroughApiPath string = passthroughApi.properties.path
output passthroughSubscriptionId string = passthroughSubscription.id
output gatewayUrl string = apimService.properties.gatewayUrl

