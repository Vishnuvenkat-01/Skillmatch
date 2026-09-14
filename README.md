# CareerMatch AI 🎯

CareerMatch AI is an intelligent RAG-powered resume analyzer and career roadmap assistant. It parses candidate resumes, extracts structured profiles, retrieves role benchmarks from a local vector database using FAISS & Sentence Transformers, computes transparent match scores in Python, and generates tailored learning roadmaps and interview preparation guidance.

---

## 🚀 Quick Setup & Installation

### 1. Prerequisites
- **Python 3.10+**
- **Gemini API Key** from [Google AI Studio](https://aistudio.google.com/)

### 2. Environment Setup
Clone or download the project repository, then set up a Python virtual environment:

```bash
# Navigate to project directory
cd "Basic RAG"

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# On Windows (CMD):
.\venv\Scripts\activate.bat
# On macOS/Linux:
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Create a `.env` file in the root directory of the project:

```env
GEMINI_API_KEY=your_actual_gemini_api_key_here
```

---

## 🏃 Running the Application

Start the Streamlit application:

```bash
streamlit run app.py
```

The app will open automatically in your browser at `http://localhost:8501`.

---

## 📁 Project Structure

```
├── app.py                     # Main Streamlit 9-section UI application
├── services/
│   ├── resume_parser.py       # PDF/DOCX text extraction with low-word-count detection
│   ├── profile_extractor.py   # LLM structured profile extraction
│   ├── vector_store.py        # FAISS vector store & Sentence Transformer embeddings
│   ├── rag_engine.py          # RAG candidate query building & role identification
│   ├── matcher.py             # Python scoring engine (word boundaries, weighted scores)
│   └── roadmap.py             # Roadmap, interview Q&A & resume suggestion generation
├── document/                  # Benchmark role profiles and guides (PDF format)
├── data/
│   └── metadata.json          # Document catalog & role metadata
├── prompts/                   # LLM prompt templates
├── vectorstore/               # Persisted FAISS index and JSON chunks cache
├── requirements.txt           # Python dependency list
└── README.md                  # Project setup and usage instructions
```

---

## ⚠️ Notes & Disclaimers

- **Illustrative Scores:** Match percentages are compatibility estimates calculated in Python for learning guidance and are not hiring predictions.
- **Privacy:** Resumes uploaded in Streamlit are processed in-memory for the duration of the session and are not saved permanently.
