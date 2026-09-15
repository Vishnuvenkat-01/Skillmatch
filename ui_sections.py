"""
ui_sections.py
==============
Pure display functions for CareerMatch AI.
Each function only calls st.* display APIs.
No service calls, no session-state writes (except render_candidate_profile_page
which owns the "Edit Profile" button action).
"""
import streamlit as st
from ui_helpers import format_section_as_text


# ─────────────────────────────────────────────────────────────
# Overview
# ─────────────────────────────────────────────────────────────
def render_overview(match_results: list, aggregated_missing: list, confirmed_profile: dict):
    """Dashboard summary page shown after pipeline completes."""
    st.title("Overview")
    name = confirmed_profile.get("name") or "Candidate"
    st.caption(f"Welcome, **{name}** — your personalized career intelligence dashboard.")
    st.divider()

    if not match_results:
        st.info("No match results available yet.")
        return

    best = match_results[0]
    best_score = best["score"]["overall_score"]

    if best_score >= 80:
        label, icon = "High Readiness", "🟢"
    elif best_score >= 55:
        label, icon = "Moderate Readiness", "🟡"
    else:
        label, icon = "Early Stage", "🔴"

    high_gaps   = sum(1 for m in aggregated_missing if m["priority"] == "high")
    medium_gaps = sum(1 for m in aggregated_missing if m["priority"] == "medium")

    # Top Command Center Metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Top Career Match", best["role"])
    c2.metric("Job Readiness", f"{best_score:.1f}%", help=f"Status: {label}")
    c3.metric("High-Priority Gaps", high_gaps)
    c4.metric("Medium-Priority Gaps", medium_gaps)

    st.divider()

    # Top Career Matches Cards
    st.subheader("Top Career Matches")
    cols = st.columns(len(match_results))
    for i, mr in enumerate(match_results):
        overall = mr["score"]["overall_score"]
        sc = mr["score"]
        matched_req = [s["skill"] for s in sc.get("matched_required_skills", [])[:3]]
        missing_req = [s["skill"] for s in sc.get("missing_required_skills", [])[:3]]

        with cols[i]:
            st.markdown(f"### {mr['role']}")
            st.progress(int(overall) / 100)
            st.metric("Match Score", f"{overall:.1f}%")
            if matched_req:
                st.markdown("**Matching:** " + ", ".join(f"`{s}`" for s in matched_req))
            if missing_req:
                st.markdown("**Missing:** " + ", ".join(f"`{s}`" for s in missing_req))

    st.divider()

    # Top Skill Gaps Summary
    st.subheader("Top Skill Gaps")
    if aggregated_missing:
        gap_cols = st.columns(min(len(aggregated_missing[:4]), 4))
        for idx, gap in enumerate(aggregated_missing[:4]):
            p = gap["priority"]
            badge_cls = "badge-high" if p == "high" else "badge-medium"
            with gap_cols[idx % 4]:
                st.markdown(
                    f"<span class='{badge_cls}'>{p.upper()}</span> &nbsp; **{gap['skill']}**",
                    unsafe_allow_html=True,
                )
    else:
        st.success("No critical skill gaps identified!")

    st.divider()

    # Recommended Next Actions
    st.subheader("Next Actions")
    if high_gaps == 0 and medium_gaps <= 2:
        st.success("🎉 You're nearly job-ready! Use the sidebar to review your roadmap and polish your portfolio.")
    elif high_gaps <= 3:
        st.info("📚 Focus on closing the high-priority skill gaps listed in **Skill Gaps** tab to boost your score.")
    else:
        st.warning("🎯 Focus on core required skills first — check your **Career Roadmap** in the sidebar.")


# ─────────────────────────────────────────────────────────────
# Resume
# ─────────────────────────────────────────────────────────────
def render_resume_view(resume_text: str, word_count: int, filename: str = ""):
    """Shows the extracted resume text."""
    st.title("Resume")
    if filename:
        st.caption(f"Uploaded file: **{filename}**")
    st.divider()

    if word_count < 50:
        st.warning(
            f"⚠️ Only **{word_count}** words were extracted. "
            "If your resume is a scanned or image PDF, text extraction may be incomplete. "
            "Consider uploading a text-based PDF or DOCX for best results."
        )
    else:
        st.success(f"✅ **{word_count}** words extracted successfully.")

    st.subheader("Extracted Text")
    st.text(resume_text)


# ─────────────────────────────────────────────────────────────
# Candidate Profile
# ─────────────────────────────────────────────────────────────
def render_candidate_profile_page(confirmed_profile: dict):
    """
    Full candidate profile display page.
    Includes the 'Edit Profile' button which resets state and triggers st.rerun().
    """
    st.title("Candidate Profile")
    st.caption("Your AI-extracted and confirmed profile. Use **Edit Profile** to make changes.")
    st.divider()

    name = confirmed_profile.get("name") or "Candidate"
    st.subheader(name)

    # Contact row
    email    = confirmed_profile.get("email", "")
    phone    = confirmed_profile.get("phone", "")
    location = confirmed_profile.get("location", "")
    contact_parts = []
    if email:    contact_parts.append(f"📧 {email}")
    if phone:    contact_parts.append(f"📞 {phone}")
    if location: contact_parts.append(f"📍 {location}")
    if contact_parts:
        st.markdown("  ·  ".join(contact_parts))

    summary = confirmed_profile.get("summary", "")
    if summary:
        st.markdown(f"> {summary}")

    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Skills")
        skills_list = confirmed_profile.get("skills", [])
        if skills_list:
            # Render as pills-style badges
            st.markdown(
                " ".join(f"`{s}`" for s in skills_list)
            )
        else:
            st.caption("*None listed*")

        st.subheader("Certifications")
        certs = confirmed_profile.get("certifications", [])
        if certs:
            if isinstance(certs, list):
                for c in certs:
                    st.markdown(f"• {c}")
            else:
                st.markdown(str(certs))
        else:
            st.caption("*None listed*")

        langs = confirmed_profile.get("languages", [])
        if langs:
            st.subheader("Languages")
            st.markdown(", ".join(langs) if isinstance(langs, list) else str(langs))

    with col2:
        st.subheader("Education")
        st.markdown(format_section_as_text(confirmed_profile.get("education", []), "education"))

        st.subheader("Experience")
        st.markdown(format_section_as_text(confirmed_profile.get("experience", []), "experience"))

    st.divider()
    if st.button("✏️ Edit Profile", type="secondary"):
        st.session_state["profile_confirmed"]  = False
        st.session_state["match_results"]      = None
        st.session_state["roadmap_data"]       = None
        st.session_state["resume_suggestions"] = None
        st.rerun()


# ─────────────────────────────────────────────────────────────
# Career Matches
# ─────────────────────────────────────────────────────────────
def render_career_matches(match_results: list):
    """Top-N career match score cards."""
    st.title("Career Matches")
    st.caption("Estimated compatibility score — not a hiring prediction.")
    st.divider()

    cols = st.columns(len(match_results))
    for i, mr in enumerate(match_results):
        overall = mr["score"]["overall_score"]
        with cols[i]:
            st.markdown(f"### {mr['role']}")
            st.progress(int(overall) / 100)
            st.metric(label="Match Score", value=f"{overall:.1f}%")


# ─────────────────────────────────────────────────────────────
# Skill Gaps  (combines old Sections 4 + 5)
# ─────────────────────────────────────────────────────────────
def render_skill_gaps(match_results: list, aggregated_missing: list):
    """Skill gap detail + explainable score breakdown."""
    st.title("Skill Gap Analysis")
    st.divider()

    # ── Per-role gap table ──────────────────────────────────
    for mr in match_results:
        sc = mr["score"]
        with st.expander(
            f"**{mr['role']}** — Skill Gap Detail",
            expanded=(mr == match_results[0]),
        ):
            bd = sc["breakdown"]
            st.markdown("**Score Breakdown**")
            st.table({
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
            })

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

    # ── Explainable score (old Section 5) ─────────────────
    st.divider()
    st.subheader("Explainable Match Score")
    st.caption("Estimated compatibility score — not a hiring prediction.")

    for mr in match_results:
        sc = mr["score"]
        bd = sc["breakdown"]
        with st.expander(
            f"**{mr['role']}** — Full Breakdown ({sc['overall_score']:.1f}%)",
            expanded=False,
        ):
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


# ─────────────────────────────────────────────────────────────
# Career Roadmap
# ─────────────────────────────────────────────────────────────
def render_career_roadmap(roadmap_data: dict):
    """2–4 week personalised learning roadmap."""
    st.title("Career Roadmap")
    st.caption(
        "A suggested 2–4 week learning plan based on your skill gaps. "
        "Completing this roadmap does not guarantee any interview or hiring outcome."
    )
    st.divider()

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
                    f"{badge_p} {badge_d} &nbsp; **{skill}** &nbsp; "
                    f"⏱ {weeks} week{'s' if weeks != 1 else ''}",
                    unsafe_allow_html=True,
                )
                col_proj, col_res = st.columns([3, 2])
                with col_proj:
                    st.markdown(f"💡 **Project Idea:** {project_idea}")
                with col_res:
                    st.markdown(f"📚 **Resource Type:** {resource}")
                st.markdown("---")
    else:
        st.info(
            "No roadmap items generated. "
            "Your skill set may already be a strong fit for your matched roles!"
        )


# ─────────────────────────────────────────────────────────────
# Projects
# ─────────────────────────────────────────────────────────────
def render_projects(confirmed_profile: dict):
    """Dedicated Projects page — shows projects from the candidate profile."""
    st.title("Projects")
    st.caption("Projects extracted from your resume.")
    st.divider()

    projects = confirmed_profile.get("projects", [])
    if projects:
        st.markdown(format_section_as_text(projects, "projects"))
    else:
        st.info(
            "No projects were found in your resume profile. "
            "If you have projects, try editing your profile and adding them to the Skills or Projects section."
        )


# ─────────────────────────────────────────────────────────────
# Interview Prep
# ─────────────────────────────────────────────────────────────
def render_interview_prep(roadmap_data: dict):
    """Interview questions grouped by skill."""
    st.title("Interview Preparation")
    st.divider()

    interview_questions = roadmap_data.get("interview_questions", [])
    if interview_questions:
        grouped: dict = {}
        for q in interview_questions:
            skill = q.get("related_skill", "General")
            grouped.setdefault(skill, []).append(q)

        for skill, questions in grouped.items():
            n = len(questions)
            with st.expander(
                f"**{skill}** ({n} question{'s' if n > 1 else ''})",
                expanded=False,
            ):
                for q in questions:
                    q_type = q.get("type", "conceptual").lower()
                    label  = "🧠 Conceptual" if q_type == "conceptual" else "🔧 Applied"
                    st.markdown(f"{label} &nbsp; — &nbsp; {q.get('question', '')}")
    else:
        st.info("No interview questions generated.")


# ─────────────────────────────────────────────────────────────
# Resume Improvement
# ─────────────────────────────────────────────────────────────
def render_resume_improvement(resume_suggestions: dict):
    """AI-generated resume improvement suggestions."""
    st.title("Resume Improvement")
    st.caption(
        "Suggestions are limited to wording, structure, and honest next-step advice. "
        "No skills or achievements will be added that aren't already on your resume."
    )
    st.divider()

    suggestions = resume_suggestions.get("suggestions", [])
    if suggestions:
        for i, suggestion in enumerate(suggestions, 1):
            st.markdown(f"**{i}.** {suggestion}")
    else:
        st.info("No resume suggestions generated.")


# ─────────────────────────────────────────────────────────────
# Job Readiness
# ─────────────────────────────────────────────────────────────
def render_job_readiness(match_results: list, aggregated_missing: list):
    """Overall job readiness score and gap summary."""
    st.title("Job Readiness")
    st.caption("Estimated compatibility score — not a hiring prediction.")
    st.divider()

    if not match_results:
        st.info("No results available.")
        return

    best       = match_results[0]
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
