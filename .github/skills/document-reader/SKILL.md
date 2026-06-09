---
name: document-reader
description: "Load local documents (PDFs, images, handwritten scans, JSON/CSV, text) via the document-reader MCP tool so agents can extract and summarize content without re-implementing file I/O."
---

# Document Reader Skill

Use this skill when the user provides (or references) local files and you need a reliable way to ingest them into the agent workflow:
- Unstructured docs: PDFs, images, scanned or handwritten notes (returned as base64 + mime)
- Structured docs: JSON, NDJSON, CSV/TSV (returned as text plus optional parsing)
- Plain text: TXT/MD/etc.

This avoids ad-hoc “write a quick Python function to read X” every time.

## Prerequisites (Local)

1. Start the MCP server:
```bash
./scripts/local-test.sh document-reader 7078
```

2. Ensure `.vscode/mcp.json` includes:
- `local-document-reader`: `http://localhost:7078/mcp`

## Tool: `read_document`

### When To Use
- The user says “see attached PDF/image” or provides a file path
- You need to extract fields from a form, notes, or report
- You need to load structured input (JSON/CSV) for transformation/validation

### Safety Defaults
- Reads are **workspace-only by default**. To read outside the repo, set `allow_outside_workspace=true`.
- Large files are blocked or truncated via `max_bytes` / `max_chars`.

### Typical Calls

Read a PDF or image as base64 (for downstream OCR/vision or archive):
```json
{
  "path": "data/intake/scanned_note.jpg",
  "mode": "binary",
  "include_data_url": true
}
```

Read JSON (returns both `text` and parsed `json` when valid):
```json
{
  "path": "data/sample_cases/prior_auth_baseline/pa_request.json",
  "mode": "text",
  "parse_structured": true
}
```

Read CSV (returns `rows` up to `max_rows`):
```json
{
  "path": "data/input/patients.csv",
  "mode": "text",
  "max_rows": 200
}
```

## Suggested Workflow

1. Call `read_document` for each referenced file path.
2. For binaries (PDF/images), use the returned `mime` + `data_url`/`base64` to drive downstream extraction.
3. Produce a de-identified structured summary (never commit PHI or secrets).

