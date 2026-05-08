# Enterprise Text-to-SQL Agent

An AI-assisted decision support prototype that translates natural-language questions into safe, locally executed SQLite queries.

## What It Does

The app lets a user connect a local SQLite database or upload CSV files, ask a plain-English question, and receive a table of results. The LLM only receives schema metadata, not raw database rows.

The current branch supports two LLM backends:

- Gemini API, using `GEMINI_API_KEY`
- Local Ollama, using a model such as `gemma3`

## Architecture

1. Python extracts SQLite `CREATE TABLE` statements.
2. Schema RAG builds table-level chunks from DDL, columns, and foreign-key relationships.
3. The most relevant schema chunks are retrieved for the user question.
4. The user question and retrieved schema are sent to the selected LLM.
5. The LLM returns one SQLite `SELECT` query.
6. Python validates that the SQL is read-only and avoids SQLite internals.
7. SQLite executes the query locally in read-only mode.
8. Streamlit renders the result table.

## Schema RAG

The project now includes a local schema RAG layer. It does not read or embed row data. It only indexes:

- table names
- column names
- `CREATE TABLE` DDL
- foreign-key neighbor tables

At question time, the backend scores schema chunks against the user's words, retrieves the top tables, includes directly related foreign-key tables, and sends only those DDL snippets to the LLM.

This improves:

- prompt size for larger databases
- latency and cost
- table selection accuracy
- privacy, because only metadata is retrieved

In the Streamlit sidebar you can toggle schema RAG and adjust how many tables are retrieved.

## Safety Model

- Generated SQL must start with `SELECT` or `WITH`.
- Data modification and schema-changing statements are blocked.
- Internal SQLite tables such as `sqlite_master` are blocked.
- SQLite is opened in read-only URI mode.
- `PRAGMA query_only = ON` is enabled during execution.
- A SQLite authorizer denies writes, DDL, transactions, attach/detach, pragmas, analyze, and reindex.
- Results are capped to avoid rendering unexpectedly large outputs.

## Project Structure

```text
.
|-- app.py                         # Streamlit frontend
|-- text_to_sql_agent_mvp.py        # Backend pipeline
|-- requirements.txt                # Dependencies
|-- data/
|   |-- customers.csv               # Small CSV sample
|   |-- sales.csv                   # Small CSV sample
|   |-- university_agent.db         # Demo university DB
|   |-- healthcare_analytics.db     # Healthcare sample DB
|   `-- retail_analytics.db         # Retail sample DB
`-- text_to_sql_agent_mvp.ipynb     # Notebook exploration
```

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

For Gemini, create `.env` in the project root:

```bash
GEMINI_API_KEY=your_api_key_here
TEXT_TO_SQL_PROVIDER=gemini
```

For local Ollama:

```bash
ollama pull gemma3
ollama serve
```

Then select `ollama` in the Streamlit sidebar.

## Run The App

```bash
streamlit run app.py
```

In the sidebar you can:

- choose Gemini or Ollama
- set the model name
- enable or disable schema RAG
- tune how many schema tables are retrieved
- use an existing `.db` path
- upload a SQLite `.db`
- upload one or more CSV files
- create the built-in university demo database

## Create Demo Data

```bash
python -c "import text_to_sql_agent_mvp as a; a.write_university_db('data/university_agent.db')"
```

## Run Tests

```bash
python -m unittest discover -s tests
```

## Notes

This is still an MVP. The most important next improvements are embedding-based schema retrieval, SQL parser-based validation, stronger query repair, and richer charting.
