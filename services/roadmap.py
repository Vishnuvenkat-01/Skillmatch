import json
import os
import re
import time
import urllib.request
import urllib.error
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PROMPT_FILE_PATH = Path(__file__).parent.parent / "prompts" / "roadmap.txt"
PROMPT_IMPROVEMENT_PATH = Path(__file__).parent.parent / "prompts" / "resume_improvement.txt"

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "mistralai/mistral-small-2603"


def _call_openrouter(prompt: str, api_key: str, max_tokens: int = 1500) -> str:
    """Call OpenRouter chat completion API. Returns raw response text."""
    payload = json.dumps({
        "model": OPENROUTER_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": max_tokens,
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
    with urllib.request.urlopen(req, timeout=40) as resp:
        body = json.loads(resp.read().decode("utf-8"))
        return body["choices"][0]["message"]["content"]


def _clean_json_response(raw_text: str) -> str:
    """
    Extract the JSON payload from a Gemini response that may contain:
    - Markdown code block fences (```json ... ```) anywhere in the response
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


def generate_roadmap(candidate_profile: dict, missing_skills: list[dict]) -> dict:
    """
    Generate a 2-4 week learning roadmap and 5 structured interview questions using Gemini API based on skill gaps.

    Args:
        candidate_profile (dict): Candidate profile dict.
        missing_skills (list[dict]): List of missing skill dicts with priorities.

    Returns:
        dict: Dict conforming to schema:
              {
                "roadmap": [...],
                "interview_questions": [...]
              }
    """
    default_fallback = {
        "roadmap": [],
        "interview_questions": [
            {
                "question": "Can you describe a challenging technical project you worked on recently?",
                "type": "applied",
                "related_skill": "General Software Engineering"
            },
            {
                "question": "How do you approach debugging complex issues in your codebase?",
                "type": "conceptual",
                "related_skill": "Debugging & Troubleshooting"
            },
            {
                "question": "What strategies do you use for code optimization and performance tuning?",
                "type": "applied",
                "related_skill": "Performance Optimization"
            },
            {
                "question": "How do you stay up-to-date with new technologies in your field?",
                "type": "conceptual",
                "related_skill": "Continuous Learning"
            },
            {
                "question": "Describe a situation where you had to collaborate across teams to deliver a feature.",
                "type": "applied",
                "related_skill": "Collaboration"
            }
        ]
    }

    if not missing_skills:
        return default_fallback

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key or api_key.strip() in ("", "your_key_here"):
        print("[roadmap] Missing OPENROUTER_API_KEY for roadmap generation.")
        return default_fallback

    if not PROMPT_FILE_PATH.exists():
        print(f"[roadmap] Prompt file missing at {PROMPT_FILE_PATH}")
        return default_fallback

    with open(PROMPT_FILE_PATH, "r", encoding="utf-8") as f:
        prompt_template = f.read()

    profile_str = json.dumps(candidate_profile, indent=2)
    skills_str = json.dumps(missing_skills, indent=2)

    prompt = (prompt_template
               .replace("{candidate_profile}", profile_str)
               .replace("{missing_skills}", skills_str))

    raw_text = None
    last_err = None
    for attempt in range(1, 4):
        try:
            raw_text = _call_openrouter(prompt, api_key.strip(), max_tokens=1500)
            if raw_text and raw_text.strip():
                break
        except Exception as api_err:
            last_err = api_err
            print(f"[roadmap] OpenRouter attempt {attempt}/3 (generate_roadmap): {type(api_err).__name__} - {str(api_err)[:100]}")
            if attempt < 3:
                time.sleep(2 * attempt)

    if not raw_text or not raw_text.strip():
        print(f"[roadmap] All OpenRouter attempts failed (generate_roadmap): {last_err}")
        return default_fallback

    cleaned_text = _clean_json_response(raw_text)

    try:
        data = json.loads(cleaned_text)
        roadmap = data.get("roadmap", [])
        questions = data.get("interview_questions", [])
        return {
            "roadmap": roadmap if isinstance(roadmap, list) else [],
            "interview_questions": questions if isinstance(questions, list) else default_fallback["interview_questions"]
        }
    except json.JSONDecodeError as json_err:
        print(f"[roadmap] JSON parse error (generate_roadmap): {json_err}\nRaw output:\n{raw_text}")
        return default_fallback


def generate_resume_suggestions(candidate_profile: dict, top_missing_skills: list) -> dict:
    """
    Generate 3-5 concrete resume improvement suggestions using Gemini API without fabricating skills.

    Args:
        candidate_profile (dict): Candidate profile dict.
        top_missing_skills (list): List of missing skills or missing skill dicts.

    Returns:
        dict: Dict conforming to schema: {"suggestions": ["...", "..."]}
    """
    default_fallback = {
        "suggestions": [
            "Quantify key accomplishments in your experience section with clear metrics and impact.",
            "Highlight core skills and tools relevant to your target roles at the top of your resume.",
            "Add detailed bullet points to major projects describing your technical role and results achieved."
        ]
    }

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key or api_key.strip() in ("", "your_key_here"):
        return default_fallback

    if not PROMPT_IMPROVEMENT_PATH.exists():
        return default_fallback

    with open(PROMPT_IMPROVEMENT_PATH, "r", encoding="utf-8") as f:
        prompt_template = f.read()

    profile_str = json.dumps(candidate_profile, indent=2)
    skills_str = json.dumps(top_missing_skills, indent=2)

    prompt = (prompt_template
               .replace("{candidate_profile}", profile_str)
               .replace("{top_missing_skills}", skills_str))

    raw_text = None
    last_err = None
    for attempt in range(1, 4):
        try:
            raw_text = _call_openrouter(prompt, api_key.strip(), max_tokens=800)
            if raw_text and raw_text.strip():
                break
        except Exception as api_err:
            last_err = api_err
            print(f"[roadmap] OpenRouter attempt {attempt}/3 (generate_resume_suggestions): {type(api_err).__name__} - {str(api_err)[:100]}")
            if attempt < 3:
                time.sleep(2 * attempt)

    if not raw_text or not raw_text.strip():
        print(f"[roadmap] All OpenRouter attempts failed (generate_resume_suggestions): {last_err}")
        return default_fallback

    cleaned_text = _clean_json_response(raw_text)

    try:
        data = json.loads(cleaned_text)
        suggestions = data.get("suggestions", [])
        return {
            "suggestions": suggestions if isinstance(suggestions, list) else default_fallback["suggestions"]
        }
    except json.JSONDecodeError as json_err:
        print(f"[roadmap] JSON parse error (generate_resume_suggestions): {json_err}\nRaw output:\n{raw_text}")
        return default_fallback
