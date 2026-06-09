# Prompt Module 02: Policy Retrieval & Evaluation

> **Bead:** `bd-pa-001-intake` — Steps 2c, 3
> **Purpose:** Optimize coverage policy search queries and evaluate retrieved policy relevance
> **When to load:** During bead `bd-pa-001-intake`, before CMS coverage tool calls (typically before Step 2c in Subskill 1)
> **Release after:** Context Checkpoint 1 (best policy captured in `waypoints/assessment.json`)

---

## Overview

This module guides three sequential operations for finding the best matching coverage policy:
1. **Query classification** — determine search strategy (keyword vs semantic)
2. **Query expansion** — generate an optimized search query with synonyms and medical codes
3. **Result evaluation** — assess retrieved policies for relevance and completeness

---

## Step 1: Query Classification

Before searching, classify the search intent to select the optimal strategy.

### Classification Rules

| Classification | When to Apply | Examples |
|---------------|---------------|----------|
| **keyword** | Short, specific, identifier-based — exact terms, codes, product names | "Policy for Adalimumab for Crohn's Disease", "Crohn's Disease", "L34567" |
| **semantic** | Natural language, exploratory, contextual, requires interpretation | "What is the process for prior authorization for Humira?", "Best therapy for Crohn's Disease based on 2023 guidelines" |

### Decision Logic

1. Contains specific codes, proper nouns, or unique identifiers → `keyword`
2. Written as a question, conversational, or requires interpretation → `semantic`
3. Contains both specific terms AND natural language → `semantic`
4. Incomplete or ambiguous → `semantic`

### Output

```json
{ "classification": "keyword" | "semantic" }
```

---

## Step 2: Query Expansion

Generate an optimized search query that maximizes recall while maintaining precision. Use the extracted clinical data as input.

### Input Fields

From request intake data (and clinical extraction if already available):
- **Diagnosis**: Primary diagnosis and ICD-10 code(s)
- **Medication/Procedure**: Requested treatment name and code(s)
- **Dosage**: Planned dosage (if available)
- **Duration**: Treatment duration (if available)
- **Rationale**: Clinical justification or service summary

### Expansion Techniques

1. **Synonym expansion**: Generate alternative names for both diagnosis and treatment
   - Diagnosis: Include formal name, abbreviations, related conditions
   - Treatment: Include brand name, generic name, drug class, mechanism of action
2. **Code inclusion**: Add ICD-10, CPT, NDC codes and their descriptions
3. **Related concepts**: Include related clinical terms that policies commonly reference
   - "refractory", "drug-resistant", "adjunctive therapy", "specialty medication", "step therapy", "prior treatment failure"
4. **Precision anchoring**: Keep the query focused on the specific diagnosis-treatment pair to avoid false positives

### Example

**Input:**
- Diagnosis: Lennox-Gastaut Syndrome
- Medication: Epidiolex
- Code: Not provided
- Dosage: 100 mg/mL
- Duration: 2.5mg/kg/day increasing to 5mg/kg/day

**Expanded Query:**
```
Prior authorization policy for Epidiolex (cannabidiol) for Lennox-Gastaut Syndrome (LGS).
Related terms: severe childhood epilepsy, drug-resistant seizures, anti-epileptic drugs (AEDs),
CBD-based seizure medication, dosage escalation from 2.5 mg/kg/day to 5 mg/kg/day,
patient with uncontrolled seizures despite multiple AED trials.
```

### Output

```json
{ "optimized_query": "expanded query string" }
```

### Insufficient Data Handling

If neither diagnosis nor medication/procedure is available:
```json
{ "optimized_query": "Need more information to construct the query." }
```
If codes are missing but diagnosis and medication are available, proceed without codes.

---

## Step 3: Policy Result Evaluation

After the CMS coverage tools return results, evaluate each policy for relevance.

### Evaluation Process

For each retrieved policy:

1. **Check direct relevance**: Does it mention the specific medication/procedure AND the diagnosis?
2. **Check criteria completeness**: Does it include coverage criteria, dosage requirements, or authorization guidelines?
3. **Cross-reference**: If multiple policies match, keep the most comprehensive and current version
4. **Deduplication**: Remove duplicate or superseded policies

### Decision Rules

| Action | When |
|--------|------|
| **Approve** | Policy explicitly references the diagnosis + treatment + PA criteria |
| **Reject** | Policy doesn't mention the diagnosis, treatment, or PA requirements |
| **Retry** | No approved policies found, or critical details missing from all results |

### Document Reasoning

For each policy:
```
"Content from [source] was approved because it mentions prior authorization
criteria for [medication] in [condition]."

"Content from [source] was rejected because it did not reference [condition]
or prior authorization."
```

### Output

```json
{
  "policies": ["path/to/approved/policy1", "path/to/approved/policy2"],
  "reasoning": ["Approval/rejection reason for each policy"],
  "retry": false
}
```

Set `retry: true` if:
- No policies mention the specific condition or medication
- Critical authorization criteria are missing from all results
- A broader or more specific search query is needed

---

## Integration with Waypoint

Map the best matching policy to `waypoints/assessment.json`:

```
Best approved policy → assessment.policy.policy_id, policy_title, policy_type
Policy criteria list → assessment.policy.covered_indications
```

After writing the waypoint, this prompt module's content is no longer needed in context.
