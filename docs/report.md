# AT3 Report Draft: Enterprise Text-to-SQL Agent

Group Number: `TODO`  
Group Members and Student IDs:

- Huy Duc Vu - 25728181
- Ngoc Bao Tran Nguyen - 25611551
- Manh Tuan Nguyen - 25739083
- Nguyen Nghia Doan Dang - 26201968

GitHub Repository: `https://github.com/tuannm3812/aipa-text-to-sql-agent`  
Live Demo: `https://aipa-text-to-sql-agent.streamlit.app/`

## Executive Summary

This project addresses a common real-world problem in organisations: non-technical users often need answers from structured databases but cannot write SQL safely or efficiently. We developed an AI-assisted Text-to-SQL decision support prototype that translates natural-language questions into read-only SQLite queries, executes them locally, and presents results through a Streamlit interface.

The solution integrates multiple AI paradigms: structural knowledge representation through database schema modelling, information retrieval through schema-level RAG, logic-based safety constraints for SQL validation, and generative AI through LLM-based query synthesis. The system supports Gemini as a hosted LLM and Ollama as a local LLM option. Evaluation is performed using benchmark natural-language questions with gold SQL queries across university, retail, and healthcare datasets.

Key findings should be filled after running the evaluation script. Report the exact-result-match rate, execution success rate, safe-SQL rate, and average latency from `evaluation/results/evaluation_llm.md`.

## 1. Introduction

Modern organisations store important operational information in relational databases, but access to that information often depends on technical staff who understand SQL. This creates bottlenecks in decision-making, especially for business users, educators, healthcare administrators, and analysts who need quick answers but may not know the database schema.

The project objective is to build a safe natural-language interface for structured data. A user can connect a SQLite database or upload CSV files, ask a question in plain English, and receive a table of results. The scope is intentionally focused on analytical, read-only queries over local structured data. The system does not support database modification, unrestricted SQL execution, or direct exposure of raw database rows to the LLM.

The significance of the problem is practical and ethical. A well-designed Text-to-SQL assistant can improve access to data and reduce repetitive analyst workload. However, careless deployment can create risks such as incorrect answers, privacy leakage, unsafe SQL execution, and over-trust in generated outputs. Therefore, the project emphasises transparency, execution safety, and empirical evaluation.

## 2. Theoretical Justification

The proposed method combines four AI-relevant components.

First, the database schema is treated as a structural knowledge representation. Tables, columns, primary keys, and foreign-key relationships represent entities and relationships in the application domain. This supports logical reasoning because SQL generation depends on mapping a question to the correct entities, attributes, aggregations, and joins.

Second, the project uses schema-level retrieval augmented generation. Instead of sending the full database content to the LLM, the system retrieves relevant table DDL using a BM25-style lexical ranking strategy with synonym expansion and foreign-key graph expansion. This improves privacy because only metadata is sent to the model, and it improves scalability because the prompt can be smaller for larger databases.

Third, an LLM generates candidate SQL. LLMs are suitable because Text-to-SQL requires semantic parsing from natural language to a formal query language. However, LLMs can hallucinate columns, produce invalid SQL, or include unsafe statements. The system therefore does not trust the model output directly.

Fourth, deterministic safety controls apply logic-based constraints. The generated SQL must begin with `SELECT` or `WITH`, dangerous keywords such as `DELETE`, `DROP`, and `ALTER` are blocked, SQLite internal tables are blocked, and execution occurs through a read-only SQLite connection with an authorizer. This combines generative flexibility with rule-based control.

Relevant literature to cite:

- Lewis et al. (2020) on retrieval-augmented generation.
- Brown et al. (2020) or a more recent LLM paper for few-shot language generation capability.
- Yu et al. (2018) Spider dataset for complex cross-domain Text-to-SQL evaluation.
- Zhong et al. (2017) WikiSQL for semantic parsing to SQL.
- Weidinger et al. (2021) or NIST AI RMF for responsible AI risks.

## 3. Workflow and Methodology

The workflow begins with data preparation. SQLite databases are used directly, while uploaded CSV files are normalised into SQLite tables with sanitised table names. The system extracts `CREATE TABLE` statements and excludes internal SQLite metadata tables.

The model workflow is:

1. User selects Gemini or Ollama and connects a database.
2. User asks a natural-language question.
3. The backend retrieves relevant schema chunks using table names, column names, DDL text, synonym expansion, and foreign-key neighbours.
4. The selected schema context and user question are sent to the LLM.
5. The LLM returns candidate SQL.
6. The safety layer validates read-only behaviour.
7. SQLite executes the query in read-only mode.
8. Streamlit displays result rows, generated SQL, schema context, and retrieval diagnostics.

Design decisions are separated from implementation details. The design choice is to use schema-only RAG for privacy and scalability. The implementation detail is a local BM25-style scorer rather than a vector database. The design choice is to support both hosted and local LLMs. The implementation detail is Gemini API for hosted generation and Ollama through LangChain for local generation.

## 4. Empirical Analysis and Results

The project includes an automated benchmark in `evaluation/cases.json`. Each case contains a natural-language question, database path, gold SQL query, expected tables, and difficulty level. The evaluator executes both the gold SQL and the generated SQL, then compares columns and result rows.

Metrics:

- Safe SQL rate: proportion of generated SQL queries passing deterministic safety checks.
- Execution success rate: proportion of generated queries that execute without error.
- Exact result match: proportion where generated query results match the gold query results exactly.
- Latency: time from question to result.

Run the reproducible evaluation:

```bash
python scripts/evaluate_text_to_sql.py --mode gold
python scripts/evaluate_text_to_sql.py --mode llm --provider gemini --model gemini-2.5-flash --delay-seconds 15
python scripts/evaluate_text_to_sql.py --mode llm --provider ollama --model gemma3
```

Results table to fill after running:

| Model | Schema RAG | Cases | Safe SQL | Execution Success | Value Match | Exact Match | Schema Recall | Average Latency |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Gold SQL baseline | Yes | 12 | 12/12 | 12/12 | 12/12 | 12/12 | 1.00 | See `evaluation/results` |
| Gemini 2.5 Flash | Yes | TODO | TODO | TODO | TODO | TODO | TODO | TODO |
| Ollama Gemma3 | Yes | TODO | TODO | TODO | TODO | TODO | TODO | TODO |

Note: Gemini free-tier API quotas may interrupt a full benchmark. If this occurs, report the completed cases separately and state that the run was quota-limited. The script supports `--delay-seconds` and `--max-cases` for controlled testing.

Interpretation should discuss which question types are easiest, where joins fail, whether Schema RAG improves table selection, and how local LLM performance compares with Gemini.

## 5. Critical Reflection

The system has several limitations. First, exact SQL correctness is not guaranteed because LLMs may hallucinate column names or choose semantically plausible but incorrect joins. Second, lexical schema retrieval can miss relevant tables when the user uses unfamiliar wording not covered by synonyms. Third, exact-result-match evaluation is strict and may mark equivalent SQL as incorrect if ordering or rounding differs. Fourth, Streamlit Community deployment is best suited to Gemini because Ollama requires a running local model server.

The main trade-off is accuracy versus privacy and cost. Sending full schema context may improve accuracy for small databases, but schema RAG scales better and limits unnecessary disclosure. Hosted LLMs may provide stronger generation quality, while local LLMs improve offline operation and data governance but depend on local compute resources.

Alternative approaches may be better in some settings. A fine-tuned Text-to-SQL model could improve domain-specific accuracy if labelled training data is available. A SQL parser and formal AST policy could strengthen validation. Embedding-based retrieval could improve semantic matching. Human-in-the-loop approval would be suitable for high-stakes decisions.

## 6. Ethics and Responsible AI

The prototype follows responsible AI principles by minimising data exposure, showing generated SQL for transparency, blocking write operations, and making failure cases visible rather than hiding them. Users should still treat outputs as decision support rather than final authority. For sensitive domains such as healthcare, deployment would require access control, audit logging, de-identification, and stronger evaluation before production use.

## 7. Conclusion and Future Work

This project demonstrates a practical AI decision support system that combines LLM-based semantic parsing, structural schema representation, retrieval, and logic-based safety controls. The prototype shows how natural-language access to relational data can be made more usable while maintaining important safety boundaries.

Future work should include embedding-based schema retrieval, query repair loops, chart generation, role-based access control, stronger benchmark coverage, and evaluation on larger real-world databases. A production system should also include monitoring, audit logs, user feedback, and formal privacy review.

## 8. Individual Contributions

Fill this section clearly for marking.

| Member | Student ID | Contributions |
|---|---|---|
| TODO | TODO | TODO |
| TODO | TODO | TODO |

## References

Brown, T. B., et al. (2020). Language Models are Few-Shot Learners.  
Lewis, P., et al. (2020). Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks.  
Yu, T., et al. (2018). Spider: A Large-Scale Human-Labeled Dataset for Complex and Cross-Domain Semantic Parsing and Text-to-SQL Task.  
Zhong, V., Xiong, C., & Socher, R. (2017). Seq2SQL: Generating Structured Queries from Natural Language using Reinforcement Learning.  
National Institute of Standards and Technology. (2023). Artificial Intelligence Risk Management Framework.
