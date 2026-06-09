# Sample Outputs

Reference examples of workflow-generated artifacts. These are committed to the
repo so new contributors can see what PA workflow output looks like without
running a full workflow.

> **Live run outputs go to `.runs/`** — see [`.runs/README.md`](../../.runs/README.md).

## Contents

### `outputs/` — Formatted Reports & Letters

| File | Description |
|------|-------------|
| `assessment_report.md` | Formatted PA assessment with criteria evaluation, evidence, and recommendations |
| `audit_justification.md` | Audit-ready justification document for regulatory compliance |
| `pend_letter.md` | Sample PEND notification letter (gaps requiring additional information) |

### `waypoints/` — Structured Checkpoint Data

| File | Description |
|------|-------------|
| `assessment.json` | Subskill 1 output — member, service, provider, clinical extraction, criteria evaluation, recommendation |

## Source Case

These samples were generated from case `003/a` (Blinatumomab for pediatric MRD+ B-ALL).
The case PENDs due to an invalid NPI despite meeting all 8/8 clinical criteria.
