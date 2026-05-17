"""SEP AI Coach — Streamlit app with auth, dashboard, and per-scenario chat."""

import os

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# Load Streamlit Cloud secrets into env vars so auth.py can use os.getenv()
for _key in ["ANTHROPIC_API_KEY", "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD"]:
    try:
        if _key in st.secrets:
            os.environ[_key] = str(st.secrets[_key])
    except Exception:
        pass

import auth
from prompts import build_system_prompt

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
    {
        "key": "interview",
        "icon": "🎯",
        "title": "Interview Prep",
        "description": "Practice mock questions and get real-time feedback",
    },
    {
        "key": "email",
        "icon": "✉️",
        "title": "Email Writing",
        "description": "Draft professional emails that make the right impression",
    },
    {
        "key": "inbox",
        "icon": "📥",
        "title": "Inbox Reset",
        "description": "Build a system to tame your overloaded inbox",
    },
    {
        "key": "conflict",
        "icon": "🤝",
        "title": "Workplace Conflict",
        "description": "Think through tense situations with clarity",
    },
]


# ---------------------------------------------------------------------------
# Streaming helpers
# ---------------------------------------------------------------------------

def stream_anthropic(messages, system_prompt):
    from anthropic import Anthropic

    client = Anthropic(api_key=ANTHROPIC_KEY)
    with client.messages.stream(
        model=MODEL,
        max_tokens=2048,
        system=system_prompt,
        messages=messages,
    ) as stream:
        yield from stream.text_stream


def stream_openai(messages, system_prompt):
    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_KEY)
    stream = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": system_prompt}, *messages],
        temperature=0.7,
        stream=True,
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


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(page_title="SEP AI Coach", page_icon="🎓", layout="centered")


# ---------------------------------------------------------------------------
# Session state init
# ---------------------------------------------------------------------------

def init_state():
    if "user" not in st.session_state:
        st.session_state.user = None
    if "active_scenario" not in st.session_state:
        st.session_state.active_scenario = None
    if "chat_histories" not in st.session_state:
        st.session_state.chat_histories = {}


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

    st.markdown("---")
    if st.button("Log Out", key="logout"):
        st.session_state.user = None
        st.session_state.active_scenario = None
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
            st.session_state.active_scenario = None
            st.rerun()
        st.markdown("---")
        nudge_limit = st.number_input(
            "Nudges before showing an example",
            min_value=0,
            max_value=5,
            value=2,
            help=(
                "How many times the coach will nudge you to expand a short answer "
                "before offering a polished example. 0 disables pacing."
            ),
        )
        st.markdown("---")
        if st.button("Start a new conversation", use_container_width=True):
            st.session_state.chat_histories[scenario_key] = []
            st.rerun()
        st.markdown("---")
        st.caption(f"Provider: `{PROVIDER or 'none'}` · Model: `{MODEL or 'n/a'}`")

    st.title(f"{tile['icon']} {tile['title']}")

    if not PROVIDER:
        st.error(
            "No API key found. Add `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` to a "
            "`.env` file in this directory and restart."
        )
        st.stop()

    system_prompt = build_system_prompt(nudge_limit=nudge_limit, scenario=scenario_key)
    messages = st.session_state.chat_histories[scenario_key]

    for msg in messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if not messages:
        primer = [
            {
                "role": "user",
                "content": (
                    f"[The student just selected the {tile['title']} scenario. "
                    "Start directly with your opening for that coaching flow.]"
                ),
            }
        ]
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
elif st.session_state.active_scenario is None:
    render_dashboard()
else:
    render_chat()
