# Prior-Auth Execution Proof Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the prior-auth agent execution plane provable offline — a runnable test suite, deterministic tests for the fragile agent-output parsing seams, a single shared assessment schema contract, and a repeatable `make eval-prior-auth` gate.

**Architecture:** The prior-auth workflow's weakest link is the boundary where free-form LLM text becomes structured state. Today that boundary is a private `_extract_json_from_text()` plus a `text.find("}")` string heuristic buried in a 1,351-line module, with no tests, no schema enforcement, and no runnable pytest. This plan extracts those seams into two small focused modules (`parsing.py`, `assessment_schema.py`), drives them with deterministic fixtures that need no LLM and no MCP servers, then makes the existing eval harness actually executable and CI-gated. Live-LLM runs are explicitly out of scope for this slice.

**Tech Stack:** Python 3.12, uv (package manager — there is no pip on this machine), pytest, ruff, Microsoft Agent Framework (`agent_framework`, `agent_framework_orchestrations`), Make, GitHub Actions.

---

## Context for the Engineer

You have zero context on this codebase. Read this section before starting.

**What prior-auth does.** A payer receives a prior-authorization (PA) request: a member, a provider, and a requested service. The workflow runs five sequential units of work called **beads**:

| Bead ID | Phase | What it does |
|---|---|---|
| `bd-pa-001-intake` | Intake | Compliance agent validates NPI / ICD-10 / CPT |
| `bd-pa-002-clinical` | Clinical | ClinicalReviewer **and** CoverageAgent run concurrently |
| `bd-pa-003-recommend` | Recommend | Synthesis agent emits APPROVE / PEND / DENY |
| `bd-pa-004-decision` | Decision | Human confirms or overrides |
| `bd-pa-005-notify` | Notify | Letter + determination JSON |

Beads 001–003 are `run_prior_auth_workflow()`; beads 004–005 are `run_prior_auth_decision()`. Bead status transitions `not-started` → `in-progress` → `completed`. After each bead the workflow writes a **waypoint** — the full assessment dict — to `.runs/<timestamp>_<request-id>/waypoints/assessment.json`. Resume works by reading those bead statuses and restarting at the first incomplete one.

**The problem this plan fixes.** Bead 002 runs two agents concurrently via `ConcurrentBuilder`. The framework returns *one* concatenated string containing *both* agents' JSON. The current code splits them with:

```python
first_close = concurrent_text.find("}")   # src/agents/workflows/prior_auth.py:735
remainder = concurrent_text[first_close + 1 :]
coverage_parsed = _extract_json_from_text(remainder)
```

`find("}")` finds the first closing brace **anywhere**, including one closing a *nested* object inside the clinical agent's JSON. When the clinical agent emits any nested object (it always does — `clinical_summary` is nested), the remainder starts mid-object and the coverage parse silently returns `None`. The workflow then produces an assessment with an empty `policy` block and no error. That is the single highest-value bug in the execution plane.

**Verified current state (do not re-verify, this was checked on 2026-07-28):**
- `pytest` is **not installed** in any environment (`python3` or `src/agents/.venv`). The existing test file `tests/eval/test_prior_auth_eval.py` has never been run here.
- `pyproject.toml` sets `testpaths = ["tests", "src"]`. `src/` contains vendored Azure Functions dependencies under `src/mcp-servers/*/.python_packages/`, which include thousands of third-party test files (e.g. `regex/tests/test_regex.py`). Collection from `src` is broken by design.
- `data/sample_cases/` **does not exist**, but `src/agents/main.py:37` points `--demo` at `data/sample_cases/prior_auth_baseline/pa_request.json`. `load_input()` silently falls back to a hardcoded dict.
- `data/cases/001/a/waypoints/assessment.json` is the **only** committed assessment, and it fails the eval schema: no `request_id`, no `workflow_id`, no `status`; `recommendation` has `confidence_scores` instead of the required `confidence` + `confidence_score`; `clinical` has no `chief_complaint` / `key_findings`; `policy` has no `medical_necessity_check`.
- `src/agents/agents.py:204-207` says "AI Never Recommends DENY", but `.github/skills/prior-auth-azure/references/rubric.md:16-31` says the AI **can** recommend DENY at ≥90% confidence NOT_MET. The rubric is the authoritative skill contract; `agents.py` is stale.
- CI (`.github/workflows/main_staging_ci.yml:71-74`) has pytest commented out and references a conda `environment.yaml`. There is no working Python test gate.

**Ground rules for this slice:**
- **This repo uses `uv`, not `pip`.** There is no `pip` and no `ensurepip` on this machine; `uv` (0.9.x) is at `~/.local/bin/uv` and the repo already has a `uv.lock` declaring the project as `source = { virtual = "." }`. Run every Python command through `uv run`, which resolves `.venv` automatically. `.venv/` is already gitignored.
- All commands below use `$REPO` for the working directory. Set it once per shell:
  ```bash
  export REPO=/home/jokarash/dev/Azure-Healthcare-Marketplace-Demo/.worktrees/prior-auth-execution-proof
  ```
  (That is the git worktree on branch `feature/prior-auth-execution-proof`. Do not work in the main checkout.)
- A few **optional** steps import the Microsoft Agent Framework to smoke-test that `prior_auth.py` still loads. That framework lives in a separate virtualenv which exists only in the main checkout, not in this worktree. Set:
  ```bash
  export AGENT_PY=/home/jokarash/dev/Azure-Healthcare-Marketplace-Demo/src/agents/.venv/bin/python
  ```
  Running `cd "$REPO"/src && "$AGENT_PY" ...` uses the main venv's *packages* while importing the *worktree's* source, which is what we want. **Known pre-existing breakage:** that venv is currently stale — importing `agents.workflows.prior_auth` fails with `ImportError: cannot import name 'AzureOpenAIResponsesClient' from 'agent_framework.azure'`. This predates this plan and is not something you introduced. Expect those optional steps to fail, note it in your report, and move on. The `uv run pytest` unit tests are always the gate.
- No live LLM calls. No running MCP servers. Every test added here must pass on a clean checkout with only the `dev` dependency group synced.
- Do not restructure `prior_auth.py` beyond extracting the two seams named in Tasks 2–4. It is 1,351 lines and a broader split is a separate plan.
- Run `ruff check .` before every commit. Line length 120, target py39 — so **no `match` statements and no `X | Y` unions in new runtime code paths that must import under 3.9**; the repo already uses `dict | None` in `prior_auth.py`, which works because of `from __future__ import annotations`-style deferred evaluation in annotations only. In new modules, add `from __future__ import annotations` at the top and you can use `X | None` freely in annotations.

---

## File Structure

**Create:**
- `pyproject.toml` — add a PEP 735 `[dependency-groups]` dev group; stop collecting tests from `src`
- `src/agents/workflows/parsing.py` — pure functions for turning agent text into dicts. No I/O, no framework imports, no logging side effects. Importable without `agent_framework` installed.
- `src/agents/workflows/assessment_schema.py` — the single source of truth for assessment shape. Pure. Importable standalone.
- `tests/unit/__init__.py`
- `tests/unit/test_parsing.py` — deterministic tests for `parsing.py`
- `tests/unit/test_assessment_schema.py` — deterministic tests for `assessment_schema.py`
- `tests/unit/fixtures/__init__.py`
- `tests/unit/fixtures/concurrent_outputs.py` — realistic captured agent-output strings
- `data/sample_cases/prior_auth_baseline/pa_request.json` — the sample input `main.py` already expects

**Modify:**
- `pyproject.toml:49` — `testpaths` must stop collecting `src`
- `src/agents/workflows/prior_auth.py:208-237` — `_extract_json_from_text` delegates to `parsing.py`
- `src/agents/workflows/prior_auth.py:730-738` — replace the `find("}")` heuristic
- `src/agents/agents.py:204-207, 599-600, 607` — align DENY policy with the rubric
- `tests/eval/prior_auth_eval.py:78-92` — import schema constants from `assessment_schema.py` instead of redefining them
- `data/cases/001/a/waypoints/assessment.json` — make it schema-valid
- `Makefile` — add `eval-prior-auth` and `test-unit` targets
- `.github/workflows/main_staging_ci.yml` — add a real Python unit-test + eval job

**Why these boundaries:** `parsing.py` and `assessment_schema.py` are pure and dependency-free, so they are testable without the agent framework, Azure credentials, or MCP servers — which is exactly what makes this slice provable offline. `assessment_schema.py` lives in `src/agents/workflows/` rather than `tests/` because the *workflow* must validate its own output; the eval harness is a consumer, not the owner.

---

### Task 1: Make the test suite runnable

Nothing else in this plan can be verified until `pytest` runs. Do this first.

**Files:**
- Modify: `pyproject.toml` (add `[dependency-groups]`, fix `testpaths`)
- Modify: `uv.lock` (regenerated by `uv sync`)

- [ ] **Step 1: Confirm the current failure**

Run:
```bash
cd "$REPO" && uv run pytest --version 2>&1 | tail -3
```
Expected: a `pytest` failure — the environment has no pytest yet. (`python3 -m pytest` reports `No module named pytest`; there is no `pip` or `ensurepip` on this machine, which is why every command in this plan goes through `uv`.)

- [ ] **Step 2: Add the dev dependency group**

Append to the end of `pyproject.toml`:

```toml
# ── Dev / test dependency group (PEP 735) ──────────────────────────────────
# Deliberately minimal: the root unit suite must resolve and run without
# Azure SDKs, the Microsoft Agent Framework, or any running MCP server.
#
# Sync with:  uv sync --group dev
[dependency-groups]
dev = [
    "pytest>=8.0.0",
    "httpx>=0.27.0",
    "ruff>=0.6.0",
]
```

`httpx` is included because `tests/conftest.py` imports it at module scope for the MCP integration fixtures; without it, collection of the whole `tests/` tree fails even for unit tests. `ruff` is already the repo's configured linter (`[tool.ruff]` is in this same file) but was never declared as a dependency.

- [ ] **Step 3: Sync the environment**

Run:
```bash
cd "$REPO" && uv sync --group dev 2>&1 | tail -8
```
Expected: uv creates `.venv` and installs `pytest`, `httpx`, `ruff`, `rich` and their transitive deps. `.venv/` is already gitignored. `uv.lock` is updated in place — commit it.

- [ ] **Step 4: Confirm collection is broken for the right reason**

Run:
```bash
cd "$REPO" && uv run pytest --collect-only -q 2>&1 | tail -5
```
Expected: a large number of collected items and/or collection errors originating from paths containing `.python_packages` — pytest is walking the vendored Azure Functions dependencies under `src/`.

- [ ] **Step 5: Restrict testpaths**

In `pyproject.toml`, replace:

```toml
testpaths = ["tests", "src"]
```

with:

```toml
testpaths = ["tests"]
norecursedirs = [".git", ".venv", "node_modules", ".python_packages", ".runs", "__pycache__"]
```

`src/` is excluded because it contains no first-party tests — only vendored third-party packages under `src/mcp-servers/*/.python_packages/`. `norecursedirs` is belt-and-braces for anyone who re-adds `src` later.

- [ ] **Step 6: Verify the existing eval tests now pass**

Run:
```bash
cd "$REPO" && uv run pytest tests/eval -q
```
Expected: all tests in `tests/eval/test_prior_auth_eval.py` PASS, 0 errors. If any fail, fix the *test* only if it is a genuine environment issue (e.g. a missing `__init__.py`); do not change eval scoring logic in this task.

- [ ] **Step 7: Verify integration tests are collected but not run**

Run:
```bash
cd "$REPO" && uv run pytest -q -m "not integration" 2>&1 | tail -5
```
Expected: PASS with the integration tests deselected. This is the command CI will use.

- [ ] **Step 8: Commit**

```bash
cd "$REPO"
git add pyproject.toml uv.lock
git commit -m "test: make the root pytest suite runnable

Declare a PEP 735 dev dependency group (pytest, httpx, ruff) and stop
collecting tests from src/, which contains vendored Azure Functions
dependencies rather than first-party tests. The eval suite has never
been executable in this repo.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
Copilot-Session: 1abce17c-0b68-47a7-9a9d-bcebbc0170e1"
```

---

### Task 2: Extract JSON parsing into a testable pure module

**Files:**
- Create: `src/agents/workflows/parsing.py`
- Create: `tests/unit/__init__.py`, `tests/unit/test_parsing.py`
- Test: `tests/unit/test_parsing.py`

- [ ] **Step 1: Create the test package marker**

Create `tests/unit/__init__.py` with a single line:

```python
"""Deterministic unit tests — no LLM, no MCP servers, no Azure credentials."""
```

- [ ] **Step 2: Write the failing test**

Create `tests/unit/test_parsing.py`:

```python
"""Unit tests for agent-output parsing helpers.

These tests are fully deterministic: they exercise pure functions over
literal strings. No LLM, no MCP server, no Azure credential is required.
"""

import pytest

from agents.workflows.parsing import extract_json_from_text


class TestExtractJsonFromText:
    def test_parses_bare_json_object(self):
        assert extract_json_from_text('{"a": 1}') == {"a": 1}

    def test_parses_json_inside_fenced_block(self):
        text = 'Here is my analysis:\n```json\n{"a": 1}\n```\nDone.'
        assert extract_json_from_text(text) == {"a": 1}

    def test_parses_json_inside_unlabelled_fence(self):
        text = '```\n{"a": 1}\n```'
        assert extract_json_from_text(text) == {"a": 1}

    def test_parses_json_embedded_in_prose(self):
        text = 'The result is {"decision": "PEND"} per policy.'
        assert extract_json_from_text(text) == {"decision": "PEND"}

    def test_handles_nested_objects(self):
        text = 'Result: {"outer": {"inner": {"deep": true}}} end'
        assert extract_json_from_text(text) == {"outer": {"inner": {"deep": True}}}

    def test_ignores_braces_inside_string_literals(self):
        text = '{"note": "a } brace in a string", "ok": true}'
        assert extract_json_from_text(text) == {"note": "a } brace in a string", "ok": True}

    def test_returns_none_for_prose_without_json(self):
        assert extract_json_from_text("No structured output was produced.") is None

    def test_returns_none_for_unbalanced_braces(self):
        assert extract_json_from_text('{"a": 1') is None

    def test_returns_none_for_empty_string(self):
        assert extract_json_from_text("") is None

    @pytest.mark.parametrize("bad", [None, 123, [], {}])
    def test_returns_none_for_non_string_input(self, bad):
        assert extract_json_from_text(bad) is None

    def test_returns_first_object_when_several_present(self):
        text = '{"first": 1}\n{"second": 2}'
        assert extract_json_from_text(text) == {"first": 1}
```

- [ ] **Step 3: Run the test to verify it fails**

Run:
```bash
cd "$REPO" && PYTHONPATH=src uv run pytest tests/unit/test_parsing.py -q 2>&1 | tail -5
```
Expected: collection ERROR — `ModuleNotFoundError: No module named 'agents.workflows.parsing'`.

- [ ] **Step 4: Write the implementation**

Create `src/agents/workflows/parsing.py`:

```python
"""Pure helpers for turning free-form agent text into structured data.

This module is deliberately dependency-free: no agent framework, no Azure
SDK, no logging side effects, no file I/O. That makes the riskiest seam in
the workflow — the boundary where LLM text becomes workflow state — fully
testable offline.
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterator

_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.DOTALL)


def iter_json_objects(text: str) -> Iterator[dict[str, Any]]:
    """Yield every top-level JSON object found in ``text``, in order.

    Scans for balanced ``{...}`` spans while tracking string literals and
    backslash escapes, so braces inside JSON strings never affect nesting
    depth. Spans that are balanced but not valid JSON are skipped.
    """
    if not isinstance(text, str):
        return

    depth = 0
    start = -1
    in_string = False
    escaped = False

    for i, ch in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth == 0:
                continue
            depth -= 1
            if depth == 0 and start >= 0:
                candidate = text[start : i + 1]
                start = -1
                try:
                    parsed = json.loads(candidate)
                except json.JSONDecodeError:
                    continue
                if isinstance(parsed, dict):
                    yield parsed


def extract_json_from_text(text: str) -> dict[str, Any] | None:
    """Return the first JSON object in ``text``, or ``None``.

    Tries, in order: the whole string as JSON, the contents of a fenced code
    block, then the first balanced brace span anywhere in the text.
    """
    if not isinstance(text, str) or not text:
        return None

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass

    for match in _FENCE_RE.finditer(text):
        try:
            parsed = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed

    for obj in iter_json_objects(text):
        return obj

    return None
```

- [ ] **Step 5: Run the test to verify it passes**

Run:
```bash
cd "$REPO" && PYTHONPATH=src uv run pytest tests/unit/test_parsing.py -q 2>&1 | tail -5
```
Expected: `14 passed` (10 test methods, one of which is parametrized over 4 inputs).

- [ ] **Step 6: Make `PYTHONPATH=src` unnecessary**

Append to `[tool.pytest.ini_options]` in `pyproject.toml`, directly after the `norecursedirs` line added in Task 1:

```toml
pythonpath = ["src"]
```

- [ ] **Step 7: Verify it works without the env var**

Run:
```bash
cd "$REPO" && uv run pytest tests/unit/test_parsing.py -q 2>&1 | tail -3
```
Expected: `14 passed`.

- [ ] **Step 8: Lint and commit**

```bash
cd "$REPO"
uv run ruff check src/agents/workflows/parsing.py tests/unit/
git add src/agents/workflows/parsing.py tests/unit/__init__.py tests/unit/test_parsing.py pyproject.toml
git commit -m "feat: extract agent-output JSON parsing into a pure tested module

The workflow's LLM-text-to-state boundary had no tests. parsing.py is
dependency-free and string-literal aware, so braces inside JSON strings
no longer corrupt brace-depth tracking.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
Copilot-Session: 1abce17c-0b68-47a7-9a9d-bcebbc0170e1"
```

---

### Task 3: Replace the `find("}")` concurrent-output split

This is the highest-value bug fix in the plan. Read the "The problem this plan fixes" note in the Context section before starting.

**Files:**
- Create: `tests/unit/fixtures/__init__.py`, `tests/unit/fixtures/concurrent_outputs.py`
- Modify: `src/agents/workflows/parsing.py` (add `split_concurrent_outputs`)
- Modify: `tests/unit/test_parsing.py` (add a test class)

- [ ] **Step 1: Create the fixtures package**

Create `tests/unit/fixtures/__init__.py`:

```python
"""Literal agent-output samples used by deterministic unit tests."""
```

- [ ] **Step 2: Create the fixture data**

Create `tests/unit/fixtures/concurrent_outputs.py`:

```python
"""Representative ConcurrentBuilder output strings for bead 002.

Bead 002 runs ClinicalReviewer and CoverageAgent concurrently; the framework
returns the two agents' outputs as one concatenated string. These literals
capture the shapes that string takes in practice, including the nested-object
case that defeats a naive ``text.find("}")`` split.
"""

CLINICAL_JSON = """{
  "clinical_summary": {
    "primary_diagnosis": "Crohn's disease",
    "clinical_indicators": ["hematochezia", "Hgb 9.0"],
    "treatment_history": "Methylprednisolone 40mg daily, inadequate response"
  },
  "clinical_confidence": 88,
  "evidence_mapping": [
    {"criterion": "2.A.i age >= 6", "status": "MET", "evidence": "10 years old", "confidence": 95}
  ],
  "literature_support": [{"pmid": "32783974", "title": "Biologics in pediatric IBD"}]
}"""

COVERAGE_JSON = """{
  "coverage_status": "COVERED_WITH_CRITERIA",
  "applicable_policies": [
    {
      "policy_id": "Cigna-Adalimumab-Products-PA-Policy",
      "title": "Inflammatory Conditions - Adalimumab Products",
      "type": "Commercial",
      "coverage_criteria": ["Age >= 6", "Corticosteroid trial"]
    }
  ],
  "medical_necessity": {
    "is_medically_necessary": true,
    "rationale": "Steroid-refractory Crohn's disease meets Section 2.A"
  }
}"""

# Both agents' JSON, back to back. This is the common real-world shape and the
# one the old find("}") heuristic gets wrong: the first "}" closes
# clinical_summary, not the clinical object.
CONCATENATED_PLAIN = CLINICAL_JSON + "\n" + COVERAGE_JSON

# Same, but each agent wrapped its output in a fenced code block and added prose.
CONCATENATED_FENCED = (
    "ClinicalReviewer:\n```json\n"
    + CLINICAL_JSON
    + "\n```\n\nCoverageAgent:\n```json\n"
    + COVERAGE_JSON
    + "\n```\n"
)

# Degenerate case: one agent merged both payloads into a single object.
MERGED_SINGLE_OBJECT = """{
  "clinical_summary": {"primary_diagnosis": "Crohn's disease", "clinical_indicators": []},
  "clinical_confidence": 80,
  "coverage_status": "COVERED_WITH_CRITERIA",
  "applicable_policies": [{"policy_id": "P-1", "title": "Policy One", "coverage_criteria": []}],
  "medical_necessity": {"is_medically_necessary": true, "rationale": "Meets criteria"}
}"""

# Degenerate case: the coverage agent failed and emitted prose only.
CLINICAL_ONLY = CLINICAL_JSON + "\n\nCoverageAgent: unable to reach the policy service."
```

- [ ] **Step 3: Write the failing test**

Append to `tests/unit/test_parsing.py` (add `split_concurrent_outputs` to the existing import line so it reads
`from agents.workflows.parsing import extract_json_from_text, split_concurrent_outputs`):

```python
class TestSplitConcurrentOutputs:
    def test_splits_two_plain_concatenated_objects(self):
        from tests.unit.fixtures import concurrent_outputs as fx

        clinical, coverage = split_concurrent_outputs(
            fx.CONCATENATED_PLAIN,
            first_marker="clinical_summary",
            second_marker="applicable_policies",
        )
        assert clinical is not None
        assert clinical["clinical_summary"]["primary_diagnosis"] == "Crohn's disease"
        assert coverage is not None
        assert coverage["applicable_policies"][0]["policy_id"] == "Cigna-Adalimumab-Products-PA-Policy"

    def test_splits_fenced_outputs(self):
        from tests.unit.fixtures import concurrent_outputs as fx

        clinical, coverage = split_concurrent_outputs(
            fx.CONCATENATED_FENCED,
            first_marker="clinical_summary",
            second_marker="applicable_policies",
        )
        assert clinical is not None and "clinical_summary" in clinical
        assert coverage is not None and "applicable_policies" in coverage

    def test_returns_same_object_twice_when_merged(self):
        from tests.unit.fixtures import concurrent_outputs as fx

        clinical, coverage = split_concurrent_outputs(
            fx.MERGED_SINGLE_OBJECT,
            first_marker="clinical_summary",
            second_marker="applicable_policies",
        )
        assert clinical is coverage
        assert clinical is not None
        assert clinical["applicable_policies"][0]["policy_id"] == "P-1"

    def test_returns_none_for_missing_second_agent(self):
        from tests.unit.fixtures import concurrent_outputs as fx

        clinical, coverage = split_concurrent_outputs(
            fx.CLINICAL_ONLY,
            first_marker="clinical_summary",
            second_marker="applicable_policies",
        )
        assert clinical is not None and "clinical_summary" in clinical
        assert coverage is None

    def test_order_independent(self):
        """Agents finish concurrently; coverage output may arrive first."""
        from tests.unit.fixtures import concurrent_outputs as fx

        reversed_text = fx.COVERAGE_JSON + "\n" + fx.CLINICAL_JSON
        clinical, coverage = split_concurrent_outputs(
            reversed_text,
            first_marker="clinical_summary",
            second_marker="applicable_policies",
        )
        assert clinical is not None and "clinical_summary" in clinical
        assert coverage is not None and "applicable_policies" in coverage

    def test_returns_none_none_for_prose(self):
        clinical, coverage = split_concurrent_outputs(
            "Both agents failed to produce output.",
            first_marker="clinical_summary",
            second_marker="applicable_policies",
        )
        assert clinical is None
        assert coverage is None
```

- [ ] **Step 4: Run the test to verify it fails**

Run:
```bash
cd "$REPO" && uv run pytest tests/unit/test_parsing.py -q 2>&1 | tail -5
```
Expected: `ImportError: cannot import name 'split_concurrent_outputs' from 'agents.workflows.parsing'`.

- [ ] **Step 5: Write the implementation**

Append to `src/agents/workflows/parsing.py`:

```python
def _iter_all_objects(text: str) -> list[dict[str, Any]]:
    """Collect every JSON object in ``text``, unwrapping fenced blocks first."""
    objects: list[dict[str, Any]] = []
    fences = _FENCE_RE.findall(text) if isinstance(text, str) else []
    for block in fences:
        objects.extend(iter_json_objects(block))
    if objects:
        return objects
    return list(iter_json_objects(text))


def split_concurrent_outputs(
    text: str,
    first_marker: str,
    second_marker: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Split one concatenated concurrent-agent result into two objects.

    ``ConcurrentBuilder`` returns both participants' outputs as a single
    string with no delimiter, and the agents may finish in either order.
    Rather than guessing at offsets, this parses *every* JSON object in the
    text and identifies each participant by a key unique to its schema.

    Returns ``(first, second)``. Either may be ``None`` when that agent
    produced no parseable output. When one object contains both markers
    (an agent merged the payloads), the same object is returned for both.
    """
    objects = _iter_all_objects(text)

    first: dict[str, Any] | None = None
    second: dict[str, Any] | None = None

    for obj in objects:
        has_first = first_marker in obj
        has_second = second_marker in obj
        if has_first and has_second:
            return obj, obj
        if has_first and first is None:
            first = obj
        elif has_second and second is None:
            second = obj

    return first, second
```

- [ ] **Step 6: Run the test to verify it passes**

Run:
```bash
cd "$REPO" && uv run pytest tests/unit/test_parsing.py -q 2>&1 | tail -3
```
Expected: `20 passed` (14 from Task 2, plus 6 new).

- [ ] **Step 7: Rewire `_extract_json_from_text` in the workflow**

In `src/agents/workflows/prior_auth.py`, delete the entire body of `_extract_json_from_text` (lines 208–237, from the `def` through `return None`) and replace it with a delegation:

```python
def _extract_json_from_text(text: str) -> dict | None:
    """Try to extract a JSON object from agent text output.

    Thin wrapper kept for call-site compatibility; the implementation lives
    in ``parsing.py`` so it can be unit tested without the agent framework.
    """
    return extract_json_from_text(text)
```

Then add the import. In the first-party import block (the one starting `from ..agents import (` around line 44), after that block add:

```python
from .parsing import extract_json_from_text, split_concurrent_outputs
```

If `re` is now unused in `prior_auth.py`, ruff will flag it — remove the `import re` line only if ruff reports `F401`.

- [ ] **Step 8: Replace the `find("}")` heuristic**

In `src/agents/workflows/prior_auth.py`, find this block (currently lines 690 and 730–738):

```python
            # --- Parse clinical reviewer output ---
            clinical_parsed = _extract_json_from_text(concurrent_text)
```

and

```python
            # --- Parse coverage agent output ---
            coverage_parsed = None
            if clinical_parsed and "coverage_status" in clinical_parsed:
                coverage_parsed = clinical_parsed
            else:
                first_close = concurrent_text.find("}")
                if first_close > 0:
                    remainder = concurrent_text[first_close + 1 :]
                    coverage_parsed = _extract_json_from_text(remainder)
```

Replace the *first* snippet with:

```python
            # --- Parse both agents' outputs from the concatenated result ---
            # ConcurrentBuilder returns one string containing both agents'
            # JSON in nondeterministic order; identify each by a schema-unique
            # key rather than by offset.
            clinical_parsed, coverage_parsed = split_concurrent_outputs(
                concurrent_text,
                first_marker="clinical_summary",
                second_marker="applicable_policies",
            )
            if clinical_parsed is None:
                logger.warning("Bead 002: no parseable ClinicalReviewer output")
            if coverage_parsed is None:
                logger.warning("Bead 002: no parseable CoverageAgent output")
```

and delete the *second* snippet entirely (the whole `# --- Parse coverage agent output ---` block through the `coverage_parsed = _extract_json_from_text(remainder)` line). Leave the following `if coverage_parsed and "applicable_policies" in coverage_parsed:` block untouched.

- [ ] **Step 9: Verify the module still imports and lints**

Run:
```bash
cd "$REPO" && uv run ruff check src/agents/workflows/ tests/unit/ && uv run pytest tests/unit -q 2>&1 | tail -3
```
Expected: ruff reports `All checks passed!` and pytest reports `20 passed`.

> Note: `uv run python -c "import agents.workflows.prior_auth"` will fail without the agent venv — that is expected and not a regression. Import-check the workflow with the venv instead:
> ```bash
> cd "$REPO"/src && "$AGENT_PY" -c "import agents.workflows.prior_auth; print('ok')"
> ```
> Expected: `ok`. If the venv is missing or broken, note it and move on — the unit tests are the gate for this task.

- [ ] **Step 10: Commit**

```bash
cd "$REPO"
git add src/agents/workflows/parsing.py src/agents/workflows/prior_auth.py tests/unit/
git commit -m "fix: split concurrent agent outputs by schema key, not by brace offset

Bead 002 split the ClinicalReviewer and CoverageAgent results with
text.find('}'), which matches the first nested closing brace and silently
dropped the coverage payload, producing assessments with an empty policy
block. Identify each participant by a schema-unique key instead, and
handle merged, reversed, and single-agent outputs.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
Copilot-Session: 1abce17c-0b68-47a7-9a9d-bcebbc0170e1"
```

---

### Task 4: Create one shared assessment schema contract

Today the assessment shape is asserted only inside the eval harness (`tests/eval/prior_auth_eval.py:78-92`). The workflow that *produces* assessments never checks its own output. This task makes the contract shared and executable.

**Files:**
- Create: `src/agents/workflows/assessment_schema.py`
- Create: `tests/unit/test_assessment_schema.py`
- Modify: `tests/eval/prior_auth_eval.py:78-92`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_assessment_schema.py`:

```python
"""Unit tests for the shared assessment schema contract."""

import copy

import pytest

from agents.workflows.assessment_schema import (
    BEAD_IDS,
    VALID_DECISIONS,
    validate_assessment,
)


def _valid_assessment() -> dict:
    return {
        "request_id": "PA-2026-0001",
        "workflow_id": "wf-abc123",
        "status": "completed",
        "beads": [
            {"id": "bd-pa-001-intake", "status": "completed"},
            {"id": "bd-pa-002-clinical", "status": "completed"},
            {"id": "bd-pa-003-recommend", "status": "completed"},
            {"id": "bd-pa-004-decision", "status": "not-started"},
            {"id": "bd-pa-005-notify", "status": "not-started"},
        ],
        "request": {
            "member": {"patient_id": "MRN 123456"},
            "service": {"name_of_medication_or_procedure": "Adalimumab"},
            "provider": {"npi": "1234567890"},
        },
        "clinical": {
            "chief_complaint": "Crohn's disease",
            "key_findings": ["Hgb 9.0"],
        },
        "policy": {
            "policy_id": "P-1",
            "policy_title": "Adalimumab PA Policy",
            "medical_necessity_check": {"is_covered": True, "policy_basis": "Section 2.A"},
        },
        "recommendation": {
            "decision": "PEND",
            "confidence": {"overall": 53.8},
            "confidence_score": 53.8,
            "rationale": "PA form incomplete.",
        },
    }


class TestValidateAssessment:
    def test_valid_assessment_has_no_errors(self):
        assert validate_assessment(_valid_assessment()) == []

    def test_reports_missing_top_level_keys(self):
        a = _valid_assessment()
        del a["request_id"]
        del a["status"]
        errors = validate_assessment(a)
        assert any("request_id" in e for e in errors)
        assert any("status" in e for e in errors)

    def test_reports_missing_recommendation_keys(self):
        a = _valid_assessment()
        del a["recommendation"]["confidence_score"]
        errors = validate_assessment(a)
        assert any("confidence_score" in e for e in errors)

    @pytest.mark.parametrize("decision", ["APPROVE", "PEND", "DENY"])
    def test_accepts_all_valid_decisions(self, decision):
        a = _valid_assessment()
        a["recommendation"]["decision"] = decision
        assert validate_assessment(a) == []

    def test_rejects_unknown_decision(self):
        a = _valid_assessment()
        a["recommendation"]["decision"] = "MAYBE"
        errors = validate_assessment(a)
        assert any("MAYBE" in e for e in errors)

    def test_rejects_missing_bead(self):
        a = _valid_assessment()
        a["beads"] = a["beads"][:-1]
        errors = validate_assessment(a)
        assert any("bd-pa-005-notify" in e for e in errors)

    def test_rejects_invalid_bead_status(self):
        a = _valid_assessment()
        a["beads"][0]["status"] = "finished"
        errors = validate_assessment(a)
        assert any("finished" in e for e in errors)

    def test_rejects_non_dict_input(self):
        assert validate_assessment("not a dict") != []

    def test_does_not_mutate_input(self):
        a = _valid_assessment()
        before = copy.deepcopy(a)
        validate_assessment(a)
        assert a == before

    def test_bead_ids_are_ordered(self):
        assert BEAD_IDS == [
            "bd-pa-001-intake",
            "bd-pa-002-clinical",
            "bd-pa-003-recommend",
            "bd-pa-004-decision",
            "bd-pa-005-notify",
        ]

    def test_valid_decisions_contract(self):
        assert VALID_DECISIONS == {"APPROVE", "PEND", "DENY"}
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
cd "$REPO" && uv run pytest tests/unit/test_assessment_schema.py -q 2>&1 | tail -5
```
Expected: `ModuleNotFoundError: No module named 'agents.workflows.assessment_schema'`.

- [ ] **Step 3: Write the implementation**

Create `src/agents/workflows/assessment_schema.py`:

```python
"""The prior-auth assessment contract, in one executable place.

The workflow writes assessments and the eval harness scores them; before
this module they each carried their own copy of the expected shape. This is
the single source of truth for both. Pure and dependency-free so it can be
imported by tests without the agent framework.

Mirrors .github/skills/prior-auth-azure/SKILL.md.
"""

from __future__ import annotations

from typing import Any

BEAD_IDS = [
    "bd-pa-001-intake",
    "bd-pa-002-clinical",
    "bd-pa-003-recommend",
    "bd-pa-004-decision",
    "bd-pa-005-notify",
]

VALID_BEAD_STATUSES = {"not-started", "in-progress", "completed", "blocked"}
VALID_DECISIONS = {"APPROVE", "PEND", "DENY"}

REQUIRED_TOP_LEVEL_KEYS = {
    "request_id",
    "workflow_id",
    "status",
    "beads",
    "request",
    "clinical",
    "policy",
    "recommendation",
}
REQUIRED_REQUEST_KEYS = {"member", "service", "provider"}
REQUIRED_RECOMMENDATION_KEYS = {"decision", "confidence", "confidence_score", "rationale"}
REQUIRED_POLICY_KEYS = {"policy_id", "policy_title", "medical_necessity_check"}
REQUIRED_CLINICAL_KEYS = {"chief_complaint", "key_findings"}


def _missing(container: Any, required: set[str], label: str) -> list[str]:
    if not isinstance(container, dict):
        return [f"{label}: expected an object, got {type(container).__name__}"]
    return [f"{label}: missing required key '{k}'" for k in sorted(required) if k not in container]


def validate_assessment(assessment: Any) -> list[str]:
    """Return a list of human-readable contract violations. Empty means valid.

    Never raises and never mutates ``assessment``.
    """
    if not isinstance(assessment, dict):
        return [f"assessment: expected an object, got {type(assessment).__name__}"]

    errors: list[str] = []
    errors += _missing(assessment, REQUIRED_TOP_LEVEL_KEYS, "assessment")
    errors += _missing(assessment.get("request"), REQUIRED_REQUEST_KEYS, "request")
    errors += _missing(assessment.get("clinical"), REQUIRED_CLINICAL_KEYS, "clinical")
    errors += _missing(assessment.get("policy"), REQUIRED_POLICY_KEYS, "policy")
    errors += _missing(assessment.get("recommendation"), REQUIRED_RECOMMENDATION_KEYS, "recommendation")

    rec = assessment.get("recommendation")
    if isinstance(rec, dict) and "decision" in rec:
        decision = str(rec.get("decision", "")).upper()
        if decision not in VALID_DECISIONS:
            errors.append(f"recommendation.decision: '{decision}' is not one of {sorted(VALID_DECISIONS)}")

    beads = assessment.get("beads")
    if not isinstance(beads, list):
        errors.append("beads: expected a list")
    else:
        by_id = {b.get("id"): b for b in beads if isinstance(b, dict)}
        for bead_id in BEAD_IDS:
            bead = by_id.get(bead_id)
            if bead is None:
                errors.append(f"beads: missing bead '{bead_id}'")
                continue
            status = bead.get("status")
            if status not in VALID_BEAD_STATUSES:
                errors.append(
                    f"beads.{bead_id}.status: '{status}' is not one of {sorted(VALID_BEAD_STATUSES)}"
                )

    return errors
```

- [ ] **Step 4: Run the test to verify it passes**

Run:
```bash
cd "$REPO" && uv run pytest tests/unit/test_assessment_schema.py -q 2>&1 | tail -3
```
Expected: `13 passed`.

- [ ] **Step 5: Make the eval harness consume the shared contract**

In `tests/eval/prior_auth_eval.py`, delete the local constant definitions in the "Assessment schema contract" section (lines 78–92: `REQUIRED_TOP_LEVEL_KEYS` through `REQUIRED_CLINICAL_KEYS`) and replace that whole block with:

```python
# ============================================================================
# Assessment schema contract — owned by the workflow, consumed here
# ============================================================================

from agents.workflows.assessment_schema import (  # noqa: E402
    REQUIRED_CLINICAL_KEYS,
    REQUIRED_POLICY_KEYS,
    REQUIRED_RECOMMENDATION_KEYS,
    REQUIRED_REQUEST_KEYS,
    REQUIRED_TOP_LEVEL_KEYS,
    VALID_DECISIONS,
)
```

Do not change `evaluate_schema`, `evaluate_beads`, `evaluate_decision`, or `compute_fidelity_score` — the constants have identical values, so behaviour is unchanged.

- [ ] **Step 6: Put `src/` on the path for the standalone CLI runner**

`tests/eval/prior_auth_eval.py` now imports from `agents.workflows`, which lives under `src/`. Pytest finds it via the `pythonpath = ["src"]` setting from Task 2, but `scripts/eval_prior_auth.py` runs as a plain script and only inserts the repo root:

```python
# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
```

Without this fix, `make eval-prior-auth` and the CI job in Task 8 both fail with `ModuleNotFoundError: No module named 'agents'`. In `scripts/eval_prior_auth.py`, replace that three-line block with:

```python
# Add project root and src/ to path — the eval harness imports the assessment
# contract from agents.workflows, which lives under src/.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))
```

- [ ] **Step 7: Verify the standalone CLI still runs**

Run:
```bash
cd "$REPO" && uv run python scripts/eval_prior_auth.py --runs-dir data/cases 2>&1 | tail -20
```
Expected: a fidelity report, not a traceback. Case 001_a will still show schema failures at this point — Task 5 fixes those. The point of this step is only that the import chain works.

- [ ] **Step 8: Verify the eval tests still pass**

Run:
```bash
cd "$REPO" && uv run pytest tests/eval tests/unit -q 2>&1 | tail -3
```
Expected: all PASS, no errors. If the import fails, confirm `pythonpath = ["src"]` from Task 2 Step 6 is present in `pyproject.toml`.

- [ ] **Step 9: Lint and commit**

```bash
cd "$REPO"
uv run ruff check src/agents/workflows/assessment_schema.py tests/ scripts/eval_prior_auth.py
git add src/agents/workflows/assessment_schema.py tests/unit/test_assessment_schema.py tests/eval/prior_auth_eval.py scripts/eval_prior_auth.py
git commit -m "refactor: move the assessment schema contract next to the producer

The workflow writes assessments but never validated them; only the eval
harness knew the shape. assessment_schema.validate_assessment() is now
the single executable contract, consumed by both.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
Copilot-Session: 1abce17c-0b68-47a7-9a9d-bcebbc0170e1"
```

---

### Task 5: Make the golden case assessment schema-valid

`data/cases/001/a/waypoints/assessment.json` is the only committed evaluation evidence in the repo, and it violates the contract. Until it is valid, the eval harness scores the repo's own reference output as broken.

**Files:**
- Modify: `data/cases/001/a/waypoints/assessment.json`
- Create: `tests/unit/test_golden_case.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_golden_case.py`:

```python
"""The committed reference assessment must satisfy the schema contract.

data/cases/001/a is the repo's only golden prior-auth output. If it drifts
from the contract, every downstream eval number is meaningless.
"""

import json
from pathlib import Path

from agents.workflows.assessment_schema import validate_assessment

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN = REPO_ROOT / "data" / "cases" / "001" / "a" / "waypoints" / "assessment.json"


def test_golden_assessment_file_exists():
    assert GOLDEN.exists(), f"missing golden assessment: {GOLDEN}"


def test_golden_assessment_is_valid_json():
    json.loads(GOLDEN.read_text())


def test_golden_assessment_satisfies_schema():
    assessment = json.loads(GOLDEN.read_text())
    errors = validate_assessment(assessment)
    assert errors == [], "golden assessment violates the contract:\n  " + "\n  ".join(errors)


def test_golden_assessment_matches_ground_truth_shape():
    """Ground truth for 001_a is 'rejected'; a PEND or DENY is consistent."""
    assessment = json.loads(GOLDEN.read_text())
    ground_truth = json.loads((REPO_ROOT / "data" / "cases" / "ground_truth.json").read_text())
    assert ground_truth["001_a"]["decision"] == "rejected"
    assert assessment["recommendation"]["decision"] in ("PEND", "DENY")
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
cd "$REPO" && uv run pytest tests/unit/test_golden_case.py -q 2>&1 | tail -20
```
Expected: `test_golden_assessment_satisfies_schema` FAILS, listing missing `request_id`, `workflow_id`, `status`; `clinical` missing `chief_complaint` and `key_findings`; `policy` missing `medical_necessity_check`; `recommendation` missing `confidence` and `confidence_score`.

- [ ] **Step 3: Add the missing top-level keys**

In `data/cases/001/a/waypoints/assessment.json`, the file currently opens with `{\n  "beads": [`. Insert three keys before `"beads"` so the file starts:

```json
{
  "request_id": "CASE-001-A",
  "workflow_id": "case-001-a-reference",
  "status": "awaiting-human-decision",
  "beads": [
```

`status` is `awaiting-human-decision` because beads 001–003 are `completed` while 004 and 005 are `not-started` — the run stopped at the human gate, which is exactly what a PEND means.

- [ ] **Step 4: Add the required clinical keys**

In the same file, the `"clinical"` object currently begins with `"diagnosis": "Crohn's disease (IBD) — ...`. Insert two keys immediately after the opening `"clinical": {`, before `"diagnosis"`:

```json
  "clinical": {
    "chief_complaint": "Steroid-refractory Crohn's disease with hematochezia and symptomatic anemia",
    "key_findings": [
      "Hgb 9.0 (LOW), Hct 32%, MCV 78 — microcytic anemia requiring pRBC transfusion",
      "ESR 30, CRP 25, fecal calprotectin 150 — active inflammation",
      "Colonoscopy: ileal ulceration with segmental strictures, colonic cobblestoning, aphthous ulcers with skip areas",
      "Methylprednisolone 40mg daily with inadequate response — ongoing hematochezia x3 overnight",
      "HR 110 with pallor and dizziness — hemodynamically significant anemia"
    ],
    "diagnosis": "Crohn's disease (IBD) — ileal and colonic involvement with strictures, cobblestoning, aphthous ulcers",
```

Leave the rest of the `clinical` object exactly as it is.

- [ ] **Step 5: Add the required policy key**

In the `"policy"` object, after the existing `"approval_duration": "6 months (initial therapy)"` line, add a comma and then:

```json
    "medical_necessity_check": {
      "is_covered": true,
      "policy_basis": "Section 2.A — patient is >= 6 years old and is currently taking corticosteroids with inadequate response, satisfying criterion 2.A.ii(a). Criterion 2.A.iii (gastroenterologist involvement) is INSUFFICIENT because the PA form does not identify a prescribing physician.",
      "criteria_met_count": 2,
      "criteria_total_count": 3
    }
```

- [ ] **Step 6: Add the required recommendation keys**

In the `"recommendation"` object, rename `"confidence_scores"` to `"confidence"` and add a flat `"confidence_score"` alongside it. The block currently reads `"confidence_scores": {` — change it to `"confidence": {`, and immediately after that object's closing `},` add:

```json
    "confidence_score": 53.8,
```

The eval harness reads `confidence_score` as a flat number for threshold comparison and `confidence` as the per-dimension breakdown; both are required by the contract.

- [ ] **Step 7: Run the test to verify it passes**

Run:
```bash
cd "$REPO" && uv run pytest tests/unit/test_golden_case.py -q 2>&1 | tail -5
```
Expected: `4 passed`. If JSON parsing fails, run `python3 -m json.tool data/cases/001/a/waypoints/assessment.json > /dev/null` to locate the syntax error (usually a missing or extra comma from Steps 5–6).

- [ ] **Step 8: Confirm the eval harness now scores it**

Run:
```bash
cd "$REPO" && uv run python scripts/eval_prior_auth.py --runs-dir data/cases 2>&1 | tail -30
```
Expected: case `001_a` reports a valid schema and a decision match against ground truth `rejected`. Record the fidelity score in the commit message — this is the first real baseline number the repo has.

- [ ] **Step 9: Commit**

```bash
cd "$REPO"
git add data/cases/001/a/waypoints/assessment.json tests/unit/test_golden_case.py
git commit -m "fix: make the golden case-001-a assessment satisfy the schema contract

The repo's only committed reference assessment was missing request_id,
workflow_id, status, clinical.chief_complaint, clinical.key_findings,
policy.medical_necessity_check, and a flat recommendation.confidence_score.
Add a regression test so it cannot drift again.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
Copilot-Session: 1abce17c-0b68-47a7-9a9d-bcebbc0170e1"
```

---

### Task 6: Create the missing sample input

`src/agents/main.py:37` points `--demo` at a file that does not exist, so demo runs silently fall back to a hardcoded dict. Anyone reading the code reasonably assumes the sample file is the source of truth.

**Files:**
- Create: `data/sample_cases/prior_auth_baseline/pa_request.json`
- Create: `tests/unit/test_sample_inputs.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_sample_inputs.py`:

```python
"""Every path in main.SAMPLE_DATA must resolve to a real, well-formed file."""

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PRIOR_AUTH_SAMPLE = REPO_ROOT / "data" / "sample_cases" / "prior_auth_baseline" / "pa_request.json"


def test_prior_auth_sample_exists():
    assert PRIOR_AUTH_SAMPLE.exists(), (
        f"src/agents/main.py references {PRIOR_AUTH_SAMPLE.relative_to(REPO_ROOT)} but it is missing"
    )


def test_prior_auth_sample_has_required_sections():
    data = json.loads(PRIOR_AUTH_SAMPLE.read_text())
    for key in ("request_id", "member", "provider", "service"):
        assert key in data, f"sample request missing '{key}'"


def test_prior_auth_sample_uses_the_demo_npi():
    """NPI 1234567890 is the demo sentinel that skips live NPI lookup."""
    data = json.loads(PRIOR_AUTH_SAMPLE.read_text())
    assert data["provider"]["npi"] == "1234567890"


def test_prior_auth_sample_contains_no_real_identifiers():
    raw = PRIOR_AUTH_SAMPLE.read_text()
    assert "SYNTHETIC" in raw or "synthetic" in raw, "sample data must be labelled synthetic"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
cd "$REPO" && uv run pytest tests/unit/test_sample_inputs.py -q 2>&1 | tail -5
```
Expected: 4 failures, the first being the missing-file assertion.

- [ ] **Step 3: Create the sample input**

Create `data/sample_cases/prior_auth_baseline/pa_request.json`:

```json
{
  "request_id": "PA-BASELINE-0001",
  "data_classification": "SYNTHETIC — no real patient or provider data",
  "submitted_at": "2026-07-28T00:00:00Z",
  "member": {
    "patient_name": "Jordan Sample",
    "patient_id": "MRN-000-BASELINE",
    "patient_date_of_birth": "2014-10-19",
    "patient_age": "11 years",
    "patient_sex": "Female",
    "plan_id": "PLAN-COMMERCIAL-001"
  },
  "provider": {
    "physician_name": "Dr. Alex Sample",
    "npi": "1234567890",
    "specialty": "Pediatric Gastroenterology",
    "state": "WA",
    "physician_contact": {
      "office_phone": "555-0100",
      "fax": "555-0101"
    }
  },
  "service": {
    "name_of_medication_or_procedure": "Adalimumab (Humira)",
    "code_of_medication_or_procedure": "J0135",
    "code_system": "HCPCS",
    "dosage": "40 mg subcutaneous every other week after induction",
    "duration": "6 months",
    "urgency": "standard",
    "rationale": "Initiation of biologic therapy for moderate-to-severe Crohn's disease refractory to corticosteroid therapy"
  },
  "diagnosis": {
    "icd10_codes": ["K50.80"],
    "primary_diagnosis": "Crohn's disease of both small and large intestine, without complications"
  },
  "clinical_summary": "11-year-old with biopsy-supported Crohn's disease. Currently on methylprednisolone 40 mg daily with inadequate response: ongoing hematochezia, abdominal cramping, and worsening microcytic anemia (Hgb 9.0) requiring transfusion. Colonoscopy shows ileal ulceration with segmental strictures and colonic cobblestoning with skip areas.",
  "prior_treatments": [
    {
      "treatment": "Methylprednisolone 40 mg daily",
      "duration": "6 weeks",
      "outcome": "Inadequate response — persistent bleeding and anemia"
    }
  ],
  "supporting_evidence": {
    "labs": {
      "hemoglobin": 9.0,
      "hematocrit": 32,
      "esr": 30,
      "crp": 25,
      "fecal_calprotectin": 150
    },
    "imaging": "MR enterography pending; colonoscopy and EGD completed with biopsies"
  }
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run:
```bash
cd "$REPO" && uv run pytest tests/unit/test_sample_inputs.py -q 2>&1 | tail -3
```
Expected: `4 passed`.

- [ ] **Step 5: Confirm `--demo` now loads the file rather than the fallback**

Run:
```bash
cd "$REPO"/src && "$AGENT_PY" -c "
import argparse, json
from agents.main import load_input
args = argparse.Namespace(demo=True, workflow='prior-auth', input=None)
data = load_input(args)
print('request_id =', data.get('request_id'))
"
```
Expected: `request_id = PA-BASELINE-0001`. If the agent venv is unavailable, skip this step and note it — the unit tests are the gate.

- [ ] **Step 6: Commit**

```bash
cd "$REPO"
git add data/sample_cases/prior_auth_baseline/pa_request.json tests/unit/test_sample_inputs.py
git commit -m "feat: add the prior-auth baseline sample input main.py already expects

src/agents/main.py:37 pointed --demo at a nonexistent file, so demo runs
silently used a hardcoded fallback dict. Add the synthetic sample and a
test that keeps SAMPLE_DATA paths honest.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
Copilot-Session: 1abce17c-0b68-47a7-9a9d-bcebbc0170e1"
```

---

### Task 7: Resolve the DENY policy contradiction

`src/agents/agents.py` tells the synthesis agent it may never recommend DENY. `.github/skills/prior-auth-azure/references/rubric.md` says it may, at ≥90% confidence NOT_MET, with the human confirming in Subskill 2. The rubric is the authoritative skill contract and carries the fuller reasoning (`INSUFFICIENT` → PEND vs. `NOT_MET` → DENY); the agent instructions are stale. Align the code to the rubric.

**Files:**
- Modify: `src/agents/agents.py:204-207, 599-600, 607`
- Create: `tests/unit/test_agent_instructions.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_agent_instructions.py`:

```python
"""Agent instructions must not contradict the authoritative skill rubric.

The rubric (.github/skills/prior-auth-azure/references/rubric.md) permits an
AI DENY recommendation when a mandatory criterion is NOT_MET at >= 90%
confidence, with the human confirming in Subskill 2. These tests keep the
prompt text and the rubric from drifting apart again.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_PY = REPO_ROOT / "src" / "agents" / "agents.py"
RUBRIC = REPO_ROOT / ".github" / "skills" / "prior-auth-azure" / "references" / "rubric.md"


def test_rubric_permits_ai_deny():
    text = RUBRIC.read_text()
    assert "The AI **can** recommend DENY" in text


def test_agent_instructions_do_not_forbid_deny():
    text = AGENTS_PY.read_text()
    forbidden = [
        "AI Never Recommends DENY",
        "You may ONLY recommend **APPROVE** or **PEND**",
        "never DENY",
    ]
    found = [phrase for phrase in forbidden if phrase in text]
    assert not found, f"agents.py contradicts the rubric: {found}"


def test_agent_instructions_describe_the_deny_condition():
    text = AGENTS_PY.read_text()
    assert "NOT_MET" in text, "agents.py must explain the NOT_MET vs INSUFFICIENT distinction"
    assert "INSUFFICIENT" in text
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
cd "$REPO" && uv run pytest tests/unit/test_agent_instructions.py -q 2>&1 | tail -10
```
Expected: `test_agent_instructions_do_not_forbid_deny` FAILS listing all three forbidden phrases.

- [ ] **Step 3: Update the synthesis agent decision rules**

In `src/agents/agents.py`, replace lines 204–207:

```
### CRITICAL: AI Never Recommends DENY
- You may ONLY recommend **APPROVE** or **PEND**.
- If criteria are clearly not met, recommend PEND with explanation.
- Denial is a human-only decision.
```

with:

```
### DENY Recommendations (NOT_MET vs INSUFFICIENT)
- You may recommend **APPROVE**, **PEND**, or **DENY**.
- Recommend **DENY** only when ALL of the following hold:
  1. At least one **mandatory** policy criterion has status `NOT_MET` (not `INSUFFICIENT`)
  2. That NOT_MET assessment carries confidence >= 90%
  3. The evidence is a documented clinical fact, not an absence of documentation
- `NOT_MET` = the record affirmatively shows the criterion is violated -> DENY candidate.
- `INSUFFICIENT` = we lack the information to decide -> **PEND** and request it.
- A DENY is still a recommendation. The human reviewer confirms, overrides, or
  downgrades it to PEND in Subskill 2. Final denial authority is always human.
```

- [ ] **Step 4: Update the evaluation order**

In the same file, replace line 201:

```
4. Clinical Criteria: ≥80% MET → APPROVE; 60-79% → PEND; <60% → PEND
```

with:

```
4. Clinical Criteria: check NOT_MET blockers first (mandatory NOT_MET at ≥90% → DENY);
   otherwise ≥80% MET → APPROVE; 60-79% → PEND; <60% → PEND
```

- [ ] **Step 5: Update the workflow description block**

In the same file, replace lines 599–600:

```
12. Apply decision rubric: APPROVE if criteria ≥80% MET + confidence ≥60%.
13. AI may only recommend **APPROVE** or **PEND** — never DENY.
```

with:

```
12. Apply decision rubric: APPROVE if criteria ≥80% MET + confidence ≥60%.
13. AI may recommend **APPROVE**, **PEND**, or **DENY**. DENY requires a mandatory
    criterion with status NOT_MET at ≥90% confidence; the human confirms in Subskill 2.
```

- [ ] **Step 6: Update the output-format line**

In the same file, replace line 607:

```
- `recommendation` (APPROVE or PEND), `confidence_score`, `criteria_summary`
```

with:

```
- `recommendation` (APPROVE, PEND, or DENY), `confidence_score`, `criteria_summary`
```

- [ ] **Step 7: Run the test to verify it passes**

Run:
```bash
cd "$REPO" && uv run pytest tests/unit/test_agent_instructions.py -q 2>&1 | tail -3
```
Expected: `3 passed`.

- [ ] **Step 8: Check for any other stale DENY prohibitions**

Run:
```bash
cd "$REPO" && grep -rn "never DENY\|only recommend\|Never Recommends DENY" --include="*.py" --include="*.md" . | grep -v node_modules | grep -v .python_packages
```
Expected: no results outside `docs/superpowers/plans/` (this plan file itself will match, which is fine). If any skill or doc file still forbids DENY, fix it in the same commit.

- [ ] **Step 9: Lint and commit**

```bash
cd "$REPO"
uv run ruff check src/agents/agents.py
git add src/agents/agents.py tests/unit/test_agent_instructions.py
git commit -m "fix: align synthesis agent DENY policy with the authoritative rubric

agents.py told the agent it may never recommend DENY while rubric.md
permits DENY for a mandatory NOT_MET criterion at >=90% confidence. The
prohibition forced clear policy violations to be masked as PEND
information gaps. Align the prompt and add a drift test.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
Copilot-Session: 1abce17c-0b68-47a7-9a9d-bcebbc0170e1"
```

---

### Task 8: Make the proof repeatable — Make targets and CI

**Files:**
- Modify: `Makefile`
- Modify: `.github/workflows/main_staging_ci.yml`

- [ ] **Step 1: Add the Make targets**

In `Makefile`, add `test-unit` and `eval-prior-auth` to the `.PHONY` list on line 5 (append them to the existing space-separated names before the trailing `\`).

Then, immediately after the `eval-contracts:` target block (lines 128–129), add:

```make
test-unit:
	@uv run pytest tests/unit tests/eval -q

eval-prior-auth:
	@uv run python scripts/eval_prior_auth.py --runs-dir data/cases
```

Finally, update the `eval-all` target on line 137 to include the new gate:

```make
eval-all: eval-contracts test-unit eval-prior-auth eval-latency-local eval-native-local
```

- [ ] **Step 2: Verify the targets run**

Run:
```bash
cd "$REPO" && make test-unit && make eval-prior-auth
```
Expected: `make test-unit` reports all tests passing; `make eval-prior-auth` prints the fidelity report for case 001_a. (Do **not** run `make eval-all` — it starts local MCP servers, which is out of scope for this slice.)

- [ ] **Step 3: Add a real CI job**

In `.github/workflows/main_staging_ci.yml`, add this job at the top level of the `jobs:` mapping, immediately before the existing `preview-deployment:` job (line 76). Match the surrounding indentation exactly — job keys sit at two spaces.

```yaml
  python-unit-tests:
    name: Python Unit Tests & Prior-Auth Eval 🧪
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install uv
        uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true

      - name: Sync dev dependencies
        run: uv sync --group dev

      - name: Lint changed source
        run: uv run ruff check src/agents tests scripts

      - name: Run deterministic unit and eval tests
        run: uv run pytest tests/unit tests/eval -q

      - name: Run prior-auth fidelity eval
        run: uv run python scripts/eval_prior_auth.py --runs-dir data/cases

      - name: Validate MCP tool contracts
        run: uv run python scripts/eval_contracts.py
```

This job needs no Azure credentials, no MCP servers, and no LLM — which is the whole point of this slice.

- [ ] **Step 4: Validate the workflow YAML**

Run:
```bash
cd "$REPO" && uv run python -c "
import sys
try:
    import yaml
except ImportError:
    sys.exit('PyYAML not installed; skipping - CI will validate on push')
d = yaml.safe_load(open('.github/workflows/main_staging_ci.yml'))
print('jobs:', list(d['jobs']))
assert 'python-unit-tests' in d['jobs']
print('OK')
"
```
Expected: `OK` with `python-unit-tests` in the job list. If PyYAML is unavailable, the message says so and GitHub will validate on push.

- [ ] **Step 5: Run the full deterministic gate exactly as CI will**

Run:
```bash
cd "$REPO" && \
  uv run ruff check src/agents tests scripts && \
  uv run pytest tests/unit tests/eval -q && \
  uv run python scripts/eval_prior_auth.py --runs-dir data/cases && \
  uv run python scripts/eval_contracts.py
```
Expected: every command exits 0. This is the acceptance gate for the whole plan.

- [ ] **Step 6: Commit**

```bash
cd "$REPO"
git add Makefile .github/workflows/main_staging_ci.yml
git commit -m "ci: gate on deterministic prior-auth unit tests and fidelity eval

Adds make test-unit and make eval-prior-auth, and a CI job that runs ruff,
the unit suite, the prior-auth fidelity eval, and the MCP contract check.
No Azure credentials, MCP servers, or LLM calls required.

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
Copilot-Session: 1abce17c-0b68-47a7-9a9d-bcebbc0170e1"
```

- [ ] **Step 7: Land the plane**

```bash
cd "$REPO"
git pull --rebase
bd sync
git push
git status
```
Expected: `git status` reports the branch is up to date with `origin`. Work is not complete until the push succeeds.

---

## Acceptance Criteria

The slice is done when all of the following are true on a clean checkout:

1. `uv sync --group dev && uv run pytest tests/unit tests/eval -q` passes.
2. Bead 002 correctly recovers **both** the clinical and coverage payloads from a concatenated `ConcurrentBuilder` result in every fixture case, including reversed order, fenced blocks, merged objects, and a missing second agent.
3. `agents.workflows.assessment_schema.validate_assessment()` is the only definition of the assessment contract, and both the workflow module and the eval harness import from it.
4. `data/cases/001/a/waypoints/assessment.json` validates cleanly and produces a recorded fidelity baseline.
5. `data/sample_cases/prior_auth_baseline/pa_request.json` exists and `--demo` loads it instead of the hardcoded fallback.
6. No file in the repo tells the AI it may never recommend DENY.
7. `make test-unit` and `make eval-prior-auth` both exit 0, and CI runs them on every push.

## Explicitly Out of Scope

Filed as follow-on work, not to be attempted in this plan:

- **Live LLM runs.** Proving the agents produce *good* content (as opposed to *well-formed* content) needs Azure OpenAI plus running MCP servers. That is the next plan, and it depends on this one for its assertions.
- **Splitting `prior_auth.py`.** At 1,351 lines it does orchestration, parsing, audit, RAG, and document generation. A decomposition is warranted but is its own plan.
- **The `_record_audit_event` / `_rag_policy_retrieval` raw-httpx bypass.** Both POST JSON-RPC directly to `tool.url` instead of going through the MCP tool abstraction. This is a control-plane concern and belongs with the governance plan.
- **Building `pa_request.json` for the other nine ground-truth cases.** Case sources are PDFs; wiring the existing `document-reader` MCP server into an ingestion path is a meaningful slice on its own.
- **Revisiting `evaluate_decision`'s `rejected → (pend | deny)` mapping.** Letting PEND satisfy a "rejected" ground truth may inflate accuracy. Worth debating once there is more than one scored case.
- **Repairing the `src/agents/.venv` agent-framework environment.** `agents.workflows.prior_auth` currently fails to import with `ImportError: cannot import name 'AzureOpenAIResponsesClient' from 'agent_framework.azure'` — the pinned `agent-framework` version drifted from what the code expects. Nothing in this plan depends on that import (all tests are offline and import only the new pure modules), but **no live workflow run is possible until it is fixed**, so it blocks the follow-on live-LLM plan. File it as the first issue of that plan.
- **Renaming the repo to `azure-governed-agents`.** Agreed but not yet executed; unrelated to execution-plane correctness.
