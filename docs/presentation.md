# AT3 Presentation Draft: Enterprise Text-to-SQL Agent

Target: 7 minutes plus 1 minute Q&A.

## Slide 1: Title

Enterprise Text-to-SQL Agent  
Group Number: `TODO`  
Members:

- Huy Duc Vu - 25728181
- Ngoc Bao Tran Nguyen - 25611551
- Manh Tuan Nguyen - 25739083
- Nguyen Nghia Doan Dang - 26201968

Live demo: `https://aipa-text-to-sql-agent.streamlit.app/`

Speaker note: Introduce the problem: users need database answers but often cannot write SQL.

## Slide 2: Real-World Problem

- Non-technical users depend on analysts for SQL queries.
- Manual querying slows decision-making.
- Direct LLM-to-database access can be unsafe.
- Goal: natural-language analytics with safety, transparency, and evaluation.

Speaker note: Emphasise this is decision support, not just a UI.

## Slide 3: AI Approach

- Structural knowledge representation: database schema as tables, columns, and relationships.
- Schema RAG: retrieve relevant table definitions before prompting.
- LLM generation: Gemini or local Ollama creates SQL.
- Logic-based safety: read-only validation and SQLite authorizer.

Speaker note: This slide maps directly to the rubric's AI method explanation.

## Slide 4: System Workflow

1. Connect SQLite DB or upload CSV files.
2. Extract schema metadata.
3. Retrieve relevant schema chunks.
4. Generate SQL with selected LLM.
5. Validate read-only query.
6. Execute locally and display results.

Speaker note: Distinguish design decisions from implementation details.

## Slide 5: Prototype Features

- Streamlit chat-style interface.
- Gemini hosted LLM and Ollama local LLM support.
- Schema RAG toggle and retrieval report.
- Generated SQL shown for transparency.
- Demo datasets: university, retail, healthcare.

Speaker note: Show the live app or screenshots here.

## Slide 6: Evaluation Design

- Benchmark cases in `evaluation/cases.json`.
- Gold SQL for each natural-language question.
- Metrics: safe SQL rate, execution success, exact result match, latency.
- Tests cover SQL safety, CSV ingestion, schema retrieval, and read-only execution.

Speaker note: Mention reproducibility through GitHub.

## Slide 7: Results

Fill after running:

| Model | Safe SQL | Executed | Exact Match | Avg Latency |
|---|---:|---:|---:|---:|
| Gold SQL baseline | 12/12 | 12/12 | 12/12 | TODO |
| Gemini | TODO | TODO | TODO | TODO |
| Ollama Gemma3 | TODO | TODO | TODO | TODO |

Speaker note: Explain at least one success and one failure case.

## Slide 8: Ethics and Limitations

- LLMs may hallucinate tables, columns, or joins.
- Local LLMs improve privacy but need local compute.
- Hosted LLMs may be stronger but require secret handling.
- Exact results should be verified for high-stakes use.
- Current prototype is limited to read-only SQLite analytics.

Speaker note: Link ethical design to schema-only prompting and safety checks.

## Slide 9: Contributions

- Backend Text-to-SQL pipeline.
- Schema RAG and safety validation.
- Streamlit UI and deployment preparation.
- Automated evaluation framework.
- Report, presentation, and documentation.

Speaker note: Replace with named member contributions.

## Slide 10: Conclusion

- The system makes structured data more accessible.
- Multiple AI paradigms are integrated in one workflow.
- Empirical evaluation provides evidence beyond a demo.
- Future work: embedding retrieval, query repair, charts, access control.

Speaker note: End with the live GitHub and Streamlit links.

## Likely Q&A

Q: Why not send all data to the LLM?  
A: The system sends schema metadata only, reducing privacy risk and prompt size.

Q: Is the SQL always correct?  
A: No. The model can be wrong, so we evaluate against gold SQL and expose generated SQL.

Q: Why support Ollama?  
A: It enables local/offline inference and better data governance, though it requires local compute and is not the best hosted Streamlit default.

Q: How is this AI rather than simple software?  
A: The system combines schema representation, retrieval, LLM semantic parsing, and rule-based reasoning for safe execution.
