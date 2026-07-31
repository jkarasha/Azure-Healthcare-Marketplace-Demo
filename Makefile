SHELL := /bin/bash

LOG_DIR := .local-logs

.PHONY: local-start local-stop local-logs local-start-reference-data local-start-clinical-research local-start-cosmos-rag local-start-document-reader setup-mcp-config eval-contracts eval-latency-local eval-native-local eval-all test-unit test-local eval-prior-auth run-prior-auth-local \
	docker-build docker-up docker-down docker-logs docker-ps docker-test \
	azure-deploy azure-deploy-single \
	devui devui-local devui-framework devui-framework-local \
	setup setup-check setup-doctor setup-guided setup-status setup-test setup-tips \
	seed-data seed-policies seed-policies-dry-run sync-local-env

define START_SERVER
	@bash -c 'mkdir -p "$(LOG_DIR)"; \
	  pids=$$(lsof -ti tcp:$(3) -sTCP:LISTEN 2>/dev/null || true); \
	  if [ -n "$$pids" ]; then \
	    echo "Port $(3) already has listener(s): $$pids. Restarting $(1)..."; \
	    kill $$pids 2>/dev/null || true; \
	    for _ in $$(seq 1 10); do \
	      if ! lsof -ti tcp:$(3) -sTCP:LISTEN >/dev/null 2>&1; then break; fi; \
	      sleep 0.1; \
	    done; \
	    pids=$$(lsof -ti tcp:$(3) -sTCP:LISTEN 2>/dev/null || true); \
	    if [ -n "$$pids" ]; then \
	      echo "Port $(3) still busy after SIGTERM. Force stopping: $$pids"; \
	      kill -9 $$pids 2>/dev/null || true; \
	    fi; \
	    for _ in $$(seq 1 10); do \
	      if ! lsof -ti tcp:$(3) -sTCP:LISTEN >/dev/null 2>&1; then break; fi; \
	      sleep 0.1; \
	    done; \
	  fi; \
	  if lsof -ti tcp:$(3) -sTCP:LISTEN >/dev/null 2>&1; then \
	    echo "ERROR: Port $(3) is still in use. Could not start $(1)."; \
	    exit 1; \
	  fi; \
	  echo "Starting $(1) on port $(3)..."; \
	  ./scripts/local-test.sh $(1) $(3) > "$(LOG_DIR)/$(2).log" 2>&1 & echo $$! > "$(LOG_DIR)/$(2).pid"; \
	  for i in $$(seq 1 30); do \
	    if lsof -ti tcp:$(3) -sTCP:LISTEN >/dev/null 2>&1; then \
	      echo "  ✓ $(1) ready on http://localhost:$(3) (pid $$(cat $(LOG_DIR)/$(2).pid))"; \
	      echo "    Logs: $(LOG_DIR)/$(2).log"; \
	      exit 0; \
	    fi; \
	    sleep 1; \
	  done; \
	  echo "  ⚠ $(1) launched but port $(3) not listening yet after 30s."; \
	  echo "    Check logs: $(LOG_DIR)/$(2).log"; \
	  tail -5 "$(LOG_DIR)/$(2).log" 2>/dev/null || true'
endef

local-start: local-stop local-start-reference-data local-start-clinical-research local-start-cosmos-rag local-start-document-reader
	@echo "All MCP servers started. Logs: $(LOG_DIR)/<server>.log"

local-start-reference-data:
	$(call START_SERVER,mcp-reference-data,mcp-reference-data,7071)

local-start-clinical-research:
	$(call START_SERVER,mcp-clinical-research,mcp-clinical-research,7072)

local-start-cosmos-rag: sync-local-env
	$(call START_SERVER,cosmos-rag,cosmos-rag,7073)

local-start-document-reader:
	$(call START_SERVER,document-reader,document-reader,7078)

# -- Seed Cosmos DB with policy PDFs -----------------------------------------
seed-data: seed-policies

seed-policies: local-start-cosmos-rag
	@echo "Seeding Cosmos DB via cosmos-rag MCP server (port 7073)..."
	python scripts/seed_cosmos_policies.py --mcp --port 7073

sync-local-env:
	@bash ./scripts/sync-local-env-from-azd.sh --quiet || true

seed-policies-direct: sync-local-env
	@echo "Seeding Cosmos DB directly via SDK..."
	python scripts/seed_cosmos_policies.py --direct

seed-policies-dry-run:
	@echo "Dry-run: extracting text from policy PDFs..."
	python scripts/seed_cosmos_policies.py --dry-run

local-stop:
	@bash -c 'if [ -d "$(LOG_DIR)" ]; then \
	  for pidfile in "$(LOG_DIR)"/*.pid; do \
	    if [ -f "$$pidfile" ]; then \
	      name=$$(basename "$$pidfile" .pid); \
	      pid=$$(cat "$$pidfile"); \
	      if kill -0 $$pid >/dev/null 2>&1; then \
	        echo "Stopping $$name (pid $$pid)"; \
	        kill $$pid; \
	        sleep 0.2; \
	        if kill -0 $$pid >/dev/null 2>&1; then \
	          echo "Force stopping $$name (pid $$pid)"; \
	          kill -9 $$pid 2>/dev/null || true; \
	        fi; \
	      else \
	        echo "Process not running for $$name (pid $$pid)"; \
	      fi; \
	      rm -f "$$pidfile"; \
	    fi; \
	  done; \
	else \
	  echo "No $(LOG_DIR) directory found. Nothing to stop."; \
	fi; \
	for port in 7071 7072 7073 7078; do \
	  pids=$$(lsof -ti tcp:$$port 2>/dev/null || true); \
	  if [ -n "$$pids" ]; then \
	    echo "Stopping listener(s) on port $$port: $$pids"; \
	    kill $$pids 2>/dev/null || true; \
	    sleep 0.2; \
	    pids=$$(lsof -ti tcp:$$port 2>/dev/null || true); \
	    if [ -n "$$pids" ]; then \
	      echo "Force stopping listener(s) on port $$port: $$pids"; \
	      kill -9 $$pids 2>/dev/null || true; \
	    fi; \
	  fi; \
	done'

local-logs:
	@bash -c 'ls -1 "$(LOG_DIR)"/*.log 2>/dev/null || echo "No logs found in $(LOG_DIR)"'

# Generate .vscode/mcp.json from template using azd environment values
setup-mcp-config:
	@bash ./scripts/postdeploy.sh

eval-contracts:
	@python3 ./scripts/eval_contracts.py

test-unit:
	@uv run pytest tests/unit tests/eval -q

test-local:
	@PYTHONPATH="src:$$(src/agents/.venv/bin/python -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')" \
		uv run pytest tests/local -q -p no:cacheprovider

run-prior-auth-local:
	@./scripts/run-prior-auth-local.sh $(INPUT)

eval-prior-auth:
	@uv run python scripts/eval_prior_auth.py

eval-latency-local:
	@python3 ./scripts/eval_latency.py --config ./scripts/evals/mcp-latency.local.json

eval-native-local:
	@src/agents/.venv/bin/python ./scripts/eval_native_agent_framework.py --config ./scripts/evals/native-agent-framework.local.json --wait-for-servers-seconds 30

eval-all: eval-contracts test-unit eval-prior-auth eval-latency-local eval-native-local

# ============================================================================
# DevUI targets
# ============================================================================

# Gradio DevUI (cloud endpoints)
devui:
	@cd src && source agents/.venv/bin/activate && python -m agents --devui

# Gradio DevUI (local MCP servers)
devui-local:
	@cd src && source agents/.venv/bin/activate && python -m agents --devui --local

# Framework DevUI (cloud endpoints)
devui-framework:
	@cd src && source agents/.venv/bin/activate && python -m agents --framework-devui

# Framework DevUI (local MCP servers)
devui-framework-local:
	@cd src && source agents/.venv/bin/activate && python -m agents --framework-devui --local

# ============================================================================
# Docker targets
# ============================================================================

docker-build:
	@echo "Building all MCP server containers..."
	docker compose build

docker-up:
	@echo "Starting all MCP servers in Docker..."
	docker compose up --build -d
	@echo "MCP servers running. Use 'make docker-logs' to follow output."

docker-down:
	@echo "Stopping all MCP server containers..."
	docker compose down

docker-logs:
	docker compose logs -f

docker-ps:
	docker compose ps

docker-test:
	@echo "Running health checks on all Docker MCP servers..."
	@failed=0; \
	for pair in "mcp-reference-data:7071" "mcp-clinical-research:7072" "cosmos-rag:7073"; do \
	  name=$${pair%%:*}; port=$${pair##*:}; \
	  printf "  %-26s " "$$name"; \
	  if curl -sf "http://localhost:$$port/health?code=docker-default-key" > /dev/null 2>&1; then \
	    echo "✓ healthy"; \
	  else \
	    echo "✗ unreachable"; failed=1; \
	  fi; \
	done; \
	if [ $$failed -eq 1 ]; then echo "Some servers are not healthy."; exit 1; fi; \
	echo "All MCP servers healthy."

# ============================================================================
# Azure deployment targets (container-based Function Apps)
# ============================================================================

# Deploy all MCP server containers to Azure (requires azd env + az login)
azure-deploy:
	@echo "Deploying all MCP server containers to Azure..."
	./scripts/deploy-mcp-containers.sh

# Deploy a single MCP server container: make azure-deploy-single SERVER=npi-lookup
azure-deploy-single:
	@if [ -z "$(SERVER)" ]; then \
	  echo "Usage: make azure-deploy-single SERVER=<server-name>"; \
	  echo "Valid servers: mcp-reference-data mcp-clinical-research cosmos-rag"; \
	  exit 1; \
	fi
	./scripts/deploy-mcp-containers.sh $(SERVER)

# ============================================================================
# Interactive Setup CLI
# ============================================================================

# Install setup CLI deps if needed, then run
define SETUP_CLI
	@pip install -q rich 2>/dev/null || pip3 install -q rich 2>/dev/null || true
	@python3 -m scripts.setup-cli $(1)
endef

# Interactive menu
setup:
	$(call SETUP_CLI,)

# Sub-commands
setup-check:
	$(call SETUP_CLI,check)

setup-guided:
	$(call SETUP_CLI,guided)

setup-doctor:
	$(call SETUP_CLI,doctor)

setup-status:
	$(call SETUP_CLI,status)

setup-test:
	$(call SETUP_CLI,test)

setup-tips:
	$(call SETUP_CLI,tips)
