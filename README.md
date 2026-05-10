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
3. The most relevant schema chunks are retrieved for the user question using hybrid lexical, semantic, and foreign-key graph signals.
4. The user question and retrieved schema are sent to the selected LLM.
5. The LLM returns one SQLite `SELECT` query.
6. Python validates that the SQL is read-only and avoids SQLite internals.
7. SQLite executes the query locally in read-only mode.
8. Streamlit renders the result table.

## Schema RAG

The project includes an advanced local schema RAG layer. It does not read or embed row data. It only indexes:

- table names
- column names
- `CREATE TABLE` DDL
- foreign-key neighbor tables

At question time, the backend:

1. tokenizes the user question
2. expands common business synonyms such as `client -> customer` and `revenue -> amount/sales`
3. scores schema chunks with a BM25-style lexical ranking
4. adds local character n-gram semantic similarity for fuzzy matching
5. adds stronger boosts for exact table and column matches
6. expands through foreign-key neighbors so joinable tables are included
7. sends only the selected DDL snippets to the LLM

This improves:

- prompt size for larger databases
- latency and cost
- table selection accuracy
- privacy, because only metadata is retrieved

In the Streamlit sidebar you can toggle schema RAG and adjust how many tables are retrieved. Each answer also includes an optional retrieval report showing selected tables, scores, matched terms, and graph-expansion reasons.

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
|-- text_to_sql_agent_mvp.py        # Backward-compatible backend wrapper
|-- text_to_sql_agent/              # Refactored backend package
|   |-- config.py                   # Defaults, model names, RAG constants
|   |-- data_setup.py               # Demo university database generation
|   |-- env.py                      # Environment loading
|   |-- execution.py                # Read-only SQLite execution
|   |-- ingestion.py                # CSV ingestion
|   |-- llm.py                      # Gemini/Ollama SQL generation
|   |-- pipeline.py                 # End-to-end ask_* workflows
|   |-- rag.py                      # Hybrid schema RAG
|   |-- safety.py                   # SQL safety checks
|   |-- schema.py                   # Schema extraction/chunking
|   `-- types.py                    # Shared dataclasses
|-- requirements.txt                # Dependencies
|-- evaluation/
|   `-- cases.json                  # Text-to-SQL benchmark cases
|-- scripts/
|   `-- evaluate_text_to_sql.py     # Automatic model evaluation
|-- docs/
|   |-- report.md                   # Assignment report draft
|   |-- presentation.md             # Presentation outline
|   `-- deployment.md               # Streamlit Community checklist
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

## Run Evaluation

The evaluation harness compares generated SQL results with gold SQL results.
Use `gold` mode first to verify that the benchmark and databases are healthy:

```bash
python scripts/evaluate_text_to_sql.py --mode gold
```

Then run an LLM evaluation:

```bash
python scripts/evaluate_text_to_sql.py --mode llm --provider gemini --model gemini-2.5-flash
python scripts/evaluate_text_to_sql.py --mode llm --provider ollama --model gemma3
```

Outputs are written to `evaluation/results/` as CSV and Markdown summaries.
For Gemini free-tier testing, use a throttle or a smaller smoke test:

```bash
python scripts/evaluate_text_to_sql.py --mode llm --provider gemini --model gemini-2.5-flash --delay-seconds 15
python scripts/evaluate_text_to_sql.py --mode llm --provider gemini --model gemini-2.5-flash --max-cases 3
python scripts/evaluate_text_to_sql.py --mode llm --provider gemini --model gemini-2.5-flash --max-cases 3 --max-retries 2 --retry-base-seconds 30 --resume
```

## Streamlit Community Cloud

For hosted deployment, use:

- Repository: `tuannm3812/aipa-text-to-sql-agent`
- Branch: `tuannm3812/main-refinement`
- Main file path: `app.py`
- Secrets: add `GEMINI_API_KEY`

See `docs/deployment.md` for the full checklist. Ollama is best treated as a local/offline demo option because Streamlit Community Cloud will not have access to your local Ollama server.

## Notes

This is still an MVP. The most important next improvements are persistent embedding-based schema retrieval, SQL parser-based validation, stronger query repair, and richer charting.
