# De-Complexing + Performance Evals Plan

This repository has strong implementation depth but unnecessary cognitive load from tool-contract drift and duplicate runtime narratives.

## 1) De-Complexing Strategy

### A. Establish one canonical MCP contract

Canonical source of truth:
- Server implementations in `src/mcp-servers/*/function_app.py`

Guardrail:
- Run `make eval-contracts` to validate high-traffic docs/config files against implemented tool names.
- Files validated today:
  - `README.md`
  - `foundry-integration/agent_setup.py`
  - `foundry-integration/agent_config.yaml`
  - `foundry-integration/tools_catalog.json`
  - `docs/MCP-SERVERS-BEGINNER-GUIDE.md`

### B. Reduce surface-area ambiguity

Recommended operating model:
1. Primary runtime path: Python Azure Function MCP servers under `src/mcp-servers/`.
2. Secondary/reference path: `azure-fhir-mcp-server/` (explicitly sample/reference only).
3. Integration files (Foundry, docs, skills) should reference only canonical tool names.

### C. Stage cleanup by risk

1. High-risk drift first:
- Foundry tool contracts
- README tool list and quick-start path

2. Medium-risk drift:
- Skill references still using legacy names (`trials_search`, `cms_search_all`, etc.)
- Deploy docs with stale tool examples

3. Low-risk cleanup:
- Naming consistency and duplication cleanup across architecture docs

## 2) Performance + Reliability Evals

### Native Agent Framework eval surfaces (first choice)

From the installed framework packages in `src/agents/.venv`:
- `agent_framework.observability` (OpenTelemetry traces + metrics + instrumentation)
- `agent_framework_lab_gaia` evaluation contracts (`Task`, `Prediction`, `Evaluation`, `TaskResult`, `Evaluator`, `TaskRunner`)
- `agent_framework_lab_gaia.GAIA` benchmark runner (dataset-backed benchmark)

Repository integration:
- `make eval-native-local`
- Script: `scripts/eval_native_agent_framework.py`
- Config: `scripts/evals/native-agent-framework.local.json`

This uses native evaluation data contracts for local MCP checks and keeps result
format aligned with Agent Framework lab patterns.

### Baseline evals (implemented)

1. Contract eval
- Command: `make eval-contracts`
- Outcome: fail fast when docs/configs reference non-existent tools.

2. Latency + reliability eval
- Command: `make eval-latency-local`
- Config: `scripts/evals/mcp-latency.local.json`
- Current focus: MCP protocol overhead (`tools/list`) across all six servers.
- Metrics: success rate, p50, p95, max latency.

3. Native-style task eval (Agent Framework contracts)
- Command: `make eval-native-local`
- Outcome: pass/fail and score per task using `Task/Prediction/Evaluation/TaskResult`.
- Current focus: MCP protocol correctness checks (`tools/list`) for all six servers.

### Suggested KPI gates

For local/dev MCP baseline:
- Success rate: `>= 99%`
- p95 latency (`tools/list`): `<= 2000ms`

For APIM-hosted baseline (next step):
- Success rate: `>= 99%`
- p95 latency (`tools/list`): `<= 2500ms`

### Next eval expansions

1. Add tool-call workload profiles per server:
- NPI: `validate_npi`
- ICD-10: `validate_icd10`
- CMS: `get_coverage_by_cpt`
- FHIR: `get_patient_observations`
- PubMed: `search_pubmed`
- Trials: `search_trials`

2. Add APIM config for latency evals:
- Use env-var headers (subscription key / token)
- Compare local vs APIM distributions

3. Add CI gate (optional):
- Run `eval-contracts` on every PR
- Run latency eval in nightly or environment smoke suite

## 3) Practical Workflow

1. Start local servers:
```bash
make local-start
```

2. Run contract gate:
```bash
make eval-contracts
```

3. Run local latency baseline:
```bash
make eval-latency-local
```

4. Run native Agent Framework-style evals:
```bash
make eval-native-local
```

4. Stop local servers:
```bash
make local-stop
```

## 4) Why this de-complexes the project

- Replaces manual contract checking with deterministic evals.
- Keeps docs and integration artifacts synchronized to real tool APIs.
- Moves performance discussion from intuition to measurable latency/reliability baselines.
