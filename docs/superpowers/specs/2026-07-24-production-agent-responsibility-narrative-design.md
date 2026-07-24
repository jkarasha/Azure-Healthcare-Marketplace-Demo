# Production Agent Responsibility Narrative Design

**Date:** 2026-07-24
**Status:** Approved design

## Purpose

Reframe the repository around a clear production-agent point of view that works
for executives, enterprise architects, and developers:

> Production agents are governed systems of responsibility, not models with
> tool access.

The narrative must position the repository as all three of the following:

1. A reference architecture for governed production agents.
2. A framework for evaluating production-agent designs.
3. An Azure accelerator that demonstrates the architecture through healthcare
   workflows.

The narrative must distinguish architectural intent from implemented,
partially implemented, and target-state capabilities.

## Goals

- Make the project's production-agent thesis explicit in the README.
- Explain responsibility boundaries in language that works at executive and
  technical depth.
- Show how the existing skills, workflows, MCP servers, Azure controls, human
  review, and evaluations implement the thesis.
- Establish a truthful evidence model for production claims.
- Make human authority, failure behavior, and operational governance explicit
  parts of the architecture.

## Non-Goals

- Redesign the workflow implementation in this phase.
- Modify runtime code, MCP servers, infrastructure, deployment workflows, or
  executable tests in this phase.
- Claim that all target-state controls are already operational.
- Replace detailed security, deployment, or workflow documentation.
- Present MCP, APIM, or any individual framework as the point of view by
  itself.
- Describe the accelerator as validated for clinical use.

Target-state controls, tests, and metrics in this design are narrative
requirements and future engineering requirements. Implementing them requires
separate approved specifications and plans.

## Documentation Scope

The next implementation plan is limited to these files:

- `README.md` - canonical production-agent thesis and layered overview.
- `docs/SKILLS-FLOW-MAP.md` - responsibility, plane, and lifecycle diagrams
  mapped to current workflows.
- `docs/architecture/APIM-ARCHITECTURE.md` - APIM's role within the broader
  control plane and explicit current-state versus target-state labeling.
- `docs/architecture/RETRIEVAL-ARCHITECTURE.md` - capability-service and
  system-of-record responsibilities.
- `docs/DECOMPLEX-PERF-EVALS.md` - gated balanced scorecard and honest current
  evidence coverage.

Other documentation may be linked but is not rewritten by this narrative
implementation. Any newly discovered contradiction outside these files should
be recorded as follow-up work rather than expanding the plan.

## Core Narrative

The repository should explain one architecture through three complementary
models:

1. **Responsibility Stack:** who owns each concern.
2. **Three Production Planes:** where execution, governance, and human
   authority operate.
3. **Governed Agent Lifecycle:** how the system is designed, executed,
   evaluated, and improved.

These are not competing frameworks. They are views of the same system for
different readers:

- Executives get the thesis, accountability model, and business relevance.
- Architects get planes, boundaries, contracts, and governance.
- Developers get concrete components, data flow, failure behavior, and tests.

## Responsibility Stack

Each responsibility belongs to one layer and is consumed by other layers
through an explicit contract.

| Layer | Owns | Must Not Own | Current Repository Mapping |
|---|---|---|---|
| Human authority | Intent, consequential approval, attributable override, accountability | Hidden or unaudited intervention | Prior-auth decision and notification phases |
| Experience surfaces | Intent capture, progress display, evidence presentation, decision interaction | Domain policy or infrastructure authorization | GitHub Copilot, Azure AI Foundry, CLI, Gradio |
| Workflow runtime | Coordination, state transitions, concurrency, checkpoints, resume, failure routing | Domain truth or permission grants | `src/agents/workflows/` and Microsoft Agent Framework |
| Domain policy | Procedures, rubrics, evidence requirements, schemas, decision criteria | Direct infrastructure access | `.github/skills/`, prompt modules, templates |
| Capability services | Narrow typed operations and external-system integration | Workflow decisions or user authorization | `src/mcp-servers/` |
| Systems of record | Durable authoritative facts and records | Agent reasoning | FHIR, Cosmos DB, Azure AI Search, external registries |

Governance cuts across all layers. It includes identity, authorization,
policy enforcement, quotas, telemetry, audit correlation, deployment control,
and version management.

### Responsibility Contract Rule

Every layer description should answer:

1. What does this layer own?
2. What is it forbidden from deciding?
3. What contract does it expose?
4. What evidence proves it performed its responsibility?

## Three Production Planes

### Agent Execution Plane

Performs request-specific work:

- Selects and loads the applicable domain procedure.
- Invokes only the capabilities allowed for the active role and workflow.
- Advances workflow state.
- Persists checkpoints and provenance.
- Produces evidence-backed draft outputs.

The execution plane cannot grant itself tools, permissions, policy changes, or
final authority over consequential decisions.

### Control Plane

Governs all workflow runs:

- Authenticates actors and workloads.
- Authorizes tools and data access.
- Versions workflows, policies, schemas, models, and capability contracts.
- Enforces quotas, time limits, cost limits, and deployment policy.
- Captures correlated security, workflow, model, and tool telemetry.
- Applies evaluation and promotion gates.
- Supports rollback, incident response, and kill controls.

APIM is one control-plane component, not the entire control plane.

The control plane may permit, constrain, block, route, and record execution. It
must not silently replace domain or human judgment with infrastructure policy.

### Human Authority Plane

Owns the decisions that remain attributable to people:

- Establishes intent and acceptable risk.
- Resolves ambiguity and exceptional cases.
- Reviews evidence and recommendations.
- Approves or overrides consequential outcomes.
- Owns accountability for the final decision.

Human actions must be authenticated, policy-constrained, attributable, and
included in the same audit lineage as agent actions.

## Governed Agent Lifecycle

The production lifecycle is a closed loop:

1. **Define:** Version skills, rubrics, schemas, tool contracts, and evaluation
   criteria.
2. **Admit:** Authenticate the actor, validate input, select the workflow, and
   assign the permitted capability set.
3. **Execute:** Reason and call tools within explicit permission, time, and cost
   boundaries.
4. **Checkpoint:** Persist state, evidence, provenance, version identifiers,
   and validation results at meaningful boundaries.
5. **Decide:** Route consequential outcomes to the human authority plane for
   approval or attributable override.
6. **Observe:** Correlate workflow, model, tool, security, latency, cost, and
   outcome telemetry.
7. **Improve:** Replay representative cases, run regression and safety
   evaluations, version changes, and promote them through controlled rollout.

## Failure and Recovery Model

The workflow must classify a failure before selecting a recovery action.

| Failure Class | Required Behavior |
|---|---|
| Transient dependency failure | Apply bounded retry with backoff; resume only from a valid checkpoint |
| Input or contract failure | Stop and request correction; do not retry unchanged invalid input |
| Missing evidence or unavailable optional capability | Degrade only when domain policy explicitly permits it; record the gap and restrict possible outcomes |
| Model or schema failure | Reject the output, attempt bounded structured regeneration, then escalate |
| Authorization, safety, or policy violation | Fail closed and create an auditable security event |
| Uncertain side effect | Do not replay blindly; reconcile with an idempotency key or route to human review |

Checkpoint recovery is allowed only when:

- Completed operations are idempotent or safely reconciled.
- The checkpoint is structurally valid.
- Workflow, domain policy, schema, model, and tool versions remain compatible.
- The recovery action is allowed by the active risk policy.

An escalation package contains the original request, completed evidence,
checkpoint state, failure classification, attempted recovery, active versions,
and recommended next action.

## Narrative Structure

The README should provide a complete but layered reading path:

1. Executive thesis.
2. Three-plane architecture diagram.
3. Responsibility Stack table.
4. Governed Agent Lifecycle and tiered failure model.
5. Mapping from the models to repository assets.
6. Production evidence and scorecard.
7. Maturity disclosure.

Detailed documents should expand these concepts without redefining them. The
README remains the canonical statement of the project's production-agent point
of view.

## Maturity Disclosure

Every production claim should use one of these labels:

- **Implemented:** Present in executable code or deployed infrastructure and
  covered by current evidence.
- **Partially implemented:** Present but missing enforcement, coverage, or
  operational proof.
- **Target state:** Architectural intent or planned capability.

The disclosure should specifically reconcile current gaps such as passthrough
APIM usage, disabled FHIR private networking, incomplete monitoring, limited
workflow reliability controls, and limited evaluation coverage.

## Evidence Model

Production readiness uses a gated balanced scorecard. Safety and governance
requirements cannot be averaged away by good latency or aggregate accuracy.

### Non-Negotiable Release Gates

- No unauthorized data or capability access.
- Required evidence, provenance, and audit lineage are complete.
- Outputs conform to the active schema and policy versions.
- Safety-critical and prohibited outcomes remain within defined thresholds.
- Recovery does not duplicate or lose consequential side effects.

### Balanced Scorecard

| Category | Representative Measures |
|---|---|
| Outcome value | Completion rate, turnaround time, user effort, downstream resolution |
| Decision quality | Precision and recall by outcome, abstention quality, calibration, high-risk cohort performance |
| Operational reliability | Completion rate, p95/p99 latency, checkpoint recovery, dependency tolerance, degraded-mode frequency |
| Human effectiveness | Review time, override rate and reason, disagreement resolution, reviewer confidence |
| Economics | Cost per correct completed workflow, tool/model cost distribution, human-escalation cost |

Results must be segmented by workflow version, policy version, model, tool
versions, risk tier, and case cohort. A single aggregate accuracy score is not
sufficient.

### Versioned Evidence Bundle

The production promotion unit is an evidence bundle containing:

- Workflow and domain-policy versions.
- Model and configuration.
- Tool contracts and server versions.
- Infrastructure and control-plane policy versions.
- Evaluation datasets and results.
- Reliability and failure-recovery results.
- Security and authorization results.
- Known limitations and approved exceptions.

## Test Strategy

The narrative should define the executable evidence that production maturity
eventually requires:

- **Domain policy:** representative case suites, rubric comparisons, outcome
  quality, abstention behavior, and high-risk cohort analysis.
- **Workflow runtime:** checkpoint/resume, cancellation, concurrency, timeout,
  idempotency, and incompatible-version recovery tests.
- **Capability services:** schema, contract, authorization, and real-backend
  integration tests.
- **Control plane:** identity, least privilege, quota, audit correlation,
  policy enforcement, promotion, rollback, and kill-control tests.
- **Human authority:** approval and override attribution, required
  justification, review latency, and audit completeness.
- **Operations:** load, latency, dependency-failure injection, cost, and
  degraded-mode tests.

The narrative implementation does not add or modify these tests. It documents
the target evidence model, labels current coverage accurately, and links to
existing evidence where available.

## Data and Decision Flow

1. A human or authorized system submits intent through an experience surface.
2. The control plane authenticates the actor and admits the request under a
   versioned workflow and policy.
3. The workflow runtime loads the applicable domain policy and receives a
   scoped capability set.
4. Capability services retrieve or change data in systems of record.
5. The runtime records evidence and state in a checkpoint.
6. The agent execution plane produces a recommendation with provenance and
   limitations.
7. The human authority plane reviews and finalizes consequential outcomes.
8. The control plane records the complete lineage and evaluates operational
   and outcome metrics.
9. Approved changes proceed through evaluation and controlled promotion.

## Documentation Deliverables

Implementation planning should cover:

1. Rewriting `README.md` opening and differentiation sections around the core
   thesis.
2. Adding the three-plane diagram, Responsibility Stack, lifecycle, failure
   model, balanced scorecard, and maturity disclosure to `README.md` at an
   executive-summary level.
3. Updating `docs/SKILLS-FLOW-MAP.md` to map current workflows to the approved
   responsibility, plane, and lifecycle terminology.
4. Updating `docs/architecture/APIM-ARCHITECTURE.md` to present APIM as one
   control-plane component and distinguish implemented controls from target
   state.
5. Updating `docs/architecture/RETRIEVAL-ARCHITECTURE.md` to distinguish
   capability services from systems of record.
6. Updating `docs/DECOMPLEX-PERF-EVALS.md` with the gated balanced scorecard and
   an accurate statement of current evaluation coverage.
7. Removing or qualifying unsupported production claims within those five
   files.
8. Linking each retained claim to current implementation evidence or labeling
   it as partially implemented or target state.

The plan must not include runtime, infrastructure, CI, test, or deployment
changes. Those become follow-up engineering proposals derived from the maturity
gaps documented here.

## Acceptance Criteria

- A mixed-audience reader can state the project's production-agent thesis after
  reading the README introduction.
- The README clearly distinguishes the Responsibility Stack, three production
  planes, and governed lifecycle while showing how they relate.
- Human authority is represented as an architectural plane with explicit
  responsibilities and constraints.
- Failure behavior is tiered by failure class and consequence.
- Production metrics use non-negotiable gates plus a balanced scorecard.
- Every major production claim in the five scoped documentation files is
  labeled implemented, partially implemented, or target state.
- Existing repository components are mapped to the model without implying that
  target-state controls are already operational.
- Supporting documentation uses consistent terminology and links back to the
  canonical README narrative.
