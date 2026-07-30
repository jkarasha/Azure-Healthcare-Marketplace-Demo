# Agent Framework 1.8 Migration — Design

**Date:** 2026-07-30
**Status:** Approved (design), pending implementation plan

## Problem

The agent CLI cannot start. Every workflow fails at import:

```
ImportError: cannot import name 'AzureOpenAIResponsesClient'
from 'agent_framework.azure'
```

`src/agents/requirements.txt` declares an unpinned lower bound:

```
agent-framework[azure]>=1.0.0b260210
```

That meta-package resolves to `agent-framework-core[all]==<latest>`. The installed
core is **1.8.0**, but the code targets the `1.0.0b260210`-era API. Between those
releases `AzureOpenAIResponsesClient` was removed. It exists in no currently
published version, and no `agent-framework-azure-ai` distribution exists either,
so downgrading is not a durable option.

This is pre-existing dependency drift. It is unrelated to the prior-auth
execution-proof work: `clinical_trials.py` has an empty diff against `main`.

### Blast radius

The entire breakage is **one symbol at 11 sites across 5 files**:

| File | Sites |
| --- | --- |
| `src/agents/workflows/prior_auth.py` | 2 (import + construction) |
| `src/agents/workflows/clinical_trials.py` | 2 |
| `src/agents/workflows/literature_search.py` | 2 |
| `src/agents/workflows/patient_data.py` | 2 |
| `src/agents/framework_devui.py` | 3 (import + two constructions) |

Everything else the repo imports is already 1.8.0-compatible, verified by
inspection of the installed packages:

- `Agent(client=...)` — matches; `agents.py` already uses `client=`.
- `MCPStreamableHTTPTool`, `SupportsChatGetResponse` — present.
- `ConcurrentBuilder(participants=[...]).build()` — matches exactly.

A partial fix is not viable: `main.py` imports all four workflows at module
load, so the CLI stays broken until every site is migrated.

## Verified replacement

`OpenAIChatClient` in 1.8.0 is a unified client that accepts Azure parameters.
The mapping is 1:1:

| Old (`AzureOpenAIResponsesClient`) | New (`OpenAIChatClient`) |
| --- | --- |
| `endpoint` | `azure_endpoint` |
| `deployment_name` | `model` |
| `credential` | `credential` |
| `api_version` | `api_version` (see below) |

This was proven end-to-end against a live Azure resource
(`gpt-4.1`, AAD via `AzureCliCredential`), returning a correct completion.

### The `api_version` constraint

Probes against a live `AIServices` resource:

| Endpoint | `api_version` | Result |
| --- | --- | --- |
| `*.openai.azure.com` | `2025-01-01-preview` | rejected — `API version not supported` |
| `*.openai.azure.com` | `2024-10-21` | rejected |
| `*.openai.azure.com` | omitted | works |
| `*.cognitiveservices.azure.com` | `preview` | works |
| `*.cognitiveservices.azure.com` | omitted | works |

Omitting the parameter (the newer "v1" surface) is the only setting that works
on both endpoint forms. Note `.env` currently sets `2025-01-01-preview`, which
this resource rejects, and `config.py` defaults to `"preview"`.

## Design

### Two modules, split by testability

The offline CI venv intentionally excludes `agent_framework`. It also excludes
`python-dotenv`, so `agents.config` is **not** importable there either. Any logic
that needs offline test coverage must therefore live in a stdlib-only module —
the same constraint that produced `parsing.py` and `assessment_schema.py`.

**`src/agents/llm_options.py`** — stdlib only, no third-party imports.

```python
def resolve_api_version(raw: str | None) -> str | None
```

Returns `None` (meaning "omit the kwarg") when `raw` is `None`, empty, or
whitespace, or when it is a non-dated sentinel (`preview`, `v1`, `none`,
case-insensitive). Otherwise returns the value unchanged, so an operator who
sets a real dated version keeps control.

This is the only conditional logic in the change, and it is unit-testable
offline in the existing CI gate.

**`src/agents/llm_client.py`** — the thin framework-touching factory.

```python
def create_chat_client(config: AgentConfig, *, local: bool) -> OpenAIChatClient
```

Responsibilities:

- Select the credential: `AzureCliCredential` when `local`, else
  `DefaultAzureCredential`.
- Map `config.openai.endpoint` → `azure_endpoint`, `deployment_name` → `model`.
- Apply `resolve_api_version`; omit the kwarg entirely when it returns `None`.

It contains no other branching, so it needs no offline test; the local-only
smoke test covers it.

### Call sites

All 11 sites collapse to:

```python
client = create_chat_client(config, local=local)
```

`framework_devui.py` currently wraps construction in a
`DefaultAzureCredential` → `AzureCliCredential` try/except. That fallback is
preserved by passing `local` appropriately rather than duplicating the
try/except inside the factory.

### Pinning

`src/agents/requirements.txt` gets exact pins for the packages actually
imported:

```
agent-framework==1.8.0
agent-framework-core==1.8.0
agent-framework-orchestrations==1.0.0rc3
```

The unpinned `>=` floor is the root cause and is removed.

### Config and environment

- Clear the stale `AZURE_OPENAI_API_VERSION=2025-01-01-preview` in `.env` and
  `.env.example`.
- `config.py`'s `"preview"` default stays and is now correctly interpreted as
  "omit".

## Testing

**`tests/unit/test_llm_options.py`** — offline, runs in CI. Covers
`resolve_api_version`: `None`, empty, whitespace, `preview`/`PREVIEW`, `v1`,
`none`, and dated values that must pass through unchanged.

**`tests/local/test_framework_api.py`** — deliberately **excluded from CI**
(requires the full framework stack). Asserts the API surface the repo depends
on still exists:

- `OpenAIChatClient.__init__` accepts `azure_endpoint`, `model`, `credential`,
  `api_version`.
- `Agent.__init__` accepts `client`.
- `ConcurrentBuilder.__init__` accepts `participants`.

This is the test that would have caught this outage.

## Verification

1. Existing 107 offline tests stay green (`make test-unit`).
2. `ruff check` clean.
3. `make eval-prior-auth` still scores 90.0/100.
4. A real end-to-end `prior-auth` run against Azure completes and writes a
   schema-valid `waypoints/assessment.json`.

## Risks

**Responses API → Chat Completions is a genuine semantic change.** The repo only
calls `agent.run(prompt)` statelessly, so no behavioral difference is expected,
but this cannot be proven until the live run. If output shape shifts, it will
surface in `parsing.py`, which has 107 tests behind it.

**Pinning to 1.8.0 is a snapshot, not a strategy.** It stops silent drift but
does not track upstream. The local-only smoke test is the mechanism for
detecting the next break deliberately rather than by outage.

## Out of scope

- `data/`, `deploy/`, and the MCP servers.
- The `cosmos-rag` credential gap (Cosmos endpoint is still a placeholder).
- The four Minor follow-ups from the prior-auth review.
- Any change to workflow prompts, agent instructions, or the assessment schema.
