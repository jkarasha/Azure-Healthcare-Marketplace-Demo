"""Clinical trials search tools — ClinicalTrials.gov API v2 integration.

Migrated from standalone clinical-trials MCP server.
"""

import json
import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CT_API_BASE = "https://clinicaltrials.gov/api/v2"
DEMO_MODE = os.environ.get("DEMO_MODE", "false").lower() in ("true", "1", "yes")

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "search_by_condition",
        "description": "Find recruiting clinical trials for a specific condition near a location.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "condition": {"type": "string", "description": "Disease or condition"},
                "location": {"type": "string", "description": "City, state, or country"},
                "distance_miles": {
                    "type": "integer",
                    "description": "Search radius in miles",
                    "default": 50,
                },
            },
            "required": ["condition"],
        },
    },
    {
        "name": "search_clinical_trials",
        "description": "Search for clinical trials by condition, intervention, location, or keywords.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query (condition, drug, device, or keywords)",
                },
                "condition": {
                    "type": "string",
                    "description": "Filter by condition/disease (e.g., 'diabetes', 'breast cancer')",
                },
                "intervention": {
                    "type": "string",
                    "description": "Filter by intervention (drug, device, procedure name)",
                },
                "status": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": [
                            "RECRUITING",
                            "NOT_YET_RECRUITING",
                            "ACTIVE_NOT_RECRUITING",
                            "COMPLETED",
                            "ENROLLING_BY_INVITATION",
                            "SUSPENDED",
                            "TERMINATED",
                            "WITHDRAWN",
                        ],
                    },
                    "description": "Filter by recruitment status",
                },
                "phase": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": [
                            "EARLY_PHASE1",
                            "PHASE1",
                            "PHASE2",
                            "PHASE3",
                            "PHASE4",
                            "NA",
                        ],
                    },
                    "description": "Filter by trial phase",
                },
                "location_country": {
                    "type": "string",
                    "description": "Filter by country (e.g., 'United States')",
                },
                "location_state": {
                    "type": "string",
                    "description": "Filter by US state (e.g., 'California')",
                },
                "location_city": {"type": "string", "description": "Filter by city"},
                "page_size": {
                    "type": "integer",
                    "description": "Number of results (1-100, default 20)",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 20,
                },
            },
        },
    },
    {
        "name": "get_trial_details",
        "description": "Get detailed information about a specific clinical trial by NCT ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "nct_id": {
                    "type": "string",
                    "description": "NCT identifier (e.g., 'NCT04280705')",
                },
            },
            "required": ["nct_id"],
        },
    },
    {
        "name": "get_trial_eligibility",
        "description": "Get eligibility criteria for a clinical trial.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "nct_id": {"type": "string", "description": "NCT identifier"},
            },
            "required": ["nct_id"],
        },
    },
    {
        "name": "get_trial_locations",
        "description": "Get recruiting locations for a clinical trial.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "nct_id": {"type": "string", "description": "NCT identifier"},
                "status": {
                    "type": "string",
                    "description": "Filter locations by recruitment status",
                },
            },
            "required": ["nct_id"],
        },
    },
    {
        "name": "get_trial_results",
        "description": "Get results summary for a completed clinical trial (if available).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "nct_id": {"type": "string", "description": "NCT identifier"},
            },
            "required": ["nct_id"],
        },
    },
]

# ---------------------------------------------------------------------------
# Helper / formatter functions
# ---------------------------------------------------------------------------


def _format_trial_summary(study: dict) -> dict:
    """Format a trial summary from search results."""
    protocol = study.get("protocolSection", {})
    id_module = protocol.get("identificationModule", {})
    status_module = protocol.get("statusModule", {})
    design = protocol.get("designModule", {})
    conditions = protocol.get("conditionsModule", {})
    interventions = protocol.get("armsInterventionsModule", {})
    contacts = protocol.get("contactsLocationsModule", {})
    sponsor = protocol.get("sponsorCollaboratorsModule", {})

    locations = contacts.get("locations", [])
    location_summary: list[str] = []
    for loc in locations[:3]:
        city = loc.get("city", "")
        state = loc.get("state", "")
        country = loc.get("country", "")
        location_summary.append(f"{city}, {state}, {country}".strip(", "))

    return {
        "nct_id": id_module.get("nctId"),
        "title": id_module.get("briefTitle"),
        "status": status_module.get("overallStatus"),
        "phase": design.get("phases", ["N/A"]),
        "study_type": design.get("studyType"),
        "conditions": conditions.get("conditions", [])[:5],
        "interventions": [
            i.get("name") for i in interventions.get("interventions", [])
        ][:5],
        "enrollment": design.get("enrollmentInfo", {}).get("count"),
        "sponsor": sponsor.get("leadSponsor", {}).get("name"),
        "locations_preview": location_summary
        if location_summary
        else ["See trial for locations"],
    }


def _format_trial_detail(data: dict) -> dict:
    """Format detailed trial information."""
    protocol = data.get("protocolSection", {})

    id_module = protocol.get("identificationModule", {})
    status_module = protocol.get("statusModule", {})
    desc_module = protocol.get("descriptionModule", {})
    design = protocol.get("designModule", {})
    eligibility = protocol.get("eligibilityModule", {})
    outcomes = protocol.get("outcomesModule", {})
    sponsor = protocol.get("sponsorCollaboratorsModule", {})
    contacts = protocol.get("contactsLocationsModule", {})
    conditions = protocol.get("conditionsModule", {})
    interventions = protocol.get("armsInterventionsModule", {})

    return {
        "nct_id": id_module.get("nctId"),
        "title": id_module.get("briefTitle"),
        "official_title": id_module.get("officialTitle"),
        "status": status_module.get("overallStatus"),
        "start_date": status_module.get("startDateStruct", {}).get("date"),
        "completion_date": status_module.get("completionDateStruct", {}).get("date"),
        "description": desc_module.get("briefSummary"),
        "detailed_description": desc_module.get("detailedDescription"),
        "study_type": design.get("studyType"),
        "phase": design.get("phases", []),
        "enrollment": design.get("enrollmentInfo", {}).get("count"),
        "conditions": conditions.get("conditions", []),
        "interventions": [
            {
                "type": i.get("type"),
                "name": i.get("name"),
                "description": i.get("description"),
            }
            for i in interventions.get("interventions", [])
        ],
        "eligibility": {
            "criteria": eligibility.get("eligibilityCriteria"),
            "gender": eligibility.get("sex"),
            "min_age": eligibility.get("minimumAge"),
            "max_age": eligibility.get("maximumAge"),
            "healthy_volunteers": eligibility.get("healthyVolunteers"),
        },
        "primary_outcomes": [
            {
                "measure": o.get("measure"),
                "time_frame": o.get("timeFrame"),
                "description": o.get("description"),
            }
            for o in outcomes.get("primaryOutcomes", [])
        ],
        "sponsor": sponsor.get("leadSponsor", {}).get("name"),
        "collaborators": [c.get("name") for c in sponsor.get("collaborators", [])],
        "central_contacts": [
            {
                "name": c.get("name"),
                "role": c.get("role"),
                "phone": c.get("phone"),
                "email": c.get("email"),
            }
            for c in contacts.get("centralContacts", [])
        ],
    }


def _format_location(loc: dict) -> dict:
    """Format a trial location."""
    return {
        "facility": loc.get("facility"),
        "city": loc.get("city"),
        "state": loc.get("state"),
        "country": loc.get("country"),
        "status": loc.get("status"),
        "contact": {
            "name": (
                loc.get("contacts", [{}])[0].get("name")
                if loc.get("contacts")
                else None
            ),
            "phone": (
                loc.get("contacts", [{}])[0].get("phone")
                if loc.get("contacts")
                else None
            ),
            "email": (
                loc.get("contacts", [{}])[0].get("email")
                if loc.get("contacts")
                else None
            ),
        },
    }


def _extract_outcomes(protocol: dict, results: dict) -> list:
    """Extract primary outcome measures."""
    outcomes_module = results.get("outcomeMeasuresModule", {})
    outcome_measures = outcomes_module.get("outcomeMeasures", [])

    primary = [o for o in outcome_measures if o.get("type") == "PRIMARY"]

    return [
        {
            "title": o.get("title"),
            "description": o.get("description"),
            "time_frame": o.get("timeFrame"),
        }
        for o in primary[:5]
    ]


# ---------------------------------------------------------------------------
# Demo data helpers
# ---------------------------------------------------------------------------


def _demo_search_results(condition: str) -> dict:
    """Return canned search results when DEMO_MODE is enabled."""
    return {
        "total_count": 1,
        "returned_count": 1,
        "trials": [
            {
                "nct_id": "NCT00000000",
                "title": f"[DEMO] Sample Trial for {condition}",
                "status": "RECRUITING",
                "phase": ["PHASE3"],
                "study_type": "INTERVENTIONAL",
                "conditions": [condition],
                "interventions": ["Placebo", "Drug A"],
                "enrollment": 200,
                "sponsor": "Demo Sponsor",
                "locations_preview": ["New York, NY, United States"],
            }
        ],
    }


def _demo_trial_detail(nct_id: str) -> dict:
    """Return canned trial detail when DEMO_MODE is enabled."""
    return {
        "found": True,
        "trial": {
            "nct_id": nct_id,
            "title": "[DEMO] Sample Clinical Trial",
            "official_title": "[DEMO] A Randomized Controlled Trial",
            "status": "RECRUITING",
            "start_date": "2025-01-01",
            "completion_date": "2027-12-31",
            "description": "This is a demo trial record.",
            "detailed_description": None,
            "study_type": "INTERVENTIONAL",
            "phase": ["PHASE3"],
            "enrollment": 200,
            "conditions": ["Demo Condition"],
            "interventions": [
                {"type": "DRUG", "name": "Drug A", "description": "Test drug"},
            ],
            "eligibility": {
                "criteria": "Ages 18-65, confirmed diagnosis",
                "gender": "ALL",
                "min_age": "18 Years",
                "max_age": "65 Years",
                "healthy_volunteers": False,
            },
            "primary_outcomes": [],
            "sponsor": "Demo Sponsor",
            "collaborators": [],
            "central_contacts": [],
        },
    }


# ---------------------------------------------------------------------------
# Tool implementation functions
# ---------------------------------------------------------------------------


async def search_by_condition(
    condition: str,
    location: Optional[str] = None,
    distance_miles: int = 50,
) -> dict:
    """Search for recruiting trials by condition near an optional location."""
    if DEMO_MODE:
        return _demo_search_results(condition)

    params = {
        "query.cond": condition,
        "filter.overallStatus": "RECRUITING,NOT_YET_RECRUITING,ENROLLING_BY_INVITATION",
        "pageSize": 25,
        "fields": (
            "NCTId,BriefTitle,Phase,Condition,InterventionName,"
            "LocationFacility,LocationCity,LocationState,LocationCountry,"
            "EnrollmentCount"
        ),
    }

    if location:
        params["query.locn"] = location
        params["filter.geo"] = f"distance({distance_miles}mi)"

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{CT_API_BASE}/studies", params=params)
        response.raise_for_status()
        data = response.json()

        return {
            "condition": condition,
            "location": location,
            "total_recruiting": data.get("totalCount", 0),
            "trials": [_format_trial_summary(s) for s in data.get("studies", [])],
        }


async def search_clinical_trials(
    query: Optional[str] = None,
    condition: Optional[str] = None,
    intervention: Optional[str] = None,
    status: Optional[str] = None,
    phase: Optional[str] = None,
    max_results: int = 10,
    location_country: Optional[str] = None,
    location_state: Optional[str] = None,
    location_city: Optional[str] = None,
) -> dict:
    """Search for clinical trials with flexible filters."""
    if DEMO_MODE:
        return _demo_search_results(condition or query or "demo")

    params: dict = {"format": "json", "pageSize": min(max_results, 100)}

    # Build query string
    query_parts: list[str] = []
    if query:
        query_parts.append(query)
    if condition:
        params["query.cond"] = condition
    if intervention:
        params["query.intr"] = intervention

    if query_parts:
        params["query.term"] = " ".join(query_parts)

    # Status / phase filters
    if status:
        if isinstance(status, list):
            params["filter.overallStatus"] = ",".join(status)
        else:
            params["filter.overallStatus"] = status
    if phase:
        if isinstance(phase, list):
            params["filter.phase"] = ",".join(phase)
        else:
            params["filter.phase"] = phase

    # Location filters
    if location_country:
        params["query.locn"] = location_country
    if location_state:
        params["query.locn"] = (
            f"{location_state}, {location_country or 'United States'}"
        )
    if location_city:
        loc_parts = [location_city]
        if location_state:
            loc_parts.append(location_state)
        if location_country:
            loc_parts.append(location_country)
        params["query.locn"] = ", ".join(loc_parts)

    # Request fields
    params["fields"] = (
        "NCTId,BriefTitle,OverallStatus,Phase,Condition,InterventionName,"
        "LocationCity,LocationState,LocationCountry,StartDate,"
        "CompletionDate,EnrollmentCount,StudyType,LeadSponsorName"
    )

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{CT_API_BASE}/studies", params=params)
        response.raise_for_status()
        data = response.json()

        studies = data.get("studies", [])

        return {
            "total_count": data.get("totalCount", 0),
            "returned_count": len(studies),
            "trials": [_format_trial_summary(s) for s in studies],
        }


async def get_trial_details(nct_id: str) -> dict:
    """Get detailed trial information by NCT ID."""
    nct_id = nct_id.upper().strip()

    if DEMO_MODE:
        return _demo_trial_detail(nct_id)

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{CT_API_BASE}/studies/{nct_id}")

        if response.status_code == 404:
            return {"found": False, "nct_id": nct_id}

        response.raise_for_status()
        data = response.json()

        return {"found": True, "trial": _format_trial_detail(data)}


async def get_trial_eligibility(nct_id: str) -> dict:
    """Get trial eligibility criteria."""
    result = await get_trial_details(nct_id)

    if not result.get("found"):
        return result

    trial = result["trial"]

    return {
        "nct_id": nct_id,
        "title": trial.get("title"),
        "eligibility": trial.get("eligibility", {}),
        "healthy_volunteers": trial.get("eligibility", {}).get("healthy_volunteers"),
    }


async def get_trial_locations(nct_id: str, status: Optional[str] = None) -> dict:
    """Get trial locations, optionally filtered by recruitment status."""
    nct_id = nct_id.upper().strip()

    if DEMO_MODE:
        return {
            "nct_id": nct_id,
            "title": "[DEMO] Sample Clinical Trial",
            "location_count": 1,
            "locations": [
                {
                    "facility": "Demo Medical Center",
                    "city": "New York",
                    "state": "New York",
                    "country": "United States",
                    "status": "RECRUITING",
                    "contact": {"name": None, "phone": None, "email": None},
                }
            ],
        }

    params = {
        "fields": (
            "NCTId,BriefTitle,LocationFacility,LocationCity,LocationState,"
            "LocationCountry,LocationStatus,LocationContactName,"
            "LocationContactPhone,LocationContactEMail"
        ),
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{CT_API_BASE}/studies/{nct_id}", params=params
        )

        if response.status_code == 404:
            return {"found": False, "nct_id": nct_id}

        response.raise_for_status()
        data = response.json()

        protocol = data.get("protocolSection", {})
        contacts_locations = protocol.get("contactsLocationsModule", {})
        locations = contacts_locations.get("locations", [])

        # Optional status filter
        if status:
            locations = [
                loc for loc in locations if loc.get("status") == status
            ]

        return {
            "nct_id": nct_id,
            "title": protocol.get("identificationModule", {}).get("briefTitle"),
            "location_count": len(locations),
            "locations": [_format_location(loc) for loc in locations],
        }


async def get_trial_results(nct_id: str) -> dict:
    """Get trial results if available."""
    nct_id = nct_id.upper().strip()

    if DEMO_MODE:
        return {
            "nct_id": nct_id,
            "title": "[DEMO] Sample Clinical Trial",
            "status": "COMPLETED",
            "has_results": False,
            "results_posted_date": None,
            "primary_outcomes": "Results not yet posted",
        }

    params = {
        "fields": (
            "NCTId,BriefTitle,OverallStatus,ResultsFirstPostDate,"
            "PrimaryOutcomeMeasure,PrimaryOutcomeDescription,"
            "OutcomeMeasureTitle,OutcomeMeasureType"
        ),
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{CT_API_BASE}/studies/{nct_id}", params=params
        )

        if response.status_code == 404:
            return {"found": False, "nct_id": nct_id}

        response.raise_for_status()
        data = response.json()

        protocol = data.get("protocolSection", {})
        results = data.get("resultsSection", {})

        has_results = bool(results)

        return {
            "nct_id": nct_id,
            "title": protocol.get("identificationModule", {}).get("briefTitle"),
            "status": protocol.get("statusModule", {}).get("overallStatus"),
            "has_results": has_results,
            "results_posted_date": (
                protocol.get("statusModule", {})
                .get("resultsFirstPostDateStruct", {})
                .get("date")
                if has_results
                else None
            ),
            "primary_outcomes": (
                _extract_outcomes(protocol, results)
                if has_results
                else "Results not yet posted"
            ),
        }


# ---------------------------------------------------------------------------
# Handler dispatch map
# ---------------------------------------------------------------------------

HANDLERS = {
    "search_by_condition": lambda args: search_by_condition(
        args.get("condition", ""),
        args.get("location"),
        args.get("distance_miles", 50),
    ),
    "search_clinical_trials": lambda args: search_clinical_trials(
        args.get("query", ""),
        args.get("condition"),
        args.get("intervention"),
        args.get("status", "RECRUITING"),
        args.get("phase"),
        args.get("max_results", 10),
    ),
    "get_trial_details": lambda args: get_trial_details(args.get("nct_id", "")),
    "get_trial_eligibility": lambda args: get_trial_eligibility(
        args.get("nct_id", "")
    ),
    "get_trial_locations": lambda args: get_trial_locations(
        args.get("nct_id", ""), args.get("status")
    ),
    "get_trial_results": lambda args: get_trial_results(args.get("nct_id", "")),
}
