"""Representative ConcurrentBuilder output strings for bead 002.

Bead 002 runs ClinicalReviewer and CoverageAgent concurrently; the framework
returns the two agents' outputs as one concatenated string. These literals
capture the shapes that string takes in practice, including the nested-object
case that defeats a naive ``text.find("}")`` split.
"""

CLINICAL_JSON = """{
  "clinical_summary": {
    "primary_diagnosis": "Crohn's disease",
    "clinical_indicators": ["hematochezia", "Hgb 9.0"],
    "treatment_history": "Methylprednisolone 40mg daily, inadequate response"
  },
  "clinical_confidence": 88,
  "evidence_mapping": [
    {"criterion": "2.A.i age >= 6", "status": "MET", "evidence": "10 years old", "confidence": 95}
  ],
  "literature_support": [{"pmid": "32783974", "title": "Biologics in pediatric IBD"}]
}"""

COVERAGE_JSON = """{
  "coverage_status": "COVERED_WITH_CRITERIA",
  "applicable_policies": [
    {
      "policy_id": "Cigna-Adalimumab-Products-PA-Policy",
      "title": "Inflammatory Conditions - Adalimumab Products",
      "type": "Commercial",
      "coverage_criteria": ["Age >= 6", "Corticosteroid trial"]
    }
  ],
  "medical_necessity": {
    "is_medically_necessary": true,
    "rationale": "Steroid-refractory Crohn's disease meets Section 2.A"
  }
}"""

# Both agents' JSON, back to back. This is the common real-world shape and the
# one the old find("}") heuristic gets wrong: the first "}" closes
# clinical_summary, not the clinical object.
CONCATENATED_PLAIN = CLINICAL_JSON + "\n" + COVERAGE_JSON

# Same, but each agent wrapped its output in a fenced code block and added prose.
CONCATENATED_FENCED = (
    "ClinicalReviewer:\n```json\n"
    + CLINICAL_JSON
    + "\n```\n\nCoverageAgent:\n```json\n"
    + COVERAGE_JSON
    + "\n```\n"
)

# Degenerate case: one agent merged both payloads into a single object.
MERGED_SINGLE_OBJECT = """{
  "clinical_summary": {"primary_diagnosis": "Crohn's disease", "clinical_indicators": []},
  "clinical_confidence": 80,
  "coverage_status": "COVERED_WITH_CRITERIA",
  "applicable_policies": [{"policy_id": "P-1", "title": "Policy One", "coverage_criteria": []}],
  "medical_necessity": {"is_medically_necessary": true, "rationale": "Meets criteria"}
}"""

# Degenerate case: the coverage agent failed and emitted prose only.
CLINICAL_ONLY = CLINICAL_JSON + "\n\nCoverageAgent: unable to reach the policy service."
