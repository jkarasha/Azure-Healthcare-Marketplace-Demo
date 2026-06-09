# Prior Authorization Decision Rubric

## Purpose
This document defines the decision rules and criteria evaluation logic for the Prior Authorization Review Skill. Claude/Copilot MUST read this file before making any recommendations.

---

## Decision Logic

### Decision Types

| Decision | When to Use | AI Can Recommend? |
|----------|-------------|-------------------|
| **APPROVE** | All criteria met, high confidence | ✅ Yes |
| **PEND** | Missing info (`INSUFFICIENT`), low confidence, or borderline | ✅ Yes |
| **DENY** | Mandatory criterion clearly `NOT_MET` with ≥90% confidence | ✅ Yes (human confirms in Subskill 2) |

### AI DENY Recommendations

The AI **can** recommend DENY when a **mandatory** policy criterion is clearly `NOT_MET` — meaning the available documentation affirmatively shows the criterion is not satisfied (not just missing information).

**DENY conditions (ALL must be true):**
1. At least one mandatory criterion has status `NOT_MET` (not `INSUFFICIENT`)
2. The NOT_MET assessment has confidence ≥ 90%
3. The evidence for NOT_MET is based on documented clinical facts, not absence of documentation

**Key distinction:**
- `NOT_MET` = documentation clearly shows criterion is violated → **DENY** candidate
- `INSUFFICIENT` = we lack information to determine → **PEND** (request more info)

**DENY is still a recommendation, not a final decision.** The human reviewer confirms, overrides, or downgrades to PEND in Subskill 2. This preserves the human-in-the-loop guardrail while giving the AI the ability to signal clear policy violations rather than masking them as information gaps.

**Example:**
- Policy requires failure of a second-generation TKI. Documentation shows only a first-generation TKI was used throughout all treatment phases. This is NOT_MET (not INSUFFICIENT) — the clinical record is clear.
- Contrast: If the treatment history section was illegible or missing entirely, that would be INSUFFICIENT → PEND.

---

## Approval Criteria (ALL must be true)

### 1. Provider Verification (Required)
```
✅ PASS: NPI found AND active AND specialty appropriate
❌ FAIL: NPI not found OR inactive OR specialty mismatch
```

**If FAIL:** Recommend PEND, request credentialing documentation

### 2. Code Validation (Required)
```
✅ PASS: All ICD-10 AND CPT/HCPCS codes valid
❌ FAIL: Any code invalid or unrecognized
```

**If FAIL:** Recommend PEND, request code clarification

### 3. Coverage Policy (Required)
```
✅ PASS: Applicable LCD/NCD found for service
❌ FAIL: No applicable policy found
```

**If FAIL:** Recommend PEND for medical director review

### 4. Clinical Criteria (≥80% Required)
```
✅ PASS: ≥80% of policy criteria marked MET
⚠️ BORDERLINE: 60-79% of criteria MET
❌ FAIL: <60% of criteria MET
```

**Before applying thresholds, check for NOT_MET blockers:**
- If ANY mandatory criterion is `NOT_MET` with confidence ≥90% → Recommend **DENY**
- If criteria are `INSUFFICIENT` (documentation gaps) → Recommend **PEND**

**If BORDERLINE (no NOT_MET blockers):** Recommend PEND for additional documentation
**If FAIL (no NOT_MET blockers):** Recommend PEND with specific gaps

### 5. Confidence Threshold (Required)
```
✅ HIGH: ≥80% overall confidence → Can recommend APPROVE
⚠️ MEDIUM: 60-79% confidence → Can recommend APPROVE with flags
❌ LOW: <60% confidence → Must recommend PEND
```

---

## Evaluation Order

Evaluate in this order (stop at first failure):

1. **Provider Verification**
   - Check NPI status
   - If not verified → PEND (request credentialing)

2. **Code Validation**
   - Validate all ICD-10 codes
   - Validate all CPT/HCPCS codes
   - If any invalid → PEND (request clarification)

3. **Coverage Policy**
   - Search for applicable LCD/NCD
   - If none found → PEND (medical director review)

4. **Clinical Criteria**
   - Evaluate each policy criterion
   - **Check for NOT_MET blockers first:**
     - If any mandatory criterion is `NOT_MET` with ≥90% confidence → **DENY**
     - If criteria are `INSUFFICIENT` → continue to threshold check
   - Calculate percentage MET
   - If <60% → PEND (significant gaps)
   - If 60-79% → PEND (borderline, request additional docs)
   - If ≥80% → Continue to confidence check

5. **Confidence Assessment**
   - Calculate overall confidence
   - If <60% → PEND (low confidence)
   - If ≥60% → Can proceed to APPROVE

---

## Criteria Evaluation Rules

### Status Definitions

| Status | Definition |
|--------|------------|
| **MET** | Clear evidence in documentation supports criterion |
| **NOT_MET** | Documentation clearly contradicts criterion |
| **INSUFFICIENT** | Unable to determine from available documentation |

### Evidence Requirements

- **MET** requires specific, quotable evidence from documentation
- **NOT_MET** requires contradicting evidence or explicit absence
- **INSUFFICIENT** means evidence was looked for but not found

### Confidence Scoring

For each criterion, assign confidence (0-100):
- 90-100: Direct, unambiguous evidence
- 70-89: Strong inference from evidence
- 50-69: Reasonable inference with some uncertainty
- <50: Significant uncertainty

---

## Override Rules

### Human Can Override To:

| From AI | To Human | Requirements |
|---------|----------|--------------|
| APPROVE | PEND | Justification required |
| APPROVE | DENY | Justification + clinical basis required |
| PEND | APPROVE | Review completed, gaps resolved |
| PEND | DENY | Justification + clinical basis required |

### Override Documentation

All overrides must include:
1. Original AI recommendation
2. Final human decision
3. Justification for override
4. Name/role of overriding authority

---

## Special Cases

### Demo Mode
When using sample files with demo NPI (1234567890):
- Skip NPI lookup for demo provider only
- All other MCP calls execute normally
- Proceed with validation as if NPI verified

### Urgent Requests
For services marked urgent:
- Expedite review (target <24 hours)
- Apply same criteria
- Flag for priority processing

### Retrospective Reviews
For services already rendered:
- Apply same criteria
- Note that service already occurred
- Decision affects payment, not service delivery

---

## Confidence Calculation

Overall confidence = weighted average:
- Provider verification: 20%
- Code validation: 15%
- Coverage policy match: 20%
- Clinical criteria: 35%
- Documentation quality: 10%

Formula:
```
Overall = (0.20 × Provider) + (0.15 × Codes) + (0.20 × Policy) + (0.35 × Clinical) + (0.10 × DocQuality)
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2024-01-01 | Initial rubric |
| 1.1 | 2024-06-01 | Added confidence calculation |
| 1.2 | 2024-12-01 | Azure APIM integration |
