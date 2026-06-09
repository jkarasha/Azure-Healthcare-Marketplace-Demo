````markdown
# Assessment Report Template

> **Purpose:** Markdown template for the assessment report. Populate all fields from `waypoints/assessment.json`.
> **Output file:** `outputs/assessment_report.md`

---

## Template

```markdown
> **[SHIELD] AI-ASSISTED DRAFT — HUMAN REVIEW REQUIRED**
>
> This document was generated with artificial intelligence assistance and is provided
> solely for decision-support purposes. It does not constitute medical advice, a final
> coverage determination, or a substitute for professional clinical judgement.
>
> Coverage policies referenced herein are sourced from publicly available Medicare
> LCDs/NCDs. If this review pertains to a commercial, Medicaid, or Medicare Advantage
> plan, payer-specific policies may differ and were not applied.
>
> **All recommendations require review and approval by a qualified human professional
> before any action is taken.**

# Prior Authorization Assessment Report

## 1. Executive Summary

| Field                  | Value                                          |
|------------------------|------------------------------------------------|
| **Request ID**         | `{{request_id}}`                               |
| **Review Date**        | {{created}}                                    |
| **Reviewed By**        | AI-Assisted (Draft for Human Review)           |
| **Member**             | {{member_name}} (ID: `{{member_id}}`)          |
| **Service**            | {{service_description}}                        |
| **CPT Code(s)**        | `{{cpt_codes}}`                                |
| **ICD-10 Code(s)**     | `{{icd10_codes}}`                              |
| **Provider**           | {{provider_name}}, {{provider_specialty}}       |
| **NPI**                | `{{provider_npi}}`                             |
| **Decision**           | **{{recommendation_decision}}**                |
| **Confidence**         | {{confidence_bar}} {{confidence_score}}%  {{confidence_level}} |
| **Criteria Met**       | {{criteria_met}} ({{criteria_percentage}}%)     |

### Decision Rationale

{{recommendation_rationale}}

---

## 2. Request Details

### 2.1 [PERSON] Member Information

| Field             | Value                      |
|-------------------|----------------------------|
| **Name**          | {{member_name}}            |
| **Member ID**     | `{{member_id}}`            |
| **Date of Birth** | {{member_dob}}             |
| **Sex**           | {{member_sex}}             |
| **Age**           | {{member_age}}             |
| **State**         | {{member_state}}           |
| **Address**       | {{member_address}}         |

### 2.2 [STETHOSCOPE] Provider Information

| Field             | Value                              |
|-------------------|------------------------------------|
| **Name**          | {{provider_name}}                  |
| **NPI**           | `{{provider_npi}}`                 |
| **Specialty**     | {{provider_specialty}}             |
| **Verified**      | {{provider_verified_status}}       |
| **Office Phone**  | {{provider_phone}}                 |
| **Address**       | {{provider_address}}               |

{{if provider not verified:}}
> **[WARNING] Provider Verification Note**
>
> {{provider_verification_note}}

### 2.3 Service Information

| Field               | Value                          |
|---------------------|--------------------------------|
| **Description**     | {{service_description}}        |
| **CPT/HCPCS**       | `{{cpt_codes}}`                |
| **ICD-10**          | `{{icd10_codes}}`              |
| **Dosage**          | {{service_dosage}}             |
| **Frequency**       | {{service_frequency}}          |
| **Duration**        | {{service_duration}}           |
| **Setting**         | {{service_setting}}            |

---

## 3. Validation Results

| Connector                | Status      | Details                            |
|--------------------------|-------------|------------------------------------|
| [STETHOSCOPE] NPI Registry | {{status}} | {{npi_details}}                    |
| [CLINICAL] ICD-10          | {{status}} | {{icd10_details}}                  |
| [POLICY] CMS Coverage      | {{status}} | {{cms_coverage_details}}           |
| [POLICY] Medical Necessity  | {{status}} | {{medical_necessity_details}}      |
| [SCIENCE] PubMed Literature | {{status}} | {{pubmed_details}}                |

> **[INFO] Note:** {{coverage_limitation_note}}

---

## 4. [CLINICAL] Clinical Synopsis

### 4.1 Diagnoses

- **Primary:** {{primary_diagnosis}}
- **Current Status:** {{current_status}}

### 4.2 Key Findings

{{for each finding:}}
- {{finding}}

### 4.3 Prior Treatments

| Phase            | Duration       | Agents                    | Outcome         |
|------------------|----------------|---------------------------|-----------------|
| {{phase_name}}   | {{duration}}   | {{agents}}                | {{outcome}}     |

### 4.4 Current Clinical Presentation

{{symptom_severity_and_impact}}

{{prognosis_and_risk_if_not_approved}}

---

## 5. [POLICY] Policy Analysis

### 5.1 Coverage Framework

{{policy_analysis_narrative}}

### 5.2 Criteria Evaluation

| #  | Criterion                        | Status    | Confidence                       | Evidence                     |
|----|----------------------------------|-----------|----------------------------------|------------------------------|
| 1  | {{criterion_name}}               | [CHECK]   | [=================---] 85%       | {{evidence_summary}}         |

### 5.3 Criteria Summary

**Criteria Met: {{criteria_met_count}}/{{criteria_total}} ({{criteria_percentage}}%)**

{{criteria_summary_bar}}

---

## 6. [SCIENCE] Literature Support

### 6.1 Search Summary

| Field               | Value                              |
|---------------------|------------------------------------|
| **Search Query**    | {{pubmed_query}}                   |
| **Articles Found**  | {{articles_found}}                 |
| **Category**        | Therapy                            |

### 6.2 Key Citations

{{for each citation:}}

**{{n}}. {{authors}} ({{year}})** — PMID `{{pmid}}`
> *{{title}}*
>
> **Finding:** {{finding}}
> **Relevance:** {{relevance}}

---

## 7. [CHART] Recommendation

### 7.1 Decision: **{{decision}}**

### 7.2 Confidence Calculation

| Component              | Weight | Score  | Weighted | Bar                         |
|------------------------|--------|--------|----------|-----------------------------|
| Provider Verification  | 20%    | {{}}%  | {{}}     | {{bar}}                     |
| Code Validation        | 15%    | {{}}%  | {{}}     | {{bar}}                     |
| Coverage Policy Match  | 20%    | {{}}%  | {{}}     | {{bar}}                     |
| Clinical Criteria      | 35%    | {{}}%  | {{}}     | {{bar}}                     |
| Documentation Quality  | 10%    | {{}}%  | {{}}     | {{bar}}                     |
| **Overall**            |        |        | **{{}}** | {{bar}}                     |

### 7.3 Rationale

{{rationale_detail}}

### 7.4 Clinical Strength Assessment

{{clinical_strength}}

---

## 8. [WARNING] Identified Gaps

| #  | Gap Description                  | Critical | Action Required                  |
|----|----------------------------------|----------|----------------------------------|
| 1  | {{gap_description}}              | {{y/n}}  | {{action}}                       |

---

## 9. [DOCUMENT] Document Metadata

| Field              | Value                              |
|--------------------|------------------------------------|
| **Generated**      | {{timestamp}}                      |
| **Request ID**     | `{{request_id}}`                   |
| **Skill**          | pa-report-formatter v1.0          |
| **Source**         | waypoints/assessment.json          |
| **Bead Status**    | {{bead_summary}}                   |

---

*[DOCUMENT] Generated: {{date}} | Request ID: `{{request_id}}` | Skill: pa-report-formatter v1.0*
*[SHIELD] AI-assisted draft. All content requires human review before use.*
```

````
