# Subskill 2: Decision & Notification

## Purpose
Accept human review of assessment findings, confirm or override the AI recommendation, generate authorization documentation, and create notification letters.

## Prerequisites

**Required Files:**
- `waypoints/assessment.json` (from Subskill 1)

**Must verify:** Subskill 1 completed (assessment status is "assessment_complete")

---

## What This Subskill Does

1. Reads assessment from Subskill 1
2. Presents findings summary for human review
3. Accepts human decision (confirm, override, or request more info)
4. Generates authorization number (if approved)
5. Creates decision waypoint with audit trail
6. Generates notification letters

---

## Prompt Module Loading

Subskill 2 spans two beads:

| Bead | Prompt Module(s) | When to Read |
|------|------------------|--------------|
| `bd-pa-004-decision` | *(none — human review phase)* | N/A |
| `bd-pa-005-notify` | `references/prompts/05-output-formatting.md` | Before Step 6 |

### Context Scope for Subskill 2

**Read from waypoints only.** By this point, all clinical data, MCP results, policy evaluation, and determination have been captured in `waypoints/assessment.json`. Do not re-read raw clinical documents, MCP results, or prompt modules 01-04.

- **Bead 004**: Read `assessment.json` → `recommendation` section + human's decision input
- **Bead 005**: Read `decision.json` + `assessment.json` → `request.member`, `request.service`, `request.provider`, `criteria_evaluation`, `recommendation.gaps`

---

## Execution Flow

### Bead Tracking (Subskill 2)

Subskill 2 spans two beads. Update bead status as you progress:

| Bead | Steps | Checklist |
|------|-------|-----------|
| `bd-pa-004-decision` | 1-5 | [ ] Assessment loaded [ ] Summary presented [ ] Human decision captured [ ] Decision waypoint written [ ] Auth number generated (if approved) |
| `bd-pa-005-notify` | 6-7 | [ ] Notification letter generated [ ] Completion summary displayed |

**Before starting each bead group:** Mark the bead `in-progress` and update `waypoints/assessment.json` (and later `waypoints/decision.json`) under the `"beads"` key.
**After completing each bead group:** Mark the bead `completed` with a timestamp and persist.

### Step 1: Load Assessment

Read `waypoints/assessment.json` and verify:
- `status` is "assessment_complete"
- All required fields populated

**If assessment not found or incomplete:**
```
Error: Assessment not found or incomplete.
Please complete Subskill 1 (Intake & Assessment) first.
```
Exit.

---

### Step 2: Present Assessment Summary

> **Bead `bd-pa-004-decision`** — mark **in-progress** now.

Display formatted summary for human review:

```
═══════════════════════════════════════════════════════════════
              PRIOR AUTHORIZATION ASSESSMENT REVIEW
═══════════════════════════════════════════════════════════════

📋 REQUEST DETAILS
───────────────────────────────────────────────────────────────
Member:      [Name] ([ID])
DOB:         [Date]
State:       [State]

Service:     [Description]
CPT Codes:   [Codes]
ICD-10:      [Codes]
DOS:         [Date]

Provider:    [Name]
NPI:         [NPI]
Specialty:   [Specialty]
Verified:    [✅/❌]

📊 VALIDATION RESULTS
───────────────────────────────────────────────────────────────
NPI Registry:     [✅ Verified / ❌ Not Found]
ICD-10 Codes:     [✅ N codes valid / ❌ Invalid codes]
CPT Codes:        [✅ N codes valid / ❌ Invalid codes]
Coverage Policy:  [✅ Found / ❌ Not Found]

📋 APPLICABLE POLICY
───────────────────────────────────────────────────────────────
Policy ID:    [ID]
Policy Title: [Title]
Contractor:   [Name]

🔍 CRITERIA EVALUATION
───────────────────────────────────────────────────────────────
[For each criterion:]
[✅/❌/⚠️] [Criterion name]
    Evidence: [Supporting evidence]
    Confidence: [X]%

───────────────────────────────────────────────────────────────
CRITERIA MET: [N]/[Total] ([Percentage]%)
OVERALL CONFIDENCE: [X]% ([HIGH/MEDIUM/LOW])
───────────────────────────────────────────────────────────────

📝 AI RECOMMENDATION: [APPROVE/PEND]
───────────────────────────────────────────────────────────────
Rationale: [Brief rationale]

[If PEND, list gaps:]
⚠️ Information Gaps:
   • [Gap 1]: [What's needed]
   • [Gap 2]: [What's needed]

═══════════════════════════════════════════════════════════════
```

---

### Step 3: Request Human Decision

```
⚠️ HUMAN DECISION REQUIRED
───────────────────────────────────────────────────────────────

Based on your review of the assessment above, please select:

  1. APPROVE - Confirm approval recommendation
  2. PEND - Request additional information
  3. DENY - Override to denial (requires justification)
  4. OVERRIDE - Override recommendation with different decision
  5. REQUEST MORE INFO - Need clarification before deciding

Enter choice (1-5):
```

**If user selects DENY or OVERRIDE:**
```
Please provide justification for this decision:
(This will be documented in the audit trail)

Justification:
```

**Decision normalization for waypoint output (`decision.outcome`):**
- User selects `APPROVE` → store `APPROVED`
- User selects `PEND` or `REQUEST MORE INFO` → store `PENDING`
- User selects `DENY` → store `DENIED`
- `OVERRIDE` must resolve to one of `APPROVED`, `PENDING`, or `DENIED`

---

### Step 4: Create Decision Waypoint

**File:** `waypoints/decision.json`

Include bead state in the decision waypoint:

```json
{
  "request_id": "...",
  "decision_date": "ISO datetime",

  "beads": [
    {"id": "bd-pa-001-intake",    "status": "completed", "completed_at": "..."},
    {"id": "bd-pa-002-clinical",   "status": "completed", "completed_at": "..."},
    {"id": "bd-pa-003-recommend",  "status": "completed", "completed_at": "..."},
    {"id": "bd-pa-004-decision",   "status": "completed", "completed_at": "..."},
    {"id": "bd-pa-005-notify",     "status": "not-started"}
  ],

  "decision": {
    "outcome": "APPROVED/DENIED/PENDING",
    "auth_number": "PA-YYYYMMDD-XXXXX" or null,
    "valid_from": "YYYY-MM-DD" or null,
    "valid_through": "YYYY-MM-DD" or null,
    "limitations": [...] or null,
    "override_applied": true/false
  },

  "rationale": {
    "summary": "...",
    "supporting_facts": ["...", "..."],
    "policy_basis": "..."
  },

  "audit": {
    "reviewed_by": "AI-Assisted Review",
    "review_date": "...",
    "turnaround_hours": float,
    "confidence": "HIGH/MEDIUM/LOW",
    "auto_approved": true/false
  },

  "override_details": {
    "original_recommendation": "APPROVE/PEND",
    "final_decision": "...",
    "override_reason": "...",
    "overriding_authority": "..."
  } or null
}
```

---

### Step 5: Generate Authorization Number

If decision is APPROVED:

```
Authorization Number: PA-[YYYYMMDD]-[5-digit random]
Valid From: [Service Date or Today]
Valid Through: [Service Date + 30 days default]
```

---

### Step 6: Generate Notification Letters

> **Bead `bd-pa-004-decision`** — mark **completed** after Step 5 finishes.
> **Bead `bd-pa-005-notify`** — mark **in-progress** now.

#### Context Checkpoint 4
Write `waypoints/decision.json`. For output generation, carry forward only compact assessment data needed for notification and determination formatting (`request.member`, `request.service`, `request.provider`, `criteria_evaluation`, `recommendation.gaps`).

**Read now:** `references/prompts/05-output-formatting.md`

Based on decision outcome, generate appropriate letter:

First, generate structured determination JSON output:
- `outputs/determination.json` (per `references/prompts/05-output-formatting.md`)

**For APPROVED:**
Create `outputs/approval_letter.md`:

```markdown
# Prior Authorization Approval

**Date:** [Date]
**Authorization Number:** [Auth Number]

---

**Member Information:**
- Name: [Name]
- Member ID: [ID]
- Date of Birth: [DOB]

**Approved Service:**
- Description: [Service]
- CPT Code(s): [Codes]
- Provider: [Name] (NPI: [NPI])

**Authorization Period:**
- Valid From: [Date]
- Valid Through: [Date]

**Limitations/Conditions:**
[List any limitations]

---

This authorization confirms that the requested service meets medical
necessity criteria based on the clinical information provided.

If you have questions, please contact [Contact Info].
```

**For PENDING:**
Create `outputs/pend_letter.md`:

```markdown
# Prior Authorization - Additional Information Required

**Date:** [Date]
**Reference Number:** [Request ID]

---

**Member Information:**
- Name: [Name]
- Member ID: [ID]

**Requested Service:**
- Description: [Service]
- CPT Code(s): [Codes]

---

## Information Needed

To complete our review of this prior authorization request, we need
the following additional information:

[For each gap:]
1. **[Gap Title]**
   - What's needed: [Description]
   - Why it's needed: [Explanation]

## How to Submit

Please submit the requested information within 14 calendar days to:
[Submission instructions]

## Questions?

If you have questions about this request, please contact [Contact Info].
```

**For DENIED:**
Create `outputs/denial_letter.md`:

```markdown
# Prior Authorization Denial

**Date:** [Date]
**Reference Number:** [Request ID]

---

**Member Information:**
- Name: [Name]
- Member ID: [ID]

**Denied Service:**
- Description: [Service]
- CPT Code(s): [Codes]

---

## Denial Reason

[Clear explanation of why request was denied]

## Policy Basis

This decision is based on:
- Policy: [Policy ID - Title]
- Criteria not met: [List]

## Appeal Rights

You have the right to appeal this decision. To appeal:
[Appeal instructions]

## Questions?

If you have questions about this decision, please contact [Contact Info].
```

---

### Step 7: Display Completion Summary

> **Bead `bd-pa-005-notify`** — mark **completed** after generating letters.

```
═══════════════════════════════════════════════════════════════
           PRIOR AUTHORIZATION REVIEW COMPLETE
═══════════════════════════════════════════════════════════════

📝 FINAL DECISION: [APPROVED/DENIED/PENDING]

[If APPROVED:]
✅ Authorization Number: [Auth Number]
   Valid: [From Date] - [Through Date]

[If PENDING:]
⏳ Additional information requested
   See: outputs/pend_letter.md

[If DENIED:]
❌ Denial issued
   Appeal rights included in notification

📁 FILES CREATED:
   • waypoints/decision.json
   • outputs/[approval/pend/denial]_letter.md

📊 TURNAROUND TIME: [X] hours

═══════════════════════════════════════════════════════════════

Review complete. What would you like to do next?
  1. Start new PA review
  2. Exit
```

---

## Output Files

| File | Content |
|------|---------|
| `waypoints/decision.json` | Structured decision data with audit trail |
| `outputs/determination.json` | Standardized determination JSON for downstream systems |
| `outputs/approval_letter.md` | Approval notification (if approved) |
| `outputs/pend_letter.md` | Pend notification (if pending) |
| `outputs/denial_letter.md` | Denial notification (if denied) |

---

## Error Handling

**Assessment not found:**
```
Error: waypoints/assessment.json not found.
Please complete Subskill 1 first.
```

**File write error:**
```
Error: Unable to write [filename].
Please check permissions and try again.
```

---

## Quality Checks

Before completing Subskill 2:
- [ ] Bead `bd-pa-004-decision` marked completed
- [ ] Bead `bd-pa-005-notify` marked completed
- [ ] All beads (`bd-pa-001` through `bd-pa-005`) in completed state
- [ ] Bead state persisted in `waypoints/decision.json`
- [ ] Assessment loaded and verified
- [ ] Human decision captured
- [ ] Override justification documented (if applicable)
- [ ] Decision waypoint created
- [ ] `outputs/determination.json` created and valid JSON
- [ ] Authorization number generated (if approved)
- [ ] Notification letter generated
- [ ] All required fields populated

---

## Notes for Claude/Copilot

1. **Always present full assessment:** Don't summarize too much - human needs all details
2. **Require explicit decision:** Don't proceed without clear human input
3. **Document everything:** All decisions and overrides go in the audit trail
4. **Generate complete letters:** Letters should be ready to send
5. **Calculate turnaround:** Track time from request to decision
6. **Respect human judgment:** If human overrides, document but don't challenge
