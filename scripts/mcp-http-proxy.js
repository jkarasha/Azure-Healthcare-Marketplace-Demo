#!/usr/bin/env node
/**
 * MCP HTTP Proxy - Bridges stdio MCP to HTTP MCP servers
 * Workaround for VS Code MCP "dynamic discovery not supported" issue
 */

const readline = require('readline');

const BASE_URL = process.env.MCP_SERVER_URL;
const APIM_KEY = process.env.APIM_SUBSCRIPTION_KEY;

if (!BASE_URL || !APIM_KEY) {
  console.error(JSON.stringify({
    jsonrpc: '2.0',
    id: null,
    error: {
      code: -32603,
      message: 'Missing MCP_SERVER_URL or APIM_SUBSCRIPTION_KEY environment variable'
    }
  }));
  process.exit(1);
}

const rl = readline.createInterface({
  input: process.stdin,
  output: process.stdout,
  terminal: false
});

async function sendToServer(message) {
  try {
    const response = await fetch(BASE_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Ocp-Apim-Subscription-Key': APIM_KEY
      },
      body: JSON.stringify(message)
    });

    if (!response.ok) {
      const errorText = await response.text();
      return {
        jsonrpc: '2.0',
        id: message.id,
        error: {
          code: -32603,
          message: `HTTP ${response.status}: ${errorText}`
        }
      };
    }

    return await response.json();
  } catch (error) {
    return {
      jsonrpc: '2.0',
      id: message.id,
      error: {
        code: -32603,
        message: `Proxy error: ${error.message}`
      }
    };
  }
}

rl.on('line', async (line) => {
  try {
    const message = JSON.parse(line);
    const response = await sendToServer(message);
    console.log(JSON.stringify(response));
  } catch (error) {
    console.log(JSON.stringify({
      jsonrpc: '2.0',
      id: null,
      error: {
        code: -32700,
        message: `Parse error: ${error.message}`
      }
    }));
  }
});

rl.on('close', () => {
  process.exit(0);
});
