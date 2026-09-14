import os, sys
sys.path.insert(0, os.getcwd())
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
key = os.getenv("GEMINI_API_KEY")
print("[TEST] API Key found:", bool(key))

genai.configure(api_key=key)
model = genai.GenerativeModel("gemini-flash-latest")
res = model.generate_content("Respond with JSON: {\"status\": \"OK\"}")
print("[TEST] gemini-flash-latest direct call output:\n", res.text)

from services.profile_extractor import extract_candidate_profile
resume_sample = """
Jane Doe
Email: jane.doe@example.com
Phone: 555-123-4567
Skills: Python, Streamlit, Machine Learning, Data Science, SQL
Education: BS Computer Science, Stanford University
Experience: Software Engineer Intern at Tech Corp
Projects: Built an AI resume screening app with RAG
"""
print("\n[TEST] Testing extract_candidate_profile with gemini-flash-latest...")
try:
    profile = extract_candidate_profile(resume_sample)
    print("[TEST] SUCCESS! Extracted candidate name:", profile.get("name"))
    print("[TEST] Extracted candidate skills:", profile.get("skills"))
except Exception as e:
    print(f"[TEST] extract_candidate_profile failed: {type(e).__name__}: {e}")
