"""
MCP Tool factory for Healthcare Agent Orchestration.

Creates MCPStreamableHTTPTool instances for the 3 consolidated MCP servers:
  - reference-data:     NPI + ICD-10 + CMS (12 tools)
  - clinical-research:  FHIR + PubMed + ClinicalTrials (20 tools)
  - cosmos-rag:         Cosmos DB RAG & Audit (6 tools)

Each agent role gets a scoped view via allowed_tools filtering.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import httpx
from agent_framework import MCPStreamableHTTPTool

from .config import APIM_SUBSCRIPTION_KEY_HEADER

if TYPE_CHECKING:
    from .config import MCPEndpoints

logger = logging.getLogger(__name__)


def _build_http_client(subscription_key: str | None) -> httpx.AsyncClient | None:
    """Create a shared httpx client that injects the APIM subscription key header."""
    if not subscription_key:
        return None
    return httpx.AsyncClient(
        headers={APIM_SUBSCRIPTION_KEY_HEADER: subscription_key},
        timeout=httpx.Timeout(60.0, connect=30.0),
    )


# ---------------------------------------------------------------------------
# Tool name constants — used for allowed_tools scoping per agent role
# ---------------------------------------------------------------------------

# --- Reference Data server (NPI + ICD-10 + CMS) ---
NPI_TOOLS_COMPLIANCE = ["validate_npi", "lookup_npi"]
NPI_TOOLS_SEARCH = ["search_providers"]

ICD10_TOOLS_COMPLIANCE = ["validate_icd10", "lookup_icd10"]
ICD10_TOOLS_SEARCH = ["search_icd10", "get_icd10_chapter"]

CMS_TOOLS_ALL = [
    "search_coverage",
    "get_coverage_by_cpt",
    "get_coverage_by_icd10",
    "check_medical_necessity",
    "get_mac_jurisdiction",
]

REFERENCE_DATA_COMPLIANCE = NPI_TOOLS_COMPLIANCE + ICD10_TOOLS_COMPLIANCE
REFERENCE_DATA_COVERAGE = CMS_TOOLS_ALL + ICD10_TOOLS_SEARCH
REFERENCE_DATA_ALL = (
    NPI_TOOLS_COMPLIANCE + NPI_TOOLS_SEARCH + ICD10_TOOLS_COMPLIANCE + ICD10_TOOLS_SEARCH + CMS_TOOLS_ALL
)

# --- Clinical Research server (FHIR + PubMed + ClinicalTrials) ---
FHIR_TOOLS_ALL = [
    "search_patients",
    "get_patient",
    "get_patient_conditions",
    "get_patient_medications",
    "get_patient_observations",
    "get_patient_encounters",
    "search_practitioners",
    "validate_resource",
]

PUBMED_TOOLS_ALL = [
    "search_pubmed",
    "get_article",
    "get_articles_batch",
    "get_article_abstract",
    "find_related_articles",
    "search_clinical_queries",
]

CLINICAL_TRIALS_TOOLS_ALL = [
    "search_clinical_trials",
    "get_trial_details",
    "get_trial_eligibility",
    "get_trial_locations",
    "search_by_condition",
    "get_trial_results",
]

CLINICAL_RESEARCH_ALL = FHIR_TOOLS_ALL + PUBMED_TOOLS_ALL + CLINICAL_TRIALS_TOOLS_ALL

# --- Cosmos RAG server ---
COSMOS_RAG_TOOLS_SEARCH = [
    "hybrid_search",
    "vector_search",
]

COSMOS_RAG_TOOLS_INDEX = [
    "index_document",
]

COSMOS_RAG_TOOLS_AUDIT = [
    "record_audit_event",
    "get_audit_trail",
    "get_session_history",
]

COSMOS_RAG_TOOLS_ALL = COSMOS_RAG_TOOLS_SEARCH + COSMOS_RAG_TOOLS_INDEX + COSMOS_RAG_TOOLS_AUDIT


# ---------------------------------------------------------------------------
# Factory functions — one per consolidated server
# ---------------------------------------------------------------------------


def create_reference_data_tool(
    url: str,
    *,
    allowed_tools: list[str] | None = None,
    name: str = "Reference Data (NPI + ICD-10 + CMS)",
    http_client: httpx.AsyncClient | None = None,
) -> MCPStreamableHTTPTool:
    """Create an MCP tool connected to the consolidated Reference Data server."""
    return MCPStreamableHTTPTool(
        name=name,
        url=url,
        allowed_tools=allowed_tools,
        description="NPI provider lookup, ICD-10-CM validation, CMS Medicare coverage policies",
        http_client=http_client,
        load_prompts=False,
    )


def create_clinical_research_tool(
    url: str,
    *,
    allowed_tools: list[str] | None = None,
    name: str = "Clinical Research (FHIR + PubMed + Trials)",
    http_client: httpx.AsyncClient | None = None,
) -> MCPStreamableHTTPTool:
    """Create an MCP tool connected to the consolidated Clinical Research server."""
    return MCPStreamableHTTPTool(
        name=name,
        url=url,
        allowed_tools=allowed_tools,
        description="FHIR patient data, PubMed literature search, ClinicalTrials.gov integration",
        http_client=http_client,
        load_prompts=False,
    )


def create_cosmos_rag_tool(
    url: str,
    *,
    allowed_tools: list[str] | None = None,
    name: str = "Cosmos RAG & Audit",
    http_client: httpx.AsyncClient | None = None,
) -> MCPStreamableHTTPTool:
    """Create an MCP tool connected to the Cosmos DB RAG & Audit server."""
    return MCPStreamableHTTPTool(
        name=name,
        url=url,
        allowed_tools=allowed_tools,
        description="Cosmos DB RAG — hybrid search, document indexing, audit trail, agent memory",
        http_client=http_client,
        load_prompts=False,
    )


@dataclass
class MCPToolKit:
    """
    Convenience container that holds the 3 consolidated MCP tool instances.

    Usage::

        toolkit = MCPToolKit.from_endpoints(config.endpoints, subscription_key="...")
        async with toolkit:
            agent = Agent(..., tools=toolkit.compliance_tools())
    """

    reference_data: MCPStreamableHTTPTool
    clinical_research: MCPStreamableHTTPTool
    cosmos_rag: MCPStreamableHTTPTool

    # Keep a flat list so we can enter/exit all at once
    _all: list[MCPStreamableHTTPTool] = field(default_factory=list, repr=False)
    # Shared httpx client with APIM subscription key header
    _http_client: httpx.AsyncClient | None = field(default=None, repr=False)

    @classmethod
    def from_endpoints(
        cls,
        endpoints: MCPEndpoints,
        subscription_key: str | None = None,
    ) -> MCPToolKit:
        client = _build_http_client(subscription_key)
        reference_data = create_reference_data_tool(endpoints.reference_data, http_client=client)
        clinical_research = create_clinical_research_tool(endpoints.clinical_research, http_client=client)
        cosmos_rag = create_cosmos_rag_tool(endpoints.cosmos_rag, http_client=client)
        return cls(
            reference_data=reference_data,
            clinical_research=clinical_research,
            cosmos_rag=cosmos_rag,
            _all=[reference_data, clinical_research, cosmos_rag],
            _http_client=client,
        )

    async def __aenter__(self) -> MCPToolKit:
        for tool in self._all:
            await tool.__aenter__()
        return self

    async def __aexit__(self, *exc: object) -> None:
        for tool in reversed(self._all):
            try:
                await tool.__aexit__(None, None, None)
            except Exception:
                logger.warning("Error closing MCP tool %s", tool.name, exc_info=True)
        # Close the shared httpx client
        if self._http_client:
            try:
                await self._http_client.aclose()
            except Exception:
                logger.warning("Error closing shared httpx client", exc_info=True)

    # ----- Role-based groupings (scoped via allowed_tools) -----

    def compliance_tools(self) -> list[MCPStreamableHTTPTool]:
        """Tools for the Compliance Agent: NPI + ICD-10 validation from reference-data."""
        return [
            create_reference_data_tool(
                self.reference_data.url,
                allowed_tools=REFERENCE_DATA_COMPLIANCE,
                name="Reference Data (Compliance)",
                http_client=self._http_client,
            ),
        ]

    def clinical_reviewer_tools(self) -> list[MCPStreamableHTTPTool]:
        """Tools for the Clinical Reviewer Agent: FHIR + PubMed + Clinical Trials."""
        return [
            create_clinical_research_tool(
                self.clinical_research.url,
                name="Clinical Research (Reviewer)",
                http_client=self._http_client,
            ),
        ]

    def coverage_tools(self) -> list[MCPStreamableHTTPTool]:
        """Tools for the Coverage Agent: CMS + ICD-10 search + RAG policy search."""
        return [
            create_reference_data_tool(
                self.reference_data.url,
                allowed_tools=REFERENCE_DATA_COVERAGE,
                name="Reference Data (Coverage)",
                http_client=self._http_client,
            ),
            create_cosmos_rag_tool(
                self.cosmos_rag.url,
                allowed_tools=COSMOS_RAG_TOOLS_SEARCH,
                name="RAG (Coverage)",
                http_client=self._http_client,
            ),
        ]

    def patient_tools(self) -> list[MCPStreamableHTTPTool]:
        """Tools for Patient Data Agent: FHIR + NPI (provider search)."""
        return [
            create_clinical_research_tool(
                self.clinical_research.url,
                allowed_tools=FHIR_TOOLS_ALL,
                name="Clinical Research (Patient)",
                http_client=self._http_client,
            ),
            create_reference_data_tool(
                self.reference_data.url,
                allowed_tools=NPI_TOOLS_SEARCH,
                name="Reference Data (Patient)",
                http_client=self._http_client,
            ),
        ]

    def literature_tools(self) -> list[MCPStreamableHTTPTool]:
        """Tools for the Literature Agent: PubMed subset of clinical-research."""
        return [
            create_clinical_research_tool(
                self.clinical_research.url,
                allowed_tools=PUBMED_TOOLS_ALL,
                name="Clinical Research (Literature)",
                http_client=self._http_client,
            ),
        ]

    def trials_research_tools(self) -> list[MCPStreamableHTTPTool]:
        """Tools for the Trials Research Agent: Clinical Trials + PubMed."""
        return [
            create_clinical_research_tool(
                self.clinical_research.url,
                allowed_tools=CLINICAL_TRIALS_TOOLS_ALL + PUBMED_TOOLS_ALL,
                name="Clinical Research (Trials)",
                http_client=self._http_client,
            ),
        ]

    # ----- Orchestrator-level groupings -----

    def rag_search_tools(self) -> list[MCPStreamableHTTPTool]:
        """Tools for RAG retrieval: hybrid and vector search over indexed documents."""
        return [
            create_cosmos_rag_tool(
                self.cosmos_rag.url,
                allowed_tools=COSMOS_RAG_TOOLS_SEARCH,
                name="RAG (Search)",
                http_client=self._http_client,
            ),
        ]

    def audit_tools(self) -> list[MCPStreamableHTTPTool]:
        """Tools for audit trail: record events, query trails and history."""
        return [
            create_cosmos_rag_tool(
                self.cosmos_rag.url,
                allowed_tools=COSMOS_RAG_TOOLS_AUDIT,
                name="Audit Trail",
                http_client=self._http_client,
            ),
        ]

    def indexing_tools(self) -> list[MCPStreamableHTTPTool]:
        """Tools for document indexing: chunk, embed, and store documents."""
        return [
            create_cosmos_rag_tool(
                self.cosmos_rag.url,
                allowed_tools=COSMOS_RAG_TOOLS_INDEX,
                name="RAG (Index)",
                http_client=self._http_client,
            ),
        ]

    def all_tools(self) -> list[MCPStreamableHTTPTool]:
        """All 3 consolidated MCP tools — for the top-level Healthcare Orchestrator."""
        return [
            create_reference_data_tool(
                self.reference_data.url, name="Reference Data", http_client=self._http_client
            ),
            create_clinical_research_tool(
                self.clinical_research.url, name="Clinical Research", http_client=self._http_client
            ),
            create_cosmos_rag_tool(
                self.cosmos_rag.url, name="Cosmos RAG & Audit", http_client=self._http_client
            ),
        ]

    def prior_auth_tools(self) -> list[MCPStreamableHTTPTool]:
        """All tools for Prior Auth Orchestrator — all 3 consolidated servers."""
        return [
            create_reference_data_tool(
                self.reference_data.url, name="Reference Data (PA)", http_client=self._http_client
            ),
            create_clinical_research_tool(
                self.clinical_research.url, name="Clinical Research (PA)", http_client=self._http_client
            ),
            create_cosmos_rag_tool(
                self.cosmos_rag.url, name="RAG & Audit (PA)", http_client=self._http_client,
            ),
        ]

    def clinical_trial_protocol_tools(self) -> list[MCPStreamableHTTPTool]:
        """Tools for the Clinical Trial Protocol Orchestrator: Trials + PubMed."""
        return [
            create_clinical_research_tool(
                self.clinical_research.url,
                allowed_tools=CLINICAL_TRIALS_TOOLS_ALL + PUBMED_TOOLS_ALL,
                name="Clinical Research (Protocol)",
                http_client=self._http_client,
            ),
        ]

    def literature_evidence_tools(self) -> list[MCPStreamableHTTPTool]:
        """Tools for the Literature & Evidence Orchestrator: PubMed + Trials."""
        return [
            create_clinical_research_tool(
                self.clinical_research.url,
                allowed_tools=PUBMED_TOOLS_ALL + CLINICAL_TRIALS_TOOLS_ALL,
                name="Clinical Research (Evidence)",
                http_client=self._http_client,
            ),
        ]
