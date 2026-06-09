````skill
---
name: pa-report-formatter
description: "Formats prior authorization assessment and decision outputs into clean, professional documents using consistent structure, material-style iconography, and proper AI-assistance disclaimers."
---

# PA Report Formatter Skill

Transform raw prior authorization assessment data (`waypoints/assessment.json`, `waypoints/decision.json`) into polished, human-readable reports suitable for clinical review, audit trails, and regulatory documentation.

**Target Users:** Utilization management teams, medical directors, compliance officers, clinical reviewers

**Key Features:**
- Consistent document structure across all report types
- Material Design-inspired iconography (no emoji)
- Prominent AI-assistance disclaimers and human-review callouts
- Structured section numbering for easy cross-referencing
- Confidence visualization with progress bars
- Clean typography hierarchy
- Audit-ready formatting with traceability metadata

---

## Important Disclaimers

> **AI-ASSISTED OUTPUT:** Documents produced by this skill are generated with AI assistance and are provided for informational and decision-support purposes only. They do not constitute medical advice, clinical judgement, or a final coverage determination.
>
> **HUMAN REVIEW MANDATORY:** Every document produced must be reviewed, validated, and approved by a qualified human professional before distribution or use in any clinical, administrative, or regulatory process.
>
> **NOT A REPLACEMENT FOR PROFESSIONAL JUDGEMENT:** This tool augments — but never replaces — the expertise of licensed clinicians, utilization management professionals, and compliance officers. All final decisions remain the sole responsibility of the reviewing organization and its authorized personnel.

---

## Prerequisites

### Required Inputs

This skill operates on the output of the `prior-auth-azure` skill. It requires:

1. **Assessment waypoint** — `waypoints/assessment.json` (from Subskill 1)
2. **Decision waypoint** — `waypoints/decision.json` (from Subskill 2, if available)

If only the assessment waypoint exists, the skill generates the assessment report and audit justification. If the decision waypoint is also present, it additionally generates the determination report and notification letter.

### No MCP Servers Required

This is a formatting-only skill. It reads structured data from waypoint files and produces formatted documents. No external API calls are made.

---

## Design System

### Iconography — Material Design Tokens

This skill uses **text-based Material Design icon tokens** instead of emoji. Icons are rendered as bracketed labels that map to Material Symbols. This ensures consistent rendering across all platforms and output targets (PDF, print, screen, assistive technology).

**Icon Reference Table:**

| Token | Meaning | Usage Context |
|-------|---------|---------------|
| `[CHECK]` | Criterion met / Validation passed | Criteria tables, validation results |
| `[CLOSE]` | Criterion not met / Validation failed | Criteria tables, validation results |
| `[WARNING]` | Caution / Needs attention | Gaps, low confidence, disclaimers |
| `[INFO]` | Informational note | Context notes, plan-specific caveats |
| `[PERSON]` | Patient / Member | Member information sections |
| `[STETHOSCOPE]` | Provider / Physician | Provider information sections |
| `[CLINICAL]` | Clinical data / Assessment | Clinical synopsis, findings |
| `[POLICY]` | Coverage policy / Regulation | Policy analysis sections |
| `[SCIENCE]` | Literature / Evidence | PubMed citations, evidence support |
| `[VERIFIED]` | Verified / Confirmed | Successful validations |
| `[PENDING]` | Pending / Awaiting action | Pend decisions, open items |
| `[APPROVED]` | Approved / Authorized | Approval decisions |
| `[DENIED]` | Denied / Rejected | Denial decisions |
| `[DOCUMENT]` | Document / Report | File references, output summaries |
| `[SHIELD]` | Security / Compliance | Disclaimers, audit notes |
| `[CLOCK]` | Time / Duration | Turnaround, valid dates |
| `[CHART]` | Metrics / Confidence | Confidence scores, percentages |

### Typography Hierarchy

```
# H1 — Document title (one per document)
## H2 — Major sections (numbered: 1, 2, 3...)
### H3 — Subsections
#### H4 — Detail groups (used sparingly)
**Bold** — Field labels, key terms
*Italic* — Supplementary context, caveats
`Monospace` — Codes (ICD-10, CPT, NPI, auth numbers)
```

### Structural Rules

1. **Section numbering:** All major sections use sequential numbers (1, 2, 3...)
2. **Consistent field labels:** Use `Label:` format with bold, followed by value
3. **Tables over bullet lists:** When comparing structured data, prefer tables
4. **Horizontal rules:** Use `---` only between major sections, never within
5. **No emoji:** Replace all emoji with material icon tokens from the table above
6. **Quote blocks:** Reserved exclusively for disclaimers and important notices
7. **Confidence bars:** Render as `[===========-------] 73%` (filled/unfilled proportional)

---

## Report Types

### 1. Assessment Report

**Output:** `outputs/assessment_report.md`
**Input:** `waypoints/assessment.json`
**When:** After Subskill 1 completes

Sections:
1. Disclaimer banner
2. Executive summary
3. Request details (member, service, provider)
4. Validation results
5. Clinical synopsis
6. Policy analysis & criteria evaluation
7. Literature support (if available)
8. Recommendation
9. Identified gaps (if any)
10. Document metadata

### 2. Audit Justification

**Output:** `outputs/audit_justification.md`
**Input:** `waypoints/assessment.json`
**When:** After Subskill 1 completes (generated alongside assessment report)

Extended version of the assessment report with additional compliance elements:
- Confidence calculation breakdown
- Complete evidence chain per criterion
- Regulatory compliance notes
- Full bead tracking audit trail

### 3. Determination Report

**Output:** `outputs/determination_report.md`
**Input:** `waypoints/decision.json` + `waypoints/assessment.json`
**When:** After Subskill 2 completes

Sections:
1. Disclaimer banner
2. Decision summary
3. Authorization details (if approved)
4. Decision rationale
5. Override documentation (if applicable)
6. Audit trail

### 4. Notification Letter

**Output:** `outputs/approval_letter.md` | `outputs/pend_letter.md` | `outputs/denial_letter.md`
**Input:** `waypoints/decision.json` + `waypoints/assessment.json`
**When:** After Subskill 2 completes

Professional correspondence formatted per decision outcome.

---

## Execution Flow

### Step 1: Load Waypoint Data

Read `waypoints/assessment.json`. If `waypoints/decision.json` also exists, read it too.

Validate that required fields are present:
- `request.member`, `request.service`, `request.provider`
- `clinical`, `criteria_evaluation`, `recommendation`

### Step 2: Select Report Template

Based on available data:
- Assessment only → Generate assessment report + audit justification
- Assessment + Decision → Generate all four report types

### Step 3: Apply Formatting

Read the formatting guide at `references/formatting-guide.md` and apply:
- Replace all emoji with material icon tokens
- Apply consistent section numbering
- Render confidence bars
- Insert disclaimer banners
- Format tables with consistent column widths

### Step 4: Write Output Files

Write formatted documents to the `outputs/` directory. Confirm file creation.

### Step 5: Display Summary

Show list of generated files with brief description of each.

---

## Implementation Requirements

1. **Always read formatting guide:** Load `references/formatting-guide.md` before generating any output.
2. **No emoji in output:** Strictly use material icon tokens. Scan output before writing to confirm.
3. **Disclaimer on every document:** The AI-assistance disclaimer banner must appear at the top of every generated document, without exception.
4. **Waypoints are source of truth:** Only use data from waypoint JSON files. Never fabricate or infer data not present in the waypoints.
5. **Consistent structure:** Follow the section ordering defined in the templates exactly. Do not reorder, merge, or skip sections.
6. **Zero placeholders:** Every field in the output must be populated with actual data. If data is missing from the waypoint, write "Not available" — never leave template placeholders.

---

## Quality Checks

Before completing the formatting workflow:

- [ ] All generated documents contain the AI-assistance disclaimer banner at the top
- [ ] No emoji characters appear anywhere in the output
- [ ] All sections are numbered consistently
- [ ] All data fields populated from waypoint data (no placeholders)
- [ ] Criteria table includes every criterion from `criteria_evaluation`
- [ ] Confidence bars render correctly
- [ ] Output files written to `outputs/` directory
- [ ] Document metadata (generation date, request ID) present at footer

````
