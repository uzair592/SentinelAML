"""Document ingestion and lexical RAG for approved AML policy materials."""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.orm import Session

from .persistence import PolicyChunk, PolicyDocument

ALLOWED_POLICY_SUFFIXES = {".pdf", ".txt", ".md", ".markdown"}
DEFAULT_POLICY_MB = 10
MAX_POLICY_CHARS = 250_000
MAX_CHUNKS = 500


def _max_bytes() -> int:
    try:
        return max(1, int(os.getenv("SENTINELAML_POLICY_MAX_UPLOAD_MB", str(DEFAULT_POLICY_MB)))) * 1024 * 1024
    except ValueError:
        return DEFAULT_POLICY_MB * 1024 * 1024


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_-]{1,}", text.lower()) if len(token) > 2}


def _chunk_text(text: str, size: int = 1200, overlap: int = 160) -> list[str]:
    normalized = re.sub(r"\r\n?", "\n", text)
    normalized = re.sub(r"[\t ]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()
    chunks = []
    start = 0
    while start < len(normalized) and len(chunks) < MAX_CHUNKS:
        end = min(len(normalized), start + size)
        if end < len(normalized):
            break_at = normalized.rfind("\n", start + size // 2, end)
            if break_at > start:
                end = break_at
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(normalized):
            break
        start = max(start + 1, end - overlap)
    return chunks


async def ingest_policy_upload(file: UploadFile, db: Session, created_by: str, title: str | None = None) -> dict[str, Any]:
    safe_name = Path(file.filename or "policy-document").name[:240]
    suffix = Path(safe_name).suffix.lower()
    if suffix not in ALLOWED_POLICY_SUFFIXES:
        raise HTTPException(status_code=415, detail="Unsupported policy format. Upload PDF, TXT, or Markdown.")
    raw = await file.read(_max_bytes() + 1)
    if not raw:
        raise HTTPException(status_code=400, detail="The policy document is empty.")
    if len(raw) > _max_bytes():
        raise HTTPException(status_code=413, detail="Policy document exceeds the configured size limit.")
    digest = hashlib.sha256(raw).hexdigest()
    existing = db.scalar(select(PolicyDocument).where(PolicyDocument.sha256 == digest))
    if existing:
        return {"id": existing.id, "title": existing.title, "file_name": existing.file_name, "chunk_count": existing.chunk_count, "duplicate": True}

    page_texts: list[tuple[int | None, str]] = []
    try:
        if suffix == ".pdf":
            import io
            reader = PdfReader(io.BytesIO(raw), strict=False)
            if reader.is_encrypted:
                raise HTTPException(status_code=422, detail="Encrypted PDFs are not supported. Provide an approved, readable copy.")
            if len(reader.pages) > 1000:
                raise HTTPException(status_code=413, detail="Policy PDF contains too many pages.")
            for page_number, page in enumerate(reader.pages, start=1):
                extracted = page.extract_text() or ""
                if extracted.strip():
                    page_texts.append((page_number, extracted))
        else:
            decoded = raw.decode("utf-8-sig", errors="replace")
            page_texts.append((None, decoded))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Could not extract text from this policy document.") from exc

    all_text = "\n\n".join(text for _, text in page_texts)
    if not all_text.strip():
        raise HTTPException(status_code=422, detail="No extractable text was found. Scanned PDFs need an approved OCR process before ingestion.")
    if len(all_text) > MAX_POLICY_CHARS:
        all_text = all_text[:MAX_POLICY_CHARS]
        truncated = True
    else:
        truncated = False

    chunks: list[tuple[int | None, str]] = []
    for page, text in page_texts:
        for chunk in _chunk_text(text):
            chunks.append((page, chunk))
            if len(chunks) >= MAX_CHUNKS:
                break
        if len(chunks) >= MAX_CHUNKS:
            break
    if not chunks:
        raise HTTPException(status_code=422, detail="No searchable text chunks could be created.")
    doc = PolicyDocument(
        id=str(uuid4()),
        created_by=created_by,
        title=(title or Path(safe_name).stem)[:300],
        file_name=safe_name,
        sha256=digest,
        page_count=sum(1 for page, _ in page_texts if page is not None),
        chunk_count=len(chunks),
    )
    db.add(doc)
    db.flush()
    for idx, (page, content) in enumerate(chunks):
        db.add(PolicyChunk(
            id=str(uuid4()),
            document_id=doc.id,
            chunk_index=idx,
            content=content,
            page_number=page,
            metadata_json={"source_file": safe_name, "page_number": page},
        ))
    db.commit()
    return {
        "id": doc.id, "title": doc.title, "file_name": doc.file_name,
        "chunk_count": doc.chunk_count, "page_count": doc.page_count,
        "sha256": doc.sha256, "truncated": truncated, "duplicate": False,
    }


def list_policies(db: Session) -> list[dict[str, Any]]:
    docs = db.scalars(select(PolicyDocument).order_by(PolicyDocument.created_at.desc()).limit(500)).all()
    return [{
        "id": doc.id,
        "title": doc.title,
        "file_name": doc.file_name,
        "source_url": doc.source_url,
        "sha256": doc.sha256,
        "page_count": doc.page_count,
        "chunk_count": doc.chunk_count,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    } for doc in docs]


def search_policies(db: Session, query: str, limit: int = 5) -> list[dict[str, Any]]:
    query_tokens = _tokens(query)
    if not query_tokens:
        return []
    chunks = db.scalars(select(PolicyChunk).limit(10_000)).all()
    docs = {doc.id: doc for doc in db.scalars(select(PolicyDocument).limit(2_000)).all()}
    ranked: list[tuple[float, PolicyChunk]] = []
    for chunk in chunks:
        content_tokens = _tokens(chunk.content)
        overlap = len(query_tokens & content_tokens)
        if not overlap:
            continue
        # A simple, transparent lexical ranking baseline; not semantic embeddings.
        score = overlap / max(1.0, len(query_tokens) ** 0.5)
        ranked.append((score, chunk))
    ranked.sort(key=lambda item: (item[0], len(item[1].content)), reverse=True)
    results = []
    for score, chunk in ranked[:max(1, min(limit, 10))]:
        doc = docs.get(chunk.document_id)
        if not doc:
            continue
        results.append({
            "chunk_id": chunk.id,
            "document_id": doc.id,
            "title": doc.title,
            "source_file": doc.file_name,
            "source_url": doc.source_url,
            "page_number": chunk.page_number,
            "chunk_index": chunk.chunk_index,
            "score": round(score, 4),
            "citation": f"{doc.title} — " + (f"page {chunk.page_number}" if chunk.page_number else f"section {chunk.chunk_index + 1}"),
            "content": chunk.content[:4000],
        })
    return results
