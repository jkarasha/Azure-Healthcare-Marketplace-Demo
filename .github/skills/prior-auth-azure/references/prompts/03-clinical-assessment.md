# Prompt Module 03: Clinical Assessment & Evidence Mapping

> **Bead:** `bd-pa-002-clinical` — Steps 4-6
> **Purpose:** Map extracted clinical evidence against coverage policy criteria
> **When to load:** At the start of bead `bd-pa-002-clinical`
> **Release after:** Context Checkpoint 2 (criteria evaluation captured in `waypoints/assessment.json`)

---

## Context Scope

**Read (required):**
- This prompt module
- `waypoints/assessment.json` → `request`, `clinical`, `policy` sections only

**Ignore (already captured in waypoint):**
- Raw clinical documentation text
- MCP tool call results (NPI, ICD-10, CMS raw responses)
- Prompt modules 01-extraction and 02-policy-retrieval

**The waypoint is your source of truth.** Do not re-read raw inputs from earlier beads.

---

## Overview

This module guides the evidence-to-criteria mapping process. For each criterion in the applicable coverage policy, evaluate whether the extracted clinical data satisfies it, producing a structured evaluation array.

---

## Step 1: Policy Criteria Extraction

From `assessment.policy`, extract every coverage criterion. Policies typically specify:

- **Required diagnoses/conditions** — specific ICD-10 codes or condition categories
- **Prior treatment requirements** — drugs that must be tried and failed first (step therapy)
- **Dosage/duration requirements** — specific dosing limits or treatment duration
- **Patient eligibility** — age, weight, comorbidity requirements
- **Physician qualifications** — specialty requirements for prescribing
- **Required diagnostics** — labs, imaging, or tests that must be documented
- **Exclusions/contraindications** — conditions that disqualify coverage
- **Authorization duration** — how long the approval is valid, renewal criteria

**Critical:** Capture EVERY criterion. Pay attention to qualifying language:
- "and" = all conditions must be met
- "or" = any condition suffices
- "must" / "shall" = mandatory
- "should" = recommended but not required
- "unless" / "except" = carve-out conditions

---

## Step 2: Evidence Mapping

For each extracted criterion, search the clinical data in `assessment.clinical` for supporting evidence.

### Evaluation per Criterion

```
Criterion: [State the policy criterion verbatim]
Assessment: MET | NOT_MET | INSUFFICIENT
Evidence: [Specific clinical facts — quote from extracted data]
Policy Reference: [Section/paragraph of the policy]
Confidence: 0-100
Notes: [Any caveats or interpretation notes]
```

### Status Definitions

| Status | Definition | Evidence Requirement |
|--------|------------|---------------------|
| **MET** | Clinical data clearly supports the criterion | Specific, quotable evidence from extracted data |
| **NOT_MET** | Clinical data clearly contradicts the criterion | Contradicting evidence or explicit documented absence |
| **INSUFFICIENT** | Cannot determine from available data | Evidence was searched for but not found |

### Confidence Scale per Criterion

| Score | Meaning |
|-------|---------|
| 90-100 | Direct, unambiguous evidence matches criterion exactly |
| 70-89 | Strong inference — evidence supports criterion with minor interpretation |
| 50-69 | Reasonable inference — some uncertainty in how evidence maps to criterion |
| <50 | Significant uncertainty — evidence is tangential or ambiguous |

---

## Step 3: Drug Class Analysis (Step Therapy)

If the policy requires prior treatment failures (step therapy), perform detailed analysis:

1. **List required prior drugs** from the policy
2. **Match against extracted prior treatments** from `assessment.clinical.prior_treatments_and_results` and `specific_drugs_taken_and_failures`
3. **For each required drug:**
   - Was it tried? (Yes/No)
   - Duration of trial?
   - Outcome? (Inadequate response, adverse reaction, contraindicated)
   - Does the outcome qualify as a "failure" per the policy definition?
4. **Count**: N of M required drugs tried and failed
5. **If shortfall**: Document which required drugs were not tried or not documented as failures

---

## Step 4: Summarize Policy for Record

Create a concise policy summary (max 4096 characters) for the waypoint:

### Structure

```
Policy Title: [Title]
Policy Summary: [Key coverage scope and purpose]
Conditions:
  - [Each coverage criterion, numbered]
Recommendations:
  - [Areas requiring particular attention during review]
```

This summary replaces the full policy text in downstream beads — keep it complete but compact.

---

## Output Schema

Add `criteria_evaluation` array to `waypoints/assessment.json`:

```json
{
  "criteria_evaluation": [
    {
      "criterion": "Patient must have diagnosis of X confirmed by Y",
      "status": "MET",
      "evidence": ["ICD-10 E11.9 confirmed", "HbA1c of 9.2% documented on 01/15/2026"],
      "policy_reference": "Section 2.1 - Diagnostic Requirements",
      "confidence": 92,
      "notes": ""
    },
    {
      "criterion": "Patient must have tried and failed at least 2 first-line agents",
      "status": "MET",
      "evidence": ["Metformin 1000mg x 6 months - inadequate response", "Glipizide 10mg x 3 months - adverse GI effects"],
      "policy_reference": "Section 3.2 - Step Therapy Requirements",
      "confidence": 88,
      "notes": "Both failures well-documented with dates and outcomes"
    }
  ]
}
```

---

## Quality Gates

Before marking bead `bd-pa-002-clinical` as completed, verify:

- [ ] Every policy criterion has a corresponding evaluation entry
- [ ] Every `MET` status has specific evidence cited
- [ ] Every `NOT_MET` has contradicting evidence or documented absence
- [ ] Step therapy analysis completed (if applicable)
- [ ] Policy summary written
- [ ] Criteria evaluation array written to waypoint
- [ ] No criterion was skipped or overlooked
