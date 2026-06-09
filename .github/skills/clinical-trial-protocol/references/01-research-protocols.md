# Step 1: Research Similar Clinical Protocols and Evidence

## Purpose
Research similar clinical trials, FDA guidance documents, and published protocols to inform clinical protocol development.

## Prerequisites
**Required Files:** `waypoints/intervention_metadata.json`
**Required Tools:** `mcp-clinical-research` server (ClinicalTrials tools)

---

## Status Reporting Protocol

Throughout this step, provide clear status updates to the user:

```
📊 Research Progress
├── Similar Trials Search: [Searching.../Complete]
├── FDA Guidance Search: [Searching.../Complete]
├── Protocol Analysis: [In Progress/Complete]
└── Summary Generation: [Pending/Complete]
```

---

## Execution Flow

### Step 1: Read Intervention Metadata

Read `waypoints/intervention_metadata.json` and extract:
- `intervention_type` (device or drug)
- `intervention_name`
- `indication`
- `target_population`

**If file doesn't exist:**
```
Error: Intervention metadata not found.
Please run Step 0 (Initialize Intervention) first.
```
Exit and return to main menu.

---

### Step 2: Search Similar Trials

**Inform user:** "Searching ClinicalTrials.gov via mcp-clinical-research (ClinicalTrials tools)..."

Use the `trials_search` MCP tool to find relevant trials:

```python
trials_search(
    condition="[indication from metadata]",
    intervention="[intervention_name from metadata]",
    status="all",  # Include completed trials for learning
    max_results=50
)
```

**After success:** "✅ ClinicalTrials search completed - Found [N] similar trials"

**Search Strategy:**
1. Primary search: Exact condition + intervention type
2. Secondary search: Broader condition terms if primary yields <10 results
3. Tertiary search: Related indications or mechanisms of action

---

### Step 3: Get Trial Details

For the top 10 most relevant trials, retrieve detailed information:

```python
for nct_id in top_trials:
    trials_details(nct_id=nct_id)
```

**Extract from each trial:**
- Study design (randomization, blinding, arms)
- Primary and secondary endpoints
- Inclusion/exclusion criteria patterns
- Sample size and statistical approach
- Duration and follow-up periods
- Safety monitoring approach

---

### Step 4: Search for FDA Guidance

**CONSTRAINT: Use ONLY ClinicalTrials.gov MCP Server** - Do not perform generic web searches.

**Primary Source:** ClinicalTrials.gov MCP Server
- Use `trials_details` to retrieve protocol documents for relevant NCT IDs
- Extract protocol structure, endpoint definitions, inclusion/exclusion criteria

**Extract:** Protocol structure, endpoint definitions, statistical analysis plans, visit schedules, safety monitoring.

---

### Step 5: Synthesize Research Findings

Create a structured summary of findings:

1. **Similar Trial Patterns**
   - Common study designs used
   - Typical sample sizes
   - Standard endpoints
   - Duration benchmarks

2. **Regulatory Insights**
   - Recommended pathway (IDE vs IND, 510(k) vs PMA)
   - Required safety data
   - Pivotal trial requirements

3. **Design Recommendations**
   - Suggested study design
   - Recommended endpoints
   - Sample size considerations
   - Key inclusion/exclusion criteria

---

### Step 6: Update Intervention Metadata

Update `waypoints/intervention_metadata.json`:
- Add `"01-research-protocols"` to `completed_steps` array
- Add regulatory pathway recommendation
- Add protocol template reference (if FDA guidance found)

---

### Step 7: Write Research Summary

Create `waypoints/01_clinical_research_summary.json`:

```json
{
  "intervention_id": "[from metadata]",
  "research_date": "YYYY-MM-DD",
  "similar_trials": {
    "total_found": 50,
    "analyzed": 10,
    "trials": [
      {
        "nct_id": "NCT12345678",
        "title": "Trial title",
        "phase": "Phase 2",
        "status": "Completed",
        "enrollment": 200,
        "design": "Randomized, double-blind, placebo-controlled",
        "primary_endpoint": "...",
        "duration": "12 months",
        "relevance_score": 0.95,
        "key_learnings": ["..."]
      }
    ]
  },
  "regulatory_pathway": {
    "recommended": "IDE" or "IND",
    "rationale": "...",
    "submission_type": "PMA" or "510(k)" or "NDA" or "BLA",
    "guidance_documents": ["..."]
  },
  "protocol_recommendations": {
    "study_design": "Randomized, controlled trial",
    "blinding": "Double-blind" or "Open-label",
    "arms": ["Treatment", "Control/Placebo"],
    "primary_endpoint": {
      "name": "...",
      "measurement": "...",
      "timepoint": "..."
    },
    "secondary_endpoints": ["..."],
    "sample_size_range": {"min": 100, "max": 300},
    "duration_months": 12,
    "key_inclusion": ["..."],
    "key_exclusion": ["..."]
  },
  "research_status": "complete"
}
```

---

### Step 8: Display Research Summary

Display a formatted summary for the user:

```
✅ Research Complete

📊 Similar Trials Analysis
  • Trials Found: [N] relevant trials
  • Most Similar: [NCT ID] - [Title]
  • Common Design: [Design pattern]
  • Typical Sample Size: [Range]

🏛️ Regulatory Pathway
  • Recommended: [IDE/IND]
  • Submission Type: [PMA/510(k)/NDA/BLA]
  • Key Guidance: [Document name]

📋 Protocol Recommendations
  • Study Design: [Design]
  • Primary Endpoint: [Endpoint]
  • Estimated N: [Sample size]
  • Duration: [Months] months

Would you like to:
  1. Continue to protocol generation (Step 2)
  2. View detailed research summary
  3. Exit and review findings
```

---

## Output Files

| File | Size | Content |
|------|------|---------|
| `waypoints/01_clinical_research_summary.json` | ~10-15KB | Research findings |
| `waypoints/intervention_metadata.json` | Updated | With regulatory info |

---

## Quality Checks

Before proceeding to Step 2:
- [ ] At least 5 similar trials analyzed
- [ ] Regulatory pathway determined
- [ ] Primary endpoint recommendation provided
- [ ] Sample size range estimated
- [ ] Research summary file created

---

## Notes for Claude/Copilot

1. **Parallel searches when possible:** Run condition and intervention searches together
2. **Prioritize relevance:** Focus on trials most similar to user's intervention
3. **Extract patterns:** Look for common design elements across trials
4. **Be specific:** Provide concrete recommendations, not generic advice
5. **Document sources:** Include NCT IDs for all referenced trials
6. **Handle sparse data:** If few trials found, expand search criteria and note limitations
