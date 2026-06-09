# MCP Server Integration Tests

End-to-end tests that exercise live MCP servers over HTTP.

## Prerequisites

Start the MCP servers locally before running tests:

```bash
# All servers via Make
make local-start

# Or via Docker Compose
make docker-up
```

## Run tests

```bash
# All integration tests (servers must be running)
pytest tests/integration -v -m integration

# Single server
pytest tests/integration/test_npi_lookup.py -v

# With Docker key
MCP_FUNCTION_KEY=docker-default-key pytest tests/integration -v -m integration
```

## Configuration

Override ports and host via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_BASE_HOST` | `http://localhost` | Base host for all servers |
| `MCP_NPI_PORT` | `7071` | NPI Lookup port |
| `MCP_ICD10_PORT` | `7072` | ICD-10 Validation port |
| `MCP_CMS_PORT` | `7073` | CMS Coverage port |
| `MCP_FHIR_PORT` | `7074` | FHIR Operations port |
| `MCP_PUBMED_PORT` | `7075` | PubMed port |
| `MCP_CLINICALTRIALS_PORT` | `7076` | Clinical Trials port |
| `MCP_FUNCTION_KEY` | *(empty)* | Function key (set for Docker) |
