import sys
from services.vector_store import build_knowledge_base, search


def main():
    print("Loading knowledge base...")
    index, chunks = build_knowledge_base()
    print(f"Knowledge base loaded with {index.ntotal} vectors and {len(chunks)} chunks.\n")

    query = "Python machine learning pandas scikit-learn"
    print(f"Running search query: '{query}'")
    print("=" * 60)

    results = search(query, index, chunks, top_k=5)

    for i, res in enumerate(results, 1):
        meta = res.get("metadata", {})
        score = res.get("score", 0.0)
        text = res.get("text", "")
        snippet = text[:150] + "..." if len(text) > 150 else text

        print(f"Result #{i} | Similarity Score: {score:.4f}")
        print(f"  Role: {meta.get('role', 'N/A')}")
        print(f"  Document Type: {meta.get('document_type', 'N/A')}")
        print(f"  Document Name: {meta.get('document_name', 'N/A')}")
        print(f"  Snippet: {snippet}")
        print("-" * 60)


if __name__ == "__main__":
    main()
