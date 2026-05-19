# Architecture Notes

The draw.io source file is available at:

```text
docs/supporting/architecture.drawio
```

Open it with [diagrams.net](https://app.diagrams.net/) and export it as PNG or PDF for the final report and slide deck.

## Current Implementation

The current project is an end-to-end Text-to-SQL decision support prototype. A user selects a SQLite database or uploads CSV files in Streamlit, asks a natural-language question, and receives generated SQL plus a local query result table.

The implemented backend flow is:

1. Extract SQLite schema metadata and foreign-key relationships.
2. Build table-level schema chunks with columns, DDL, relationship data, and low-cardinality value hints.
3. Retrieve relevant schema using hybrid lexical, synonym, character n-gram, hashed embedding, value-hint, and graph-neighbour signals.
4. Generate one SQLite query with Gemini or a local Ollama model.
5. Validate that the query is read-only with deterministic checks and optional `sqlglot` AST parsing.
6. Execute through a read-only SQLite connection with `PRAGMA query_only` and an authorizer.
7. Display generated SQL, result rows, selected schema context, and retrieval diagnostics in Streamlit.

The local verification status as of this documentation pass is:

- Unit tests: `18` tests passing with `python3 -m unittest discover -s tests`.
- Gold evaluation: `12/12` safe, executed, value-matched, row-matched, and exact-matched cases with `python3 scripts/evaluate_text_to_sql.py --mode gold`.
- Gemini evaluation: `gemini-2.5-flash` completed all `12` cases with multi-key quota failover, reaching `11/12` value match.
- Local LLM evaluation: Ollama `llama3:latest` reached `8/12` value match with `12/12` safe/executed queries; `gemma4:latest` reached `8/12` value match overall and `8/10` among executed queries.

## Diagram Source

The file has two pages:

- `Presentation Architecture`: use this page in the report and PowerPoint. It shows the end-to-end flow, layer boundaries, numbered user journey, safety branch, and evaluation/report evidence.
- `Implementation Modules`: use this page if the teacher asks how the code is organized after the refactor.

Several dashed boxes are logo placeholders. In diagrams.net, select each placeholder and replace it with the official or preferred icon for Streamlit, Gemini, Ollama, SQLite, Python, sqlglot, or Streamlit Cloud.

The diagram is styled with Google Sans. If the font is not available on the export machine, diagrams.net will fall back to the closest installed sans-serif font; the layout should still remain readable.

The presentation page uses a layered layout:

- User and interface layer
- Data and context layer
- AI generation layer
- Safety and execution layer
- Evaluation layer
- Report and presentation evidence
- Hybrid Schema RAG internal flow

## Export Guidance

In diagrams.net, open `docs/supporting/architecture.drawio`, choose the page tab at the bottom, then use `File -> Export as -> PNG` or `PDF`. For slides, export the `Presentation Architecture` page as a PNG with a transparent background disabled so it remains readable on a white slide.

Before final submission, export both pages:

- `Presentation Architecture` for the report workflow figure and presentation workflow slide.
- `Implementation Modules` as backup evidence if asked how the refactored code maps to the system design.

## Diagram Caption

The Enterprise Text-to-SQL Agent grounds LLM SQL generation using hybrid schema RAG, validates generated SQL through deterministic and AST-based safety checks, executes only read-only SQLite queries, and returns results with generated SQL and retrieval evidence.

## Recommended Placement

- Report: Workflow and Methodology section.
- Presentation: System Workflow slide.
