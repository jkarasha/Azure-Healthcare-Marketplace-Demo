# Production-Agent Evidence and Evaluation Model

This document defines the evidence required to support production-agent claims
and records the repository's current evaluation maturity.

For the canonical responsibility narrative, see
[`README.md`](../README.md).

## Current Evidence Coverage

| Evidence Surface | Maturity | Current Coverage | Important Limitation |
|---|---|---|---|
| MCP contract runner | **Partially implemented** | Extracts 38 consolidated tool names and checks selected consumers | The current run finds zero README tool references and skips removed Foundry and beginner-guide files, so a passing result does not prove broad contract consistency |
| MCP latency runner | **Partially implemented** | Measures success rate and p50/p95/max latency | Default cases focus on MCP protocol operations; no committed APIM production baseline is established |
| Native Agent Framework runner | **Partially implemented** | Uses Agent Framework lab task and evaluation contracts | Current tasks primarily validate MCP protocol correctness, not workflow outcome quality |
| Prior-auth fidelity runner | **Partially implemented** | Evaluates schema, bead ordering, and decision comparison | Current data contains one evaluated assessment; that assessment is schema-invalid, so `1/1` decision agreement is not meaningful production evidence |
| CI evaluation gate | **Target state** | Workflow files exist | Deployment sets `RUN_EVALS=false`, and the quality workflow does not run pytest |

## Evidence Principle

The production promotion unit is a versioned evidence bundle, not a prompt or
model deployment. The bundle identifies the workflow, skill and rubric, model,
tool contracts, infrastructure policy, evaluation data, results, known
limitations, and approved exceptions.

## Non-Negotiable Release Gates

- No unauthorized data or capability access.
- Required evidence, provenance, and audit lineage are complete.
- Outputs conform to active schema and policy versions.
- Safety-critical and prohibited outcomes remain within defined thresholds.
- Recovery does not duplicate or lose consequential side effects.

A release fails when any gate fails. Strong latency, cost, or aggregate
accuracy cannot compensate for a failed gate.

## Balanced Scorecard

| Category | Required Measures |
|---|---|
| Outcome value | Completion rate, turnaround time, user effort, downstream resolution |
| Decision quality | Precision and recall by outcome class, abstention quality, calibration, high-risk cohort performance |
| Operational reliability | Completion rate, p95/p99 latency, checkpoint recovery, dependency tolerance, degraded-mode frequency |
| Human effectiveness | Review time, override rate and reason, disagreement resolution, reviewer confidence |
| Economics | Cost per correct completed workflow, model/tool cost distribution, human-escalation cost |

Results must be segmented by workflow version, policy version, model, tool
versions, risk tier, and case cohort. Do not present a single aggregate
accuracy result as production readiness.

## Evidence Roadmap

### 1. Repair Current Contract Coverage

- Make the contract runner fail when an expected consumer yields zero
  references.
- Replace removed consumer paths with current Foundry, skill, and documentation
  surfaces.
- Validate role-specific `allowed_tools` sets as well as global tool names.

### 2. Expand Workflow Outcome Cases

- Add approved, pending, rejected, ambiguous, missing-evidence, invalid-input,
  and dependency-failure cohorts.
- Require schema validity before counting decision agreement.
- Report confidence calibration and abstention behavior.

### 3. Add Reliability and Recovery Evidence

- Exercise bounded retry, timeout, cancellation, checkpoint resume,
  incompatible-version recovery, and uncertain side-effect reconciliation.
- Publish local and APIM-hosted latency distributions separately.

### 4. Add Human-Authority Evidence

- Measure review latency, override rate and reason, disagreement resolution,
  and audit completeness.

### 5. Enforce Promotion Gates

- Run deterministic contract checks on pull requests.
- Run representative workflow and resilience suites before promotion.
- Store the evidence bundle with the promoted version.

## Current Local Checks

These commands exercise existing runners. They do not, by themselves,
constitute the complete production evidence model above.

### Contract Surface

```bash
make eval-contracts
```

### Local MCP Latency

```bash
make eval-latency-local
```

### Native Agent Framework Contracts

```bash
make eval-native-local
```

### Prior-Authorization Fidelity

```bash
python3 scripts/eval_prior_auth.py --json
```

At the time this narrative was written, the prior-auth runner evaluated one
assessment with a fidelity score of 72, a schema-invalid result, and `1/1`
decision agreement. Treat this as a smoke signal, not an accuracy claim.

## Practical Local Sequence

1. Start local capability services:

   ```bash
   make local-start
   ```

2. Run available checks:

   ```bash
   make eval-contracts
   make eval-latency-local
   make eval-native-local
   python3 scripts/eval_prior_auth.py --json
   ```

3. Stop local services:

   ```bash
   make local-stop
   ```

Passing these checks means the covered local cases passed. It does not mean the
system has satisfied the release gates or balanced scorecard.
