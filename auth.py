"""
auth.py
=======
Authentication layer for CareerMatch AI.

Backend: Supabase Auth (email + password) + Supabase PostgreSQL (profiles table).
Frontend: Unchanged premium CareerMatch AI Login / Sign-Up UI.

Public API (called by app.py — signatures unchanged):
  run_auth_gate()      → checks session, renders Login/SignUp if needed, st.stop() if unauth
  render_user_badge()  → sidebar widget: name, email, Sign Out button

This module does NOT touch any RAG, FAISS, LLM, resume-parsing, or matching logic.
"""

from __future__ import annotations

import os
import re
import streamlit as st
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# ── Supabase client (singleton) ───────────────────────────────────────────────
_SUPABASE_URL: str = os.environ.get("SUPABASE_URL", "")
_SUPABASE_ANON_KEY: str = os.environ.get("SUPABASE_ANON_KEY", "")

if not _SUPABASE_URL or not _SUPABASE_ANON_KEY:
    raise EnvironmentError(
        "SUPABASE_URL and SUPABASE_ANON_KEY must be set in your .env file. "
        "Get them from Supabase Dashboard → Project Settings → API."
    )

_supabase: Client = create_client(_SUPABASE_URL, _SUPABASE_ANON_KEY)


# ── Premium CSS (identical to previous version — visual design unchanged) ─────
_AUTH_CSS = """
<style>
/* ── Force light theme for auth pages ── */
html, body, [data-testid="stAppViewContainer"], [data-testid="stApp"] {
    background-color: #f8fafc !important;
}

/* ── Hide Streamlit chrome on auth pages ── */
#MainMenu { visibility: hidden; }
footer    { visibility: hidden; }
header    { visibility: hidden; }

/* ── Auth card container ── */
.auth-card {
    background: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 16px;
    padding: 2.5rem 2.25rem 2rem;
    box-shadow: 0 4px 24px rgba(31, 59, 179, 0.07), 0 1px 4px rgba(0,0,0,0.04);
    max-width: 440px;
    margin: 0 auto;
}

/* ── Logo / brand area ── */
.auth-logo {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 0.35rem;
}
.auth-logo-icon {
    width: 38px;
    height: 38px;
    background: linear-gradient(135deg, #1f3bb3 0%, #3b63e8 100%);
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.25rem;
    color: #fff;
    flex-shrink: 0;
}
.auth-logo-name {
    font-size: 1.25rem;
    font-weight: 700;
    color: #0f172a;
    letter-spacing: -0.02em;
    font-family: 'Inter', system-ui, sans-serif;
}
.auth-logo-name span {
    color: #1f3bb3;
}
.auth-tagline {
    font-size: 0.875rem;
    color: #64748b;
    margin-bottom: 1.6rem;
    margin-top: 0.1rem;
    font-style: italic;
}
.auth-title {
    font-size: 1.35rem !important;
    font-weight: 700 !important;
    color: #0f172a !important;
    margin-bottom: 0.2rem !important;
    letter-spacing: -0.02em;
}
.auth-subtitle {
    font-size: 0.875rem;
    color: #64748b;
    margin-bottom: 1.5rem;
}

/* ── Override stAuth widget ── */
[data-testid="stForm"] {
    border: none !important;
    padding: 0 !important;
    background: transparent !important;
}

/* ── Input fields ── */
[data-testid="stTextInput"] > div > div > input {
    border: 1.5px solid #e2e8f0 !important;
    border-radius: 8px !important;
    padding: 0.55rem 0.85rem !important;
    font-size: 0.92rem !important;
    background: #fff !important;
    color: #0f172a !important;
    transition: border-color 0.15s ease !important;
}
[data-testid="stTextInput"] > div > div > input:focus {
    border-color: #1f3bb3 !important;
    box-shadow: 0 0 0 3px rgba(31, 59, 179, 0.12) !important;
    outline: none !important;
}
[data-testid="stTextInput"] label {
    font-size: 0.83rem !important;
    font-weight: 600 !important;
    color: #475569 !important;
    margin-bottom: 4px !important;
}

/* ── Primary submit button ── */
[data-testid="stFormSubmitButton"] > button,
[data-testid="stButton"] > button {
    background: linear-gradient(135deg, #1f3bb3 0%, #2d50d4 100%) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 0.92rem !important;
    padding: 10px 20px !important;
    width: 100% !important;
    transition: opacity 0.15s ease, transform 0.1s ease !important;
    letter-spacing: 0.01em !important;
    cursor: pointer !important;
}
[data-testid="stFormSubmitButton"] > button:hover,
[data-testid="stButton"] > button:hover {
    opacity: 0.92 !important;
    transform: translateY(-1px) !important;
}

/* ── Status messages ── */
[data-testid="stAlert"] {
    border-radius: 8px !important;
    font-size: 0.875rem !important;
}

/* ── Checkbox ── */
[data-testid="stCheckbox"] label p {
    font-size: 0.85rem !important;
    color: #475569 !important;
}

/* ── Link row ── */
.auth-link-row {
    text-align: center;
    margin-top: 1.2rem;
    font-size: 0.875rem;
    color: #64748b;
}
.auth-link-row a {
    color: #1f3bb3;
    font-weight: 600;
    text-decoration: none;
}
.auth-link-row a:hover { text-decoration: underline; }

/* ── Section separator ── */
.auth-sep {
    border: none;
    border-top: 1px solid #e2e8f0;
    margin: 1.2rem 0;
}
</style>
"""


# ── Email regex ───────────────────────────────────────────────────────────────
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def _valid_email(email: str) -> bool:
    return bool(_EMAIL_RE.match(email.strip()))


# ── Brand header HTML (unchanged from previous version) ──────────────────────
def _brand_html(subtitle: str, title: str) -> str:
    return f"""
    <div class="auth-logo">
        <div class="auth-logo-icon">🎯</div>
        <div class="auth-logo-name">CareerMatch <span>AI</span></div>
    </div>
    <div class="auth-tagline">Turn your resume into your career roadmap.</div>
    <div class="auth-title">{title}</div>
    <div class="auth-subtitle">{subtitle}</div>
    """


# ── Friendly error mapper ─────────────────────────────────────────────────────
def _friendly_error(raw: str) -> str:
    """Convert Supabase / GoTrue error messages into user-friendly text."""
    msg = raw.lower()
    if "invalid login credentials" in msg or "invalid_credentials" in msg:
        return "❌ Incorrect email or password. Please try again."
    if "email already registered" in msg or "user already registered" in msg:
        return "❌ An account with this email already exists. Please sign in instead."
    if "password should be at least" in msg:
        return "❌ Password is too short. Supabase requires at least 6 characters."
    if "unable to validate email" in msg or "invalid email" in msg:
        return "❌ Please enter a valid email address."
    if "email not confirmed" in msg:
        return "📧 Your email is not yet confirmed. Please check your inbox and click the confirmation link."
    if "network" in msg or "connection" in msg or "timeout" in msg:
        return "🌐 Network error. Please check your connection and try again."
    if "rate limit" in msg:
        return "⏳ Too many attempts. Please wait a moment and try again."
    # Fallback — never expose raw Supabase internals
    return "❌ Authentication error. Please try again."


# ── Session helpers ───────────────────────────────────────────────────────────
def _store_session(user) -> None:
    """Persist authenticated user data into Streamlit session state."""
    meta = user.user_metadata or {}
    st.session_state["sb_user_id"]   = user.id
    st.session_state["sb_email"]     = user.email
    st.session_state["sb_full_name"] = meta.get("full_name", "")
    st.session_state["authenticated"] = True


def _clear_session() -> None:
    """Wipe authentication state (called on logout or session expiry)."""
    for key in ["sb_user_id", "sb_email", "sb_full_name", "authenticated"]:
        st.session_state.pop(key, None)


def _is_authenticated() -> bool:
    return bool(st.session_state.get("authenticated"))


# ── Profile fetch / create ────────────────────────────────────────────────────
def _fetch_profile(user_id: str) -> dict:
    """Fetch the user's row from public.profiles. Returns {} on failure."""
    try:
        res = _supabase.table("profiles").select("*").eq("id", user_id).single().execute()
        return res.data or {}
    except Exception:
        return {}


def _upsert_profile(user_id: str, full_name: str, email: str) -> None:
    """Insert or update profile row. Silently swallows errors (trigger may have already created it)."""
    try:
        _supabase.table("profiles").upsert(
            {"id": user_id, "full_name": full_name, "email": email},
            on_conflict="id",
        ).execute()
    except Exception as exc:
        # Non-fatal: the trigger already creates the row; log but don't crash
        print(f"[auth] Profile upsert warning: {exc}")


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC API — signatures match the previous streamlit-authenticator version
# ══════════════════════════════════════════════════════════════════════════════

def run_auth_gate() -> Client:
    """
    Entry point called at the top of app.py.

    1. Injects premium CSS.
    2. If session already exists  → returns immediately (dashboard loads).
    3. If no session              → shows Login or Sign-Up page → st.stop().

    Returns the Supabase client so app.py can pass it to render_user_badge().
    """
    st.markdown(_AUTH_CSS, unsafe_allow_html=True)

    # ── Initialise auth mode ──────────────────────────────────────────────────
    if "auth_mode" not in st.session_state:
        st.session_state["auth_mode"] = "login"

    # ── Already authenticated (session survived rerun / refresh) ──────────────
    if _is_authenticated():
        return _supabase

    # ── Try to restore session from Supabase (handles cookie/token refresh) ──
    try:
        session_res = _supabase.auth.get_session()
        if session_res and session_res.user:
            _store_session(session_res.user)
            # Enrich full_name from profiles table if metadata is empty
            if not st.session_state.get("sb_full_name"):
                profile = _fetch_profile(session_res.user.id)
                st.session_state["sb_full_name"] = profile.get("full_name", "")
            return _supabase
    except Exception:
        pass  # No active session — fall through to login UI

    # ── Render centred auth card ──────────────────────────────────────────────
    _, col, _ = st.columns([1, 1.6, 1])
    with col:
        if st.session_state["auth_mode"] == "login":
            _render_login()
        else:
            _render_signup()

    # Still not authenticated → block dashboard
    if not _is_authenticated():
        st.stop()

    return _supabase


def render_user_badge(_client: Client = None) -> None:
    """
    Render the authenticated user's name, email, and Sign Out button
    at the bottom of the existing sidebar.

    Accepts the Supabase client (or None) for API compatibility with the
    previous version that accepted the stauth Authenticate instance.
    """
    full_name = st.session_state.get("sb_full_name", "")
    email     = st.session_state.get("sb_email", "")
    display   = full_name or email or "User"

    st.divider()
    st.markdown(
        f"""
        <div style="
            background:#f0f4ff;
            border:1px solid #c7d7f9;
            border-radius:10px;
            padding:10px 12px;
            margin-bottom:8px;
        ">
            <div style="font-size:0.82rem;font-weight:700;color:#1f3bb3;margin-bottom:2px;">
                👤 {display}
            </div>
            <div style="font-size:0.76rem;color:#64748b;word-break:break-all;">
                {email}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button("🚪 Sign Out", key="sidebar_logout", use_container_width=True):
        try:
            _supabase.auth.sign_out()
        except Exception:
            pass  # Sign out locally regardless
        _clear_session()
        # Also clear CareerMatch AI pipeline state so next user starts fresh
        for key in [
            "resume_text", "resume_word_count", "candidate_profile",
            "profile_confirmed", "match_results", "roadmap_data",
            "resume_suggestions", "current_file_name",
        ]:
            st.session_state.pop(key, None)
        st.session_state["auth_mode"] = "login"
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PRIVATE — Login page
# ══════════════════════════════════════════════════════════════════════════════

def _render_login() -> None:
    st.markdown(
        _brand_html("Welcome back — sign in to continue.", "Sign in to your account"),
        unsafe_allow_html=True,
    )
    st.markdown("<hr class='auth-sep'>", unsafe_allow_html=True)

    with st.form("login_form", clear_on_submit=False):
        email    = st.text_input("Email Address", placeholder="you@example.com")
        password = st.text_input("Password", type="password", placeholder="Your password")
        submitted = st.form_submit_button("Sign In", use_container_width=True)

    if submitted:
        _handle_login(email.strip(), password)

    st.caption("🔒 Your session is secured by Supabase Auth.")
    st.markdown("<hr class='auth-sep'>", unsafe_allow_html=True)

    if st.button("Create an account →", key="to_signup_btn", use_container_width=True):
        st.session_state["auth_mode"] = "signup"
        st.rerun()


def _handle_login(email: str, password: str) -> None:
    """Validate inputs then call Supabase sign-in."""
    if not email:
        st.error("❌ Email is required.")
        return
    if not _valid_email(email):
        st.error("❌ Please enter a valid email address.")
        return
    if not password:
        st.error("❌ Password is required.")
        return

    with st.spinner("Signing in…"):
        try:
            res = _supabase.auth.sign_in_with_password(
                {"email": email, "password": password}
            )
        except Exception as exc:
            st.error(_friendly_error(str(exc)))
            return

    if not res or not res.user:
        st.error("❌ Sign in failed. Please check your credentials.")
        return

    _store_session(res.user)

    # Fetch profile (enriches full_name if not in metadata)
    profile = _fetch_profile(res.user.id)
    if profile.get("full_name"):
        st.session_state["sb_full_name"] = profile["full_name"]

    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PRIVATE — Sign-Up page
# ══════════════════════════════════════════════════════════════════════════════

def _render_signup() -> None:
    st.markdown(
        _brand_html("Create a free account to get started.", "Create your account"),
        unsafe_allow_html=True,
    )
    st.markdown("<hr class='auth-sep'>", unsafe_allow_html=True)

    with st.form("signup_form", clear_on_submit=False):
        full_name  = st.text_input("Full Name", placeholder="e.g. Jane Smith")
        email      = st.text_input("Email Address", placeholder="you@example.com")
        password   = st.text_input(
            "Password",
            type="password",
            placeholder="At least 8 characters",
        )
        confirm_pw = st.text_input(
            "Confirm Password",
            type="password",
            placeholder="Re-enter your password",
        )
        submitted = st.form_submit_button("Create Account", use_container_width=True)

    if submitted:
        _handle_signup(full_name.strip(), email.strip(), password, confirm_pw)

    st.caption("🔒 Passwords are managed by Supabase Auth — never stored as plain text.")
    st.markdown("<hr class='auth-sep'>", unsafe_allow_html=True)

    if st.button("← Back to Sign In", key="to_login_btn", use_container_width=True):
        st.session_state["auth_mode"] = "login"
        st.rerun()


def _handle_signup(
    full_name: str, email: str, password: str, confirm_pw: str
) -> None:
    """Validate inputs, call Supabase sign-up, create profile row."""
    errors = _validate_signup_inputs(full_name, email, password, confirm_pw)
    if errors:
        for err in errors:
            st.error(err)
        return

    with st.spinner("Creating your account…"):
        try:
            res = _supabase.auth.sign_up(
                {
                    "email": email,
                    "password": password,
                    "options": {
                        "data": {"full_name": full_name}  # stored in raw_user_meta_data
                    },
                }
            )
        except Exception as exc:
            st.error(_friendly_error(str(exc)))
            return

    if not res or not res.user:
        st.error("❌ Registration failed. Please try again.")
        return

    user = res.user

    # If Supabase returns a session immediately (email confirmation disabled)
    # → log in straight away
    if res.session:
        _store_session(user)
        # The DB trigger auto-creates the profile, but upsert ensures full_name is set
        _upsert_profile(user.id, full_name, email)
        st.success(f"✅ Welcome, {full_name}! Your account has been created.")
        st.balloons()
        st.rerun()
    else:
        # Email confirmation is enabled — tell the user to check their inbox
        st.success(
            f"✅ Account created! We sent a confirmation email to **{email}**. "
            "Please click the link in that email to activate your account, then sign in here."
        )
        st.session_state["auth_mode"] = "login"


def _validate_signup_inputs(
    full_name: str, email: str, password: str, confirm_pw: str
) -> list[str]:
    errors: list[str] = []

    if not full_name:
        errors.append("❌ Full Name is required.")
    elif len(full_name) < 2:
        errors.append("❌ Full Name must be at least 2 characters.")

    if not email:
        errors.append("❌ Email is required.")
    elif not _valid_email(email):
        errors.append("❌ Please enter a valid email address (e.g. you@example.com).")

    if not password:
        errors.append("❌ Password is required.")
    elif len(password) < 8:
        errors.append("❌ Password must be at least 8 characters long.")
    elif not re.search(r"[A-Z]", password):
        errors.append("❌ Password must contain at least one uppercase letter.")
    elif not re.search(r"[0-9]", password):
        errors.append("❌ Password must contain at least one number.")

    if password and confirm_pw != password:
        errors.append("❌ Passwords do not match. Please re-enter your password.")

    return errors
