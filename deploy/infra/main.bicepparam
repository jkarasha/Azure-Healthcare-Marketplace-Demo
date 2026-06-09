using 'main.bicep'

// ============================================================================
// DEBUG / DEV Configuration — Public Network Access Enabled
// Use this file for local development and debugging:
//   azd provision --parameters deploy/infra/main.debug.bicepparam
// ============================================================================

// Azure region (must support AI Services and APIM Standard v2)
param location = 'eastus2'

// Base name for all resources (3-15 characters, alphanumeric and hyphens)
param baseName = 'healthcaremcp'

// APIM publisher email
param apimPublisherEmail = 'jinle@microsoft.com'

// APIM publisher organization name
param apimPublisherName = 'Healthcare MCP Platform'

// APIM SKU — StandardV2 is sufficient for dev/debug
param apimSku = 'StandardV2'

// VNet address space
param vnetAddressPrefix = '192.168.0.0/16'

// ============================================================================
// PUBLIC ACCESS — all resources reachable from your local machine
// ============================================================================
param enablePublicAccess = true

// FHIR private endpoint not needed when everything is public
param enableFhirPrivateEndpoint = false

// Cosmos DB public access (already implied by enablePublicAccess, kept explicit)
param enableCosmosPublicAccess = true

// Container Registry — Basic SKU, admin enabled for easy local docker push/pull
param containerRegistrySku = 'Basic'
param containerRegistryAdminUserEnabled = true

// Cosmos DB in separate region if primary has capacity issues
param cosmosDbLocation = 'westus2'

// AI Model deployments — same models, lower capacity for cost savings
param modelDeployments = [
  {
    name: 'gpt-4o'
    model: 'gpt-4o'
    version: '2024-08-06'
    capacity: 5
  }
  {
    name: 'gpt-4o-mini'
    model: 'gpt-4o-mini'
    version: '2024-07-18'
    capacity: 5
  }
  {
    name: 'text-embedding-3-large'
    model: 'text-embedding-3-large'
    version: '1'
    capacity: 5
  }
]

// Resource tags — clearly marked as dev environment
param tags = {
  project: 'healthcare-mcp'
  environment: 'dev'
  managedBy: 'bicep'
  costCenter: 'healthcare-it'
  SecurityControl: 'Ignore'
  SecurityControls: 'Ignore'
}
