# Prior Authorization Flow Optimization Plan

## Executive Summary

With the MCP server consolidation (7 → 3), the prior-auth workflow already reduces MCP connections from 7 to 3. This document details additional optimizations:

1. **Prompt Enhancement Layer** — validate and refine vague user inputs before entering the pipeline
2. **Batched Tool Calls** — structure agent instructions to minimize round-trips per MCP server
3. **Validation Checkpoints** — bead-boundary gates that catch issues early and allow course correction
4. **Structured Intake Form** — ensure consistent input quality with confirmation before execution

---

## 1. Connection Reduction (Implemented)

### Before (7 servers, up to 14 connections per workflow)
```
ComplianceAgent → NPI server (7071) + ICD-10 server (7072)         = 2 connections
ClinicalAgent   → FHIR server (7074) + PubMed (7075) + Trials (7076) = 3 connections
CoverageAgent   → CMS server (7073) + ICD-10 (7072) + RAG (7077)  = 3 connections
SynthesisAgent  → no tools                                         = 0 connections
Audit events    → RAG server (7077)                                = 1 connection
                                                            Total: 9 MCP connections
```

### After (3 servers, up to 5 connections per workflow)
```
ComplianceAgent → reference-data (7071)                            = 1 connection
ClinicalAgent   → clinical-research (7072)                         = 1 connection
CoverageAgent   → reference-data (7071) + cosmos-rag (7073)        = 2 connections
SynthesisAgent  → no tools                                         = 0 connections
Audit events    → cosmos-rag (7073)                                = 1 connection
                                                            Total: 5 MCP connections
```

**Net reduction: 9 → 5 connections (44% fewer)**

Each `MCPStreamableHTTPTool` carries overhead: HTTP session setup, MCP `initialize` handshake, `tools/list` discovery. Reducing connections directly reduces latency.

---

## 2. Prompt Enhancement Layer

### Problem
Users may submit vague or incomplete requests:
- "Run prior auth for the patient" (no specifics)
- "Check if knee surgery is covered" (missing NPI, ICD-10, member info)
- "Prior auth for John Smith" (insufficient clinical context)

### Solution: Pre-Pipeline Intake Agent

Add a lightweight **Intake Enhancement Agent** (no MCP tools) that runs _before_ the workflow:

```
User Input → Intake Enhancement Agent → Structured PA Request → Workflow Pipeline
                    ↓ (if incomplete)
              Clarification Request → User Confirmation → Workflow Pipeline
```

#### Intake Enhancement Agent Design

```python
INTAKE_ENHANCEMENT_INSTRUCTIONS = """
You are a Prior Authorization Intake Specialist. Your role is to:

1. PARSE the user's request and extract:
   - Patient/member info (name, ID, DOB, state)
   - Provider info (NPI, name, specialty)
   - Service info (procedure description, CPT codes, ICD-10 codes)
   - Clinical context (diagnosis, supporting documentation)

2. IDENTIFY missing required fields:
   - NPI (required for compliance gate)
   - At least one ICD-10 code (required for validation)
   - At least one CPT code (required for coverage check)
   - Member ID or name (required for FHIR lookup)

3. ENHANCE vague descriptions:
   - "knee surgery" → "Total knee arthroplasty (TKA), CPT 27447"
   - "cancer treatment" → "What type? (e.g., chemotherapy, radiation, immunotherapy)"
   - "back pain" → "Specify: lumbar radiculopathy (M54.16)? Degenerative disc (M51.16)?"

4. OUTPUT a structured PA request JSON matching the workflow contract,
   OR a clarification request listing what's missing.

Always output in this format:
{
  "status": "ready" | "needs_clarification",
  "pa_request": { ... },  // if ready
  "clarifications_needed": [ ... ],  // if needs_clarification
  "enhancements_applied": [ ... ]  // list of auto-enhancements made
}
"""
```

#### Confirmation Flow

```
┌─────────────────────────────────────────────────┐
│ User: "Run prior auth for knee replacement,      │
│        Dr. Smith NPI 1234567890"                 │
└──────────────────────┬──────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────┐
│ Intake Enhancement Agent:                        │
│                                                  │
│ I've structured your request:                    │
│ • Provider: NPI 1234567890 (will verify)         │
│ • Procedure: Total Knee Arthroplasty (CPT 27447)│
│ • Missing: ICD-10 code — suggesting M17.11      │
│   (Primary osteoarthritis, right knee)           │
│ • Missing: Member/patient ID                     │
│                                                  │
│ Enhancements applied:                            │
│ ✓ "knee replacement" → CPT 27447 (TKA)          │
│ ✓ Suggested ICD-10: M17.11                       │
│                                                  │
│ Please confirm or provide:                       │
│ 1. Patient name/ID for FHIR lookup               │
│ 2. Confirm ICD-10 M17.11 or specify different    │
└─────────────────────────────────────────────────┘
```

---

## 3. Batched Tool Calls Per Agent

### Current Pattern (Sequential one-by-one)
```
ComplianceAgent:
  1. tools/call → validate_npi(1234567890)     # round-trip to reference-data
  2. tools/call → lookup_npi(1234567890)       # round-trip to reference-data  
  3. tools/call → validate_icd10(M17.11)       # round-trip to reference-data
  4. tools/call → validate_icd10(Z96.651)      # round-trip to reference-data
  5. tools/call → lookup_icd10(M17.11)         # round-trip to reference-data
                                          Total: 5 round-trips
```

### Optimized Pattern: Instruction-Driven Batching

The LLM agent decides tool call order. We can influence this by restructuring agent instructions to encourage parallel-compatible calls:

```python
COMPLIANCE_AGENT_OPTIMIZED_INSTRUCTIONS = """
## Validation Strategy (minimize round-trips)

STEP 1 — Validate ALL codes in parallel:
  - Call validate_npi for provider NPI
  - Call validate_icd10 for EACH ICD-10 code  
  - The framework may batch these if supported

STEP 2 — Lookup only if validation passes:
  - Call lookup_npi to get provider details (only if NPI is valid)
  - Call lookup_icd10 for the primary diagnosis code (only if valid)

Do NOT call lookup before validate — this wastes a round-trip if invalid.
"""
```

### Server-Side Batch Endpoint (Future Enhancement)

Add a `/mcp/batch` endpoint that accepts multiple `tools/call` in one HTTP request:

```json
{
  "jsonrpc": "2.0",
  "id": "batch-1",
  "method": "tools/call_batch",
  "params": {
    "calls": [
      {"name": "validate_npi", "arguments": {"npi": "1234567890"}},
      {"name": "validate_icd10", "arguments": {"code": "M17.11"}},
      {"name": "validate_icd10", "arguments": {"code": "Z96.651"}}
    ]
  }
}
```

This would reduce ComplianceAgent from 5 round-trips to 2 (batch validate → batch lookup).

---

## 4. Validation Checkpoints

### Current Checkpoints (per SKILL.md beads)

| Bead | Gate | Action on Failure |
|------|------|-------------------|
| 001 Intake | NPI valid + ICD-10 valid | PEND with compliance gaps |
| 002 Clinical | FHIR patient found | Continue with reduced confidence |
| 003 Recommend | All criteria evaluated | PEND with criteria gaps |

### Enhanced Checkpoints

Add mid-bead validation gates:

```
Bead 001: Intake
  ├── Gate 1a: Input completeness (pre-agent)
  │   └── Missing required fields → return to user for clarification
  ├── Gate 1b: Provider verification (post NPI check)
  │   └── NPI invalid → PEND immediately (don't waste clinical review)
  ├── Gate 1c: Code validation (post ICD-10 check)
  │   └── All codes invalid → PEND (no valid diagnosis to review)
  └── Gate 1d: RAG policy found
      └── No policy → flag as "off-label" but continue

Bead 002: Clinical
  ├── Gate 2a: FHIR patient match
  │   └── No match → continue with submitted clinical docs only
  ├── Gate 2b: Coverage policy match
  │   └── No LCD/NCD found → flag as "no specific policy" 
  └── Gate 2c: Medical necessity check
      └── Not covered → early PEND with specific policy reference

Bead 003: Recommend  
  ├── Gate 3a: Minimum evidence threshold
  │   └── <2 criteria met → PEND with gap list
  └── Gate 3b: Confidence threshold
      └── confidence_score < 0.6 → PEND for human review
```

### Implementation: Checkpoint Decorator

```python
async def checkpoint(
    assessment: dict,
    gate_id: str,
    condition: bool,
    on_fail: Literal["pend", "warn", "continue"] = "pend",
    message: str = "",
) -> bool:
    """Evaluate a validation checkpoint within a bead."""
    assessment.setdefault("checkpoints", []).append({
        "gate": gate_id,
        "passed": condition,
        "action": "proceed" if condition else on_fail,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    
    if not condition and on_fail == "pend":
        assessment["recommendation"]["decision"] = "PEND"
        assessment["recommendation"]["gaps"].append({
            "what": message,
            "gate": gate_id,
            "critical": True,
        })
        return False  # stop workflow
    return True  # continue
```

---

## 5. Structured Response Schemas

Define strict output schemas for each agent to ensure consistent parsing:

```python
COMPLIANCE_OUTPUT_SCHEMA = {
    "provider_verification": {
        "npi": str,
        "verified": bool,
        "name": str,
        "specialty": str,
        "status": Literal["active", "inactive", "not_found"],
    },
    "code_validation": {
        "all_codes_valid": bool,
        "icd10_results": [{"code": str, "valid": bool, "description": str}],
        "cpt_results": [{"code": str, "description": str}],
    },
    "completeness": {
        "can_proceed": bool,
        "missing_fields": [str],
        "warnings": [str],
    },
}
```

Each agent's instructions include: "Output ONLY a JSON object matching this schema."

---

## 6. Implementation Priority

| Priority | Change | Effort | Impact |
|----------|--------|--------|--------|
| ✅ Done | Server consolidation 7→3 | Medium | 44% fewer connections |
| P1 | Enhanced checkpoints in prior_auth.py | Low | Earlier failure detection |
| P1 | Structured output schemas | Low | Reliable parsing, fewer retries |
| P2 | Intake Enhancement Agent | Medium | Prevents bad-input waste |
| P2 | Instruction-driven batching | Low | Fewer round-trips per agent |
| P3 | Server-side batch endpoint | High | Optimal round-trip reduction |

---

## 7. Metrics to Track

- **MCP round-trips per workflow**: target < 15 (was ~25-30)
- **Time-to-first-gate**: target < 5s (compliance checkpoint)
- **Prompt enhancement acceptance rate**: % of enhanced prompts confirmed without changes
- **Early PEND rate**: % of requests caught by checkpoint gates before bead 003
- **Parse success rate**: % of agent outputs successfully parsed to schema
