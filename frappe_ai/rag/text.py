import hashlib
import os

import frappe


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    chunks = []
    step = max(chunk_size - overlap, 1)
    for start in range(0, len(text), step):
        chunk = text[start : start + chunk_size]
        if chunk.strip():
            chunks.append(chunk)
    return chunks


def extract_text_from_file(file_url: str) -> str:
    file_doc = frappe.get_doc("File", {"file_url": file_url})
    file_path = file_doc.get_full_path()
    ext = (file_url.rsplit(".", 1)[-1] or "").lower()

    if ext == "pdf":
        import fitz
        doc = fitz.open(file_path)
        return "\n\n".join(page.get_text() for page in doc)

    with open(file_path, "r", errors="replace") as f:
        return f.read()


def file_hash(file_url: str) -> str:
    file_doc = frappe.get_doc("File", {"file_url": file_url})
    content = file_doc.get_content()
    if isinstance(content, str):
        content = content.encode()
    return hashlib.sha256(content).hexdigest()


def text_from_doctype_record(record, fields: list[str]) -> str:
    parts = []
    for field in fields:
        val = record.get(field)
        if val and isinstance(val, str) and val.strip():
            parts.append(f"{field}: {val.strip()}")
    return "\n".join(parts)
