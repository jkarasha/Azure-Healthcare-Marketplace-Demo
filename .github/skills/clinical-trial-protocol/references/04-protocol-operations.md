# Step 4: Clinical Protocol Operations and Statistics

## Purpose

Generate the operational and statistical sections (9-12) of the clinical protocol, including study assessments, adverse event reporting, statistical analysis plan, and supporting documentation.

## Prerequisites

**Required Files:**
- `waypoints/intervention_metadata.json`
- `waypoints/01_clinical_research_summary.json`
- `waypoints/02_protocol_foundation.md`
- `waypoints/02_protocol_metadata.json` (must show step_3_status: "completed")
- `waypoints/03_protocol_intervention.md`

---

## What This Subskill Does

1. Verifies Step 3 completion
2. **Performs sample size calculation** (asks user for parameters, runs calculator script)
3. Reads protocol template and shared guidance
4. Synthesizes operational and statistical content for Sections 9-12
5. Creates new file `waypoints/04_protocol_operations.md` with Sections 9-12
6. Updates protocol and intervention metadata

---

## Protocol Section Structure

### Sections Generated in Step 4:

```
SECTION 9: STUDY ASSESSMENTS AND PROCEDURES
  9.1 Efficacy Assessments
  9.2 Safety Assessments
  9.3 Adverse Events and Serious Adverse Events
    9.3.1 Definition of Adverse Events
    9.3.2 Definition of Serious Adverse Events
    9.3.3 Time Period for AE Reporting
    9.3.4 AE Severity Grading
    9.3.5 Relationship to Study Intervention
    9.3.6 Reporting Procedures
    9.3.7 Follow-up of AEs
    9.3.8 Pregnancy Reporting
    9.3.9 Disease-Related Events
  9.4 Laboratory Assessments
  9.5 Schedule of Assessments

SECTION 10: STATISTICAL CONSIDERATIONS
  10.1 Statistical Hypotheses
  10.2 Sample Size Determination
    10.2.1 Sample Size Calculation Parameters
    10.2.2 Dropout and Protocol Deviation Allowances
  10.3 Analysis Populations
    10.3.1 Intent-to-Treat (ITT) Population
    10.3.2 Per-Protocol Population
    10.3.3 Safety Population
  10.4 Statistical Analyses
    10.4.1 Primary Endpoint Analysis
    10.4.2 Secondary Endpoint Analyses
    10.4.3 Interim Analyses
    10.4.4 Subgroup Analyses
    10.4.5 Missing Data Handling
  10.5 Data Safety Monitoring

SECTION 11: SUPPORTING DOCUMENTATION AND OPERATIONS
  11.1 Regulatory, Ethical, and Study Oversight
    11.1.1 Regulatory Considerations
    11.1.2 Ethical Conduct
    11.1.3 IRB/Ethics Committee
  11.2 Informed Consent Process
  11.3 Data Handling and Record Keeping
  11.4 Quality Assurance and Quality Control
  11.5 Study and Site Closure
  11.6 Publication Policy

SECTION 12: REFERENCES
```

---

## Execution Flow

### Step 1: Verify Prerequisites

Read `waypoints/02_protocol_metadata.json` and verify:
- `step_3_status` is "completed"
- All section files exist

**If Step 3 not completed:**
```
Error: Step 3 must be completed before generating operations sections.
Step 3 status: [current status]

Please complete Step 3 to generate intervention details (Sections 7-8).
```
Exit.

---

### Step 2: Sample Size Calculation (Interactive)

**Prompt user for sample size parameters:**

```
📊 Sample Size Calculation

To calculate the required sample size, I need some information:

1. Endpoint Type:
   a) Continuous (e.g., change in blood pressure, score improvement)
   b) Binary (e.g., response rate, success/failure)

Enter choice (a or b):
```

**For Continuous Endpoints:**
```
2. Expected Effect Size (mean difference between groups):
3. Expected Standard Deviation:
4. Alpha (Type I error rate, default 0.05):
5. Power (default 0.80):
6. Expected Dropout Rate (default 0.15):
```

**For Binary Endpoints:**
```
2. Expected proportion in control group (p1):
3. Expected proportion in treatment group (p2):
4. Alpha (Type I error rate, default 0.05):
5. Power (default 0.80):
6. Expected Dropout Rate (default 0.15):
```

**Run the calculator:**
```bash
python scripts/sample_size_calculator.py \
  --endpoint-type continuous \
  --effect-size [user input] \
  --std-dev [user input] \
  --alpha 0.05 \
  --power 0.80 \
  --dropout 0.15 \
  --output waypoints/02_sample_size_calculation.json
```

**If Python not available:**
```
Note: Python sample size calculator not available.
Using statistical formulas for estimation.

Estimated sample size based on research findings:
[Provide estimate from similar trials in research summary]

⚠️ Recommend verification by biostatistician.
```

---

### Step 3: Generate Section 9 (Assessments)

Generate comprehensive assessment section:

**9.1 Efficacy Assessments:**
- List all efficacy assessments aligned with endpoints
- Specify timing and method of each assessment
- Include validated instruments/scales if applicable

**9.2 Safety Assessments:**
- Vital signs schedule
- Physical examinations
- ECG monitoring (if applicable)
- Imaging (if applicable)

**9.3 Adverse Events (CRITICAL - Include ALL 9 Subsections):**
- Complete AE/SAE definitions per ICH E2A
- CTCAE grading scale reference
- Causality assessment criteria
- Reporting timelines (24 hours for SAEs)
- Follow-up requirements

**9.4 Laboratory Assessments:**
- Required lab panels
- Testing frequency
- Central vs local lab considerations

**9.5 Schedule of Assessments:**
- Create comprehensive assessment schedule table
- Visits: Screening, Baseline, Treatment, Follow-up
- Windows for each visit

---

### Step 4: Generate Section 10 (Statistics)

Use sample size calculation results:

**10.1 Statistical Hypotheses:**
- Null and alternative hypotheses
- Superiority, non-inferiority, or equivalence

**10.2 Sample Size:**
- Include calculation parameters
- Show formula used
- State N per arm and total N (adjusted for dropout)

**10.3 Analysis Populations:**
- ITT definition
- Per-protocol definition
- Safety population definition

**10.4 Statistical Analyses:**
- Primary analysis method
- Secondary analyses
- Handling of missing data (LOCF, MMRM, etc.)
- Multiplicity adjustment if needed

**10.5 DSMB:**
- Composition recommendation
- Meeting schedule
- Stopping rules

---

### Step 5: Generate Section 11 (Operations)

**11.1 Regulatory/Ethical:**
- Applicable regulations (21 CFR, ICH)
- Ethics committee requirements
- Protocol amendments process

**11.2 Informed Consent:**
- ICF requirements
- Re-consent triggers
- Assent for minors (if applicable)

**11.3 Data Handling:**
- EDC system requirements
- Source documentation
- Data retention period (typically 15 years)

**11.4 Quality Assurance:**
- Monitoring approach
- Audit provisions
- Inspection readiness

**11.5 Site Closure:**
- Criteria for site closure
- Document retention requirements

---

### Step 6: Generate Section 12 (References)

Compile references organized by category:
- Regulatory guidelines (FDA, ICH)
- Disease/indication literature
- Intervention literature
- Statistical methods
- Assessment instruments

Include 30-60 references typical for a comprehensive protocol.

---

### Step 7: Create Operations File

**File:** `waypoints/04_protocol_operations.md`

Write Sections 9-12 to markdown file.

---

### Step 8: Update Protocol Metadata

Update `waypoints/02_protocol_metadata.json`:
- Set `step_4_status` to "completed"
- Add sections 9, 10, 11, 12 to `sections_completed` array
- Update `protocol_status` to "sections_complete"
- Add `waypoint_files` object tracking all protocol section files
- Update notes

---

### Step 9: Update Intervention Metadata

Update `waypoints/intervention_metadata.json`:
- Add "04-protocol-operations" to `completed_steps` array
- Set `protocol_status` to "sections_complete"

---

### Step 10: Display Summary

```
✅ Step 4: Operations and Statistics - COMPLETED
✅ ALL PROTOCOL SECTIONS GENERATED

Intervention: [Name]
Protocol: Version 1.0 Draft ([Date])

📊 Sample Size Calculation:
  • Primary Endpoint: [Endpoint name]
  • Sample Size Per Arm: [n_per_arm]
  • Total Enrollment Target: [adjusted_n_total]
  • Power: [power]%, Alpha: [alpha]

📄 Sections Generated:
  ✓ Section 9: Study Assessments
  ✓ Section 10: Statistical Considerations
  ✓ Section 11: Supporting Documentation
  ✓ Section 12: References

Protocol Status: All 12 Sections Generated

📁 Protocol Files:
  • waypoints/02_protocol_foundation.md (Sections 1-6)
  • waypoints/03_protocol_intervention.md (Sections 7-8)
  • waypoints/04_protocol_operations.md (Sections 9-12)

⚠️ DRAFT: Requires biostatistician review and regulatory approval.

Next: Proceed to Step 5 to concatenate all sections into final protocol.
```

---

## Output Files

**Created:**
- `waypoints/04_protocol_operations.md` (Sections 9-12)
- `waypoints/02_sample_size_calculation.json` (sample size calculation results)

**Updated:**
- `waypoints/02_protocol_metadata.json` (step 4 marked complete)
- `waypoints/intervention_metadata.json` (step 4 marked complete)

---

## Error Handling

**If prerequisite files missing:**
```
Error: Required protocol section files not found.
Expected:
  - waypoints/02_protocol_foundation.md (Step 2 output)
  - waypoints/03_protocol_intervention.md (Step 3 output)

Please ensure Steps 2 and 3 are completed.
```

**If sample size calculation fails:**
```
Warning: Sample size calculation encountered an error.
[Error details]

Options:
  1. Retry with different parameters
  2. Continue with estimated sample size from similar trials
  3. Exit and resolve calculation issue
```

---

## Quality Checks

Before finalizing Step 4:
- [ ] Sample size calculation completed (or fallback with disclaimer)
- [ ] Section 9 generated with ALL 9 AE/SAE subsections
- [ ] Section 10 generated with statistical analysis plan
- [ ] Sample size section uses actual calculated values
- [ ] Section 11 includes all operational subsections
- [ ] Section 12 includes 30-60 references organized by category
- [ ] Protocol metadata updated correctly
- [ ] Intervention metadata updated correctly

---

## Notes for Claude/Copilot

- **Sample size calculation is interactive** - requires user input
- **Output stays within token limits** by focusing on Sections 9-12 only
- **AE/SAE section is critical** - must include all regulatory requirements
- **Statistical section must be specific** - use actual calculation parameters
- **References should be real** - cite actual FDA guidances and literature
