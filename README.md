# Enterprise Text-to-SQL Agent

An AI-assisted decision support prototype that translates natural-language questions into safe, locally executed SQLite queries.

## Project Overview

This repo contains a Streamlit MVP for querying structured data without writing SQL. The application sends only database schema metadata to Gemini, receives a candidate SQLite `SELECT` query, validates it, and executes it locally against the selected SQLite database.

The LLM never receives table rows or raw user data.

## Architecture

1. Schema extraction: Python reads `CREATE TABLE` statements from the local SQLite database.
2. Context injection: The user question and schema DDL are sent to Gemini.
3. SQL generation: Gemini returns a single SQLite query.
4. Safety validation: Python checks that the query is read-only and does not reference SQLite internals.
5. Read-only execution: SQLite is opened in read-only mode with query-only and authorizer protections.
6. Result rendering: Streamlit displays the generated result table and optional schema details.

## Key Files

```text
.
|-- app.py                         # Streamlit frontend
|-- text_to_sql_agent_mvp.py        # Core backend pipeline and demo data builder
|-- requirements.txt                # Runtime dependencies
|-- tests/                          # Unit tests
|-- data/
|   |-- customers.csv               # Small CSV sample
|   |-- sales.csv                   # Small CSV sample
|   |-- dynamic_agent.db            # Sample/generated SQLite DB
|   `-- university_agent.db         # Demo SQLite DB
`-- text_to_sql_agent_mvp.ipynb     # Notebook version of the MVP exploration
```

## Requirements

- Python 3.9+
- Google Gemini API key

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```bash
GEMINI_API_KEY=your_api_key_here
```

## Create Demo Data

The demo database can be created from the backend module:

```bash
python -c "import text_to_sql_agent_mvp as a; a.write_university_db('data/university_agent.db')"
```

## Run the App

```bash
streamlit run app.py
```

In the sidebar you can:

- Use an existing `.db` path.
- Upload a SQLite `.db` file.
- Upload one or more CSV files, which are converted into a temporary SQLite database.
- Create the built-in university demo database.

## Run Tests

```bash
python -m unittest discover -s tests
```

The tests cover SQL safety checks, schema extraction, CSV ingestion/table naming, read-only execution, and end-to-end fail-closed behavior without calling Gemini.

## Current Safety Model

This is still an MVP, but it now has multiple safety layers:

- Prompt instruction requires a single SQLite `SELECT`.
- `is_safe_query()` rejects non-read SQL and internal SQLite tables.
- SQLite opens user databases in read-only URI mode.
- `PRAGMA query_only = ON` adds a database-level read-only guard.
- SQLite authorizer denies write, DDL, attach/detach, transaction, analyze, reindex, and pragma operations.
- Query results are capped to avoid accidentally rendering very large result sets.

## Known Trade-offs

- Static schema injection is simple and reliable for small databases, but large enterprise schemas should use schema retrieval before prompting.
- CSV ingestion prioritizes convenience over full relational modeling; production ingestion should define constraints and types explicitly.
- LLM-generated SQL can still be invalid or semantically wrong, so production systems should log generated SQL, add feedback loops, and consider SQL parser-based validation.
- The Streamlit app is designed for local demos, not multi-user hosted deployments.
