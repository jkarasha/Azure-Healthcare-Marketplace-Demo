# Step 3: Clinical Protocol Intervention Details

## Purpose

Generate the intervention-specific sections (7-8) of a clinical study protocol. Adds detailed intervention administration, dose modifications (if applicable), preparation/handling, randomization/blinding, compliance monitoring, and discontinuation procedures.

## Prerequisites

**Required Files:**
- `waypoints/intervention_metadata.json` (must contain `protocol_template` field from Step 2)
- `waypoints/01_clinical_research_summary.json`
- `waypoints/02_protocol_foundation.md` (Sections 1-6 from Step 2)
- `waypoints/02_protocol_metadata.json` (must show step_2_status: "completed")

---

## What This Subskill Does

1. Verifies Step 2 completion
2. Reads intervention metadata and research summary
3. Generates Sections 7-8 of the clinical protocol
4. Creates intervention details waypoint file
5. Updates protocol metadata

---

## Protocol Section Structure

### Sections Generated in Step 3:

```
SECTION 7: STUDY INTERVENTION
  7.1 Study Intervention(s) Administered
    7.1.1 Study Intervention Description
    7.1.2 Dosing and Administration
  7.2 Preparation/Handling/Storage/Accountability
    7.2.1 Acquisition and Accountability
    7.2.2 Formulation, Appearance, Packaging, and Labeling
    7.2.3 Product Storage and Stability
    7.2.4 Preparation
  7.3 Measures to Minimize Bias: Randomization and Blinding
  7.4 Study Intervention Compliance
  7.5 Concomitant Therapy
    7.5.1 Rescue Medicine

SECTION 8: STUDY INTERVENTION DISCONTINUATION AND WITHDRAWAL
  8.1 Discontinuation of Study Intervention
  8.2 Participant Discontinuation/Withdrawal from the Study
  8.3 Lost to Follow-Up
```

---

## Execution Flow

### Step 1: Verify Prerequisites

Read `waypoints/02_protocol_metadata.json` and verify:
- `step_2_status` is "completed"

**If Step 2 not completed:**
```
Error: Protocol foundation (Step 2) must be completed first.
Step 2 status: [current status]

Please complete Step 2 before generating intervention details.
```
Exit.

---

### Step 2: Load Context Data

Read all prerequisite files:
- Intervention metadata (type, name, description)
- Research summary (similar trial interventions)
- Protocol foundation (design, population)

Extract key information:
- Is this a device or drug?
- What dosing/use patterns were seen in similar trials?
- What are the control/comparator interventions?

---

### Step 3: Generate Intervention Sections

Generate Sections 7-8 based on intervention type:

#### For Medical Devices:

**Section 7.1 - Intervention Description:**
- Device description and components
- Mechanism of action
- Technical specifications
- Intended use environment

**Section 7.1.2 - Administration:**
- Implantation/application procedure
- Required training for investigators
- Procedure duration and setting

**Section 7.2 - Handling:**
- Device receipt and inspection
- Storage requirements
- Sterilization (if applicable)
- Accountability tracking

#### For Drugs/Biologics:

**Section 7.1 - Intervention Description:**
- Drug formulation and appearance
- Mechanism of action
- Pharmacokinetic summary

**Section 7.1.2 - Dosing:**
- Dose levels
- Route of administration
- Frequency and duration
- Dose modifications/escalation rules

**Section 7.2 - Handling:**
- Storage temperature
- Stability data
- Reconstitution instructions
- Accountability procedures

#### Section 7.3 - Randomization/Blinding (Both Types):
- Randomization method
- Stratification factors
- Blinding approach (double-blind, single-blind, open-label)
- Unblinding procedures

#### Section 7.4 - Compliance:
- Compliance monitoring methods
- Acceptable compliance threshold
- Actions for non-compliance

#### Section 7.5 - Concomitant Therapy:
- Allowed medications
- Prohibited medications
- Rescue therapy provisions

#### Section 8 - Discontinuation:
- Criteria for intervention discontinuation
- Criteria for study withdrawal
- Follow-up requirements after discontinuation
- Lost to follow-up procedures

---

### Step 4: Create Intervention Details File

**File:** `waypoints/03_protocol_intervention.md`

Write Sections 7-8 to markdown file:
- Use consistent heading hierarchy with Step 2
- Device-specific or drug-specific content as appropriate
- Target ~1,200 lines

---

### Step 5: Update Protocol Metadata

Update `waypoints/02_protocol_metadata.json`:
- Set `step_3_status` to "completed"
- Add sections 7, 8 to `sections_completed` array
- Remove sections 7, 8 from `sections_pending` array

---

### Step 6: Update Intervention Metadata

Update `waypoints/intervention_metadata.json`:
- Add `"03-protocol-intervention"` to `completed_steps` array

---

### Step 7: Display Summary

```
✅ Step 3: Intervention Details - COMPLETED

Protocol: [Intervention Name] v1.0 Draft

📄 Sections Generated:
  ✓ Section 7: Study Intervention
  ✓ Section 8: Discontinuation and Withdrawal

📁 Files Created:
  • waypoints/03_protocol_intervention.md

Protocol Progress: 8/12 sections complete (67%)

⚠️ DRAFT: Requires review by clinical operations and quality teams.

Next: Proceed to Step 4 (Operations & Statistics) to generate Sections 9-12.
```

---

## Output Files

**Created:**
- `waypoints/03_protocol_intervention.md` (Sections 7-8, ~1,200 lines)

**Updated:**
- `waypoints/02_protocol_metadata.json` (step 3 marked complete)

---

## Error Handling

**If prerequisite files missing:**
```
Error: Required waypoint files not found.
Expected:
  - waypoints/02_protocol_foundation.md (from Step 2)
  - waypoints/02_protocol_metadata.json (from Step 2)

Please ensure Steps 0, 1, and 2 are completed.
```

**If Step 3 already completed:**
```
Warning: Step 3 appears to be already completed.
Files exist: waypoints/03_protocol_intervention.md

Would you like to:
  1. Skip Step 3 and continue to Step 4
  2. Regenerate Step 3 (will overwrite existing content)
  3. Exit
```

---

## Quality Checks

Before marking Step 3 complete:
- [ ] Section 7 covers all intervention aspects
- [ ] Dosing/administration clearly specified
- [ ] Handling procedures complete
- [ ] Randomization method described
- [ ] Compliance monitoring defined
- [ ] Discontinuation criteria clear
- [ ] Content appropriate for intervention type (device vs drug)

---

## Notes for Claude/Copilot

1. **Match intervention type:** Use device terminology for devices, drug terminology for drugs
2. **Be operationally specific:** Include enough detail for site staff to follow
3. **Reference similar trials:** Use approaches seen in research findings
4. **Consider safety:** Include appropriate safety-related discontinuation criteria
5. **Stay consistent:** Match terminology from Sections 1-6
