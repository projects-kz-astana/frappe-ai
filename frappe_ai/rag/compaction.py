import frappe
import numpy as np

from frappe_ai.rag.store import load_index, save_index


def compact_all_rag_indexes() -> None:
    index_names = frappe.get_all(
        "RAG Data Source",
        filters={"enabled": 1},
        pluck="index_name",
    )
    for index_name in set(index_names):
        try:
            compact(index_name)
        except Exception:
            frappe.log_error(
                title=f"RAG: compaction failed for index '{index_name}'",
                message=frappe.get_traceback(),
            )


def compact(index_name: str) -> None:
    import faiss

    index, metadata, vectors = load_index(index_name)
    if not metadata or vectors.shape[0] == 0:
        return

    active_mask = np.array([m.get("active", True) for m in metadata], dtype=bool)
    if active_mask.all():
        return

    active_meta = [m for m, keep in zip(metadata, active_mask) if keep]
    active_vecs = vectors[active_mask]

    if active_vecs.shape[0] == 0:
        return

    new_index = faiss.IndexFlatL2(active_vecs.shape[1])
    new_index.add(active_vecs.astype(np.float32))
    save_index(index_name, new_index, active_meta, active_vecs)
