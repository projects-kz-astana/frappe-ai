import json
import os

import numpy as np
from frappe.utils import get_site_path


def rag_dir() -> str:
    path = get_site_path("private", "files", "rag")
    os.makedirs(path, exist_ok=True)
    return path


def index_paths(index_name: str) -> tuple[str, str, str]:
    base = rag_dir()
    return (
        os.path.join(base, f"{index_name}.index"),
        os.path.join(base, f"{index_name}.meta"),
        os.path.join(base, f"{index_name}.npy"),
    )


def load_index(index_name: str) -> tuple:
    import faiss

    index_path, meta_path, vecs_path = index_paths(index_name)

    index = faiss.read_index(index_path) if os.path.exists(index_path) else None

    metadata: list[dict] = []
    if os.path.exists(meta_path):
        with open(meta_path) as f:
            metadata = json.load(f)

    vectors = np.load(vecs_path) if os.path.exists(vecs_path) else np.empty((0, 0), np.float32)

    return index, metadata, vectors


def save_index(index_name: str, index, metadata: list[dict], vectors: np.ndarray) -> None:
    import faiss

    index_path, meta_path, vecs_path = index_paths(index_name)
    faiss.write_index(index, index_path)
    with open(meta_path, "w") as f:
        json.dump(metadata, f)
    np.save(vecs_path, vectors)
