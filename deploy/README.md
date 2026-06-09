# Healthcare MCP Infrastructure Deployment

This guide walks through deploying the production-grade Azure infrastructure for the Healthcare MCP Marketplace.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         VNet (192.168.0.0/16)                           │
│  ┌────────────────┬────────────────┬────────────────┬────────────────┐ │
│  │ agent-subnet   │ apim-subnet    │ function-subnet│ pe-subnet      │ │
│  │ 192.168.0.0/24 │ 192.168.2.0/24 │ 192.168.3.0/24 │ 192.168.1.0/24 │ │
│  │                │                │                │                │ │
│  │ AI Foundry     │ APIM Standard  │ Function Apps  │ Private        │ │
│  │ Project        │ v2             │ (6x MCP)       │ Endpoints      │ │
│  └────────────────┴────────────────┴────────────────┴────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

### Components

| Component | Description |
|-----------|-------------|
| **VNet** | Private network with 4 subnets for network isolation |
| **APIM Standard v2** | API gateway for secure MCP server exposure |
| **Function Apps (3x)** | Hosts consolidated MCP servers (Reference Data, Clinical Research, Cosmos RAG) |
| **Azure Container Registry** | Stores docker images for azd-deployed containerized MCP servers |
| **AI Foundry** | AI Services account with GPT-4o model deployments |
| **Private Endpoints** | Secure connectivity for all Azure services |
| **Supporting Services** | Storage, AI Search, Cosmos DB, Application Insights |

## Prerequisites

1. **Azure CLI** installed and logged in
   ```bash
   az login
   az account set --subscription "<your-subscription-id>"
   ```

2. **Bicep CLI** installed
   ```bash
   az bicep install
   # or upgrade existing
   az bicep upgrade
   ```

3. **Azure subscription** with Owner or Contributor access

4. **Required resource providers** registered:
   ```bash
   az provider register --namespace Microsoft.ApiManagement
   az provider register --namespace Microsoft.Web
   az provider register --namespace Microsoft.Storage
   az provider register --namespace Microsoft.CognitiveServices
   az provider register --namespace Microsoft.Search
   az provider register --namespace Microsoft.DocumentDB
   az provider register --namespace Microsoft.Network
   az provider register --namespace Microsoft.ContainerRegistry
   az provider register --namespace Microsoft.App
   az provider register --namespace Microsoft.Insights
   az provider register --namespace Microsoft.OperationalInsights
   ```

## Quick Start

### 1. Configure Parameters

Edit `infra/main.bicepparam` with your values:

```bicep
using 'main.bicep'

param location = 'eastus2'                              // Azure region
param baseName = 'healthcaremcp'                        // Base name (3-15 chars)
param apimPublisherEmail = 'your-email@domain.com'      // Required: Your email
param apimPublisherName = 'Healthcare MCP Platform'
param apimSku = 'StandardV2'                            // StandardV2 or Premium
param vnetAddressPrefix = '192.168.0.0/16'
param enablePublicAccess = false                        // true for dev
param enableCosmosPublicAccess = true                   // local Cosmos access + private endpoint
```

### 2. Create Resource Group

```bash
az group create \
  --name rg-healthcare-mcp \
  --location eastus2 \
  --tags project=healthcare-mcp environment=production
```

### 3. Validate Template

```bash
az deployment group validate \
  --resource-group rg-healthcare-mcp \
  --template-file infra/main.bicep \
  --parameters infra/main.bicepparam
```

### 4. Deploy Infrastructure

⚠️ **Note**: Deployment takes **45-60 minutes** due to APIM Standard v2 provisioning.

```bash
az deployment group create \
  --name healthcare-mcp-deploy \
  --resource-group rg-healthcare-mcp \
  --template-file infra/main.bicep \
  --parameters infra/main.bicepparam \
  --verbose
```

Monitor progress in Azure Portal: **Resource Groups** → **rg-healthcare-mcp** → **Deployments**

### 5. Get Deployment Outputs

```bash
az deployment group show \
  --name healthcare-mcp-deploy \
  --resource-group rg-healthcare-mcp \
  --query properties.outputs
```

Key outputs:
- `apimGatewayUrl` - APIM gateway URL for MCP endpoints
- `apimName` - APIM instance name
- `functionAppNames` - List of deployed Function Apps
- `aiServicesEndpoint` - AI Services endpoint
- `containerRegistryName` - Azure Container Registry name
- `containerRegistryLoginServer` - ACR login server for image pushes/pulls

### 6. Create APIM Subscription Key

```bash
# Create subscription
az apim subscription create \
  --resource-group rg-healthcare-mcp \
  --service-name healthcaremcp-apim \
  --product-id healthcare-mcp \
  --display-name "Healthcare MCP Dev" \
  --subscription-id healthcare-mcp-dev

# Get subscription keys
az apim subscription keys list \
  --resource-group rg-healthcare-mcp \
  --service-name healthcaremcp-apim \
  --subscription-id healthcare-mcp-dev
```

## MCP Server Endpoints

After deployment, MCP servers are available at:

| Server | Endpoint (Passthrough) |
|--------|----------|
| Reference Data | `{apimGatewayUrl}/mcp-pt/reference-data/mcp` |
| Clinical Research | `{apimGatewayUrl}/mcp-pt/clinical-research/mcp` |
| Cosmos RAG | `{apimGatewayUrl}/mcp-pt/cosmos-rag/mcp` |
| Azure OpenAI v1 | `{apimGatewayUrl}/ai/openai/v1` |

For the Azure OpenAI v1 API, send the APIM subscription key in the `api-key` header.

## Testing the Deployment

### Test MCP Endpoint (tools/list)

```bash
APIM_URL="https://healthcaremcp-apim.azure-api.net"
SUBSCRIPTION_KEY="<your-subscription-key>"

curl -X POST "${APIM_URL}/mcp-pt/reference-data/mcp" \
  -H "Content-Type: application/json" \
  -H "Ocp-Apim-Subscription-Key: ${SUBSCRIPTION_KEY}" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list",
    "params": {}
  }'
```

### Test Tool Call (NPI Lookup)

```bash
curl -X POST "${APIM_URL}/mcp-pt/reference-data/mcp" \
  -H "Content-Type: application/json" \
  -H "Ocp-Apim-Subscription-Key: ${SUBSCRIPTION_KEY}" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "npi_lookup_provider",
      "arguments": {"npi": "1234567890"}
    }
  }'
```

## MCP Client Configuration

Add to your MCP client settings (Claude Desktop, VS Code, etc.):

```json
{
  "mcpServers": {
    "azure-reference-data": {
      "url": "https://healthcaremcp-apim.azure-api.net/mcp-pt/reference-data/mcp",
      "transport": "http",
      "headers": {
        "Ocp-Apim-Subscription-Key": "${AZURE_MCP_SUBSCRIPTION_KEY}"
      }
    },
    "azure-clinical-research": {
      "url": "https://healthcaremcp-apim.azure-api.net/mcp-pt/clinical-research/mcp",
      "transport": "http",
      "headers": {
        "Ocp-Apim-Subscription-Key": "${AZURE_MCP_SUBSCRIPTION_KEY}"
      }
    },
    "azure-cosmos-rag": {
      "url": "https://healthcaremcp-apim.azure-api.net/mcp-pt/cosmos-rag/mcp",
      "transport": "http",
      "headers": {
        "Ocp-Apim-Subscription-Key": "${AZURE_MCP_SUBSCRIPTION_KEY}"
      }
    }
  }
}
```

Set the environment variable:
```bash
export AZURE_MCP_SUBSCRIPTION_KEY="<your-subscription-key>"
```

## Module Reference

| Module | Description |
|--------|-------------|
| `modules/vnet.bicep` | VNet with agent, PE, APIM, and function subnets |
| `modules/apim.bicep` | APIM Standard v2 with Healthcare MCP product and APIs |
| `modules/function-apps.bicep` | 3 Function Apps on Elastic Premium plan |
| `modules/ai-foundry.bicep` | AI Services with GPT-4o, GPT-4o-mini, text-embedding-3-large |
| `modules/private-endpoints.bicep` | Private endpoints and DNS zones for all services |
| `modules/dependent-resources.bicep` | Storage, AI Search, Cosmos DB, App Insights |

## Cost Considerations

| Resource | SKU | Estimated Monthly Cost |
|----------|-----|------------------------|
| APIM Standard v2 | StandardV2 (1 unit) | ~$175 |
| Function Apps | Elastic Premium EP1 | ~$150 |
| AI Services | S0 | Pay-per-use |
| AI Search | Standard | ~$250 |
| Cosmos DB | Serverless | Pay-per-use |
| Storage | Standard ZRS | ~$25 |
| Private Endpoints | 8 endpoints | ~$60 |

**Estimated Total**: ~$660/month (excluding AI usage)

## Cleanup

⚠️ **Warning**: This deletes ALL resources!

```bash
az group delete --name rg-healthcare-mcp --yes --no-wait
```

## Troubleshooting

### APIM Deployment Timeout
APIM Standard v2 takes 30-45 minutes. If deployment times out:
```bash
# Check deployment status
az deployment group show \
  --name healthcare-mcp-deploy \
  --resource-group rg-healthcare-mcp \
  --query properties.provisioningState
```

### Function App Not Responding
1. Check Function App is running:
   ```bash
   az functionapp show --name healthcaremcp-mcp-reference-data-func \
     --resource-group rg-healthcare-mcp --query state
   ```
2. Check Application Insights for errors
3. Verify VNet integration is active

### Private Endpoint DNS Issues
Ensure DNS zones are linked to VNet:
```bash
az network private-dns zone list --resource-group rg-healthcare-mcp -o table
```

## Next Steps

1. **Deploy MCP Server Code** - Deploy actual MCP server implementations to Function Apps
2. **Configure OAuth 2.0** - Set up Azure AD app registration for production auth
3. **Store Keys in Key Vault** - Move subscription keys to Azure Key Vault
4. **Set Up Monitoring** - Configure Application Insights alerts
5. **Enable WAF** - Add Azure Front Door with WAF for additional security
