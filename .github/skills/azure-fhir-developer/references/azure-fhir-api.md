# Azure API for FHIR Reference

## Service Endpoints

### Base URL Format
```
https://{workspace-name}-{fhir-service-name}.fhir.azurehealthcareapis.com
```

### Capability Statement
```http
GET https://{fhir-server}/metadata
```

## Authentication

### Getting an Access Token

#### Using Azure CLI
```bash
az account get-access-token --resource https://{fhir-server}.azurehealthcareapis.com
```

#### Using MSAL (JavaScript)
```typescript
import { PublicClientApplication } from '@azure/msal-browser';

const msalConfig = {
  auth: {
    clientId: '<client-id>',
    authority: 'https://login.microsoftonline.com/<tenant-id>'
  }
};

const pca = new PublicClientApplication(msalConfig);

const tokenRequest = {
  scopes: ['https://{fhir-server}.azurehealthcareapis.com/.default']
};

const response = await pca.acquireTokenSilent(tokenRequest);
const accessToken = response.accessToken;
```

#### Using DefaultAzureCredential (Python)
```python
from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential()
token = credential.get_token("https://{fhir-server}.azurehealthcareapis.com/.default")
access_token = token.token
```

## Common Operations

### Create Resource
```http
POST /{resourceType}
Content-Type: application/fhir+json
Authorization: Bearer {token}

{resource-body}
```

### Read Resource
```http
GET /{resourceType}/{id}
Authorization: Bearer {token}
```

### Update Resource
```http
PUT /{resourceType}/{id}
Content-Type: application/fhir+json
Authorization: Bearer {token}

{resource-body}
```

### Delete Resource
```http
DELETE /{resourceType}/{id}
Authorization: Bearer {token}
```

### Search Resources
```http
GET /{resourceType}?{parameters}
Authorization: Bearer {token}
```

### Conditional Create
```http
POST /{resourceType}
Content-Type: application/fhir+json
If-None-Exist: identifier={value}
Authorization: Bearer {token}

{resource-body}
```

## Bulk Operations

### Export (System-Level)
```http
GET /$export
Accept: application/fhir+json
Prefer: respond-async
Authorization: Bearer {token}
```

### Export (Patient-Level)
```http
GET /Patient/$export
Accept: application/fhir+json
Prefer: respond-async
Authorization: Bearer {token}
```

### Export Parameters
| Parameter | Description |
|-----------|-------------|
| `_outputFormat` | Output format (ndjson) |
| `_since` | Resources updated after this time |
| `_type` | Resource types to export |

### Import
```http
POST /$import
Content-Type: application/fhir+json
Authorization: Bearer {token}

{
  "resourceType": "Parameters",
  "parameter": [
    {
      "name": "inputFormat",
      "valueString": "application/fhir+ndjson"
    },
    {
      "name": "mode",
      "valueString": "IncrementalLoad"
    },
    {
      "name": "input",
      "part": [
        {
          "name": "type",
          "valueString": "Patient"
        },
        {
          "name": "url",
          "valueUri": "https://storage.blob.core.windows.net/container/patients.ndjson"
        }
      ]
    }
  ]
}
```

## Custom Operations

### $validate
```http
POST /{resourceType}/$validate
Content-Type: application/fhir+json
Authorization: Bearer {token}

{resource-body}
```

### $convert-data
```http
POST /$convert-data
Content-Type: application/fhir+json
Authorization: Bearer {token}

{
  "resourceType": "Parameters",
  "parameter": [
    {
      "name": "inputData",
      "valueString": "{hl7v2-message}"
    },
    {
      "name": "inputDataType",
      "valueString": "Hl7v2"
    },
    {
      "name": "templateCollectionReference",
      "valueString": "microsofthealth/fhirconverter:default"
    },
    {
      "name": "rootTemplate",
      "valueString": "ADT_A01"
    }
  ]
}
```

### $member-match
```http
POST /Patient/$member-match
Content-Type: application/fhir+json
Authorization: Bearer {token}

{
  "resourceType": "Parameters",
  "parameter": [
    {
      "name": "MemberPatient",
      "resource": {
        "resourceType": "Patient",
        "name": [{"family": "Smith", "given": ["John"]}],
        "birthDate": "1970-01-01"
      }
    },
    {
      "name": "Coverage",
      "resource": {
        "resourceType": "Coverage",
        "payor": [{"reference": "Organization/payer"}]
      }
    }
  ]
}
```

## Error Responses

### OperationOutcome
```json
{
  "resourceType": "OperationOutcome",
  "issue": [{
    "severity": "error",
    "code": "invalid",
    "diagnostics": "Resource failed validation",
    "location": ["Patient.birthDate"]
  }]
}
```

### Common HTTP Status Codes
| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 409 | Conflict (version mismatch) |
| 412 | Precondition Failed |
| 422 | Unprocessable Entity |

## Rate Limits and Quotas

| Metric | Default Limit |
|--------|---------------|
| Requests per minute | 100 |
| Bundle size | 500 entries |
| Response size | 1MB |
| Search results | 1000 per page |

## Monitoring Queries (Log Analytics)

### Request Latency
```kusto
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.HEALTHCAREAPIS"
| where Category == "AuditLogs"
| summarize avg(DurationMs), percentile(DurationMs, 95) by OperationName
| order by avg_DurationMs desc
```

### Error Rate
```kusto
AzureDiagnostics
| where ResourceProvider == "MICROSOFT.HEALTHCAREAPIS"
| where ResultType != "Success"
| summarize count() by ResultType, OperationName
| order by count_ desc
```
