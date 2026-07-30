# Agent Framework 1.8 Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the agent CLI by migrating from the removed `AzureOpenAIResponsesClient` to `OpenAIChatClient`, behind a single client factory, and pin the dependency that drifted.

**Architecture:** Extract one factory, `create_chat_client()`, into `src/agents/llm_client.py`. Put its only conditional logic — the `api_version` rule — into a stdlib-only `src/agents/llm_options.py` so it is testable in the offline CI venv. Replace all 11 call sites across 5 files with calls to the factory. Pin every agent-framework distribution the repo imports.

**Tech Stack:** Python 3.11, `agent-framework` 1.8.0, `azure-identity`, pytest, `uv` (offline venv) and `src/agents/.venv` (full framework venv).

**Spec:** `docs/superpowers/specs/2026-07-30-agent-framework-1.8-migration-design.md`

---

## Critical environment facts

Read these before starting. Getting them wrong will waste your time.

**Two different virtualenvs.** They are not interchangeable.

| Venv | How to invoke | Contains |
| --- | --- | --- |
| Offline (uv) | `uv run pytest ...` | pytest, httpx, ruff, rich **only** |
| Agents | `src/agents/.venv/bin/python ...` | full agent-framework stack |

The offline venv has **no** `agent_framework` and **no** `python-dotenv`. So
`src/agents/config.py` and `src/agents/llm_client.py` are **not importable** by
`tests/unit/`. Only stdlib-only modules are. This is why `llm_options.py` exists
as a separate file.

**Line endings.** `.gitattributes` forces LF only for `*.sh`, `Makefile`,
`*.bash`. Many tracked files are **CRLF**, including all four workflow files,
`framework_devui.py`, and `src/agents/requirements.txt`. Editors that normalize
line endings will turn a 3-line change into a whole-file diff.

**After every commit, run `git show --numstat HEAD`** and confirm the line
counts are proportionate to your actual change. If a file shows hundreds of
changed lines for a small edit, you converted its line endings — fix it before
moving on.

**Do not run `git push`.** The human will handle landing the branch.

---

## File Structure

| File | Status | Responsibility |
| --- | --- | --- |
| `src/agents/llm_options.py` | Create | Stdlib-only. `resolve_api_version()` — decides whether to send `api_version`. |
| `src/agents/llm_client.py` | Create | Builds the `OpenAIChatClient`. Owns credential selection and kwarg mapping. |
| `src/agents/workflows/prior_auth.py` | Modify | Lines 39, 411-417 → factory call. |
| `src/agents/workflows/clinical_trials.py` | Modify | Lines 24, 66-72 → factory call. |
| `src/agents/workflows/literature_search.py` | Modify | Lines 20, 62-68 → factory call. |
| `src/agents/workflows/patient_data.py` | Modify | Lines 16, 52-58 → factory call. |
| `src/agents/framework_devui.py` | Modify | Lines 58, 98-127 → factory call, keeping its retry fallback. |
| `src/agents/requirements.txt` | Modify | Exact pins for all 6 imported distributions. |
| `pyproject.toml` | Modify | `addopts` gains `--ignore=tests/local`. |
| `Makefile` | Modify | New `test-local` target. |
| `.env.example` | Modify | Clear the stale `AZURE_OPENAI_API_VERSION`. |
| `src/agents/devui.py` | Modify | Lines 239, 247, 591 → stop writing back the rejected api_version. |
| `tests/unit/test_llm_options.py` | Create | Offline test of the api_version rule. Runs in CI. |
| `tests/local/test_framework_api.py` | Create | Framework API-drift guard. Excluded from CI. |

---

## Task 1: The `api_version` resolver

The only conditional logic in this migration. Stdlib-only so the offline CI
gate can test it.

**Rule:** send `api_version` only when the operator set a real dated version.
Treat unset, empty, whitespace, and the sentinels `preview` / `v1` / `none` as
"omit the kwarg". Omitting is the only setting that works against both
`*.openai.azure.com` and `*.cognitiveservices.azure.com`.

**Files:**
- Create: `src/agents/llm_options.py`
- Test: `tests/unit/test_llm_options.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_llm_options.py`:

```python
"""Tests for the Azure OpenAI api_version resolution rule.

This module must stay importable in the offline CI venv, which has no
agent_framework and no python-dotenv. Import only from agents.llm_options.
"""

import pytest

from agents.llm_options import resolve_api_version


class TestResolveApiVersionOmits:
    """Values that mean 'do not send api_version at all'."""

    @pytest.mark.parametrize(
        "raw",
        [
            None,
            "",
            "   ",
            "\t",
            "preview",
            "PREVIEW",
            "Preview",
            "v1",
            "V1",
            "none",
            "NONE",
            "  preview  ",
        ],
    )
    def test_returns_none(self, raw):
        assert resolve_api_version(raw) is None


class TestResolveApiVersionPassesThrough:
    """Real dated versions stay under operator control."""

    @pytest.mark.parametrize(
        "raw",
        [
            "2024-10-21",
            "2025-01-01-preview",
            "2025-04-01-preview",
        ],
    )
    def test_returns_value_unchanged(self, raw):
        assert resolve_api_version(raw) == raw

    def test_strips_surrounding_whitespace(self):
        assert resolve_api_version("  2024-10-21  ") == "2024-10-21"
```

- [ ] **Step 2: Run the test and verify it fails**

```bash
uv run pytest tests/unit/test_llm_options.py -q
```

Expected: collection error, `ModuleNotFoundError: No module named 'agents.llm_options'`.

- [ ] **Step 3: Write the implementation**

Create `src/agents/llm_options.py`:

```python
"""Pure helpers for Azure OpenAI client options.

This module must not import anything outside the standard library. It is
imported by the offline unit-test suite, whose venv contains neither
agent_framework nor python-dotenv.
"""

from __future__ import annotations

# Values that are not real API versions. Azure's newer "v1" surface is
# selected by omitting api_version entirely, which is also the only setting
# that works against both *.openai.azure.com and *.cognitiveservices.azure.com.
_OMIT_SENTINELS = frozenset({"preview", "v1", "none"})


def resolve_api_version(raw: str | None) -> str | None:
    """Return the api_version to send, or None to omit the kwarg entirely.

    Args:
        raw: The configured value, typically ``AZURE_OPENAI_API_VERSION``.

    Returns:
        The trimmed version string, or ``None`` when the caller should not
        pass ``api_version`` at all.
    """
    if raw is None:
        return None
    value = raw.strip()
    if not value:
        return None
    if value.lower() in _OMIT_SENTINELS:
        return None
    return value
```

- [ ] **Step 4: Run the test and verify it passes**

```bash
uv run pytest tests/unit/test_llm_options.py -q
```

Expected: `16 passed`.

- [ ] **Step 5: Run the full offline suite and lint**

```bash
uv run pytest tests/unit tests/eval -q && uv run ruff check src/agents tests scripts
```

Expected: `123 passed` (107 existing + 16 new), then `All checks passed!`.

- [ ] **Step 6: Commit**

```bash
git add src/agents/llm_options.py tests/unit/test_llm_options.py
git commit -m "feat: add stdlib-only api_version resolver

Omitting api_version is the only setting that works against both
*.openai.azure.com and *.cognitiveservices.azure.com. Kept stdlib-only
so the offline CI venv (no agent_framework, no dotenv) can test it."
git show --numstat HEAD
```

Confirm numstat shows only the two new files.

---

## Task 2: The client factory

**Files:**
- Create: `src/agents/llm_client.py`

There is no offline test for this file — it imports `agent_framework`, so the
offline venv cannot load it. Task 6 adds the guard test that covers it.

- [ ] **Step 1: Write the implementation**

Create `src/agents/llm_client.py`:

```python
"""Factory for the Azure-backed chat client used by every workflow.

agent_framework 1.8 removed AzureOpenAIResponsesClient. The replacement is the
unified OpenAIChatClient, which accepts Azure parameters directly:

    endpoint        -> azure_endpoint
    deployment_name -> model

This module is the single seam where the framework's client is constructed, so
a future upstream change is a one-file fix rather than an 11-site hunt.
"""

from __future__ import annotations

from typing import Any

from agent_framework.openai import OpenAIChatClient
from azure.identity import AzureCliCredential, DefaultAzureCredential

from .config import AgentConfig
from .llm_options import resolve_api_version


def create_chat_client(
    config: AgentConfig,
    *,
    local: bool,
    credential: Any | None = None,
) -> OpenAIChatClient:
    """Build the chat client for a workflow run.

    Args:
        config: Loaded agent configuration.
        local: When True, prefer AzureCliCredential (developer machine).
        credential: Explicit credential. When provided, ``local`` is not used
            for credential selection. This exists so framework_devui.py can
            keep its DefaultAzureCredential -> AzureCliCredential retry, which
            is a fallback-on-failure and is NOT equivalent to choosing a
            credential up front.

    Returns:
        A configured OpenAIChatClient.
    """
    if credential is None:
        credential = AzureCliCredential() if local else DefaultAzureCredential()

    kwargs: dict[str, Any] = {
        "credential": credential,
        "azure_endpoint": config.openai.endpoint,
        "model": config.openai.deployment_name,
    }

    api_version = resolve_api_version(config.openai.api_version)
    if api_version is not None:
        kwargs["api_version"] = api_version

    return OpenAIChatClient(**kwargs)
```

- [ ] **Step 2: Verify it imports under the agents venv**

```bash
src/agents/.venv/bin/python -c "
import warnings; warnings.filterwarnings('ignore')
import sys; sys.path.insert(0, 'src')
from agents.llm_client import create_chat_client
print('import OK')
" 2>&1 | tail -1
```

Expected: `import OK`.

- [ ] **Step 3: Verify lint and that the offline suite is unaffected**

```bash
uv run ruff check src/agents tests scripts && uv run pytest tests/unit tests/eval -q
```

Expected: `All checks passed!` then `123 passed`.

- [ ] **Step 4: Commit**

```bash
git add src/agents/llm_client.py
git commit -m "feat: add create_chat_client factory

Single seam for framework client construction. Accepts an explicit
credential so framework_devui can keep its retry-on-failure fallback."
git show --numstat HEAD
```

---

## Task 3: Migrate the four workflows

All four are byte-identical at the call site, so the same edit applies to each.
Do all four in this one task and commit once.

**Files:**
- Modify: `src/agents/workflows/prior_auth.py` (import line 39, client line 411)
- Modify: `src/agents/workflows/clinical_trials.py` (import line 24, client line 66)
- Modify: `src/agents/workflows/literature_search.py` (import line 20, client line 62)
- Modify: `src/agents/workflows/patient_data.py` (import line 16, client line 52)

**All four files are CRLF.** Preserve it.

- [ ] **Step 1: Confirm the current state**

```bash
grep -rn "AzureOpenAIResponsesClient" src/ --include=*.py | grep -v ".venv"
```

Expected: 11 lines across the 5 files.

- [ ] **Step 2: Replace the import in each of the four workflow files**

Remove this line:

```python
from agent_framework.azure import AzureOpenAIResponsesClient
```

The `azure.identity` import on the adjacent line is still needed only if the
file uses those credentials elsewhere. After Step 3 it will not, so also remove:

```python
from azure.identity import AzureCliCredential, DefaultAzureCredential
```

Add, in the local-import group with the other `.`-relative imports:

```python
from ..llm_client import create_chat_client
```

Note the **two** dots: these files live in `src/agents/workflows/`, and
`llm_client` is in `src/agents/`.

- [ ] **Step 3: Replace the construction in each of the four workflow files**

Replace this exact two-statement block:

```python
    credential = DefaultAzureCredential() if not local else AzureCliCredential()
    client = AzureOpenAIResponsesClient(
        credential=credential,
        endpoint=config.openai.endpoint,
        deployment_name=config.openai.deployment_name,
        api_version=config.openai.api_version,
    )
```

with:

```python
    client = create_chat_client(config, local=local)
```

- [ ] **Step 4: Verify no workflow still references the removed symbol**

```bash
grep -rn "AzureOpenAIResponsesClient" src/agents/workflows/ && echo "STILL PRESENT - FIX" || echo "workflows clean"
```

Expected: `workflows clean`.

- [ ] **Step 5: Verify every workflow module imports**

```bash
src/agents/.venv/bin/python -c "
import warnings; warnings.filterwarnings('ignore')
import sys; sys.path.insert(0, 'src')
from agents.workflows import prior_auth, clinical_trials, literature_search, patient_data
print('all four workflow modules import OK')
" 2>&1 | tail -1
```

Expected: `all four workflow modules import OK`.

- [ ] **Step 6: Verify the CLI itself starts**

```bash
cd src && ../src/agents/.venv/bin/python -m agents --help 2>&1 | tail -3; cd ..
```

Expected: argparse help text, no traceback. This is the first moment the CLI
works again.

- [ ] **Step 7: Lint and run the offline suite**

```bash
uv run ruff check src/agents tests scripts && uv run pytest tests/unit tests/eval -q
```

Expected: `All checks passed!` then `123 passed`.

Ruff will flag an unused import if you missed removing `AzureCliCredential` /
`DefaultAzureCredential` from any file. Fix and re-run.

- [ ] **Step 8: Commit and check line endings**

```bash
git add src/agents/workflows/
git commit -m "fix: migrate the four workflows to create_chat_client

agent_framework 1.8 removed AzureOpenAIResponsesClient. All four
workflows constructed it identically, so they collapse to one factory
call. This is what makes the CLI importable again."
git show --numstat HEAD
```

Expected numstat: roughly 3-9 changed lines per file. If any file shows
hundreds, you converted CRLF to LF — revert and redo that file.

---

## Task 4: Migrate the DevUI

`framework_devui.py` differs from the workflows in three ways: it uses
`azure_endpoint=`/`azure_deployment=` kwargs, it reads `os.getenv` directly
instead of `AgentConfig`, and it wraps construction in a retry.

`AgentConfig.load()` reads the same three environment variables with the same
defaults (`gpt-4o`, `preview`), so switching to it changes no behavior.

**The retry must be preserved.** Collapsing it into `local=` would change
behavior: today the code *retries* after a failure; a flag *chooses* up front.

**Files:**
- Modify: `src/agents/framework_devui.py` (import line 58, block lines 98-127)

This file is CRLF.

- [ ] **Step 1: Replace the imports at line 58**

Remove:

```python
    from agent_framework.azure import AzureOpenAIResponsesClient
```

Keep the existing `agent_framework_orchestrations` and `azure.identity` imports
— both credentials are still used by the retry. Add alongside them:

```python
    from .config import AgentConfig
    from .llm_client import create_chat_client
```

- [ ] **Step 2: Replace the whole client block (lines 98-127)**

Replace this:

```python
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4o")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION", "preview")

    if not endpoint:
        raise OSError(
            "AZURE_OPENAI_ENDPOINT is not set. "
            "Create src/agents/.env with:\n"
            "  AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com\n"
            "  AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o"
        )

    try:
        credential = DefaultAzureCredential()
        client = AzureOpenAIResponsesClient(
            azure_endpoint=endpoint,
            azure_deployment=deployment,
            credential=credential,
            api_version=api_version,
        )
    except Exception:
        # Fall back to AzureCliCredential if DefaultAzureCredential fails
        logger.warning("DefaultAzureCredential failed, trying AzureCliCredential")
        credential = AzureCliCredential()
        client = AzureOpenAIResponsesClient(
            azure_endpoint=endpoint,
            azure_deployment=deployment,
            credential=credential,
            api_version=api_version,
        )
```

with this:

```python
    config = AgentConfig.load(local=False)

    if not config.openai.endpoint:
        raise OSError(
            "AZURE_OPENAI_ENDPOINT is not set. "
            "Create src/agents/.env with:\n"
            "  AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com\n"
            "  AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o"
        )

    try:
        client = create_chat_client(
            config, local=False, credential=DefaultAzureCredential()
        )
    except Exception:
        # Fall back to AzureCliCredential if DefaultAzureCredential fails
        logger.warning("DefaultAzureCredential failed, trying AzureCliCredential")
        client = create_chat_client(
            config, local=False, credential=AzureCliCredential()
        )
```

The error message text is unchanged on purpose — it is user-facing guidance.

- [ ] **Step 3: Verify the symbol is gone everywhere**

```bash
grep -rn "AzureOpenAIResponsesClient" src/ --include=*.py | grep -v ".venv" && echo "STILL PRESENT - FIX" || echo "repo clean of removed symbol"
```

Expected: `repo clean of removed symbol`.

- [ ] **Step 4: Verify the module imports**

```bash
src/agents/.venv/bin/python -c "
import warnings; warnings.filterwarnings('ignore')
import sys; sys.path.insert(0, 'src')
import agents.framework_devui
print('framework_devui imports OK')
" 2>&1 | tail -1
```

Expected: `framework_devui imports OK`.

If ruff later reports `os` as unused in this file, leave it — check first
whether `os` is used elsewhere in the module before removing the import.

- [ ] **Step 5: Lint and run the offline suite**

```bash
uv run ruff check src/agents tests scripts && uv run pytest tests/unit tests/eval -q
```

Expected: `All checks passed!` then `123 passed`.

- [ ] **Step 6: Commit and check line endings**

```bash
git add src/agents/framework_devui.py
git commit -m "fix: migrate framework_devui to create_chat_client

Keeps the DefaultAzureCredential -> AzureCliCredential retry by passing
the credential explicitly; collapsing it into the local flag would turn
a retry-on-failure into an up-front choice. Switches to AgentConfig,
which reads the same env vars with the same defaults."
git show --numstat HEAD
```

---

## Task 5: Pin the dependencies

The unpinned floor is the root cause of this outage.

**Files:**
- Modify: `src/agents/requirements.txt`

**This file is CRLF.** Edit it without normalizing line endings.

- [ ] **Step 1: Confirm the installed versions you are about to pin**

```bash
src/agents/.venv/bin/python -m pip list 2>/dev/null | grep -iE "^agent-framework(-core|-openai|-orchestrations|-devui|-lab)?\s"
```

Expected:

```
agent-framework                       1.8.0
agent-framework-core                  1.8.0
agent-framework-devui                 1.0.0b260528
agent-framework-lab                   1.0.0b251024
agent-framework-openai                1.8.0
agent-framework-orchestrations        1.0.0rc3
```

If any version differs, pin what is actually installed and note the difference
in the commit message. Do not pin a version you have not verified.

- [ ] **Step 2: Replace the agent-framework lines**

Replace these three lines:

```
# Core agent framework (includes openai, azure providers)
agent-framework[azure]>=1.0.0b260210
agent-framework-orchestrations>=1.0.0b260210
```

and this line further down:

```
agent-framework-devui
```

with a single pinned block (keep the surrounding comments and the
`azure-identity` / dotenv entries untouched):

```
# Core agent framework. PINNED: an unpinned floor let core drift to 1.8.0,
# which removed AzureOpenAIResponsesClient and broke every workflow.
# Pin every distribution the repo imports directly.
agent-framework==1.8.0
agent-framework-core==1.8.0
agent-framework-openai==1.8.0
agent-framework-orchestrations==1.0.0rc3

# Framework Developer UI (React app with debug panel, traces, entity discovery)
agent-framework-devui==1.0.0b260528

# agent_framework_lab_gaia, used by scripts/eval_native_agent_framework.py
agent-framework-lab==1.0.0b251024
```

- [ ] **Step 3: Verify the file is still CRLF**

```bash
file src/agents/requirements.txt
```

Expected: output contains `CRLF line terminators` and does **not** say
`CRLF, LF`. If it says both, you introduced mixed endings — normalize the whole
file back to CRLF.

- [ ] **Step 4: Verify the pins match the working venv**

```bash
src/agents/.venv/bin/python - <<'PY'
import re, subprocess
pins = {}
for line in open('src/agents/requirements.txt', encoding='utf-8'):
    m = re.match(r'^(agent-framework[\w-]*)==(\S+)\s*$', line.strip())
    if m:
        pins[m.group(1).lower()] = m.group(2)
out = subprocess.run(['src/agents/.venv/bin/python','-m','pip','list'],
                     capture_output=True, text=True).stdout
installed = {}
for line in out.splitlines():
    parts = line.split()
    if len(parts) == 2 and parts[0].lower().startswith('agent-framework'):
        installed[parts[0].lower()] = parts[1]
bad = [(k, v, installed.get(k)) for k, v in pins.items() if installed.get(k) != v]
print('pinned:', len(pins))
print('MISMATCHES:', bad if bad else 'none')
PY
```

Expected: `pinned: 6` and `MISMATCHES: none`.

- [ ] **Step 5: Commit**

```bash
git add src/agents/requirements.txt
git commit -m "fix: pin every imported agent-framework distribution

agent-framework[azure]>=1.0.0b260210 resolved to core 1.8.0, which
removed AzureOpenAIResponsesClient and broke all four workflows. Pin
the six distributions the repo imports directly, including
agent-framework-openai (provides OpenAIChatClient) and
agent-framework-lab (used by scripts/eval_native_agent_framework.py)."
git show --numstat HEAD
```

Expected numstat: a handful of lines. Hundreds means CRLF damage.

---

## Task 6: The API-drift guard test

The test that would have caught this outage. It runs under the agents venv and
is deliberately excluded from CI.

**Files:**
- Create: `tests/local/__init__.py`
- Create: `tests/local/test_framework_api.py`
- Modify: `pyproject.toml` (line 55, `addopts`)
- Modify: `Makefile` (new `test-local` target)

- [ ] **Step 1: Exclude `tests/local` from default collection first**

Do this *before* creating the directory, so you never leave the repo in a state
where `pytest` breaks.

In `pyproject.toml`, change line 55 from:

```toml
addopts = "-v --tb=short"
```

to:

```toml
addopts = "-v --tb=short --ignore=tests/local"
```

`testpaths = ["tests"]` means a bare `pytest` would otherwise collect
`tests/local` and fail with `ModuleNotFoundError: agent_framework`.

- [ ] **Step 2: Verify bare pytest still works**

```bash
uv run pytest tests/unit tests/eval -q
```

Expected: `123 passed`.

- [ ] **Step 3: Create the guard test**

Create `tests/local/__init__.py` as an empty file.

Create `tests/local/test_framework_api.py`:

```python
"""Guard against agent_framework API drift.

NOT part of the CI gate. Requires the full framework stack, so run it with
the agents venv:

    make test-local

An unpinned agent-framework floor once drifted to 1.8.0, which removed
AzureOpenAIResponsesClient and broke every workflow with no failing test.
These assertions are signature-only: no network, no credentials, no LLM calls.
"""

import inspect

import pytest

pytest.importorskip("agent_framework", reason="requires the agents venv")


def _params(func) -> set[str]:
    return set(inspect.signature(func).parameters)


class TestChatClientSurface:
    def test_openai_chat_client_accepts_azure_parameters(self):
        from agent_framework.openai import OpenAIChatClient

        params = _params(OpenAIChatClient.__init__)
        for name in ("azure_endpoint", "model", "credential", "api_version"):
            assert name in params, f"OpenAIChatClient lost '{name}'"


class TestAgentSurface:
    def test_agent_accepts_client(self):
        from agent_framework import Agent

        assert "client" in _params(Agent.__init__)

    def test_core_symbols_exist(self):
        import agent_framework

        for name in ("Agent", "MCPStreamableHTTPTool", "SupportsChatGetResponse"):
            assert hasattr(agent_framework, name), f"agent_framework lost '{name}'"


class TestOrchestrationsSurface:
    def test_concurrent_builder_accepts_participants(self):
        from agent_framework_orchestrations import ConcurrentBuilder

        assert "participants" in _params(ConcurrentBuilder.__init__)

    def test_concurrent_builder_has_build(self):
        from agent_framework_orchestrations import ConcurrentBuilder

        assert callable(ConcurrentBuilder.build)


class TestFactoryImports:
    def test_llm_client_imports(self):
        from agents.llm_client import create_chat_client

        params = _params(create_chat_client)
        assert {"config", "local", "credential"} <= params
```

- [ ] **Step 4: Add the Make target**

In `Makefile`, add next to `test-unit`:

```make
test-local:
	@src/agents/.venv/bin/python -m pytest tests/local -q -p no:cacheprovider
```

Add `test-local` to the `.PHONY` list on line 5.

**The `Makefile` is LF** (enforced by `.gitattributes`) and **requires a real
tab** for the recipe line, not spaces.

- [ ] **Step 5: Run the guard test**

```bash
make test-local
```

Expected: `6 passed`.

- [ ] **Step 6: Confirm CI collection is unaffected**

```bash
uv run pytest tests/unit tests/eval -q && uv run pytest --collect-only -q 2>&1 | tail -3
```

Expected: `123 passed`, and the collect-only output must not list any
`tests/local` items.

- [ ] **Step 7: Lint and commit**

```bash
uv run ruff check src/agents tests scripts
git add tests/local pyproject.toml Makefile
git commit -m "test: add framework API-drift guard

Signature-only assertions covering the symbols the repo depends on.
Excluded from CI via addopts --ignore=tests/local, since testpaths
would otherwise collect it into the framework-free offline venv.
Run with: make test-local"
git show --numstat HEAD
```

---

## Task 7: Clear the stale API version

`.env.example` advertises an `api_version` that the live resource rejects, and
the DevUI settings panel actively **writes it back**.

**Files:**
- Modify: `.env.example`
- Modify: `src/agents/devui.py` (lines 239, 247, 591)

`.env` itself is gitignored — the human updates their own copy.

`src/agents/devui.py` is a **different file** from `src/agents/framework_devui.py`
(Task 4). It does not import the removed client class, which is why it is not in
the 5-file migration map. It matters anyway: its settings panel defaults
`api_version` to `2025-01-01-preview`, coerces a blank input **back** to that
value, and then persists it to both `os.environ` and `src/agents/.env`. Left
alone, any user who opens the settings UI gets the exact value the live resource
rejects written into their environment, with no way to clear it — silently
defeating `resolve_api_version()`.

- [ ] **Step 1: Inspect the current values**

```bash
grep -n "AZURE_OPENAI_API_VERSION" .env.example
grep -n "2025-01-01-preview" src/agents/devui.py
```

Expected: one line in `.env.example`, and three lines in `devui.py` (239, 247, 591).

- [ ] **Step 2: Replace the line in `.env.example`**

Set the value to empty and document why:

```
# Leave empty to use the current Azure OpenAI API surface. This is the only
# setting that works against both *.openai.azure.com and
# *.cognitiveservices.azure.com. Set a dated version only if you need to pin one.
AZURE_OPENAI_API_VERSION=
```

- [ ] **Step 3: Stop `devui.py` defaulting to the rejected version**

At line 239, in `_load_settings()`, change:

```python
        "api_version": os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview"),
```

to:

```python
        "api_version": os.getenv("AZURE_OPENAI_API_VERSION", ""),
```

- [ ] **Step 4: Stop `devui.py` coercing a blank back to the rejected version**

At line 247, in `_save_settings()`, change:

```python
    api_version = api_version.strip() or "2025-01-01-preview"
```

to:

```python
    # Empty is meaningful: it selects the current API surface, which is the
    # only setting that works against both endpoint forms. Do not coerce it.
    api_version = api_version.strip()
```

Leave the `deployment` coercion on the line above **unchanged** — `gpt-4o` is a
real default and blank there is not meaningful.

- [ ] **Step 5: Stop the UI advertising the rejected version**

At line 591, change the placeholder:

```python
                    placeholder="2025-01-01-preview",
```

to:

```python
                    placeholder="leave empty for the current API surface",
```

- [ ] **Step 6: Verify no rejected version remains in tracked source**

```bash
grep -rn "2025-01-01-preview" src/ .env.example --include=* 2>/dev/null | grep -v ".venv" || echo "clean"
```

Expected: `clean`. (Your own `.env` is gitignored and may still contain it —
that is Task 8 Step 5's concern, not this one.)

- [ ] **Step 7: Verify the module still imports and lint passes**

```bash
src/agents/.venv/bin/python -c "
import warnings; warnings.filterwarnings('ignore')
import sys; sys.path.insert(0, 'src')
import agents.devui
print('devui imports OK')
" 2>&1 | tail -1
uv run ruff check src/agents tests scripts
```

Expected: `devui imports OK`, then `All checks passed!`.

If `agents.devui` fails to import because `gradio` is missing, that is
pre-existing and out of scope — report it and rely on the ruff check instead.

- [ ] **Step 8: Verify line endings are unchanged**

```bash
file .env.example src/agents/devui.py && git diff --numstat .env.example src/agents/devui.py
```

Expected: small line counts (roughly 4 and 5), and the same line-ending
description each file had before your edit.

- [ ] **Step 9: Commit**

```bash
git add .env.example src/agents/devui.py
git commit -m "fix: stop writing the rejected AZURE_OPENAI_API_VERSION

2025-01-01-preview is rejected by current Azure OpenAI resources;
omitting api_version works against both endpoint forms. The DevUI
settings panel defaulted to that value and coerced a blank input back
to it, persisting it to os.environ and .env, which would have silently
defeated resolve_api_version(). Empty is now preserved as meaningful."
git show --numstat HEAD
```

---

## Task 8: Full verification and the live run

The point of the whole exercise. Nothing here changes code.

- [ ] **Step 1: Run the complete offline gate**

```bash
uv run ruff check src/agents tests scripts && \
uv run pytest tests/unit tests/eval -q && \
uv run python scripts/eval_prior_auth.py 2>&1 | tail -6 && \
uv run python scripts/eval_contracts.py 2>&1 | tail -2
```

Expected: `All checks passed!`, `123 passed`, `Average fidelity: 90.0 / 100`
with `Decision accuracy: 1/1 (100%)`, and `Contract eval passed.`

- [ ] **Step 2: Run the drift guard**

```bash
make test-local
```

Expected: `6 passed`.

- [ ] **Step 3: Confirm the MCP servers are up**

The live run needs them on 7081/7082. Ports 7071-7073 are occupied by an
unrelated Windows-side process, which is why non-default ports are used.

```bash
for p in 7081 7082; do echo "port $p: $(curl -s -m 5 -o /dev/null -w '%{http_code}' http://localhost:$p/.well-known/mcp)"; done
```

Expected: `200` for both. If not, restart them:

```bash
nohup ./scripts/local-test.sh mcp-reference-data 7081 > .local-logs/alt-reference-data.log 2>&1 &
nohup ./scripts/local-test.sh mcp-clinical-research 7082 > .local-logs/alt-clinical-research.log 2>&1 &
sleep 40
```

- [ ] **Step 4: Confirm Azure auth is live**

```bash
az account get-access-token --resource https://cognitiveservices.azure.com --query expiresOn -o tsv
```

Expected: a future timestamp. If it errors, stop and ask the human to run
`az login` — it is interactive and you cannot complete it.

- [ ] **Step 5: Check the local `.env` for a rejected API version**

Task 7 only fixed `.env.example`. `.env` is gitignored and is **not** changed by
this plan, so it may still carry the stale value.

```bash
grep -n "AZURE_OPENAI_API_VERSION" .env src/agents/.env 2>/dev/null
```

If either file sets a dated value such as `2025-01-01-preview`, do **not** edit
the human's `.env`. The run command in the next step passes
`AZURE_OPENAI_API_VERSION=` explicitly, which `resolve_api_version()` maps to
"omit" and which overrides the file. Note in your report that the human should
clear the value in their own `.env` to avoid the same trap outside this run.

- [ ] **Step 6: Run the workflow against Azure**

Two overrides are required. The resource has `gpt-4.1`, not the `gpt-4o`
default, and it **rejects** `2025-01-01-preview`, so `api_version` is forced
empty (which means "omit").

```bash
cd src && source agents/.venv/bin/activate && \
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4.1 \
AZURE_OPENAI_API_VERSION= \
MCP_REFERENCE_DATA_URL=http://localhost:7081/mcp \
MCP_CLINICAL_RESEARCH_URL=http://localhost:7082/mcp \
MCP_COSMOS_RAG_URL=http://localhost:7083/mcp \
python -m agents --workflow prior-auth \
  --input ../data/sample_cases/prior_auth_baseline/pa_request.json --local 2>&1 | tail -30
cd ..
```

Expected: no traceback, and a run directory written under `.runs/`.

`cosmos-rag` on 7083 is **not** running (its Cosmos endpoint is still a
placeholder), so the policy-RAG step will degrade or fall back. That is
expected and out of scope. Beads 001-003 should still complete.

- [ ] **Step 7: Validate the produced assessment against the schema**

```bash
uv run python -c "
import json, sys, pathlib
sys.path.insert(0, 'src')
from agents.workflows.assessment_schema import validate_assessment
runs = sorted(pathlib.Path('.runs').glob('*/waypoints/assessment.json'),
              key=lambda p: p.stat().st_mtime)
if not runs:
    print('NO ASSESSMENT WRITTEN'); sys.exit(1)
latest = runs[-1]
data = json.loads(latest.read_text(encoding='utf-8'))
errors = validate_assessment(data)
print('file    :', latest)
print('decision:', data.get('recommendation', {}).get('decision'))
print('beads   :', sum(1 for b in data.get('beads', []) if b.get('status') == 'completed'), '/', len(data.get('beads', [])))
print('errors  :', errors if errors else 'none — schema valid')
"
```

Expected: a decision in `{APPROVE, PEND, DENY}` and `errors: none — schema valid`.

If the schema fails, capture the errors and report them. Do **not** patch
`parsing.py` or the schema to make it pass — a real shape change from the
Responses-to-ChatCompletions switch is a finding that needs discussion, and
`parsing.py` is covered by 107 tests that must not be weakened.

- [ ] **Step 8: Confirm the branch is clean and report**

```bash
git status --porcelain && git --no-pager log --oneline main..HEAD
```

Expected: no unexpected untracked files (`.runs/` is gitignored), and the task
commits listed.

Do **not** push. Report to the human:

- The live decision and whether the assessment was schema-valid.
- Whether the `cosmos-rag` gap changed the outcome.
- Any behavioral difference observed versus the golden case.
- Whether their `.env` still carries a stale `AZURE_OPENAI_API_VERSION` that
  they should clear (from Step 5).

---

## Out of scope

Do not touch these, even if you notice problems:

- `data/`, `deploy/`, and the MCP server implementations.
- The `cosmos-rag` Cosmos credential placeholder.
- Workflow prompts, agent instructions, and the assessment schema.
- The golden case's `confidence_score: 53.8` vs the documented formula's 57.8.
- The four Minor follow-ups from the prior-auth review (triplicated `BEAD_IDS`;
  the `VALID_BEAD_STATUSES` / `BEAD_VALID_STATUSES` disagreement on `blocked`;
  the unvalidated decision write at `prior_auth.py:815`; the unbalanced-quote
  hole in `_iter_all_objects`).
