"""
Lightweight document loader helpers.

Goal: make it easy for agents to consume local documents (text/structured and binary)
without each agent re-implementing ad-hoc file reading logic.

This module is intentionally dependency-free. For PDFs/images, it returns base64 by
default. Optional extraction (PDF text, OCR) can be layered in later.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import json
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ReadOptions:
    # How to interpret a file when possible.
    # - auto: text for "text-like" extensions, otherwise binary base64
    # - text: force text decode (with replacement)
    # - binary: force base64
    mode: str = "auto"

    # Safety: default to workspace-only to avoid accidental reads of secrets.
    allow_outside_workspace: bool = False

    # Limits to avoid blowing up MCP responses.
    max_bytes: int = 4_000_000
    max_chars: int = 200_000
    max_rows: int = 500

    # Structured parsing for common formats.
    parse_structured: bool = True
    csv_delimiter: str = ","

    # Convenience for UI/LLM "image_url" usage.
    include_data_url: bool = False


TEXT_EXTS = {
    ".txt",
    ".md",
    ".markdown",
    ".log",
    ".yaml",
    ".yml",
    ".xml",
    ".html",
    ".htm",
    ".sql",
}

STRUCTURED_EXTS = {".json", ".csv", ".tsv", ".ndjson"}

BINARY_EXTS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".tif",
    ".tiff",
    ".webp",
    ".heic",
}


def _is_within(root: Path, path: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def resolve_path(path: str, *, workspace_root: Path) -> Path:
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = (workspace_root / p).resolve()
    else:
        p = p.resolve()
    return p


def _guess_mime(path: Path) -> str:
    mime, _enc = mimetypes.guess_type(str(path))
    if mime:
        return mime

    # A few high-value fallbacks when the platform's mime DB is sparse.
    ext = path.suffix.lower()
    if ext == ".pdf":
        return "application/pdf"
    if ext in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if ext == ".png":
        return "image/png"
    if ext == ".tif" or ext == ".tiff":
        return "image/tiff"
    return "application/octet-stream"


def read_document(path: str, *, workspace_root: Path, options: ReadOptions | None = None) -> dict[str, Any]:
    """
    Read a document from disk.

    Returns a JSON-serializable dict suitable for returning from an MCP tool.
    """
    opts = options or ReadOptions()
    p = resolve_path(path, workspace_root=workspace_root)

    if not p.exists():
        return {"ok": False, "error": "not_found", "path": str(p)}
    if not p.is_file():
        return {"ok": False, "error": "not_a_file", "path": str(p)}

    if not opts.allow_outside_workspace and not _is_within(workspace_root, p):
        return {
            "ok": False,
            "error": "outside_workspace",
            "path": str(p),
            "workspace_root": str(workspace_root),
        }

    ext = p.suffix.lower()
    mime = _guess_mime(p)
    size_bytes = p.stat().st_size

    # Decide mode in auto.
    mode = (opts.mode or "auto").lower()
    if mode == "auto":
        if ext in TEXT_EXTS or ext in STRUCTURED_EXTS:
            mode = "text"
        elif ext in BINARY_EXTS:
            mode = "binary"
        else:
            # default unknowns to text if mime suggests it
            mode = "text" if (mime.startswith("text/") or mime in {"application/json"}) else "binary"

    if mode == "binary":
        if size_bytes > opts.max_bytes:
            return {
                "ok": False,
                "error": "too_large",
                "path": str(p),
                "size_bytes": size_bytes,
                "max_bytes": opts.max_bytes,
            }

        data = p.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        b64 = base64.b64encode(data).decode("ascii")
        result: dict[str, Any] = {
            "ok": True,
            "path": str(p),
            "kind": "binary",
            "mime": mime,
            "size_bytes": size_bytes,
            "sha256": digest,
            "base64": b64,
        }
        if opts.include_data_url:
            result["data_url"] = f"data:{mime};base64,{b64}"
        return result

    # mode == "text"
    truncated_bytes = False
    if size_bytes > opts.max_bytes:
        truncated_bytes = True
        with p.open("rb") as f:
            data = f.read(opts.max_bytes)
    else:
        data = p.read_bytes()

    text = data.decode("utf-8", errors="replace")
    truncated_chars = False
    if len(text) > opts.max_chars:
        truncated_chars = True
        text = text[: opts.max_chars]

    result = {
        "ok": True,
        "path": str(p),
        "kind": "text",
        "mime": mime,
        "size_bytes": size_bytes,
        "truncated_bytes": truncated_bytes,
        "truncated_chars": truncated_chars,
        "text": text,
    }

    if not opts.parse_structured:
        return result

    if ext == ".json":
        try:
            result["kind"] = "json"
            result["json"] = json.loads(text)
        except Exception:
            # Leave as plain text on parse failure.
            result["kind"] = "text"
    elif ext == ".ndjson":
        items: list[Any] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except Exception:
                # If any line fails, don't partially parse; return raw text.
                items = []
                break
        if items:
            result["kind"] = "ndjson"
            result["items"] = items
    elif ext in {".csv", ".tsv"}:
        delim = "\t" if ext == ".tsv" else (opts.csv_delimiter or ",")
        reader = csv.reader(text.splitlines(), delimiter=delim)
        rows: list[list[str]] = []
        for i, row in enumerate(reader):
            if i >= opts.max_rows:
                break
            rows.append(row)
        result["kind"] = "csv"
        result["delimiter"] = delim
        result["rows"] = rows
        result["truncated_rows"] = len(rows) >= opts.max_rows

    return result

