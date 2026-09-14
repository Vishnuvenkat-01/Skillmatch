import json
from pathlib import Path
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from services.document_processor import load_documents, chunk_documents

# Module-level cache for the embedder model
_EMBEDDER = None


def get_embedder(model_name: str = "all-MiniLM-L6-v2") -> SentenceTransformer:
    """
    Lazily load and cache the SentenceTransformer model instance.

    Args:
        model_name (str): HuggingFace model name. Defaults to "all-MiniLM-L6-v2".

    Returns:
        SentenceTransformer: Cached model instance.
    """
    global _EMBEDDER
    if _EMBEDDER is None:
        _EMBEDDER = SentenceTransformer(model_name)
    return _EMBEDDER


def embed_chunks(chunks: list[dict], model_name: str = "all-MiniLM-L6-v2") -> tuple[np.ndarray, list[dict]]:
    """
    Generate normalized embeddings for a list of document chunks.

    Args:
        chunks (list[dict]): Flat list of chunk dicts containing 'text' and 'metadata'.
        model_name (str): HuggingFace model name. Defaults to "all-MiniLM-L6-v2".

    Returns:
        tuple[np.ndarray, list[dict]]: A tuple containing:
            - np.ndarray: Float32 array of shape (N, embedding_dim) with normalized vectors.
            - list[dict]: Original chunks list mapped to vector indices.
    """
    if not chunks:
        return np.empty((0, 384), dtype=np.float32), []

    texts = [c["text"] for c in chunks]
    embedder = get_embedder(model_name)

    # Encode with L2 normalization enabled for Cosine Similarity via Inner Product
    raw_embeddings = embedder.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=False
    )

    embeddings = np.array(raw_embeddings, dtype=np.float32)
    return embeddings, chunks


def build_faiss_index(vectors: np.ndarray) -> faiss.IndexFlatIP:
    """
    Create a FAISS IndexFlatIP (inner product for cosine similarity with L2 normalized vectors)
    and add vectors to it.

    Args:
        vectors (np.ndarray): 2D Float32 array of normalized vectors.

    Returns:
        faiss.IndexFlatIP: Initialized and populated FAISS index.
    """
    if vectors.ndim != 2:
        raise ValueError(f"Expected 2D array of vectors, got shape {vectors.shape}")

    dimension = vectors.shape[1]
    index = faiss.IndexFlatIP(dimension)
    index.add(vectors)
    return index


def build_knowledge_base(force_rebuild: bool = False) -> tuple[faiss.IndexFlatIP, list[dict]]:
    """
    Tie together loading, chunking, embedding, indexing, and persistence for the knowledge base.
    Saves/loads index and chunks from vectorstore/ directory.

    Args:
        force_rebuild (bool): Force re-processing and re-indexing even if saved files exist.

    Returns:
        tuple[faiss.IndexFlatIP, list[dict]]: A tuple containing (index, chunks).

    Raises:
        RuntimeError: If the knowledge base cannot be built or loaded.
    """
    project_root = Path(__file__).parent.parent
    vectorstore_dir = project_root / "vectorstore"
    index_path = vectorstore_dir / "faiss.index"
    chunks_path = vectorstore_dir / "chunks.json"

    # Load cached index and chunks if both exist
    if not force_rebuild and index_path.exists() and chunks_path.exists():
        try:
            index = faiss.read_index(str(index_path))
            with open(chunks_path, "r", encoding="utf-8") as f:
                chunks = json.load(f)
            if index.ntotal > 0 and chunks:
                return index, chunks
            print("[vector_store] Cached index is empty; rebuilding from source documents.")
        except Exception as cache_err:
            # Log the technical detail but fall through to a full rebuild
            print(f"[vector_store] WARNING: Could not load cached index ({cache_err}); rebuilding.")

    # Rebuild from source documents
    try:
        documents = load_documents()
        chunks = chunk_documents(documents)
        if not chunks:
            raise RuntimeError(
                "No chunks were produced from the knowledge base documents. "
                "Check that the 'document/' directory contains readable PDF files."
            )
        vectors, chunks = embed_chunks(chunks)
        index = build_faiss_index(vectors)
    except RuntimeError:
        raise
    except Exception as build_err:
        raise RuntimeError(
            f"Failed to build the knowledge base index: {build_err}"
        ) from build_err

    if index.ntotal == 0:
        raise RuntimeError(
            "The FAISS index was built but contains no vectors. "
            "Ensure the knowledge base PDFs contain extractable text."
        )

    # Persist index and chunks to disk
    try:
        vectorstore_dir.mkdir(parents=True, exist_ok=True)
        faiss.write_index(index, str(index_path))
        with open(chunks_path, "w", encoding="utf-8") as f:
            json.dump(chunks, f, indent=2)
    except Exception as save_err:
        # Non-fatal: the index is in memory; just log the failure
        print(f"[vector_store] WARNING: Could not persist index to disk ({save_err}).")

    return index, chunks


def load_index(force_rebuild: bool = False) -> tuple[faiss.IndexFlatIP, list[dict]]:
    """
    Public alias for build_knowledge_base used by the Streamlit app.
    Wraps the underlying call with a user-facing RuntimeError on failure.

    Returns:
        tuple[faiss.IndexFlatIP, list[dict]]: Loaded (index, chunks).

    Raises:
        RuntimeError: Propagated from build_knowledge_base on any failure.
    """
    return build_knowledge_base(force_rebuild=force_rebuild)


def search(
    query_text: str,
    index: faiss.IndexFlatIP,
    chunks: list[dict],
    top_k: int = 5,
    role_filter: str = None
) -> list[dict]:
    """
    Embed query_text, search the FAISS index, and return top_k matching chunks
    with similarity scores and metadata. Optionally filters by role.

    Args:
        query_text (str): Input query text.
        index (faiss.IndexFlatIP): FAISS index instance.
        chunks (list[dict]): List of chunk dictionaries aligned with FAISS vector IDs.
        top_k (int): Number of top matches to return. Defaults to 5.
        role_filter (str, optional): Role name filter (case-insensitive).

    Returns:
        list[dict]: List of top matching chunk dicts, each augmented with a 'score' key.
    """
    if not query_text or not query_text.strip():
        return []

    if index.ntotal == 0 or not chunks:
        return []

    embedder = get_embedder()
    query_vector = embedder.encode(
        [query_text],
        normalize_embeddings=True,
        show_progress_bar=False
    )
    query_vector = np.array(query_vector, dtype=np.float32)

    # Retrieve more candidates if filtering by role to guarantee top_k results
    search_k = min(index.ntotal, max(top_k * 10, 100)) if role_filter else min(top_k, index.ntotal)
    distances, indices = index.search(query_vector, search_k)

    results = []
    norm_filter = role_filter.strip().lower() if role_filter else None

    for score, idx in zip(distances[0], indices[0]):
        if idx < 0 or idx >= len(chunks):
            continue

        chunk = chunks[idx]
        if norm_filter:
            chunk_role = chunk.get("metadata", {}).get("role", "").strip().lower()
            if norm_filter not in chunk_role and chunk_role not in norm_filter:
                continue

        result_item = dict(chunk)
        result_item["score"] = float(score)
        results.append(result_item)

        if len(results) >= top_k:
            break

    return results
