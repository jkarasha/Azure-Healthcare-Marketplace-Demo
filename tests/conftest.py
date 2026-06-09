"""
Shared pytest fixtures for MCP server integration tests.

Supports:
  - Consolidated servers (v2): 3 servers on ports 7071-7073
  - Legacy server names: backwards-compatible aliases for old 7-server layout

HTTP clients and helper utilities for testing MCP servers locally or in Docker.
"""

import json
import os
from typing import Any

import httpx
import pytest

# ============================================================================
# Port configuration — consolidated (v2) servers
# ============================================================================

MCP_CONSOLIDATED_PORTS = {
    "mcp-reference-data": int(os.getenv("MCP_REFERENCE_DATA_PORT", "7071")),
    "mcp-clinical-research": int(os.getenv("MCP_CLINICAL_RESEARCH_PORT", "7072")),
    "cosmos-rag": int(os.getenv("MCP_COSMOS_RAG_PORT", "7073")),
}

# Legacy port aliases — map old server names to consolidated ports
MCP_LEGACY_PORTS = {
    "npi-lookup": MCP_CONSOLIDATED_PORTS["mcp-reference-data"],
    "icd10-validation": MCP_CONSOLIDATED_PORTS["mcp-reference-data"],
    "cms-coverage": MCP_CONSOLIDATED_PORTS["mcp-reference-data"],
    "fhir-operations": MCP_CONSOLIDATED_PORTS["mcp-clinical-research"],
    "pubmed": MCP_CONSOLIDATED_PORTS["mcp-clinical-research"],
    "clinical-trials": MCP_CONSOLIDATED_PORTS["mcp-clinical-research"],
}

# Combined for any lookup
MCP_SERVER_PORTS = {**MCP_LEGACY_PORTS, **MCP_CONSOLIDATED_PORTS}

MCP_BASE_HOST = os.getenv("MCP_BASE_HOST", "http://localhost")
MCP_FUNCTION_KEY = os.getenv("MCP_FUNCTION_KEY", "")  # empty for local, set for Docker


def _base_url(server_name: str) -> str:
    port = MCP_SERVER_PORTS[server_name]
    return f"{MCP_BASE_HOST}:{port}"


def _headers() -> dict:
    headers = {"Content-Type": "application/json"}
    if MCP_FUNCTION_KEY:
        headers["x-functions-key"] = MCP_FUNCTION_KEY
    return headers


# ---------------------------------------------------------------------------
# Canonical tool inventory — the full set of 38 tools across 3 servers
# (used by backwards-compat and parity tests)
# ---------------------------------------------------------------------------

CANONICAL_TOOLS = {
    "mcp-reference-data": {
        "validate_npi",
        "lookup_npi",
        "search_providers",
        "validate_icd10",
        "lookup_icd10",
        "search_icd10",
        "get_icd10_chapter",
        "search_coverage",
        "get_coverage_by_cpt",
        "get_coverage_by_icd10",
        "check_medical_necessity",
        "get_mac_jurisdiction",
    },
    "mcp-clinical-research": {
        "search_patients",
        "get_patient",
        "get_patient_conditions",
        "get_patient_medications",
        "get_patient_observations",
        "get_patient_encounters",
        "search_practitioners",
        "validate_resource",
        "search_pubmed",
        "get_article",
        "get_articles_batch",
        "get_article_abstract",
        "find_related_articles",
        "search_clinical_queries",
        "search_by_condition",
        "search_clinical_trials",
        "get_trial_details",
        "get_trial_eligibility",
        "get_trial_locations",
        "get_trial_results",
    },
    "cosmos-rag": {
        "hybrid_search",
        "vector_search",
        "index_document",
        "record_audit_event",
        "get_audit_trail",
        "get_session_history",
    },
}

CANONICAL_TOOL_COUNTS = {k: len(v) for k, v in CANONICAL_TOOLS.items()}
CANONICAL_ALL_TOOLS = set().union(*CANONICAL_TOOLS.values())


# ---------------------------------------------------------------------------
# Generic MCP helpers
# ---------------------------------------------------------------------------


class MCPClient:
    """Lightweight wrapper for MCP JSON-RPC calls."""

    def __init__(self, base_url: str, headers: dict | None = None):
        self.base_url = base_url
        self.headers = headers or _headers()
        self._http = httpx.Client(base_url=base_url, headers=self.headers, timeout=30.0)
        self._id = 0

    def _next_id(self) -> int:
        self._id += 1
        return self._id

    # -- Discovery -----------------------------------------------------------
    def discover(self) -> httpx.Response:
        return self._http.get("/.well-known/mcp")

    # -- JSON-RPC helpers ----------------------------------------------------
    def rpc(self, method: str, params: dict | None = None) -> httpx.Response:
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params or {},
        }
        return self._http.post("/mcp", json=payload)

    def initialize(self) -> httpx.Response:
        return self.rpc(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "clientInfo": {"name": "pytest", "version": "1.0.0"},
            },
        )

    def list_tools(self) -> httpx.Response:
        return self.rpc("tools/list")

    def call_tool(self, name: str, arguments: dict | None = None) -> httpx.Response:
        return self.rpc("tools/call", {"name": name, "arguments": arguments or {}})

    def ping(self) -> httpx.Response:
        return self.rpc("ping")

    def health(self) -> httpx.Response:
        return self._http.get("/health")

    def get_tool_names(self) -> set[str]:
        """Convenience: list tools and return just the names."""
        resp = self.list_tools()
        if resp.status_code != 200:
            return set()
        tools = resp.json().get("result", {}).get("tools", [])
        return {t["name"] for t in tools}

    def call_tool_parsed(self, name: str, arguments: dict | None = None) -> dict[str, Any]:
        """Call a tool and return the parsed JSON content."""
        resp = self.call_tool(name, arguments)
        if resp.status_code != 200:
            return {"_error": f"HTTP {resp.status_code}"}
        result = resp.json().get("result", {})
        content = result.get("content", [])
        if content and content[0].get("type") == "text":
            try:
                return json.loads(content[0]["text"])
            except (json.JSONDecodeError, KeyError):
                return {"_raw": content[0].get("text", "")}
        return result

    def close(self):
        self._http.close()


# ---------------------------------------------------------------------------
# Consolidated server fixtures (v2) — primary
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def mcp_reference_data() -> MCPClient:
    """MCP client for consolidated Reference Data server (NPI + ICD-10 + CMS)."""
    client = MCPClient(_base_url("mcp-reference-data"))
    yield client
    client.close()


@pytest.fixture(scope="session")
def mcp_clinical_research() -> MCPClient:
    """MCP client for consolidated Clinical Research server (FHIR + PubMed + Trials)."""
    client = MCPClient(_base_url("mcp-clinical-research"))
    yield client
    client.close()


@pytest.fixture(scope="session")
def mcp_cosmos_rag() -> MCPClient:
    """MCP client for Cosmos RAG & Audit server."""
    client = MCPClient(_base_url("cosmos-rag"))
    yield client
    client.close()


# ---------------------------------------------------------------------------
# Legacy fixtures — backwards-compatible aliases (same ports, same servers)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def mcp_npi() -> MCPClient:
    """Legacy alias → mcp-reference-data (NPI tools)."""
    client = MCPClient(_base_url("npi-lookup"))
    yield client
    client.close()


@pytest.fixture(scope="session")
def mcp_icd10() -> MCPClient:
    """Legacy alias → mcp-reference-data (ICD-10 tools)."""
    client = MCPClient(_base_url("icd10-validation"))
    yield client
    client.close()


@pytest.fixture(scope="session")
def mcp_cms() -> MCPClient:
    """Legacy alias → mcp-reference-data (CMS tools)."""
    client = MCPClient(_base_url("cms-coverage"))
    yield client
    client.close()


@pytest.fixture(scope="session")
def mcp_fhir() -> MCPClient:
    """Legacy alias → mcp-clinical-research (FHIR tools)."""
    client = MCPClient(_base_url("fhir-operations"))
    yield client
    client.close()


@pytest.fixture(scope="session")
def mcp_pubmed() -> MCPClient:
    """Legacy alias → mcp-clinical-research (PubMed tools)."""
    client = MCPClient(_base_url("pubmed"))
    yield client
    client.close()


@pytest.fixture(scope="session")
def mcp_clinical_trials() -> MCPClient:
    """Legacy alias → mcp-clinical-research (Clinical Trials tools)."""
    client = MCPClient(_base_url("clinical-trials"))
    yield client
    client.close()
