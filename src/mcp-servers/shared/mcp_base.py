"""
Base MCP Server implementation for Azure Functions.
Provides common functionality for all Healthcare MCP servers.

Supports MCP Protocol 2025-06-18 with Streamable HTTP transport
for Azure API Management integration.
"""

import json
import logging
import uuid
from abc import ABC
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)

# MCP Protocol version - 2025-06-18 required for APIM MCP Server feature
MCP_PROTOCOL_VERSION = "2025-06-18"


@dataclass
class Tool:
    """MCP Tool definition."""

    name: str
    description: str
    input_schema: dict
    handler: Callable = None


@dataclass
class MCPServer(ABC):
    """Base class for MCP servers."""

    name: str
    version: str
    description: str
    tools: list[Tool] = field(default_factory=list)

    def register_tool(self, name: str, description: str, input_schema: dict):
        """Decorator to register a tool handler."""

        def decorator(func: Callable):
            self.tools.append(Tool(name=name, description=description, input_schema=input_schema, handler=func))
            return func

        return decorator

    def get_discovery_response(self) -> dict:
        """Generate the /.well-known/mcp discovery response."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "protocol_version": MCP_PROTOCOL_VERSION,
            "capabilities": {"tools": True, "resources": False, "prompts": False},
            "tools": [
                {"name": tool.name, "description": tool.description, "inputSchema": tool.input_schema}
                for tool in self.tools
            ],
        }

    def _find_tool(self, name: str) -> Tool | None:
        """Find a tool by name."""
        for tool in self.tools:
            if tool.name == name:
                return tool
        return None

    async def handle_message(self, message: dict) -> dict:
        """Handle incoming MCP JSON-RPC message."""
        method = message.get("method")
        params = message.get("params", {})
        msg_id = message.get("id")

        try:
            if method == "initialize":
                return self._response(
                    msg_id,
                    {
                        "protocolVersion": MCP_PROTOCOL_VERSION,
                        "serverInfo": {"name": self.name, "version": self.version},
                        "capabilities": {"tools": {"listChanged": False}},
                    },
                )

            elif method == "tools/list":
                return self._response(
                    msg_id,
                    {
                        "tools": [
                            {"name": tool.name, "description": tool.description, "inputSchema": tool.input_schema}
                            for tool in self.tools
                        ]
                    },
                )

            elif method == "tools/call":
                tool_name = params.get("name")
                tool_args = params.get("arguments", {})

                tool = self._find_tool(tool_name)
                if not tool:
                    return self._error(msg_id, -32602, f"Unknown tool: {tool_name}")

                try:
                    result = await tool.handler(tool_args)
                    return self._response(
                        msg_id,
                        {
                            "content": [
                                {
                                    "type": "text",
                                    "text": json.dumps(result) if isinstance(result, (dict, list)) else str(result),
                                }
                            ]
                        },
                    )
                except Exception as e:
                    logger.exception(f"Tool execution error: {tool_name}")
                    return self._error(msg_id, -32603, f"Tool execution failed: {e!s}")

            elif method == "ping":
                return self._response(msg_id, {})

            else:
                return self._error(msg_id, -32601, f"Method not found: {method}")

        except Exception as e:
            logger.exception("Error handling MCP message")
            return self._error(msg_id, -32603, f"Internal error: {e!s}")

    def _response(self, msg_id: Any, result: dict) -> dict:
        """Create a JSON-RPC success response."""
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    def _error(self, msg_id: Any, code: int, message: str) -> dict:
        """Create a JSON-RPC error response."""
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}


def create_function_app_handlers(server: MCPServer):
    """Create Azure Function handlers for an MCP server.

    Supports both:
    - Legacy discovery endpoint: GET /.well-known/mcp
    - Streamable HTTP transport: POST /mcp (MCP 2025-06-18)
    """
    import azure.functions as func

    async def discovery_handler(req: func.HttpRequest) -> func.HttpResponse:
        """Handle /.well-known/mcp discovery requests (legacy compatibility)."""
        return func.HttpResponse(
            json.dumps(server.get_discovery_response()),
            mimetype="application/json",
            headers={"X-MCP-Protocol-Version": MCP_PROTOCOL_VERSION, "Cache-Control": "no-cache"},
        )

    async def message_handler(req: func.HttpRequest) -> func.HttpResponse:
        """Handle MCP JSON-RPC messages via Streamable HTTP transport.

        Supports MCP 2025-06-18 Streamable HTTP transport:
        - POST /mcp with JSON-RPC body
        - Mcp-Session-Id header for session tracking
        - Returns JSON-RPC response
        """
        try:
            # Get or generate session ID for APIM MCP tracking
            session_id = req.headers.get("Mcp-Session-Id", str(uuid.uuid4()))

            body = req.get_json()
            response = await server.handle_message(body)

            return func.HttpResponse(
                json.dumps(response),
                mimetype="application/json",
                headers={
                    "X-MCP-Protocol-Version": MCP_PROTOCOL_VERSION,
                    "Mcp-Session-Id": session_id,
                    "Cache-Control": "no-cache",
                },
            )
        except ValueError:
            return func.HttpResponse(
                json.dumps({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}),
                status_code=400,
                mimetype="application/json",
            )

    return discovery_handler, message_handler
