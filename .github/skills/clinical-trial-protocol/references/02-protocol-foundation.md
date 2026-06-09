# Step 2: Clinical Protocol Foundation

## Purpose
Generate the foundation sections (1-6) of a clinical study protocol based on research findings and intervention metadata.

## Prerequisites

**Required Files:**
- `waypoints/intervention_metadata.json`
- `waypoints/01_clinical_research_summary.json`

**Must verify:** Step 1 is complete (check `completed_steps` array in intervention metadata)

---

## What This Subskill Does

1. Verifies Step 1 completion
2. Reads research summary and intervention metadata
3. Reads protocol template (user-provided or FDA standard from assets)
4. Generates Sections 1-6 of the clinical protocol
5. Creates protocol foundation waypoint file
6. Creates protocol metadata tracking file

---

## Protocol Section Structure

### Sections Generated in Step 2:

```
TITLE PAGE
  Protocol Title
  Protocol Version and Date
  Sponsor Information
  Investigator Information
  Confidentiality Statement

SECTION 1: STATEMENT OF COMPLIANCE
  1.1 Protocol Compliance
  1.2 Regulatory Compliance
  1.3 Institutional Review Board

SECTION 2: PROTOCOL SUMMARY (SYNOPSIS)
  2.1 Study Overview Table
  2.2 Schema/Design Diagram

SECTION 3: INTRODUCTION
  3.1 Background
  3.2 Rationale for the Study
  3.3 Risk/Benefit Assessment

SECTION 4: OBJECTIVES AND ENDPOINTS
  4.1 Primary Objective
  4.2 Secondary Objectives
  4.3 Exploratory Objectives
  4.4 Endpoints
    4.4.1 Primary Endpoint(s)
    4.4.2 Secondary Endpoints
    4.4.3 Exploratory Endpoints

SECTION 5: STUDY DESIGN
  5.1 Overall Design
  5.2 Scientific Rationale for Study Design
  5.3 Justification for Dose Selection
  5.4 End of Study Definition

SECTION 6: STUDY POPULATION
  6.1 Inclusion Criteria
  6.2 Exclusion Criteria
  6.3 Lifestyle Considerations
  6.4 Screen Failures
  6.5 Strategies for Recruitment
```

---

## Execution Flow

### Step 1: Verify Prerequisites

Read `waypoints/intervention_metadata.json` and verify:
- `protocol_status` is "initialized" or later
- `01-research-protocols` is in `completed_steps`

**If Step 1 not completed:**
```
Error: Research step not completed.
Please run Step 1 before generating protocol foundation.
```
Exit.

---

### Step 2: Load Research Data

Read `waypoints/01_clinical_research_summary.json` and extract:
- Similar trial designs
- Recommended endpoints
- Sample size guidance
- Inclusion/exclusion patterns
- Regulatory pathway

---

### Step 3: Load Protocol Template

Check `intervention_metadata.json` for `user_provided_template`:

**If user provided template:**
- Read the template file
- Use it as the formatting guide

**If no user template:**
- Use `assets/FDA-Clinical-Protocol-Template.md`
- Apply NIH/FDA standard structure

---

### Step 4: Generate Protocol Foundation

Generate Sections 1-6 with the following guidelines:

#### Title Page
- Use intervention name from metadata
- Version: "1.0 Draft"
- Date: Current date
- Include sponsor placeholder and confidentiality statement

#### Section 1: Statement of Compliance
- Reference 21 CFR Part 50 (human subjects protection)
- Reference 21 CFR Part 56 (IRB requirements)
- Reference ICH E6 GCP guidelines
- For devices: Reference 21 CFR Part 812 (IDE)
- For drugs: Reference 21 CFR Part 312 (IND)

#### Section 2: Protocol Summary
- Create structured synopsis table
- Include study schema diagram (text-based)
- Summarize key design elements

#### Section 3: Introduction
- Background from research findings
- Scientific rationale
- Benefit/risk assessment based on similar trials

#### Section 4: Objectives and Endpoints
- Primary objective derived from indication
- Endpoints from research recommendations
- Measurable, time-bound specifications

#### Section 5: Study Design
- Design type from research recommendations
- Randomization approach
- Blinding strategy
- Treatment arms

#### Section 6: Study Population
- Inclusion criteria (8-12 criteria typical)
- Exclusion criteria (10-15 criteria typical)
- Based on patterns from similar trials

---

### Step 5: Create Protocol Foundation File

**File:** `waypoints/02_protocol_foundation.md`

Write all Sections 1-6 to a single markdown file:
- Use proper heading hierarchy
- Include placeholders for site-specific information marked as `[TO BE DETERMINED]`
- Format tables using markdown syntax
- Target ~1,500 lines for comprehensive coverage

---

### Step 6: Create Protocol Metadata

Create `waypoints/02_protocol_metadata.json`:

```json
{
  "intervention_id": "[from metadata]",
  "intervention_name": "[from metadata]",
  "protocol_version": "1.0 Draft",
  "protocol_date": "[current date]",
  "study_design": "[from Step 1]",
  "enrollment_target": "[from Step 1]",
  "primary_endpoint": "[generated in Section 4]",
  "duration_months": "[from Step 1 or generated]",
  "regulatory_pathway": "[IDE or IND]",
  "protocol_status": "foundation_complete",
  "step_2_status": "completed",
  "step_3_status": "pending",
  "step_4_status": "pending",
  "sections_completed": [1, 2, 3, 4, 5, 6],
  "sections_pending": [7, 8, 9, 10, 11, 12],
  "notes": ["DRAFT for planning purposes only"]
}
```

---

### Step 7: Update Intervention Metadata

Update `waypoints/intervention_metadata.json`:
- Add `"02-protocol-foundation"` to `completed_steps` array
- Add `protocol_template` field with path to generated protocol

---

### Step 8: Display Summary

```
✅ Step 2: Protocol Foundation - COMPLETED

Protocol: [Intervention Name] Clinical Trial Protocol v1.0 Draft

📄 Sections Generated:
  ✓ Section 1: Statement of Compliance
  ✓ Section 2: Protocol Summary
  ✓ Section 3: Introduction
  ✓ Section 4: Objectives and Endpoints
  ✓ Section 5: Study Design
  ✓ Section 6: Study Population

📁 Files Created:
  • waypoints/02_protocol_foundation.md
  • waypoints/02_protocol_metadata.json

⚠️ DRAFT: This protocol is for planning purposes only.
   Requires review by regulatory affairs, biostatistics, and clinical teams.

Next: Proceed to Step 3 (Intervention Details) to generate Sections 7-8.
```

---

## Output Files

**Created:**
- `waypoints/02_protocol_foundation.md` (~100KB - Sections 1-6, ~1,500 lines)
- `waypoints/02_protocol_metadata.json` (~1KB - protocol metadata)

**Updated:**
- `waypoints/intervention_metadata.json`

---

## Error Handling

**If waypoint files missing:**
```
Error: Required waypoint files not found.
Cannot draft protocol without previous step data.
Please run steps in order (Step 0, Step 1, then Step 2).
```

**If user declines protocol foundation:**
```
Protocol foundation skipped at user request.
Step 2 not completed - no waypoint files created.
User can return to this step later if needed.
```

**If Step 2 already completed:**
```
Warning: Step 2 appears to be already completed.
Files exist: waypoints/02_protocol_foundation.md

Would you like to:
  1. Skip Step 2 and continue to Step 3
  2. Regenerate Step 2 (will overwrite existing content)
  3. Exit
```

---

## Quality Checks

Before marking Step 2 complete:
- [ ] All 6 sections generated
- [ ] Primary endpoint clearly defined
- [ ] Inclusion/exclusion criteria complete
- [ ] Study design matches research recommendations
- [ ] Protocol metadata file created
- [ ] No placeholder text remaining (except `[TO BE DETERMINED]` for site-specific items)

---

## Notes for Claude/Copilot

1. **Use research data:** Don't invent endpoints or criteria - use research findings
2. **Be specific:** Avoid generic text - tailor to the specific intervention
3. **Include rationale:** Explain design choices based on similar trials
4. **Mark uncertainties:** Use `[TO BE DETERMINED]` for items needing sponsor input
5. **Follow regulatory standards:** Match terminology to FDA/ICH guidelines
6. **Respect token limits:** Generate in chunks if needed to stay within limits
