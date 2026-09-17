import streamlit as st
from auth import run_auth_gate, render_user_badge
from services.resume_parser import extract_resume_text
from services.profile_extractor import extract_candidate_profile
from services.vector_store import load_index
from services.rag_engine import identify_candidate_roles
from services.matcher import extract_role_requirements, calculate_match_score
from services.roadmap import generate_roadmap, generate_resume_suggestions
from ui_helpers import format_section_as_text
from ui_sections import (
    render_overview,
    render_resume_view,
    render_candidate_profile_page,
    render_career_matches,
    render_skill_gaps,
    render_career_roadmap,
    render_projects,
    render_interview_prep,
    render_resume_improvement,
    render_job_readiness,
)

# ── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CareerMatch AI",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ──────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Main Canvas & Layout Tokens ── */
.main .block-container {
    padding-top: 2rem !important;
    padding-bottom: 3rem !important;
    max-width: 1060px !important;
}

/* ── Typography Scale ── */
h1 {
    font-size: 1.65rem !important;
    font-weight: 700 !important;
    color: #0f172a !important;
    letter-spacing: -0.02em !important;
    margin-bottom: 0.4rem !important;
}

h2, h3 {
    font-size: 1.20rem !important;
    font-weight: 600 !important;
    color: #1e293b !important;
    margin-top: 1.5rem !important;
    margin-bottom: 0.75rem !important;
}

p, span, label {
    color: #334155;
}

/* ── Skill-gap priority badges ── */
.badge-high   { background:#fee2e2; color:#ef4444; border:1px solid #fca5a5;
                padding:3px 10px; border-radius:99px; font-size:.76rem; font-weight:600; }
.badge-medium { background:#fef3c7; color:#d97706; border:1px solid #fcd34d;
                padding:3px 10px; border-radius:99px; font-size:.76rem; font-weight:600; }
.badge-beginner     { background:#e0f2fe; color:#0284c7; border:1px solid #bae6fd;
                      padding:3px 10px; border-radius:99px; font-size:.76rem; font-weight:600; }
.badge-intermediate { background:#f3e8ff; color:#9333ea; border:1px solid #e9d5ff;
                      padding:3px 10px; border-radius:99px; font-size:.76rem; font-weight:600; }

/* ── Metric Card Refinements ── */
[data-testid="stMetric"] {
    background-color: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 10px !important;
    padding: 14px 18px !important;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.02) !important;
    transition: transform 0.15s ease, box-shadow 0.15s ease !important;
}

[data-testid="stMetric"]:hover {
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04) !important;
    border-color: #cbd5e1 !important;
}

[data-testid="stMetricLabel"] p,
[data-testid="stMetricLabel"] span {
    font-size: 0.76rem !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
    color: #64748b !important;
    margin-bottom: 4px !important;
}

[data-testid="stMetricValue"] div,
[data-testid="stMetricValue"] span {
    font-size: 1.70rem !important;
    font-weight: 700 !important;
    color: #1f3bb3 !important;
    line-height: 1.2 !important;
}

/* ── File Uploader & Dropzone Styling ── */
[data-testid="stFileUploader"] {
    background: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 12px !important;
    padding: 16px !important;
}

[data-testid="stFileUploader"] section {
    background-color: #ffffff !important;
    border: 2px dashed #cbd5e1 !important;
    border-radius: 10px !important;
    padding: 24px 16px !important;
    transition: border-color 0.15s ease, background-color 0.15s ease !important;
}

[data-testid="stFileUploader"] section:hover {
    border-color: #1f3bb3 !important;
    background-color: #f8fafc !important;
}

/* ── Consent Checkbox Styling ── */
[data-testid="stCheckbox"] {
    margin-top: 10px !important;
    margin-bottom: 14px !important;
}

[data-testid="stCheckbox"] input[type="checkbox"] {
    accent-color: #1f3bb3 !important;
    width: 16px !important;
    height: 16px !important;
    cursor: pointer !important;
}

[data-testid="stCheckbox"] label p {
    font-size: 0.92rem !important;
    color: #334155 !important;
    font-weight: 500 !important;
}

/* ── Status Banner Polish ── */
[data-testid="stNotification"] {
    border-radius: 8px !important;
    border: 1px solid #bfdbfe !important;
    background-color: #eff6ff !important;
}

/* ── Primary Buttons & Controls ── */
.stButton > button {
    background-color: #1f3bb3 !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 6px !important;
    font-weight: 600 !important;
    padding: 8px 16px !important;
    transition: background-color 0.15s ease !important;
}

.stButton > button:hover {
    background-color: #1a3299 !important;
}

/* ── Sidebar Navigation Rectangular Menu Block Styling ── */
section[data-testid="stSidebar"] {
    min-width: 250px !important;
}

section[data-testid="stSidebar"] div[role="radiogroup"] {
    width: 100% !important;
    gap: 4px !important;
}

/* Hide only the radio circle graphic container, keeping text container intact */
section[data-testid="stSidebar"] div[role="radiogroup"] > label > div:first-child:not([data-testid="stMarkdownContainer"]) {
    display: none !important;
}

/* Base style for full-width rectangular navigation items */
section[data-testid="stSidebar"] div[role="radiogroup"] > label {
    position: relative !important;
    display: flex !important;
    align-items: center !important;
    width: 100% !important;
    padding: 9px 12px !important;
    margin: 0 !important;
    border-radius: 8px !important;
    cursor: pointer !important;
    background: transparent !important;
    transition: background 0.15s ease-in-out !important;
    box-sizing: border-box !important;
}

section[data-testid="stSidebar"] div[role="radiogroup"] > label p {
    margin: 0 !important;
    font-size: 0.92rem !important;
    font-weight: 500 !important;
    color: #3c4257 !important;
    line-height: 1.4 !important;
}

/* Hover state for inactive rectangular items */
section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover {
    background: #f2f4f9 !important;
}

/* Active / Selected rectangular item highlight */
section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {
    background: #e8edff !important;
}

section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) p {
    color: #1f3bb3 !important;
    font-weight: 600 !important;
}

/* Section Group Headings */
section[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(1) {
    margin-top: 14px !important;
}
section[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(1)::before {
    content: "MAIN";
    position: absolute;
    top: -16px;
    left: 8px;
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    color: #94a3b8;
    pointer-events: none;
}

section[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(2) {
    margin-top: 22px !important;
}
section[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(2)::before {
    content: "PROFILE";
    position: absolute;
    top: -16px;
    left: 8px;
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    color: #94a3b8;
    pointer-events: none;
}

section[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(4) {
    margin-top: 22px !important;
}
section[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(4)::before {
    content: "CAREER ANALYSIS";
    position: absolute;
    top: -16px;
    left: 8px;
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    color: #94a3b8;
    pointer-events: none;
}

section[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(7) {
    margin-top: 22px !important;
}
section[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(7)::before {
    content: "PREPARATION";
    position: absolute;
    top: -16px;
    left: 8px;
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    color: #94a3b8;
    pointer-events: none;
}

section[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(10) {
    margin-top: 22px !important;
}
section[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(10)::before {
    content: "FINAL INSIGHT";
    position: absolute;
    top: -16px;
    left: 8px;
    font-size: 0.68rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    color: #94a3b8;
    pointer-events: none;
}
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# AUTHENTICATION GATE
# Must run before any protected content is rendered.
# ════════════════════════════════════════════════════════════════════════════
_authenticator = run_auth_gate()


# ════════════════════════════════════════════════════════════════════════════
# SIDEBAR NAVIGATION
# Rendered first so it is always visible regardless of which gate fires below.
# ════════════════════════════════════════════════════════════════════════════
PAGES = [
    "📋 Overview",
    "📄 Resume",
    "👤 Candidate Profile",
    "🏆 Career Matches",
    "🔍 Skill Gaps",
    "🗺️ Career Roadmap",
    "🚀 Projects",
    "🎤 Interview Prep",
    "📝 Resume Improvement",
    "⚡ Job Readiness",
]

with st.sidebar:
    st.markdown("## 🎯 CareerMatch AI")
    st.markdown("*AI-powered career intelligence*")
    st.divider()

    selected_page = st.radio(
        "Navigation",
        PAGES,
        label_visibility="collapsed",
        key="nav_page",
    )

    st.divider()
    st.caption("**Pipeline Status**")
    st.caption("✅ Resume uploaded"   if st.session_state.get("resume_text")      else "⏳ Resume not yet uploaded")
    st.caption("✅ Profile confirmed" if st.session_state.get("profile_confirmed") else "⏳ Profile not yet confirmed")
    st.caption("✅ Analysis complete" if st.session_state.get("match_results")     else "⏳ Analysis not yet run")
    st.divider()
    st.caption("🔒 Resume is processed for this session only and not stored permanently.")
    # ── Authenticated user info + logout ──────────────────────────────────
    render_user_badge(_authenticator)


# ════════════════════════════════════════════════════════════════════════════
# PIPELINE — GATE 1: UPLOAD + CONSENT
# All pipeline gates are UNCHANGED from the original app.
# ════════════════════════════════════════════════════════════════════════════
st.subheader("Upload Your Resume")
st.caption(
    "🔒 This prototype does not permanently store uploaded resumes. "
    "Your resume is processed only for this session."
)

uploaded_file = st.file_uploader(
    "Upload your resume (PDF or DOCX)",
    type=["pdf", "docx"],
    help="Supported formats: PDF (.pdf), Word (.docx)",
)
consent = st.checkbox("I consent to processing my resume text for career analysis.")

# Reset state when a new file is uploaded
if uploaded_file is not None:
    if st.session_state.get("current_file_name") != uploaded_file.name:
        st.session_state.update({
            "current_file_name":  uploaded_file.name,
            "resume_text":        None,
            "candidate_profile":  None,
            "profile_confirmed":  False,
            "match_results":      None,
            "roadmap_data":       None,
            "resume_suggestions": None,
        })

if uploaded_file is None:
    st.session_state.update({
        "current_file_name":  None,
        "resume_text":        None,
        "candidate_profile":  None,
        "profile_confirmed":  False,
        "match_results":      None,
        "roadmap_data":       None,
        "resume_suggestions": None,
    })
    st.info("💡 Upload your resume above and check the consent box to get started.")
    st.caption("✨ Once uploaded, CareerMatch AI will extract your profile, evaluate role readiness, and generate your step-by-step career roadmap.")
    st.stop()

if not consent:
    st.info("ℹ️ Please check the consent box above to process your uploaded resume.")
    st.stop()


# ════════════════════════════════════════════════════════════════════════════
# PIPELINE — STEP A: EXTRACT RESUME TEXT
# ════════════════════════════════════════════════════════════════════════════
if not st.session_state.get("resume_text"):
    try:
        with st.spinner("Extracting resume text…"):
            text, word_count = extract_resume_text(uploaded_file)
            st.session_state["resume_text"]       = text
            st.session_state["resume_word_count"] = word_count
    except Exception as e:
        print(f"[app] Resume extraction error: {e}")
        st.error(f"❌ Resume Extraction Error: {e}")
        st.stop()

resume_text = st.session_state["resume_text"]
word_count  = st.session_state.get("resume_word_count", len(resume_text.split()))

if word_count < 50:
    st.warning(
        f"⚠️ **Low Text Warning:** Only {word_count} words could be extracted. "
        "If your resume is a scanned document or image PDF, extraction may be incomplete."
    )

st.success("✅ Resume extracted. Use the sidebar to navigate.")


# ════════════════════════════════════════════════════════════════════════════
# PIPELINE — STEP B: EXTRACT CANDIDATE PROFILE VIA LLM
# ════════════════════════════════════════════════════════════════════════════
if not st.session_state.get("candidate_profile"):
    try:
        with st.spinner("Extracting your profile via AI…"):
            profile = extract_candidate_profile(resume_text)
            st.session_state["candidate_profile"] = profile
            st.session_state["profile_confirmed"] = False
    except Exception as e:
        print(f"[app] Profile extraction error: {e}")
        st.error(f"❌ Profile Extraction Error: {e}")
        st.stop()


# ════════════════════════════════════════════════════════════════════════════
# PIPELINE — GATE 2: PROFILE REVIEW / CONFIRM FORM
# ════════════════════════════════════════════════════════════════════════════
profile = st.session_state["candidate_profile"]

if not st.session_state.get("profile_confirmed", False):
    st.divider()
    st.subheader("👤 Review & Confirm Your Profile")
    st.caption("Review the AI-extracted information below, edit if needed, then confirm to continue.")

    with st.form("profile_edit_form"):
        edited_name = st.text_input("Name", value=profile.get("name", ""))

        skills_val    = profile.get("skills", [])
        initial_skills = ", ".join(skills_val) if isinstance(skills_val, list) else str(skills_val or "")
        edited_skills  = st.text_area("Skills (comma-separated)", value=initial_skills, height=100)

        certs_val = profile.get("certifications", [])
        if isinstance(certs_val, list):
            cert_items    = [c.get("name") if isinstance(c, dict) else str(c) for c in certs_val]
            initial_certs = ", ".join(cert_items)
        else:
            initial_certs = str(certs_val or "")
        edited_certs = st.text_area("Certifications (comma-separated)", value=initial_certs)

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            with st.expander("🎓 Education"):
                st.markdown(format_section_as_text(profile.get("education", []), "education"))
        with col_b:
            with st.expander("💼 Experience"):
                st.markdown(format_section_as_text(profile.get("experience", []), "experience"))
        with col_c:
            with st.expander("🚀 Projects"):
                st.markdown(format_section_as_text(profile.get("projects", []), "projects"))

        if st.form_submit_button("✅ Confirm & Continue", type="primary"):
            parsed_skills = [s.strip() for s in edited_skills.split(",") if s.strip()]
            parsed_certs  = [c.strip() for c in edited_certs.split(",")  if c.strip()]
            updated = dict(profile)
            updated["name"]           = edited_name.strip()
            updated["skills"]         = parsed_skills
            updated["certifications"] = parsed_certs
            st.session_state["candidate_profile"]  = updated
            st.session_state["profile_confirmed"]  = True
            st.session_state["match_results"]      = None
            st.session_state["roadmap_data"]       = None
            st.session_state["resume_suggestions"] = None
            st.rerun()

    st.stop()


# ── Confirmed profile shortcut variable (used throughout the pipeline below) ──
confirmed_profile = st.session_state["candidate_profile"]


# ════════════════════════════════════════════════════════════════════════════
# PIPELINE — LOAD VECTOR STORE (cached across reruns)
# ════════════════════════════════════════════════════════════════════════════
@st.cache_resource(show_spinner="Loading knowledge base index…")
def _load_index():
    return load_index()

try:
    index, chunks = _load_index()
except Exception as e:
    print(f"[app] Knowledge base index load error: {e}")
    st.error(f"❌ Knowledge Base Error: {e}")
    st.stop()


# ════════════════════════════════════════════════════════════════════════════
# PIPELINE — RUN MATCHING (once; cached in session_state)
# ════════════════════════════════════════════════════════════════════════════
if not st.session_state.get("match_results"):
    profile_skills = confirmed_profile.get("skills", [])
    profile_exp    = confirmed_profile.get("experience", [])
    profile_proj   = confirmed_profile.get("projects", [])
    profile_edu    = confirmed_profile.get("education", [])

    if not profile_skills and not profile_exp and not profile_proj and not profile_edu:
        st.error(
            "❌ Missing Profile Data: Your candidate profile has no skills, experience, projects, or "
            "education listed. Please click the sidebar **👤 Candidate Profile** page and use "
            "**Edit Profile** to add your details."
        )
        st.stop()

    try:
        with st.spinner("Identifying your top career matches…"):
            top_roles = identify_candidate_roles(confirmed_profile, index, chunks, top_n=3)

        if not top_roles:
            st.warning("⚠️ Could not identify matching roles from the knowledge base. Try enriching your skills section.")
            st.stop()

        match_results = []
        for role in top_roles:
            role_chunks = [
                c for c in chunks
                if c.get("metadata", {}).get("role", "").strip().lower() == role.strip().lower()
                and c.get("metadata", {}).get("document_type") == "role_profile"
            ]
            with st.spinner(f"Scoring match for **{role}**…"):
                req   = extract_role_requirements(role, role_chunks)
                score = calculate_match_score(
                    confirmed_profile,
                    req,
                    candidate_education=confirmed_profile.get("education"),
                    full_resume_text=resume_text,
                )
            match_results.append({
                "role":         role,
                "requirements": req,
                "score":        score,
            })

        match_results.sort(key=lambda r: r["score"]["overall_score"], reverse=True)
        st.session_state["match_results"] = match_results

    except Exception as e:
        print(f"[app] Career matching error: {e}")
        st.error(f"❌ Career Matching Error: {e}")
        st.stop()

match_results = st.session_state["match_results"]


# ── Aggregate missing skills (used by multiple pages) ───────────────────────
all_missing: dict = {}
for mr in match_results:
    for ms in mr["score"].get("missing_skills", []):
        skill = ms["skill"]
        if skill not in all_missing or (
            all_missing[skill]["priority"] == "medium" and ms["priority"] == "high"
        ):
            all_missing[skill] = ms
aggregated_missing       = list(all_missing.values())
top_missing_high_medium  = [m for m in aggregated_missing if m["priority"] in ("high", "medium")][:8]


# ════════════════════════════════════════════════════════════════════════════
# PIPELINE — GENERATE ROADMAP (once; cached in session_state)
# ════════════════════════════════════════════════════════════════════════════
if not st.session_state.get("roadmap_data"):
    try:
        with st.spinner("Generating your personalised learning roadmap…"):
            st.session_state["roadmap_data"] = generate_roadmap(
                confirmed_profile, top_missing_high_medium
            )
    except Exception as e:
        print(f"[app] Roadmap generation error: {e}")
        st.warning(f"⚠️ Roadmap Generation Notice: {e}")
        st.session_state["roadmap_data"] = {"roadmap": [], "interview_questions": []}

roadmap_data = st.session_state["roadmap_data"]


# ════════════════════════════════════════════════════════════════════════════
# PIPELINE — GENERATE RESUME SUGGESTIONS (once; cached in session_state)
# ════════════════════════════════════════════════════════════════════════════
if not st.session_state.get("resume_suggestions"):
    try:
        with st.spinner("Generating resume improvement suggestions…"):
            st.session_state["resume_suggestions"] = generate_resume_suggestions(
                confirmed_profile, top_missing_high_medium
            )
    except Exception as e:
        print(f"[app] Resume suggestions error: {e}")
        st.warning(f"⚠️ Resume Suggestions Notice: {e}")
        st.session_state["resume_suggestions"] = {"suggestions": []}

resume_suggestions = st.session_state["resume_suggestions"]


# ════════════════════════════════════════════════════════════════════════════
# DISPLAY — Route to the selected sidebar page
# All pipeline gates have passed by this point.
# ════════════════════════════════════════════════════════════════════════════
st.divider()

if selected_page == "📋 Overview":
    render_overview(match_results, aggregated_missing, confirmed_profile)

elif selected_page == "📄 Resume":
    render_resume_view(
        resume_text,
        word_count,
        uploaded_file.name if uploaded_file else "",
    )

elif selected_page == "👤 Candidate Profile":
    render_candidate_profile_page(confirmed_profile)

elif selected_page == "🏆 Career Matches":
    render_career_matches(match_results)

elif selected_page == "🔍 Skill Gaps":
    render_skill_gaps(match_results, aggregated_missing)

elif selected_page == "🗺️ Career Roadmap":
    render_career_roadmap(roadmap_data)

elif selected_page == "🚀 Projects":
    render_projects(confirmed_profile)

elif selected_page == "🎤 Interview Prep":
    render_interview_prep(roadmap_data)

elif selected_page == "📝 Resume Improvement":
    render_resume_improvement(resume_suggestions)

elif selected_page == "⚡ Job Readiness":
    render_job_readiness(match_results, aggregated_missing)

st.divider()
st.caption("CareerMatch AI · Analysis is illustrative only · Not a hiring or placement service.")
