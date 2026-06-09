"""
Document Reader MCP Server - Azure Function App

Provides a lightweight tool to load local documents for agent consumption:
- Text/structured docs: returns decoded text and optional JSON/CSV parsing
- PDFs/images/other binaries: returns base64 + mime (optionally data_url)

Supports MCP Protocol 2025-06-18 with Streamable HTTP transport for APIM integration.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from pathlib import Path

import azure.functions as func

# Ensure sibling "shared" can be imported (../shared).
MCP_SERVERS_ROOT = Path(__file__).resolve().parents[1]
if str(MCP_SERVERS_ROOT) not in sys.path:
    sys.path.insert(0, str(MCP_SERVERS_ROOT))

try:
    # Local dev: ../shared is on sys.path
    from shared.mcp_base import MCPServer, create_function_app_handlers  # noqa: E402
except ImportError:
    # Container: Dockerfile copies shared/mcp_base.py to function app root
    from mcp_base import MCPServer, create_function_app_handlers  # type: ignore[no-redef]  # noqa: E402

from document_reader import ReadOptions, read_document  # noqa: E402

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)
logger = logging.getLogger(__name__)

MCP_PROTOCOL_VERSION = os.environ.get("MCP_PROTOCOL_VERSION", "2025-06-18")

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]

server = MCPServer(
    name="document-reader",
    version="0.1.0",
    description="Load local documents (PDF/images/handwritten scans via base64; structured docs via text/parse) for agent consumption.",
)


@server.register_tool(
    name="read_document",
    description=(
        "Read a local file and return text/structured content or base64 for binary files (PDF/images). "
        "Defaults to workspace-only reads for safety."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Path to a local file (absolute or workspace-relative)."},
            "mode": {
                "type": "string",
                "description": "auto|text|binary. auto returns text for text-like files and base64 for binaries.",
                "default": "auto",
                "enum": ["auto", "text", "binary"],
            },
            "allow_outside_workspace": {
                "type": "boolean",
                "description": "Allow reading files outside the repo root. Defaults to false for safety.",
                "default": False,
            },
            "max_bytes": {
                "type": "integer",
                "description": "Max bytes to read/return (binary hard limit; text may truncate bytes).",
                "default": 4000000,
                "minimum": 1,
            },
            "max_chars": {
                "type": "integer",
                "description": "Max decoded characters to return for text modes.",
                "default": 200000,
                "minimum": 1,
            },
            "max_rows": {
                "type": "integer",
                "description": "Max CSV/TSV rows to parse/return when parse_structured=true.",
                "default": 500,
                "minimum": 1,
            },
            "parse_structured": {
                "type": "boolean",
                "description": "If true, attempt JSON/NDJSON/CSV/TSV parsing when applicable.",
                "default": True,
            },
            "csv_delimiter": {
                "type": "string",
                "description": "Delimiter for .csv parsing (ignored for .tsv).",
                "default": ",",
            },
            "include_data_url": {
                "type": "boolean",
                "description": "If true, include a data: URL for binary results (useful for image_url).",
                "default": False,
            },
        },
        "required": ["path"],
    },
)
async def read_document_tool(args: dict) -> dict:
    opts = ReadOptions(
        mode=str(args.get("mode", "auto")),
        allow_outside_workspace=bool(args.get("allow_outside_workspace", False)),
        max_bytes=int(args.get("max_bytes", 4_000_000)),
        max_chars=int(args.get("max_chars", 200_000)),
        max_rows=int(args.get("max_rows", 500)),
        parse_structured=bool(args.get("parse_structured", True)),
        csv_delimiter=str(args.get("csv_delimiter", ",")),
        include_data_url=bool(args.get("include_data_url", False)),
    )

    return read_document(str(args.get("path", "")), workspace_root=WORKSPACE_ROOT, options=opts)


discovery_handler, message_handler = create_function_app_handlers(server)


@app.route(route=".well-known/mcp", methods=["GET"])
async def mcp_discovery(req: func.HttpRequest) -> func.HttpResponse:
    return await discovery_handler(req)


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
            headers={"Allow": "POST", "X-MCP-Protocol-Version": MCP_PROTOCOL_VERSION, "Mcp-Session-Id": session_id},
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
        headers={"X-MCP-Protocol-Version": MCP_PROTOCOL_VERSION, "Cache-Control": "no-cache"},
    )


@app.route(route="mcp", methods=["POST"])
async def mcp_message(req: func.HttpRequest) -> func.HttpResponse:
    return await message_handler(req)


@app.route(route="health", methods=["GET"])
async def health_check(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse(
        json.dumps({"status": "healthy", "server": server.name, "version": server.version}), mimetype="application/json"
    )

