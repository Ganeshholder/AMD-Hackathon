# Text-to-SQL Analytics

A Streamlit app that lets you query your SQLite database using plain English.
Powered by HuggingFace models: `Phi-3-mini` (router) + `sqlcoder-7b-2` (SQL generation).

---

## Project Structure

```
Project/
├── main.py                  # Streamlit entry point
├── requirements.txt
├── .env.example             # Copy to .env and fill in HF_TOKEN
├── .gitignore
│
├── config/
│   └── settings.py          # All config, env vars, table metadata
│
├── database/
│   ├── db_client.py         # DB access layer (execute_query, etc.)
│   └── seed.py              # One-time data seeding script
│
├── agents/
│   ├── llm_client.py        # HuggingFace client wrapper
│   ├── router_agent.py      # Routes question → relevant tables
│   └── sql_agent.py         # Generates SQLite SQL from question
│
├── app/
│   └── pages/
│       ├── home.py          # Query page (main UI)
│       └── explorer.py      # Table explorer page
│
└── .streamlit/
    └── config.toml          # Theme and server settings
```

---

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Set up environment
```bash
copy .env.example .env
# Edit .env and add your HuggingFace token
```

### 3. Seed the database
```bash
# Copy analytics.db to the Project folder, or re-seed:
python -m database.seed
```

### 4. Run the app
```bash
python -m streamlit run main.py
```
> **Note (Windows / Microsoft Store Python):** If `streamlit` is not recognised as a command, use `python -m streamlit run main.py` instead.

---

## Notes

- The `analytics.db` file should be placed in the `Project/` folder (or update `DB_PATH` in `.env`).
- `ILIKE` is not supported in SQLite — the SQL agent uses `LIKE` with `LOWER()` instead.
- Table metadata lives in `config/settings.py` — update it if you add new tables.
