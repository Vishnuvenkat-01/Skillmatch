import os
from dotenv import load_dotenv
import google.generativeai as genai

def test_all_models():
    load_dotenv()
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        print("No key found.")
        return
    genai.configure(api_key=key.strip())
    
    models = genai.list_models()
    gen_models = [m.name.replace("models/", "") for m in models if "generateContent" in m.supported_generation_methods]
    
    print(f"Testing {len(gen_models)} models for generateContent capability:\n")
    
    working_models = []
    
    for m in gen_models:
        try:
            mod = genai.GenerativeModel(m)
            res = mod.generate_content("Respond with only the word OK")
            txt = res.text.strip() if res and hasattr(res, "text") else "NO_TEXT"
            print(f"  [SUCCESS] '{m}' -> '{txt}'")
            working_models.append(m)
        except Exception as e:
            msg = str(e).splitlines()[0] if str(e) else type(e).__name__
            print(f"  [FAIL] '{m}' -> {type(e).__name__}: {msg[:120]}")
            
    print("\n--- Summary ---")
    print(f"Working models count: {len(working_models)}")
    for wm in working_models:
        print(f"  - {wm}")

if __name__ == "__main__":
    test_all_models()
