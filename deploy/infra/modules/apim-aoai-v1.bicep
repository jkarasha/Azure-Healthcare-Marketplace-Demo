// APIM Azure OpenAI v1 API
// Captures the portal-configured aoai-v1 API and backend wiring.

@description('Name of the API Management service')
param apimServiceName string

@description('Azure AI Services account name used for v1 endpoint backend URL')
param aiServicesName string

resource apimService 'Microsoft.ApiManagement/service@2023-09-01-preview' existing = {
  name: apimServiceName
}

resource aoaiV1Backend 'Microsoft.ApiManagement/service/backends@2023-09-01-preview' = {
  parent: apimService
  name: 'aoai-v1-ai-endpoint'
  properties: {
    protocol: 'http'
    url: 'https://${aiServicesName}.services.ai.azure.com/openai/v1'
    credentials: any({
      managedIdentity: {
        resource: 'https://cognitiveservices.azure.com/'
      }
    })
  }
}

resource aoaiV1Api 'Microsoft.ApiManagement/service/apis@2023-09-01-preview' = {
  parent: apimService
  name: 'aoai-v1'
  properties: {
    displayName: 'aoai-v1'
    path: 'ai/openai/v1'
    protocols: ['https']
    subscriptionRequired: true
    subscriptionKeyParameterNames: {
      header: 'api-key'
      query: 'subscription-key'
    }
    format: 'openapi+json'
    value: string(loadJsonContent('../specs/aoai-v1-openapi.json'))
  }
}

resource aoaiV1ApiPolicy 'Microsoft.ApiManagement/service/apis/policies@2023-09-01-preview' = {
  parent: aoaiV1Api
  name: 'policy'
  properties: {
    format: 'rawxml'
    value: '''
<policies>
  <inbound>
    <base />
    <set-backend-service backend-id="aoai-v1-ai-endpoint" />
  </inbound>
  <backend>
    <base />
  </backend>
  <outbound>
    <base />
  </outbound>
  <on-error>
    <base />
  </on-error>
</policies>
'''
  }
  dependsOn: [aoaiV1Backend]
}

output aoaiV1ApiId string = aoaiV1Api.id
output aoaiV1ApiPath string = aoaiV1Api.properties.path
output aoaiV1BackendId string = aoaiV1Backend.id
