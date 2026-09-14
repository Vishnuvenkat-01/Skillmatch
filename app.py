import streamlit as st
from services.resume_parser import extract_resume_text
from services.profile_extractor import extract_candidate_profile
from services.vector_store import load_index
from services.rag_engine import identify_candidate_roles
from services.matcher import extract_role_requirements, calculate_match_score
from services.roadmap import generate_roadmap, generate_resume_suggestions

# ── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CareerMatch AI",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Minimal custom CSS ───────────────────────────────────────────────────────
st.markdown("""
<style>
.badge-high   { background:#ff4b4b22; color:#ff4b4b; border:1px solid #ff4b4b55;
                padding:2px 8px; border-radius:99px; font-size:.78rem; font-weight:600; }
.badge-medium { background:#ffa50022; color:#e07c00; border:1px solid #ffa50055;
                padding:2px 8px; border-radius:99px; font-size:.78rem; font-weight:600; }
.badge-beginner     { background:#0068c922; color:#0068c9; border:1px solid #0068c955;
                      padding:2px 8px; border-radius:99px; font-size:.78rem; font-weight:600; }
.badge-intermediate { background:#83368222; color:#833682; border:1px solid #83368255;
                      padding:2px 8px; border-radius:99px; font-size:.78rem; font-weight:600; }
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════════════════
# SECTION 1 – HEADER & RESUME UPLOAD
# ════════════════════════════════════════════════════════════════════════════
st.title("🎯 CareerMatch AI")
st.markdown("#### Understand where your resume fits — and what to learn next.")
st.caption(
    "🔒 This prototype does not permanently store uploaded resumes. "
    "Your resume is processed only for this session."
)
st.divider()

st.subheader("📄 Step 1 — Upload Your Resume")
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
            "current_file_name": uploaded_file.name,
            "resume_text": None,
            "candidate_profile": None,
            "profile_confirmed": False,
            "match_results": None,
            "roadmap_data": None,
            "resume_suggestions": None,
        })

if uploaded_file is None:
    st.session_state.update({
        "current_file_name": None,
        "resume_text": None,
        "candidate_profile": None,
        "profile_confirmed": False,
        "match_results": None,
        "roadmap_data": None,
        "resume_suggestions": None,
    })
    st.info("💡 Upload your resume above and check the consent box to get started.")
    st.stop()

if not consent:
    st.info("ℹ️ Please check the consent box above to process your uploaded resume.")
    st.stop()


# ── Extract raw resume text ──────────────────────────────────────────────────
if not st.session_state.get("resume_text"):
    try:
        with st.spinner("Extracting resume text…"):
            text, word_count = extract_resume_text(uploaded_file)
            st.session_state["resume_text"] = text
            st.session_state["resume_word_count"] = word_count
    except Exception as e:
        print(f"[app] Resume extraction error: {e}")
        st.error(f"❌ Resume Extraction Error: {e}")
        st.stop()

resume_text = st.session_state["resume_text"]
word_count = st.session_state.get("resume_word_count", len(resume_text.split()))

if word_count < 50:
    st.warning(
        f"⚠️ **Low Text Warning:** Only {word_count} words could be extracted from your resume. "
        "If your resume is a scanned document or image PDF, extraction may be incomplete. "
        "Consider uploading a text-based document for best results."
    )

st.success("✅ Resume text extracted successfully!")
with st.expander("View extracted text (for your review)"):
    st.text(resume_text)


# ── Extract candidate profile via LLM ───────────────────────────────────────
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


# ── Text formatting helper for profile sections ────────────────────────────────
def format_section_as_text(items, section_type="general") -> str:
    """
    Format a list of dicts or strings into clean, human-readable markdown text.
    Replaces raw JSON displays for Education, Experience, and Projects.
    """
    if not items:
        return "*None listed*"

    if isinstance(items, str):
        return items.strip() or "*None listed*"

    if not isinstance(items, list):
        return str(items)

    formatted_blocks = []
    for item in items:
        if isinstance(item, str):
            formatted_blocks.append(f"• {item}")
        elif isinstance(item, dict):
            if section_type == "education":
                degree = item.get("degree") or item.get("title") or item.get("field") or ""
                institution = item.get("institution") or item.get("university") or item.get("school") or ""
                year = item.get("year") or item.get("dates") or item.get("duration") or ""

                parts = []
                if degree:
                    parts.append(f"**{degree}**")
                if institution:
                    parts.append(f"*{institution}*")
                if year:
                    parts.append(f"({year})")

                line = " - ".join(parts) if parts else ", ".join([f"{k.replace('_', ' ').title()}: {v}" for k, v in item.items() if v])
                formatted_blocks.append(f"• {line}")

            elif section_type == "experience":
                title = item.get("title") or item.get("role") or item.get("position") or ""
                company = item.get("company") or item.get("organization") or ""
                duration = item.get("duration") or item.get("dates") or item.get("year") or ""
                desc = item.get("description") or item.get("responsibilities") or ""

                header_parts = []
                if title:
                    header_parts.append(f"**{title}**")
                if company:
                    header_parts.append(f"*{company}*")
                if duration:
                    header_parts.append(f"({duration})")

                header = " | ".join(header_parts) if header_parts else ", ".join([f"{k.replace('_', ' ').title()}: {v}" for k, v in item.items() if k != "description" and v])
                block = f"• {header}"
                if desc:
                    if isinstance(desc, list):
                        for d in desc:
                            block += f"\n  - {d}"
                    else:
                        block += f"\n  - {desc}"
                formatted_blocks.append(block)

            elif section_type == "projects":
                name = item.get("name") or item.get("title") or ""
                desc = item.get("description") or item.get("summary") or ""
                tech = item.get("tech_stack") or item.get("technologies") or item.get("skills") or ""

                parts = []
                if name:
                    parts.append(f"**{name}**")

                header = " ".join(parts) if parts else ", ".join([f"{k.replace('_', ' ').title()}: {v}" for k, v in item.items() if k != "description" and v])
                block = f"• {header}"
                if desc:
                    block += f"\n  - {desc}"
                if tech:
                    tech_str = ", ".join(tech) if isinstance(tech, list) else str(tech)
                    block += f"\n  - *Tech:* {tech_str}"
                formatted_blocks.append(block)
            else:
                fields = [f"**{k.replace('_', ' ').title()}:** {v}" for k, v in item.items() if v]
                formatted_blocks.append("• " + " | ".join(fields))
        else:
            formatted_blocks.append(f"• {str(item)}")

    return "\n\n".join(formatted_blocks)


# ════════════════════════════════════════════════════════════════════════════
# SECTION 2 – CANDIDATE PROFILE REVIEW / EDIT GATE
# ════════════════════════════════════════════════════════════════════════════
st.divider()
st.subheader("👤 Step 2 — Review & Confirm Your Profile")

profile = st.session_state["candidate_profile"]

if not st.session_state.get("profile_confirmed", False):
    st.caption("Review the AI-extracted information below, edit if needed, then confirm to continue.")

    with st.form("profile_edit_form"):
        edited_name = st.text_input("Name", value=profile.get("name", ""))

        skills_val = profile.get("skills", [])
        initial_skills = ", ".join(skills_val) if isinstance(skills_val, list) else str(skills_val or "")
        edited_skills = st.text_area("Skills (comma-separated)", value=initial_skills, height=100)

        certs_val = profile.get("certifications", [])
        if isinstance(certs_val, list):
            cert_items = [c.get("name") if isinstance(c, dict) else str(c) for c in certs_val]
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

# Show compact confirmed profile summary
confirmed_profile = st.session_state["candidate_profile"]
with st.expander(f"✅ Profile confirmed — {confirmed_profile.get('name') or 'Candidate'}", expanded=False):
    skills_list = confirmed_profile.get("skills", [])
    st.markdown(f"**Skills:** {', '.join(skills_list) if skills_list else '*None listed*'}")
    certs_list = confirmed_profile.get("certifications", [])
    st.markdown(f"**Certifications:** {', '.join(certs_list) if certs_list else '*None listed*'}")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**Education**")
        st.markdown(format_section_as_text(confirmed_profile.get("education", []), "education"))
    with col2:
        st.markdown("**Experience**")
        st.markdown(format_section_as_text(confirmed_profile.get("experience", []), "experience"))
    with col3:
        st.markdown("**Projects**")
        st.markdown(format_section_as_text(confirmed_profile.get("projects", []), "projects"))
    if st.button("✏️ Edit Profile"):
        st.session_state["profile_confirmed"]  = False
        st.session_state["match_results"]      = None
        st.session_state["roadmap_data"]       = None
        st.session_state["resume_suggestions"] = None
        st.rerun()


# ════════════════════════════════════════════════════════════════════════════
# LOAD VECTOR STORE (cached across reruns via st.cache_resource)
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
# RUN MATCHING PIPELINE (once; cached in session_state)
# ════════════════════════════════════════════════════════════════════════════
if not st.session_state.get("match_results"):
    # Validate essential profile fields before proceeding to matching
    profile_skills = confirmed_profile.get("skills", [])
    profile_exp = confirmed_profile.get("experience", [])
    profile_proj = confirmed_profile.get("projects", [])
    profile_edu = confirmed_profile.get("education", [])

    if not profile_skills and not profile_exp and not profile_proj and not profile_edu:
        st.error(
            "❌ Missing Profile Data: Your candidate profile has no skills, experience, projects, or education listed. "
            "Please click '✏️ Edit Profile' above to add your details before running career matching."
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
                req = extract_role_requirements(role, role_chunks)
                score = calculate_match_score(
                    confirmed_profile,
                    req,
                    candidate_education=confirmed_profile.get("education"),
                    full_resume_text=resume_text,
                )
            match_results.append({
                "role": role,
                "requirements": req,
                "score": score,
            })

        match_results.sort(key=lambda r: r["score"]["overall_score"], reverse=True)
        st.session_state["match_results"] = match_results

    except Exception as e:
        print(f"[app] Career matching error: {e}")
        st.error(f"❌ Career Matching Error: {e}")
        st.stop()

match_results = st.session_state["match_results"]

# Aggregate all missing skills across all roles for roadmap & resume advice
all_missing: dict = {}
for mr in match_results:
    for ms in mr["score"].get("missing_skills", []):
        skill = ms["skill"]
        if skill not in all_missing or (all_missing[skill]["priority"] == "medium" and ms["priority"] == "high"):
            all_missing[skill] = ms
aggregated_missing = list(all_missing.values())
top_missing_high_medium = [m for m in aggregated_missing if m["priority"] in ("high", "medium")][:8]


# ════════════════════════════════════════════════════════════════════════════
# SECTION 3 – TOP 3 CAREER MATCHES
# ════════════════════════════════════════════════════════════════════════════
st.divider()
st.subheader("🏆 Step 3 — Top 3 Career Matches")
st.caption("Estimated compatibility score — not a hiring prediction.")

cols = st.columns(len(match_results))
for i, mr in enumerate(match_results):
    overall = mr["score"]["overall_score"]
    with cols[i]:
        st.markdown(f"### {mr['role']}")
        st.progress(int(overall) / 100)
        st.metric(label="Match Score", value=f"{overall:.1f}%")


# ════════════════════════════════════════════════════════════════════════════
# SECTION 4 – SKILL GAP ANALYSIS
# ════════════════════════════════════════════════════════════════════════════
st.divider()
st.subheader("🔍 Step 4 — Skill Gap Analysis")

for mr in match_results:
    sc = mr["score"]
    with st.expander(f"**{mr['role']}** — Skill Gap Detail", expanded=(mr == match_results[0])):
        bd = sc["breakdown"]
        st.markdown("**Score Breakdown**")
        breakdown_data = {
            "Component": [
                "Required Skills (50%)",
                "Preferred Skills (20%)",
                "Education (15%)",
                "Project Relevance (10%)",
                "Experience (5%)",
            ],
            "Score": [
                f"{bd['required_skills_score']:.1f} / 50",
                f"{bd['preferred_skills_score']:.1f} / 20",
                f"{bd['education_score']:.1f} / 15",
                f"{bd['project_score']:.1f} / 10",
                f"{bd['experience_score']:.1f} / 5",
            ],
        }
        st.table(breakdown_data)

        col_r, col_p = st.columns(2)
        with col_r:
            st.markdown("**Required Skills**")
            for s in sc.get("matched_required_skills", []):
                st.markdown(f"✅ {s['skill']}")
            for s in sc.get("missing_required_skills", []):
                st.markdown(f"🔴 {s['skill']}")
        with col_p:
            st.markdown("**Preferred Skills**")
            for s in sc.get("matched_preferred_skills", []):
                st.markdown(f"✅ {s['skill']}")
            for s in sc.get("missing_preferred_skills", []):
                st.markdown(f"🟡 {s['skill']}")


# ════════════════════════════════════════════════════════════════════════════
# SECTION 5 – EXPLAINABLE MATCH SCORE
# ════════════════════════════════════════════════════════════════════════════
st.divider()
st.subheader("📊 Step 5 — Explainable Match Score")
st.caption("Estimated compatibility score — not a hiring prediction.")

for mr in match_results:
    sc = mr["score"]
    bd = sc["breakdown"]
    with st.expander(f"**{mr['role']}** — Full Breakdown ({sc['overall_score']:.1f}%)", expanded=False):
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Required Skills", f"{bd['required_skills_score']:.1f}/50")
        c2.metric("Preferred Skills", f"{bd['preferred_skills_score']:.1f}/20")
        c3.metric("Education",        f"{bd['education_score']:.1f}/15")
        c4.metric("Projects",         f"{bd['project_score']:.1f}/10")
        c5.metric("Experience",       f"{bd['experience_score']:.1f}/5")

        missing_skills = sc.get("missing_skills", [])
        if missing_skills:
            st.markdown("**Priority Gaps**")
            for ms in missing_skills:
                badge_cls = "badge-high" if ms["priority"] == "high" else "badge-medium"
                badge_lbl = ms["priority"].upper()
                st.markdown(
                    f"<span class='{badge_cls}'>{badge_lbl}</span> &nbsp; {ms['skill']}",
                    unsafe_allow_html=True,
                )
        else:
            st.success("No significant skill gaps found for this role!")


# ════════════════════════════════════════════════════════════════════════════
# GENERATE ROADMAP (once; cached in session_state)
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
# SECTION 6 – PREPARATION ROADMAP
# ════════════════════════════════════════════════════════════════════════════
st.divider()
st.subheader("🗺️ Step 6 — Preparation Roadmap")
st.caption(
    "A suggested 2–4 week learning plan based on your skill gaps. "
    "Completing this roadmap does not guarantee any interview or hiring outcome."
)

roadmap_items = roadmap_data.get("roadmap", [])
if roadmap_items:
    for item in roadmap_items:
        priority     = item.get("priority", "medium")
        difficulty   = item.get("difficulty", "beginner").lower()
        skill        = item.get("skill", "")
        project_idea = item.get("project_idea", "")
        resource     = item.get("resource_type", "")
        weeks        = item.get("estimated_weeks", 1)

        badge_p = (
            "<span class='badge-high'>HIGH</span>"
            if priority == "high"
            else "<span class='badge-medium'>MEDIUM</span>"
        )
        badge_d = (
            "<span class='badge-beginner'>Beginner</span>"
            if difficulty == "beginner"
            else "<span class='badge-intermediate'>Intermediate</span>"
        )

        with st.container():
            st.markdown(
                f"{badge_p} {badge_d} &nbsp; **{skill}** &nbsp; ⏱ {weeks} week{'s' if weeks != 1 else ''}",
                unsafe_allow_html=True,
            )
            col_proj, col_res = st.columns([3, 2])
            with col_proj:
                st.markdown(f"💡 **Project Idea:** {project_idea}")
            with col_res:
                st.markdown(f"📚 **Resource Type:** {resource}")
            st.markdown("---")
else:
    st.info("No roadmap items generated. Your skill set may already be a strong fit for your matched roles!")


# ════════════════════════════════════════════════════════════════════════════
# SECTION 7 – INTERVIEW PREPARATION
# ════════════════════════════════════════════════════════════════════════════
st.divider()
st.subheader("🎤 Step 7 — Interview Preparation")

interview_questions = roadmap_data.get("interview_questions", [])
if interview_questions:
    grouped: dict = {}
    for q in interview_questions:
        skill = q.get("related_skill", "General")
        grouped.setdefault(skill, []).append(q)

    for skill, questions in grouped.items():
        with st.expander(f"**{skill}** ({len(questions)} question{'s' if len(questions) > 1 else ''})", expanded=False):
            for q in questions:
                q_type = q.get("type", "conceptual").lower()
                label  = "🧠 Conceptual" if q_type == "conceptual" else "🔧 Applied"
                st.markdown(f"{label} &nbsp; — &nbsp; {q.get('question', '')}")
else:
    st.info("No interview questions generated.")


# ════════════════════════════════════════════════════════════════════════════
# GENERATE RESUME SUGGESTIONS (once; cached in session_state)
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
# SECTION 8 – RESUME IMPROVEMENT
# ════════════════════════════════════════════════════════════════════════════
st.divider()
st.subheader("📝 Step 8 — Resume Improvement Suggestions")
st.caption(
    "Suggestions are limited to wording, structure, and honest next-step advice. "
    "No skills or achievements will be added that aren't already on your resume."
)

suggestions = resume_suggestions.get("suggestions", [])
if suggestions:
    for i, suggestion in enumerate(suggestions, 1):
        st.markdown(f"**{i}.** {suggestion}")
else:
    st.info("No resume suggestions generated.")


# ════════════════════════════════════════════════════════════════════════════
# SECTION 9 – JOB READINESS SCORE
# ════════════════════════════════════════════════════════════════════════════
st.divider()
st.subheader("⚡ Step 9 — Job Readiness Score")
st.caption("Estimated compatibility score — not a hiring prediction.")

if match_results:
    best = match_results[0]
    best_score = best["score"]["overall_score"]

    if best_score >= 80:
        label, icon = "High Readiness",     "🟢"
    elif best_score >= 55:
        label, icon = "Moderate Readiness", "🟡"
    else:
        label, icon = "Early Stage",        "🔴"

    col_left, col_right = st.columns([1, 2])
    with col_left:
        st.metric(
            label=f"{icon} {label}",
            value=f"{best_score:.1f}%",
            help="Based on your best-matched role. Not a hiring prediction.",
        )
        st.progress(int(best_score) / 100)
    with col_right:
        high_gaps   = sum(1 for m in aggregated_missing if m["priority"] == "high")
        medium_gaps = sum(1 for m in aggregated_missing if m["priority"] == "medium")
        st.markdown(f"- 🔴 **High-priority gaps:** {high_gaps}")
        st.markdown(f"- 🟡 **Medium-priority gaps:** {medium_gaps}")
        st.markdown(f"- 🏆 **Best matched role:** {best['role']}")

        if high_gaps == 0 and medium_gaps <= 2:
            st.success("You're nearly job-ready! Focus on portfolio polish.")
        elif high_gaps <= 3:
            st.info("Close the high-priority gaps and you'll be in a strong position.")
        else:
            st.warning("Focus on core required skills first — aim for high-priority items in the roadmap.")

st.divider()
st.caption("CareerMatch AI · Analysis is illustrative only · Not a hiring or placement service.")
