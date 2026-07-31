#!/bin/bash
# ============================================================================
# One-command local prior-auth run.
#
# Starts the three MCP servers the prior-auth workflow needs, waits for them to
# answer, runs the workflow, then shuts the servers down again.
#
# Usage:
#   ./scripts/run-prior-auth-local.sh                  # --demo
#   ./scripts/run-prior-auth-local.sh path/to/pa.json  # a specific request
#
# Ports default to 7081-7083 rather than the usual 7071-7073, because those are
# frequently held by an unrelated Windows-side Functions host that answers 401.
# Override with REFERENCE_DATA_PORT / CLINICAL_RESEARCH_PORT / COSMOS_RAG_PORT.
#
# All three servers are required. MCPToolKit connects every endpoint up front,
# so a missing cosmos-rag aborts the run instead of degrading it.
# ============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

REFERENCE_DATA_PORT=${REFERENCE_DATA_PORT:-7081}
CLINICAL_RESEARCH_PORT=${CLINICAL_RESEARCH_PORT:-7082}
COSMOS_RAG_PORT=${COSMOS_RAG_PORT:-7083}

# Bead 002 has been observed hanging (issue h1g), so never run unbounded.
RUN_TIMEOUT=${RUN_TIMEOUT:-900}
STARTUP_TIMEOUT=${STARTUP_TIMEOUT:-120}

PYTHON="$PROJECT_ROOT/src/agents/.venv/bin/python"
LOG_DIR="$PROJECT_ROOT/.local-logs"
PIDS=()

cleanup() {
    if [ ${#PIDS[@]} -gt 0 ]; then
        echo ""
        echo "Stopping MCP servers..."
        for pid in "${PIDS[@]}"; do
            # Negative PID targets the whole process group, so the func host and
            # its Python workers go too. Orphaned workers otherwise keep the
            # port bound and break the next run.
            kill -TERM -- "-$pid" 2>/dev/null || true
        done
        sleep 3
        for pid in "${PIDS[@]}"; do
            kill -KILL -- "-$pid" 2>/dev/null || true
        done
    fi
}
trap cleanup EXIT INT TERM

# -- Preflight ---------------------------------------------------------------
if [ ! -x "$PYTHON" ]; then
    echo "ERROR: agents venv not found at $PYTHON" >&2
    echo "The offline 'uv' venv will not work: it has no agent_framework." >&2
    exit 1
fi

if ! "$PYTHON" -c "import agent_framework" >/dev/null 2>&1; then
    echo "ERROR: agent_framework is not importable from the agents venv." >&2
    exit 1
fi

if ! az account get-access-token \
        --resource https://cognitiveservices.azure.com \
        --query expiresOn -o tsv >/dev/null 2>&1; then
    echo "ERROR: no valid Azure token. Run 'az login' first." >&2
    exit 1
fi

mkdir -p "$LOG_DIR"

start_server() {
    local name=$1 port=$2
    echo "Starting $name on $port..."
    # setsid gives each server its own process group so cleanup can take down
    # the func host and its workers together.
    setsid bash -c "cd '$PROJECT_ROOT' && ./scripts/local-test.sh '$name' '$port'" \
        > "$LOG_DIR/run-pa-$name.log" 2>&1 &
    PIDS+=($!)
}

wait_for_server() {
    local name=$1 port=$2 waited=0
    while [ "$waited" -lt "$STARTUP_TIMEOUT" ]; do
        if curl -s -m 3 -X POST "http://localhost:$port/mcp" \
                -H "Content-Type: application/json" \
                -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' \
                2>/dev/null | grep -q '"result"'; then
            echo "  $name ready on $port"
            return 0
        fi
        sleep 3
        waited=$((waited + 3))
    done
    echo "ERROR: $name did not become ready on $port within ${STARTUP_TIMEOUT}s." >&2
    echo "       See $LOG_DIR/run-pa-$name.log" >&2
    echo "       If the port answers 401, another Functions host owns it." >&2
    return 1
}

start_server mcp-reference-data   "$REFERENCE_DATA_PORT"
start_server mcp-clinical-research "$CLINICAL_RESEARCH_PORT"
start_server cosmos-rag            "$COSMOS_RAG_PORT"

echo "Waiting for servers (up to ${STARTUP_TIMEOUT}s each)..."
wait_for_server mcp-reference-data    "$REFERENCE_DATA_PORT"
wait_for_server mcp-clinical-research "$CLINICAL_RESEARCH_PORT"
wait_for_server cosmos-rag            "$COSMOS_RAG_PORT"

# -- Run ---------------------------------------------------------------------
if [ $# -gt 0 ]; then
    INPUT_ARGS=(--input "$1")
    echo ""
    echo "Running prior-auth on $1 (timeout ${RUN_TIMEOUT}s)..."
else
    INPUT_ARGS=(--demo)
    echo ""
    echo "Running prior-auth --demo (timeout ${RUN_TIMEOUT}s)..."
fi

set +e
( cd "$PROJECT_ROOT/src" && \
  MCP_REFERENCE_DATA_URL="http://localhost:$REFERENCE_DATA_PORT/mcp" \
  MCP_CLINICAL_RESEARCH_URL="http://localhost:$CLINICAL_RESEARCH_PORT/mcp" \
  MCP_COSMOS_RAG_URL="http://localhost:$COSMOS_RAG_PORT/mcp" \
  timeout "$RUN_TIMEOUT" "$PYTHON" -m agents \
      --workflow prior-auth "${INPUT_ARGS[@]}" --local )
STATUS=$?
set -e

if [ "$STATUS" -eq 124 ]; then
    echo "" >&2
    echo "TIMED OUT after ${RUN_TIMEOUT}s. If it stalled in bead 002 with no log" >&2
    echo "output, that is the known concurrent-stage hang (issue h1g)." >&2
fi

LATEST=$(ls -td "$PROJECT_ROOT"/.runs/*/ 2>/dev/null | head -1 || true)
[ -n "$LATEST" ] && echo "" && echo "Run output: $LATEST"

exit "$STATUS"
