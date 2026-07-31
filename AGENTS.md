# Agent.md - Healthcare Marketplace for Azure

## Purpose
Operational guide for coding agents working in this repository. Keep this file concise, action-oriented, and specific to this project.

## Scope
Build and maintain an Azure-native healthcare marketplace across:
- Skills (`.github/skills/`)
- MCP servers (`src/mcp-servers/`)
- Agent workflows (`src/agents/`)
- Infra and deployment assets (`deploy/`)

## Do
- Keep changes small and focused on the requested task.
- Follow existing patterns before introducing new abstractions.
- Validate locally first (single server/workflow), then expand scope.
- Use de-identified/sample data only; never commit PHI or secrets.
- Update docs when behavior or commands change.
- Prefer references to canonical docs instead of duplicating long explanations.

## Do Not
- Do not run cloud-destructive or expensive commands (`azd up`, resource deletes) without explicit user approval.
- Do not rewrite unrelated files during a targeted fix.
- Do not add new dependencies unless required for the task.
- Do not hardcode credentials, API keys, tenant IDs, or endpoint secrets.

## Project Map
- `.github/skills/`: domain guidance and templates for healthcare workflows.
- `src/mcp-servers/`: Python Azure Function MCP servers (consolidated):
  - `mcp-reference-data` (NPI + ICD-10 + CMS, 12 tools)
  - `mcp-clinical-research` (FHIR + PubMed + ClinicalTrials, 20 tools)
  - `cosmos-rag` (Cosmos DB RAG & Audit, 6 tools)
  - `document-reader`, `shared/`
- `src/agents/`: orchestration CLI and workflows (`prior-auth`, `clinical-trial`, `patient-data`, `literature-search`).
- `.runs/`: timestamped workflow run outputs (gitignored). Each run has `waypoints/`, `outputs/`, `eval/`.
- `data/`: case data, ground truth, sample outputs, and policy documents.
  - `data/cases/`: PA evaluation cases with ground truth.
  - `data/samples/`: committed reference output examples.
- `scripts/`: local launchers, APIM tests, post-deploy config scripts.
  - `scripts/setup-cli/`: interactive setup wizard (`make setup` / `make setup-guided`).
- `deploy/`: Azure Bicep infrastructure and deployment assets.
- `docs/`: operational, architecture, and testing guides.

## Default Workflow
1. Understand the target surface (skill, MCP server, workflow, infra, extension).
2. Edit only the relevant files.
3. Run the smallest useful validation loop.
4. Summarize what changed, why, and how it was validated.

## Commands
### Run MCP servers locally
```bash
make local-start
make local-logs
make local-stop
```

### Run one MCP server
```bash
./scripts/local-test.sh mcp-reference-data 7071
```

### MCP smoke test
```bash
curl http://localhost:7071/.well-known/mcp | jq
curl -X POST http://localhost:7071/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | jq
```

### Run agent workflows (local MCP mode)
```bash
cd src
source agents/.venv/bin/activate
python -m agents --workflow prior-auth --demo --local
python -m agents --workflow clinical-trial --demo --local
python -m agents --workflow literature-search --demo --local
```

### Run prior-auth sample input
```bash
cd src
source agents/.venv/bin/activate
python -m agents \
  --workflow prior-auth \
  --input ../data/sample_cases/prior_auth_baseline/pa_request.json \
  --local
```

## Safety and Approval Boundaries
Ask before running:
- `azd up`, `az deployment *`, or any command that creates/modifies cloud resources.
- Bulk dependency installs or upgrades across multiple subprojects.
- Potentially destructive operations (mass deletes, force resets, schema drops).

Safe by default:
- Local file edits in scope.
- Local MCP/workflow runs and targeted smoke tests.
- Read-only discovery commands (`rg`, `ls`, `cat`, `git status`, `git diff`).

## Patterns to Reuse
- MCP server shape: `src/mcp-servers/mcp-reference-data/function_app.py`
- MCP tool wiring: `src/agents/tools.py`
- Hybrid workflow orchestration: `src/agents/workflows/prior_auth.py`
- Sequential workflow orchestration: `src/agents/workflows/clinical_trials.py`
- Skill structure and assets: `.github/skills/prior-auth-azure/SKILL.md`

## Definition of Done
- Code changes are limited to task-relevant files.
- Related local checks/workflow runs complete successfully, or failures are explained.
- No secrets or PHI introduced.
- Documentation updated when commands/behavior changed.

## If Blocked
- State the blocker precisely (missing env var, unavailable service, auth issue, ambiguous requirement).
- Propose the minimum next step and continue once clarified.

## Canonical Docs
- `README.md`
- `docs/architecture/SYSTEM-OVERVIEW.md` (start here: how the layers fit together)
- `docs/GETTING-STARTED.md` (consolidated from DEVELOPER-GUIDE, LOCAL-TESTING, MCP-SERVERS-BEGINNER-GUIDE)
- `docs/MCP-OAUTH-PRM.md`
- `docs/SKILLS-FLOW-MAP.md`
- `docs/architecture/APIM-ARCHITECTURE.md`
- `docs/architecture/RETRIEVAL-ARCHITECTURE.md`

# Agent Instructions

This project uses **bd** (beads) for issue tracking. Run `bd onboard` to get started.

## Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --status in_progress  # Claim work
bd close <id>         # Complete work
bd sync               # Sync with git
```

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd sync
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:ca08a54f -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

## Session Completion

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd dolt push
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
<!-- END BEADS INTEGRATION -->
