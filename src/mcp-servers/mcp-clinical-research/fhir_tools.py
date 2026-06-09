"""FHIR R4 operations tools — patient data retrieval and clinical queries.
Migrated from standalone fhir-operations MCP server."""

import logging
import os
from typing import Optional

import httpx
from azure.identity import DefaultAzureCredential

logger = logging.getLogger(__name__)

FHIR_SERVER_URL = os.environ.get("FHIR_SERVER_URL", "")

TOOLS = [
    {
        "name": "search_patients",
        "description": "Search for patients in the FHIR server by various criteria (name, DOB, identifier, etc.)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "family": {"type": "string", "description": "Patient family (last) name"},
                "given": {"type": "string", "description": "Patient given (first) name"},
                "birthdate": {"type": "string", "description": "Birth date (YYYY-MM-DD)"},
                "identifier": {"type": "string", "description": "Patient identifier (e.g., MRN)"},
                "gender": {"type": "string", "enum": ["male", "female", "other", "unknown"]},
                "count": {"type": "integer", "description": "Max results (default 10)", "default": 10},
            },
        },
    },
    {
        "name": "get_patient",
        "description": "Retrieve a specific patient by FHIR resource ID",
        "inputSchema": {
            "type": "object",
            "properties": {"patient_id": {"type": "string", "description": "FHIR Patient resource ID"}},
            "required": ["patient_id"],
        },
    },
    {
        "name": "get_patient_conditions",
        "description": "Get all conditions/diagnoses for a patient",
        "inputSchema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string", "description": "FHIR Patient resource ID"},
                "clinical_status": {
                    "type": "string",
                    "enum": ["active", "recurrence", "relapse", "inactive", "remission", "resolved"],
                    "description": "Filter by clinical status",
                },
                "count": {"type": "integer", "description": "Max results", "default": 50},
            },
            "required": ["patient_id"],
        },
    },
    {
        "name": "get_patient_medications",
        "description": "Get active medications for a patient",
        "inputSchema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string", "description": "FHIR Patient resource ID"},
                "status": {
                    "type": "string",
                    "enum": ["active", "completed", "stopped", "on-hold"],
                    "description": "Filter by medication status",
                    "default": "active",
                },
            },
            "required": ["patient_id"],
        },
    },
    {
        "name": "get_patient_observations",
        "description": "Get observations (vitals, lab results) for a patient",
        "inputSchema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string", "description": "FHIR Patient resource ID"},
                "category": {
                    "type": "string",
                    "enum": ["vital-signs", "laboratory", "social-history", "imaging"],
                    "description": "Observation category filter",
                },
                "code": {"type": "string", "description": "LOINC code filter"},
                "count": {"type": "integer", "default": 20},
            },
            "required": ["patient_id"],
        },
    },
    {
        "name": "get_patient_encounters",
        "description": "Get encounters (visits) for a patient",
        "inputSchema": {
            "type": "object",
            "properties": {
                "patient_id": {"type": "string", "description": "FHIR Patient resource ID"},
                "status": {"type": "string", "enum": ["planned", "arrived", "in-progress", "finished", "cancelled"]},
                "date": {"type": "string", "description": "Date filter (YYYY-MM-DD or range like ge2023-01-01)"},
                "count": {"type": "integer", "default": 20},
            },
            "required": ["patient_id"],
        },
    },
    {
        "name": "search_practitioners",
        "description": "Search for healthcare practitioners/providers",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Practitioner name"},
                "identifier": {"type": "string", "description": "NPI or other identifier"},
                "specialty": {"type": "string", "description": "Specialty/qualification"},
            },
        },
    },
    {
        "name": "validate_resource",
        "description": "Validate a FHIR resource against the server's profiles",
        "inputSchema": {
            "type": "object",
            "properties": {
                "resource_type": {"type": "string", "description": "FHIR resource type (e.g., Patient, Observation)"},
                "resource": {"type": "object", "description": "The FHIR resource JSON to validate"},
            },
            "required": ["resource_type", "resource"],
        },
    },
]


# ---------------------------------------------------------------------------
# FHIR client
# ---------------------------------------------------------------------------

async def get_fhir_client() -> httpx.AsyncClient:
    """Get authenticated FHIR client."""
    headers = {"Accept": "application/fhir+json"}

    if FHIR_SERVER_URL:
        try:
            credential = DefaultAzureCredential()
            token = credential.get_token("https://fhir.azure.com/.default")
            headers["Authorization"] = f"Bearer {token.token}"
        except Exception as e:
            logger.warning(f"Could not get Azure credential: {e}")

    return httpx.AsyncClient(base_url=FHIR_SERVER_URL or "https://hapi.fhir.org/baseR4", headers=headers, timeout=30.0)


# ---------------------------------------------------------------------------
# Helper / formatting
# ---------------------------------------------------------------------------

def _format_bundle(bundle: dict, resource_type: str) -> dict:
    """Format a FHIR Bundle response."""
    entries = bundle.get("entry", [])
    return {"total": bundle.get("total", len(entries)), "resources": [e.get("resource", {}) for e in entries]}


# ---------------------------------------------------------------------------
# Demo data functions (used when no FHIR server is configured)
# ---------------------------------------------------------------------------

def _demo_patients(params: dict) -> dict:
    return {
        "total": 1,
        "resources": [
            {
                "resourceType": "Patient",
                "id": "demo-patient-1",
                "name": [{"family": "Smith", "given": ["John"]}],
                "gender": "male",
                "birthDate": "1970-01-15",
            }
        ],
        "note": "Demo data - configure FHIR_SERVER_URL for real data",
    }


def _demo_patient(patient_id: str) -> dict:
    return {
        "found": True,
        "resource": {
            "resourceType": "Patient",
            "id": patient_id,
            "name": [{"family": "Smith", "given": ["John"]}],
            "gender": "male",
            "birthDate": "1970-01-15",
        },
        "note": "Demo data",
    }


def _demo_conditions(patient_id: str) -> dict:
    return {
        "total": 2,
        "resources": [
            {
                "resourceType": "Condition",
                "id": "c1",
                "code": {
                    "coding": [
                        {
                            "system": "http://hl7.org/fhir/sid/icd-10",
                            "code": "E11.9",
                            "display": "Type 2 diabetes mellitus",
                        }
                    ]
                },
                "clinicalStatus": {"coding": [{"code": "active"}]},
            },
            {
                "resourceType": "Condition",
                "id": "c2",
                "code": {
                    "coding": [
                        {"system": "http://hl7.org/fhir/sid/icd-10", "code": "I10", "display": "Essential hypertension"}
                    ]
                },
                "clinicalStatus": {"coding": [{"code": "active"}]},
            },
        ],
        "note": "Demo data",
    }


def _demo_medications(patient_id: str) -> dict:
    return {
        "total": 2,
        "resources": [
            {
                "resourceType": "MedicationRequest",
                "id": "m1",
                "medicationCodeableConcept": {
                    "coding": [
                        {
                            "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                            "code": "860975",
                            "display": "Metformin 500mg",
                        }
                    ]
                },
                "status": "active",
            },
            {
                "resourceType": "MedicationRequest",
                "id": "m2",
                "medicationCodeableConcept": {
                    "coding": [
                        {
                            "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                            "code": "197361",
                            "display": "Lisinopril 10mg",
                        }
                    ]
                },
                "status": "active",
            },
        ],
        "note": "Demo data",
    }


def _demo_observations(patient_id: str) -> dict:
    return {
        "total": 2,
        "resources": [
            {
                "resourceType": "Observation",
                "id": "o1",
                "code": {"coding": [{"system": "http://loinc.org", "code": "8480-6", "display": "Systolic BP"}]},
                "valueQuantity": {"value": 128, "unit": "mmHg"},
            },
            {
                "resourceType": "Observation",
                "id": "o2",
                "code": {"coding": [{"system": "http://loinc.org", "code": "4548-4", "display": "HbA1c"}]},
                "valueQuantity": {"value": 7.2, "unit": "%"},
            },
        ],
        "note": "Demo data",
    }


def _demo_encounters(patient_id: str) -> dict:
    return {
        "total": 1,
        "resources": [
            {
                "resourceType": "Encounter",
                "id": "e1",
                "status": "finished",
                "class": {"code": "AMB"},
                "period": {"start": "2025-01-15", "end": "2025-01-15"},
            }
        ],
        "note": "Demo data",
    }


def _demo_practitioners() -> dict:
    return {
        "total": 1,
        "resources": [
            {
                "resourceType": "Practitioner",
                "id": "p1",
                "name": [{"family": "Johnson", "given": ["Sarah"]}],
                "identifier": [{"system": "http://hl7.org/fhir/sid/us-npi", "value": "1234567890"}],
            }
        ],
        "note": "Demo data",
    }


# ---------------------------------------------------------------------------
# Tool implementation functions
# ---------------------------------------------------------------------------

async def search_patients(params: dict) -> dict:
    """Search for patients."""
    if not FHIR_SERVER_URL:
        return _demo_patients(params)

    async with await get_fhir_client() as client:
        search_params = {k: v for k, v in params.items() if v}
        response = await client.get("/Patient", params=search_params)
        response.raise_for_status()
        bundle = response.json()

        return _format_bundle(bundle, "Patient")


async def get_patient(patient_id: str) -> dict:
    """Get a specific patient."""
    if not FHIR_SERVER_URL:
        return _demo_patient(patient_id)

    async with await get_fhir_client() as client:
        response = await client.get(f"/Patient/{patient_id}")
        if response.status_code == 404:
            return {"found": False, "patient_id": patient_id}
        response.raise_for_status()
        return {"found": True, "resource": response.json()}


async def get_patient_conditions(patient_id: str, clinical_status: Optional[str] = None, count: int = 50) -> dict:
    """Get patient conditions."""
    if not FHIR_SERVER_URL:
        return _demo_conditions(patient_id)

    params = {"patient": patient_id, "_count": count}
    if clinical_status:
        params["clinical-status"] = clinical_status

    async with await get_fhir_client() as client:
        response = await client.get("/Condition", params=params)
        response.raise_for_status()
        return _format_bundle(response.json(), "Condition")


async def get_patient_medications(patient_id: str, status: str = "active") -> dict:
    """Get patient medications."""
    if not FHIR_SERVER_URL:
        return _demo_medications(patient_id)

    params = {"patient": patient_id, "status": status}

    async with await get_fhir_client() as client:
        response = await client.get("/MedicationRequest", params=params)
        response.raise_for_status()
        return _format_bundle(response.json(), "MedicationRequest")


async def get_patient_observations(
    patient_id: str, category: Optional[str] = None, code: Optional[str] = None, count: int = 20
) -> dict:
    """Get patient observations."""
    if not FHIR_SERVER_URL:
        return _demo_observations(patient_id)

    params = {"patient": patient_id, "_count": count, "_sort": "-date"}
    if category:
        params["category"] = category
    if code:
        params["code"] = code

    async with await get_fhir_client() as client:
        response = await client.get("/Observation", params=params)
        response.raise_for_status()
        return _format_bundle(response.json(), "Observation")


async def get_patient_encounters(
    patient_id: str, status: Optional[str] = None, date: Optional[str] = None, count: int = 20
) -> dict:
    """Get patient encounters."""
    if not FHIR_SERVER_URL:
        return _demo_encounters(patient_id)

    params = {"patient": patient_id, "_count": count, "_sort": "-date"}
    if status:
        params["status"] = status
    if date:
        params["date"] = date

    async with await get_fhir_client() as client:
        response = await client.get("/Encounter", params=params)
        response.raise_for_status()
        return _format_bundle(response.json(), "Encounter")


async def search_practitioners(params: dict) -> dict:
    """Search for practitioners."""
    if not FHIR_SERVER_URL:
        return _demo_practitioners()

    async with await get_fhir_client() as client:
        search_params = {k: v for k, v in params.items() if v}
        response = await client.get("/Practitioner", params=search_params)
        response.raise_for_status()
        return _format_bundle(response.json(), "Practitioner")


async def validate_resource(resource_type: str, resource: dict) -> dict:
    """Validate a FHIR resource."""
    if not FHIR_SERVER_URL:
        return {"valid": True, "message": "Validation skipped (no FHIR server configured)"}

    async with await get_fhir_client() as client:
        response = await client.post(
            f"/{resource_type}/$validate", json=resource, headers={"Content-Type": "application/fhir+json"}
        )
        result = response.json()

        issues = result.get("issue", [])
        errors = [i for i in issues if i.get("severity") in ["error", "fatal"]]

        return {"valid": len(errors) == 0, "issues": issues}


# ---------------------------------------------------------------------------
# Handler dispatch map — maps tool names to lambda dispatch functions
# ---------------------------------------------------------------------------

HANDLERS = {
    "search_patients": lambda args: search_patients(args),
    "get_patient": lambda args: get_patient(args.get("patient_id", "")),
    "get_patient_conditions": lambda args: get_patient_conditions(
        args.get("patient_id", ""), args.get("clinical_status"), args.get("count", 50)
    ),
    "get_patient_medications": lambda args: get_patient_medications(
        args.get("patient_id", ""), args.get("status", "active")
    ),
    "get_patient_observations": lambda args: get_patient_observations(
        args.get("patient_id", ""), args.get("category"), args.get("code"), args.get("count", 20)
    ),
    "get_patient_encounters": lambda args: get_patient_encounters(
        args.get("patient_id", ""), args.get("status"), args.get("date"), args.get("count", 20)
    ),
    "search_practitioners": lambda args: search_practitioners(args),
    "validate_resource": lambda args: validate_resource(args.get("resource_type", ""), args.get("resource", {})),
}
