import json
import os
import re
import time
import urllib.request
import urllib.error
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PROMPT_FILE_PATH = Path(__file__).parent.parent / "prompts" / "matching.txt"

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "mistralai/mistral-small-2603"


def _call_openrouter(prompt: str, api_key: str) -> str:
    """Call OpenRouter chat completion API. Returns raw response text."""
    payload = json.dumps({
        "model": OPENROUTER_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
        "max_tokens": 800,
    }).encode("utf-8")

    req = urllib.request.Request(
        OPENROUTER_API_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:8503",
            "X-Title": "CareerMatch AI",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode("utf-8"))
        return body["choices"][0]["message"]["content"]


def _clean_json_response(raw_text: str) -> str:
    """
    Extract the JSON payload from an LLM response that may contain:
    - Markdown code fences (```json ... ```) anywhere in the response
    - Preamble text before the fence
    - Trailing commentary after the closing fence
    - Bare JSON with no fencing at all
    - Leading / trailing whitespace
    """
    text = raw_text.strip()

    fence_match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip()

    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        return brace_match.group(0).strip()

    return text


def extract_role_requirements(role_name: str, role_chunks: list[dict]) -> dict:
    """
    Extract required_skills and preferred_skills for a given role from its document chunks
    using OpenRouter (mistral-7b-instruct).

    Args:
        role_name (str): Target role name.
        role_chunks (list[dict]): Chunks associated with this role.

    Returns:
        dict: Dict containing {"required_skills": [...], "preferred_skills": [...]}
    """
    if not role_chunks:
        print(f"[matcher] No chunks available for role '{role_name}'; returning empty requirements.")
        return {"required_skills": [], "preferred_skills": []}

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key or api_key.strip() in ("", "your_key_here"):
        print(f"[matcher] OPENROUTER_API_KEY missing for role '{role_name}'.")
        return {"required_skills": [], "preferred_skills": []}

    if not PROMPT_FILE_PATH.exists():
        print(f"[matcher] Prompt file missing: {PROMPT_FILE_PATH}")
        return {"required_skills": [], "preferred_skills": []}

    with open(PROMPT_FILE_PATH, "r", encoding="utf-8") as f:
        prompt_template = f.read()

    role_text = "\n\n".join([c.get("text", "") for c in role_chunks if c.get("text")])
    prompt = (prompt_template
               .replace("{role_name}", role_name)
               .replace("{role_text}", role_text))

    raw_text = None
    last_err = None
    for attempt in range(1, 4):
        try:
            raw_text = _call_openrouter(prompt, api_key.strip())
            if raw_text and raw_text.strip():
                break
        except Exception as api_err:
            last_err = api_err
            print(f"[matcher] OpenRouter attempt {attempt}/3 for role '{role_name}': {type(api_err).__name__} - {str(api_err)[:100]}")
            if attempt < 3:
                time.sleep(2 * attempt)

    if not raw_text or not raw_text.strip():
        print(f"[matcher] All OpenRouter attempts failed for role '{role_name}': {last_err}")
        return {"required_skills": [], "preferred_skills": []}

    cleaned_text = _clean_json_response(raw_text)

    try:
        data = json.loads(cleaned_text)
        req_skills = data.get("required_skills", [])
        pref_skills = data.get("preferred_skills", [])
        return {
            "required_skills": req_skills if isinstance(req_skills, list) else [],
            "preferred_skills": pref_skills if isinstance(pref_skills, list) else []
        }
    except json.JSONDecodeError as json_err:
        print(f"[matcher] JSON parse error for role '{role_name}': {json_err}\nRaw output:\n{raw_text}")
        return {"required_skills": [], "preferred_skills": []}


def _normalize_text(text: str) -> str:
    """Normalize string for fuzzy/token comparison."""
    return re.sub(r'[^a-z0-9\s]', '', str(text).lower()).strip()


def _skill_pattern(norm_skill: str) -> re.Pattern:
    """
    Build a compiled regex that matches the skill on word boundaries.
    This prevents short skills like 'R', 'Go', or 'C' from ghost-matching
    inside longer words (e.g. 'R' inside 'React', 'C' inside 'Science').
    """
    return re.compile(r'(?<![a-z0-9])' + re.escape(norm_skill) + r'(?![a-z0-9])')


def _is_skill_matched(target_skill: str, candidate_skills: list[str], full_resume_text: str = "") -> bool:
    """
    Check if target_skill matches any candidate skill or appears in full_resume_text.

    Matching rules (in priority order):
    1. Word-boundary regex match against each candidate skill string.
    2. Multi-word target: every token in target must appear in the candidate skill
       (e.g. 'Machine Learning' matches 'Machine Learning Engineer').
    3. Word-boundary regex match against the full resume text.

    The former reverse-subset rule (cand_tokens ⊆ target_tokens) is intentionally
    removed: a candidate who lists 'Python' should NOT auto-match 'Python Django'.
    """
    norm_target = _normalize_text(target_skill)
    if not norm_target:
        return False

    target_tokens = norm_target.split()
    pattern = _skill_pattern(norm_target)

    # 1. Match against each declared candidate skill
    for cand_skill in candidate_skills:
        norm_cand = _normalize_text(cand_skill)
        if not norm_cand:
            continue

        # Exact or word-boundary substring match
        if pattern.search(norm_cand):
            return True

        # Multi-word target: all target tokens must appear in the candidate skill string
        if len(target_tokens) > 1:
            cand_tokens = set(norm_cand.split())
            if all(t in cand_tokens for t in target_tokens):
                return True

    # 2. Fall back to whole-resume word-boundary search
    if full_resume_text:
        norm_resume = _normalize_text(full_resume_text)
        if pattern.search(norm_resume):
            return True

    return False


def _calculate_education_score(candidate_education) -> float:
    """
    Calculate education score out of 15 points.

    Tiers (evaluated top-down, first match wins):
      15 = STEM/tech-specific degree confirmed
      10 = Generic degree (bachelor/master/phd) without STEM keyword
       5 = Any education entry present but degree level unclear
       0 = No education listed

    Separating generic degree words ('bachelor', 'master') into a lower tier
    prevents a BA in an unrelated field from earning full education credit.
    """
    if not candidate_education:
        return 0.0

    edu_str = (
        json.dumps(candidate_education).lower()
        if not isinstance(candidate_education, str)
        else candidate_education.lower()
    )
    if not edu_str.strip():
        return 0.0

    # Tier 1 — explicit STEM / tech field keywords
    stem_keywords = [
        "computer science", "data science", "information technology",
        "artificial intelligence", "machine learning", "software engineering",
        "computer engineering", "electrical engineering", "electronics",
        "mathematics", "statistics", "physics",
        "b.tech", "m.tech", "b.e", "m.e",
    ]
    for kw in stem_keywords:
        if kw in edu_str:
            return 15.0

    # Tier 2 — a degree is mentioned but field is generic or unclear
    degree_keywords = ["bachelor", "master", "phd", "b.s", "m.s", "b.a", "m.a", "degree"]
    for kw in degree_keywords:
        if kw in edu_str:
            return 10.0

    # Tier 3 — some education data present but unrecognised format
    return 5.0


def _calculate_project_score(candidate_projects, target_skills: list[str]) -> float:
    """
    Calculate project score out of 10 points.

    Score is proportional: (# of target skills found in projects) / (# target skills) * 10.
    Uses the same word-boundary matching as _is_skill_matched to avoid false positives
    from short skill names embedded in longer words.
    Capped at 10.0.
    """
    if not candidate_projects or not target_skills:
        return 0.0

    proj_str = (
        json.dumps(candidate_projects).lower()
        if not isinstance(candidate_projects, str)
        else candidate_projects.lower()
    )
    if not proj_str.strip():
        return 0.0

    matched = 0
    for skill in target_skills:
        norm_skill = _normalize_text(skill)
        if not norm_skill:
            continue
        if _skill_pattern(norm_skill).search(proj_str):
            matched += 1

    return min(10.0, (matched / len(target_skills)) * 10.0)


def _calculate_experience_score(candidate_experience) -> float:
    """
    Calculate experience score out of 5 points.
    5 = experience entry exists
    0 = empty
    """
    if not candidate_experience:
        return 0.0
    if isinstance(candidate_experience, list) and len(candidate_experience) > 0:
        return 5.0
    if isinstance(candidate_experience, str) and candidate_experience.strip():
        return 5.0
    return 0.0


def categorize_skill_gaps(missing_required: list, missing_preferred: list) -> list[dict]:
    """
    Categorize missing skills into priority tiers:
    - Missing required skills -> priority 'high'
    - Missing preferred skills -> priority 'medium'

    Args:
        missing_required (list): List of missing required skills (dicts or strings).
        missing_preferred (list): List of missing preferred skills (dicts or strings).

    Returns:
        list[dict]: Categorized missing skills: [{"skill": "Docker", "priority": "high"}, ...]
    """
    missing_skills = []

    for item in missing_required:
        skill_name = item.get("skill") if isinstance(item, dict) else str(item)
        if skill_name:
            missing_skills.append({
                "skill": skill_name,
                "priority": "high"
            })

    for item in missing_preferred:
        skill_name = item.get("skill") if isinstance(item, dict) else str(item)
        if skill_name:
            missing_skills.append({
                "skill": skill_name,
                "priority": "medium"
            })

    return missing_skills


def calculate_match_score(
    candidate_profile: dict,
    role_requirements: dict,
    candidate_education=None,
    full_resume_text: str = ""
) -> dict:
    """
    Compute role match score purely in Python using fixed weight formula.

    Weights:
    - Required Skills: 50%
    - Preferred Skills: 20%
    - Education/Eligibility: 15%
    - Relevant Projects: 10%
    - Experience: 5%

    Args:
        candidate_profile (dict): Extracted candidate profile.
        role_requirements (dict): {"required_skills": [...], "preferred_skills": [...]}
        candidate_education: Candidate education info (optional, defaults to profile education).
        full_resume_text (str): Optional raw resume text for deep skill verification.

    Returns:
        dict: Detailed breakdown containing percentage score, component scores,
              checkmark-style boolean skill lists, and prioritized missing_skills list.
    """
    cand_skills = candidate_profile.get("skills", [])
    if isinstance(cand_skills, str):
        cand_skills = [s.strip() for s in cand_skills.split(",") if s.strip()]

    if candidate_education is None:
        candidate_education = candidate_profile.get("education", [])

    candidate_projects = candidate_profile.get("projects", [])
    candidate_experience = candidate_profile.get("experience", [])

    req_skills = role_requirements.get("required_skills", [])
    pref_skills = role_requirements.get("preferred_skills", [])

    # 1. Required Skills Match (50%)
    matched_req = []
    missing_req = []
    for skill in req_skills:
        matched = _is_skill_matched(skill, cand_skills, full_resume_text)
        if matched:
            matched_req.append({"skill": skill, "matched": True})
        else:
            missing_req.append({"skill": skill, "matched": False})

    req_count = len(req_skills)
    matched_req_count = len(matched_req)
    # If the role extraction returned no required skills, award 0 (unknown ≠ perfect match).
    # Defaulting to 50 would give every resume an artificial floor of 70/100.
    req_score = (matched_req_count / req_count) * 50.0 if req_count > 0 else 0.0

    # 2. Preferred Skills Match (20%)
    matched_pref = []
    missing_pref = []
    for skill in pref_skills:
        matched = _is_skill_matched(skill, cand_skills, full_resume_text)
        if matched:
            matched_pref.append({"skill": skill, "matched": True})
        else:
            missing_pref.append({"skill": skill, "matched": False})

    pref_count = len(pref_skills)
    matched_pref_count = len(matched_pref)
    # Same logic: 0 if no preferred skills extracted, not automatic full credit.
    pref_score = (matched_pref_count / pref_count) * 20.0 if pref_count > 0 else 0.0

    # 3. Education Match (15%)
    edu_score = _calculate_education_score(candidate_education)

    # 4. Project Match (10%)
    all_target_skills = req_skills + pref_skills
    proj_score = _calculate_project_score(candidate_projects, all_target_skills)

    # 5. Experience Match (5%)
    exp_score = _calculate_experience_score(candidate_experience)

    # Overall percentage score calculation
    overall_score = min(100.0, req_score + pref_score + edu_score + proj_score + exp_score)

    # Categorize skill gaps into high/medium priority lists
    missing_skills = categorize_skill_gaps(missing_req, missing_pref)

    return {
        "overall_score": round(overall_score, 1),
        "breakdown": {
            "required_skills_score": round(req_score, 1),
            "preferred_skills_score": round(pref_score, 1),
            "education_score": round(edu_score, 1),
            "project_score": round(proj_score, 1),
            "experience_score": round(exp_score, 1)
        },
        "matched_required_skills": matched_req,
        "missing_required_skills": missing_req,
        "matched_preferred_skills": matched_pref,
        "missing_preferred_skills": missing_pref,
        "missing_skills": missing_skills
    }
