# SEP AI Coach

A Streamlit chatbot for college students with four coaching modes: interview practice, inbox reset, professional email writing, and workplace conflict navigation. The bot auto-routes to the right scenario based on what the student says — no menu.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Then edit .env and paste your OPENAI_API_KEY
```

## Run

```bash
streamlit run app.py
```

Opens at http://localhost:8501.

## Files

- `app.py` — Streamlit UI and OpenAI call
- `prompts.py` — system prompt containing triage logic + all four scenario flows
