# Azure Healthcare Marketplace Architecture Analysis

## Anthropic Healthcare Marketplace: Hidden Layers Revealed

The GitHub repository (`anthropics/healthcare`) shows the **surface layer** only. Here's what you're *not* seeing:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    VISIBLE IN GITHUB REPO                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│  • SKILL.md files (instructions, metadata, triggers)                        │
│  • .claude-plugin manifests (plugin registry configuration)                 │
│  • Python scripts (scipy/numpy for protocol generation)                     │
│  • MCP server URLs (pointers to hosted endpoints)                           │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    HIDDEN LAYER 1: MCP Server Runtime                       │
├─────────────────────────────────────────────────────────────────────────────┤
│  Endpoints like: https://mcp.deepsense.ai/cms_coverage/mcp                  │
│                  https://pubmed.mcp.claude.com/mcp                          │
│                                                                             │
│  What's behind these:                                                       │
│  • JSON-RPC 2.0 server implementation                                       │
│  • Tool discovery endpoints (tools/list)                                    │
│  • Tool execution handlers (tools/call)                                     │
│  • Resource providers (resources/list, resources/read)                      │
│  • OAuth/API key authentication middleware                                  │
│  • Rate limiting, logging, observability                                    │
│  • Actual API integrations (CMS, NPI Registry, PubMed APIs)                 │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    HIDDEN LAYER 2: Skill Execution Runtime                  │
├─────────────────────────────────────────────────────────────────────────────┤
│  Claude Code Plugin System:                                                 │
│  • Marketplace registry (plugin index, versioning)                          │
│  • Progressive disclosure loader (name → description → full SKILL.md)       │
│  • Context injection engine (system prompt augmentation)                    │
│  • Script sandbox (Python execution for protocol generation)                │
│  • File I/O for skill assets (templates, references)                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    HIDDEN LAYER 3: Backend Data Services                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  • CMS Coverage Database (Medicare/Medicaid policy lookup)                  │
│  • NPI Registry (NPPES API wrapper + caching)                               │
│  • PubMed (NCBI E-utilities integration)                                    │
│  • ICD-10 code lookup service                                               │
│  • CPT code validation                                                      │
│  • Clinical guidelines knowledge bases                                      │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    HIDDEN LAYER 4: LLM Orchestration                        │
├─────────────────────────────────────────────────────────────────────────────┤
│  • Claude API (messages endpoint with tool_use)                             │
│  • System prompt construction with skill injection                          │
│  • Multi-turn conversation state management                                 │
│  • Tool call routing and result parsing                                     │
│  • Streaming response handling                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Breakdown: What Each Piece Does

### 1. Skills (Static Knowledge Layer)

**What it is**: Markdown files with YAML frontmatter that inject domain expertise into the LLM's context.

```yaml
# Example structure from anthropics/healthcare
---
name: fhir-developer
description: "HL7 FHIR R4 for healthcare data exchange, including resource
              structures, coding systems (LOINC, SNOMED CT, RxNorm)"
---
# FHIR Developer Skill
## Resource Structures
...procedural knowledge about Patient, Observation, etc...

## Code Systems
...LOINC, SNOMED mapping tables...
```

**Key insight**: Skills are **stateless** instruction sets—they don't call APIs directly. They teach the LLM *how* to do something, not *do* it.

### 2. MCP Servers (Dynamic Tool Layer)

**What it is**: Remote HTTP endpoints implementing the Model Context Protocol specification.

```
Protocol: JSON-RPC 2.0 over Streamable HTTP
Transport: POST for requests, SSE for streaming responses

Core Methods:
├── initialize         → Capability negotiation
├── tools/list         → Discover available functions
├── tools/call         → Execute a function
├── resources/list     → Discover data sources
├── resources/read     → Fetch data
└── prompts/list       → Get prompt templates
```

**The CMS Coverage MCP server** (`https://mcp.deepsense.ai/cms_coverage/mcp`) likely exposes tools like:

```json
{
  "tools": [
    {
      "name": "search_coverage_policy",
      "description": "Search CMS National Coverage Determinations",
      "inputSchema": {
        "type": "object",
        "properties": {
          "procedure_code": { "type": "string" },
          "diagnosis_code": { "type": "string" }
        }
      }
    },
    {
      "name": "get_lcd_details",
      "description": "Get Local Coverage Determination details",
      "inputSchema": {
        "type": "object",
        "properties": { "lcd_id": { "type": "string" } }
      }
    }
  ]
}
```

### 3. Plugin Marketplace (Distribution Layer)

**What it is**: A GitHub-based registry that Claude Code can query to discover and install skills/MCP servers.

```bash
# How it works in Claude Code
/plugin marketplace add anthropics/healthcare  # Register the repo
/plugin install fhir-developer@healthcare      # Install a skill

# Behind the scenes:
# 1. Fetch .claude-plugin/manifest.json from repo
# 2. Download SKILL.md to local skills directory
# 3. Update available_skills index for context injection
```

---

## Azure Implementation Architecture

Here's how to build an equivalent system for Azure + GitHub Copilot + M365 Agents:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         AZURE HEALTHCARE MARKETPLACE                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐         │
│  │  GitHub Repo    │    │  Azure AI       │    │  M365 Agents    │         │
│  │  (Skills Store) │    │  Foundry Tools  │    │  (Copilot Studio)│        │
│  └────────┬────────┘    └────────┬────────┘    └────────┬────────┘         │
│           │                      │                      │                   │
│           ▼                      ▼                      ▼                   │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │                    MCP SERVER LAYER                              │       │
│  │  (Azure Functions / Azure Container Apps)                        │       │
│  │                                                                  │       │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │       │
│  │  │ Azure FHIR   │  │ Azure Health │  │ Custom       │           │       │
│  │  │ MCP Server   │  │ Data MCP     │  │ Healthcare   │           │       │
│  │  │              │  │ Server       │  │ APIs         │           │       │
│  │  └──────────────┘  └──────────────┘  └──────────────┘           │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────┐       │
│  │                    BACKEND DATA SERVICES                         │       │
│  │                                                                  │       │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │       │
│  │  │ Azure API    │  │ Azure Health │  │ Azure        │           │       │
│  │  │ for FHIR     │  │ Data Services│  │ Cognitive    │           │       │
│  │  │              │  │ (DICOM, etc) │  │ Search       │           │       │
│  │  └──────────────┘  └──────────────┘  └──────────────┘           │       │
│  │                                                                  │       │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │       │
│  │  │ Cosmos DB    │  │ Azure Blob   │  │ Key Vault    │           │       │
│  │  │ (Policy DB)  │  │ (Documents)  │  │ (Secrets)    │           │       │
│  │  └──────────────┘  └──────────────┘  └──────────────┘           │       │
│  └─────────────────────────────────────────────────────────────────┘       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Phases

### Phase 1: Skills Layer (GitHub Copilot + VS Code)

**Goal**: Create reusable domain knowledge for Azure healthcare developers.

```
.github/skills/
├── azure-fhir-developer/
│   ├── SKILL.md              # Core instructions
│   ├── references/
│   │   ├── fhir-r4-resources.md
│   │   └── azure-fhir-api.md
│   └── scripts/
│       └── validate-bundle.py
├── azure-health-data-services/
│   ├── SKILL.md
│   └── references/
│       └── dicom-api.md
└── prior-auth-azure/
    ├── SKILL.md
    └── templates/
        └── prior-auth-request.json
```

**SKILL.md Example** (Azure FHIR):

```yaml
---
name: azure-fhir-developer
description: "Azure API for FHIR development including resource management,
              SMART on FHIR authentication, bulk data export, and integration
              with Azure Health Data Services. Use when building FHIR apps on Azure."
---

# Azure FHIR Developer Skill

## Authentication Patterns

### SMART on FHIR with Azure AD B2C
When implementing patient-facing apps, use the SMART on FHIR launch sequence:
1. Register app in Azure AD B2C
2. Configure FHIR server CORS and authentication
3. Implement authorization code flow with PKCE

## Common Operations

### Creating a Patient Resource
```http
POST https://{fhir-server}.azurehealthcareapis.com/Patient
Authorization: Bearer {token}
Content-Type: application/fhir+json

{
  "resourceType": "Patient",
  "identifier": [{ "system": "...", "value": "..." }]
}
```

## Azure-Specific Considerations
- Use managed identity for service-to-service auth
- Enable diagnostic settings for audit logging
- Configure private endpoints for HIPAA compliance
```

### Phase 2: MCP Servers (Azure Functions)

**Goal**: Create callable tools for real-time healthcare data access.

**Architecture Decision**: Azure Functions with HTTP trigger (Streamable HTTP transport)

```typescript
// azure-fhir-mcp-server/src/index.ts
import { McpServer, McpToolHandler } from '@modelcontextprotocol/sdk';
import { AzureFhirClient } from './fhir-client';

const server = new McpServer({
  name: 'azure-fhir',
  version: '1.0.0'
});

// Tool: Search for patients
server.tool(
  'search_patients',
  {
    description: 'Search for patients in Azure FHIR by name, identifier, or demographics',
    inputSchema: {
      type: 'object',
      properties: {
        name: { type: 'string', description: 'Patient name (partial match)' },
        identifier: { type: 'string', description: 'Patient identifier (MRN, SSN, etc)' },
        birthdate: { type: 'string', format: 'date' }
      }
    }
  },
  async (params) => {
    const fhir = new AzureFhirClient(process.env.FHIR_SERVER_URL);
    const results = await fhir.search('Patient', params);
    return { content: [{ type: 'text', text: JSON.stringify(results, null, 2) }] };
  }
);

// Tool: Get coverage policy
server.tool(
  'check_coverage_policy',
  {
    description: 'Check insurance coverage policy for a procedure',
    inputSchema: {
      type: 'object',
      properties: {
        cpt_code: { type: 'string', description: 'CPT procedure code' },
        icd10_code: { type: 'string', description: 'ICD-10 diagnosis code' },
        payer_id: { type: 'string', description: 'Insurance payer identifier' }
      },
      required: ['cpt_code']
    }
  },
  async (params) => {
    // Query coverage policy database
    const policy = await coverageDb.findPolicy(params);
    return { content: [{ type: 'text', text: formatPolicyResponse(policy) }] };
  }
);

export default server.createHttpHandler();
```

**Deployment (Azure Functions)**:

```yaml
# .github/workflows/deploy-mcp-server.yml
name: Deploy MCP Server
on:
  push:
    branches: [main]
    paths: ['azure-fhir-mcp-server/**']

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: azure/login@v2
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}
      - uses: azure/functions-action@v2
        with:
          app-name: 'healthcare-mcp-server'
          package: './azure-fhir-mcp-server'
```

### Phase 3: Azure AI Foundry Integration

**Goal**: Register MCP servers as tools for Foundry agents.

```python
# foundry_agent_setup.py
from azure.ai.agents.persistent import PersistentAgentsClient
from azure.identity import DefaultAzureCredential

client = PersistentAgentsClient(
    endpoint="https://your-foundry.api.azureml.ms",
    credential=DefaultAzureCredential()
)

# Register custom healthcare MCP servers
agent = client.agents.create(
    model="gpt-4o",
    name="healthcare-assistant",
    instructions="""You are a healthcare administrative assistant.
    Use the available tools to check coverage policies, look up provider information,
    and assist with prior authorization workflows.""",
    tools=[
        {
            "type": "mcp",
            "server_label": "azure_fhir",
            "server_url": "https://healthcare-mcp-server.azurewebsites.net/mcp",
            "allowed_tools": ["search_patients", "get_patient", "search_observations"]
        },
        {
            "type": "mcp",
            "server_label": "coverage_policy",
            "server_url": "https://coverage-mcp-server.azurewebsites.net/mcp",
            "allowed_tools": ["check_coverage_policy", "get_ncd_details"]
        }
    ]
)
```

### Phase 4: GitHub Copilot Extension

**Goal**: Make skills accessible in VS Code via Copilot.

**Option A: Copilot Skillset** (Simpler)

```json
// skillset-config.json
{
  "name": "azure-healthcare",
  "description": "Azure healthcare development tools",
  "skills": [
    {
      "name": "fhir_resource_validator",
      "inference_description": "Validates FHIR resources against Azure profiles",
      "url": "https://healthcare-api.azurewebsites.net/validate",
      "parameters": {
        "type": "object",
        "properties": {
          "resource": { "type": "string", "description": "FHIR resource JSON" },
          "profile": { "type": "string", "description": "Profile URL to validate against" }
        }
      }
    }
  ]
}
```

**Option B: VS Code Chat Participant** (More control)

```typescript
// src/extension.ts
import * as vscode from 'vscode';

export function activate(context: vscode.ExtensionContext) {
  const participant = vscode.chat.createChatParticipant(
    'azure-healthcare',
    async (request, context, response, token) => {
      // Load relevant skill based on request
      const skill = await loadHealthcareSkill(request.prompt);

      // Augment prompt with skill instructions
      const augmentedPrompt = `${skill.instructions}\n\nUser request: ${request.prompt}`;

      // Use Copilot API
      const result = await vscode.lm.selectChatModels({ family: 'gpt-4o' });
      // ... generate response
    }
  );

  participant.iconPath = vscode.Uri.joinPath(context.extensionUri, 'icon.png');
}
```

### Phase 5: M365 Copilot / Copilot Studio Integration

**Goal**: Expose healthcare tools through Microsoft 365 agents.

```yaml
# declarative-agent.yaml (for Copilot Studio)
name: Healthcare Prior Auth Assistant
description: Assists with prior authorization workflows
instructions: |
  You help healthcare administrators process prior authorization requests.
  Always verify coverage policies before recommending approval.

capabilities:
  - name: check_coverage
    description: Check insurance coverage for procedures
    connection: healthcare-logic-app
  - name: search_providers
    description: Search NPI registry for provider information
    connection: npi-mcp-server

actions:
  - type: plugin
    id: microsoft.graph
    capabilities: [calendar, mail]  # For scheduling, notifications
```

---

## Azure Services Mapping

| Anthropic Component | Azure Equivalent | Notes |
|---------------------|------------------|-------|
| MCP Server (hosted) | Azure Functions / Container Apps | Serverless, auto-scaling |
| Skills Repository | GitHub + Azure Repos | Use GitHub for Copilot integration |
| Claude API | Azure OpenAI / AI Foundry | gpt-4o, gpt-4o-mini |
| PubMed Connector | Azure Cognitive Search + PubMed API | Index PubMed for RAG |
| CMS Coverage DB | Cosmos DB + Azure Functions | Replicate CMS data |
| Plugin Marketplace | GitHub Marketplace + Foundry Tools Catalog | Dual distribution |

---

## Security & Compliance Considerations

### HIPAA Compliance Checklist

```
□ Enable Azure Private Link for all FHIR endpoints
□ Configure Azure AD Conditional Access
□ Enable diagnostic logging to Log Analytics
□ Implement Azure Key Vault for secrets
□ Use Managed Identities (no secrets in code)
□ Configure VNET integration for MCP servers
□ Enable audit logging for all tool calls
□ Implement data residency controls
□ Sign BAA with Microsoft
```

### MCP Server Security

```typescript
// Secure MCP server with Azure AD authentication
import { AuthenticationMiddleware } from '@azure/identity';

server.use(async (req, res, next) => {
  const token = req.headers.authorization?.replace('Bearer ', '');

  // Validate Azure AD token
  const claims = await validateAzureAdToken(token, {
    audience: 'api://healthcare-mcp-server',
    issuer: `https://sts.windows.net/${TENANT_ID}/`
  });

  // Check required scopes
  if (!claims.scp?.includes('Healthcare.Read')) {
    return res.status(403).json({ error: 'Insufficient permissions' });
  }

  req.user = claims;
  next();
});
```

---

## Quick Start Checklist

### Week 1-2: Foundation
- [ ] Create GitHub repo structure (skills directory)
- [ ] Write 2-3 core SKILL.md files (FHIR, Prior Auth, ICD-10)
- [ ] Set up Azure subscription with Health Data Services
- [ ] Deploy Azure API for FHIR instance

### Week 3-4: MCP Layer
- [ ] Create first MCP server (Azure Functions)
- [ ] Implement 3-5 core tools (patient search, coverage check, etc.)
- [ ] Configure authentication (Azure AD)
- [ ] Test with MCP Inspector tool

### Week 5-6: Integration
- [ ] Register MCP servers with Azure AI Foundry
- [ ] Create GitHub Copilot skillset
- [ ] Test end-to-end with VS Code
- [ ] Document usage patterns

### Week 7-8: Distribution
- [ ] Set up Foundry Tools catalog entry
- [ ] Create VS Code extension (if needed)
- [ ] Write developer documentation
- [ ] Create sample applications

---

## References

- [MCP Specification](https://modelcontextprotocol.io/docs)
- [Azure AI Foundry MCP Integration](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/how-to/tools/model-context-protocol)
- [GitHub Copilot Skillsets](https://docs.github.com/en/copilot/building-copilot-extensions/building-a-copilot-skillset-for-your-copilot-extension)
- [VS Code Agent Skills](https://code.visualstudio.com/docs/copilot/customization/agent-skills)
- [Azure Health Data Services](https://learn.microsoft.com/en-us/azure/healthcare-apis/)
- [Foundry Tools Catalog](https://learn.microsoft.com/en-us/azure/ai-foundry/agents/concepts/tool-catalog)
