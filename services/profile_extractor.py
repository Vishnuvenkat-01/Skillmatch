import json
import re
import os
import time
import urllib.request
import urllib.error
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

PROMPT_FILE_PATH = Path(__file__).parent.parent / "prompts" / "profile_extraction.txt"

# OpenRouter API endpoint and model
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
# mistral-7b: fast, cheap, excellent JSON output
OPENROUTER_MODEL = "mistralai/mistral-small-2603"


def _call_openrouter(prompt: str, api_key: str) -> str:
    """
    Call OpenRouter chat completion API using the OpenAI-compatible endpoint.
    Returns the raw response text from the model.
    Raises ValueError on API errors.
    """
    payload = json.dumps({
        "model": OPENROUTER_MODEL,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.1,
        "max_tokens": 1500,
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

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return body["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as http_err:
        raw = http_err.read().decode("utf-8", errors="replace")
        raise ValueError(
            f"OpenRouter API error {http_err.code}: {raw[:200]}"
        ) from http_err
    except urllib.error.URLError as url_err:
        raise ValueError(
            f"OpenRouter connection error: {url_err.reason}"
        ) from url_err


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

    # 1. Try to pull out the first fenced block (``` or ```json)
    fence_match = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip()

    # 2. No fence found — try to extract the first {...} JSON object
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        return brace_match.group(0).strip()

    # 3. Return as-is and let json.loads report the error
    return text


_PROFILE_DEFAULTS: dict = {
    "name": "",
    "email": "",
    "phone": "",
    "location": "",
    "summary": "",
    "education": [],
    "skills": [],
    "certifications": [],
    "projects": [],
    "experience": [],
    "languages": [],
    "achievements": [],
}


def _apply_defaults(profile: dict) -> dict:
    """
    Ensure every expected profile field is present with a safe default value.
    Never overwrites a field that the model already populated.
    """
    for key, default in _PROFILE_DEFAULTS.items():
        if key not in profile or profile[key] is None:
            profile[key] = default
    return profile


def extract_candidate_profile(resume_text: str) -> dict:
    """
    Extract structured candidate profile information from raw resume text
    using OpenRouter (mistral-7b-instruct).

    Args:
        resume_text (str): The extracted plain text of the candidate's resume.

    Returns:
        dict: Candidate profile conforming to the JSON schema.

    Raises:
        ValueError: If API key is missing, prompt template is missing,
                    API call fails, or LLM response is not valid JSON.
    """
    if not resume_text or not resume_text.strip():
        raise ValueError(
            "The resume text is empty — nothing could be extracted from your file. "
            "Please upload a text-based PDF or Word document."
        )

    # Validate OPENROUTER_API_KEY
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key or api_key.strip() in ("", "your_key_here"):
        raise ValueError(
            "An OpenRouter API key is required but was not found. "
            "Please add OPENROUTER_API_KEY=<your_key> to your .env file and restart the app."
        )

    # Load prompt template
    if not PROMPT_FILE_PATH.exists():
        raise ValueError(
            "The profile extraction prompt template is missing. "
            f"Expected it at: {PROMPT_FILE_PATH}"
        )

    with open(PROMPT_FILE_PATH, "r", encoding="utf-8") as f:
        prompt_template = f.read()

    prompt = prompt_template.replace("{resume_text}", resume_text)

    # Call OpenRouter with retry
    last_err = None
    raw_text = None
    for attempt in range(1, 4):
        try:
            raw_text = _call_openrouter(prompt, api_key.strip())
            if raw_text and raw_text.strip():
                break
        except Exception as api_err:
            last_err = api_err
            err_type = type(api_err).__name__
            err_msg = str(api_err)
            print(
                f"[profile_extractor] OpenRouter attempt {attempt}/3 failed: "
                f"type={err_type}, msg={err_msg[:120]}"
            )
            if attempt < 3:
                time.sleep(2 * attempt)

    if not raw_text or not raw_text.strip():
        err_type = type(last_err).__name__ if last_err else "UnknownError"
        err_msg = str(last_err) if last_err else "No response returned"
        print(f"[profile_extractor] All OpenRouter attempts failed: {err_type} - {err_msg}")
        raise ValueError(
            f"The AI service could not be reached while extracting your profile. "
            f"[{err_type}: {err_msg[:120]}]"
        )

    cleaned_text = _clean_json_response(raw_text)

    # Parse JSON
    try:
        profile_dict = json.loads(cleaned_text)
        if not isinstance(profile_dict, dict):
            raise ValueError(
                f"Expected a JSON object from the AI, got {type(profile_dict).__name__}."
            )
        return _apply_defaults(profile_dict)
    except json.JSONDecodeError as json_err:
        print(
            f"[profile_extractor] JSON parse error: {json_err}\n"
            f"Cleaned text:\n{cleaned_text}\n"
            f"Original response:\n{raw_text}"
        )
        raise ValueError(
            "The AI returned a response that could not be understood (invalid JSON). "
            "Please try uploading your resume again."
        ) from json_err
