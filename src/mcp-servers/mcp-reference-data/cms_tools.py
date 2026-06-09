"""
CMS Coverage tools — Medicare coverage determination lookup.

Migrated from standalone cms-coverage MCP server.
"""

from typing import Optional

TOOLS = [
    {
        "name": "search_coverage",
        "description": "Search for Medicare coverage determinations (LCD/NCD) by keyword, procedure, or diagnosis. Returns relevant coverage policies.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search term (e.g., 'MRI lumbar spine', 'diabetes screening', 'knee replacement')",
                },
                "coverage_type": {
                    "type": "string",
                    "enum": ["all", "lcd", "ncd"],
                    "description": "Type of coverage determination: 'lcd' (Local), 'ncd' (National), or 'all'",
                    "default": "all",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results (1-20, default 10)",
                    "minimum": 1,
                    "maximum": 20,
                    "default": 10,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_coverage_by_cpt",
        "description": "Get Medicare coverage information for a specific CPT/HCPCS procedure code.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "cpt_code": {"type": "string", "description": "CPT or HCPCS procedure code (e.g., '99213', 'G0438')"}
            },
            "required": ["cpt_code"],
        },
    },
    {
        "name": "get_coverage_by_icd10",
        "description": "Get Medicare coverage policies related to a specific ICD-10 diagnosis code.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "icd10_code": {"type": "string", "description": "ICD-10-CM diagnosis code (e.g., 'E11.9', 'M54.5')"}
            },
            "required": ["icd10_code"],
        },
    },
    {
        "name": "check_medical_necessity",
        "description": "Check if a procedure is medically necessary for a given diagnosis according to Medicare coverage policies.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "cpt_code": {"type": "string", "description": "CPT or HCPCS procedure code"},
                "icd10_codes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of ICD-10-CM diagnosis codes supporting medical necessity",
                },
            },
            "required": ["cpt_code", "icd10_codes"],
        },
    },
    {
        "name": "get_mac_jurisdiction",
        "description": "Get Medicare Administrative Contractor (MAC) information for a state or ZIP code.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "state": {"type": "string", "description": "Two-letter state code (e.g., 'CA', 'NY')"},
                "zip_code": {"type": "string", "description": "5-digit ZIP code (alternative to state)"},
            },
        },
    },
]

MAC_JURISDICTIONS = {
    "CA": {"mac": "Noridian Healthcare Solutions", "jurisdiction": "JE", "part_a": "Part A/B MAC"},
    "NY": {"mac": "National Government Services", "jurisdiction": "JK", "part_a": "Part A/B MAC"},
    "TX": {"mac": "Novitas Solutions", "jurisdiction": "JH", "part_a": "Part A/B MAC"},
    "FL": {"mac": "First Coast Service Options", "jurisdiction": "JN", "part_a": "Part A/B MAC"},
    "IL": {"mac": "National Government Services", "jurisdiction": "JK", "part_a": "Part A/B MAC"},
    "PA": {"mac": "Novitas Solutions", "jurisdiction": "JL", "part_a": "Part A/B MAC"},
    "OH": {"mac": "CGS Administrators", "jurisdiction": "J15", "part_a": "Part A/B MAC"},
    "GA": {"mac": "Palmetto GBA", "jurisdiction": "JJ", "part_a": "Part A/B MAC"},
    "NC": {"mac": "Palmetto GBA", "jurisdiction": "JM", "part_a": "Part A/B MAC"},
    "MI": {"mac": "Wisconsin Physicians Service", "jurisdiction": "J8", "part_a": "Part A/B MAC"},
}

COMMON_COVERAGES = {
    "99213": {
        "description": "Office visit, established patient, low complexity",
        "coverage": "covered",
        "conditions": "Medical necessity must be documented",
        "frequency": "As medically necessary",
    },
    "99214": {
        "description": "Office visit, established patient, moderate complexity",
        "coverage": "covered",
        "conditions": "Medical necessity must be documented",
        "frequency": "As medically necessary",
    },
    "G0438": {
        "description": "Annual wellness visit, initial",
        "coverage": "covered",
        "conditions": "Once per lifetime for initial visit",
        "frequency": "Once per lifetime",
    },
    "G0439": {
        "description": "Annual wellness visit, subsequent",
        "coverage": "covered",
        "conditions": "12 months after initial AWV",
        "frequency": "Once per 12 months",
    },
    "72148": {
        "description": "MRI lumbar spine without contrast",
        "coverage": "covered_with_conditions",
        "conditions": "LCD applies - must meet medical necessity criteria including failed conservative treatment",
        "lcd_reference": "L34997",
    },
    "27447": {
        "description": "Total knee arthroplasty",
        "coverage": "covered_with_conditions",
        "conditions": "NCD 150.9 - Documentation of functional limitation and failed conservative treatment required",
        "ncd_reference": "150.9",
    },
}


async def search_coverage(query: str, coverage_type: str = "all", limit: int = 10) -> dict:
    results = []
    query_lower = query.lower()

    if "mri" in query_lower or "imaging" in query_lower:
        results.append(
            {
                "type": "LCD",
                "id": "L34997",
                "title": "Magnetic Resonance Imaging (MRI) of the Spine",
                "contractor": "Multiple MACs",
                "effective_date": "2023-10-01",
                "summary": "Outlines coverage criteria for MRI of the spine including medical necessity requirements",
            }
        )

    if "knee" in query_lower or "arthroplasty" in query_lower:
        results.append(
            {
                "type": "NCD",
                "id": "150.9",
                "title": "Knee Arthroplasty (Knee Replacement Surgery)",
                "effective_date": "2022-04-01",
                "summary": "National coverage criteria for total and partial knee replacement surgery",
            }
        )

    if "diabetes" in query_lower or "glucose" in query_lower:
        results.append(
            {
                "type": "NCD",
                "id": "40.2",
                "title": "Home Blood Glucose Monitors",
                "effective_date": "2021-01-01",
                "summary": "Coverage of home blood glucose monitors for diabetic patients",
            }
        )
        results.append(
            {
                "type": "LCD",
                "id": "L33822",
                "title": "Continuous Glucose Monitors",
                "contractor": "CGS Administrators",
                "effective_date": "2023-01-01",
                "summary": "Local coverage for CGM devices and supplies",
            }
        )

    if "screening" in query_lower or "preventive" in query_lower:
        results.append(
            {
                "type": "NCD",
                "id": "210.10",
                "title": "Screening for Lung Cancer with LDCT",
                "effective_date": "2022-02-10",
                "summary": "Annual screening for lung cancer with LDCT for eligible beneficiaries",
            }
        )

    if coverage_type != "all":
        results = [r for r in results if r["type"].lower() == coverage_type.lower()]

    return {
        "query": query,
        "coverage_type": coverage_type,
        "result_count": len(results[:limit]),
        "results": results[:limit],
    }


async def get_coverage_by_cpt(cpt_code: str) -> dict:
    code = cpt_code.upper().strip()

    if code in COMMON_COVERAGES:
        coverage = COMMON_COVERAGES[code]
        return {
            "code": code,
            "found": True,
            "description": coverage["description"],
            "medicare_coverage": coverage["coverage"],
            "conditions": coverage["conditions"],
            "frequency_limitation": coverage.get("frequency"),
            "lcd_reference": coverage.get("lcd_reference"),
            "ncd_reference": coverage.get("ncd_reference"),
        }

    return {
        "code": code,
        "found": False,
        "message": "Coverage information not found in local database. Recommend checking CMS Medicare Coverage Database directly.",
        "cms_link": f"https://www.cms.gov/medicare-coverage-database/search.aspx?q={code}",
    }


async def get_coverage_by_icd10(icd10_code: str) -> dict:
    code = icd10_code.upper().strip()
    results = []

    if code.startswith("E11") or code.startswith("E10"):
        results.append(
            {
                "code": code,
                "diagnosis_group": "Diabetes Mellitus",
                "relevant_coverages": [
                    {"type": "NCD", "id": "40.2", "title": "Home Blood Glucose Monitors"},
                    {"type": "LCD", "id": "L33822", "title": "Continuous Glucose Monitors"},
                    {"type": "NCD", "id": "280.1", "title": "Diabetes Self-Management Training"},
                ],
            }
        )

    if code.startswith("M54"):
        results.append(
            {
                "code": code,
                "diagnosis_group": "Dorsalgia (Back Pain)",
                "relevant_coverages": [
                    {"type": "LCD", "id": "L34997", "title": "MRI of the Spine"},
                    {"type": "LCD", "id": "L35036", "title": "Lumbar Spinal Fusion"},
                ],
            }
        )

    if not results:
        return {
            "code": code,
            "found": False,
            "message": "No specific coverage policies found for this diagnosis code",
            "recommendation": "Check CMS Medicare Coverage Database for related coverage policies",
        }

    return {"code": code, "found": True, "results": results}


async def check_medical_necessity(cpt_code: str, icd10_codes: list[str]) -> dict:
    cpt = cpt_code.upper().strip()
    diagnoses = [d.upper().strip() for d in icd10_codes]

    coverage = COMMON_COVERAGES.get(cpt)

    if not coverage:
        return {
            "cpt_code": cpt,
            "icd10_codes": diagnoses,
            "determination": "unknown",
            "message": "CPT code not found in coverage database. Manual review required.",
        }

    result = {
        "cpt_code": cpt,
        "cpt_description": coverage["description"],
        "icd10_codes": diagnoses,
        "base_coverage": coverage["coverage"],
        "coverage_conditions": coverage["conditions"],
    }

    if coverage["coverage"] == "covered":
        result["determination"] = "likely_covered"
        result["message"] = "Procedure is generally covered. Ensure documentation supports medical necessity."
    elif coverage["coverage"] == "covered_with_conditions":
        result["determination"] = "review_required"
        result["message"] = "Procedure requires specific criteria. Review LCD/NCD requirements."
        if coverage.get("lcd_reference"):
            result["lcd_reference"] = coverage["lcd_reference"]
        if coverage.get("ncd_reference"):
            result["ncd_reference"] = coverage["ncd_reference"]
    else:
        result["determination"] = "not_covered"
        result["message"] = "Procedure may not be covered under Medicare."

    return result


async def get_mac_jurisdiction(state: Optional[str] = None, zip_code: Optional[str] = None) -> dict:
    if not state and not zip_code:
        return {"error": "Either state or zip_code is required"}

    lookup_state = state.upper() if state else None

    if zip_code and not state:
        return {"zip_code": zip_code, "message": "ZIP code lookup not implemented. Please provide state code."}

    if lookup_state in MAC_JURISDICTIONS:
        mac_info = MAC_JURISDICTIONS[lookup_state]
        return {
            "state": lookup_state,
            "found": True,
            "mac_name": mac_info["mac"],
            "jurisdiction": mac_info["jurisdiction"],
            "mac_type": mac_info["part_a"],
            "contact_info": f"Visit MAC website for {mac_info['mac']}",
        }

    return {"state": lookup_state, "found": False, "message": "State not found in MAC database"}


HANDLERS = {
    "search_coverage": lambda args: search_coverage(
        args.get("query", ""), args.get("coverage_type", "all"), args.get("limit", 10)
    ),
    "get_coverage_by_cpt": lambda args: get_coverage_by_cpt(args.get("cpt_code", "")),
    "get_coverage_by_icd10": lambda args: get_coverage_by_icd10(args.get("icd10_code", "")),
    "check_medical_necessity": lambda args: check_medical_necessity(
        args.get("cpt_code", ""), args.get("icd10_codes", [])
    ),
    "get_mac_jurisdiction": lambda args: get_mac_jurisdiction(args.get("state"), args.get("zip_code")),
}
