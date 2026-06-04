#!/bin/bash
# ============================================================================
# Quick start script for local MCP server testing
#
# Uses `uv` for fast venv creation and dependency installation when available,
# falls back to standard `python -m venv` + `pip` otherwise.
#
# Usage:
#   ./scripts/local-test.sh <server-name> [port]
#   ./scripts/local-test.sh cosmos-rag 7077
# ============================================================================
set -e

SERVER=${1:-mcp-reference-data}
PORT=${2:-}

# -- Port mapping (auto-detect if not provided) ------------------------------
if [ -z "$PORT" ]; then
    case "$SERVER" in
        mcp-reference-data)    PORT=7071 ;;
        mcp-clinical-research) PORT=7072 ;;
        cosmos-rag)            PORT=7073 ;;
        document-reader)       PORT=7078 ;;
        *)                     PORT=7071 ;;
    esac
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SERVER_DIR="$PROJECT_ROOT/src/mcp-servers/$SERVER"
SHARED_DIR="$PROJECT_ROOT/src/mcp-servers/shared"

load_env_file() {
    local env_file="$1"
    if [ -f "$env_file" ]; then
        echo "Loading env: $(basename "$env_file")"
        # Filter out non-assignment lines (e.g. ERROR: messages) before sourcing
        local tmp_env
        tmp_env=$(mktemp)
        grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$env_file" 2>/dev/null > "$tmp_env" || true
        set -a
        # shellcheck disable=SC1090
        source "$tmp_env" || true
        set +a
        rm -f "$tmp_env"
    fi
}

if [ "$SERVER" = "cosmos-rag" ] && [ -x "$PROJECT_ROOT/scripts/sync-local-env-from-azd.sh" ]; then
    "$PROJECT_ROOT/scripts/sync-local-env-from-azd.sh" --quiet || true
fi

load_env_file "$PROJECT_ROOT/.env"
load_env_file "$PROJECT_ROOT/.env.local"

if [ ! -d "$SERVER_DIR" ]; then
    echo "Error: Server '$SERVER' not found at $SERVER_DIR"
    echo ""
    echo "Available servers:"
    ls -1 "$PROJECT_ROOT/src/mcp-servers" | grep -v '^shared$' | grep -v '^Dockerfile$' | grep -v '^\.'
    exit 1
fi

echo "============================================"
echo "Healthcare MCP Server - Local Testing"
echo "============================================"
echo ""
echo "Server:     $SERVER"
echo "Port:       $PORT"
echo "Directory:  $SERVER_DIR"
echo ""

cd "$SERVER_DIR"

# -- Detect Azure Functions max Python version --------------------------------
detect_func_max_python_minor() {
    local default_max=12
    local func_path func_real worker_root dir base minor max_minor

    max_minor=$default_max
    func_path=$(command -v func 2>/dev/null || true)
    if [ -z "$func_path" ]; then
        echo "$max_minor"
        return 0
    fi

    func_real=$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$func_path" 2>/dev/null || echo "$func_path")
    worker_root="$(cd "$(dirname "$func_real")/.." && pwd)/workers/python"

    if [ -d "$worker_root" ]; then
        for dir in "$worker_root"/3.*; do
            [ -d "$dir" ] || continue
            base=$(basename "$dir")
            minor=${base#3.}
            if [[ "$minor" =~ ^[0-9]+$ ]] && [ "$minor" -gt "$max_minor" ]; then
                max_minor=$minor
            fi
        done
    fi

    echo "$max_minor"
    return 0
}

FUNC_MAX_MINOR=$(detect_func_max_python_minor)
USE_UV=false

# -- Check for uv ------------------------------------------------------------
if command -v uv >/dev/null 2>&1; then
    USE_UV=true
    echo "Package manager: uv ($(uv --version 2>/dev/null))"
else
    echo "Package manager: pip (install uv for 10-50x faster setup: curl -LsSf https://astral.sh/uv/install.sh | sh)"
fi

# -- Compute requirements hash for cache invalidation ------------------------
# Include both server-specific and shared base requirements
REQ_HASH_INPUT=""
if [ -f requirements.txt ]; then
    REQ_HASH_INPUT+=$(cat requirements.txt)
fi
if [ -f "$SHARED_DIR/requirements-base.txt" ]; then
    REQ_HASH_INPUT+=$(cat "$SHARED_DIR/requirements-base.txt")
fi
REQ_HASH=$(echo "$REQ_HASH_INPUT" | shasum | awk '{print $1}')
REQ_HASH_FILE=".venv/.requirements.sha"

# -- Resolve Python interpreter (pip fallback only) ---------------------------
pick_python() {
    local candidates=("python3.12" "python3.11" "python3.10" "python3.9" "/usr/bin/python3")
    for py in "${candidates[@]}"; do
        if ! command -v "$py" >/dev/null 2>&1; then continue; fi
        local minor
        minor=$("$py" -c 'import sys; print(sys.version_info.minor)' 2>/dev/null || echo "")
        if [ -n "$minor" ] && [ "$minor" -ge 9 ] && [ "$minor" -le "$FUNC_MAX_MINOR" ]; then
            echo "$py"
            return 0
        fi
    done
    echo ""
    return 1
}

if ! $USE_UV; then
    PYTHON_CMD=$(pick_python || true)
    if [ -z "$PYTHON_CMD" ]; then
        echo "Error: No supported Python 3.9-3.$FUNC_MAX_MINOR found and uv not available."
        echo "Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    fi
fi

# -- Install dependencies -----------------------------------------------------
install_deps() {
    local req_files=()

    # Collect all requirement files (shared base first, then server-specific)
    if [ -f "$SHARED_DIR/requirements-base.txt" ]; then
        req_files+=("$SHARED_DIR/requirements-base.txt")
    fi
    if [ -f requirements.txt ]; then
        req_files+=("requirements.txt")
    fi

    if [ ${#req_files[@]} -eq 0 ]; then
        echo "  No requirements.txt found. Skipping."
        return 0
    fi

    local req_args=()
    for f in "${req_files[@]}"; do
        req_args+=("-r" "$f")
    done

    if $USE_UV; then
        # uv pip: ~10-50x faster than pip
        uv pip install "${req_args[@]}" --quiet --python .venv/bin/python

        # Also install to .python_packages for Azure Functions worker
        echo "  Syncing .python_packages for Azure Functions worker..."
        uv pip install "${req_args[@]}" \
            --target ".python_packages/lib/site-packages" \
            --quiet --python .venv/bin/python
    else
        source .venv/bin/activate
        pip install --upgrade pip -q
        pip install "${req_args[@]}" -q

        echo "  Syncing .python_packages for Azure Functions worker..."
        pip install "${req_args[@]}" \
            --target=".python_packages/lib/site-packages" --upgrade -q
    fi
}

# -- Create / validate venv ---------------------------------------------------
setup_venv() {
    local needs_create=false
    local needs_install=false

    # Check if venv exists and is valid
    if [ ! -d ".venv" ]; then
        needs_create=true
    elif [ ! -x ".venv/bin/python" ] || [ ! -f ".venv/bin/activate" ]; then
        echo "  Corrupted venv detected, recreating..."
        rm -rf .venv
        needs_create=true
    else
        # Check Python version compatibility
        local venv_minor
        venv_minor=$(.venv/bin/python -c 'import sys; print(sys.version_info.minor)' 2>/dev/null || echo "")
        if [ -n "$venv_minor" ] && { [ "$venv_minor" -lt 9 ] || [ "$venv_minor" -gt "$FUNC_MAX_MINOR" ]; }; then
            echo "  venv Python 3.$venv_minor outside range 3.9-3.$FUNC_MAX_MINOR, recreating..."
            rm -rf .venv
            needs_create=true
        fi
    fi

    # Check if deps need updating
    if [ ! -f "$REQ_HASH_FILE" ] || [ "$(cat "$REQ_HASH_FILE" 2>/dev/null)" != "$REQ_HASH" ]; then
        needs_install=true
    fi

    if $needs_create; then
        echo "  Creating venv..."
        if $USE_UV; then
            uv venv .venv --python ">=3.9,<=3.$FUNC_MAX_MINOR" --quiet 2>/dev/null || \
                uv venv .venv --quiet
        else
            "$PYTHON_CMD" -m venv .venv
        fi

        if [ ! -x ".venv/bin/python" ]; then
            echo "Error: venv creation failed at $SERVER_DIR/.venv"
            exit 1
        fi
        needs_install=true  # fresh venv always needs deps
    fi

    if $needs_install; then
        echo "  Installing dependencies..."
        install_deps
        echo "$REQ_HASH" > "$REQ_HASH_FILE"
    else
        echo "  Dependencies up to date (hash match)."
    fi
}

# -- Main setup flow ----------------------------------------------------------
echo "Setting up environment..."
setup_venv

# Activate venv
source .venv/bin/activate
echo ""
echo "Python:     $(python --version) ($(which python))"

# Configure Azure Functions to use this venv's Python
export languageWorkers__python__defaultExecutablePath="$SERVER_DIR/.venv/bin/python"

# Ensure the worker can import deps from both locations
VENV_SITE_PACKAGES=$(python -c 'import site; print(next(p for p in site.getsitepackages() if p.endswith("site-packages")))')
export PYTHONPATH="$VENV_SITE_PACKAGES:$SERVER_DIR/.python_packages/lib/site-packages:${PYTHONPATH:-}"

# Quick sanity check — verify key imports work
echo ""
echo "Dependency check:"
python -c "import azure.functions; print(f'  azure-functions {azure.functions.__version__} ✓')" 2>/dev/null || echo "  ⚠ azure-functions not importable"
python -c "import httpx; print(f'  httpx {httpx.__version__} ✓')" 2>/dev/null || echo "  ⚠ httpx not importable"

# Server-specific checks
case "$SERVER" in
    cosmos-rag)
        python -c "import azure.cosmos; print(f'  azure-cosmos ✓')" 2>/dev/null || echo "  ⚠ azure-cosmos not importable"
        python -c "import openai; print(f'  openai {openai.__version__} ✓')" 2>/dev/null || echo "  ⚠ openai not importable"
        AI_EP=$(python - <<'PY'
import json
import os
from pathlib import Path

ep = os.environ.get("AZURE_AI_SERVICES_ENDPOINT", "").strip() or os.environ.get("AZURE_OPENAI_ENDPOINT", "").strip()
if not ep:
    settings = Path("local.settings.json")
    if settings.exists():
        try:
            data = json.loads(settings.read_text())
            values = data.get("Values", {})
            ep = (values.get("AZURE_AI_SERVICES_ENDPOINT", "") or values.get("AZURE_OPENAI_ENDPOINT", "")).strip()
        except Exception:
            pass
print(ep)
PY
)
        if [ -z "$AI_EP" ]; then
            echo "  ⚠ Missing AZURE_AI_SERVICES_ENDPOINT (or AZURE_OPENAI_ENDPOINT)."
            echo "    Cosmos RAG indexing/seed will fail without an embeddings endpoint."
        elif [[ "$AI_EP" != http://* && "$AI_EP" != https://* ]]; then
            echo "  ⚠ Embeddings endpoint missing scheme: '$AI_EP'"
            echo "    Use a full URL, e.g. https://<resource>.services.ai.azure.com"
        fi
        ;;
    mcp-clinical-research)
        python -c "import azure.identity; print(f'  azure-identity ✓')" 2>/dev/null || echo "  ⚠ azure-identity not importable"
        ;;
esac

# Verify .python_packages
if [ -d ".python_packages/lib/site-packages/httpx" ]; then
    echo "  .python_packages ✓"
else
    echo "  ⚠ .python_packages/httpx missing"
fi

echo ""
echo "============================================"
echo "Endpoints:"
echo "============================================"
echo "Discovery:  http://localhost:$PORT/.well-known/mcp"
echo "Messages:   http://localhost:$PORT/mcp"
echo "Health:     http://localhost:$PORT/health"
echo ""
echo "Test commands:"
echo "  curl http://localhost:$PORT/.well-known/mcp | jq"
echo "  curl http://localhost:$PORT/health | jq"
echo ""
echo "Starting Azure Functions host..."
echo "============================================"
echo ""

# Ensure a local.settings.json exists so `func start` can detect the worker
# runtime (Python). The repo .gitignores this file, so generate a minimal
# stub on first run. Existing user-authored files are left untouched.
if [ ! -f local.settings.json ]; then
    echo "  Creating minimal local.settings.json (Python worker runtime)..."
    cat > local.settings.json <<'JSON'
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "",
    "FUNCTIONS_WORKER_RUNTIME": "python"
  }
}
JSON
fi

# Belt-and-braces: also export the env var so func start always sees it.
export FUNCTIONS_WORKER_RUNTIME=python

func start -p $PORT --python
