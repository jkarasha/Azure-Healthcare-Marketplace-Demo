# FHIR R4 Resource Reference

## Core Clinical Resources

### Patient
The Patient resource represents demographic and administrative information about an individual receiving care.

```json
{
  "resourceType": "Patient",
  "id": "example",
  "identifier": [
    {
      "use": "usual",
      "type": {
        "coding": [{
          "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
          "code": "MR"
        }]
      },
      "system": "http://hospital.example.org",
      "value": "12345"
    }
  ],
  "active": true,
  "name": [
    {
      "use": "official",
      "family": "Smith",
      "given": ["John", "Michael"]
    }
  ],
  "telecom": [
    {
      "system": "phone",
      "value": "555-555-5555",
      "use": "home"
    }
  ],
  "gender": "male",
  "birthDate": "1970-01-01",
  "address": [
    {
      "use": "home",
      "line": ["123 Main St"],
      "city": "Anytown",
      "state": "CA",
      "postalCode": "12345"
    }
  ]
}
```

### Observation
Used for vital signs, lab results, and other measurements.

```json
{
  "resourceType": "Observation",
  "id": "blood-pressure",
  "status": "final",
  "category": [{
    "coding": [{
      "system": "http://terminology.hl7.org/CodeSystem/observation-category",
      "code": "vital-signs"
    }]
  }],
  "code": {
    "coding": [{
      "system": "http://loinc.org",
      "code": "85354-9",
      "display": "Blood pressure panel"
    }]
  },
  "subject": {
    "reference": "Patient/example"
  },
  "effectiveDateTime": "2024-01-15T09:30:00Z",
  "component": [
    {
      "code": {
        "coding": [{
          "system": "http://loinc.org",
          "code": "8480-6",
          "display": "Systolic blood pressure"
        }]
      },
      "valueQuantity": {
        "value": 120,
        "unit": "mmHg",
        "system": "http://unitsofmeasure.org",
        "code": "mm[Hg]"
      }
    },
    {
      "code": {
        "coding": [{
          "system": "http://loinc.org",
          "code": "8462-4",
          "display": "Diastolic blood pressure"
        }]
      },
      "valueQuantity": {
        "value": 80,
        "unit": "mmHg",
        "system": "http://unitsofmeasure.org",
        "code": "mm[Hg]"
      }
    }
  ]
}
```

### Condition
Represents a clinical condition, problem, or diagnosis.

```json
{
  "resourceType": "Condition",
  "id": "example",
  "clinicalStatus": {
    "coding": [{
      "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
      "code": "active"
    }]
  },
  "verificationStatus": {
    "coding": [{
      "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
      "code": "confirmed"
    }]
  },
  "category": [{
    "coding": [{
      "system": "http://terminology.hl7.org/CodeSystem/condition-category",
      "code": "encounter-diagnosis"
    }]
  }],
  "code": {
    "coding": [{
      "system": "http://snomed.info/sct",
      "code": "44054006",
      "display": "Type 2 diabetes mellitus"
    }]
  },
  "subject": {
    "reference": "Patient/example"
  },
  "onsetDateTime": "2020-01-01"
}
```

### MedicationRequest
An order for medication for a patient.

```json
{
  "resourceType": "MedicationRequest",
  "id": "example",
  "status": "active",
  "intent": "order",
  "medicationCodeableConcept": {
    "coding": [{
      "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
      "code": "860975",
      "display": "Metformin 500 MG Oral Tablet"
    }]
  },
  "subject": {
    "reference": "Patient/example"
  },
  "authoredOn": "2024-01-15",
  "requester": {
    "reference": "Practitioner/example"
  },
  "dosageInstruction": [{
    "text": "Take 500mg twice daily with meals",
    "timing": {
      "repeat": {
        "frequency": 2,
        "period": 1,
        "periodUnit": "d"
      }
    },
    "doseAndRate": [{
      "doseQuantity": {
        "value": 500,
        "unit": "mg",
        "system": "http://unitsofmeasure.org",
        "code": "mg"
      }
    }]
  }]
}
```

## Financial Resources

### Coverage
Insurance coverage for a patient.

```json
{
  "resourceType": "Coverage",
  "id": "example",
  "status": "active",
  "type": {
    "coding": [{
      "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
      "code": "HIP",
      "display": "health insurance plan policy"
    }]
  },
  "subscriber": {
    "reference": "Patient/example"
  },
  "beneficiary": {
    "reference": "Patient/example"
  },
  "relationship": {
    "coding": [{
      "code": "self"
    }]
  },
  "period": {
    "start": "2024-01-01",
    "end": "2024-12-31"
  },
  "payor": [{
    "reference": "Organization/insurance-company"
  }],
  "class": [{
    "type": {
      "coding": [{
        "system": "http://terminology.hl7.org/CodeSystem/coverage-class",
        "code": "plan"
      }]
    },
    "value": "GOLD"
  }]
}
```

### Claim
A request for payment for services rendered.

```json
{
  "resourceType": "Claim",
  "id": "example",
  "status": "active",
  "type": {
    "coding": [{
      "system": "http://terminology.hl7.org/CodeSystem/claim-type",
      "code": "professional"
    }]
  },
  "use": "claim",
  "patient": {
    "reference": "Patient/example"
  },
  "created": "2024-01-15",
  "provider": {
    "reference": "Organization/provider"
  },
  "priority": {
    "coding": [{
      "code": "normal"
    }]
  },
  "insurance": [{
    "sequence": 1,
    "focal": true,
    "coverage": {
      "reference": "Coverage/example"
    }
  }],
  "item": [{
    "sequence": 1,
    "productOrService": {
      "coding": [{
        "system": "http://www.ama-assn.org/go/cpt",
        "code": "99213",
        "display": "Office visit, established patient"
      }]
    },
    "servicedDate": "2024-01-15",
    "unitPrice": {
      "value": 150.00,
      "currency": "USD"
    }
  }]
}
```

## Search Parameters

### Common Search Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `_id` | token | Resource ID |
| `_lastUpdated` | date | Last update time |
| `_profile` | uri | Profiles the resource conforms to |
| `_tag` | token | Tags applied to the resource |
| `_include` | special | Include referenced resources |
| `_revinclude` | special | Include resources that reference this one |

### Patient Search Parameters

| Parameter | Type | Example |
|-----------|------|---------|
| `name` | string | `Patient?name=Smith` |
| `birthdate` | date | `Patient?birthdate=1970-01-01` |
| `identifier` | token | `Patient?identifier=12345` |
| `gender` | token | `Patient?gender=male` |
| `address-city` | string | `Patient?address-city=Seattle` |
