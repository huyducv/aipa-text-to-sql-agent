# Architecture Diagram

The draw.io source file is available at:

```text
docs/architecture.drawio
```

Open it with [diagrams.net](https://app.diagrams.net/) and export it as PNG or PDF for the final report and slide deck.

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

In diagrams.net, open `docs/architecture.drawio`, choose the page tab at the bottom, then use `File -> Export as -> PNG` or `PDF`. For slides, export the `Presentation Architecture` page as a PNG with a transparent background disabled so it remains readable on a white slide.

## Diagram Caption

The Enterprise Text-to-SQL Agent grounds LLM SQL generation using hybrid schema RAG, validates generated SQL through deterministic and AST-based safety checks, executes only read-only SQLite queries, and returns results with generated SQL and retrieval evidence.

## Recommended Placement

- Report: Workflow and Methodology section.
- Presentation: System Workflow slide.
