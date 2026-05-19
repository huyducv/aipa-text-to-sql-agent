# Streamlit Community Deployment

Use this checklist to deploy the current Streamlit app from the project repository.

## Repository Settings

- Repository: `tuannm3812/aipa-text-to-sql-agent`
- Branch: `tuannm3812/main-refinement`
- Main file path: `app.py`
- Python version: choose Python 3.12 in Streamlit Community Cloud advanced settings

## Secrets

For Gemini deployment, add this in Streamlit Community Cloud secrets:

```toml
GEMINI_API_KEY = "your_key_here"
TEXT_TO_SQL_PROVIDER = "gemini"
```

For multiple Gemini keys, add either `GOOGLE_API_KEYS` as a comma-separated value or indexed keys such as `GOOGLE_API_KEY`, `GOOGLE_API_KEY_1`, and `GOOGLE_API_KEY_2`. The app can rotate through keys when quota-related errors occur.

Do not commit `.env` or `.streamlit/secrets.toml`.

## Notes

- Gemini is suitable for Streamlit Community Cloud because it calls a hosted API.
- Ollama is suitable for local demos. Streamlit Community Cloud does not provide your local Ollama server, so local models should be presented as a local/offline option rather than the hosted default.
- The app has `requirements.txt` at the repository root and `app.py` at the repository root, which matches Streamlit Community Cloud's expected project layout.
- Uploaded `.db` and CSV files are stored in temporary paths during a session. They are not intended as persistent production storage.
- The deployed demo should be described as read-only decision support, not as an autonomous database administration tool.

## Deploy Steps

1. Go to `https://share.streamlit.io`.
2. Create a new app from an existing GitHub repository.
3. Select repository, branch, and `app.py`.
4. Add secrets in advanced settings.
5. Deploy and check the app logs.

## Post-Deployment Smoke Test

After deployment, run this quick check in the live app:

1. Select `Gemini` and `gemini-2.5-flash`.
2. Select the `Retail Analytics` demo database.
3. Keep Schema RAG enabled with the default top-k setting.
4. Ask: `Which return reasons occur most often?`
5. Confirm that the app shows generated SQL, a result table, selected schema context, and retrieval diagnostics.

If the model returns a quota error, wait for quota reset or add another Gemini key in Streamlit secrets.
