"""Integration tests for the 3 consolidated MCP servers.

Tests MCP protocol compliance, tool inventory, health endpoints,
and sample tool invocations for each server.

Requires servers running locally:
  - mcp-reference-data:    port 7071
  - mcp-clinical-research: port 7072
  - cosmos-rag:            port 7073

Run with:
  pytest tests/integration/test_consolidated_servers.py -v -m integration
"""

import pytest

from tests.conftest import CANONICAL_TOOL_COUNTS, CANONICAL_TOOLS

pytestmark = pytest.mark.integration


# ============================================================================
# mcp-reference-data (NPI + ICD-10 + CMS) — port 7071
# ============================================================================


class TestReferenceDataDiscovery:
    """MCP protocol and discovery tests for reference-data."""

    def test_well_known_mcp(self, mcp_reference_data):
        resp = mcp_reference_data.discover()
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "mcp-reference-data"
        assert body["version"] == "2.0.0"
        assert "tools" in body

    def test_initialize(self, mcp_reference_data):
        resp = mcp_reference_data.initialize()
        assert resp.status_code == 200
        body = resp.json()
        assert body["result"]["protocolVersion"] == "2025-06-18"
        assert body["result"]["serverInfo"]["name"] == "mcp-reference-data"

    def test_ping(self, mcp_reference_data):
        resp = mcp_reference_data.ping()
        assert resp.status_code == 200
        assert "result" in resp.json()

    def test_health_endpoint(self, mcp_reference_data):
        resp = mcp_reference_data.health()
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert body["server"] == "mcp-reference-data"
        assert set(body["domains"]) == {"npi", "icd10", "cms"}

    def test_tools_list_has_correct_count(self, mcp_reference_data):
        """Verify the server exposes exactly 12 tools."""
        resp = mcp_reference_data.list_tools()
        assert resp.status_code == 200
        tools = resp.json()["result"]["tools"]
        assert len(tools) == CANONICAL_TOOL_COUNTS["mcp-reference-data"]

    def test_tools_list_matches_canonical(self, mcp_reference_data):
        """Verify all expected tool names are present."""
        names = mcp_reference_data.get_tool_names()
        expected = CANONICAL_TOOLS["mcp-reference-data"]
        assert names == expected, f"Missing: {expected - names}, Extra: {names - expected}"

    def test_tools_have_input_schema(self, mcp_reference_data):
        """Every tool must declare an inputSchema."""
        resp = mcp_reference_data.list_tools()
        tools = resp.json()["result"]["tools"]
        for tool in tools:
            assert "inputSchema" in tool, f"Tool {tool['name']} missing inputSchema"
            assert tool["inputSchema"]["type"] == "object"


class TestReferenceDataNPITools:
    """NPI domain tools on reference-data server."""

    def test_lookup_npi(self, mcp_reference_data):
        resp = mcp_reference_data.call_tool("lookup_npi", {"npi": "1234567890"})
        assert resp.status_code == 200
        assert not resp.json()["result"].get("isError", False)

    def test_validate_npi(self, mcp_reference_data):
        resp = mcp_reference_data.call_tool("validate_npi", {"npi": "1234567890"})
        assert resp.status_code == 200

    def test_search_providers(self, mcp_reference_data):
        resp = mcp_reference_data.call_tool(
            "search_providers", {"last_name": "Smith", "state": "NY"}
        )
        assert resp.status_code == 200
        assert not resp.json()["result"].get("isError", False)


class TestReferenceDataICD10Tools:
    """ICD-10 domain tools on reference-data server."""

    def test_validate_icd10(self, mcp_reference_data):
        resp = mcp_reference_data.call_tool("validate_icd10", {"code": "M17.11"})
        assert resp.status_code == 200

    def test_lookup_icd10(self, mcp_reference_data):
        resp = mcp_reference_data.call_tool("lookup_icd10", {"code": "E11.9"})
        assert resp.status_code == 200

    def test_search_icd10(self, mcp_reference_data):
        resp = mcp_reference_data.call_tool("search_icd10", {"query": "diabetes"})
        assert resp.status_code == 200

    def test_get_icd10_chapter(self, mcp_reference_data):
        resp = mcp_reference_data.call_tool("get_icd10_chapter", {"code_prefix": "E11"})
        assert resp.status_code == 200


class TestReferenceDataCMSTools:
    """CMS coverage domain tools on reference-data server."""

    def test_search_coverage(self, mcp_reference_data):
        resp = mcp_reference_data.call_tool(
            "search_coverage", {"query": "knee replacement"}
        )
        assert resp.status_code == 200

    def test_get_coverage_by_cpt(self, mcp_reference_data):
        resp = mcp_reference_data.call_tool("get_coverage_by_cpt", {"cpt_code": "27447"})
        assert resp.status_code == 200

    def test_get_coverage_by_icd10(self, mcp_reference_data):
        resp = mcp_reference_data.call_tool("get_coverage_by_icd10", {"icd10_code": "M17.11"})
        assert resp.status_code == 200

    def test_check_medical_necessity(self, mcp_reference_data):
        resp = mcp_reference_data.call_tool(
            "check_medical_necessity",
            {"cpt_code": "27447", "icd10_codes": ["M17.11"]},
        )
        assert resp.status_code == 200

    def test_get_mac_jurisdiction(self, mcp_reference_data):
        resp = mcp_reference_data.call_tool("get_mac_jurisdiction", {"state": "NY"})
        assert resp.status_code == 200


# ============================================================================
# mcp-clinical-research (FHIR + PubMed + ClinicalTrials) — port 7072
# ============================================================================


class TestClinicalResearchDiscovery:
    """MCP protocol and discovery tests for clinical-research."""

    def test_well_known_mcp(self, mcp_clinical_research):
        resp = mcp_clinical_research.discover()
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "mcp-clinical-research"
        assert body["version"] == "2.0.0"

    def test_initialize(self, mcp_clinical_research):
        resp = mcp_clinical_research.initialize()
        assert resp.status_code == 200
        body = resp.json()
        assert body["result"]["protocolVersion"] == "2025-06-18"
        assert body["result"]["serverInfo"]["name"] == "mcp-clinical-research"

    def test_ping(self, mcp_clinical_research):
        resp = mcp_clinical_research.ping()
        assert resp.status_code == 200

    def test_health_endpoint(self, mcp_clinical_research):
        resp = mcp_clinical_research.health()
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert body["server"] == "mcp-clinical-research"
        assert set(body["domains"]) == {"fhir", "pubmed", "clinical-trials"}

    def test_tools_list_has_correct_count(self, mcp_clinical_research):
        """Verify the server exposes exactly 20 tools."""
        resp = mcp_clinical_research.list_tools()
        assert resp.status_code == 200
        tools = resp.json()["result"]["tools"]
        assert len(tools) == CANONICAL_TOOL_COUNTS["mcp-clinical-research"]

    def test_tools_list_matches_canonical(self, mcp_clinical_research):
        """Verify all expected tool names are present."""
        names = mcp_clinical_research.get_tool_names()
        expected = CANONICAL_TOOLS["mcp-clinical-research"]
        assert names == expected, f"Missing: {expected - names}, Extra: {names - expected}"


class TestClinicalResearchPubMedTools:
    """PubMed domain tools on clinical-research server."""

    def test_search_pubmed(self, mcp_clinical_research):
        resp = mcp_clinical_research.call_tool(
            "search_pubmed", {"query": "adalimumab crohn's disease"}
        )
        assert resp.status_code == 200

    def test_search_clinical_queries(self, mcp_clinical_research):
        resp = mcp_clinical_research.call_tool(
            "search_clinical_queries",
            {"query": "diabetes treatment", "category": "therapy"},
        )
        assert resp.status_code == 200


class TestClinicalResearchTrialsTools:
    """Clinical Trials domain tools on clinical-research server."""

    def test_search_clinical_trials(self, mcp_clinical_research):
        resp = mcp_clinical_research.call_tool(
            "search_clinical_trials",
            {"condition": "breast cancer", "status": "RECRUITING"},
        )
        assert resp.status_code == 200

    def test_search_by_condition(self, mcp_clinical_research):
        resp = mcp_clinical_research.call_tool(
            "search_by_condition", {"condition": "diabetes"}
        )
        assert resp.status_code == 200

    def test_unknown_tool_returns_error(self, mcp_clinical_research):
        """Calling a non-existent tool should return a JSON-RPC error, not 500."""
        resp = mcp_clinical_research.call_tool("nonexistent_tool", {})
        assert resp.status_code == 200  # JSON-RPC error is 200 with error body
        body = resp.json()
        assert "error" in body


# ============================================================================
# cosmos-rag — port 7073
# ============================================================================


class TestCosmosRagDiscovery:
    """MCP protocol and discovery tests for cosmos-rag."""

    def test_well_known_mcp(self, mcp_cosmos_rag):
        resp = mcp_cosmos_rag.discover()
        assert resp.status_code == 200

    def test_initialize(self, mcp_cosmos_rag):
        resp = mcp_cosmos_rag.initialize()
        assert resp.status_code == 200
        body = resp.json()
        assert body["result"]["protocolVersion"] == "2025-06-18"

    def test_ping(self, mcp_cosmos_rag):
        resp = mcp_cosmos_rag.ping()
        assert resp.status_code == 200

    def test_tools_list_has_correct_count(self, mcp_cosmos_rag):
        """Verify the server exposes exactly 6 tools."""
        resp = mcp_cosmos_rag.list_tools()
        assert resp.status_code == 200
        tools = resp.json()["result"]["tools"]
        assert len(tools) == CANONICAL_TOOL_COUNTS["cosmos-rag"]

    def test_tools_list_matches_canonical(self, mcp_cosmos_rag):
        """Verify all expected tool names are present."""
        names = mcp_cosmos_rag.get_tool_names()
        expected = CANONICAL_TOOLS["cosmos-rag"]
        assert names == expected, f"Missing: {expected - names}, Extra: {names - expected}"


# ============================================================================
# Cross-server: total tool inventory
# ============================================================================


class TestTotalToolInventory:
    """Verify combined tool count across all 3 servers matches canonical set."""

    def test_total_tool_count(
        self, mcp_reference_data, mcp_clinical_research, mcp_cosmos_rag
    ):
        """All 3 servers combined should expose exactly 38 tools."""
        all_names = set()
        all_names |= mcp_reference_data.get_tool_names()
        all_names |= mcp_clinical_research.get_tool_names()
        all_names |= mcp_cosmos_rag.get_tool_names()

        from tests.conftest import CANONICAL_ALL_TOOLS

        assert all_names == CANONICAL_ALL_TOOLS, (
            f"Missing: {CANONICAL_ALL_TOOLS - all_names}, "
            f"Extra: {all_names - CANONICAL_ALL_TOOLS}"
        )

    def test_no_tool_name_overlap(
        self, mcp_reference_data, mcp_clinical_research, mcp_cosmos_rag
    ):
        """No two servers should expose the same tool name."""
        ref = mcp_reference_data.get_tool_names()
        clin = mcp_clinical_research.get_tool_names()
        rag = mcp_cosmos_rag.get_tool_names()

        assert not (ref & clin), f"Overlap ref/clin: {ref & clin}"
        assert not (ref & rag), f"Overlap ref/rag: {ref & rag}"
        assert not (clin & rag), f"Overlap clin/rag: {clin & rag}"
