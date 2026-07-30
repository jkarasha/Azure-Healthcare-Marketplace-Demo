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

### The call sites are NOT uniform

The four workflows and `framework_devui.py` use **different keyword spellings**
for the same client. This must not be assumed away during implementation:

```python
# The 4 workflows (prior_auth, clinical_trials, literature_search, patient_data)
AzureOpenAIResponsesClient(
    credential=credential,
    endpoint=config.openai.endpoint,
    deployment_name=config.openai.deployment_name,
    api_version=config.openai.api_version,
)

# framework_devui.py — different kwargs
AzureOpenAIResponsesClient(
    azure_endpoint=endpoint,
    azure_deployment=deployment,
    credential=credential,
    api_version=api_version,
)
```

`framework_devui.py` also differs behaviorally: it wraps construction in a
`try: DefaultAzureCredential() / except: AzureCliCredential()` fallback, and it
reads endpoint/deployment from `os.getenv` directly rather than from
`AgentConfig`.

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
def create_chat_client(
    config: AgentConfig,
    *,
    local: bool,
    credential: object | None = None,
) -> OpenAIChatClient
```

Responsibilities:

- Select the credential: use `credential` if explicitly supplied; otherwise
  `AzureCliCredential` when `local`, else `DefaultAzureCredential`.
- Map `config.openai.endpoint` → `azure_endpoint`, `deployment_name` → `model`.
- Apply `resolve_api_version`; omit the kwarg entirely when it returns `None`.

It contains no other branching, so it needs no offline test; the local-only
smoke test covers it.

The explicit `credential` parameter exists solely so `framework_devui.py` can
keep its existing `DefaultAzureCredential` → `AzureCliCredential` try/except
fallback. Collapsing that fallback into the factory's `local` flag would be a
**behavior change**, not a refactor: the current code retries on failure,
whereas `local` selects one credential up front. The fallback stays at the
devui call site.

Note `AgentConfig` is imported from `agents.config`, which requires
`python-dotenv`. That is acceptable here because `llm_client.py` already
imports `agent_framework` and is therefore never importable by the offline
suite. This is precisely why `resolve_api_version` lives in the separate
stdlib-only `llm_options.py`.

### Call sites

The four workflows collapse to:

```python
client = create_chat_client(config, local=local)
```

`framework_devui.py` keeps its own try/except and passes the credential
explicitly, preserving today's retry semantics exactly:

```python
try:
    client = create_chat_client(config, local=False,
                                credential=DefaultAzureCredential())
except Exception:
    logger.warning("DefaultAzureCredential failed, trying AzureCliCredential")
    client = create_chat_client(config, local=False,
                                credential=AzureCliCredential())
```

`framework_devui.py` currently reads endpoint/deployment from `os.getenv`
rather than `AgentConfig`. The implementation must either build an
`AgentConfig` there or keep those reads and pass them through; whichever is
chosen, the existing "endpoint not set" error message and its guidance text
must be preserved.

### Pinning

`src/agents/requirements.txt` gets exact pins for **every** agent-framework
distribution the repo actually imports, verified against the working venv:

```
agent-framework==1.8.0
agent-framework-core==1.8.0
agent-framework-openai==1.8.0
agent-framework-orchestrations==1.0.0rc3
agent-framework-devui==1.0.0b260528
agent-framework-lab==1.0.0b251024
```

`agent-framework-openai` is a **separate distribution** that provides
`agent_framework.openai` (and therefore `OpenAIChatClient`, the class this
migration depends on). Omitting it would leave the exact same drift hole this
change exists to close. `agent-framework-devui` is required by
`framework_devui.py`. `agent-framework-lab` provides `agent_framework_lab_gaia`,
imported by `scripts/eval_native_agent_framework.py`, which
`make eval-native-local` (and therefore `make eval-all`) invokes.

Note that `agent-framework` is only a meta-package that requires
`agent-framework-core[all]`, and `[all]` pulls ~20 sibling distributions
unpinned. Pinning the five above constrains everything the repo imports
directly; the remaining siblings stay unpinned by choice, since pinning
packages the code never imports would create maintenance burden without
reducing risk. If a future import reaches a new sibling, that sibling must be
added here.

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

**`tests/local/test_framework_api.py`** — deliberately **excluded from CI**.
Asserts the API surface the repo depends on still exists:

- `OpenAIChatClient.__init__` accepts `azure_endpoint`, `model`, `credential`,
  `api_version`.
- `Agent.__init__` accepts `client`.
- `ConcurrentBuilder.__init__` accepts `participants`.

These are signature assertions only — no network, no credentials, no LLM calls.

This is the test that would have caught this outage.

### Excluding `tests/local` from the default run — required

`pyproject.toml` sets `testpaths = ["tests"]`, so a bare `pytest` **would**
collect `tests/local/` and fail with `ModuleNotFoundError: agent_framework`.
The implementation must prevent this explicitly. Required changes:

1. Add `--ignore=tests/local` to `[tool.pytest.ini_options] addopts` in
   `pyproject.toml`, so bare `pytest` and `testpaths` both skip it.
2. Add a `test-local` Make target that runs it **with the agents venv**, not
   the `uv` venv:

   ```
   test-local:
   	@src/agents/.venv/bin/python -m pytest tests/local -q
   ```

`make test-unit`, `make eval-all`, and the `python-unit-tests` CI job pass
explicit paths (`tests/unit tests/eval`) and so are already unaffected; the
`addopts` change protects the bare-`pytest` case, which is how a developer or a
future CI job would most plausibly trip over it.

Running `tests/local` under `uv run pytest` will always fail by design, because
that venv intentionally excludes the framework. The Make target exists so the
correct interpreter is not left to memory.

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
