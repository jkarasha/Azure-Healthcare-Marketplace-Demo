"""
NPI Lookup tools — provider verification and search via CMS NPI Registry.

Migrated from standalone npi-lookup MCP server.
"""

import httpx

NPI_REGISTRY_URL = "https://npiregistry.cms.hhs.gov/api/"

TOOLS = [
    {
        "name": "lookup_npi",
        "description": "Look up a healthcare provider by their NPI number. Returns provider details including name, specialty, address, and credentials.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "npi": {
                    "type": "string",
                    "description": "The 10-digit National Provider Identifier number",
                    "pattern": "^[0-9]{10}$",
                }
            },
            "required": ["npi"],
        },
    },
    {
        "name": "search_providers",
        "description": "Search for healthcare providers by name, specialty, or location. Returns a list of matching providers with their NPI numbers.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "first_name": {
                    "type": "string",
                    "description": "Provider's first name (for individual providers)",
                },
                "last_name": {
                    "type": "string",
                    "description": "Provider's last name (for individual providers)",
                },
                "organization_name": {
                    "type": "string",
                    "description": "Organization name (for organizational providers)",
                },
                "taxonomy_description": {
                    "type": "string",
                    "description": "Provider specialty/taxonomy (e.g., 'Family Medicine', 'Cardiology')",
                },
                "city": {"type": "string", "description": "City where provider practices"},
                "state": {
                    "type": "string",
                    "description": "Two-letter state code (e.g., 'CA', 'NY')",
                    "pattern": "^[A-Z]{2}$",
                },
                "postal_code": {"type": "string", "description": "5-digit ZIP code"},
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results (1-200, default 10)",
                    "minimum": 1,
                    "maximum": 200,
                    "default": 10,
                },
            },
        },
    },
    {
        "name": "validate_npi",
        "description": "Validate that an NPI number is correctly formatted and exists in the NPI Registry.",
        "inputSchema": {
            "type": "object",
            "properties": {"npi": {"type": "string", "description": "The NPI number to validate"}},
            "required": ["npi"],
        },
    },
]


async def lookup_npi(npi: str) -> dict:
    """Look up provider by NPI number."""
    async with httpx.AsyncClient() as client:
        response = await client.get(NPI_REGISTRY_URL, params={"number": npi, "version": "2.1"})
        response.raise_for_status()
        data = response.json()

        if data.get("result_count", 0) == 0:
            return {"found": False, "npi": npi, "message": "NPI not found in registry"}

        result = data["results"][0]
        return {
            "found": True,
            "npi": npi,
            "provider_type": "Individual" if result.get("enumeration_type") == "NPI-1" else "Organization",
            "basic": result.get("basic", {}),
            "addresses": result.get("addresses", []),
            "taxonomies": result.get("taxonomies", []),
            "identifiers": result.get("identifiers", []),
        }


async def search_providers(params: dict) -> dict:
    """Search for providers by various criteria."""
    query_params = {"version": "2.1"}

    param_mapping = {
        "first_name": "first_name",
        "last_name": "last_name",
        "organization_name": "organization_name",
        "taxonomy_description": "taxonomy_description",
        "city": "city",
        "state": "state",
        "postal_code": "postal_code",
        "limit": "limit",
    }

    for key, api_key in param_mapping.items():
        if params.get(key):
            query_params[api_key] = params[key]

    if "limit" not in query_params:
        query_params["limit"] = 10

    async with httpx.AsyncClient() as client:
        response = await client.get(NPI_REGISTRY_URL, params=query_params)
        response.raise_for_status()
        data = response.json()

        return {
            "result_count": data.get("result_count", 0),
            "providers": [
                {
                    "npi": r.get("number"),
                    "provider_type": "Individual" if r.get("enumeration_type") == "NPI-1" else "Organization",
                    "name": _format_provider_name(r),
                    "specialty": _get_primary_taxonomy(r),
                    "address": _format_primary_address(r),
                }
                for r in data.get("results", [])
            ],
        }


async def validate_npi(npi: str) -> dict:
    """Validate NPI number format and existence."""
    if not npi or len(npi) != 10 or not npi.isdigit():
        return {"valid": False, "npi": npi, "reason": "NPI must be exactly 10 digits"}

    if not _luhn_check(f"80840{npi}"):
        return {"valid": False, "npi": npi, "reason": "NPI fails checksum validation"}

    result = await lookup_npi(npi)
    if not result.get("found"):
        return {"valid": False, "npi": npi, "reason": "NPI not found in CMS registry"}

    return {
        "valid": True,
        "npi": npi,
        "provider_name": _format_provider_name_from_basic(result.get("basic", {})),
        "provider_type": result.get("provider_type"),
    }


def _luhn_check(number: str) -> bool:
    digits = [int(d) for d in number]
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    checksum = sum(odd_digits)
    for d in even_digits:
        checksum += sum(divmod(d * 2, 10))
    return checksum % 10 == 0


def _format_provider_name(result: dict) -> str:
    basic = result.get("basic", {})
    return _format_provider_name_from_basic(basic)


def _format_provider_name_from_basic(basic: dict) -> str:
    if basic.get("organization_name"):
        return basic["organization_name"]
    parts = []
    if basic.get("first_name"):
        parts.append(basic["first_name"])
    if basic.get("last_name"):
        parts.append(basic["last_name"])
    if basic.get("credential"):
        parts.append(f", {basic['credential']}")
    return " ".join(parts) if parts else "Unknown"


def _get_primary_taxonomy(result: dict) -> str:
    taxonomies = result.get("taxonomies", [])
    for t in taxonomies:
        if t.get("primary"):
            return t.get("desc", "Unknown")
    return taxonomies[0].get("desc", "Unknown") if taxonomies else "Unknown"


def _format_primary_address(result: dict) -> str:
    addresses = result.get("addresses", [])
    for addr in addresses:
        if addr.get("address_purpose") == "LOCATION":
            parts = [
                addr.get("address_1", ""),
                addr.get("city", ""),
                addr.get("state", ""),
                addr.get("postal_code", "")[:5] if addr.get("postal_code") else "",
            ]
            return ", ".join(p for p in parts if p)
    return "Address not available"


# Tool dispatch map
HANDLERS = {
    "lookup_npi": lambda args: lookup_npi(args.get("npi", "")),
    "search_providers": lambda args: search_providers(args),
    "validate_npi": lambda args: validate_npi(args.get("npi", "")),
}
