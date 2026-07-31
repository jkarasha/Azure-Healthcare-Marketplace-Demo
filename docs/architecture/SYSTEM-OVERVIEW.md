# System Overview

How the pieces of this repository fit together, and what state they are in. Start here before
drilling into `APIM-ARCHITECTURE.md` or `RETRIEVAL-ARCHITECTURE.md`.

## The one-sentence version

Azure Functions expose healthcare data as MCP tools, LLM agents receive deliberately scoped
subsets of those tools, and workflows sequence the agents into a business process with
checkpoints and gates.

## Three layers

```
+---------------------------------------------------------+
|  LAYER 3  WORKFLOWS          src/agents/workflows/       |
|  prior_auth (1326 loc) - clinical_trials - patient_data  |
|  - literature_search                                     |
|  Sequences agents into "beads", writes waypoints, gates  |
+---------------------------------------------------------+
|  LAYER 2  AGENTS + WIRING    src/agents/                 |
|  agents.py (882)  = prompts and roles                    |
|  tools.py  (393)  = which tools each role may call       |
|  llm_client.py    = Azure OpenAI + AAD auth              |
|  config.py        = endpoints, env                       |
+---------------------------------------------------------+
|  LAYER 1  MCP SERVERS        src/mcp-servers/            |
|  mcp-reference-data (12 tools)  NPI - ICD-10 - CMS       |
|  mcp-clinical-research (20)     FHIR - PubMed - Trials   |
|  cosmos-rag (6)                 RAG search - audit       |
|  Python Azure Functions, JSON-RPC over HTTP POST /mcp    |
+---------------------------------------------------------+
```

Alongside these sits `.github/skills/` (six skills, including `prior-auth-azure` and
`pa-report-formatter`). These are not runtime code. They are the marketplace deliverable:
instructions that teach a coding agent how to drive the system.

## Layer 1 - MCP servers

Each server is a Python Azure Function exposing four routes (see
`src/mcp-servers/mcp-reference-data/function_app.py`):

| Route | Purpose |
| --- | --- |
| `GET /.well-known/mcp` | discovery |
| `POST /mcp` | JSON-RPC message handling (`tools/list`, `tools/call`) |
| `GET /mcp` | returns 405; the client retries and falls back to POST |
| `GET /health` | liveness |

Tool implementations live in sibling modules (`npi_tools.py`, `icd10_tools.py`, `cms_tools.py`)
so `function_app.py` stays a thin transport layer. `shared/` holds code common to all servers.

## Layer 2 - agents and scoped tool views

The most important design choice in the repository lives in `src/agents/tools.py`. There are 38
tools across the three servers, and **no agent ever sees all 38**. A single server is sliced into
different views per role:

```python
REFERENCE_DATA_COMPLIANCE = ["validate_npi", "lookup_npi", "validate_icd10", "lookup_icd10"]
REFERENCE_DATA_COVERAGE   = CMS_TOOLS_ALL + ICD10_TOOLS_SEARCH
```

`MCPToolKit.compliance_tools()` hands the Compliance Agent a connection carrying
`allowed_tools=REFERENCE_DATA_COMPLIANCE`, so it sees four tools. `coverage_tools()` returns a
different slice of the same server plus RAG search.

This matters because tool-selection accuracy degrades sharply when a model is shown dozens of
options. Scoping is what makes the workflow reproducible.

Two properties of `MCPToolKit` are worth knowing before debugging:

- `__aenter__` connects **every** server up front. A server that is down aborts the run rather
  than degrading it, which is why a local run needs all three processes even if the workflow
  barely touches one of them.
- Every role method constructs a *new* tool instance over a shared `httpx.AsyncClient`. The
  client injects the APIM subscription key header when one is configured.

Agent roles are defined in `agents.py` via `create_*_agent` factories (compliance, clinical
reviewer, coverage, synthesis, plus per-workflow orchestrators).

## Layer 3 - workflows, beads, and waypoints

Prior-auth is not one prompt. It is five stages, called beads:

| Bead | Does | Pattern |
| --- | --- | --- |
| 001 intake | Compliance validates NPI / ICD-10 / CPT | **gate**, can halt the run |
| 002 clinical | Clinical Reviewer and Coverage in parallel | **concurrent** |
| 003 recommend | Synthesis produces APPROVE / PEND / DENY | sequential |
| 004 decision | Human confirms or overrides | separate entry point |
| 005 notify | Notification letter and determination JSON | sequential |

After each bead the whole assessment is serialized to
`.runs/<timestamp>_<request-id>/waypoints/assessment.json`. State lives on disk rather than only
in memory, so an interrupted run still yields a readable artifact showing exactly how far it got.
That file is also the resumption mechanism (`_first_incomplete_bead`, `_bead_needs_work`).

Bead 004 is a separate function (`run_prior_auth_decision`) by design: a human sits between the
AI recommendation and the decision of record.

## Request flow

```
main.py --workflow prior-auth --local
  -> config.py       reads MCP_*_URL from env (localhost:708x under --local)
  -> llm_client.py   AzureCliCredential -> Azure OpenAI
  -> MCPToolKit      connects all three servers up front
  -> bead 001        Compliance agent, four scoped tools, gate
  -> bead 002        ConcurrentBuilder: two agents, six tool calls
  -> bead 003        Synthesis
```

## Running it locally

```bash
make run-prior-auth-local          # or: RUN_TIMEOUT=180 make run-prior-auth-local
```

`scripts/run-prior-auth-local.sh` runs preflight checks, starts the three servers on ports
7081-7083 under `setsid`, waits for each to answer, runs the workflow under `timeout`, then kills
each process group so no workers are orphaned. Ports and timeouts are environment-overridable.

Two environment facts that cost real debugging time:

- **Ports 7071-7073 may already be taken.** An unrelated Functions host can hold them and answer
  401, which looks like an auth bug rather than a port collision. Hence the 7081-7083 default.
- **Two virtualenvs exist and are not interchangeable.** `src/agents/.venv` has the full agent
  stack but no pytest; the top-level `uv` venv has pytest but no `agent_framework`. `make
  test-local` bridges them with a `PYTHONPATH` splice.

## Verified working

A live run against Azure exercises the full chain: AAD auth, Azure OpenAI, MCP transport, scoped
tool dispatch, orchestration, artifact write, and teardown. Bead 001 completes and the gate
passes; the four coverage tools return in roughly 30 ms each.

## Known gaps

| Issue | Impact |
| --- | --- |
| `h1g` | Bead 002 hangs when a concurrent tool call fails. The model replies after the tool results, then the superstep never completes. Blocks a full five-bead run. |
| `h3v` | `cosmos-rag` has no backing database or embedding endpoint locally, so `hybrid_search` returns 500 and audit writes fail. This is what currently triggers `h1g`. |

Because bead 003 never runs, a halted assessment reports
`recommendation.decision: ""`, which fails schema validation. That is an artifact of the
incomplete run, not a schema defect.

## Testing

CI (`.github/workflows/main_staging_ci.yml`) runs exactly:

```bash
uv run ruff check src/agents tests scripts
uv run pytest tests/unit tests/eval -q
uv run python scripts/eval_prior_auth.py
uv run python scripts/eval_contracts.py
```

`tests/integration/` is **not** in CI; it requires live services and fails offline.
