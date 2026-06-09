````markdown
# Notification Letter Templates

> **Purpose:** Markdown templates for approval, pend, and denial notification letters.
> **When to use:** After a decision has been made in Subskill 2.

---

## Approval Letter Template

**Output file:** `outputs/approval_letter.md`

```markdown
> **[SHIELD] AI-ASSISTED DRAFT — HUMAN REVIEW REQUIRED**
>
> This document was generated with artificial intelligence assistance and is provided
> solely for decision-support purposes. It does not constitute a final coverage
> determination or a substitute for professional clinical judgement.
>
> **All correspondence requires review and approval by authorized personnel before distribution.**

# Prior Authorization — Approved

**Authorization Number:** `{{auth_number}}`
**Date:** {{date}}
**Effective:** {{valid_from}} through {{valid_through}}

---

## 1. [PERSON] Member Information

| Field             | Value                      |
|-------------------|----------------------------|
| **Name**          | {{member_name}}            |
| **Member ID**     | `{{member_id}}`            |
| **Date of Birth** | {{member_dob}}             |

---

## 2. Approved Service

| Field               | Value                          |
|---------------------|--------------------------------|
| **Description**     | {{service_description}}        |
| **CPT/HCPCS Code**  | `{{cpt_codes}}`                |
| **ICD-10 Code**     | `{{icd10_codes}}`              |
| **Dosage**          | {{dosage}}                     |
| **Duration**        | {{duration}}                   |

---

## 3. Authorized Provider

| Field             | Value                          |
|-------------------|--------------------------------|
| **Name**          | {{provider_name}}              |
| **NPI**           | `{{provider_npi}}`             |
| **Specialty**     | {{provider_specialty}}         |

---

## 4. Authorization Details

| Field                  | Value                      |
|------------------------|----------------------------|
| **Authorization #**    | `{{auth_number}}`          |
| **Valid From**         | {{valid_from}}             |
| **Valid Through**      | {{valid_through}}          |
| **Setting**            | {{service_setting}}        |

---

## 5. Conditions and Limitations

{{conditions_and_limitations, or "No additional conditions or limitations apply to this authorization."}}

---

## 6. [INFO] Important Information

- This authorization confirms that the requested service has been reviewed and meets
  applicable coverage criteria based on the clinical information provided.
- This authorization does not guarantee payment. Payment is subject to member eligibility
  at the time of service and applicable plan terms.
- If you have questions, please contact us at {{contact_phone}} and reference
  authorization number `{{auth_number}}`.

---

*[DOCUMENT] Generated: {{date}} | Authorization: `{{auth_number}}` | Skill: pa-report-formatter v1.0*
*[SHIELD] AI-assisted draft. All correspondence requires human review and authorization before distribution.*
```

---

## Pend Letter Template

**Output file:** `outputs/pend_letter.md`

```markdown
> **[SHIELD] AI-ASSISTED DRAFT — HUMAN REVIEW REQUIRED**
>
> This document was generated with artificial intelligence assistance and is provided
> solely for decision-support purposes. It does not constitute a final coverage
> determination or a substitute for professional clinical judgement.
>
> **All correspondence requires review and approval by authorized personnel before distribution.**

# Prior Authorization — Additional Information Required

**Reference:** `{{request_id}}`
**Date:** {{date}}
**Response Deadline:** {{deadline}} (14 calendar days)

---

## 1. [PERSON] Member Information

| Field             | Value                      |
|-------------------|----------------------------|
| **Name**          | {{member_name}}            |
| **Member ID**     | `{{member_id}}`            |
| **Date of Birth** | {{member_dob}}             |

---

## 2. Requested Service

| Field               | Value                          |
|---------------------|--------------------------------|
| **Medication/Procedure** | {{service_description}}   |
| **CPT/HCPCS Code**  | `{{cpt_codes}}`                |
| **Dosage**          | {{dosage}}                     |
| **Provider**        | {{provider_name}}, {{provider_specialty}} |

---

## 3. [WARNING] Information Needed

We have reviewed the submitted prior authorization request and clinical documentation
for the above-referenced member. To complete our review, we require the following
additional information:

{{for each gap:}}

### Item {{n}} — {{gap_title}}

**What is needed:** {{gap_description}}

**Why it is needed:** {{gap_policy_basis}}

**How to submit:** {{submission_method}}

---

## 4. Submission Instructions

Please submit the requested information by **{{deadline}}** using one of the
following methods:

- **Fax:** {{fax_number}}
- **Online:** {{online_portal}}
- **Phone:** {{phone_number}}

If the requested information is not received by the deadline, this request may be
closed. A new prior authorization request may be submitted at any time with the
required information.

---

## 5. [INFO] Important Information

- This letter pertains only to the information needed to complete our review.
  It is not a coverage determination.
- If you have questions about this request, please contact us at {{contact_phone}}
  and reference `{{request_id}}`.

---

*[DOCUMENT] Generated: {{date}} | Request ID: `{{request_id}}` | Skill: pa-report-formatter v1.0*
*[SHIELD] AI-assisted draft. All correspondence requires human review and authorization before distribution.*
```

---

## Denial Letter Template

**Output file:** `outputs/denial_letter.md`

```markdown
> **[SHIELD] AI-ASSISTED DRAFT — HUMAN REVIEW REQUIRED**
>
> This document was generated with artificial intelligence assistance and is provided
> solely for decision-support purposes. It does not constitute a final coverage
> determination or a substitute for professional clinical judgement.
>
> **All correspondence requires review and approval by authorized personnel before distribution.**

# Prior Authorization — Not Authorized

**Reference:** `{{request_id}}`
**Date:** {{date}}

---

## 1. [PERSON] Member Information

| Field             | Value                      |
|-------------------|----------------------------|
| **Name**          | {{member_name}}            |
| **Member ID**     | `{{member_id}}`            |
| **Date of Birth** | {{member_dob}}             |

---

## 2. Service Not Authorized

| Field               | Value                          |
|---------------------|--------------------------------|
| **Description**     | {{service_description}}        |
| **CPT/HCPCS Code**  | `{{cpt_codes}}`                |
| **ICD-10 Code**     | `{{icd10_codes}}`              |
| **Provider**        | {{provider_name}}              |

---

## 3. [CLOSE] Reason for Decision

{{denial_reason — clear, specific, non-technical explanation}}

---

## 4. [POLICY] Policy Basis

This decision is based on the following coverage criteria:

- **Policy:** {{policy_id}} — {{policy_title}}
- **Criteria not met:**
{{for each unmet criterion:}}
  - {{criterion_name}}: {{reason_not_met}}

---

## 5. Appeal Rights

You have the right to appeal this decision. If you disagree with this determination,
you or your authorized representative may request a review.

### Internal Appeal

- **How to file:** Submit a written appeal to {{appeal_address}}
- **Deadline:** 180 calendar days from the date of this notice
- **What to include:** Member name, member ID, reference number, reason for appeal,
  and any additional clinical documentation supporting your request

### External Review

If the internal appeal is upheld, you may request an independent external review.
Information about the external review process will be provided with the internal
appeal decision.

---

## 6. [INFO] Important Information

- You may provide additional clinical information that was not available at the time
  of the initial review. New information may result in a different determination.
- If you have questions, please contact us at {{contact_phone}} and reference
  `{{request_id}}`.

---

*[DOCUMENT] Generated: {{date}} | Request ID: `{{request_id}}` | Skill: pa-report-formatter v1.0*
*[SHIELD] AI-assisted draft. All correspondence requires human review and authorization before distribution.*
```

````
