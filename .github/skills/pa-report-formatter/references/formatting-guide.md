````markdown
# Formatting Guide — PA Report Formatter

> **Purpose:** Definitive reference for document styling, icon tokens, layout rules, and structural patterns.
> **When to load:** Before generating any formatted output document.
> **Scope:** Applies to all documents produced by the `pa-report-formatter` skill.

---

## 1. Disclaimer Banner

Every document **must** open with this banner. It is non-negotiable and non-customizable.

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
```

---

## 2. Icon Token Reference

Use **only** the tokens below. Never use Unicode emoji, emoticons, or pictographs.

### Status Icons

| Token | Renders As | When to Use |
|-------|-----------|-------------|
| `[CHECK]` | Passed / Met | Criterion met, validation passed, item complete |
| `[CLOSE]` | Failed / Not met | Criterion not met, validation failed |
| `[WARNING]` | Attention needed | Gaps, caveats, low confidence items |
| `[INFO]` | Informational | Contextual notes, non-critical observations |
| `[PENDING]` | Awaiting action | Pend decisions, items requiring follow-up |

### Domain Icons

| Token | Renders As | When to Use |
|-------|-----------|-------------|
| `[PERSON]` | Member/Patient | Member information headers and fields |
| `[STETHOSCOPE]` | Provider | Provider information headers and fields |
| `[CLINICAL]` | Clinical data | Clinical synopsis, findings, lab results |
| `[POLICY]` | Policy/Coverage | Policy analysis, criteria evaluation |
| `[SCIENCE]` | Literature | PubMed citations, evidence-based support |
| `[DOCUMENT]` | Document/File | File references, report metadata |
| `[SHIELD]` | Compliance | Disclaimers, audit notes, security |
| `[CLOCK]` | Time/Duration | Dates, turnaround times, valid periods |
| `[CHART]` | Metrics | Confidence scores, percentages, calculations |

### Decision Icons

| Token | Renders As | When to Use |
|-------|-----------|-------------|
| `[APPROVED]` | Approved | Approval decisions, authorized items |
| `[DENIED]` | Denied | Denial decisions (human-only) |
| `[PENDING]` | Pending | Pend decisions, awaiting information |
| `[VERIFIED]` | Verified | Confirmed validations |

---

## 3. Confidence Visualization

Render confidence scores as text-based progress bars.

### Format

```
[============--------] 60%  MEDIUM
[================----] 80%  HIGH
[======--------------] 30%  LOW
[====================] 100% HIGH
```

**Rules:**
- Bar width: exactly 20 characters
- Filled character: `=`
- Unfilled character: `-`
- Calculate filled count: `round(score / 5)`
- Append percentage and level label
- Level thresholds: LOW < 60%, MEDIUM 60–79%, HIGH >= 80%

### Weighted Confidence Table Format

```
| Component              | Weight | Score | Weighted | Bar                         |
|------------------------|--------|-------|----------|-----------------------------|
| Provider Verification  | 20%    | 100%  | 20.0     | [====================] 100% |
| Code Validation        | 15%    | 95%   | 14.25    | [====================-] 95% |
| Coverage Policy Match  | 20%    | 80%   | 16.0     | [================----] 80%  |
| Clinical Criteria      | 35%    | 92%   | 32.2     | [==================--] 92%  |
| Documentation Quality  | 10%    | 88%   | 8.8      | [==================--] 88%  |
| **Overall**            |        |       | **91.25**| [==================--] 91%  |
```

---

## 4. Section Structure — Assessment Report

```
DISCLAIMER BANNER

# Prior Authorization Assessment Report

## 1. Executive Summary
   Table: Request ID, Review Date, Member, Service, Provider, Decision, Confidence

## 2. Request Details
   ### 2.1 [PERSON] Member Information
   ### 2.2 [STETHOSCOPE] Provider Information
   ### 2.3 Service Information

## 3. Validation Results
   Table: Connector | Status | Details
   Use [CHECK], [CLOSE], [WARNING] tokens for status column

## 4. [CLINICAL] Clinical Synopsis
   ### 4.1 Diagnoses
   ### 4.2 Key Findings
   ### 4.3 Prior Treatments
   Table: Phase | Duration | Agents | Outcome
   ### 4.4 Current Status

## 5. [POLICY] Policy Analysis
   ### 5.1 Coverage Framework
   ### 5.2 Criteria Evaluation
   Table: # | Criterion | Status | Confidence | Evidence
   Status column uses [CHECK] / [CLOSE] / [WARNING] tokens
   ### 5.3 Criteria Summary Bar

## 6. [SCIENCE] Literature Support (if available)
   ### 6.1 Search Summary
   ### 6.2 Key Citations
   Numbered list with PMID, title, finding, relevance

## 7. [CHART] Recommendation
   ### 7.1 Decision
   ### 7.2 Confidence Calculation
   Weighted confidence table with bars
   ### 7.3 Rationale
   ### 7.4 Clinical Strength Assessment

## 8. [WARNING] Identified Gaps (if any)
   Table: # | Gap | Critical | Action Required

## 9. [DOCUMENT] Document Metadata
   Generation timestamp, request ID, skill version, reviewer attribution
   Repeat disclaimer in abbreviated form
```

---

## 5. Section Structure — Notification Letters

### Approval Letter

```
DISCLAIMER BANNER

# Prior Authorization — Approved

**Authorization Number:** `PA-XXXXXXXX-XXXXX`
**Effective:** [start] through [end]

---

## 1. [PERSON] Member Information
## 2. Approved Service
## 3. Authorized Provider
## 4. Authorization Details
## 5. Conditions and Limitations (if any)
## 6. [INFO] Important Information
   - Reminder that this is AI-assisted draft pending human confirmation
   - Contact information
## 7. [DOCUMENT] Metadata
```

### Pend Letter

```
DISCLAIMER BANNER

# Prior Authorization — Additional Information Required

**Reference:** `PA-XXXXXXXX-XXXXX`
**Response Deadline:** [date + 14 calendar days]

---

## 1. [PERSON] Member Information
## 2. Requested Service
## 3. [WARNING] Information Needed
   Numbered list of gaps with:
   - What is needed
   - Why it is needed (policy basis)
   - How to submit
## 4. Submission Instructions
## 5. [INFO] Important Information
## 6. [DOCUMENT] Metadata
```

### Denial Letter

```
DISCLAIMER BANNER

# Prior Authorization — Not Authorized

**Reference:** `PA-XXXXXXXX-XXXXX`

---

## 1. [PERSON] Member Information
## 2. Service Not Authorized
## 3. [CLOSE] Reason for Decision
## 4. [POLICY] Policy Basis
## 5. Appeal Rights
   Clear instructions for both internal and external appeal
## 6. [INFO] Important Information
## 7. [DOCUMENT] Metadata
```

---

## 6. Table Formatting Rules

- **Header row:** Always bold with pipe separators
- **Alignment:** Left-align text, right-align numbers
- **Status cells:** Use icon tokens, not colored text or emoji
- **Empty cells:** Write `—` (em dash), never leave blank
- **Max columns:** 6 (split into multiple tables if more needed)
- **Code values:** Always wrap in backticks: `J9039`, `C91.00`, `1234567890`

---

## 7. Prohibited Patterns

The following are **strictly prohibited** in all output documents:

| Prohibited | Use Instead |
|------------|-------------|
| Unicode emoji (🔍, ✅, ❌, ⚠️, 📋, etc.) | Material icon tokens (`[CHECK]`, `[CLOSE]`, etc.) |
| Emoji in headers | Icon tokens or plain text |
| Colored text / HTML | Standard Markdown only |
| Placeholder text (`{{FIELD}}`, `[TBD]`) | Actual data or "Not available" |
| Unexplained abbreviations | Define on first use |
| Inline footnotes | Use subsection or parenthetical |
| More than one `# H1` per document | Single H1, use `## H2` for sections |

---

## 8. Tone and Voice

- **Professional:** Formal but accessible. Suitable for clinical and administrative audiences.
- **Objective:** Present facts and evidence without advocacy. Let the data speak.
- **Precise:** Use specific values, dates, and references. Avoid vague qualifiers ("somewhat," "fairly").
- **Transparent:** Clearly label what is AI-generated vs. source data. Flag uncertainty explicitly.
- **Empathetic in correspondence:** Notification letters should be respectful of the patient's situation while maintaining professional clarity.

---

## 9. Footer Template

Every document ends with:

```markdown
---

*[DOCUMENT] Generated: YYYY-MM-DD | Request ID: PA-XXXXXXXX | Skill: pa-report-formatter v1.0*
*[SHIELD] AI-assisted draft. All content requires human review before use.*
```

````
