# MedTech Service Reference

Complete reference for Azure Health Data Services MedTech (IoT Connector) service.

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌──────────────────┐
│  IoT Devices    │───▶│  Event Hubs     │───▶│  MedTech Service │
│  (Wearables,    │    │  (Ingestion)    │    │  (Normalization) │
│   Monitors)     │    │                 │    │                  │
└─────────────────┘    └─────────────────┘    └────────┬─────────┘
                                                       │
                                                       ▼
                                              ┌──────────────────┐
                                              │   FHIR Service   │
                                              │  (Observations)  │
                                              └──────────────────┘
```

## Data Flow

1. **Device** sends telemetry to Event Hub
2. **MedTech** normalizes data using Device Mapping
3. **MedTech** groups normalized data by patient/device
4. **MedTech** transforms to FHIR using FHIR Mapping
5. **FHIR Service** persists Observations

## Prerequisites

### Event Hub Setup
```bash
# Create Event Hub namespace
az eventhubs namespace create \
  --resource-group $RESOURCE_GROUP \
  --name $EVENTHUB_NAMESPACE \
  --sku Standard \
  --enable-auto-inflate true \
  --maximum-throughput-units 10

# Create Event Hub for device data
az eventhubs eventhub create \
  --resource-group $RESOURCE_GROUP \
  --namespace-name $EVENTHUB_NAMESPACE \
  --name device-telemetry \
  --partition-count 4 \
  --message-retention 7

# Create consumer group for MedTech
az eventhubs eventhub consumer-group create \
  --resource-group $RESOURCE_GROUP \
  --namespace-name $EVENTHUB_NAMESPACE \
  --eventhub-name device-telemetry \
  --name medtech-consumer-group

# Get connection string
az eventhubs namespace authorization-rule keys list \
  --resource-group $RESOURCE_GROUP \
  --namespace-name $EVENTHUB_NAMESPACE \
  --name RootManageSharedAccessKey \
  --query primaryConnectionString -o tsv
```

## Device Message Formats

### Simple Flat Message
```json
{
  "deviceId": "pulse-ox-001",
  "patientId": "patient-12345",
  "timestamp": "2024-01-15T14:30:00.000Z",
  "heartRate": 72,
  "spo2": 98
}
```

### Nested Message
```json
{
  "header": {
    "deviceId": "monitor-001",
    "deviceType": "vital-signs-monitor",
    "timestamp": "2024-01-15T14:30:00.000Z"
  },
  "patient": {
    "id": "patient-12345",
    "mrn": "MRN-98765"
  },
  "vitals": {
    "heartRate": {
      "value": 72,
      "unit": "bpm"
    },
    "bloodPressure": {
      "systolic": 120,
      "diastolic": 80,
      "unit": "mmHg"
    },
    "temperature": {
      "value": 37.2,
      "unit": "Celsius"
    },
    "respiratoryRate": {
      "value": 16,
      "unit": "breaths/min"
    },
    "oxygenSaturation": {
      "value": 98,
      "unit": "%"
    }
  }
}
```

### Array Message (Multiple Readings)
```json
{
  "deviceId": "cgm-001",
  "patientId": "patient-12345",
  "readings": [
    {
      "timestamp": "2024-01-15T14:30:00.000Z",
      "glucoseLevel": 105
    },
    {
      "timestamp": "2024-01-15T14:35:00.000Z",
      "glucoseLevel": 108
    },
    {
      "timestamp": "2024-01-15T14:40:00.000Z",
      "glucoseLevel": 112
    }
  ]
}
```

## Device Mapping Templates

### Template Types

| Type | Description | Use Case |
|------|-------------|----------|
| CollectionContent | Container for multiple templates | Always root template |
| JsonPathContent | Extract values using JSONPath | Standard JSON messages |
| IotJsonPathContent | Simplified for IoT Hub messages | Azure IoT Hub integration |
| IotCentralJsonPathContent | Specific to IoT Central | Azure IoT Central |
| CalculatedContent | Compute derived values | BMI, ratios, etc. |

### Basic JsonPathContent Template
```json
{
  "templateType": "CollectionContent",
  "template": [
    {
      "templateType": "JsonPathContent",
      "template": {
        "typeName": "heartRate",
        "typeMatchExpression": "$..[?(@heartRate)]",
        "deviceIdExpression": "$.deviceId",
        "patientIdExpression": "$.patientId",
        "timestampExpression": "$.timestamp",
        "values": [
          {
            "required": true,
            "valueExpression": "$.heartRate",
            "valueName": "hr"
          }
        ]
      }
    }
  ]
}
```

### Nested Data Template
```json
{
  "templateType": "CollectionContent",
  "template": [
    {
      "templateType": "JsonPathContent",
      "template": {
        "typeName": "heartRate",
        "typeMatchExpression": "$.vitals.heartRate",
        "deviceIdExpression": "$.header.deviceId",
        "patientIdExpression": "$.patient.id",
        "timestampExpression": "$.header.timestamp",
        "values": [
          {
            "required": true,
            "valueExpression": "$.vitals.heartRate.value",
            "valueName": "hr"
          }
        ]
      }
    },
    {
      "templateType": "JsonPathContent",
      "template": {
        "typeName": "bloodPressure",
        "typeMatchExpression": "$.vitals.bloodPressure",
        "deviceIdExpression": "$.header.deviceId",
        "patientIdExpression": "$.patient.id",
        "timestampExpression": "$.header.timestamp",
        "values": [
          {
            "required": true,
            "valueExpression": "$.vitals.bloodPressure.systolic",
            "valueName": "systolic"
          },
          {
            "required": true,
            "valueExpression": "$.vitals.bloodPressure.diastolic",
            "valueName": "diastolic"
          }
        ]
      }
    },
    {
      "templateType": "JsonPathContent",
      "template": {
        "typeName": "oxygenSaturation",
        "typeMatchExpression": "$.vitals.oxygenSaturation",
        "deviceIdExpression": "$.header.deviceId",
        "patientIdExpression": "$.patient.id",
        "timestampExpression": "$.header.timestamp",
        "values": [
          {
            "required": true,
            "valueExpression": "$.vitals.oxygenSaturation.value",
            "valueName": "spo2"
          }
        ]
      }
    }
  ]
}
```

### Array Processing Template
```json
{
  "templateType": "CollectionContent",
  "template": [
    {
      "templateType": "JsonPathContent",
      "template": {
        "typeName": "glucoseLevel",
        "typeMatchExpression": "$.readings[*]",
        "deviceIdExpression": "$.deviceId",
        "patientIdExpression": "$.patientId",
        "timestampExpression": "$.readings[*].timestamp",
        "values": [
          {
            "required": true,
            "valueExpression": "$.readings[*].glucoseLevel",
            "valueName": "glucose"
          }
        ]
      }
    }
  ]
}
```

### Calculated Content Template
```json
{
  "templateType": "CollectionContent",
  "template": [
    {
      "templateType": "JsonPathContent",
      "template": {
        "typeName": "bodyMeasurements",
        "typeMatchExpression": "$.body",
        "deviceIdExpression": "$.deviceId",
        "patientIdExpression": "$.patientId",
        "timestampExpression": "$.timestamp",
        "values": [
          {
            "required": true,
            "valueExpression": "$.body.heightMeters",
            "valueName": "height"
          },
          {
            "required": true,
            "valueExpression": "$.body.weightKg",
            "valueName": "weight"
          }
        ]
      }
    },
    {
      "templateType": "CalculatedContent",
      "template": {
        "typeName": "bmi",
        "typeMatchExpression": "$.body",
        "deviceIdExpression": "$.deviceId",
        "patientIdExpression": "$.patientId",
        "timestampExpression": "$.timestamp",
        "values": [
          {
            "required": true,
            "valueExpression": "divide($.body.weightKg, multiply($.body.heightMeters, $.body.heightMeters))",
            "valueName": "bmi"
          }
        ]
      }
    }
  ]
}
```

**Supported Functions:**
- `add(a, b)`, `subtract(a, b)`, `multiply(a, b)`, `divide(a, b)`

## FHIR Destination Mapping

### Template Types

| Type | Description | Output |
|------|-------------|--------|
| CodeValueFhir | Simple quantitative observation | Observation with valueQuantity |
| SampledDataFhir | High-frequency sampled data | Observation with valueSampledData |
| StringFhir | Text-based observation | Observation with valueString |
| CodeableConceptFhir | Categorical observation | Observation with valueCodeableConcept |

### Basic Vital Signs Mapping
```json
{
  "templateType": "CollectionFhir",
  "template": [
    {
      "templateType": "CodeValueFhir",
      "template": {
        "typeName": "heartRate",
        "value": {
          "valueName": "hr",
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
        ],
        "periodInterval": 60
      }
    }
  ]
}
```

### Blood Pressure Component Observation
```json
{
  "templateType": "CodeValueFhir",
  "template": {
    "typeName": "bloodPressure",
    "codes": [
      {
        "system": "http://loinc.org",
        "code": "85354-9",
        "display": "Blood pressure panel with all children optional"
      }
    ],
    "category": [
      {
        "system": "http://terminology.hl7.org/CodeSystem/observation-category",
        "code": "vital-signs",
        "display": "Vital Signs"
      }
    ],
    "components": [
      {
        "codes": [
          {
            "system": "http://loinc.org",
            "code": "8480-6",
            "display": "Systolic blood pressure"
          }
        ],
        "value": {
          "valueName": "systolic",
          "valueType": "Quantity",
          "unit": "mmHg",
          "system": "http://unitsofmeasure.org",
          "code": "mm[Hg]"
        }
      },
      {
        "codes": [
          {
            "system": "http://loinc.org",
            "code": "8462-4",
            "display": "Diastolic blood pressure"
          }
        ],
        "value": {
          "valueName": "diastolic",
          "valueType": "Quantity",
          "unit": "mmHg",
          "system": "http://unitsofmeasure.org",
          "code": "mm[Hg]"
        }
      }
    ],
    "periodInterval": 60
  }
}
```

### Complete Vital Signs Template
```json
{
  "templateType": "CollectionFhir",
  "template": [
    {
      "templateType": "CodeValueFhir",
      "template": {
        "typeName": "heartRate",
        "value": {
          "valueName": "hr",
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
            "code": "vital-signs"
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
            "code": "vital-signs"
          }
        ]
      }
    },
    {
      "templateType": "CodeValueFhir",
      "template": {
        "typeName": "bodyTemperature",
        "value": {
          "valueName": "temp",
          "valueType": "Quantity",
          "unit": "Cel",
          "system": "http://unitsofmeasure.org",
          "code": "Cel"
        },
        "codes": [
          {
            "system": "http://loinc.org",
            "code": "8310-5",
            "display": "Body temperature"
          }
        ],
        "category": [
          {
            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
            "code": "vital-signs"
          }
        ]
      }
    },
    {
      "templateType": "CodeValueFhir",
      "template": {
        "typeName": "respiratoryRate",
        "value": {
          "valueName": "rr",
          "valueType": "Quantity",
          "unit": "breaths/min",
          "system": "http://unitsofmeasure.org",
          "code": "/min"
        },
        "codes": [
          {
            "system": "http://loinc.org",
            "code": "9279-1",
            "display": "Respiratory rate"
          }
        ],
        "category": [
          {
            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
            "code": "vital-signs"
          }
        ]
      }
    },
    {
      "templateType": "CodeValueFhir",
      "template": {
        "typeName": "glucoseLevel",
        "value": {
          "valueName": "glucose",
          "valueType": "Quantity",
          "unit": "mg/dL",
          "system": "http://unitsofmeasure.org",
          "code": "mg/dL"
        },
        "codes": [
          {
            "system": "http://loinc.org",
            "code": "2339-0",
            "display": "Glucose [Mass/volume] in Blood"
          }
        ],
        "category": [
          {
            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
            "code": "laboratory"
          }
        ]
      }
    },
    {
      "templateType": "CodeValueFhir",
      "template": {
        "typeName": "bmi",
        "value": {
          "valueName": "bmi",
          "valueType": "Quantity",
          "unit": "kg/m2",
          "system": "http://unitsofmeasure.org",
          "code": "kg/m2"
        },
        "codes": [
          {
            "system": "http://loinc.org",
            "code": "39156-5",
            "display": "Body mass index (BMI) [Ratio]"
          }
        ],
        "category": [
          {
            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
            "code": "vital-signs"
          }
        ]
      }
    }
  ]
}
```

### Common LOINC Codes for Device Data

| Measurement | LOINC Code | Display |
|-------------|------------|---------|
| Heart Rate | 8867-4 | Heart rate |
| SpO2 | 2708-6 | Oxygen saturation in Arterial blood |
| Body Temperature | 8310-5 | Body temperature |
| Respiratory Rate | 9279-1 | Respiratory rate |
| Systolic BP | 8480-6 | Systolic blood pressure |
| Diastolic BP | 8462-4 | Diastolic blood pressure |
| Blood Glucose | 2339-0 | Glucose [Mass/volume] in Blood |
| Body Weight | 29463-7 | Body weight |
| Body Height | 8302-2 | Body height |
| BMI | 39156-5 | Body mass index (BMI) [Ratio] |
| Steps | 55423-8 | Number of steps in 24 hour |
| Sleep Duration | 93832-4 | Sleep duration |
| ECG | 131329 | MDC ECG Heart Rate |

## Resolution Types

Configure how MedTech identifies Patient and Device resources in FHIR.

### Lookup Resolution (Recommended)
Search FHIR for existing resources:
```json
{
  "resolutionType": "Lookup",
  "fhirServerUrl": "https://workspace-fhir.fhir.azurehealthcareapis.com"
}
```

### Create Resolution
Create resources if not found:
```json
{
  "resolutionType": "Create",
  "fhirServerUrl": "https://workspace-fhir.fhir.azurehealthcareapis.com"
}
```

## MedTech Deployment

### Create MedTech Service
```bash
az healthcareapis iot-connector create \
  --resource-group $RESOURCE_GROUP \
  --workspace-name $WORKSPACE_NAME \
  --iot-connector-name $MEDTECH_NAME \
  --location $LOCATION \
  --identity-type SystemAssigned \
  --ingestion-endpoint-configuration \
    eventHubName=device-telemetry \
    consumerGroup=medtech-consumer-group \
    fullyQualifiedEventHubNamespace="${EVENTHUB_NAMESPACE}.servicebus.windows.net"
```

### Configure Device Mapping
```bash
az healthcareapis iot-connector device-mapping update \
  --resource-group $RESOURCE_GROUP \
  --workspace-name $WORKSPACE_NAME \
  --iot-connector-name $MEDTECH_NAME \
  --content @device-mapping.json
```

### Create FHIR Destination
```bash
az healthcareapis iot-connector fhir-destination create \
  --resource-group $RESOURCE_GROUP \
  --workspace-name $WORKSPACE_NAME \
  --iot-connector-name $MEDTECH_NAME \
  --fhir-destination-name default \
  --fhir-service-resource-id $(az healthcareapis fhir-service show \
    --resource-group $RESOURCE_GROUP \
    --workspace-name $WORKSPACE_NAME \
    --fhir-service-name $FHIR_SERVICE_NAME \
    --query id -o tsv) \
  --resource-identity-resolution-type Lookup \
  --fhir-mapping @fhir-mapping.json
```

### Grant Permissions
```bash
# Get MedTech managed identity
MEDTECH_PRINCIPAL_ID=$(az healthcareapis iot-connector show \
  --resource-group $RESOURCE_GROUP \
  --workspace-name $WORKSPACE_NAME \
  --iot-connector-name $MEDTECH_NAME \
  --query identity.principalId -o tsv)

# Grant FHIR Data Writer role
FHIR_ID=$(az healthcareapis fhir-service show \
  --resource-group $RESOURCE_GROUP \
  --workspace-name $WORKSPACE_NAME \
  --fhir-service-name $FHIR_SERVICE_NAME \
  --query id -o tsv)

az role assignment create \
  --assignee $MEDTECH_PRINCIPAL_ID \
  --role "FHIR Data Writer" \
  --scope $FHIR_ID

# Grant Event Hub Data Receiver role
EVENTHUB_ID=$(az eventhubs eventhub show \
  --resource-group $RESOURCE_GROUP \
  --namespace-name $EVENTHUB_NAMESPACE \
  --name device-telemetry \
  --query id -o tsv)

az role assignment create \
  --assignee $MEDTECH_PRINCIPAL_ID \
  --role "Azure Event Hubs Data Receiver" \
  --scope $EVENTHUB_ID
```

## Testing & Validation

### Send Test Message to Event Hub
```python
from azure.eventhub import EventHubProducerClient, EventData
from azure.identity import DefaultAzureCredential
import json
from datetime import datetime

credential = DefaultAzureCredential()

producer = EventHubProducerClient(
    fully_qualified_namespace=f"{EVENTHUB_NAMESPACE}.servicebus.windows.net",
    eventhub_name="device-telemetry",
    credential=credential
)

message = {
    "deviceId": "test-device-001",
    "patientId": "patient-12345",
    "timestamp": datetime.utcnow().isoformat() + "Z",
    "heartRate": 72,
    "spo2": 98
}

with producer:
    event_data_batch = producer.create_batch()
    event_data_batch.add(EventData(json.dumps(message)))
    producer.send_batch(event_data_batch)
    print("Message sent successfully")
```

### Verify FHIR Output
```python
import requests
from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential()
fhir_url = "https://workspace-fhir.fhir.azurehealthcareapis.com"
token = credential.get_token(f"{fhir_url}/.default")

# Check for new Observations
response = requests.get(
    f"{fhir_url}/Observation",
    headers={
        "Authorization": f"Bearer {token.token}",
        "Content-Type": "application/fhir+json"
    },
    params={
        "subject": "Patient/patient-12345",
        "_sort": "-_lastUpdated",
        "_count": 10
    }
)

observations = response.json()
print(f"Found {len(observations.get('entry', []))} observations")
```

### Debug Mapping Issues
```bash
# Check MedTech diagnostic logs
az monitor diagnostic-settings create \
  --resource $(az healthcareapis iot-connector show \
    --resource-group $RESOURCE_GROUP \
    --workspace-name $WORKSPACE_NAME \
    --iot-connector-name $MEDTECH_NAME \
    --query id -o tsv) \
  --name medtech-logs \
  --workspace $LOG_ANALYTICS_WORKSPACE \
  --logs '[
    {"category": "DiagnosticLogs", "enabled": true},
    {"category": "AuditLogs", "enabled": true}
  ]'
```

### KQL Queries for Troubleshooting
```kusto
// MedTech ingestion errors
AzureDiagnostics
| where ResourceType == "WORKSPACES/IOTCONNECTORS"
| where Level == "Error"
| project TimeGenerated, Message, CorrelationId
| order by TimeGenerated desc

// Mapping failures
AzureDiagnostics
| where ResourceType == "WORKSPACES/IOTCONNECTORS"
| where Message contains "mapping" or Message contains "normalization"
| project TimeGenerated, Level, Message
| order by TimeGenerated desc

// Throughput metrics
AzureDiagnostics
| where ResourceType == "WORKSPACES/IOTCONNECTORS"
| where Category == "DiagnosticLogs"
| summarize MessagesProcessed = count() by bin(TimeGenerated, 1h)
| render timechart
```

## Common Errors & Solutions

| Error | Cause | Solution |
|-------|-------|----------|
| No normalized events | typeMatchExpression doesn't match | Test JSONPath against sample message |
| Patient not found | FHIR Patient doesn't exist | Create Patient resource or use Create resolution |
| Invalid timestamp | Wrong timestamp format | Ensure ISO 8601 format with Z suffix |
| Missing required value | valueExpression returns null | Check JSONPath path accuracy |
| Permission denied | Missing RBAC role | Grant FHIR Data Writer role |
| Event Hub connection failed | Wrong connection string | Verify managed identity permissions |

## Best Practices

1. **Test Mappings First** - Use the debug tool to test device and FHIR mappings before deployment
2. **Use Lookup Resolution** - Pre-create Patient/Device resources instead of auto-creating
3. **Set Period Intervals** - Aggregate high-frequency data (60-300 seconds)
4. **Monitor Lag** - Track time between Event Hub and FHIR write
5. **Handle Errors** - Set up alerts for normalization/transformation failures
6. **Use Standard Codes** - Always use LOINC, SNOMED CT, or other standard terminologies
7. **Document Device IDs** - Maintain mapping between physical devices and FHIR Device resources
