import time

import frappe

from frappe_ai.rag.embeddings import embed_text
from frappe_ai.rag.settings import get_settings
from frappe_ai.rag.store import load_index


@frappe.whitelist()
def query(question: str, data_source_name: str, session_id: str | None = None) -> dict:
    t_start = time.monotonic()

    settings = get_settings()
    data_source = frappe.get_doc("RAG Data Source", data_source_name)
    index_name = data_source.index_name or "default"
    top_k = int(settings.top_k or 7)

    index, metadata, _vectors = load_index(index_name)
    if index is None or not metadata:
        return {"error": "Index not built yet. Run indexing first."}

    q_vec = embed_text(question, settings).reshape(1, -1)

    if settings.get("hybrid_search_enabled"):
        from frappe_ai.rag.hybrid import hybrid_search
        active_hits = hybrid_search(question, q_vec, index, metadata, top_k)
    else:
        k_fetch = min(top_k * 3, index.ntotal)
        _distances, indices = index.search(q_vec, k=k_fetch)
        active_hits = [
            i for i in indices[0]
            if 0 <= i < len(metadata) and metadata[i].get("active", True)
        ][:top_k]

    context_blocks: list[str] = []
    for i in active_hits:
        entry = metadata[i]
        source = entry.get("source", "Unknown")
        content = entry.get("content", "")
        context_blocks.append(f"--- Source: {source} ---\n{content}")

    context = "\n\n".join(context_blocks)
    base_prompt = (settings.get("system_prompt") or "").strip() or (
        "You are a helpful assistant. Answer the question using only the provided context."
    )
    full_prompt = (
        f"{base_prompt}\n\n"
        f"[CONTEXT]\n{context}\n[/CONTEXT]\n\n"
        f"Question: {question}"
    )

    from frappe_ai.api.chat import ask
    answer = ask(docname=settings.llm_client, user_message=full_prompt)

    latency_ms = round((time.monotonic() - t_start) * 1000, 2)

    log = frappe.get_doc({
        "doctype": "RAG Query Log",
        "data_source": data_source_name,
        "user": frappe.session.user,
        "session_id": session_id or "",
        "question": question,
        "response": answer,
        "latency_ms": latency_ms,
    })
    log.insert(ignore_permissions=True)
    frappe.db.commit()

    return {"answer": answer}
