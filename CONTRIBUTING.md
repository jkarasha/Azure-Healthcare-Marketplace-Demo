# Contributing to Healthcare MCP

Thank you for your interest in contributing! This guide will get you from zero to productive as quickly as possible.

## First-Time Setup (5 minutes)

The fastest path to a working local environment:

```bash
# 1. Clone and enter the repo
git clone https://github.com/JinLee794/healthcare-for-microsoft.git
cd healthcare-for-microsoft

# 2. Run the interactive setup wizard
make setup-guided
```

The wizard walks you through:
- Verifying prerequisites (Python 3.9+, Node.js, Azure Functions Core Tools, Azurite)
- Creating virtual environments for all MCP servers
- Starting servers locally
- Running smoke tests
- Generating `.vscode/mcp.json` for Copilot integration

**Alternative paths** (if you prefer manual setup):

| Path | Command | When to use |
|---|---|---|
| Docker Compose | `make docker-up` | Don't want to install Python/func tools locally |
| Manual native | `make local-start` | Already have venvs set up |
| Interactive menu | `make setup` | Browse all options |

## Prerequisites

| Tool | Required | Install |
|---|---|---|
| Python 3.9–3.13 | Yes | `brew install python@3.11` |
| Azure Functions Core Tools v4 | Yes | `brew install azure-functions-core-tools@4` |
| Node.js 18+ | Yes | `brew install node` |
| Azurite | Yes (local) | `npm install -g azurite` |
| Docker | Optional | [Docker Desktop](https://docker.com/get-docker) |
| Azure CLI | Optional (deploy) | `brew install azure-cli` |
| Azure Developer CLI (azd) | Optional (deploy) | `brew install azd` |

## Project Layout

```
healthcare-for-microsoft/
├── .github/skills/          # Healthcare domain skills (auto-loaded by Copilot)
├── src/
│   ├── mcp-servers/         # 7 Python Azure Function MCP servers
│   │   ├── npi-lookup/      #   NPI provider registry    :7071
│   │   ├── icd10-validation/#   ICD-10 code validation    :7072
│   │   ├── cms-coverage/    #   Medicare coverage search  :7073
│   │   ├── fhir-operations/ #   FHIR patient data         :7074
│   │   ├── pubmed/          #   PubMed literature search  :7075
│   │   ├── clinical-trials/ #   ClinicalTrials.gov search :7076
│   │   ├── cosmos-rag/      #   Cosmos DB RAG search      :7077
│   │   └── shared/          #   Shared utilities
│   └── agents/              # Multi-agent orchestration CLI + dev UIs
├── scripts/                 # Automation: setup CLI, evals, deploy helpers
│   └── setup-cli/           # Interactive setup wizard (powers `make setup`)
├── deploy/                  # Azure Bicep infrastructure
├── docs/                    # Architecture, testing, and reference docs
├── vscode-extension/        # VS Code @healthcare chat participant
├── samples/                 # Standalone reference implementations
│   └── azure-fhir-mcp-server/  # TypeScript FHIR MCP server sample
└── foundry-integration/     # Azure AI Foundry agent registration
```

## Common Tasks

```bash
# Start all MCP servers locally
make local-start

# Check server status
make setup-status

# Run smoke tests against running servers
make setup-test

# Run contract + latency evaluations
make eval-all

# Start Docker Compose stack
make docker-up

# Launch Gradio DevUI (local servers)
make devui-local

# Full diagnostics if something is broken
make setup-doctor
```

## MCP Server Development

Each MCP server lives in `src/mcp-servers/<name>/` and follows the same pattern:

```
src/mcp-servers/npi-lookup/
├── function_app.py      # Azure Function entry point + MCP tool definitions
├── host.json            # Azure Functions host config
├── local.settings.json  # Local environment variables
├── requirements.txt     # Python dependencies
├── .venv/               # Virtual environment (created by setup)
└── .python_packages/    # Azure Functions worker packages (created by setup)
```

**To add a new tool to an existing server**, edit `function_app.py` and follow the pattern in `src/mcp-servers/npi-lookup/function_app.py`.

**To add a new MCP server**, copy an existing server directory and:
1. Update `function_app.py` with your tools
2. Add the server to `scripts/setup-cli/styles.py` → `MCP_SERVERS`
3. Add a Makefile target (`local-start-<name>`)
4. Add to `docker-compose.yml`
5. Update `deploy/infra/modules/function-apps.bicep` for Azure deployment

## Code Style

- Python: Format with [Ruff](https://docs.astral.sh/ruff/) — config in `pyproject.toml`
- Bicep: Format with `bicep format`
- TypeScript: Standard ESLint/Prettier

## Environment Variables

See [.env.example](.env.example) for all variables used across the platform. Each MCP server also has its own `local.settings.json` for Azure Functions-specific config.

## Documentation

| Doc | Purpose |
|---|---|
| [docs/GETTING-STARTED.md](docs/GETTING-STARTED.md) | Deep-dive local setup & testing |
| [docs/MCP-OAUTH-PRM.md](docs/MCP-OAUTH-PRM.md) | OAuth + PRM architecture |
| [docs/SKILLS-FLOW-MAP.md](docs/SKILLS-FLOW-MAP.md) | Skill → MCP tool flow diagrams |
| [docs/architecture/](docs/architecture/) | APIM and retrieval architecture |
| [deploy/README.md](deploy/README.md) | Azure infrastructure deployment |

## Safety Rules

- **No PHI or real patient data** — use only de-identified sample data
- **No secrets in code** — use environment variables and `.env` files
- **Ask before cloud operations** — `azd up`, resource deletes, etc.
- **Keep changes focused** — one task per PR, minimal blast radius
