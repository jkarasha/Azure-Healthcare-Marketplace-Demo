"""Backwards compatibility tests — verify consolidated servers are superset of legacy.

Ensures:
  1. Every tool from the old 7-server layout exists in the new 3-server layout
  2. Tool names used by agents/tools.py match what the servers actually expose
  3. Legacy test fixtures (mcp_npi, mcp_icd10, etc.) still reach the correct tools

Run with:
  pytest tests/integration/test_backwards_compat.py -v -m integration
"""

import pytest

from tests.conftest import CANONICAL_ALL_TOOLS

pytestmark = pytest.mark.integration


# ============================================================================
# Legacy tool name expectations (what the old 7 servers exposed)
# ============================================================================

LEGACY_NPI_TOOLS = {"lookup_npi", "validate_npi", "search_providers"}
LEGACY_ICD10_TOOLS = {"validate_icd10", "lookup_icd10", "search_icd10", "get_icd10_chapter"}
LEGACY_CMS_TOOLS = {
    "search_coverage",
    "get_coverage_by_cpt",
    "get_coverage_by_icd10",
    "check_medical_necessity",
    "get_mac_jurisdiction",
}
LEGACY_FHIR_TOOLS = {
    "search_patients",
    "get_patient",
    "get_patient_conditions",
    "get_patient_medications",
    "get_patient_observations",
    "get_patient_encounters",
    "search_practitioners",
    "validate_resource",
}
LEGACY_PUBMED_TOOLS = {
    "search_pubmed",
    "get_article",
    "get_articles_batch",
    "get_article_abstract",
    "find_related_articles",
    "search_clinical_queries",
}
LEGACY_CLINICAL_TRIALS_TOOLS = {
    "search_by_condition",
    "search_clinical_trials",
    "get_trial_details",
    "get_trial_eligibility",
    "get_trial_locations",
    "get_trial_results",
}
LEGACY_COSMOS_RAG_TOOLS = {
    "hybrid_search",
    "vector_search",
    "index_document",
    "record_audit_event",
    "get_audit_trail",
    "get_session_history",
}

LEGACY_ALL_TOOLS = (
    LEGACY_NPI_TOOLS
    | LEGACY_ICD10_TOOLS
    | LEGACY_CMS_TOOLS
    | LEGACY_FHIR_TOOLS
    | LEGACY_PUBMED_TOOLS
    | LEGACY_CLINICAL_TRIALS_TOOLS
    | LEGACY_COSMOS_RAG_TOOLS
)


class TestLegacyToolParity:
    """Consolidated servers are a superset of legacy tool inventory."""

    def test_consolidated_is_superset_of_legacy(self):
        """The canonical consolidated set must contain every legacy tool."""
        missing = LEGACY_ALL_TOOLS - CANONICAL_ALL_TOOLS
        assert not missing, f"Legacy tools missing from consolidated: {missing}"

    def test_no_renamed_tools(self):
        """Sanity: canonical exactly equals legacy (no renames)."""
        extra = CANONICAL_ALL_TOOLS - LEGACY_ALL_TOOLS
        assert not extra, f"Tools in consolidated but not legacy: {extra}"


class TestLegacyFixturesReachTools:
    """Verify that legacy fixture aliases connect to the right tools."""

    def test_mcp_npi_has_npi_tools(self, mcp_npi):
        """Legacy mcp_npi fixture reaches NPI tools on reference-data."""
        names = mcp_npi.get_tool_names()
        assert names >= LEGACY_NPI_TOOLS, f"Missing NPI tools: {LEGACY_NPI_TOOLS - names}"

    def test_mcp_icd10_has_icd10_tools(self, mcp_icd10):
        """Legacy mcp_icd10 fixture reaches ICD-10 tools on reference-data."""
        names = mcp_icd10.get_tool_names()
        assert names >= LEGACY_ICD10_TOOLS, f"Missing ICD-10 tools: {LEGACY_ICD10_TOOLS - names}"

    def test_mcp_cms_has_cms_tools(self, mcp_cms):
        """Legacy mcp_cms fixture reaches CMS tools on reference-data."""
        names = mcp_cms.get_tool_names()
        assert names >= LEGACY_CMS_TOOLS, f"Missing CMS tools: {LEGACY_CMS_TOOLS - names}"

    def test_mcp_fhir_has_fhir_tools(self, mcp_fhir):
        """Legacy mcp_fhir fixture reaches FHIR tools on clinical-research."""
        names = mcp_fhir.get_tool_names()
        assert names >= LEGACY_FHIR_TOOLS, f"Missing FHIR tools: {LEGACY_FHIR_TOOLS - names}"

    def test_mcp_pubmed_has_pubmed_tools(self, mcp_pubmed):
        """Legacy mcp_pubmed fixture reaches PubMed tools on clinical-research."""
        names = mcp_pubmed.get_tool_names()
        assert names >= LEGACY_PUBMED_TOOLS, f"Missing PubMed: {LEGACY_PUBMED_TOOLS - names}"

    def test_mcp_clinical_trials_has_trials_tools(self, mcp_clinical_trials):
        """Legacy mcp_clinical_trials fixture reaches Trials tools on clinical-research."""
        names = mcp_clinical_trials.get_tool_names()
        assert names >= LEGACY_CLINICAL_TRIALS_TOOLS, (
            f"Missing Trials tools: {LEGACY_CLINICAL_TRIALS_TOOLS - names}"
        )

    def test_mcp_cosmos_rag_has_rag_tools(self, mcp_cosmos_rag):
        """Legacy mcp_cosmos_rag fixture reaches RAG tools on cosmos-rag."""
        names = mcp_cosmos_rag.get_tool_names()
        assert names >= LEGACY_COSMOS_RAG_TOOLS, (
            f"Missing RAG tools: {LEGACY_COSMOS_RAG_TOOLS - names}"
        )


class TestAgentToolsAlignment:
    """
    Verify that tool name constants in src/agents/tools.py match the
    actual server-exposed tools. This prevents allowed_tools filtering
    from silently dropping tools.
    """

    def test_reference_data_tool_names_match(self, mcp_reference_data):
        from src.agents.tools import REFERENCE_DATA_ALL

        server_tools = mcp_reference_data.get_tool_names()
        agent_tools = set(REFERENCE_DATA_ALL)
        missing = agent_tools - server_tools
        extra = server_tools - agent_tools
        assert not missing, f"Agent lists tools not on server: {missing}"
        assert not extra, f"Server has tools not in agent constants: {extra}"

    def test_clinical_research_tool_names_match(self, mcp_clinical_research):
        from src.agents.tools import CLINICAL_RESEARCH_ALL

        server_tools = mcp_clinical_research.get_tool_names()
        agent_tools = set(CLINICAL_RESEARCH_ALL)
        missing = agent_tools - server_tools
        extra = server_tools - agent_tools
        assert not missing, f"Agent lists tools not on server: {missing}"
        assert not extra, f"Server has tools not in agent constants: {extra}"

    def test_cosmos_rag_tool_names_match(self, mcp_cosmos_rag):
        from src.agents.tools import COSMOS_RAG_TOOLS_ALL

        server_tools = mcp_cosmos_rag.get_tool_names()
        agent_tools = set(COSMOS_RAG_TOOLS_ALL)
        missing = agent_tools - server_tools
        extra = server_tools - agent_tools
        assert not missing, f"Agent lists tools not on server: {missing}"
        assert not extra, f"Server has tools not in agent constants: {extra}"
