"""SEP AI Coach — Streamlit app with auth, onboarding, dashboard, and per-scenario chat."""

import os

import streamlit as st
from dotenv import load_dotenv
import users as auth
from prompts import build_system_prompt, SESSION_SUMMARY_PROMPT

# ---------------------------------------------------------------------------
# Page config — must be the very first Streamlit call
# ---------------------------------------------------------------------------

st.set_page_config(page_title="SEP AI Coach", page_icon="🎓", layout="centered")

# ---------------------------------------------------------------------------
# Load secrets — safe to access st.secrets after set_page_config
# ---------------------------------------------------------------------------

load_dotenv()

for _key in ["ANTHROPIC_API_KEY", "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]:
    try:
        os.environ.setdefault(_key, str(st.secrets[_key]))
    except Exception:
        pass

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_KEY = os.getenv("OPENAI_API_KEY")

PROVIDER = os.getenv("PROVIDER", "").lower()
if not PROVIDER:
    if ANTHROPIC_KEY:
        PROVIDER = "anthropic"
    elif OPENAI_KEY:
        PROVIDER = "openai"

DEFAULT_MODELS = {"anthropic": "claude-opus-4-7", "openai": "gpt-4o-mini"}
MODEL = os.getenv("MODEL") or DEFAULT_MODELS.get(PROVIDER, "")

SCENARIOS = [
    {"key": "interview", "icon": "🎯", "title": "Interview Prep",
     "description": "Practice mock questions and get real-time feedback"},
    {"key": "inbox",     "icon": "📥", "title": "Inbox Reset",
     "description": "Build a system to tame your overloaded inbox"},
    {"key": "email",     "icon": "✉️",  "title": "Email Writing",
     "description": "Draft professional emails that make the right impression"},
    {"key": "conflict",  "icon": "🤝", "title": "Workplace Conflict",
     "description": "Think through tense situations with clarity"},
]

SCENARIO_ICONS = {s["key"]: s["icon"] for s in SCENARIOS}
SCENARIO_TITLES = {s["key"]: s["title"] for s in SCENARIOS}


# ---------------------------------------------------------------------------
# Streaming helpers
# ---------------------------------------------------------------------------

def stream_anthropic(messages, system_prompt):
    from anthropic import Anthropic
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    with client.messages.stream(
        model=MODEL, max_tokens=2048, system=system_prompt, messages=messages,
    ) as stream:
        yield from stream.text_stream


def stream_openai(messages, system_prompt):
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    stream = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": system_prompt}, *messages],
        temperature=0.7, stream=True,
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


def stream_reply(messages, system_prompt):
    if PROVIDER == "anthropic":
        return stream_anthropic(messages, system_prompt)
    if PROVIDER == "openai":
        return stream_openai(messages, system_prompt)
    raise RuntimeError(f"Unsupported provider: {PROVIDER!r}")


def call_anthropic(messages, system_prompt) -> str:
    from anthropic import Anthropic
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    response = client.messages.create(
        model=MODEL, max_tokens=512, system=system_prompt, messages=messages,
    )
    return response.content[0].text


def call_openai(messages, system_prompt) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": system_prompt}, *messages],
        temperature=0.3,
    )
    return response.choices[0].message.content


def call_llm(messages, system_prompt) -> str:
    """Non-streaming LLM call used for session summaries."""
    if PROVIDER == "anthropic":
        return call_anthropic(messages, system_prompt)
    if PROVIDER == "openai":
        return call_openai(messages, system_prompt)
    raise RuntimeError(f"Unsupported provider: {PROVIDER!r}")


# ---------------------------------------------------------------------------
# Session state init
# ---------------------------------------------------------------------------

def init_state():
    defaults = {
        "user": None,
        "active_scenario": None,
        "chat_histories": {},
        "profile": None,
        "profile_checked": False,
        "session_notes": [],
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

    # Load profile + session notes from DB once per login
    if st.session_state.user and not st.session_state.profile_checked:
        st.session_state.profile = auth.get_profile(st.session_state.user)
        st.session_state.session_notes = auth.get_session_notes(st.session_state.user, limit=3)
        st.session_state.profile_checked = True


# ---------------------------------------------------------------------------
# Session summary helper
# ---------------------------------------------------------------------------

def maybe_save_session_summary(scenario_key: str):
    """If the conversation is long enough, generate and save a summary."""
    messages = st.session_state.chat_histories.get(scenario_key, [])
    if len(messages) < 4:
        return
    with st.spinner("Saving session notes..."):
        try:
            summary = call_llm(
                messages + [{"role": "user", "content": SESSION_SUMMARY_PROMPT}],
                system_prompt="You are a concise note-taker summarizing a coaching session.",
            )
            auth.save_session_note(st.session_state.user, scenario_key, summary)
            # Refresh in-memory notes
            st.session_state.session_notes = auth.get_session_notes(st.session_state.user, limit=3)
        except Exception:
            pass  # Never block navigation on a summary failure


# ---------------------------------------------------------------------------
# Auth screen
# ---------------------------------------------------------------------------

def render_auth():
    st.title("SEP AI Coach 🎓")
    st.markdown("Your personal coach for early-career challenges.")
    st.markdown("---")

    tab_login, tab_signup = st.tabs(["Log In", "Sign Up"])

    with tab_login:
        st.markdown("#### Welcome back")
        username = st.text_input("Username", key="login_user")
        password = st.text_input("Password", type="password", key="login_pass")
        if st.button("Log In", use_container_width=True, key="btn_login"):
            ok, err = auth.login(username, password)
            if ok:
                st.session_state.user = username
                st.rerun()
            else:
                st.error(err)

    with tab_signup:
        st.markdown("#### Create your account")
        username = st.text_input("Choose a username", key="signup_user")
        password = st.text_input("Choose a password", type="password", key="signup_pass")
        if st.button("Sign Up", use_container_width=True, key="btn_signup"):
            ok, err = auth.register(username, password)
            if ok:
                st.session_state.user = username
                st.rerun()
            else:
                st.error(err)


# ---------------------------------------------------------------------------
# Onboarding screen (shown once after first signup)
# ---------------------------------------------------------------------------

def render_onboarding():
    st.title("Welcome to SEP AI Coach 🎓")
    st.markdown("Let's personalise your experience so the AI can coach you in a way that's actually relevant to you.")
    st.markdown("---")

    st.markdown("#### Three quick questions:")
    field = st.text_input(
        "What are you studying?",
        placeholder="e.g. Computer Science, Nursing, Criminal Justice, Marine Biology...",
        key="onboard_field",
    )
    role = st.text_input(
        "What kind of role or career are you working toward?",
        placeholder="e.g. Software internship, Clinical rotation, Policy research, Fashion design...",
        key="onboard_role",
    )
    school = st.text_input(
        "What school do you go to?",
        placeholder="e.g. Santa Clara University, University of Denver, UCLA...",
        key="onboard_school",
    )

    col_go, col_skip = st.columns([3, 1])
    with col_go:
        if st.button("Let's go →", use_container_width=True, key="btn_onboard"):
            if field.strip() or role.strip() or school.strip():
                auth.save_profile(st.session_state.user, field.strip(), role.strip(), school.strip())
                st.session_state.profile = {"field": field.strip(), "target_role": role.strip(), "school": school.strip()}
            else:
                st.session_state.profile = {}
            st.rerun()
    with col_skip:
        if st.button("Skip for now", use_container_width=True, key="btn_skip"):
            st.session_state.profile = {}
            st.rerun()


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

def render_dashboard():
    st.title(f"Hi, {st.session_state.user}! 👋")
    st.markdown("What would you like to work on today?")
    st.markdown("---")

    col1, col2 = st.columns(2)
    cols = [col1, col2, col1, col2]

    for tile, col in zip(SCENARIOS, cols):
        with col:
            with st.container(border=True):
                st.markdown(f"### {tile['icon']} {tile['title']}")
                st.caption(tile["description"])
                if st.button("Start →", key=f"start_{tile['key']}", use_container_width=True):
                    st.session_state.active_scenario = tile["key"]
                    st.rerun()

    # Recent sessions
    st.markdown("---")
    notes = st.session_state.get("session_notes", [])
    if notes:
        st.markdown("#### Your recent sessions")
        for note in notes:
            icon = SCENARIO_ICONS.get(note["scenario"], "💬")
            title = SCENARIO_TITLES.get(note["scenario"], note["scenario"])
            date_str = note["created_at"].strftime("%b %d") if hasattr(note["created_at"], "strftime") else str(note["created_at"])[:10]
            first_bullet = note["notes"].split("\n")[0].strip().lstrip("•").strip()
            with st.container(border=True):
                st.caption(f"{icon} **{title}** · {date_str}")
                st.markdown(f"_{first_bullet}_")
    else:
        st.markdown("#### Your recent sessions")
        st.caption("Complete your first session to start building your coaching history.")

    st.markdown("---")
    if st.button("Log Out", key="logout"):
        for key in ["user", "active_scenario", "chat_histories", "profile", "profile_checked", "session_notes"]:
            st.session_state[key] = None if key in ("user", "active_scenario", "profile") else ([] if key == "session_notes" else ({} if key == "chat_histories" else False))
        st.rerun()


# ---------------------------------------------------------------------------
# Chat view
# ---------------------------------------------------------------------------

def render_chat():
    scenario_key = st.session_state.active_scenario
    tile = next(t for t in SCENARIOS if t["key"] == scenario_key)

    if scenario_key not in st.session_state.chat_histories:
        st.session_state.chat_histories[scenario_key] = []

    with st.sidebar:
        if st.button("← Back to Dashboard", use_container_width=True):
            maybe_save_session_summary(scenario_key)
            st.session_state.active_scenario = None
            st.rerun()
        st.markdown("---")
        nudge_limit = st.number_input(
            "Nudges before showing an example",
            min_value=0, max_value=5, value=2,
        )
        st.markdown("---")
        if st.button("Start a new conversation", use_container_width=True):
            maybe_save_session_summary(scenario_key)
            st.session_state.chat_histories[scenario_key] = []
            st.rerun()
        st.markdown("---")
        st.caption(f"Provider: `{PROVIDER or 'none'}` · Model: `{MODEL or 'n/a'}`")

    st.title(f"{tile['icon']} {tile['title']}")

    if not PROVIDER:
        st.error("No API key found. Add ANTHROPIC_API_KEY to Streamlit secrets.")
        st.stop()

    system_prompt = build_system_prompt(
        nudge_limit=nudge_limit,
        scenario=scenario_key,
        profile=st.session_state.get("profile"),
        session_notes=st.session_state.get("session_notes"),
    )
    messages = st.session_state.chat_histories[scenario_key]

    for msg in messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if not messages:
        primer = [{"role": "user", "content": (
            f"[The student just selected the {tile['title']} scenario. "
            "Start directly with your opening for that coaching flow.]"
        )}]
        with st.chat_message("assistant"):
            opener = st.write_stream(stream_reply(primer, system_prompt))
        messages.append({"role": "assistant", "content": opener})

    if user_input := st.chat_input("Type your message..."):
        messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)
        with st.chat_message("assistant"):
            reply = st.write_stream(stream_reply(messages, system_prompt))
        messages.append({"role": "assistant", "content": reply})


# ---------------------------------------------------------------------------
# Main router
# ---------------------------------------------------------------------------

init_state()

if st.session_state.user is None:
    render_auth()
elif st.session_state.profile_checked and st.session_state.profile is None:
    render_onboarding()
elif st.session_state.active_scenario is None:
    render_dashboard()
else:
    render_chat()
