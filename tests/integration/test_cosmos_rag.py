"""
Integration tests for Cosmos DB RAG MCP server.

Tests validate:
  1. Cosmos DB connectivity and MCP server health
  2. Document indexing (chunk + embed + upsert)
  3. Hybrid search (vector + BM25 with RRF)
  4. Vector search (pure semantic similarity)
  5. Audit trail recording and retrieval
  6. Session history queries

Requires:
  - cosmos-rag MCP server running on MCP_COSMOS_RAG_PORT (default 7077)
  - Cosmos DB emulator or live instance with healthcare-mcp database
  - Azure OpenAI endpoint for embeddings (or mock)
"""

import json
import uuid

import pytest

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Sample test data — small synthetic policy snippets (no real PHI)
# ---------------------------------------------------------------------------

SAMPLE_POLICY = {
    "title": "Test Policy — Knee Replacement Coverage",
    "category": "payer-policy",
    "content": (
        "Coverage Determination: Total Knee Arthroplasty (TKA). "
        "CPT Code 27447 is covered when the following criteria are met: "
        "1. Patient has documented moderate-to-severe osteoarthritis of the knee "
        "confirmed by weight-bearing radiographs showing Kellgren-Lawrence grade 3 or 4. "
        "2. Conservative treatment has been attempted for at least 3 months including "
        "physical therapy, NSAIDs, and/or corticosteroid injections without adequate relief. "
        "3. Pain and functional limitation significantly impair activities of daily living. "
        "4. BMI is below 40 kg/m², or the patient has been evaluated by a bariatric specialist. "
        "Medical necessity must be established by the treating orthopedic surgeon. "
        "Pre-authorization is required. Supporting documentation must include: "
        "operative report indication, imaging results, prior treatment records, "
        "and a letter of medical necessity. "
        "Exclusion criteria: active infection, insufficient bone stock, "
        "uncontrolled diabetes (HbA1c > 8.0%), or non-compliance with pre-operative protocols."
    ),
    "metadata": {
        "source_file": "test_policy.pdf",
        "case_ids": ["test_001"],
        "tags": ["orthopedic", "knee-replacement", "tka"],
        "document_type": "coverage-policy",
    },
}

SAMPLE_GUIDELINE = {
    "title": "Test Guideline — Biologic Therapy for Rheumatoid Arthritis",
    "category": "clinical-guideline",
    "content": (
        "Clinical Practice Guideline: Biologic DMARD Therapy for Rheumatoid Arthritis. "
        "Biologic disease-modifying antirheumatic drugs (bDMARDs) are indicated when "
        "conventional synthetic DMARDs (csDMARDs) such as methotrexate have failed "
        "after adequate trial of 3-6 months. Recommended biologics include: "
        "TNF inhibitors (adalimumab, etanercept, infliximab), IL-6 inhibitors (tocilizumab), "
        "T-cell co-stimulation modulators (abatacept), and B-cell depleting agents (rituximab). "
        "Step therapy is required: first-line biologic should be a TNF inhibitor unless "
        "contraindicated. Monitoring: CBC, LFTs, and TB screening before initiation; "
        "regular follow-up at 3-month intervals. Discontinuation criteria: lack of "
        "clinical response after 12 weeks at adequate dose."
    ),
    "metadata": {
        "source_file": "test_guideline.pdf",
        "tags": ["rheumatology", "biologic", "dmard"],
        "document_type": "clinical-guideline",
    },
}


# ============================================================================
# 1. Cosmos DB Health & MCP Discovery
# ============================================================================


class TestCosmosRAGDiscovery:
    """MCP discovery, initialization, and health check tests."""

    def test_health_endpoint(self, mcp_cosmos_rag):
        """Cosmos DB health check returns status."""
        resp = mcp_cosmos_rag._http.get("/health")
        assert resp.status_code in (200, 503)
        body = resp.json()
        assert "status" in body
        assert "cosmos_db" in body

    def test_health_cosmos_connected(self, mcp_cosmos_rag):
        """Cosmos DB is reachable and the database exists."""
        resp = mcp_cosmos_rag._http.get("/health")
        body = resp.json()
        assert body["cosmos_db"] == "connected", f"Cosmos DB not connected: {body.get('cosmos_db')}"

    def test_well_known_mcp(self, mcp_cosmos_rag):
        """MCP discovery endpoint returns server capabilities."""
        resp = mcp_cosmos_rag.discover()
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "cosmos-rag"
        assert "tools" in body

    def test_initialize(self, mcp_cosmos_rag):
        """MCP initialize handshake succeeds."""
        resp = mcp_cosmos_rag.initialize()
        assert resp.status_code == 200
        body = resp.json()
        result = body.get("result", {})
        assert result.get("protocolVersion") == "2025-06-18"

    def test_tools_list(self, mcp_cosmos_rag):
        """All expected RAG + audit tools are registered."""
        resp = mcp_cosmos_rag.list_tools()
        assert resp.status_code == 200
        tools = resp.json().get("result", {}).get("tools", [])
        tool_names = {t["name"] for t in tools}
        expected = {
            "index_document",
            "hybrid_search",
            "vector_search",
            "record_audit_event",
            "get_audit_trail",
            "get_session_history",
        }
        assert expected <= tool_names, f"Missing tools: {expected - tool_names}"


# ============================================================================
# 2. Document Indexing
# ============================================================================


class TestDocumentIndexing:
    """Test the index_document tool — chunk, embed, upsert."""

    def test_index_small_document(self, mcp_cosmos_rag):
        """Index a policy document and verify chunk count."""
        resp = mcp_cosmos_rag.call_tool(
            "index_document",
            {
                "title": SAMPLE_POLICY["title"],
                "content": SAMPLE_POLICY["content"],
                "category": SAMPLE_POLICY["category"],
                "metadata": SAMPLE_POLICY["metadata"],
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert not body.get("result", {}).get("isError", False), f"Tool error: {body}"

        result = json.loads(body["result"]["content"][0]["text"])
        assert result["status"] == "indexed"
        assert result["totalChunks"] >= 1
        assert result["category"] == "payer-policy"
        assert "documentId" in result

    def test_index_with_custom_chunking(self, mcp_cosmos_rag):
        """Index with custom chunk size and overlap."""
        resp = mcp_cosmos_rag.call_tool(
            "index_document",
            {
                "title": "Chunking Test Doc",
                "content": SAMPLE_GUIDELINE["content"],
                "category": "test-chunking",
                "chunk_size": 200,
                "chunk_overlap": 50,
            },
        )
        assert resp.status_code == 200
        result = json.loads(resp.json()["result"]["content"][0]["text"])
        assert result["status"] == "indexed"
        # With 200-char chunks, a ~800+ char doc should produce multiple chunks
        assert result["totalChunks"] >= 2

    def test_index_multiple_categories(self, mcp_cosmos_rag):
        """Index documents in different categories for search filtering."""
        for doc in [SAMPLE_POLICY, SAMPLE_GUIDELINE]:
            resp = mcp_cosmos_rag.call_tool(
                "index_document",
                {
                    "title": doc["title"],
                    "content": doc["content"],
                    "category": doc["category"],
                    "metadata": doc.get("metadata", {}),
                },
            )
            assert resp.status_code == 200
            result = json.loads(resp.json()["result"]["content"][0]["text"])
            assert result["status"] == "indexed"


# ============================================================================
# 3. Hybrid Search (Vector + BM25 with RRF)
# ============================================================================


class TestHybridSearch:
    """Test hybrid_search tool — requires indexed documents."""

    def test_hybrid_search_basic(self, mcp_cosmos_rag):
        """Hybrid search returns results for a relevant query."""
        # First ensure a doc is indexed
        mcp_cosmos_rag.call_tool(
            "index_document",
            {
                "title": SAMPLE_POLICY["title"],
                "content": SAMPLE_POLICY["content"],
                "category": SAMPLE_POLICY["category"],
            },
        )

        resp = mcp_cosmos_rag.call_tool(
            "hybrid_search",
            {
                "query": "knee replacement coverage criteria",
                "top_k": 5,
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert not body.get("result", {}).get("isError", False), f"Tool error: {body}"

        result = json.loads(body["result"]["content"][0]["text"])
        assert result["searchType"] == "hybrid"
        assert result["resultCount"] >= 1
        assert len(result["results"]) >= 1

        # Verify result structure
        first = result["results"][0]
        assert "content" in first
        assert "title" in first
        assert "documentId" in first

    def test_hybrid_search_with_category_filter(self, mcp_cosmos_rag):
        """Category filter narrows search to specific document type."""
        resp = mcp_cosmos_rag.call_tool(
            "hybrid_search",
            {
                "query": "CPT 27447 total knee arthroplasty",
                "category": "payer-policy",
                "top_k": 3,
            },
        )
        assert resp.status_code == 200
        result = json.loads(resp.json()["result"]["content"][0]["text"])
        for r in result["results"]:
            assert r["category"] == "payer-policy"

    def test_hybrid_search_no_results(self, mcp_cosmos_rag):
        """Search with unrelated query returns empty or low results gracefully."""
        resp = mcp_cosmos_rag.call_tool(
            "hybrid_search",
            {
                "query": "quantum computing blockchain decentralized",
                "category": "nonexistent-category",
                "top_k": 3,
            },
        )
        assert resp.status_code == 200
        result = json.loads(resp.json()["result"]["content"][0]["text"])
        assert result["searchType"] == "hybrid"
        # Should handle gracefully — 0 results is fine
        assert isinstance(result["results"], list)


# ============================================================================
# 4. Vector Search (Pure Semantic Similarity)
# ============================================================================


class TestVectorSearch:
    """Test vector_search tool — pure DiskANN similarity."""

    def test_vector_search_basic(self, mcp_cosmos_rag):
        """Vector search returns semantically similar results."""
        # Ensure docs are indexed
        mcp_cosmos_rag.call_tool(
            "index_document",
            {
                "title": SAMPLE_GUIDELINE["title"],
                "content": SAMPLE_GUIDELINE["content"],
                "category": SAMPLE_GUIDELINE["category"],
            },
        )

        resp = mcp_cosmos_rag.call_tool(
            "vector_search",
            {
                "query": "biologic therapy for autoimmune disease treatment options",
                "top_k": 5,
            },
        )
        assert resp.status_code == 200
        result = json.loads(resp.json()["result"]["content"][0]["text"])
        assert result["searchType"] == "vector"
        assert result["resultCount"] >= 1

        # Vector search should return similarity scores
        first = result["results"][0]
        assert "score" in first
        assert "content" in first

    def test_vector_search_top_k_limit(self, mcp_cosmos_rag):
        """top_k parameter limits result count."""
        resp = mcp_cosmos_rag.call_tool(
            "vector_search",
            {
                "query": "medical coverage policy",
                "top_k": 2,
            },
        )
        assert resp.status_code == 200
        result = json.loads(resp.json()["result"]["content"][0]["text"])
        assert len(result["results"]) <= 2


# ============================================================================
# 5. Audit Trail
# ============================================================================


class TestAuditTrail:
    """Test audit event recording and retrieval."""

    def test_record_audit_event(self, mcp_cosmos_rag):
        """Record an audit event and verify it was stored."""
        workflow_id = f"test-wf-{uuid.uuid4().hex[:8]}"

        resp = mcp_cosmos_rag.call_tool(
            "record_audit_event",
            {
                "workflow_id": workflow_id,
                "workflow_type": "prior-auth",
                "phase": "compliance-gate",
                "agent_name": "test-agent",
                "action": "npi_validated",
                "status": "success",
                "input_summary": "NPI 1234567890 for Dr. Smith",
                "output_summary": "NPI valid, active provider",
            },
        )
        assert resp.status_code == 200
        result = json.loads(resp.json()["result"]["content"][0]["text"])
        assert result["status"] == "recorded"
        assert result["workflowId"] == workflow_id
        assert "eventId" in result
        assert "timestamp" in result

    def test_get_audit_trail(self, mcp_cosmos_rag):
        """Record events then retrieve the trail for the workflow."""
        workflow_id = f"test-trail-{uuid.uuid4().hex[:8]}"

        # Record multiple events
        events = [
            {"phase": "intake", "action": "request_received", "status": "success"},
            {"phase": "compliance-gate", "action": "npi_validated", "status": "success"},
            {"phase": "compliance-gate", "action": "icd10_validated", "status": "success"},
            {"phase": "clinical-review", "action": "policy_searched", "status": "success"},
            {"phase": "synthesis", "action": "decision_rendered", "status": "success"},
        ]

        for evt in events:
            resp = mcp_cosmos_rag.call_tool(
                "record_audit_event",
                {
                    "workflow_id": workflow_id,
                    "workflow_type": "prior-auth",
                    "agent_name": "test-agent",
                    **evt,
                },
            )
            assert resp.status_code == 200

        # Retrieve full trail
        resp = mcp_cosmos_rag.call_tool(
            "get_audit_trail",
            {
                "workflow_id": workflow_id,
            },
        )
        assert resp.status_code == 200
        result = json.loads(resp.json()["result"]["content"][0]["text"])
        assert result["workflowId"] == workflow_id
        assert result["eventCount"] == 5

        # Verify ordering by timestamp
        timestamps = [e["timestamp"] for e in result["events"]]
        assert timestamps == sorted(timestamps), "Audit events should be ordered by timestamp"

    def test_get_audit_trail_filter_by_phase(self, mcp_cosmos_rag):
        """Filter audit trail by workflow phase."""
        workflow_id = f"test-phase-{uuid.uuid4().hex[:8]}"

        # Record events in different phases
        for phase in ["intake", "compliance-gate", "compliance-gate", "synthesis"]:
            mcp_cosmos_rag.call_tool(
                "record_audit_event",
                {
                    "workflow_id": workflow_id,
                    "workflow_type": "prior-auth",
                    "phase": phase,
                    "agent_name": "test-agent",
                    "action": "test_action",
                    "status": "success",
                },
            )

        # Filter to compliance-gate only
        resp = mcp_cosmos_rag.call_tool(
            "get_audit_trail",
            {
                "workflow_id": workflow_id,
                "phase": "compliance-gate",
            },
        )
        assert resp.status_code == 200
        result = json.loads(resp.json()["result"]["content"][0]["text"])
        assert result["eventCount"] == 2
        for evt in result["events"]:
            assert evt["phase"] == "compliance-gate"


# ============================================================================
# 6. Session History (Cross-Workflow)
# ============================================================================


class TestSessionHistory:
    """Test session history queries across workflows."""

    def test_get_session_history_by_type(self, mcp_cosmos_rag):
        """Query session history filtered by workflow type."""
        workflow_ids = [f"test-hist-{uuid.uuid4().hex[:8]}" for _ in range(3)]

        for wf_id in workflow_ids:
            mcp_cosmos_rag.call_tool(
                "record_audit_event",
                {
                    "workflow_id": wf_id,
                    "workflow_type": "prior-auth-test",
                    "phase": "synthesis",
                    "agent_name": "test-agent",
                    "action": "decision_rendered",
                    "status": "success",
                },
            )

        resp = mcp_cosmos_rag.call_tool(
            "get_session_history",
            {
                "workflow_type": "prior-auth-test",
                "limit": 10,
            },
        )
        assert resp.status_code == 200
        result = json.loads(resp.json()["result"]["content"][0]["text"])
        assert result["workflowType"] == "prior-auth-test"
        assert result["eventCount"] >= 3

    def test_get_session_history_by_status(self, mcp_cosmos_rag):
        """Filter session history by status."""
        workflow_id = f"test-status-{uuid.uuid4().hex[:8]}"

        mcp_cosmos_rag.call_tool(
            "record_audit_event",
            {
                "workflow_id": workflow_id,
                "workflow_type": "status-test",
                "phase": "compliance-gate",
                "agent_name": "test-agent",
                "action": "validation_failed",
                "status": "failure",
                "output_summary": "NPI not found in registry",
            },
        )

        resp = mcp_cosmos_rag.call_tool(
            "get_session_history",
            {
                "workflow_type": "status-test",
                "status": "failure",
            },
        )
        assert resp.status_code == 200
        result = json.loads(resp.json()["result"]["content"][0]["text"])
        for evt in result["events"]:
            assert evt["status"] == "failure"


# ============================================================================
# 7. End-to-End: Index → Search → Retrieve
# ============================================================================


class TestEndToEndRetrieval:
    """Full workflow: index a policy, then retrieve it via search."""

    def test_index_then_hybrid_retrieve(self, mcp_cosmos_rag):
        """Index a unique policy document, then find it via hybrid search."""
        unique_marker = uuid.uuid4().hex[:8]
        title = f"E2E Test Policy {unique_marker}"
        content = (
            f"Coverage Policy {unique_marker}: Spinal Fusion Surgery (CPT 22612). "
            "This procedure is covered for patients with documented degenerative disc "
            "disease, spondylolisthesis grade 2 or higher, or spinal instability confirmed "
            "by flexion-extension radiographs. Conservative management including physical "
            "therapy for at least 6 months must be documented. Pre-authorization required."
        )

        # Index
        resp = mcp_cosmos_rag.call_tool(
            "index_document",
            {
                "title": title,
                "content": content,
                "category": "payer-policy",
                "metadata": {"marker": unique_marker, "cpt_codes": ["22612"]},
            },
        )
        assert resp.status_code == 200
        index_result = json.loads(resp.json()["result"]["content"][0]["text"])
        doc_id = index_result["documentId"]

        # Search — the unique marker should help retrieve exactly this doc
        resp = mcp_cosmos_rag.call_tool(
            "hybrid_search",
            {
                "query": f"spinal fusion coverage {unique_marker}",
                "category": "payer-policy",
                "top_k": 3,
            },
        )
        assert resp.status_code == 200
        search_result = json.loads(resp.json()["result"]["content"][0]["text"])
        assert search_result["resultCount"] >= 1

        # Verify our document appears in results
        found_ids = {r["documentId"] for r in search_result["results"]}
        assert doc_id in found_ids, f"Indexed document {doc_id} not found in search results. " f"Got: {found_ids}"

    def test_index_then_vector_retrieve(self, mcp_cosmos_rag):
        """Index a unique guideline, then find it via vector search."""
        unique_marker = uuid.uuid4().hex[:8]
        title = f"E2E Guideline {unique_marker}"
        content = (
            f"Guideline {unique_marker}: Management of Type 2 Diabetes Mellitus. "
            "First-line therapy is metformin. If HbA1c target not met after 3 months, "
            "add a second agent: SGLT2 inhibitor for patients with cardiovascular disease, "
            "GLP-1 receptor agonist for patients with obesity, or DPP-4 inhibitor for "
            "patients who cannot tolerate the others. Insulin should be considered when "
            "HbA1c remains above 10% despite dual therapy."
        )

        # Index
        resp = mcp_cosmos_rag.call_tool(
            "index_document",
            {
                "title": title,
                "content": content,
                "category": "clinical-guideline",
                "metadata": {"marker": unique_marker},
            },
        )
        assert resp.status_code == 200
        index_result = json.loads(resp.json()["result"]["content"][0]["text"])
        doc_id = index_result["documentId"]

        # Vector search by semantic meaning
        resp = mcp_cosmos_rag.call_tool(
            "vector_search",
            {
                "query": "diabetes medication treatment algorithm metformin insulin",
                "category": "clinical-guideline",
                "top_k": 5,
            },
        )
        assert resp.status_code == 200
        search_result = json.loads(resp.json()["result"]["content"][0]["text"])
        assert search_result["resultCount"] >= 1

        found_ids = {r["documentId"] for r in search_result["results"]}
        assert doc_id in found_ids, f"Indexed guideline {doc_id} not found in vector search. Got: {found_ids}"
