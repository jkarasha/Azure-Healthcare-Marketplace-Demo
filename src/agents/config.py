"""
Centralized configuration for Healthcare Agent Orchestration.

MCP server URLs sourced from APIM passthrough endpoints.
Supports environment variable overrides for local development.

Consolidated MCP servers (v2):
  - reference-data:     NPI + ICD-10 + CMS (12 tools)
  - clinical-research:  FHIR + PubMed + ClinicalTrials (20 tools)
  - cosmos-rag:         Cosmos DB RAG & Audit (6 tools)
"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()

# Default APIM base URL (passthrough — no OAuth, function key injected by APIM policy)
DEFAULT_APIM_BASE_URL = "https://healthcaremcp-apim-v4nrndu5paa6o.azure-api.net/mcp-pt"

# APIM subscription key header name
APIM_SUBSCRIPTION_KEY_HEADER = "Ocp-Apim-Subscription-Key"

# Local development ports (consolidated servers)
LOCAL_PORTS = {
    "reference-data": 7071,
    "clinical-research": 7072,
    "cosmos-rag": 7073,
}


@dataclass(frozen=True)
class MCPEndpoints:
    """MCP server endpoint URLs (3 consolidated servers)."""

    reference_data: str
    clinical_research: str
    cosmos_rag: str

    @classmethod
    def from_env(cls, local: bool = False) -> "MCPEndpoints":
        """Build endpoints from environment, with optional local override."""
        if local:
            return cls(
                reference_data=os.getenv(
                    "MCP_REFERENCE_DATA_URL",
                    f"http://localhost:{LOCAL_PORTS['reference-data']}/mcp",
                ),
                clinical_research=os.getenv(
                    "MCP_CLINICAL_RESEARCH_URL",
                    f"http://localhost:{LOCAL_PORTS['clinical-research']}/mcp",
                ),
                cosmos_rag=os.getenv(
                    "MCP_COSMOS_RAG_URL",
                    f"http://localhost:{LOCAL_PORTS['cosmos-rag']}/mcp",
                ),
            )

        base = os.getenv("APIM_BASE_URL", DEFAULT_APIM_BASE_URL).rstrip("/")
        return cls(
            reference_data=os.getenv("MCP_REFERENCE_DATA_URL", f"{base}/reference-data/mcp"),
            clinical_research=os.getenv("MCP_CLINICAL_RESEARCH_URL", f"{base}/clinical-research/mcp"),
            cosmos_rag=os.getenv("MCP_COSMOS_RAG_URL", f"{base}/cosmos-rag/mcp"),
        )


@dataclass(frozen=True)
class AzureOpenAIConfig:
    """Azure OpenAI settings for agent LLM backend."""

    endpoint: str = ""
    deployment_name: str = "gpt-4o"
    api_version: str = "preview"
    temperature: float = 0.3

    @classmethod
    def from_env(cls) -> "AzureOpenAIConfig":
        return cls(
            endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
            deployment_name=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "preview"),
            temperature=float(os.getenv("AGENT_TEMPERATURE", "0.3")),
        )


@dataclass
class AgentConfig:
    """Top-level configuration bundle."""

    endpoints: MCPEndpoints
    openai: AzureOpenAIConfig
    apim_subscription_key: str = ""

    @classmethod
    def load(cls, local: bool = False) -> "AgentConfig":
        return cls(
            endpoints=MCPEndpoints.from_env(local=local),
            openai=AzureOpenAIConfig.from_env(),
            apim_subscription_key=os.getenv("APIM_SUBSCRIPTION_KEY", ""),
        )
