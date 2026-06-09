# Subskill 1: Intake & Assessment

## Purpose
Collect prior authorization request information, validate credentials and codes, extract clinical data, identify applicable coverage policies, assess medical necessity, and generate approval recommendation.

## Prerequisites

### Required MCP Servers (Consolidated Architecture)

This subskill uses **2 consolidated MCP servers** for healthcare data validation:

1. **`mcp-reference-data`** — NPI + ICD-10 + CMS Coverage (12 tools, single endpoint)
   - **NPI Tools:** `lookup_npi(npi="...")`, `validate_npi(npi="...")`, `search_providers(...)`
   - **ICD-10 Tools:** `validate_icd10(code="...")`, `lookup_icd10(code="...")`, `search_icd10(query="...")`, `get_icd10_chapter(code_prefix="...")`
   - **CMS Tools:** `search_coverage(query="...", coverage_type="all", limit=10)`, `check_medical_necessity(cpt_code="...", icd10_codes=[...])`, `get_coverage_by_cpt(cpt_code="...")`, `get_coverage_by_icd10(icd10_code="...")`, `get_mac_jurisdiction(state="...")`
   - **Success Notification:** `✅ mcp-reference-data invoked successfully`

2. **`mcp-clinical-research`** — FHIR + PubMed + ClinicalTrials (20 tools, single endpoint)
   - **PubMed Tools:** `search_pubmed(query="...")`, `search_clinical_queries(query="...", category="therapy")`, `get_article(pmid="...")`, `get_article_abstract(pmid="...")`
   - **FHIR Tools:** `search_patients(identifier="...")`, `get_patient_conditions(patient_id="...")`, `get_patient_medications(patient_id="...")`, `get_patient_observations(patient_id="...")`
   - **Success Notification:** `✅ mcp-clinical-research invoked successfully`
   - **Note:** Optional — PubMed enhances evidence, FHIR enriches clinical context. If unavailable, skip and note in assessment

---

## What This Subskill Does

1. Collects PA request details (member, service, provider, clinical documentation)
2. Validates provider credentials and medical codes via MCP connectors (parallel execution)
3. Searches for applicable coverage policies and checks medical necessity
4. Extracts clinical data and maps to policy criteria
5. Searches PubMed for supporting literature (optional, strengthens evidence)
6. Performs medical necessity assessment
7. Generates recommendation (APPROVE/PEND)

---

## Prompt Module Loading

Subskill 1 spans three beads with different prompt modules:

| Bead | Prompt Module(s) | When to Read |
|------|------------------|--------------|
| `bd-pa-001-intake` | `references/prompts/01-extraction.md` + `references/prompts/02-policy-retrieval.md` | Read `01-extraction.md` before Step 1; read `02-policy-retrieval.md` before Step 2c |
| `bd-pa-002-clinical` | `references/prompts/03-clinical-assessment.md` | Before Step 4 |
| `bd-pa-003-recommend` | `references/prompts/04-determination.md` + `references/rubric.md` | Before Step 7 |

**Read only the prompt module(s) needed for the current step.** Do not pre-load modules for later beads.

---

## Execution Flow

### Bead Tracking (Subskill 1)

Subskill 1 spans three beads. Update bead status as you progress:

| Bead | Steps | Checklist |
|------|-------|-----------|
| `bd-pa-001-intake` | 1-3 | [ ] Collect request info [ ] NPI validated [ ] ICD-10 validated [ ] CMS policy found [ ] Medical necessity checked [ ] CPT validated |
| `bd-pa-002-clinical` | 4-6 | [ ] Clinical data extracted [ ] Rubric read [ ] Evidence mapped to criteria |
| `bd-pa-003-recommend` | 7-10 | [ ] Recommendation generated [ ] assessment.json written [ ] audit_justification.md written [ ] Summary displayed |

**Before starting each bead group:** Mark the bead `in-progress` and persist to `waypoints/assessment.json` under the `"beads"` key.
**After completing each bead group:** Mark the bead `completed` with a timestamp and persist.

### Step 1: Collect Request Information

Request PA details from user:

```
Prior Authorization Request Information:

1. Member Information
   - Member Name:
   - Member ID:
   - Date of Birth:
   - State:

2. Service Information
   - Service Description:
   - CPT/HCPCS Code(s):
   - ICD-10 Diagnosis Code(s):
   - Requested Date of Service:

3. Provider Information
   - Provider Name:
   - NPI:
   - Specialty:

4. Clinical Documentation
   - Please provide or paste clinical notes/documentation
```

**Or if using sample files:**
Read from `data/sample_cases/prior_auth_baseline/` directory.

---

### Step 2: Parallel MCP Validation

> **Bead `bd-pa-001-intake`** — mark **in-progress** before starting this step.

Execute MCP calls in parallel for optimal performance:

**2a. NPI Validation**

Display: "Verifying provider credentials via mcp-reference-data (NPI tools)..."

```python
lookup_npi(npi="[provider_npi]")
```
- Verify NPI is active
- Confirm specialty matches service
- Check license state

After successful call, display: "✅ NPI validation completed - Provider: [Name], Specialty: [Specialty], Status: Active"

**If provider not found:**
Display error: "Provider NPI [number] not found or inactive. Per rubric.md policy, requests without verified provider will result in PENDING status (request credentialing documentation)."

**2b. ICD-10 Validation**

Display: "Validating diagnosis codes via mcp-reference-data (ICD-10 tools)..."

```python
validate_icd10(code="E11.9")  # Call once per code
validate_icd10(code="J06.9")  # Can be parallelized
```

For each valid code, get details:
```python
lookup_icd10(code="E11.9")  # Single code only
```

After successful call, display: "✅ ICD-10 validation completed - Validated [N] codes"

**2c. CMS Coverage Policy Search**

Display: "Searching coverage policies via mcp-reference-data (CMS tools)..."

```python
search_coverage(
    query="[service description]",
    limit=10
)
```
- Find applicable LCDs/NCDs for service

After successful call, display: "✅ CMS Coverage search completed - Found policy: [Policy ID] - [Title]"

**2d. CMS Medical Necessity Check**

Display: "Checking medical necessity via mcp-reference-data (CMS tools)..."

```python
check_medical_necessity(
    cpt_code="[primary CPT code]",
    icd10_codes=["E11.9", "J06.9"]  # All diagnosis codes from request
)
```
- Determine if the procedure is medically necessary for the given diagnoses per Medicare policy
- Returns coverage determination with supporting policy references

After successful call, display: "✅ CMS Medical Necessity Check completed - [Covered/Not Covered]: [Policy basis]"

**2e. CMS Coverage by CPT** (optional, for additional detail)

```python
get_coverage_by_cpt(cpt_code="[primary CPT code]")
```
- Retrieve detailed coverage information specific to the procedure code

**2f. CMS Coverage by ICD-10** (optional, for additional detail)

```python
get_coverage_by_icd10(icd10_code="[primary diagnosis code]")
```
- Retrieve coverage policies anchored to the primary diagnosis

**Important:** Also display contextual limitation notice:
> "Note: Coverage policies are sourced from Medicare LCDs/NCDs. If this review is for a commercial or Medicare Advantage plan, payer-specific policies may differ."

**2g. FHIR Patient History** (optional — when `mcp-clinical-research` FHIR tools are available and member has FHIR record)

Display: "Retrieving patient history via mcp-clinical-research (FHIR tools)..."

If a member ID is available, search for the patient and pull relevant history:

```python
search_patients(identifier="[member_id]")  # or by name + DOB
```

If patient found, retrieve clinical context in parallel:
```python
get_patient_conditions(patient_id="[fhir_id]", clinical_status="active")
get_patient_medications(patient_id="[fhir_id]", status="active")
get_patient_observations(patient_id="[fhir_id]", category="laboratory", count=10)
```

After successful calls, display: "✅ FHIR patient data retrieved - [N] active conditions, [N] medications, [N] recent observations"

**How FHIR data is used:**
- Cross-reference reported diagnoses in PA form with active conditions in EHR
- Verify prior treatments mentioned in clinical docs match medication history
- Enrich clinical extraction (Step 4) with lab values and encounter history
- Stored in `assessment.json` under `fhir_patient_context` field

**Graceful degradation:** If the `mcp-clinical-research` server is unavailable or no patient record found, skip and rely solely on submitted clinical documentation. Note in assessment that FHIR enrichment was not performed.

---

### Step 3: CPT/HCPCS Validation (WebFetch)

Display: "Validating CPT/HCPCS codes via CMS Fee Schedule..."

For each CPT/HCPCS code:
- WebFetch to CMS Medicare Physician Fee Schedule
- Verify code is valid and active
- Get code description

Display: "✅ CPT validation completed - [Code]: [Description]"

---

### Step 4: Extract Clinical Data

> **Bead `bd-pa-001-intake`** — mark **completed** after Step 3 finishes.
> **Bead `bd-pa-002-clinical`** — mark **in-progress** now.

#### Context Checkpoint 1
Write collected data to `waypoints/assessment.json` (`request`, `clinical`, `policy` sections). From this point forward, use the **waypoint as source of truth** — do not re-read raw clinical documents or MCP tool results. Release prompt modules 01-extraction and 02-policy-retrieval from consideration.

**Read now:** `references/prompts/03-clinical-assessment.md`

Parse clinical documentation to extract:
- Chief complaint
- Relevant diagnoses
- Prior treatments tried
- Current symptoms/findings
- Test results (labs, imaging)
- Clinical justification for service

Calculate extraction confidence (0-100%):
- High confidence (>80%): Clear, structured documentation
- Medium confidence (60-80%): Some inference required
- Low confidence (<60%): Significant gaps

---

### Step 5: Read Rubric

**CRITICAL:** Before making any recommendation, read `references/rubric.md` to understand:
- Current decision policy
- Criteria evaluation order
- Override rules
- Confidence thresholds

---

### Step 5a: PubMed Evidence Search (Optional — Strengthens Recommendation)

Display: "Searching PubMed for evidence via mcp-clinical-research (PubMed tools)..."

Search for published literature supporting the requested service for the given diagnoses:

```python
search_clinical_queries(
    query="[service description] [primary diagnosis]",
    category="therapy",
    scope="narrow",
    max_results=5
)
```

If relevant articles are found, retrieve key abstracts:

```python
get_article_abstract(pmid="[top PMID]")
```

After successful call, display: "✅ PubMed search completed - Found [N] relevant studies supporting [service] for [condition]"

**How evidence is used:**
- Strengthens criteria evaluation with published support
- Cited in `assessment.json` under `literature_support` field
- Referenced in `outputs/audit_justification.md` for regulatory documentation
- If no relevant literature found, note as a gap but do not downgrade recommendation solely for this reason

**Graceful degradation:** If `mcp-clinical-research` PubMed tools are unavailable, skip this step and note in the assessment that literature search was not performed. Continue with criteria mapping.

### Step 6: Map Evidence to Policy Criteria

For each criterion in the applicable policy:
1. Search clinical data for supporting evidence
2. Mark as MET, NOT_MET, or INSUFFICIENT
3. Document specific evidence supporting determination
4. Assign confidence score (0-100)

---

### Step 7: Generate Recommendation

> **Bead `bd-pa-002-clinical`** — mark **completed** after Step 6 finishes.
> **Bead `bd-pa-003-recommend`** — mark **in-progress** now.

#### Context Checkpoint 2
Update `waypoints/assessment.json` with `criteria_evaluation` array. Release prompt module 03-clinical-assessment from consideration.

**Read now:** `references/prompts/04-determination.md` and `references/rubric.md`

Apply rubric.md decision rules:

**APPROVE** (must meet ALL):
- Provider verified (NPI valid and active)
- All ICD-10 codes valid
- All CPT codes valid
- Coverage policy found
- ≥80% of required criteria MET
- Overall confidence ≥60%

**PEND** (any of these):
- Provider not verified → Request credentialing docs
- Missing criteria evidence → Request additional documentation
- Confidence <60% → Request clarification
- Borderline case → Request medical director review

**Note:** AI never recommends DENY in default mode.

---

### Step 8: Create Assessment Waypoint

**File:** `waypoints/assessment.json`

**Consolidated structure** (includes bead tracking):
```json
{
  "request_id": "...",
  "created": "ISO datetime",
  "status": "assessment_complete",

  "beads": [
    {"id": "bd-pa-001-intake",    "status": "completed", "completed_at": "..."},
    {"id": "bd-pa-002-clinical",   "status": "completed", "completed_at": "..."},
    {"id": "bd-pa-003-recommend",  "status": "completed", "completed_at": "..."},
    {"id": "bd-pa-004-decision",   "status": "not-started"},
    {"id": "bd-pa-005-notify",     "status": "not-started"}
  ],

  "request": {
    "member": {"name": "...", "id": "...", "dob": "...", "state": "..."},
    "service": {"type": "...", "description": "...", "cpt_codes": [...], "icd10_codes": [...]},
    "provider": {"npi": "...", "name": "...", "specialty": "...", "verified": true/false}
  },

  "fhir_patient_context": {
    "patient_found": true/false,
    "fhir_patient_id": "..." or null,
    "active_conditions": ["..."],
    "active_medications": ["..."],
    "recent_observations": [{"code": "...", "value": "...", "date": "..."}],
    "cross_reference_notes": "Diagnoses in PA form confirmed/discrepancies noted"
  },

  "clinical": {
    "chief_complaint": "...",
    "key_findings": ["...", "..."],
    "prior_treatments": ["..."],
    "extraction_confidence": 0-100
  },

  "policy": {
    "policy_id": "...",
    "policy_title": "...",
    "policy_type": "LCD/NCD",
    "contractor": "...",
    "covered_indications": ["...", "..."],
    "medical_necessity_check": {
      "cpt_code": "...",
      "icd10_codes": ["..."],
      "is_covered": true/false,
      "policy_basis": "..."
    }
  },

  "literature_support": {
    "searched": true/false,
    "query_used": "...",
    "articles_found": 0,
    "key_citations": [
      {"pmid": "...", "title": "...", "relevance": "..."}
    ],
    "evidence_summary": "..."
  },

  "criteria_evaluation": [
    {"criterion": "...", "status": "MET/NOT_MET/INSUFFICIENT", "evidence": [...], "notes": "...", "confidence": 0-100}
  ],

  "recommendation": {
    "decision": "APPROVE/PEND",
    "confidence": "HIGH/MEDIUM/LOW",
    "confidence_score": 0-100,
    "rationale": "...",
    "criteria_met": "N/N",
    "gaps": [{"what": "...", "critical": true/false, "request": "..."}]
  }
}
```

**Write file.**

---

### Step 9: Generate Audit Justification Document

**Purpose:** Create a detailed, human-readable audit justification document for regulatory compliance and review.

**File:** `outputs/audit_justification.md`

Inform user: "Generating audit justification document..."

**Generate comprehensive Markdown report with the following sections:**

**0. Disclaimer Header (REQUIRED - must appear at top of document)**

```
⚠️ AI-ASSISTED DRAFT - REVIEW REQUIRED
Coverage policies reflect Medicare LCDs/NCDs only. If this review is for a
commercial or Medicare Advantage plan, payer-specific policies were not applied.
All decisions require human clinical review before finalization.
```

1. **Executive Summary**
   - Request ID, review date, reviewed by
   - Member details (name, ID, DOB)
   - Service description
   - Provider details (name, NPI, specialty)
   - Decision (APPROVE/PEND)
   - Overall confidence (percentage and level)

2. **Clinical Synopsis**
   - Chief complaint
   - Relevant diagnoses with ICD-10 codes
   - Key clinical findings
   - Prior treatments

3. **Policy Analysis**
   - Applicable policy (LCD/NCD)
   - Coverage criteria
   - Criteria evaluation (met/not met)

4. **Recommendation Details**
   - Decision rationale
   - Supporting evidence
   - Gaps identified (if any)

---

### Step 10: Display Summary

> **Bead `bd-pa-003-recommend`** — mark **completed** after writing all files.

```
✅ INTAKE & ASSESSMENT COMPLETE

📋 Request Summary:
   Member: [Name] ([ID])
   Service: [Description] ([CPT Code])
   Provider: [Name] ([NPI]) - [Verified/Not Verified]

📊 Validation Results:
   NPI: ✅ Verified
   ICD-10 Codes: ✅ [N] codes validated
   CPT Codes: ✅ [N] codes validated
   Coverage Policy: ✅ Found - [Policy ID]

🔍 Clinical Assessment:
   Criteria Met: [N]/[Total]
   Confidence: [Percentage]% ([Level])

📝 RECOMMENDATION: [APPROVE/PEND]
   Rationale: [Brief rationale]

📁 Files Created:
   • waypoints/assessment.json
   • outputs/audit_justification.md

---

⚠️ HUMAN REVIEW REQUIRED
This is a draft recommendation. Please review the assessment
and proceed to Subskill 2 for final decision.

Ready to continue? (Yes/No)
```

---

## Output Files

| File | Content |
|------|---------|
| `waypoints/assessment.json` | Structured assessment data |
| `outputs/audit_justification.md` | Human-readable audit document |

---

## Error Handling

### MCP Server Unavailable

Display error: "MCP Server Unavailable - Cannot access required healthcare data servers. This skill requires the `mcp-reference-data` server (NPI + ICD-10 + CMS tools) to function. Please configure the missing server and try again."

Exit subskill and return to main menu.

### Low Confidence Clinical Extraction

If overall confidence < 60%:

Display warning: "LOW CONFIDENCE WARNING - Extraction Confidence: [X]%"

List low confidence areas and offer options:
1. Continue (may result in pend)
2. Request additional documentation
3. Abort

---

## Quality Checks

Before completing Subskill 1:
- [ ] Bead `bd-pa-001-intake` marked completed
- [ ] Bead `bd-pa-002-clinical` marked completed
- [ ] Bead `bd-pa-003-recommend` marked completed
- [ ] Bead state persisted in `waypoints/assessment.json`
- [ ] All MCP validations completed
- [ ] Coverage policy identified
- [ ] Clinical data extracted
- [ ] Criteria evaluation complete
- [ ] Recommendation generated
- [ ] Assessment waypoint created
- [ ] Audit document generated

---

## Notes for Claude/Copilot

### Implementation Hints

1. **Parallel MCP calls save time:** Execute NPI, ICD-10, and Coverage searches concurrently in Step 2
2. **ICD-10 validation:** Use `validate_icd10(code=...)` for each code (can be parallelized), then `lookup_icd10(code=...)` for each to get details
3. **CPT validation is sequential:** WebFetch each CPT/HCPCS code to CMS Fee Schedule in Step 3 (no MCP available)
4. **Display MCP notifications:** Show success notifications after each MCP connector invocation for user visibility
5. **Policy-aware extraction:** Focus clinical extraction on what policy criteria need
6. **Be specific with evidence:** Document exact clinical facts supporting each criterion
7. **Honest confidence:** Low confidence should trigger warnings/human review

**Display notifications:**
- BEFORE each MCP/WebFetch call: Inform user which connector is being used and what data is being queried
- AFTER each successful call: Display success notification with summary

### Common Mistakes to Avoid

**MCP and Validation:**
- ❌ Don't call `validate_icd10()` with multiple codes - it takes a single `code` string parameter
- ❌ Don't call `lookup_icd10()` with array parameter - it takes single code only
- ❌ Don't skip CPT/HCPCS validation - it's required even though no MCP exists
- ❌ Don't forget to display MCP success notifications after each connector invocation

**Decision Policy Enforcement (CRITICAL):**
- ❌ Don't ignore provider verification status when calculating recommendation
- ❌ Don't make decisions without first reading rubric.md
- ✅ DO read rubric.md FIRST to understand current policy
- ✅ DO apply the decision rules specified in rubric.md
- ✅ DO store validation failure status for Step 2

**Clinical Assessment:**
- ❌ Don't mark criteria as "MET" without specific evidence
- ✅ DO check validation status per rubric.md rules
- ✅ DO follow the evaluation order specified in rubric.md
- ✅ DO execute MCP calls in parallel where possible
- ✅ DO validate CPT codes via WebFetch to CMS Fee Schedule
- ✅ DO provide clear, specific evidence for each criterion
- ✅ DO flag borderline cases for human review
