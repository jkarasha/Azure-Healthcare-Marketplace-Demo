# Prompt Module 05: Output Formatting & Notification

> **Bead:** `bd-pa-005-notify` — Steps 6-7
> **Purpose:** Generate structured determination output and notification letters
> **When to load:** At the start of bead `bd-pa-005-notify`
> **Release after:** Workflow complete

---

## Context Scope

**Read (required):**
- This prompt module
- `waypoints/decision.json` → `decision`, `rationale`, `audit` sections
- `waypoints/assessment.json` → `request.member`, `request.service`, `request.provider`, `criteria_evaluation`, `recommendation.gaps` sections

**Ignore (no longer relevant):**
- Clinical extraction details
- MCP tool results
- All prior prompt modules (01-04)

**The decision waypoint is your source of truth.**

---

## Overview

This module handles two output operations:
1. **Structured determination JSON** — converting the decision into a standardized schema for downstream systems
2. **Notification letters** — generating human-readable letters appropriate to the decision outcome

---

## Part 1: Structured Determination Output

Convert the decision into a standardized JSON schema. Extract all information from `waypoints/decision.json` and `waypoints/assessment.json`.

**File:** `outputs/determination.json`

### Determination Schema

```json
{
  "Determination": "Approved | Rejected | Needs More Information",
  "Rationale": "Concise summary of the decision rationale",
  "DetailedAnalysis": {
    "PolicyCriteriaAssessment": [
      {
        "CriterionName": "Name of the policy criterion",
        "Assessment": "Fully Met | Partially Met | Not Met",
        "Evidence": "Supporting evidence from the adjudication",
        "PolicyReference": "Reference to the policy language",
        "Notes": "Additional clarifications (optional)"
      }
    ],
    "MissingInformation": [
      {
        "InformationNeeded": "What specific data or documentation is required",
        "Reason": "Why this is necessary per policy"
      }
    ]
  }
}
```

### Mapping Rules

| Decision Waypoint | Determination Schema |
|---|---|
| `decision.outcome = "APPROVED"` | `Determination = "Approved"` |
| `decision.outcome = "PENDING"` | `Determination = "Needs More Information"` |
| `decision.outcome = "DENIED"` | `Determination = "Rejected"` |
| `assessment.criteria_evaluation[].status = "MET"` | `Assessment = "Fully Met"` |
| `assessment.criteria_evaluation[].status = "NOT_MET"` | `Assessment = "Not Met"` |
| `assessment.criteria_evaluation[].status = "INSUFFICIENT"` | `Assessment = "Partially Met"` |

### Data Integrity Rules

- Output MUST be valid JSON — no markdown formatting, no code fences in the output
- Maintain logical consistency between determination, rationale, and criteria assessments
- Only include information explicitly present in the waypoint files — no hallucination
- Every criterion from the assessment must appear in `PolicyCriteriaAssessment`
- If determination is "Needs More Information", `MissingInformation` array must be populated
- Write this JSON to `outputs/determination.json`

---

## Part 2: Notification Letters

Generate the appropriate letter based on `decision.outcome`. Letters should be complete, professional, and ready to send.

### Letter: Approval

**File:** `outputs/approval_letter.md`

**Required sections:**
1. Header with date and authorization number
2. Member information (name, ID, DOB)
3. Approved service details (description, CPT codes, provider + NPI)
4. Authorization period (valid from/through dates)
5. Limitations/conditions (if any)
6. Closing statement confirming medical necessity
7. Contact information

### Letter: Pend (Additional Information Required)

**File:** `outputs/pend_letter.md`

**Required sections:**
1. Header with date and reference number
2. Member information (name, ID)
3. Requested service (description, CPT codes)
4. **Information needed** — for each gap:
   - Gap title
   - What's needed (specific and actionable)
   - Why it's needed (policy basis)
5. Submission deadline (14 calendar days)
6. Submission instructions
7. Contact information

### Letter: Denial

**File:** `outputs/denial_letter.md`

**Required sections:**
1. Header with date and reference number
2. Member information (name, ID)
3. Denied service details
4. **Denial reason** — clear, specific explanation
5. **Policy basis** — policy ID, title, and unmet criteria
6. **Appeal rights** — instructions for appealing the decision
7. Contact information

---

## Letter Formatting Guidelines

- Use professional, empathetic tone
- Avoid medical jargon where possible — letters may be read by patients
- Include all required regulatory elements (appeal rights for denials)
- Format as clean Markdown with clear headings and structure
- Ensure no PHI placeholders remain — all fields must be populated from waypoints

---

## Quality Gates

Before marking bead `bd-pa-005-notify` as completed:

- [ ] Structured determination JSON is valid and complete
- [ ] Structured determination JSON written to `outputs/determination.json`
- [ ] All criteria from assessment appear in the determination output
- [ ] Appropriate notification letter generated based on decision outcome
- [ ] Letter contains all required sections for that decision type
- [ ] All member/service/provider fields populated (no placeholders)
- [ ] Appeal rights included if decision is DENIED
- [ ] Output files written successfully
