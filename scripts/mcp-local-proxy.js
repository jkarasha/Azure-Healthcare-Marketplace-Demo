#!/usr/bin/env node
/**
 * MCP Local Proxy — Bridges stdio MCP ↔ local HTTP MCP server
 *
 * Usage:
 *   node mcp-local-proxy.js <server-url>
 *   node mcp-local-proxy.js http://localhost:7071/mcp
 *
 * Reads JSON-RPC messages from stdin (one per line), POSTs them to the
 * HTTP MCP endpoint, and writes the response to stdout.
 */

const readline = require('readline');

const url = process.argv[2] || process.env.MCP_SERVER_URL;

if (!url) {
  process.stderr.write('Usage: node mcp-local-proxy.js <server-url>\n');
  process.exit(1);
}

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout,
  terminal: false,
});

async function forward(message) {
  try {
    const response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(message),
    });

    if (!response.ok) {
      const text = await response.text();
      return {
        jsonrpc: '2.0',
        id: message.id,
        error: { code: -32603, message: `HTTP ${response.status}: ${text}` },
      };
    }

    return await response.json();
  } catch (error) {
    return {
      jsonrpc: '2.0',
      id: message.id,
      error: { code: -32603, message: `Proxy error: ${error.message}` },
    };
  }
}

rl.on('line', async (line) => {
  try {
    const message = JSON.parse(line);

    // Notifications (no id) — fire-and-forget
    if (message.id === undefined) {
      forward(message).catch(() => {});
      return;
    }

    const result = await forward(message);
    console.log(JSON.stringify(result));
  } catch (error) {
    console.log(
      JSON.stringify({
        jsonrpc: '2.0',
        id: null,
        error: { code: -32700, message: `Parse error: ${error.message}` },
      })
    );
  }
});

rl.on('close', () => process.exit(0));
