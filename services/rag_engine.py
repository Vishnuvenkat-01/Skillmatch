from collections import defaultdict
from services.vector_store import search


def build_candidate_query(candidate_profile: dict) -> str:
    """
    Construct a consolidated query string from a candidate profile's skills,
    projects, certifications, and experience.

    Args:
        candidate_profile (dict): Extracted candidate profile dictionary.

    Returns:
        str: A consolidated query string for vector similarity retrieval.
    """
    if not candidate_profile:
        return ""

    query_parts = []

    # 1. Extract Skills
    skills = candidate_profile.get("skills", [])
    if isinstance(skills, list) and skills:
        cleaned_skills = [str(s).strip() for s in skills if s and str(s).strip()]
        if cleaned_skills:
            query_parts.append("Skills: " + ", ".join(cleaned_skills))
    elif isinstance(skills, str) and skills.strip():
        query_parts.append(f"Skills: {skills.strip()}")

    # 2. Extract Certifications
    certs = candidate_profile.get("certifications", [])
    if isinstance(certs, list) and certs:
        cert_names = []
        for c in certs:
            if isinstance(c, dict):
                cert_names.append(c.get("name") or str(c))
            elif c:
                cert_names.append(str(c))
        if cert_names:
            query_parts.append("Certifications: " + ", ".join(cert_names))
    elif isinstance(certs, str) and certs.strip():
        query_parts.append(f"Certifications: {certs.strip()}")

    # 3. Extract Projects & Tech Stacks
    projects = candidate_profile.get("projects", [])
    if isinstance(projects, list) and projects:
        proj_texts = []
        for p in projects:
            if isinstance(p, dict):
                p_title = p.get("title") or p.get("name", "")
                p_tech = p.get("tech_stack") or p.get("technologies", "")
                p_desc = p.get("description", "")
                p_str = " ".join(filter(None, [str(p_title), str(p_tech), str(p_desc)]))
                if p_str:
                    proj_texts.append(p_str)
            elif p:
                proj_texts.append(str(p))
        if proj_texts:
            query_parts.append("Projects: " + " | ".join(proj_texts))

    # 4. Extract Experience
    experience = candidate_profile.get("experience", [])
    if isinstance(experience, list) and experience:
        exp_texts = []
        for e in experience:
            if isinstance(e, dict):
                role_title = e.get("title") or e.get("role", "")
                exp_desc = e.get("description") or e.get("highlights", "")
                exp_str = " ".join(filter(None, [str(role_title), str(exp_desc)]))
                if exp_str:
                    exp_texts.append(exp_str)
            elif e:
                exp_texts.append(str(e))
        if exp_texts:
            query_parts.append("Experience: " + " | ".join(exp_texts))

    consolidated_query = " ".join(query_parts).strip()
    return consolidated_query if consolidated_query else "Candidate technical profile"


def retrieve_relevant_knowledge(
    candidate_profile: dict,
    index,
    chunks: list[dict],
    top_k: int = 8
) -> list[dict]:
    """
    Build a candidate query string and retrieve the top_k relevant knowledge base chunks.

    Args:
        candidate_profile (dict): Candidate profile dictionary.
        index (faiss.IndexFlatIP): FAISS index instance.
        chunks (list[dict]): Full list of chunks aligned with the FAISS index.
        top_k (int): Number of chunks to retrieve. Defaults to 8.

    Returns:
        list[dict]: Raw retrieved chunk dictionaries with similarity scores.

    Raises:
        RuntimeError: If the query is empty or the vector search returns no results.
    """
    query_text = build_candidate_query(candidate_profile)
    if not query_text.strip():
        raise RuntimeError(
            "Could not build a search query from your profile. "
            "Please make sure your resume contains at least a few skills or work items."
        )

    retrieved_chunks = search(
        query_text=query_text,
        index=index,
        chunks=chunks,
        top_k=top_k,
        role_filter=None
    )

    if not retrieved_chunks:
        raise RuntimeError(
            "No relevant content was found in the knowledge base for your profile. "
            "This may mean the knowledge base index is empty or your profile is very sparse."
        )

    return retrieved_chunks


def identify_candidate_roles(
    candidate_profile: dict,
    index,
    chunks: list[dict],
    top_n: int = 3
) -> list[str]:
    """
    Identify the top N distinct candidate target roles from retrieved role_profile chunks.

    Args:
        candidate_profile (dict): Candidate profile dictionary.
        index (faiss.IndexFlatIP): FAISS index instance.
        chunks (list[dict]): Full list of chunks aligned with the FAISS index.
        top_n (int): Number of distinct target roles to return. Defaults to 3.

    Returns:
        list[str]: List of top distinct role names (e.g. ["Machine Learning Engineer", ...]).
    """
    # Retrieve a larger set of top chunks to aggregate role signals
    retrieved_chunks = retrieve_relevant_knowledge(
        candidate_profile=candidate_profile,
        index=index,
        chunks=chunks,
        top_k=25
    )

    role_scores = defaultdict(float)

    for chunk in retrieved_chunks:
        meta = chunk.get("metadata", {})
        doc_type = meta.get("document_type", "")
        role = meta.get("role")

        # Only consider role_profile document types (excluding general guides)
        if doc_type == "role_profile" and role and role.strip() and role.strip().lower() != "general":
            score = chunk.get("score", 1.0)
            role_scores[role.strip()] += score

    # Sort roles by cumulative similarity score in descending order
    sorted_roles = sorted(role_scores.items(), key=lambda x: x[1], reverse=True)
    top_roles = [role for role, score in sorted_roles[:top_n]]

    return top_roles
