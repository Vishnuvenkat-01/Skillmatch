import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
key = os.getenv("GEMINI_API_KEY")
if key:
    genai.configure(api_key=key.strip())

candidates = [
    "gemini-flash-latest",
    "gemini-pro-latest",
    "gemini-2.5-flash-lite",
    "gemini-3.6-flash",
]

print("=== Targeted Model Test ===")
for m in candidates:
    try:
        model = genai.GenerativeModel(m)
        res = model.generate_content("OK")
        print(f"MODEL '{m}': SUCCESS -> '{res.text.strip()}'")
    except Exception as e:
        print(f"MODEL '{m}': FAIL -> {type(e).__name__}: {str(e)[:150]}")
