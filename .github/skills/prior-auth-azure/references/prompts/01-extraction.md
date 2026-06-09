# Prompt Module 01: Data Extraction (NER)

> **Bead:** `bd-pa-001-intake` — Steps 1, 4
> **Purpose:** Extract structured patient, physician, and clinical data from PA request documents
> **When to load:** At the start of bead `bd-pa-001-intake`, before processing clinical documentation
> **Release after:** Context Checkpoint 1 (data captured in `waypoints/assessment.json`)

---

## Overview

This module provides structured extraction guidance for three entity categories from PA request forms, clinical notes, lab results, and imaging reports. Apply these instructions when parsing user-provided documentation to populate the `request` and `clinical` sections of `waypoints/assessment.json`.

---

## General Extraction Rules

1. **OCR Error Correction**: Use contextual clues to resolve ambiguous characters:
   - `O` vs `0`, `I` vs `1`, `S` vs `5`, `B` vs `8`, `G` vs `6`, `Z` vs `2`
   - Verify dates are in MM/DD/YYYY format
   - Verify phone numbers include area codes
   - Cross-check medical codes (ICD-10, CPT, NDC) against standard patterns

2. **Checkbox / Form Interpretation**: Identify checked boxes (checkmarks, X's, shaded boxes) and associate them with form labels.

3. **Handwritten Text**: Carefully transcribe, resolving ambiguous characters (`m` vs `nn`, `c` vs `e`) from context.

4. **Cross-Verification**: If the same data appears in multiple places, cross-check for consistency. Prefer typed over handwritten when conflicting.

5. **Missing Data**: If information is not found after thorough search, record `"Not provided"` — never fabricate values.

---

## Entity 1: Patient Information

Extract from document headers, form fields, and insurance sections.

### Fields to Extract

| Field | Description | Format |
|-------|-------------|--------|
| `patient_name` | Full name as it appears in the document | String |
| `patient_date_of_birth` | Date of birth | MM/DD/YYYY |
| `patient_id` | Insurance/member ID (e.g., Cigna ID, UHG ID) | String |
| `patient_address` | Full mailing address (street, city, state, ZIP) | String |
| `patient_phone_number` | Contact phone with area code | (123) 456-7890 |

### Output Schema

```json
{
  "patient_name": "string",
  "patient_date_of_birth": "string",
  "patient_id": "string",
  "patient_address": "string",
  "patient_phone_number": "string"
}
```

---

## Entity 2: Physician Information

Extract from letterheads, signatures, stamps, form fields, and credential sections. If multiple physicians appear, focus on the **primary treating physician** (use titles, signatures, and department context to disambiguate).

### Fields to Extract

| Field | Description | Format |
|-------|-------------|--------|
| `physician_name` | Full name with titles (e.g., "Dr. John A. Smith, MD") | String |
| `specialty` | Area of specialization (e.g., "Cardiology") | String |
| `office_phone` | Office phone with area code | (123) 456-7890 |
| `fax` | Fax number with area code | (123) 456-7890 |
| `office_address` | Full office address (street, suite, city, state, ZIP) | String |

### Output Schema

```json
{
  "physician_name": "string",
  "specialty": "string",
  "physician_contact": {
    "office_phone": "string",
    "fax": "string",
    "office_address": "string"
  }
}
```

---

## Entity 3: Clinical Information

Extract from clinical notes, lab reports, imaging reports, and PA form clinical sections. This is the most critical extraction — focus on information that will be evaluated against coverage policy criteria.

### Fields to Extract

| Field | Description |
|-------|-------------|
| `diagnosis` | Primary diagnosis and any secondary diagnoses |
| `icd_10_code` | ICD-10 code(s) — verify format (letter + 2 digits + optional decimal + digits) |
| `prior_treatments_and_results` | Complete history of prior medications/treatments and their outcomes |
| `specific_drugs_taken_and_failures` | Specific drugs tried and whether the patient failed them |
| `alternative_drugs_required` | How many and which alternative drugs the PA form requires before approval |
| `relevant_lab_results_or_imaging` | Key findings, values, dates from labs and imaging |
| `symptom_severity_and_impact` | How symptoms affect the patient's daily life |
| `prognosis_and_risk_if_not_approved` | Potential outcomes if treatment is denied |
| `clinical_rationale_for_urgency` | Why urgent approval is needed (if applicable) |

### Treatment Request Fields

| Field | Description |
|-------|-------------|
| `name_of_medication_or_procedure` | Exact name of requested treatment |
| `code_of_medication_or_procedure` | CPT, NDC, or HCPCS code — infer if not explicitly stated |
| `dosage` | Dosage with units (e.g., mg, mL) |
| `duration` | Treatment duration with specific dates if available |
| `rationale` | Why this specific treatment is being requested |
| `presumed_eligibility` | Eligibility based on PA form question answers |

### Output Schema

```json
{
  "diagnosis": "string",
  "icd_10_code": "string",
  "prior_treatments_and_results": "string",
  "specific_drugs_taken_and_failures": "string",
  "alternative_drugs_required": "string",
  "relevant_lab_results_or_imaging": "string",
  "symptom_severity_and_impact": "string",
  "prognosis_and_risk_if_not_approved": "string",
  "clinical_rationale_for_urgency": "string",
  "treatment_request": {
    "name_of_medication_or_procedure": "string",
    "code_of_medication_or_procedure": "string",
    "dosage": "string",
    "duration": "string",
    "rationale": "string",
    "presumed_eligibility": "string"
  }
}
```

### Clinical Extraction Quality Rules

- **Prior treatments**: Capture ALL medication names, dosages, duration of use, and why they were stopped (side effects, lack of efficacy, etc.)
- **Lab results**: Include key values, reference ranges, and dates
- **ICD-10 codes**: Verify format — do not accept malformed codes
- **Multiple entries**: If multiple diagnoses, treatments, or lab results exist, concatenate with clear delimiters
- **Treatment duration**: Extract specific dates, capture total duration, note any escalation/taper schedules

---

## Extraction Confidence Scoring

After extraction, assess confidence for each entity category:

| Score | Level | Meaning |
|-------|-------|---------|
| 90-100 | High | All fields found with clear, unambiguous data |
| 70-89 | Medium | Most fields found, some inference needed |
| 50-69 | Low | Significant gaps, handwriting ambiguity, or missing sections |
| <50 | Very Low | Major portions unreadable or missing — flag for human review |

Report overall extraction confidence as a weighted average:
- Patient info: 15%
- Physician info: 15%
- Clinical info: 70%

**If overall confidence < 60%, trigger the low-confidence warning per SKILL.md.**

---

## Integration with Waypoint

Map extracted data to `waypoints/assessment.json` sections:

```
Patient extraction  → assessment.request.member
Physician extraction → assessment.request.provider
Clinical extraction → assessment.clinical + assessment.request.service
```

After writing the waypoint, this prompt module's content is no longer needed in context.
