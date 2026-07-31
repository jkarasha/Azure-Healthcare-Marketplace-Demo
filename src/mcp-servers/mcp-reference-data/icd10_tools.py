"""
ICD-10-CM validation tools — code validation, lookup, and search via NLM Clinical Tables.

Migrated from standalone icd10-validation MCP server.
"""

import re

import httpx

ICD10_API_URL = "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search"

TOOLS = [
    {
        "name": "validate_icd10",
        "description": "Validate an ICD-10-CM diagnosis code. Checks format and verifies the code exists in the official code set.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "The ICD-10-CM code to validate (e.g., 'E11.9', 'J18.9')"}
            },
            "required": ["code"],
        },
    },
    {
        "name": "lookup_icd10",
        "description": "Look up an ICD-10-CM code and return its description, category, and related codes.",
        "inputSchema": {
            "type": "object",
            "properties": {"code": {"type": "string", "description": "The ICD-10-CM code to look up"}},
            "required": ["code"],
        },
    },
    {
        "name": "search_icd10",
        "description": "Search for ICD-10-CM codes by description or keyword. Returns matching codes with descriptions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search term (e.g., 'diabetes', 'pneumonia', 'fracture femur')",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results (1-50, default 10)",
                    "minimum": 1,
                    "maximum": 50,
                    "default": 10,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_icd10_chapter",
        "description": "Get information about an ICD-10-CM chapter or category based on a code prefix.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code_prefix": {
                    "type": "string",
                    "description": "ICD-10 code prefix (e.g., 'E11' for Type 2 diabetes, 'J' for respiratory)",
                }
            },
            "required": ["code_prefix"],
        },
    },
]

ICD10_CHAPTERS = {
    "A": ("A00-B99", "Certain infectious and parasitic diseases"),
    "B": ("A00-B99", "Certain infectious and parasitic diseases"),
    "C": ("C00-D49", "Neoplasms"),
    "D": ("D50-D89", "Diseases of the blood and blood-forming organs"),
    "E": ("E00-E89", "Endocrine, nutritional and metabolic diseases"),
    "F": ("F01-F99", "Mental, behavioral and neurodevelopmental disorders"),
    "G": ("G00-G99", "Diseases of the nervous system"),
    "H": ("H00-H59", "Diseases of the eye and adnexa / ear and mastoid process"),
    "I": ("I00-I99", "Diseases of the circulatory system"),
    "J": ("J00-J99", "Diseases of the respiratory system"),
    "K": ("K00-K95", "Diseases of the digestive system"),
    "L": ("L00-L99", "Diseases of the skin and subcutaneous tissue"),
    "M": ("M00-M99", "Diseases of the musculoskeletal system and connective tissue"),
    "N": ("N00-N99", "Diseases of the genitourinary system"),
    "O": ("O00-O9A", "Pregnancy, childbirth and the puerperium"),
    "P": ("P00-P96", "Certain conditions originating in the perinatal period"),
    "Q": ("Q00-Q99", "Congenital malformations, deformations and chromosomal abnormalities"),
    "R": ("R00-R99", "Symptoms, signs and abnormal clinical and laboratory findings"),
    "S": ("S00-T88", "Injury, poisoning and certain other consequences of external causes"),
    "T": ("S00-T88", "Injury, poisoning and certain other consequences of external causes"),
    "V": ("V00-Y99", "External causes of morbidity"),
    "W": ("V00-Y99", "External causes of morbidity"),
    "X": ("V00-Y99", "External causes of morbidity"),
    "Y": ("V00-Y99", "External causes of morbidity"),
    "Z": ("Z00-Z99", "Factors influencing health status and contact with health services"),
}


def _validate_icd10_format(code: str) -> tuple[bool, str]:
    clean_code = code.upper().replace(".", "")
    pattern = r"^[A-Z][0-9][0-9A-Z]{0,5}$"
    if not re.match(pattern, clean_code):
        return False, "Invalid format. ICD-10-CM codes start with a letter followed by 2-6 alphanumeric characters"
    if clean_code[0] not in ICD10_CHAPTERS and clean_code[0] != "U":
        return False, f"Invalid category letter: {clean_code[0]}"
    return True, "Format valid"


def _search_term(clean_code: str) -> str:
    """Restore the decimal point for NLM lookups.

    The NLM table indexes codes in dotted form, so "K5080" returns no rows
    even though "K50.80" exists. Callers accept undotted input, and the dot
    always follows the 3-character category.
    """
    return clean_code if len(clean_code) <= 3 else f"{clean_code[:3]}.{clean_code[3:]}"


async def validate_icd10(code: str) -> dict:
    format_valid, format_msg = _validate_icd10_format(code)
    if not format_valid:
        return {"valid": False, "code": code, "reason": format_msg}

    clean_code = code.upper().replace(".", "")
    search_term = _search_term(clean_code)
    async with httpx.AsyncClient() as client:
        response = await client.get(ICD10_API_URL, params={"terms": search_term, "maxList": 10, "sf": "code"})
        response.raise_for_status()
        data = response.json()

        if data[0] > 0 and clean_code in [c.replace(".", "") for c in data[1]]:
            idx = [c.replace(".", "") for c in data[1]].index(clean_code)
            return {
                "valid": True,
                "code": data[1][idx],
                # data[3][idx] is [code, description]; [0] would echo the code.
                "description": (
                    data[3][idx][1] if data[3] and len(data[3][idx]) > 1 else "Description not available"
                ),
            }

        return {"valid": False, "code": code, "reason": "Code not found in ICD-10-CM code set"}


async def lookup_icd10(code: str) -> dict:
    clean_code = code.upper().replace(".", "")

    async with httpx.AsyncClient() as client:
        response = await client.get(
            ICD10_API_URL, params={"terms": _search_term(clean_code), "maxList": 10, "sf": "code"}
        )
        response.raise_for_status()
        data = response.json()

        if data[0] == 0:
            return {"found": False, "code": code, "message": "Code not found"}

        codes = data[1]
        descriptions = data[3]

        for i, c in enumerate(codes):
            if c.replace(".", "") == clean_code:
                first_letter = clean_code[0]
                chapter_info = ICD10_CHAPTERS.get(first_letter, ("Unknown", "Unknown"))

                return {
                    "found": True,
                    "code": c,
                    "description": descriptions[i][1] if len(descriptions[i]) > 1 else "N/A",
                    "chapter": {"range": chapter_info[0], "name": chapter_info[1]},
                    "category": clean_code[:3],
                    "is_billable": len(clean_code) >= 4,
                }

        return {
            "found": False,
            "code": code,
            "message": "Exact code not found",
            "similar_codes": [
                {"code": codes[i], "description": descriptions[i][1] if len(descriptions[i]) > 1 else "N/A"}
                for i in range(min(5, len(codes)))
            ],
        }


async def search_icd10(query: str, limit: int = 10) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(ICD10_API_URL, params={"terms": query, "maxList": limit})
        response.raise_for_status()
        data = response.json()

        if data[0] == 0:
            return {"query": query, "result_count": 0, "results": []}

        results = []
        for i in range(min(data[0], limit)):
            results.append(
                {"code": data[1][i], "description": data[3][i][0] if data[3] and i < len(data[3]) else "N/A"}
            )

        return {"query": query, "result_count": len(results), "results": results}


async def get_icd10_chapter(code_prefix: str) -> dict:
    prefix = code_prefix.upper().replace(".", "")

    if not prefix:
        return {"error": "Code prefix required"}

    first_letter = prefix[0]
    if first_letter not in ICD10_CHAPTERS:
        return {"prefix": code_prefix, "found": False, "message": f"Unknown chapter for prefix: {code_prefix}"}

    chapter_info = ICD10_CHAPTERS[first_letter]

    async with httpx.AsyncClient() as client:
        response = await client.get(ICD10_API_URL, params={"terms": prefix, "maxList": 10, "sf": "code"})
        response.raise_for_status()
        data = response.json()

        examples = []
        if data[0] > 0:
            for i in range(min(5, data[0])):
                examples.append(
                    {"code": data[1][i], "description": data[3][i][0] if data[3] and i < len(data[3]) else "N/A"}
                )

    return {
        "prefix": code_prefix,
        "found": True,
        "chapter": {"range": chapter_info[0], "name": chapter_info[1]},
        "example_codes": examples,
    }


HANDLERS = {
    "validate_icd10": lambda args: validate_icd10(args.get("code", "")),
    "lookup_icd10": lambda args: lookup_icd10(args.get("code", "")),
    "search_icd10": lambda args: search_icd10(args.get("query", ""), args.get("limit", 10)),
    "get_icd10_chapter": lambda args: get_icd10_chapter(args.get("code_prefix", "")),
}
