"""
Clinical Research MCP Server — Consolidated Azure Function App

Combines FHIR Operations, PubMed/MEDLINE, and Clinical Trials into a single
MCP server. All 20 tools are exposed through one endpoint.

Domains:
  - FHIR: Patient search, conditions, observations, medications, encounters (Azure API for FHIR)
  - PubMed: Article search, clinical queries, batch retrieval, abstracts (NCBI E-utilities)
  - ClinicalTrials: Trial search, eligibility, locations, results (ClinicalTrials.gov API v2)
"""

import json
import logging
import os
import uuid

import azure.functions as func

from fhir_tools import HANDLERS as FHIR_HANDLERS
from fhir_tools import TOOLS as FHIR_TOOLS
from pubmed_tools import HANDLERS as PUBMED_HANDLERS
from pubmed_tools import TOOLS as PUBMED_TOOLS
from clinical_trials_tools import HANDLERS as TRIALS_HANDLERS
from clinical_trials_tools import TOOLS as TRIALS_TOOLS

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

logger = logging.getLogger(__name__)

MCP_PROTOCOL_VERSION = os.environ.get("MCP_PROTOCOL_VERSION", "2025-06-18")

SERVER_NAME = "mcp-clinical-research"
SERVER_VERSION = "2.0.0"
SERVER_DESCRIPTION = (
    "Consolidated healthcare MCP server for clinical research: "
    "FHIR patient data, PubMed literature search, and ClinicalTrials.gov integration"
)

# Merge all tools and handlers from domain modules
ALL_TOOLS = FHIR_TOOLS + PUBMED_TOOLS + TRIALS_TOOLS
ALL_HANDLERS = {**FHIR_HANDLERS, **PUBMED_HANDLERS, **TRIALS_HANDLERS}


# ============================================================================
# Azure Function Endpoints
# ============================================================================


@app.route(route=".well-known/mcp", methods=["GET"])
async def mcp_discovery(req: func.HttpRequest) -> func.HttpResponse:
    """MCP Discovery endpoint — returns server capabilities and all 20 tools."""
    return func.HttpResponse(
        json.dumps(
            {
                "name": SERVER_NAME,
                "version": SERVER_VERSION,
                "description": SERVER_DESCRIPTION,
                "protocol_version": MCP_PROTOCOL_VERSION,
                "capabilities": {"tools": True, "resources": False, "prompts": False},
                "tools": ALL_TOOLS,
            }
        ),
        mimetype="application/json",
        headers={"X-MCP-Protocol-Version": MCP_PROTOCOL_VERSION, "Cache-Control": "no-cache"},
    )


@app.route(route="mcp", methods=["GET"])
async def mcp_get(req: func.HttpRequest) -> func.HttpResponse:
    """MCP GET — transport negotiation. Directs clients to use POST."""
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
            headers={"Allow": "POST", "X-MCP-Protocol-Version": MCP_PROTOCOL_VERSION, "Mcp-Session-Id": session_id},
        )

    return func.HttpResponse(
        json.dumps(
            {
                "name": SERVER_NAME,
                "version": SERVER_VERSION,
                "protocol_version": MCP_PROTOCOL_VERSION,
                "transport": "streamable-http",
                "endpoint": "/mcp",
                "methods_supported": ["POST"],
            }
        ),
        mimetype="application/json",
        headers={"X-MCP-Protocol-Version": MCP_PROTOCOL_VERSION, "Cache-Control": "no-cache"},
    )


@app.route(route="mcp", methods=["POST"])
async def mcp_message(req: func.HttpRequest) -> func.HttpResponse:
    """MCP Message endpoint — handles JSON-RPC messages via Streamable HTTP."""
    session_id = req.headers.get("Mcp-Session-Id", str(uuid.uuid4()))

    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}),
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
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                "capabilities": {"tools": {"listChanged": False}},
            }

        elif method == "tools/list":
            result = {"tools": ALL_TOOLS}

        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})

            handler = ALL_HANDLERS.get(tool_name)
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
            result = {"content": [{"type": "text", "text": json.dumps(tool_result)}]}

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
                {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32603, "message": f"Internal error: {e!s}"}}
            ),
            status_code=500,
            mimetype="application/json",
            headers={"Mcp-Session-Id": session_id},
        )


@app.route(route="health", methods=["GET"])
async def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """Health check endpoint."""
    return func.HttpResponse(
        json.dumps({
            "status": "healthy",
            "server": SERVER_NAME,
            "version": SERVER_VERSION,
            "domains": ["fhir", "pubmed", "clinical-trials"],
            "tool_count": len(ALL_TOOLS),
        }),
        mimetype="application/json",
    )
