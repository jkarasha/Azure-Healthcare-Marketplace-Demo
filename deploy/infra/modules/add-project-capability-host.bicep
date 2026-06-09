// Capability Host Module — Project level only
// Based on foundry-samples/15-private-network-standard-agent-setup
// add-project-capability-host.bicep
//
// Only the project-level capability host is managed in Bicep.
//
// The project capability host references connections by name, so those
// connections must already exist on the project before this module runs.
//
// Ref: https://github.com/microsoft-foundry/foundry-samples/tree/main/infrastructure/infrastructure-setup-bicep/15-private-network-standard-agent-setup

@description('Name of the AI Services account')
param accountName string

@description('Name of the AI Project (child of account)')
param projectName string

@description('Name for the project-level capability host')
param projectCapHost string = 'caphost-agents'

@description('Cosmos DB connection name (must match the connection resource name on the project)')
param cosmosDBConnection string

@description('Azure Storage connection name (must match the connection resource name on the project)')
param azureStorageConnection string

@description('AI Search connection name (must match the connection resource name on the project)')
param aiSearchConnection string

// Build connection arrays from names
var threadConnections = [cosmosDBConnection]
var storageConnections = [azureStorageConnection]
var vectorStoreConnections = [aiSearchConnection]

// ============================================================================
// Existing resource references — uses parent property per Bicep best practices
// ============================================================================

#disable-next-line BCP081
resource account 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: accountName
}

#disable-next-line BCP081
resource project 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' existing = {
  name: projectName
  parent: account
}

// // ============================================================================
// // Project-level capability host only
// // ============================================================================

// #disable-next-line BCP081
// resource projectCapabilityHost 'Microsoft.CognitiveServices/accounts/projects/capabilityHosts@2025-04-01-preview' = {
//   name: projectCapHost
//   parent: project
//   properties: {
//     #disable-next-line BCP037
//     capabilityHostKind: 'Agents'
//     vectorStoreConnections: vectorStoreConnections
//     storageConnections: storageConnections
//     threadStorageConnections: threadConnections
//   }
// }

// // ============================================================================
// // Outputs
// // ============================================================================

// output projectCapHost string = projectCapabilityHost.name
