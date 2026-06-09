#!/usr/bin/env python3
"""
Seed Cosmos DB vector store with healthcare coverage policy PDFs.

Extracts text from policy PDFs in data/policies/,
chunks the content, generates embeddings, and upserts into the Cosmos DB
`documents` container (category='payer-policy') for hybrid RAG retrieval.

Supports two modes:
  1. --mcp   : Index via the cosmos-rag MCP server's index_document tool (default)
  2. --direct: Write directly to Cosmos DB using the Python SDK

Usage:
  # Via MCP server (server must be running on --port)
  python scripts/seed_cosmos_policies.py --mcp --port 7077

  # Direct to Cosmos DB (requires COSMOS_DB_ENDPOINT, AZURE_AI_SERVICES_ENDPOINT)
  python scripts/seed_cosmos_policies.py --direct

  # Dry-run: extract text only, no writes
  python scripts/seed_cosmos_policies.py --dry-run

Environment Variables (direct mode):
  COSMOS_DB_ENDPOINT          - Cosmos DB account endpoint
  COSMOS_DB_DATABASE           - Database name (default: healthcare-mcp)
  AZURE_AI_SERVICES_ENDPOINT   - Azure OpenAI endpoint for embeddings
  EMBEDDING_DEPLOYMENT_NAME    - Deployment name (default: text-embedding-3-large)
  EMBEDDING_DIMENSIONS         - Vector dimensions (default: 3072)
"""

import argparse
import asyncio
import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
POLICIES_DIR = REPO_ROOT / "data" / "policies"
CATEGORY = "payer-policy"
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 200

# Policy metadata keyed by filename stem
POLICY_METADATA = {
    "001": {
        "title": "Coverage Policy 001 — Inflammatory Conditions",
        "tags": ["inflammatory", "autoimmune", "biologic-therapy"],
        "case_ids": ["001_a", "001_b"],
    },
    "002": {
        "title": "Coverage Policy 002 — Orthopedic Procedures",
        "tags": ["orthopedic", "joint-replacement", "surgical"],
        "case_ids": ["002_a", "002_b"],
    },
    "003": {
        "title": "Coverage Policy 003 — Cardiology Services",
        "tags": ["cardiology", "cardiac", "diagnostic"],
        "case_ids": ["003_a", "003_b"],
    },
    "004": {
        "title": "Coverage Policy 004 — Mental Health Services",
        "tags": ["mental-health", "behavioral", "psychiatric"],
        "case_ids": ["004_a", "004_b"],
    },
    "005": {
        "title": "Coverage Policy 005 — Oncology Treatment",
        "tags": ["oncology", "cancer", "chemotherapy"],
        "case_ids": ["005_a", "005_b"],
    },
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def normalize_endpoint(raw_endpoint: str, env_var_name: str, default_scheme: str = "https") -> str:
    """Validate and normalize an HTTP(S) endpoint from environment settings."""
    endpoint = (raw_endpoint or "").strip()
    if not endpoint:
        logger.error(f"{env_var_name} env var is required")
        sys.exit(1)

    if "://" not in endpoint:
        endpoint = f"{default_scheme}://{endpoint}"

    parsed = urlparse(endpoint)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        logger.error(
            "%s must be a valid URL with http:// or https:// (received: %r)",
            env_var_name,
            raw_endpoint,
        )
        sys.exit(1)

    return endpoint.rstrip("/")


# ---------------------------------------------------------------------------
# PDF Text Extraction
# ---------------------------------------------------------------------------


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract text from a PDF file using PyMuPDF (fitz)."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        logger.info("PyMuPDF not found. Installing automatically...")
        import shutil
        import subprocess

        if shutil.which("uv"):
            subprocess.check_call(["uv", "pip", "install", "PyMuPDF>=1.24.0", "--quiet"])
        else:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "PyMuPDF>=1.24.0", "-q"])
        import fitz  # retry after install

    doc = fitz.open(str(pdf_path))
    pages = []
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        text = page.get_text("text")
        if text.strip():
            pages.append(text.strip())
    doc.close()

    full_text = "\n\n".join(pages)
    logger.info(f"  Extracted {len(pages)} pages, {len(full_text)} chars from {pdf_path.name}")
    return full_text


# ---------------------------------------------------------------------------
# Text Chunking (mirrors cosmos-rag function_app.py logic)
# ---------------------------------------------------------------------------


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Split text into overlapping chunks at sentence boundaries."""
    if len(text) <= chunk_size:
        return [text]

    sentences = []
    current = ""
    for char in text:
        current += char
        if char in ".!?\n" and len(current.strip()) > 0:
            sentences.append(current.strip())
            current = ""
    if current.strip():
        sentences.append(current.strip())

    chunks = []
    current_chunk = ""

    for sentence in sentences:
        if len(current_chunk) + len(sentence) + 1 > chunk_size and current_chunk:
            chunks.append(current_chunk.strip())
            words = current_chunk.split()
            overlap_text = ""
            for word in reversed(words):
                if len(overlap_text) + len(word) + 1 > overlap:
                    break
                overlap_text = word + " " + overlap_text
            current_chunk = overlap_text.strip() + " " + sentence
        else:
            current_chunk = (current_chunk + " " + sentence).strip()

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks


# ---------------------------------------------------------------------------
# MCP Mode — Index via cosmos-rag MCP server
# ---------------------------------------------------------------------------


def seed_via_mcp(policies: list[dict], base_url: str) -> dict:
    """Index policies through the cosmos-rag MCP server's index_document tool."""
    try:
        import httpx
    except ImportError:
        logger.info("httpx not found. Installing automatically...")
        import shutil
        import subprocess

        if shutil.which("uv"):
            subprocess.check_call(["uv", "pip", "install", "httpx>=0.25.0", "--quiet"])
        else:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx>=0.25.0", "-q"])
        import httpx

    client = httpx.Client(base_url=base_url, timeout=120.0)
    headers = {"Content-Type": "application/json"}
    msg_id = 0
    results = {"indexed": 0, "failed": 0, "documents": []}

    # Initialize MCP session
    msg_id += 1
    resp = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": msg_id,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "clientInfo": {"name": "seed-script", "version": "1.0.0"},
            },
        },
        headers=headers,
    )
    resp.raise_for_status()
    logger.info("MCP session initialized")

    for policy in policies:
        msg_id += 1
        logger.info(f"Indexing via MCP: {policy['title']} ({len(policy['content'])} chars)")

        resp = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": msg_id,
                "method": "tools/call",
                "params": {
                    "name": "index_document",
                    "arguments": {
                        "title": policy["title"],
                        "content": policy["content"],
                        "category": CATEGORY,
                        "metadata": policy["metadata"],
                        "chunk_size": DEFAULT_CHUNK_SIZE,
                        "chunk_overlap": DEFAULT_CHUNK_OVERLAP,
                    },
                },
            },
            headers=headers,
        )

        if resp.status_code == 200:
            body = resp.json()
            result = body.get("result", {})
            content = result.get("content", [{}])
            if content and not result.get("isError"):
                tool_result = json.loads(content[0].get("text", "{}"))
                results["indexed"] += 1
                results["documents"].append(
                    {
                        "policy": policy["filename"],
                        "documentId": tool_result.get("documentId"),
                        "chunks": tool_result.get("totalChunks"),
                    }
                )
                logger.info(
                    f"  ✓ Indexed {tool_result.get('totalChunks', '?')} chunks, "
                    f"docId={tool_result.get('documentId', '?')}"
                )
            else:
                results["failed"] += 1
                logger.error(f"  ✗ Tool error: {content}")
        else:
            results["failed"] += 1
            logger.error(f"  ✗ HTTP {resp.status_code}: {resp.text[:200]}")

    client.close()
    return results


# ---------------------------------------------------------------------------
# Direct Mode — Write to Cosmos DB using SDK
# ---------------------------------------------------------------------------


async def seed_direct(policies: list[dict]) -> dict:
    """Index policies directly into Cosmos DB using the Python SDK + Azure OpenAI."""
    from azure.cosmos.aio import CosmosClient
    from azure.identity.aio import DefaultAzureCredential
    from openai import AsyncAzureOpenAI

    endpoint = os.environ.get("COSMOS_DB_ENDPOINT", "")
    database_name = os.environ.get("COSMOS_DB_DATABASE", "healthcare-mcp")
    ai_endpoint = os.environ.get("AZURE_AI_SERVICES_ENDPOINT", "") or os.environ.get("AZURE_OPENAI_ENDPOINT", "")
    embedding_deployment = os.environ.get("EMBEDDING_DEPLOYMENT_NAME", "text-embedding-3-large")
    embedding_dimensions = int(os.environ.get("EMBEDDING_DIMENSIONS", "3072"))

    endpoint = normalize_endpoint(endpoint, "COSMOS_DB_ENDPOINT")
    ai_endpoint = normalize_endpoint(
        ai_endpoint,
        "AZURE_AI_SERVICES_ENDPOINT (or AZURE_OPENAI_ENDPOINT fallback)",
    )

    credential = DefaultAzureCredential()
    cosmos = CosmosClient(endpoint, credential=credential)
    database = cosmos.get_database_client(database_name)
    container = database.get_container_client("documents")

    # Azure OpenAI client
    token = await credential.get_token("https://cognitiveservices.azure.com/.default")
    openai_client = AsyncAzureOpenAI(
        azure_endpoint=ai_endpoint,
        api_version="2024-10-21",
        azure_ad_token=token.token,
    )

    async def embed(text: str) -> list[float]:
        resp = await openai_client.embeddings.create(
            input=text, model=embedding_deployment, dimensions=embedding_dimensions
        )
        return resp.data[0].embedding

    results = {"indexed": 0, "failed": 0, "documents": []}

    for policy in policies:
        try:
            doc_id = str(uuid.uuid4())
            chunks = chunk_text(policy["content"], DEFAULT_CHUNK_SIZE, DEFAULT_CHUNK_OVERLAP)
            logger.info(f"Indexing direct: {policy['title']} → {len(chunks)} chunks")

            for i, chunk in enumerate(chunks):
                chunk_id = f"{doc_id}-chunk-{i}"
                embedding = await embed(chunk)

                item = {
                    "id": chunk_id,
                    "documentId": doc_id,
                    "category": CATEGORY,
                    "title": policy["title"],
                    "content": chunk,
                    "embedding": embedding,
                    "chunkIndex": i,
                    "totalChunks": len(chunks),
                    "metadata": policy["metadata"],
                    "indexedAt": datetime.now(timezone.utc).isoformat(),
                }
                await container.upsert_item(item)

            results["indexed"] += 1
            results["documents"].append({"policy": policy["filename"], "documentId": doc_id, "chunks": len(chunks)})
            logger.info(f"  ✓ Indexed {len(chunks)} chunks, docId={doc_id}")

        except Exception as e:
            results["failed"] += 1
            logger.error(f"  ✗ Failed to index {policy['filename']}: {e}")

    await cosmos.close()
    await credential.close()
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def load_policies() -> list[dict]:
    """Load and extract text from all policy PDFs."""
    if not POLICIES_DIR.exists():
        logger.error(f"Policies directory not found: {POLICIES_DIR}")
        sys.exit(1)

    pdf_files = sorted(POLICIES_DIR.glob("*.pdf"))
    if not pdf_files:
        logger.error(f"No PDF files found in {POLICIES_DIR}")
        sys.exit(1)

    logger.info(f"Found {len(pdf_files)} policy PDFs in {POLICIES_DIR}")
    policies = []

    for pdf_path in pdf_files:
        stem = pdf_path.stem  # e.g. "001"
        meta = POLICY_METADATA.get(stem, {})
        title = meta.get("title", f"Coverage Policy {stem}")

        logger.info(f"Processing {pdf_path.name}...")
        text = extract_text_from_pdf(pdf_path)

        if not text.strip():
            logger.warning(f"  Skipping {pdf_path.name} — no extractable text")
            continue

        policies.append(
            {
                "filename": pdf_path.name,
                "stem": stem,
                "title": title,
                "content": text,
                "metadata": {
                    "source_file": pdf_path.name,
                    "case_ids": meta.get("case_ids", []),
                    "tags": meta.get("tags", []),
                    "document_type": "coverage-policy",
                    "indexed_by": "seed_cosmos_policies.py",
                    "indexed_at": datetime.now(timezone.utc).isoformat(),
                },
            }
        )

    return policies


def main():
    parser = argparse.ArgumentParser(description="Seed Cosmos DB with healthcare coverage policy documents")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--mcp", action="store_true", default=True, help="Index via MCP server (default)")
    mode.add_argument("--direct", action="store_true", help="Write directly to Cosmos DB SDK")
    parser.add_argument("--dry-run", action="store_true", help="Extract text only, don't write")
    parser.add_argument("--port", type=int, default=7077, help="MCP server port (default: 7077)")
    parser.add_argument("--host", default="http://localhost", help="MCP server host")
    args = parser.parse_args()

    policies = load_policies()
    logger.info(f"Loaded {len(policies)} policies with extractable text")

    if args.dry_run:
        for p in policies:
            chunks = chunk_text(p["content"])
            print(f"\n{'=' * 60}")
            print(f"Policy: {p['title']}")
            print(f"File:   {p['filename']}")
            print(f"Chars:  {len(p['content'])}")
            print(f"Chunks: {len(chunks)}")
            print(f"Tags:   {p['metadata'].get('tags', [])}")
            print(f"First 300 chars:\n{p['content'][:300]}...")
        return

    if args.direct:
        results = asyncio.run(seed_direct(policies))
    else:
        host = args.host.rstrip("/")
        if "://" not in host:
            host = f"http://{host}"
        base_url = normalize_endpoint(host, "--host", default_scheme="http")

        parsed_host = urlparse(base_url)
        if parsed_host.port is None:
            base_url = f"{base_url}:{args.port}"

        results = seed_via_mcp(policies, base_url)

    print(f"\n{'=' * 60}")
    print(f"Seeding complete: {results['indexed']} indexed, {results['failed']} failed")
    for doc in results["documents"]:
        print(f"  {doc['policy']} → {doc['chunks']} chunks (docId: {doc['documentId']})")

    if results["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
