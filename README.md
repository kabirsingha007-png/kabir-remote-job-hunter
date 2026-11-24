# Kabir's Remote Job Hunter AI

A Streamlit web app for discovering public remote-job listings, matching them against a configurable professional profile, and tracking application status.

## Run locally

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Streamlit Community Cloud

1. Push this complete project to a GitHub repository.
2. In Streamlit Community Cloud, create an app from that repository.
3. Set the main file path to `app.py`.
4. Add secrets only through Streamlit's app settings. Never commit API keys.

Optional secrets:
```toml
OPENAI_API_KEY = "your-key"
OPENAI_MODEL = "gpt-4.1-mini"
```

The app reads environment variables, so Streamlit secrets should be exposed as environment variables in deployment settings or the app can be updated to read `st.secrets`.

## Current capabilities

- Public listing discovery from Remotive and Arbeitnow feeds.
- Deduplication by original listing URL.
- Profile keyword matching and optional OpenAI fit assessment.
- SQLite storage and application-status tracking.
- Links back to original job listings.

## Important limitations

- This is a starter application, not a guaranteed comprehensive job crawler.
- Job-board feeds have their own coverage, terms, and rate limits.
- Verify that each employer accepts applicants located in India.
- The app does not submit applications. It is designed for human review and approval.
- SQLite is suitable for a first test; production cloud deployment should use managed persistent storage such as Supabase/Postgres.
- Never upload private CVs, personal documents, passwords, or API keys to a public repository.
