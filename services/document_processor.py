import json
import re
from pathlib import Path
import pypdf


def clean_text(text: str) -> str:
    """
    Collapse excess whitespace and newlines, and remove non-printable control characters.

    Args:
        text (str): Raw text extracted from document.

    Returns:
        str: Cleaned and normalized text.
    """
    if not text:
        return ""
    # Remove control/unprintable characters (excluding standard whitespace)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', text)
    # Collapse multiple whitespaces and newlines into a single space
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def chunk_documents(documents: list[dict], chunk_size: int = 500, overlap: int = 50) -> list[dict]:
    """
    Split document texts into overlapping character chunks and attach parent metadata.

    Args:
        documents (list[dict]): List of document dicts with 'text' and 'metadata'.
        chunk_size (int): Character size of each chunk. Defaults to 500.
        overlap (int): Overlap size in characters. Defaults to 50.

    Returns:
        list[dict]: Flat list of chunk dicts in format:
                    [{"chunk_id": "doc_01_c000", "text": "...", "metadata": {...}}, ...]
    """
    chunks = []
    stride = max(1, chunk_size - overlap)

    for doc in documents:
        raw_text = doc.get("text", "")
        cleaned = clean_text(raw_text)
        meta = doc.get("metadata", {})
        doc_id = meta.get("document_id", "doc")

        if not cleaned:
            continue

        text_len = len(cleaned)
        chunk_index = 0
        for start_idx in range(0, text_len, stride):
            end_idx = min(start_idx + chunk_size, text_len)
            chunk_str = cleaned[start_idx:end_idx].strip()
            
            if chunk_str:
                chunk_id = f"{doc_id}_c{chunk_index:03d}"
                chunk_meta = dict(meta)
                chunk_meta["chunk_id"] = chunk_id
                
                chunks.append({
                    "chunk_id": chunk_id,
                    "text": chunk_str,
                    "metadata": chunk_meta
                })
                chunk_index += 1

            if end_idx >= text_len:
                break

    return chunks


def load_documents() -> list[dict]:
    """
    Load PDF documents from the 'document' directory, extract raw text using pypdf,
    and attach matching metadata from data/metadata.json by filename.

    Returns:
        list[dict]: A list of dictionaries in the format:
                    [{"text": "extracted text...", "metadata": {...}}, ...]
    """
    project_root = Path(__file__).parent.parent
    
    # Path to metadata.json
    metadata_path = project_root / "data" / "metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"Metadata file not found at: {metadata_path}")

    with open(metadata_path, "r", encoding="utf-8") as f:
        metadata_list = json.load(f)

    # Map filename -> metadata dict
    metadata_by_name = {meta["document_name"]: meta for meta in metadata_list}

    # Locate document directory (check 'document' or 'Documents' for cross-platform support)
    doc_dir = project_root / "document"
    if not doc_dir.exists():
        doc_dir = project_root / "Documents"

    if not doc_dir.exists():
        raise FileNotFoundError(f"Document directory not found at: {doc_dir}")

    pdf_files = list(doc_dir.glob("*.pdf"))
    if not pdf_files:
        raise FileNotFoundError(f"No PDF files found in directory: {doc_dir}")

    documents = []
    for pdf_path in sorted(pdf_files):
        filename = pdf_path.name

        try:
            reader = pypdf.PdfReader(pdf_path)
            extracted_pages = []
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    extracted_pages.append(page_text)
            
            raw_text = "\n".join(extracted_pages).strip()
        except Exception as e:
            raw_text = ""

        # Retrieve matching metadata or fallback
        metadata = metadata_by_name.get(
            filename,
            {
                "document_id": f"doc_{filename.split('_')[0]}",
                "document_name": filename,
                "document_type": "unknown",
                "role": "Unknown",
                "category": "AI/ML",
                "source_type": "synthetic",
                "data_status": "generalized"
            }
        )

        documents.append({
            "text": raw_text,
            "metadata": metadata
        })

    return documents
