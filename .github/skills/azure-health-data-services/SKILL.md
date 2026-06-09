---
name: azure-health-data-services
description: "Azure Health Data Services for DICOM imaging, MedTech device data, and FHIR integration. Use when working with medical imaging, IoT health devices, or unified health data."
---

# Azure Health Data Services Skill

Azure Health Data Services provides a unified workspace for managing healthcare data across FHIR, DICOM (medical imaging), and MedTech (IoT device) services with enterprise-grade security and compliance.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Azure Health Data Services Workspace                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐                │
│  │  FHIR Service  │  │ DICOM Service  │  │ MedTech Service│                │
│  │                │  │                │  │                │                │
│  │ • Patient      │  │ • STOW-RS      │  │ • Device Ingest│                │
│  │ • Observation  │  │ • WADO-RS      │  │ • Normalization│                │
│  │ • ImagingStudy │  │ • QIDO-RS      │  │ • FHIR Output  │                │
│  │ • $export      │  │ • Change Feed  │  │                │                │
│  └───────┬────────┘  └───────┬────────┘  └───────┬────────┘                │
│          │                   │                   │                          │
│          └───────────────────┼───────────────────┘                          │
│                              ▼                                              │
│               ┌──────────────────────────┐                                  │
│               │   Azure Event Grid       │                                  │
│               │   (Real-time Events)     │                                  │
│               └──────────────────────────┘                                  │
│                              │                                              │
│          ┌───────────────────┼───────────────────┐                          │
│          ▼                   ▼                   ▼                          │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐                    │
│  │Azure Functions│   │ Logic Apps   │   │ Power Platform│                   │
│  └──────────────┘   └──────────────┘   └──────────────┘                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Service Components

### FHIR Service
- **Purpose**: Store and manage clinical data using HL7 FHIR R4
- **Capabilities**: CRUD operations, search, $export, $convert-data, $patient-everything
- **See**: [azure-fhir-developer skill](../azure-fhir-developer/SKILL.md) for detailed FHIR patterns

### DICOM Service
- **Purpose**: Store, retrieve, and search medical imaging data
- **Standards**: DICOMweb (STOW-RS, WADO-RS, QIDO-RS)
- **Reference**: [01-dicom-service.md](references/01-dicom-service.md)

### MedTech Service
- **Purpose**: Ingest IoT device telemetry and convert to FHIR Observations
- **Protocols**: MQTT via IoT Hub, Event Hubs for high-volume ingestion
- **Reference**: [02-medtech-service.md](references/02-medtech-service.md)

## Workspace Deployment

### Bicep Template
```bicep
@description('Azure Health Data Services workspace')
resource workspace 'Microsoft.HealthcareApis/workspaces@2023-11-01' = {
  name: workspaceName
  location: location
  properties: {
    publicNetworkAccess: 'Disabled'
  }
  tags: {
    environment: environment
    compliance: 'HIPAA'
  }
}

resource fhirService 'Microsoft.HealthcareApis/workspaces/fhirservices@2023-11-01' = {
  parent: workspace
  name: fhirServiceName
  location: location
  kind: 'fhir-R4'
  properties: {
    authenticationConfiguration: {
      authority: 'https://login.microsoftonline.com/${tenantId}'
      audience: 'https://${workspaceName}-${fhirServiceName}.fhir.azurehealthcareapis.com'
    }
    corsConfiguration: {
      origins: corsOrigins
      methods: ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']
    }
  }
  identity: {
    type: 'SystemAssigned'
  }
}

resource dicomService 'Microsoft.HealthcareApis/workspaces/dicomservices@2023-11-01' = {
  parent: workspace
  name: dicomServiceName
  location: location
  properties: {
    corsConfiguration: {
      origins: corsOrigins
      methods: ['GET', 'POST', 'DELETE']
    }
  }
  identity: {
    type: 'SystemAssigned'
  }
}
```

### Azure CLI Deployment
```bash
# Create workspace
az healthcareapis workspace create \
  --resource-group $RESOURCE_GROUP \
  --name $WORKSPACE_NAME \
  --location $LOCATION

# Create FHIR service
az healthcareapis fhir-service create \
  --resource-group $RESOURCE_GROUP \
  --workspace-name $WORKSPACE_NAME \
  --fhir-service-name $FHIR_SERVICE_NAME \
  --kind fhir-R4 \
  --identity-type SystemAssigned

# Create DICOM service
az healthcareapis dicom-service create \
  --resource-group $RESOURCE_GROUP \
  --workspace-name $WORKSPACE_NAME \
  --dicom-service-name $DICOM_SERVICE_NAME

# Create MedTech service
az healthcareapis iot-connector create \
  --resource-group $RESOURCE_GROUP \
  --workspace-name $WORKSPACE_NAME \
  --iot-connector-name $MEDTECH_SERVICE_NAME \
  --device-mapping @device-mapping.json \
  --fhir-mapping @fhir-mapping.json \
  --event-hub-connection-string $EVENTHUB_CONNECTION
```

## DICOM Service Quick Reference

### Endpoints
| Operation | Method | Endpoint | Description |
|-----------|--------|----------|-------------|
| Store | POST | `/v1/studies` | Upload DICOM instances (STOW-RS) |
| Retrieve Study | GET | `/v1/studies/{studyUID}` | Download entire study (WADO-RS) |
| Retrieve Series | GET | `/v1/studies/{studyUID}/series/{seriesUID}` | Download series |
| Retrieve Instance | GET | `/v1/studies/{studyUID}/series/{seriesUID}/instances/{instanceUID}` | Download single instance |
| Search Studies | GET | `/v1/studies?{params}` | Query studies (QIDO-RS) |
| Search Series | GET | `/v1/studies/{studyUID}/series?{params}` | Query series within study |
| Delete Study | DELETE | `/v1/studies/{studyUID}` | Remove study |
| Change Feed | GET | `/v1/changefeed` | Track changes |
| Extended Query Tags | GET | `/v1/extendedquerytags` | Custom search tags |

### QIDO-RS Search Parameters
```http
GET /v1/studies?PatientName=Smith*&StudyDate=20240101-20240131&ModalitiesInStudy=CT
Accept: application/dicom+json
Authorization: Bearer {token}
```

**Common Parameters:**
- `PatientName` - Patient name (supports wildcards)
- `PatientID` - Patient identifier
- `StudyDate` - Date or date range (YYYYMMDD or YYYYMMDD-YYYYMMDD)
- `AccessionNumber` - Accession number
- `ModalitiesInStudy` - CT, MR, US, XR, etc.
- `StudyDescription` - Study description
- `offset` / `limit` - Pagination

### DICOM JSON Response Format
```json
[{
  "00080020": { "vr": "DA", "Value": ["20240115"] },
  "00080030": { "vr": "TM", "Value": ["143022"] },
  "00080050": { "vr": "SH", "Value": ["ACC123456"] },
  "00080061": { "vr": "CS", "Value": ["CT"] },
  "00100010": { "vr": "PN", "Value": [{ "Alphabetic": "Smith^John" }] },
  "00100020": { "vr": "LO", "Value": ["PAT001"] },
  "0020000D": { "vr": "UI", "Value": ["1.2.840.113619.2.416.1234567890"] },
  "00201206": { "vr": "IS", "Value": [120] },
  "00201208": { "vr": "IS", "Value": [240] }
}]
```

### Common DICOM Tags
| Tag | Name | Description |
|-----|------|-------------|
| 00080020 | StudyDate | Date study was performed |
| 00080030 | StudyTime | Time study started |
| 00080050 | AccessionNumber | RIS/HIS identifier |
| 00080060 | Modality | CT, MR, US, XR, etc. |
| 00100010 | PatientName | Patient's name |
| 00100020 | PatientID | Patient identifier |
| 0020000D | StudyInstanceUID | Unique study identifier |
| 0020000E | SeriesInstanceUID | Unique series identifier |
| 00080018 | SOPInstanceUID | Unique instance identifier |

## MedTech Service Quick Reference

### Device Message Format (Event Hub)
```json
{
  "deviceId": "SpO2-Monitor-001",
  "patientId": "patient-12345",
  "measurementTime": "2024-01-15T14:30:00.000Z",
  "readings": {
    "heartRate": {
      "value": 72,
      "unit": "beats/min"
    },
    "oxygenSaturation": {
      "value": 98,
      "unit": "%"
    },
    "bloodPressure": {
      "systolic": 120,
      "diastolic": 80,
      "unit": "mmHg"
    }
  }
}
```

### Device Mapping Template
```json
{
  "templateType": "CollectionContent",
  "template": [
    {
      "templateType": "JsonPathContent",
      "template": {
        "typeName": "heartRate",
        "typeMatchExpression": "$.readings.heartRate",
        "deviceIdExpression": "$.deviceId",
        "patientIdExpression": "$.patientId",
        "timestampExpression": "$.measurementTime",
        "values": [
          {
            "required": true,
            "valueExpression": "$.readings.heartRate.value",
            "valueName": "heartRate"
          }
        ]
      }
    },
    {
      "templateType": "JsonPathContent",
      "template": {
        "typeName": "oxygenSaturation",
        "typeMatchExpression": "$.readings.oxygenSaturation",
        "deviceIdExpression": "$.deviceId",
        "patientIdExpression": "$.patientId",
        "timestampExpression": "$.measurementTime",
        "values": [
          {
            "required": true,
            "valueExpression": "$.readings.oxygenSaturation.value",
            "valueName": "spo2"
          }
        ]
      }
    }
  ]
}
```

### FHIR Destination Mapping
```json
{
  "templateType": "CollectionFhir",
  "template": [
    {
      "templateType": "CodeValueFhir",
      "template": {
        "typeName": "heartRate",
        "value": {
          "valueName": "heartRate",
          "valueType": "Quantity",
          "unit": "beats/min",
          "system": "http://unitsofmeasure.org",
          "code": "/min"
        },
        "codes": [
          {
            "system": "http://loinc.org",
            "code": "8867-4",
            "display": "Heart rate"
          }
        ],
        "category": [
          {
            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
            "code": "vital-signs",
            "display": "Vital Signs"
          }
        ]
      }
    },
    {
      "templateType": "CodeValueFhir",
      "template": {
        "typeName": "oxygenSaturation",
        "value": {
          "valueName": "spo2",
          "valueType": "Quantity",
          "unit": "%",
          "system": "http://unitsofmeasure.org",
          "code": "%"
        },
        "codes": [
          {
            "system": "http://loinc.org",
            "code": "2708-6",
            "display": "Oxygen saturation in Arterial blood"
          }
        ],
        "category": [
          {
            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
            "code": "vital-signs",
            "display": "Vital Signs"
          }
        ]
      }
    }
  ]
}
```

### Generated FHIR Observation
```json
{
  "resourceType": "Observation",
  "status": "final",
  "category": [{
    "coding": [{
      "system": "http://terminology.hl7.org/CodeSystem/observation-category",
      "code": "vital-signs",
      "display": "Vital Signs"
    }]
  }],
  "code": {
    "coding": [{
      "system": "http://loinc.org",
      "code": "8867-4",
      "display": "Heart rate"
    }]
  },
  "subject": {
    "reference": "Patient/patient-12345"
  },
  "device": {
    "reference": "Device/SpO2-Monitor-001"
  },
  "effectiveDateTime": "2024-01-15T14:30:00.000Z",
  "valueQuantity": {
    "value": 72,
    "unit": "beats/min",
    "system": "http://unitsofmeasure.org",
    "code": "/min"
  }
}
```

## Integration Patterns

### DICOM-FHIR Linking via ImagingStudy
```json
{
  "resourceType": "ImagingStudy",
  "id": "imaging-study-001",
  "status": "available",
  "subject": {
    "reference": "Patient/patient-12345"
  },
  "started": "2024-01-15T10:00:00Z",
  "endpoint": [{
    "reference": "Endpoint/dicom-endpoint"
  }],
  "numberOfSeries": 2,
  "numberOfInstances": 240,
  "procedureCode": [{
    "coding": [{
      "system": "http://snomed.info/sct",
      "code": "77477000",
      "display": "CT of chest"
    }]
  }],
  "series": [{
    "uid": "1.2.840.113619.2.416.1234567890.1",
    "number": 1,
    "modality": {
      "system": "http://dicom.nema.org/resources/ontology/DCM",
      "code": "CT"
    },
    "description": "CT Chest Without Contrast",
    "numberOfInstances": 120,
    "bodySite": {
      "system": "http://snomed.info/sct",
      "code": "51185008",
      "display": "Thorax"
    }
  }]
}
```

### Event Grid for Real-Time Processing
```json
{
  "id": "ahds-event-sub",
  "properties": {
    "destination": {
      "endpointType": "AzureFunction",
      "properties": {
        "resourceId": "/subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Web/sites/{app}/functions/{func}"
      }
    },
    "filter": {
      "includedEventTypes": [
        "Microsoft.HealthcareApis.FhirResourceCreated",
        "Microsoft.HealthcareApis.FhirResourceUpdated",
        "Microsoft.HealthcareApis.DicomImageCreated"
      ],
      "advancedFilters": [{
        "key": "data.resourceType",
        "operatorType": "StringIn",
        "values": ["Observation", "DiagnosticReport"]
      }]
    }
  }
}
```

### Event Payload Structure
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "eventType": "Microsoft.HealthcareApis.FhirResourceCreated",
  "subject": "workspace/fhir-service/Observation/obs-12345",
  "eventTime": "2024-01-15T14:30:05.123Z",
  "data": {
    "resourceType": "Observation",
    "resourceFhirAccount": "https://workspace-fhir.fhir.azurehealthcareapis.com",
    "resourceFhirId": "obs-12345",
    "resourceVersionId": "1"
  },
  "dataVersion": "2"
}
```

## Security Configuration

### Private Link Setup
```bash
# Create private endpoint for FHIR service
az network private-endpoint create \
  --resource-group $RESOURCE_GROUP \
  --name pe-fhir \
  --vnet-name $VNET_NAME \
  --subnet $SUBNET_NAME \
  --private-connection-resource-id $(az healthcareapis fhir-service show \
    --resource-group $RESOURCE_GROUP \
    --workspace-name $WORKSPACE_NAME \
    --fhir-service-name $FHIR_SERVICE_NAME \
    --query id -o tsv) \
  --group-id fhir \
  --connection-name fhir-connection

# Create private endpoint for DICOM service
az network private-endpoint create \
  --resource-group $RESOURCE_GROUP \
  --name pe-dicom \
  --vnet-name $VNET_NAME \
  --subnet $SUBNET_NAME \
  --private-connection-resource-id $(az healthcareapis dicom-service show \
    --resource-group $RESOURCE_GROUP \
    --workspace-name $WORKSPACE_NAME \
    --dicom-service-name $DICOM_SERVICE_NAME \
    --query id -o tsv) \
  --group-id dicom \
  --connection-name dicom-connection
```

### RBAC Roles
| Role | Scope | Description |
|------|-------|-------------|
| FHIR Data Contributor | FHIR Service | Read/write/delete FHIR resources |
| FHIR Data Reader | FHIR Service | Read-only FHIR access |
| FHIR Data Exporter | FHIR Service | Execute $export operations |
| FHIR SMART User | FHIR Service | SMART on FHIR app access |
| DICOM Data Owner | DICOM Service | Full DICOM access including delete |
| DICOM Data Reader | DICOM Service | Read-only DICOM access |

### Managed Identity Authentication
```python
from azure.identity import DefaultAzureCredential
from azure.mgmt.healthcareapis import HealthcareApisManagementClient
import requests

credential = DefaultAzureCredential()
fhir_url = "https://workspace-fhir.fhir.azurehealthcareapis.com"

# Get token for FHIR service
token = credential.get_token(f"{fhir_url}/.default")

# Make FHIR request
response = requests.get(
    f"{fhir_url}/Patient",
    headers={
        "Authorization": f"Bearer {token.token}",
        "Content-Type": "application/fhir+json"
    }
)
```

## Monitoring & Diagnostics

### Diagnostic Settings
```json
{
  "logs": [
    {
      "category": "AuditLogs",
      "enabled": true,
      "retentionPolicy": {
        "enabled": true,
        "days": 365
      }
    },
    {
      "category": "DiagnosticLogs",
      "enabled": true,
      "retentionPolicy": {
        "enabled": true,
        "days": 90
      }
    }
  ],
  "metrics": [
    {
      "category": "AllMetrics",
      "enabled": true
    }
  ]
}
```

### Key Metrics
| Metric | Service | Description |
|--------|---------|-------------|
| TotalRequests | All | Total API requests |
| TotalLatency | All | Request latency in ms |
| TotalErrors | All | Failed requests |
| ServiceAvailability | All | Uptime percentage |
| StudiesStored | DICOM | Total DICOM studies |
| MessagesIngested | MedTech | Device messages processed |
| ObservationsCreated | MedTech | FHIR Observations generated |

### KQL Queries for Log Analytics
```kusto
// FHIR request latency by operation
AzureDiagnostics
| where ResourceType == "WORKSPACES/FHIRSERVICES"
| summarize AvgLatencyMs = avg(DurationMs) by OperationName, bin(TimeGenerated, 1h)
| render timechart

// DICOM storage growth
AzureDiagnostics
| where ResourceType == "WORKSPACES/DICOMSERVICES"
| where OperationName == "StoreTransaction"
| summarize StudiesStored = count() by bin(TimeGenerated, 1d)
| render columnchart

// MedTech ingestion errors
AzureDiagnostics
| where ResourceType == "WORKSPACES/IOTCONNECTORS"
| where Level == "Error"
| project TimeGenerated, Message, CorrelationId
| order by TimeGenerated desc
```

## References

For detailed implementation guides, see:

- [01-dicom-service.md](references/01-dicom-service.md) - Complete DICOM service reference
- [02-medtech-service.md](references/02-medtech-service.md) - MedTech device ingestion patterns
- [03-integration-patterns.md](references/03-integration-patterns.md) - Cross-service integration

## Best Practices

1. **Use Workspaces** - Group related FHIR, DICOM, and MedTech services for unified management
2. **Enable Private Link** - Required for HIPAA compliance in production
3. **Configure Event Grid** - Enable real-time processing of health data changes
4. **Use Managed Identity** - Avoid storing credentials; use system-assigned identity for service-to-service auth
5. **Implement Change Feed** - Track data changes for audit and sync scenarios
6. **Monitor Latency** - Set alerts for P95 latency exceeding SLA thresholds
7. **Plan Capacity** - DICOM storage can grow rapidly; monitor and set budgets
8. **Test Device Mappings** - Validate MedTech mappings with sample data before production
