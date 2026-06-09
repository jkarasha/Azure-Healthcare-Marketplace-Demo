---
name: azure-fhir-developer
description: "Build FHIR R4 applications faster with specialized knowledge of Azure API for FHIR, including resource structures, coding systems (LOINC, SNOMED CT, RxNorm), and Azure-specific authentication patterns."
---

# FHIR Developer Skill (Azure)

Connect healthcare systems faster with specialized knowledge of HL7 FHIR R4 for healthcare data exchange, including resource structures, coding systems, validation patterns, and Azure Health Data Services integration.

**Target Users:** Healthcare developers, integration engineers, EHR developers

**Key Features:**
- FHIR R4 resource reference with required fields
- Common coding systems (LOINC, SNOMED CT, RxNorm, ICD-10)
- Azure-specific authentication (SMART on FHIR, Managed Identity)
- Pydantic v2 model generation patterns
- Bulk data export and import
- Azure Health Data Services integration

---

## Quick Reference

### HTTP Status Codes

| Code | Meaning | When Returned |
|------|---------|---------------|
| 200 | OK | Successful GET, successful search |
| 201 | Created | Successful POST creating new resource |
| 204 | No Content | Successful DELETE |
| 400 | Bad Request | Invalid FHIR resource, validation failure |
| 401 | Unauthorized | Missing or invalid token |
| 403 | Forbidden | Token valid but insufficient scope |
| 404 | Not Found | Resource doesn't exist |
| 409 | Conflict | Version conflict on update |
| 412 | Precondition Failed | If-Match header doesn't match |
| 422 | Unprocessable Entity | Business rule violation |

### Required Fields by Resource

| Resource | Required Fields |
|----------|-----------------|
| Patient | `identifier` OR `name` (one must be present) |
| Observation | `status`, `code`, `subject` |
| Condition | `clinicalStatus`, `code`, `subject` |
| MedicationRequest | `status`, `intent`, `medication[x]`, `subject` |
| Encounter | `status`, `class`, `subject` |
| Procedure | `status`, `code`, `subject` |
| DiagnosticReport | `status`, `code`, `subject` |
| AllergyIntolerance | `clinicalStatus`, `patient` |
| Immunization | `status`, `vaccineCode`, `patient`, `occurrence[x]` |
| CarePlan | `status`, `intent`, `subject` |

---

## Coding Systems

### LOINC (Logical Observation Identifiers Names and Codes)

**System URL:** `http://loinc.org`

**Use for:** Laboratory observations, vital signs, clinical documents

| Code | Display | Category |
|------|---------|----------|
| 8867-4 | Heart rate | Vital Signs |
| 8310-5 | Body temperature | Vital Signs |
| 8480-6 | Systolic blood pressure | Vital Signs |
| 8462-4 | Diastolic blood pressure | Vital Signs |
| 8302-2 | Body height | Vital Signs |
| 29463-7 | Body weight | Vital Signs |
| 59408-5 | Oxygen saturation | Vital Signs |
| 8478-0 | Mean blood pressure | Vital Signs |
| 2339-0 | Glucose [Mass/volume] in Blood | Lab |
| 2093-3 | Cholesterol [Mass/volume] in Serum or Plasma | Lab |
| 718-7 | Hemoglobin [Mass/volume] in Blood | Lab |
| 4548-4 | Hemoglobin A1c/Hemoglobin.total in Blood | Lab |

**Example:**
```json
{
  "coding": [{
    "system": "http://loinc.org",
    "code": "8867-4",
    "display": "Heart rate"
  }]
}
```

### SNOMED CT (Systematized Nomenclature of Medicine)

**System URL:** `http://snomed.info/sct`

**Use for:** Clinical findings, procedures, body structures, organisms

| Code | Display | Category |
|------|---------|----------|
| 73211009 | Diabetes mellitus | Condition |
| 38341003 | Hypertensive disorder | Condition |
| 195967001 | Asthma | Condition |
| 40055000 | Chronic kidney disease | Condition |
| 427623005 | Chronic obstructive pulmonary disease | Condition |
| 414545008 | Ischemic heart disease | Condition |
| 80146002 | Appendectomy | Procedure |
| 27737000 | Cesarean section | Procedure |
| 174776001 | Total hip replacement | Procedure |

**Example:**
```json
{
  "coding": [{
    "system": "http://snomed.info/sct",
    "code": "73211009",
    "display": "Diabetes mellitus"
  }]
}
```

### RxNorm (Normalized Drug Names)

**System URL:** `http://www.nlm.nih.gov/research/umls/rxnorm`

**Use for:** Medications, drug ingredients, brand names

| Code | Display | Type |
|------|---------|------|
| 197361 | Metformin 500 MG Oral Tablet | SCD |
| 311700 | Lisinopril 10 MG Oral Tablet | SCD |
| 310798 | Atorvastatin 20 MG Oral Tablet | SCD |
| 197319 | Omeprazole 20 MG Delayed Release Oral Capsule | SCD |
| 314076 | Aspirin 81 MG Oral Tablet | SCD |

### ICD-10-CM (International Classification of Diseases)

**System URL:** `http://hl7.org/fhir/sid/icd-10-cm`

**Use for:** Diagnoses (billing/administrative)

| Code | Display |
|------|---------|
| E11.9 | Type 2 diabetes mellitus without complications |
| I10 | Essential (primary) hypertension |
| J45.909 | Unspecified asthma, uncomplicated |
| N18.9 | Chronic kidney disease, unspecified |
| J44.9 | Chronic obstructive pulmonary disease, unspecified |

---

## Azure Authentication Patterns

### SMART on FHIR (Patient-Facing Apps)

```typescript
// Configure MSAL for SMART on FHIR
const msalConfig = {
  auth: {
    clientId: process.env.CLIENT_ID,
    authority: `https://login.microsoftonline.com/${process.env.TENANT_ID}`,
    redirectUri: process.env.REDIRECT_URI
  }
};

// Request FHIR scopes
const loginRequest = {
  scopes: [
    `${process.env.FHIR_URL}/.default`,
    'openid',
    'profile',
    'launch/patient'
  ]
};
```

### Managed Identity (Backend Services)

```typescript
import { DefaultAzureCredential } from '@azure/identity';

const credential = new DefaultAzureCredential();
const token = await credential.getToken(
  `${process.env.FHIR_URL}/.default`
);

const response = await fetch(`${process.env.FHIR_URL}/Patient`, {
  headers: {
    'Authorization': `Bearer ${token.token}`,
    'Content-Type': 'application/fhir+json'
  }
});
```

### Service Principal

```bash
# Get token via Azure CLI
az account get-access-token \
  --resource https://{workspace}-{fhir-service}.fhir.azurehealthcareapis.com \
  --query accessToken -o tsv
```

---

## Pydantic v2 Patterns

### Patient Model

```python
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date

class HumanName(BaseModel):
    use: Optional[str] = None
    family: Optional[str] = None
    given: Optional[List[str]] = None

class Identifier(BaseModel):
    system: Optional[str] = None
    value: Optional[str] = None

class Patient(BaseModel):
    resourceType: str = Field(default="Patient", frozen=True)
    id: Optional[str] = None
    identifier: Optional[List[Identifier]] = None
    active: Optional[bool] = True
    name: Optional[List[HumanName]] = None
    gender: Optional[str] = None
    birthDate: Optional[date] = None

    model_config = {
        "populate_by_name": True,
        "json_schema_extra": {
            "example": {
                "resourceType": "Patient",
                "identifier": [{"system": "http://example.org", "value": "12345"}],
                "name": [{"family": "Smith", "given": ["John"]}],
                "gender": "male",
                "birthDate": "1970-01-01"
            }
        }
    }
```

### Observation Model

```python
class Coding(BaseModel):
    system: Optional[str] = None
    code: Optional[str] = None
    display: Optional[str] = None

class CodeableConcept(BaseModel):
    coding: Optional[List[Coding]] = None
    text: Optional[str] = None

class Quantity(BaseModel):
    value: Optional[float] = None
    unit: Optional[str] = None
    system: Optional[str] = Field(default="http://unitsofmeasure.org")
    code: Optional[str] = None

class Reference(BaseModel):
    reference: Optional[str] = None
    display: Optional[str] = None

class Observation(BaseModel):
    resourceType: str = Field(default="Observation", frozen=True)
    id: Optional[str] = None
    status: str  # required
    code: CodeableConcept  # required
    subject: Reference  # required
    effectiveDateTime: Optional[str] = None
    valueQuantity: Optional[Quantity] = None
    valueCodeableConcept: Optional[CodeableConcept] = None
```

---

## Validation Patterns

### Profile Validation

```http
POST https://{fhir-server}.azurehealthcareapis.com/Patient/$validate
Content-Type: application/fhir+json

{
  "resourceType": "Parameters",
  "parameter": [{
    "name": "resource",
    "resource": {
      "resourceType": "Patient",
      "name": [{"family": "Smith"}]
    }
  }]
}
```

### Bundle Validation

```http
POST https://{fhir-server}.azurehealthcareapis.com
Content-Type: application/fhir+json

{
  "resourceType": "Bundle",
  "type": "transaction",
  "entry": [
    {
      "fullUrl": "urn:uuid:patient-1",
      "resource": {
        "resourceType": "Patient",
        "name": [{"family": "Smith"}]
      },
      "request": {
        "method": "POST",
        "url": "Patient"
      }
    }
  ]
}
```

---

## Search Parameters

### Common Search Modifiers

| Modifier | Example | Description |
|----------|---------|-------------|
| `:exact` | `name:exact=John` | Case-sensitive exact match |
| `:contains` | `name:contains=Jo` | Substring match |
| `:missing` | `email:missing=true` | Field is/isn't present |
| `:not` | `status:not=cancelled` | Negation |

### Date Search Prefixes

| Prefix | Meaning | Example |
|--------|---------|---------|
| `eq` | Equals | `date=eq2024-01-01` |
| `ne` | Not equals | `date=ne2024-01-01` |
| `lt` | Less than | `date=lt2024-01-01` |
| `le` | Less than or equal | `date=le2024-01-01` |
| `gt` | Greater than | `date=gt2024-01-01` |
| `ge` | Greater than or equal | `date=ge2024-01-01` |

### Common Search Patterns

```http
# Search patients by name and birthdate
GET /Patient?name=Smith&birthdate=1970-01-01

# Search observations by patient and code
GET /Observation?patient=Patient/123&code=http://loinc.org|8867-4

# Include related resources
GET /Patient?_id=123&_include=Patient:organization

# Reverse include
GET /Patient?_id=123&_revinclude=Observation:patient

# Paginated search
GET /Patient?_count=50&_offset=100
```

---

## Bulk Data Operations

### System Export

```http
GET https://{fhir-server}.azurehealthcareapis.com/$export
Accept: application/fhir+json
Prefer: respond-async

# Response: 202 Accepted
# Content-Location: https://{fhir-server}/_operations/export/{job-id}
```

### Export Status Check

```http
GET https://{fhir-server}/_operations/export/{job-id}

# When complete (200 OK):
{
  "transactionTime": "2024-01-15T12:00:00Z",
  "request": "https://{fhir-server}/$export",
  "output": [
    {
      "type": "Patient",
      "url": "https://storage.blob.core.windows.net/export/Patient.ndjson"
    }
  ]
}
```

---

## Azure-Specific Features

### Private Link Configuration

```bash
az network private-endpoint create \
  --name pe-fhir \
  --resource-group myRG \
  --vnet-name myVNet \
  --subnet default \
  --private-connection-resource-id $(az healthcareapis workspace show \
    --name myWorkspace --resource-group myRG --query id -o tsv) \
  --group-id fhir \
  --connection-name fhir-connection
```

### Diagnostic Logging

```bash
az monitor diagnostic-settings create \
  --name fhir-diagnostics \
  --resource $(az healthcareapis workspace fhir-service show \
    --name myFhir --workspace-name myWorkspace --resource-group myRG \
    --query id -o tsv) \
  --logs '[{"category": "AuditLogs", "enabled": true}]' \
  --workspace $(az monitor log-analytics workspace show \
    --name myLAWorkspace --resource-group myRG --query id -o tsv)
```

---

## References

For detailed documentation, see:
- [references/fhir-r4-resources.md](references/fhir-r4-resources.md) - Complete resource reference
- [references/azure-fhir-api.md](references/azure-fhir-api.md) - Azure API specifics
- [references/smart-auth.md](references/smart-auth.md) - SMART on FHIR authentication
- [references/pagination.md](references/pagination.md) - Pagination patterns
- [references/bundles.md](references/bundles.md) - Transaction and batch bundles
