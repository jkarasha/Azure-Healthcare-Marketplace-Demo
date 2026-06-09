# Skills Flow Map

This document visualizes how GitHub Copilot, MCP server configuration, and the `.github/skills` workflows work together in this repository.

## 1) System Flow (Copilot + MCP)

```mermaid
flowchart LR
    U["Developer in VS Code"] --> VSC["VS Code Chat Surface"]
    VSC --> LM["GitHub Copilot Agent"]
    LM --> SK[".github/skills/* context"]
    LM --> M[".vscode/mcp.json"]
    M --> L["Local MCP<br/>localhost:7071-7076"]
    M --> F["Function App MCP<br/>https://*.azurewebsites.net/mcp"]
    M --> A["APIM MCP<br/>https://*.azure-api.net/mcp*/..."]
    L --> X[src/mcp-servers/*]
    F --> X
    A --> X
    X --> E["Healthcare data APIs"]
    LM --> R1["Response in chat"]
```

## 2) Copilot Skills Loading Path

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant VS as VS Code
    participant Repo as .github/skills
    participant LLM as GitHub Copilot Agent

    Dev->>VS: Ask a healthcare workflow question
    VS->>LLM: Send prompt
    LLM->>Repo: Read relevant skill + references
    Repo-->>LLM: Skill context
    LLM-->>VS: Streamed response
```

Notes:
- No custom VS Code chat participant is required.
- Skill routing is model-driven from repository context in `.github/skills`.

## 3) Native Copilot MCP Path (`mcp.json`)

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant VS as VS Code
    participant MCPConf as .vscode/mcp.json
    participant MCP as MCP Endpoint

    Dev->>VS: Use Copilot with MCP-enabled tools
    VS->>MCPConf: Resolve configured server
    MCPConf->>MCP: Send MCP initialize/tools/list/tools/call
    MCP-->>VS: MCP tool responses
    VS-->>Dev: Tool-augmented response
```

## 4) Prior Authorization Skill Flow

Source files:
- `.github/skills/prior-auth-azure/SKILL.md`
- `.github/skills/prior-auth-azure/references/01-intake-assessment.md`
- `.github/skills/prior-auth-azure/references/02-decision-notification.md`
- `.github/skills/prior-auth-azure/references/rubric.md`

```mermaid
flowchart TD
    A[Input: PA request + clinical docs] --> B["bd-pa-001-intake\nCompliance Agent"]

    B --> RAG["RAG policy retrieval\n(cosmos-rag hybrid_search)"]
    B --> VAL{"Parallel MCP validation\n(mcp-reference-data)"}
    VAL --> NPI["NPI verification"]
    VAL --> ICD["ICD-10 validation"]

    RAG --> GATE
    NPI --> GATE
    ICD --> GATE
    GATE{"Compliance\ngate"} -->|Fail| PEND_EARLY["PEND with compliance gaps"]
    GATE -->|Pass| CP1["Context Checkpoint 1\nwaypoints/assessment.json"]

    CP1 --> CONC
    subgraph CONC["bd-pa-002-clinical — Concurrent Agents"]
        CR["Clinical Reviewer Agent\nFHIR + PubMed + Trials\n(mcp-clinical-research)"]
        CA["Coverage Agent\nCMS policies + RAG\n(mcp-reference-data + cosmos-rag)"]
    end

    CONC --> CP2["Context Checkpoint 2"]
    CP2 --> E["bd-pa-003-recommend\nSynthesis Agent\n(reads rubric.md · no MCP tools)"]
    E --> WP["waypoints/assessment.json\n+ outputs/audit_justification.md"]

    WP --> F["bd-pa-004-decision\nSubskill 2: Human review"]
    F --> G{Human decision}
    G --> H[APPROVE]
    G --> I[PEND]
    G --> J[DENY / OVERRIDE]
    H --> K["bd-pa-005-notify\nwaypoints/decision.json\n+ determination.json + letters"]
    I --> K
    J --> K
```

### Prior Auth Bead Tracking

| Bead ID | Phase | Agent | Status Persisted In |
|---------|-------|-------|---------------------|
| `bd-pa-001-intake` | RAG retrieval + NPI/ICD-10 compliance gate | Compliance Agent | `waypoints/assessment.json` |
| `bd-pa-002-clinical` | Clinical review + CMS coverage (concurrent) | Clinical Reviewer + Coverage Agent | `waypoints/assessment.json` |
| `bd-pa-003-recommend` | Synthesis → recommendation + audit doc | Synthesis Agent | `waypoints/assessment.json` |
| `bd-pa-004-decision` | Human review + decision capture | Human | `waypoints/decision.json` |
| `bd-pa-005-notify` | Determination JSON + notification letters | (code generation) | `waypoints/decision.json` |

## 5) Clinical Trial Protocol Skill Flow

Source files:
- `.github/skills/clinical-trial-protocol/SKILL.md`
- `.github/skills/clinical-trial-protocol/references/00-05*.md`
- `.github/skills/clinical-trial-protocol/scripts/sample_size_calculator.py`

```mermaid
flowchart TD
    S0["bd-ct-000-init\n00-initialize-intervention.md"] --> W0[waypoints/intervention_metadata.json]
    W0 --> S1["bd-ct-001-research\n01-research-protocols.md"]
    S1 --> CT[Clinical Trials MCP<br/>trials_search + trials_details]
    CT --> W1[waypoints/01_clinical_research_summary.json]

    W1 --> S2["bd-ct-002-foundation\n02-protocol-foundation.md"]
    S2 --> W2[waypoints/02_protocol_foundation.md<br/>+ 02_protocol_metadata.json]

    W2 --> S3["bd-ct-003-intervention\n03-protocol-intervention.md"]
    S3 --> W3[waypoints/03_protocol_intervention.md]

    W3 --> S4["bd-ct-004-operations\n04-protocol-operations.md"]
    S4 --> PY[sample_size_calculator.py]
    PY --> W4[waypoints/04_protocol_operations.md]

    W4 --> S5["bd-ct-005-concatenate\n05-concatenate-protocol.md"]
    S5 --> OUT[waypoints/protocol_complete.md]
```

### Clinical Trial Bead Tracking

| Bead ID | Step | Status Persisted In |
|---------|------|---------------------|
| `bd-ct-000-init` | Initialize intervention | `waypoints/intervention_metadata.json` |
| `bd-ct-001-research` | Research protocols | `waypoints/intervention_metadata.json` |
| `bd-ct-002-foundation` | Protocol foundation | `waypoints/intervention_metadata.json` |
| `bd-ct-003-intervention` | Intervention details | `waypoints/intervention_metadata.json` |
| `bd-ct-004-operations` | Operations & statistics | `waypoints/intervention_metadata.json` |
| `bd-ct-005-concatenate` | Concatenate final | `waypoints/intervention_metadata.json` |

Resume behavior reads bead state from `intervention_metadata.json` first, falling back to file-existence detection.

## 6) Skills Directory Anatomy

```mermaid
flowchart LR
    ROOT[.github/skills/skill-name] --> SK[SKILL.md]
    ROOT --> REF[references/]
    ROOT --> AST[assets/]
    ROOT --> TMP[templates/]
    ROOT --> SCR[scripts/]

    SK --> FLOW[Workflow contract]
    REF --> RULES[Step logic + policy/rubric]
    AST --> SAMPLE[Sample cases and docs]
    TMP --> STRUCT[Input/output structure]
    SCR --> CALC[Optional helper scripts]
```

## 7) OCR and RAG Knowledge Layer Extension

```mermaid
flowchart LR
    DOCS[Unstructured corpus<br/>clinical notes and scanned PDFs] --> OCR[OCR and parsing]
    OCR --> CHUNK[Chunk and enrich metadata]
    CHUNK --> IDX[Vector and semantic index]
    IDX --> KMCP[Document Knowledge MCP]

    KMCP --> PA[prior-auth-azure skill flow]
    KMCP --> CTP[clinical-trial-protocol skill flow]
    PA --> OUT1[Evidence-backed PA outputs]
    CTP --> OUT2[Citation-backed protocol outputs]
```

Adoption touchpoints:
- MCP layer: add a document-knowledge server and register it in `.vscode/mcp.json`.
- Skill layer: add retrieval prerequisites in `SKILL.md` and tool definitions in `references/tools.md`.
- Prompt layer: require retrieval before synthesis and enforce source citations.

## 8) Beads Task Tracking Pattern

All skills use **beads** (`bd-*`) to track progress through multi-step workflows. Each bead represents a discrete phase, has a unique ID, and follows a `not-started → in-progress → completed` lifecycle.

```mermaid
flowchart LR
    NS[not-started] --> IP[in-progress]
    IP --> C[completed]
    IP -.->|error/retry| IP
    C -.->|never goes back| C
```

### Rules

1. **One active bead** at a time (only one `in-progress`)
2. **Sequential execution** — beads complete in order
3. **Persisted in waypoints** — bead state is written to JSON waypoint files under a `"beads"` key
4. **Resume from beads** — on startup, read bead array and resume from first non-completed bead
5. **Audit trail** — each completed bead records a `completed_at` timestamp

### Bead State Schema

```json
{
  "beads": [
    {"id": "bd-XX-NNN-name", "status": "completed", "completed_at": "2026-02-10T12:00:00Z"},
    {"id": "bd-XX-NNN-name", "status": "in-progress", "started_at": "2026-02-10T12:05:00Z"},
    {"id": "bd-XX-NNN-name", "status": "not-started"}
  ]
}
```

### Skill Bead Registries

| Skill | Bead Prefix | Bead Count | Persisted In |
|-------|-------------|------------|---------------|
| Prior Authorization | `bd-pa-*` | 5 beads | `assessment.json`, `decision.json` |
| Clinical Trial Protocol | `bd-ct-*` | 6 beads | `intervention_metadata.json` |

---

## 9) Practical Reading Order

1. Open `SKILL.md` for orchestration rules.
2. Follow `references/*.md` in execution order.
3. Use `data/sample_cases/prior_auth_baseline/*` for test runs.
4. Validate MCP connectivity in `.vscode/mcp.json`.
5. Run workflow and inspect `waypoints/*`.
