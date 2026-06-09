"""
Cosmos DB RAG & Audit MCP Server - Azure Function App

Provides hybrid search (vector + BM25), document indexing, audit trail,
and agent memory capabilities via Azure Cosmos DB NoSQL.

Uses:
- DiskANN vector indexes with text-embedding-3-large (3072-dim)
- BM25 full-text search with RRF (Reciprocal Rank Fusion) for hybrid retrieval
- Immutable audit trail for healthcare workflow compliance
- Semantic agent memory with configurable TTL

Supports MCP Protocol 2025-06-18 with Streamable HTTP transport for APIM integration.
"""

import json
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import azure.functions as func
from azure.cosmos.aio import CosmosClient
from azure.identity.aio import DefaultAzureCredential
from openai import AsyncAzureOpenAI

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

logger = logging.getLogger(__name__)

# MCP Protocol version 2025-06-18 required for Azure APIM MCP Server feature
MCP_PROTOCOL_VERSION = os.environ.get("MCP_PROTOCOL_VERSION", "2025-06-18")

# Cosmos DB configuration
COSMOS_DB_ENDPOINT = os.environ.get("COSMOS_DB_ENDPOINT", "")
COSMOS_DB_DATABASE = os.environ.get("COSMOS_DB_DATABASE", "healthcare-mcp")

# Azure AI Services / OpenAI configuration
AI_SERVICES_ENDPOINT = os.environ.get("AZURE_AI_SERVICES_ENDPOINT", "")
EMBEDDING_DEPLOYMENT = os.environ.get("EMBEDDING_DEPLOYMENT_NAME", "text-embedding-3-large")
EMBEDDING_DIMENSIONS = int(os.environ.get("EMBEDDING_DIMENSIONS", "3072"))

# Container names (must match Bicep definitions in dependent-resources.bicep)
DOCUMENTS_CONTAINER = "documents"
AUDIT_TRAIL_CONTAINER = "audit-trail"
AGENT_MEMORY_CONTAINER = "agent-memory"

# Chunking defaults
DEFAULT_CHUNK_SIZE = 1000  # characters
DEFAULT_CHUNK_OVERLAP = 200  # characters


# ============================================================================
# Cosmos DB & Embedding Clients (lazy-initialized)
# ============================================================================

_credential: DefaultAzureCredential | None = None
_cosmos_client: CosmosClient | None = None
_openai_client: AsyncAzureOpenAI | None = None


def normalize_endpoint(raw_endpoint: str, env_var_name: str) -> str:
    """Validate and normalize an HTTP(S) endpoint from environment settings."""
    endpoint = (raw_endpoint or "").strip()
    if not endpoint:
        raise ValueError(f"{env_var_name} is not set. Configure it in local.settings.json or app settings.")

    if "://" not in endpoint:
        endpoint = f"https://{endpoint}"

    parsed = urlparse(endpoint)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError(f"{env_var_name} must be a valid URL with http:// or https:// (received: {raw_endpoint!r})")

    return endpoint.rstrip("/")


async def get_credential() -> DefaultAzureCredential:
    """Get or create shared Azure credential."""
    global _credential
    if _credential is None:
        _credential = DefaultAzureCredential()
    return _credential


async def get_cosmos_client() -> CosmosClient:
    """Get or create Cosmos DB client using managed identity."""
    global _cosmos_client
    if _cosmos_client is None:
        credential = await get_credential()
        cosmos_endpoint = normalize_endpoint(COSMOS_DB_ENDPOINT, "COSMOS_DB_ENDPOINT")
        _cosmos_client = CosmosClient(cosmos_endpoint, credential=credential)
    return _cosmos_client


async def get_openai_client() -> AsyncAzureOpenAI:
    """Get or create Azure OpenAI client for embeddings."""
    global _openai_client
    if _openai_client is None:
        ai_endpoint_raw = AI_SERVICES_ENDPOINT or os.environ.get("AZURE_OPENAI_ENDPOINT", "")
        ai_endpoint = normalize_endpoint(
            ai_endpoint_raw,
            "AZURE_AI_SERVICES_ENDPOINT (or AZURE_OPENAI_ENDPOINT fallback)",
        )

        credential = await get_credential()
        token = await credential.get_token("https://cognitiveservices.azure.com/.default")
        _openai_client = AsyncAzureOpenAI(
            azure_endpoint=ai_endpoint,
            api_version="2024-10-21",
            azure_ad_token=token.token,
        )
    return _openai_client


async def get_container(container_name: str):
    """Get a Cosmos DB container client."""
    client = await get_cosmos_client()
    database = client.get_database_client(COSMOS_DB_DATABASE)
    return database.get_container_client(container_name)


async def generate_embedding(text: str) -> list[float]:
    """Generate embedding vector for text using Azure OpenAI."""
    client = await get_openai_client()
    response = await client.embeddings.create(
        input=text,
        model=EMBEDDING_DEPLOYMENT,
        dimensions=EMBEDDING_DIMENSIONS,
    )
    return response.data[0].embedding


# ============================================================================
# Text Chunking
# ============================================================================


def chunk_text(text: str, chunk_size: int = DEFAULT_CHUNK_SIZE, overlap: int = DEFAULT_CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks at sentence boundaries."""
    if len(text) <= chunk_size:
        return [text]

    # Split on sentence boundaries
    sentences = []
    current = ""
    for char in text:
        current += char
        if char in ".!?\n" and len(current.strip()) > 0:
            sentences.append(current.strip())
            current = ""
    if current.strip():
        sentences.append(current.strip())

    chunks = []
    current_chunk = ""

    for sentence in sentences:
        if len(current_chunk) + len(sentence) + 1 > chunk_size and current_chunk:
            chunks.append(current_chunk.strip())
            # Keep overlap from end of current chunk
            words = current_chunk.split()
            overlap_text = ""
            for word in reversed(words):
                if len(overlap_text) + len(word) + 1 > overlap:
                    break
                overlap_text = word + " " + overlap_text
            current_chunk = overlap_text.strip() + " " + sentence
        else:
            current_chunk = (current_chunk + " " + sentence).strip()

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


# ============================================================================
# MCP Server Definition
# ============================================================================


@dataclass
class CosmosRAGServer:
    """MCP Server for Cosmos DB RAG, audit trail, and agent memory."""

    name: str = "cosmos-rag"
    version: str = "1.0.0"
    description: str = (
        "Healthcare MCP server for document RAG (hybrid search), " "audit trail, and agent memory via Azure Cosmos DB"
    )

    def get_tools(self) -> list[dict]:
        return [
            {
                "name": "index_document",
                "description": (
                    "Index a document for RAG retrieval. Chunks the content, generates "
                    "embeddings, and stores in Cosmos DB with full-text and vector indexes. "
                    "Use for clinical guidelines, payer policies, formularies, and other "
                    "reference documents."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Document title"},
                        "content": {"type": "string", "description": "Full document text content to index"},
                        "category": {
                            "type": "string",
                            "description": (
                                "Document category (partition key). Examples: "
                                "'clinical-guideline', 'payer-policy', 'formulary', "
                                "'procedure-code', 'coverage-determination'"
                            ),
                        },
                        "metadata": {
                            "type": "object",
                            "description": (
                                "Optional metadata (e.g., payer, effective_date, " "cpt_codes, icd10_codes, source_url)"
                            ),
                        },
                        "chunk_size": {
                            "type": "integer",
                            "description": "Characters per chunk (default 1000)",
                            "default": 1000,
                        },
                        "chunk_overlap": {
                            "type": "integer",
                            "description": "Overlap between chunks (default 200)",
                            "default": 200,
                        },
                    },
                    "required": ["title", "content", "category"],
                },
            },
            {
                "name": "hybrid_search",
                "description": (
                    "Search indexed documents using hybrid retrieval (vector similarity + "
                    "BM25 full-text) with RRF fusion. Best for natural language queries "
                    "where both semantic meaning and keyword matching matter. Use this for "
                    "finding relevant clinical guidelines, payer policies, and coverage "
                    "information."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Natural language search query"},
                        "category": {
                            "type": "string",
                            "description": "Optional category filter to narrow search scope",
                        },
                        "top_k": {
                            "type": "integer",
                            "description": "Number of results to return (default 5)",
                            "default": 5,
                            "minimum": 1,
                            "maximum": 20,
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "vector_search",
                "description": (
                    "Search indexed documents using pure vector similarity. Best for "
                    "semantic similarity queries where exact keyword matching is less "
                    "important. Use when the query meaning matters more than specific terms."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Natural language search query"},
                        "category": {"type": "string", "description": "Optional category filter"},
                        "top_k": {
                            "type": "integer",
                            "description": "Number of results to return (default 5)",
                            "default": 5,
                            "minimum": 1,
                            "maximum": 20,
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "record_audit_event",
                "description": (
                    "Record an audit event for a healthcare workflow. Creates an immutable "
                    "log entry in the audit trail for compliance and traceability. Use at "
                    "each decision point in prior authorization, clinical review, and "
                    "coverage determination workflows."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "workflow_id": {"type": "string", "description": "Unique workflow/session identifier"},
                        "workflow_type": {
                            "type": "string",
                            "description": (
                                "Type of workflow (e.g., 'prior-auth', 'clinical-trial', "
                                "'coverage-determination', 'literature-search')"
                            ),
                        },
                        "phase": {
                            "type": "string",
                            "description": (
                                "Workflow phase (e.g., 'compliance-gate', "
                                "'clinical-review', 'coverage-analysis', 'synthesis')"
                            ),
                        },
                        "agent_name": {"type": "string", "description": "Name of the agent performing the action"},
                        "action": {
                            "type": "string",
                            "description": "Action performed (e.g., 'npi_validated', 'policy_searched', 'decision_rendered')",
                        },
                        "input_summary": {
                            "type": "string",
                            "description": "Summary of input data (must not contain PHI)",
                        },
                        "output_summary": {
                            "type": "string",
                            "description": "Summary of output/decision (must not contain PHI)",
                        },
                        "status": {
                            "type": "string",
                            "enum": ["success", "failure", "warning", "pending"],
                            "description": "Outcome status of the action",
                        },
                        "details": {
                            "type": "object",
                            "description": "Additional structured details (codes, references, scores)",
                        },
                    },
                    "required": ["workflow_id", "workflow_type", "phase", "agent_name", "action", "status"],
                },
            },
            {
                "name": "get_audit_trail",
                "description": (
                    "Retrieve the audit trail for a specific workflow. Returns all audit "
                    "events ordered by timestamp. Use to review the decision history and "
                    "compliance record for prior authorization and other workflows."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "workflow_id": {"type": "string", "description": "Workflow/session identifier to query"},
                        "phase": {"type": "string", "description": "Optional: filter to specific workflow phase"},
                        "limit": {
                            "type": "integer",
                            "description": "Maximum events to return (default 50)",
                            "default": 50,
                        },
                    },
                    "required": ["workflow_id"],
                },
            },
            {
                "name": "get_session_history",
                "description": (
                    "Query audit trail across workflows by type and time range. Use to "
                    "find historical prior authorization decisions, review patterns, or "
                    "generate compliance reports across multiple sessions."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "workflow_type": {
                            "type": "string",
                            "description": "Filter by workflow type (e.g., 'prior-auth')",
                        },
                        "start_date": {
                            "type": "string",
                            "description": "ISO 8601 date string for range start (e.g., '2025-01-01T00:00:00Z')",
                        },
                        "end_date": {"type": "string", "description": "ISO 8601 date string for range end"},
                        "status": {
                            "type": "string",
                            "enum": ["success", "failure", "warning", "pending"],
                            "description": "Optional: filter by status",
                        },
                        "limit": {"type": "integer", "description": "Maximum results (default 25)", "default": 25},
                    },
                    "required": ["workflow_type"],
                },
            },
        ]

    def get_discovery_response(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "protocol_version": MCP_PROTOCOL_VERSION,
            "capabilities": {"tools": True, "resources": False, "prompts": False},
            "tools": self.get_tools(),
        }


server = CosmosRAGServer()


# ============================================================================
# Tool Handlers
# ============================================================================


async def index_document(args: dict) -> dict:
    """Index a document: chunk, embed, and upsert into Cosmos DB documents container."""
    title = args["title"]
    content = args["content"]
    category = args["category"]
    metadata = args.get("metadata", {})
    chunk_size = args.get("chunk_size", DEFAULT_CHUNK_SIZE)
    chunk_overlap = args.get("chunk_overlap", DEFAULT_CHUNK_OVERLAP)

    doc_id = str(uuid.uuid4())
    chunks = chunk_text(content, chunk_size, chunk_overlap)

    container = await get_container(DOCUMENTS_CONTAINER)
    indexed_chunks = []

    for i, chunk in enumerate(chunks):
        chunk_id = f"{doc_id}-chunk-{i}"
        embedding = await generate_embedding(chunk)

        item = {
            "id": chunk_id,
            "documentId": doc_id,
            "category": category,
            "title": title,
            "content": chunk,
            "embedding": embedding,
            "chunkIndex": i,
            "totalChunks": len(chunks),
            "metadata": metadata,
            "indexedAt": datetime.now(timezone.utc).isoformat(),
        }

        await container.upsert_item(item)
        indexed_chunks.append(
            {
                "chunkId": chunk_id,
                "chunkIndex": i,
                "contentLength": len(chunk),
            }
        )

    return {
        "documentId": doc_id,
        "title": title,
        "category": category,
        "totalChunks": len(chunks),
        "chunks": indexed_chunks,
        "status": "indexed",
    }


async def hybrid_search(args: dict) -> dict:
    """Hybrid search: vector (DiskANN) + BM25 full-text with RRF fusion."""
    query_text = args["query"]
    category = args.get("category")
    top_k = min(args.get("top_k", 5), 20)

    query_embedding = await generate_embedding(query_text)
    container = await get_container(DOCUMENTS_CONTAINER)

    # Build parameterized hybrid query with RRF
    # Cosmos DB NoSQL hybrid search: ORDER BY RANK RRF(VectorDistance, FullTextScore)
    where_clause = "WHERE c.category = @category" if category else ""
    params: list[dict[str, Any]] = []
    if category:
        params.append({"name": "@category", "value": category})
    params.append({"name": "@topK", "value": top_k})

    query = f"""
        SELECT TOP @topK
            c.id,
            c.documentId,
            c.title,
            c.content,
            c.category,
            c.chunkIndex,
            c.totalChunks,
            c.metadata,
            c.indexedAt
        FROM c
        {where_clause}
        ORDER BY RANK RRF(
            VectorDistance(c.embedding, {json.dumps(query_embedding)}),
            FullTextScore(c.content, ['{query_text.replace("'", "''")}'])
        )
    """

    results = []
    async for item in container.query_items(
        query=query,
        parameters=params,
        max_item_count=top_k,
    ):
        results.append(
            {
                "id": item["id"],
                "documentId": item.get("documentId"),
                "title": item.get("title"),
                "content": item.get("content"),
                "category": item.get("category"),
                "chunkIndex": item.get("chunkIndex"),
                "totalChunks": item.get("totalChunks"),
                "metadata": item.get("metadata", {}),
            }
        )

    return {
        "query": query_text,
        "searchType": "hybrid",
        "resultCount": len(results),
        "results": results,
    }


async def vector_search(args: dict) -> dict:
    """Pure vector similarity search using DiskANN index."""
    query_text = args["query"]
    category = args.get("category")
    top_k = min(args.get("top_k", 5), 20)

    query_embedding = await generate_embedding(query_text)
    container = await get_container(DOCUMENTS_CONTAINER)

    where_clause = "WHERE c.category = @category" if category else ""
    params: list[dict[str, Any]] = []
    if category:
        params.append({"name": "@category", "value": category})
    params.append({"name": "@topK", "value": top_k})

    query = f"""
        SELECT TOP @topK
            c.id,
            c.documentId,
            c.title,
            c.content,
            c.category,
            c.chunkIndex,
            c.totalChunks,
            c.metadata,
            c.indexedAt,
            VectorDistance(c.embedding, {json.dumps(query_embedding)}) AS score
        FROM c
        {where_clause}
        ORDER BY VectorDistance(c.embedding, {json.dumps(query_embedding)})
    """

    results = []
    async for item in container.query_items(
        query=query,
        parameters=params,
        max_item_count=top_k,
    ):
        results.append(
            {
                "id": item["id"],
                "documentId": item.get("documentId"),
                "title": item.get("title"),
                "content": item.get("content"),
                "category": item.get("category"),
                "chunkIndex": item.get("chunkIndex"),
                "totalChunks": item.get("totalChunks"),
                "metadata": item.get("metadata", {}),
                "score": item.get("score"),
            }
        )

    return {
        "query": query_text,
        "searchType": "vector",
        "resultCount": len(results),
        "results": results,
    }


async def record_audit_event(args: dict) -> dict:
    """Record an immutable audit event in the audit-trail container."""
    event_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    event = {
        "id": event_id,
        "workflowId": args["workflow_id"],
        "workflowType": args["workflow_type"],
        "phase": args["phase"],
        "agentName": args["agent_name"],
        "action": args["action"],
        "status": args["status"],
        "timestamp": now,
        "inputSummary": args.get("input_summary", ""),
        "outputSummary": args.get("output_summary", ""),
        "details": args.get("details", {}),
    }

    container = await get_container(AUDIT_TRAIL_CONTAINER)
    await container.create_item(event)

    return {
        "eventId": event_id,
        "workflowId": args["workflow_id"],
        "timestamp": now,
        "status": "recorded",
    }


async def get_audit_trail(args: dict) -> dict:
    """Query audit trail by workflow ID, ordered by timestamp."""
    workflow_id = args["workflow_id"]
    phase = args.get("phase")
    limit = min(args.get("limit", 50), 200)

    container = await get_container(AUDIT_TRAIL_CONTAINER)

    conditions = ["c.workflowId = @workflowId"]
    params: list[dict[str, Any]] = [
        {"name": "@workflowId", "value": workflow_id},
    ]
    if phase:
        conditions.append("c.phase = @phase")
        params.append({"name": "@phase", "value": phase})

    where = " AND ".join(conditions)
    query = f"""
        SELECT TOP {limit} *
        FROM c
        WHERE {where}
        ORDER BY c.workflowId ASC, c.timestamp ASC
    """

    events = []
    async for item in container.query_items(
        query=query,
        parameters=params,
        partition_key=workflow_id,
        max_item_count=limit,
    ):
        events.append(
            {
                "eventId": item["id"],
                "workflowId": item["workflowId"],
                "workflowType": item.get("workflowType"),
                "phase": item.get("phase"),
                "agentName": item.get("agentName"),
                "action": item.get("action"),
                "status": item.get("status"),
                "timestamp": item.get("timestamp"),
                "inputSummary": item.get("inputSummary"),
                "outputSummary": item.get("outputSummary"),
                "details": item.get("details", {}),
            }
        )

    return {
        "workflowId": workflow_id,
        "eventCount": len(events),
        "events": events,
    }


async def get_session_history(args: dict) -> dict:
    """Query audit trail across workflows by type and time range."""
    workflow_type = args["workflow_type"]
    start_date = args.get("start_date")
    end_date = args.get("end_date")
    status_filter = args.get("status")
    limit = min(args.get("limit", 25), 100)

    container = await get_container(AUDIT_TRAIL_CONTAINER)

    conditions = ["c.workflowType = @workflowType"]
    params: list[dict[str, Any]] = [
        {"name": "@workflowType", "value": workflow_type},
    ]

    if start_date:
        conditions.append("c.timestamp >= @startDate")
        params.append({"name": "@startDate", "value": start_date})
    if end_date:
        conditions.append("c.timestamp <= @endDate")
        params.append({"name": "@endDate", "value": end_date})
    if status_filter:
        conditions.append("c.status = @status")
        params.append({"name": "@status", "value": status_filter})

    where = " AND ".join(conditions)
    # Cross-partition query — uses composite index on (workflowType, timestamp DESC)
    query = f"""
        SELECT TOP {limit} *
        FROM c
        WHERE {where}
        ORDER BY c.workflowType ASC, c.timestamp DESC
    """

    events = []
    async for item in container.query_items(
        query=query,
        parameters=params,
        max_item_count=limit,
    ):
        events.append(
            {
                "eventId": item["id"],
                "workflowId": item["workflowId"],
                "workflowType": item.get("workflowType"),
                "phase": item.get("phase"),
                "agentName": item.get("agentName"),
                "action": item.get("action"),
                "status": item.get("status"),
                "timestamp": item.get("timestamp"),
                "inputSummary": item.get("inputSummary"),
                "outputSummary": item.get("outputSummary"),
            }
        )

    return {
        "workflowType": workflow_type,
        "eventCount": len(events),
        "events": events,
    }


# ============================================================================
# Tool Dispatch
# ============================================================================

TOOL_HANDLERS = {
    "index_document": index_document,
    "hybrid_search": hybrid_search,
    "vector_search": vector_search,
    "record_audit_event": record_audit_event,
    "get_audit_trail": get_audit_trail,
    "get_session_history": get_session_history,
}


# ============================================================================
# Azure Function Endpoints
# ============================================================================


@app.route(route=".well-known/mcp", methods=["GET"])
async def mcp_discovery(req: func.HttpRequest) -> func.HttpResponse:
    """MCP Discovery endpoint - returns server capabilities and tools."""
    return func.HttpResponse(
        json.dumps(server.get_discovery_response()),
        mimetype="application/json",
        headers={
            "X-MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
            "Cache-Control": "no-cache",
        },
    )


@app.route(route="mcp", methods=["GET"])
async def mcp_get(req: func.HttpRequest) -> func.HttpResponse:
    """MCP GET endpoint - used for SSE transport negotiation and capability discovery."""
    session_id = req.headers.get("Mcp-Session-Id", str(uuid.uuid4()))

    accept = req.headers.get("Accept", "")
    if "text/event-stream" in accept:
        return func.HttpResponse(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32600,
                        "message": "SSE transport not supported. Use POST for Streamable HTTP transport.",
                    },
                    "id": None,
                }
            ),
            status_code=405,
            mimetype="application/json",
            headers={
                "Allow": "POST",
                "X-MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
                "Mcp-Session-Id": session_id,
            },
        )

    return func.HttpResponse(
        json.dumps(
            {
                "name": server.name,
                "version": server.version,
                "protocol_version": MCP_PROTOCOL_VERSION,
                "transport": "streamable-http",
                "endpoint": "/mcp",
                "methods_supported": ["POST"],
            }
        ),
        mimetype="application/json",
        headers={
            "X-MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
            "Cache-Control": "no-cache",
        },
    )


@app.route(route="mcp", methods=["POST"])
async def mcp_message(req: func.HttpRequest) -> func.HttpResponse:
    """MCP Message endpoint - handles JSON-RPC messages via Streamable HTTP transport."""
    session_id = req.headers.get("Mcp-Session-Id", str(uuid.uuid4()))

    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "Parse error"},
                }
            ),
            status_code=400,
            mimetype="application/json",
        )

    method = body.get("method")
    params = body.get("params", {})
    msg_id = body.get("id")

    try:
        if method == "initialize":
            result = {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "serverInfo": {"name": server.name, "version": server.version},
                "capabilities": {"tools": {"listChanged": False}},
            }

        elif method == "tools/list":
            result = {"tools": server.get_tools()}

        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})

            handler = TOOL_HANDLERS.get(tool_name)
            if not handler:
                return func.HttpResponse(
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": msg_id,
                            "error": {"code": -32602, "message": f"Unknown tool: {tool_name}"},
                        }
                    ),
                    mimetype="application/json",
                )

            tool_result = await handler(tool_args)
            result = {
                "content": [{"type": "text", "text": json.dumps(tool_result)}],
            }

        elif method == "ping":
            result = {}

        else:
            return func.HttpResponse(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {"code": -32601, "message": f"Method not found: {method}"},
                    }
                ),
                mimetype="application/json",
            )

        return func.HttpResponse(
            json.dumps({"jsonrpc": "2.0", "id": msg_id, "result": result}),
            mimetype="application/json",
            headers={
                "X-MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
                "Mcp-Session-Id": session_id,
                "Cache-Control": "no-cache",
            },
        )

    except Exception as e:
        logger.exception("Error handling MCP message")
        return func.HttpResponse(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {"code": -32603, "message": f"Internal error: {e!s}"},
                }
            ),
            status_code=500,
            mimetype="application/json",
            headers={"Mcp-Session-Id": session_id},
        )


@app.route(route="health", methods=["GET"])
async def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """Health check endpoint."""
    health = {"status": "healthy", "server": server.name, "version": server.version}

    # Optionally check Cosmos DB connectivity. When COSMOS_DB_ENDPOINT is not
    # configured (e.g. local Docker smoke tests without Azure credentials),
    # skip the probe so the liveness check still reports healthy.
    if not COSMOS_DB_ENDPOINT:
        health["cosmos_db"] = "not_configured"
    else:
        try:
            client = await get_cosmos_client()
            database = client.get_database_client(COSMOS_DB_DATABASE)
            await database.read()
            health["cosmos_db"] = "connected"
        except Exception as e:
            health["cosmos_db"] = f"error: {e!s}"
            health["status"] = "degraded"

    status_code = 200 if health["status"] == "healthy" else 503
    return func.HttpResponse(
        json.dumps(health),
        mimetype="application/json",
        status_code=status_code,
    )
