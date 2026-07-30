# Prompt Module 04: Prior Authorization Determination

> **Bead:** `bd-pa-003-recommend` — Steps 7-10
> **Purpose:** Generate APPROVE/PEND/DENY recommendation using structured, rubric-aligned evaluation
> **When to load:** At the start of bead `bd-pa-003-recommend`
> **Release after:** Context Checkpoint 3 (recommendation captured in `waypoints/assessment.json`)

---

## Context Scope

**Read (required):**
- This prompt module
- `references/rubric.md` (decision rules — MUST read before proceeding)
- `waypoints/assessment.json` → `criteria_evaluation`, `policy`, `request.provider.verified` sections

**Ignore (already captured in waypoint):**
- Raw clinical documentation
- MCP tool call results
- Prompt modules 01, 02, 03
- Extraction details (summarized in waypoint)

**The waypoint criteria evaluation is your source of truth.**

---

## Overview

This module guides the final determination using a structured evaluation approach. The agent evaluates the complete criteria assessment, applies the rubric decision tree, and generates a justified recommendation.

**CRITICAL:** Read `references/rubric.md` FIRST. The rubric defines current decision policy, thresholds, and override rules. This module provides the reasoning framework; the rubric provides the rules.

---

## Reasoning Approach: Step-by-Step Analysis

Follow these steps in order. Capture concise, evidence-based outputs for each step.

### Step 1: Analyze All Policy Criteria

Review the `criteria_evaluation` array from the waypoint:

1. List every criterion and its status (MET / NOT_MET / INSUFFICIENT)
2. Calculate the percentage of criteria that are MET
3. Identify any NOT_MET criteria — these are potential blockers
4. Identify any INSUFFICIENT criteria — these represent documentation gaps

```
Criteria Summary:
  Total criteria: N
  MET: X (Y%)
  NOT_MET: A
  INSUFFICIENT: B
```

### Step 2: Validate Prerequisites (Rubric Evaluation Order)

Apply the rubric's evaluation order — **stop at first failure**:

**2a. Provider Verification**
- Check `assessment.request.provider.verified`
- If `false` → PEND (request credentialing documentation)
- If `true` → continue

**2b. Code Validation**
- Check that all ICD-10 codes were validated (from waypoint validation results)
- Check that all CPT/HCPCS codes were validated
- If any invalid → PEND (request code clarification)
- If all valid → continue

**2c. Coverage Policy**
- Check `assessment.policy` is populated
- If no policy found → PEND (medical director review)
- If policy found → continue

**2d. Clinical Criteria Threshold**
- **First, check for NOT_MET blockers:**
  - Scan `criteria_evaluation` for any criterion with `status: NOT_MET` AND `confidence ≥ 90`
  - If found → this is a DENY candidate (mandatory criterion is clearly violated by documented evidence)
  - If NOT_MET criteria exist but confidence < 90 → treat as borderline, PEND
- **Then apply threshold (if no NOT_MET blockers):**
  - Calculate percentage of criteria MET
  - If < 60% → PEND (significant gaps)
  - If 60-79% → PEND (borderline, request additional documentation)
  - If ≥80% → continue to confidence check

**2e. Confidence Assessment**
- Calculate overall confidence using rubric formula:
  ```
  Overall = (0.20 × Provider) + (0.15 × Codes) + (0.20 × Policy) + (0.35 × Clinical) + (0.10 × DocQuality)
  ```
- If < 60% → PEND (low confidence)
- If ≥ 60% → eligible for APPROVE

### Step 3: Generate Decision

Based on the evaluation:

**APPROVE** — ALL of the following are true:
- Provider verified (NPI valid and active)
- All ICD-10 and CPT codes valid
- Coverage policy found and applicable
- No mandatory criteria are `NOT_MET`
- ≥80% of required criteria MET
- Overall confidence ≥60%

**PEND** — Any of the following:
- Provider not verified → request credentialing docs
- Any codes invalid → request code clarification
- No coverage policy found → request medical director review
- Criteria are `INSUFFICIENT` (documentation gaps) → request additional documentation
- < 80% criteria met (but no NOT_MET blockers) → request additional documentation
- Confidence < 60% → request clarification
- Borderline case → request medical director review

**DENY** — ALL of the following are true:
- At least one mandatory policy criterion is `NOT_MET` (not `INSUFFICIENT`)
- The NOT_MET assessment has confidence ≥ 90%
- The evidence is based on documented clinical facts showing the criterion is clearly violated
- This is not a missing-information problem — the documentation affirmatively shows the requirement is not satisfied

**Key distinction:** `NOT_MET` means the record clearly shows the criterion is violated (DENY candidate). `INSUFFICIENT` means we lack information to judge (PEND for more docs). Do not conflate these — a known policy violation is not an information gap.

### Step 4: Document Rationale

Produce a structured rationale:

```
Decision: APPROVE | PEND | DENY
Confidence: HIGH (≥80%) | MEDIUM (60-79%) | LOW (<60%)
Confidence Score: 0-100

Rationale Summary:
  [2-3 sentence justification]

Supporting Evidence:
  - [Each key piece of evidence supporting the decision]

Gaps (if PEND):
  - [Gap 1]: [What's needed] — Critical: Yes/No
  - [Gap 2]: [What's needed] — Critical: Yes/No

Denial Basis (if DENY):
  - Unmet Criterion: [Criterion name]
  - Evidence: [Clinical facts showing criterion is NOT_MET]
  - Policy Reference: [Section/clause]
  - Confidence: [X]%

Criteria Met: X/N (Y%)
```

---

## Output: Determination Detail

### For the Waypoint

Add `recommendation` block to `waypoints/assessment.json`:

```json
{
  "recommendation": {
    "decision": "APPROVE | PEND | DENY",
    "confidence": "HIGH | MEDIUM | LOW",
    "confidence_score": 0-100,
    "rationale": "Clear, evidence-based justification",
    "criteria_met": "X/N",
    "criteria_percentage": 0-100,
    "prerequisite_checks": {
      "provider_verified": true,
      "codes_valid": true,
      "policy_found": true,
      "criteria_threshold_met": true,
      "confidence_threshold_met": true
    },
    "gaps": [
      {
        "what": "Description of missing evidence",
        "critical": true,
        "request": "What to ask for"
      }
    ]
  }
}
```

### For the Audit Document

Generate `outputs/audit_justification.md` with these sections:

1. **Disclaimer Header** (REQUIRED at top):
   ```
   ⚠️ AI-ASSISTED DRAFT - REVIEW REQUIRED
   Coverage policies reflect Medicare LCDs/NCDs only. Commercial/MA plans may differ.
   All decisions require human clinical review before finalization.
   ```

2. **Executive Summary** — Request ID, member, service, provider, decision, confidence
3. **Clinical Synopsis** — Diagnoses, key findings, prior treatments
4. **Policy Analysis** — Applicable policy, criteria evaluation table
5. **Recommendation Details** — Decision rationale, evidence, gaps

---

## Quality Gates

Before marking bead `bd-pa-003-recommend` as completed:

- [ ] Rubric.md was read before making any determination
- [ ] All 5 prerequisite checks evaluated in order
- [ ] Decision follows rubric rules exactly
- [ ] Confidence score calculated using rubric formula
- [ ] Rationale includes specific evidence citations
- [ ] Gaps documented with actionable requests (if PEND)
- [ ] `waypoints/assessment.json` updated with recommendation block
- [ ] `outputs/audit_justification.md` generated with disclaimer header
