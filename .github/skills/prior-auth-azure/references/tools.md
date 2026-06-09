# Healthcare MCP Tool Reference

A quick reference guide for all tools available across the **3 consolidated MCP servers**. Each server bundles multiple tool domains into a single Azure Function endpoint.

> **Architecture Note:** The project consolidated ~7 individual MCP servers into 3:
> - **`mcp-reference-data`** (12 tools) — NPI + ICD-10 + CMS Coverage
> - **`mcp-clinical-research`** (20 tools) — FHIR + PubMed + ClinicalTrials
> - **`cosmos-rag`** (6 tools) — Document RAG + Audit Trail

---

## `mcp-reference-data` — Reference Data Server (12 tools)

Consolidated server for healthcare reference data: provider verification, diagnosis code validation, and Medicare coverage policies.

### NPI Tools

| Tool | Purpose |
|------|---------|
| `lookup_npi` | Look up a specific provider by their 10-digit NPI number. Returns name, specialty, address, credentials. |
| `search_providers` | Search providers by name, location, specialty, or organization. Supports wildcards. Filter by individual (NPI-1) or organization (NPI-2). |
| `validate_npi` | Validate NPI format (Luhn check with 80840 prefix) and existence in CMS registry. |

---

### CMS Coverage Tools

| Tool | Purpose |
|------|---------|
| `search_coverage` | Search Medicare coverage determinations (LCD/NCD). |
| `get_coverage_by_cpt` | Get Medicare coverage details for a CPT/HCPCS code. |
| `get_coverage_by_icd10` | Get Medicare coverage details related to an ICD-10 code. |
| `check_medical_necessity` | Check likely medical necessity for CPT + ICD-10 combinations. |
| `get_mac_jurisdiction` | Resolve MAC jurisdiction by state/ZIP for regional policy context. |

---

### ICD-10 Tools

| Tool | Purpose |
|------|---------|
| `validate_icd10` | Validate an ICD-10-CM code for format correctness and existence in official code set. |
| `lookup_icd10` | Get comprehensive info for a specific code: description, chapter, billability status. |
| `search_icd10` | Search diagnosis codes by clinical description, symptom, condition, or partial code. |
| `get_icd10_chapter` | Get chapter information and example codes for a code prefix (e.g., 'E11' for diabetes). |

---

### NPI Tools

| Tool | Purpose |
|------|---------|
| `lookup_npi` | Look up a specific provider by their 10-digit NPI number. Returns name, specialty, address, credentials. |
| `search_providers` | Search providers by name, location, specialty, or organization. Supports wildcards. Filter by individual (NPI-1) or organization (NPI-2). |
| `validate_npi` | Validate NPI format (Luhn check with 80840 prefix) and existence in CMS registry. |

---

## `mcp-clinical-research` — Clinical Research Server (20 tools)

Consolidated server for clinical research data: FHIR patient records, PubMed literature, and ClinicalTrials.gov.

### Clinical Trials Tools

| Tool | Purpose |
|------|---------|
| `search_trials` | Search ClinicalTrials.gov by condition, intervention, sponsor, location, status, or phase. Returns up to 100 results. |
| `get_trial` | Get comprehensive details for a specific trial by NCT ID, including eligibility criteria, outcomes, study design, and contact information. |
| `get_trial_eligibility` | Get eligibility criteria (inclusion/exclusion) for a clinical trial. |
| `get_trial_locations` | Get recruiting locations for a clinical trial with contact information. |
| `search_by_condition` | Find recruiting clinical trials for a specific condition near a location. |
| `get_trial_results` | Get results summary for a completed clinical trial (if available). |

---

### FHIR Tools

| Tool | Purpose |
|------|---------|
| `search_patients` | Search patients by name, DOB, identifier, gender. |
| `get_patient` | Retrieve a specific patient by FHIR resource ID. |
| `get_patient_conditions` | Get all conditions/diagnoses for a patient. Filter by `clinical_status`. |
| `get_patient_medications` | Get medications for a patient. Filter by `status` (active/completed/stopped). |
| `get_patient_observations` | Get observations (vitals, lab results) for a patient. Filter by `category` or LOINC `code`. |
| `get_patient_encounters` | Get encounters (visits) for a patient. Filter by `status` or `date`. |
| `search_practitioners` | Search for practitioners/providers by name, identifier, or specialty. |
| `validate_resource` | Validate a FHIR resource against the server's profiles without persisting. |

---

## `cosmos-rag` — Document RAG & Audit Trail Server (6 tools)

Cosmos DB-backed server for hybrid document search (vector + BM25) and immutable audit trail.

| Tool | Purpose |
|------|---------|
| `index_document` | Index a document for RAG retrieval. Chunks content, generates embeddings, stores in Cosmos DB. |
| `hybrid_search` | Search indexed documents using hybrid retrieval (vector + BM25 with RRF fusion). Best for natural language queries. |
| `vector_search` | Search indexed documents using pure vector similarity. Best when semantic meaning matters more than keywords. |
| `record_audit_event` | Record an immutable audit event for a healthcare workflow (compliance/traceability). |
| `get_audit_trail` | Retrieve audit trail for a specific workflow, ordered by timestamp. |
| `get_session_history` | Query audit trail across workflows by type and time range. |

---

## Azure APIM Endpoints

All MCP servers are accessible via Azure API Management. Each consolidated server exposes a single `/mcp` endpoint:

| Server | APIM Endpoint | Tools |
|--------|---------------|-------|
| `mcp-reference-data` | `https://healthcare-mcp.azure-api.net/reference-data/mcp` | NPI, ICD-10, CMS (12) |
| `mcp-clinical-research` | `https://healthcare-mcp.azure-api.net/clinical-research/mcp` | FHIR, PubMed, ClinicalTrials (20) |
| `cosmos-rag` | `https://healthcare-mcp.azure-api.net/cosmos-rag/mcp` | RAG, Audit (6) |

### Authentication

All endpoints require Azure AD authentication:

```bash
# Get access token
az account get-access-token --scope api://healthcare-mcp/.default

# Use with consolidated MCP server (all tools on one endpoint)
curl -X POST https://healthcare-mcp.azure-api.net/reference-data/mcp \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

---

## Error Handling

All tools return structured errors:

```json
{
  "error": {
    "code": "PROVIDER_NOT_FOUND",
    "message": "NPI 1234567890 not found in NPPES registry",
    "details": {
      "searched_npi": "1234567890",
      "suggestion": "Verify NPI is correct and provider is enrolled"
    }
  }
}
```

Common error codes:
- `INVALID_INPUT` - Bad parameter format
- `NOT_FOUND` - Resource not found
- `RATE_LIMITED` - Too many requests
- `SERVICE_UNAVAILABLE` - Backend service down
