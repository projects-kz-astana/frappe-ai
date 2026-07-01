import json
import os

import frappe
import numpy as np
from frappe.utils import now_datetime

from frappe_ai.rag.embeddings import embed_text
from frappe_ai.rag.settings import get_settings
from frappe_ai.rag.store import load_index, save_index
from frappe_ai.rag.text import chunk_text, extract_text_from_file, file_hash, text_from_doctype_record


def set_job(name: str, values: dict) -> None:
    frappe.db.set_value("RAG Index Job", name, values)
    frappe.db.commit()


def set_rag_doc(name: str, values: dict) -> None:
    frappe.db.set_value("RAG Document", name, values)
    frappe.db.commit()


def index_file_source(
    data_source,
    job_name: str,
    settings,
    index,
    metadata: list[dict],
    vectors: np.ndarray,
) -> tuple:
    import faiss

    chunk_size = int(settings.chunk_size or 1000)
    overlap = int(settings.chunk_overlap or 200)
    ds_name = data_source.name

    docs = frappe.get_all(
        "RAG Document",
        filters={"data_source": ds_name, "status": ["in", ["Pending", "Failed"]]},
        pluck="name",
    )
    set_job(job_name, {"total_documents": len(docs)})

    log_lines: list[str] = []
    processed = 0

    for doc_name in docs:
        rag_doc = frappe.get_doc("RAG Document", doc_name)
        try:
            set_rag_doc(doc_name, {"status": "Indexing"})

            if not rag_doc.file:
                raise ValueError("No file attached.")

            new_hash = file_hash(rag_doc.file)
            if rag_doc.content_hash == new_hash:
                set_rag_doc(doc_name, {"status": "Indexed"})
                processed += 1
                log_lines.append(f"[SKIP] {doc_name} (unchanged)")
                continue

            for entry in metadata:
                if entry.get("rag_document") == doc_name:
                    entry["active"] = False

            text = extract_text_from_file(rag_doc.file)
            chunks = chunk_text(text, chunk_size, overlap)

            new_vectors: list[np.ndarray] = []
            new_meta: list[dict] = []
            for i, chunk in enumerate(chunks):
                vec = embed_text(chunk, settings)
                new_vectors.append(vec)
                new_meta.append({
                    "rag_document": doc_name,
                    "data_source": ds_name,
                    "source": os.path.basename(rag_doc.file),
                    "chunk_index": i,
                    "content": chunk,
                    "active": True,
                })

            if new_vectors:
                matrix = np.vstack(new_vectors).astype(np.float32)
                dim = matrix.shape[1]

                if index is None:
                    index = faiss.IndexFlatL2(dim)
                index.add(matrix)
                metadata.extend(new_meta)
                vectors = matrix if vectors.shape[0] == 0 else np.vstack([vectors, matrix])

            set_rag_doc(doc_name, {
                "status": "Indexed",
                "content_hash": new_hash,
                "version": (rag_doc.version or 1) + 1,
                "last_indexed_on": now_datetime(),
                "error_log": None,
            })
            processed += 1
            log_lines.append(f"[OK] {doc_name} ({len(chunks)} chunks)")
            set_job(job_name, {"processed_documents": processed})

        except Exception:
            tb = frappe.get_traceback()
            set_rag_doc(doc_name, {"status": "Failed", "error_log": tb})
            log_lines.append(f"[FAIL] {doc_name}: {tb[:300]}")
            frappe.log_error(title=f"RAG: failed to index {doc_name}", message=tb)

    return index, metadata, vectors, "\n".join(log_lines)


def index_doctype_source(
    data_source,
    job_name: str,
    settings,
    index,
    metadata: list[dict],
    vectors: np.ndarray,
) -> tuple:
    import faiss

    chunk_size = int(settings.chunk_size or 1000)
    overlap = int(settings.chunk_overlap or 200)
    ds_name = data_source.name
    target_doctype = data_source.target_doctype

    if not target_doctype:
        frappe.throw(f"RAG Data Source '{ds_name}' has no Target DocType configured.")

    filters: dict = {}
    raw_filters = (data_source.doctype_filters or "").strip()
    if raw_filters:
        try:
            filters = json.loads(raw_filters)
        except json.JSONDecodeError:
            frappe.log_error(
                title=f"RAG: invalid doctype_filters on {ds_name}",
                message=raw_filters,
            )

    raw_fields = (data_source.doctype_fields or "").strip()
    if raw_fields:
        text_fields = [f.strip() for f in raw_fields.split(",") if f.strip()]
    else:
        meta = frappe.get_meta(target_doctype)
        text_fields = [
            f.fieldname
            for f in meta.fields
            if f.fieldtype in ("Data", "Small Text", "Text", "Long Text", "Text Editor")
        ]

    records = frappe.get_all(
        target_doctype,
        filters=filters,
        fields=["name"] + text_fields,
    )
    set_job(job_name, {"total_documents": len(records)})

    for entry in metadata:
        if entry.get("data_source") == ds_name and entry.get("source_type") == "DocType":
            entry["active"] = False

    log_lines: list[str] = []
    processed = 0

    for record in records:
        try:
            text = text_from_doctype_record(record, text_fields)
            if not text.strip():
                continue

            chunks = chunk_text(text, chunk_size, overlap)
            new_vectors: list[np.ndarray] = []
            new_meta: list[dict] = []

            for i, chunk in enumerate(chunks):
                vec = embed_text(chunk, settings)
                new_vectors.append(vec)
                new_meta.append({
                    "source_type": "DocType",
                    "data_source": ds_name,
                    "doctype": target_doctype,
                    "record_name": record.name,
                    "source": f"{target_doctype}/{record.name}",
                    "chunk_index": i,
                    "content": chunk,
                    "active": True,
                })

            if new_vectors:
                matrix = np.vstack(new_vectors).astype(np.float32)
                dim = matrix.shape[1]

                if index is None:
                    index = faiss.IndexFlatL2(dim)
                index.add(matrix)
                metadata.extend(new_meta)
                vectors = matrix if vectors.shape[0] == 0 else np.vstack([vectors, matrix])

            processed += 1
            log_lines.append(f"[OK] {target_doctype}/{record.name} ({len(chunks)} chunks)")
            set_job(job_name, {"processed_documents": processed})

        except Exception:
            tb = frappe.get_traceback()
            log_lines.append(f"[FAIL] {target_doctype}/{record.name}: {tb[:300]}")
            frappe.log_error(
                title=f"RAG: failed to index {target_doctype}/{record.name}",
                message=tb,
            )

    return index, metadata, vectors, "\n".join(log_lines)


def run_index_job(rag_job_name: str) -> None:
    job_name = rag_job_name
    job = frappe.get_doc("RAG Index Job", job_name)
    try:
        set_job(job_name, {"status": "Running", "started_on": now_datetime()})

        settings = get_settings()
        data_source = frappe.get_doc("RAG Data Source", job.data_source)
        index_name = data_source.index_name or "default"

        index, metadata, vectors = load_index(index_name)
        source_type = data_source.source_type or "PDF"

        if source_type == "DocType":
            index, metadata, vectors, log = index_doctype_source(
                data_source, job_name, settings, index, metadata, vectors
            )
        else:
            index, metadata, vectors, log = index_file_source(
                data_source, job_name, settings, index, metadata, vectors
            )

        if index is not None:
            save_index(index_name, index, metadata, vectors)

        set_job(job_name, {
            "status": "Completed",
            "finished_on": now_datetime(),
            "logs": log,
        })

    except Exception:
        tb = frappe.get_traceback()
        set_job(job_name, {
            "status": "Failed",
            "finished_on": now_datetime(),
            "logs": tb,
        })
        frappe.log_error(title=f"RAG Index Job failed: {job_name}", message=tb)
        raise


@frappe.whitelist()
def enqueue_indexing(data_source_name: str) -> str:
    job = frappe.get_doc({
        "doctype": "RAG Index Job",
        "data_source": data_source_name,
        "status": "Queued",
    })
    job.insert(ignore_permissions=True)
    frappe.db.commit()

    frappe.enqueue(
        "frappe_ai.rag.indexing.run_index_job",
        rag_job_name=job.name,
        queue="long",
        timeout=7200,
    )
    return job.name
