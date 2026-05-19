# Enterprise Text-to-SQL Agent: Academic Report

Group Number: to be confirmed by the submission portal

Group Members and Student IDs:

- Huy Duc Vu - 25728181
- Ngoc Bao Tran Nguyen - 25611551
- Manh Tuan Nguyen - 25739083
- Nguyen Nghia Doan Dang - 26201968

GitHub Repository: `https://github.com/tuannm3812/aipa-text-to-sql-agent`

Live Demo: `https://aipa-text-to-sql-agent.streamlit.app/`

## Table of Contents

1. [Executive Summary](#1-executive-summary)  
   1.1 [Overview of the Project](#11-overview-of-the-project)  
   1.2 [Objectives](#12-objectives)  
   1.3 [Key Findings](#13-key-findings)

2. [Introduction](#2-introduction)  
   2.1 [Background and Context](#21-background-and-context)  
   2.2 [Problem Statement](#22-problem-statement)  
   2.3 [Significance and Impact](#23-significance-and-impact)  
   2.4 [Challenges and Constraints](#24-challenges-and-constraints)  
   2.5 [Project Objectives and Scope](#25-project-objectives-and-scope)

3. [Theoretical Justification](#3-theoretical-justification)  
   3.1 [Overview of AI Methods Used](#31-overview-of-ai-methods-used)  
   3.2 [Theoretical Foundations](#32-theoretical-foundations)  
   3.3 [Justification of Selected Methods](#33-justification-of-selected-methods)  
   3.4 [Related Work and Literature Support](#34-related-work-and-literature-support)

4. [Workflow and Methodology](#4-workflow-and-methodology)  
   4.1 [System Architecture Overview](#41-system-architecture-overview)  
   4.2 [Data Collection and Preprocessing](#42-data-collection-and-preprocessing)  
   4.3 [Feature Engineering](#43-feature-engineering)  
   4.4 [Model Design and Algorithmic Approach](#44-model-design-and-algorithmic-approach)  
   4.5 [Integration of AI Paradigms](#45-integration-of-ai-paradigms)  
   4.6 [Design Decisions vs Implementation Details](#46-design-decisions-vs-implementation-details)

5. [Empirical Analysis and Results](#5-empirical-analysis-and-results)  
   5.1 [Experimental Setup](#51-experimental-setup)  
   5.2 [Dataset Description](#52-dataset-description)  
   5.3 [Evaluation Metrics](#53-evaluation-metrics)  
   5.4 [Results](#54-results)  
   5.5 [Result Interpretation and Discussion](#55-result-interpretation-and-discussion)

6. [Critical Reflection](#6-critical-reflection)  
   6.1 [Limitations of the Approach](#61-limitations-of-the-approach)  
   6.2 [Failure Cases](#62-failure-cases)  
   6.3 [Trade-offs](#63-trade-offs)  
   6.4 [Scalability and Computational Constraints](#64-scalability-and-computational-constraints)  
   6.5 [Alternative Methods and Improvements](#65-alternative-methods-and-improvements)

7. [GitHub Repository](#7-github-repository)  
   7.1 [Repository Link](#71-repository-link)  
   7.2 [Instructions to Run the Project](#72-instructions-to-run-the-project)

8. [Conclusion](#8-conclusion)  
   8.1 [Summary of Findings](#81-summary-of-findings)  
   8.2 [Key Insights](#82-key-insights)  
   8.3 [Future Work](#83-future-work)

9. [Individual Contributions](#9-individual-contributions)

10. [References](#10-references)

## 1. Executive Summary

### 1.1 Overview of the Project

This project presents an **AI-assisted Text-to-SQL decision support agent** that enables non-technical users to query relational data using natural language. The system accepts a user question, retrieves the most relevant database schema context, asks a **large language model (LLM)** to generate SQLite SQL, validates the generated query through deterministic safety controls, executes it in a **read-only SQLite environment**, and returns both the result table and the generated SQL through a Streamlit interface.

The project addresses a practical organisational problem: valuable operational data is often stored in relational databases, yet meaningful access is limited to users who can write SQL and understand database schemas. This creates a dependency on technical staff, slows decision-making, and can exclude business users, educators, analysts, and administrators from direct evidence-based inquiry. The proposed system reduces this barrier by combining **generative AI**, **schema retrieval augmented generation (Schema RAG)**, **structured knowledge representation**, and **logic-based safety validation**.

### 1.2 Objectives

The core objective is to design and evaluate a safe, usable, and reproducible natural-language interface for structured data. The specific objectives are to:

- translate natural-language questions into executable SQLite `SELECT` queries;
- expose only **schema metadata** and privacy-safe categorical hints to the LLM, rather than raw database rows;
- support both a hosted model pathway through **Gemini** and a local/offline pathway through **Ollama**;
- validate generated SQL using conservative **read-only safety constraints**;
- evaluate the system against benchmark questions with gold SQL answers; and
- document the architecture, workflow, limitations, and ethical implications in a reproducible GitHub repository.

### 1.3 Key Findings

The empirical results show that the project successfully implements the required end-to-end workflow and safety-oriented architecture. In gold-baseline evaluation, all 12 benchmark cases executed correctly, producing a **12/12 safe SQL rate**, **12/12 execution success rate**, **12/12 value match**, **12/12 row match**, and **12/12 exact result match**. This confirms that the benchmark datasets, gold SQL, SQLite execution layer, and evaluation harness are internally consistent.

The Schema RAG component achieved an average **schema table recall of 1.0** across the benchmark cases, meaning the expected relevant tables were retrieved for all cases. This is important because Text-to-SQL systems frequently fail when the model receives incomplete or irrelevant schema context. The prompt-size saving in the gold baseline averaged **6.0%**, with larger savings on some retail cases where the schema contained more tables and relationships.

Gemini evaluation was then run with `gemini-2.5-flash` using 10 configured API keys for quota failover. This full 12-case run completed with **12/12 safe SQL**, **12/12 execution success**, **11/12 value match**, **6/12 row match**, and **0/12 exact result match**, with average latency of **3.28 seconds**. Earlier single-key Gemini testing hit `429 RESOURCE_EXHAUSTED` errors, so the multi-key manager is an important operational improvement rather than a cosmetic feature.

The same benchmark was also run with local Ollama models. `llama3:latest` achieved **12/12 safe SQL**, **12/12 execution success**, **8/12 value match**, **5/12 row match**, and **0/12 exact result match**, with average latency of **3.78 seconds**. `gemma4:latest` achieved **10/12 safe SQL**, **10/12 execution success**, **8/12 value match overall**, **8/10 value match among executed queries**, **3/12 row match**, and **0/12 exact result match**, with average latency of **5.65 seconds**. These results show that exact-match scoring is intentionally strict: many generated queries returned useful values but failed exact matching because of aliases, rounding, or row-order differences.

Overall, the project demonstrates that a practical Text-to-SQL assistant should not rely on generation alone. A more responsible architecture combines **LLM semantic parsing** with **retrieval grounding**, **transparent SQL display**, **read-only execution**, and **empirical validation**.

## 2. Introduction

### 2.1 Background and Context

Relational databases remain a dominant technology for storing operational and analytical data because they provide structured schemas, transaction support, and a mature query language in SQL. However, SQL is a formal language that requires knowledge of table names, column names, joins, filtering, grouping, aggregation, and ordering. In many organisations, this creates a gap between people who need information and people who can retrieve it.

Recent progress in **large language models** has made it possible to translate natural language into formal representations such as code, API calls, and SQL. This task is commonly known as **Text-to-SQL**. In principle, Text-to-SQL can allow users to ask questions such as "Which product categories generate the most completed order revenue?" and receive the corresponding query and result table. In practice, the task is difficult because natural language is ambiguous, database schemas vary across domains, and SQL is unforgiving: a small error in a join condition, column name, aggregation, or filter can produce invalid or misleading results.

This project is situated at the intersection of **decision support systems**, **semantic parsing**, **retrieval augmented generation**, and **responsible AI**. It focuses on a realistic but bounded use case: read-only analytical querying over local SQLite databases and uploaded CSV files.

### 2.2 Problem Statement

The problem addressed by this project is that non-technical users often cannot independently obtain answers from structured databases, while direct unrestricted use of LLM-generated SQL can be unsafe and unreliable. A useful system must therefore solve two connected problems:

First, it must perform **semantic translation** from a natural-language question into a valid SQL query that uses the correct tables, columns, joins, filters, and aggregations. Second, it must manage **operational risk** by preventing destructive SQL, limiting exposure of sensitive data, and making generated outputs inspectable.

The central research and engineering question is: how can an AI system provide accessible natural-language querying over relational data while maintaining safety, transparency, privacy awareness, and empirical accountability?

### 2.3 Significance and Impact

The significance of this problem is both practical and ethical. Practically, a reliable Text-to-SQL assistant can reduce repetitive analyst workload, shorten the time between question and evidence, and make structured data more accessible to stakeholders without specialist SQL knowledge. In education, it can help staff analyse student records or course outcomes. In retail, it can support revenue, returns, and customer-service analysis. In healthcare administration, it can support operational reporting over appointments, hospitals, treatments, and patient registrations.

Ethically, the same capability can introduce risks. If an LLM generates an incorrect query, users may make decisions based on false evidence. If raw rows are sent to an external model, privacy risks increase. If write operations are permitted, the system could modify or destroy data. If generated SQL is hidden, users cannot audit how an answer was produced. For these reasons, this project treats **safety**, **privacy minimisation**, and **explainability** as architectural requirements rather than optional enhancements.

### 2.4 Challenges and Constraints

The main technical challenge is schema grounding. A question may refer to business concepts such as "revenue", "completed orders", "student performance", or "hospital city", while the database may represent these concepts through different table and column names. The system must map user language to schema structures without seeing or exposing all database rows.

A second challenge is reliability. LLMs can hallucinate non-existent columns, omit necessary joins, generate SQL that is syntactically invalid, or produce semantically plausible queries that answer a different question. A third challenge is safety: even if a model is prompted to produce only `SELECT` statements, prompt instructions alone are insufficient for security. The system must therefore include deterministic validation and read-only execution controls.

The project also operates under assignment-scale constraints. It uses SQLite rather than enterprise data warehouses, a compact benchmark rather than a large public dataset such as Spider, and local heuristic retrieval rather than a production vector database. These constraints are appropriate for a prototype, but they shape the scope of the claims that can be made from the results.

### 2.5 Project Objectives and Scope

The scope is an end-to-end **MVP decision support agent** for SQLite databases and CSV-derived tables. The system supports analytical read-only queries, schema retrieval, LLM generation, validation, execution, and result display. It does not support database modification, user authentication, row-level access control, production audit logging, or guaranteed correctness.

The project objectives are to:

- build a working Streamlit application for natural-language database querying;
- implement a backend package with separate modules for ingestion, schema extraction, retrieval, generation, safety, execution, and orchestration;
- evaluate the approach using multiple domains and query difficulty levels;
- critically analyse limitations, failure cases, and trade-offs; and
- document reproducible setup and evaluation instructions through GitHub.

## 3. Theoretical Justification

### 3.1 Overview of AI Methods Used

The system integrates several AI methods. The first is **knowledge representation**, where the relational schema is treated as a structured representation of the domain. Tables represent entity sets, columns represent attributes, and foreign keys represent relationships. This provides the symbolic foundation needed to generate SQL joins and aggregations.

The second method is **retrieval augmented generation**. Instead of sending the full database or relying only on a user question, the system retrieves a targeted subset of schema context relevant to the question. This Schema RAG approach grounds the LLM in the available tables and columns while reducing unnecessary prompt content.

The third method is **generative AI** through LLM-based SQL synthesis. The LLM performs semantic parsing by mapping natural language to SQLite SQL. The system supports Gemini as a hosted LLM and Ollama-compatible local models such as Gemma for offline experimentation.

The fourth method is **logic-based reasoning and constraint checking**. Generated SQL must pass deterministic validation before execution. This is not learning-based; it is a symbolic control layer that enforces system policy.

### 3.2 Theoretical Foundations

Text-to-SQL is a form of **semantic parsing**, where natural language is converted into a formal executable representation. Classical semantic parsing systems depend heavily on grammars, manually engineered features, or supervised learning. Modern LLMs improve flexibility because they have learned broad linguistic and code patterns from large-scale pretraining. However, LLMs are probabilistic models and do not guarantee factual or syntactic correctness. This makes grounding and validation essential.

The Schema RAG component follows the broader theory of **retrieval augmented generation**. Lewis et al. (2020) showed that generation can be improved by retrieving relevant external knowledge and conditioning the model on that retrieved context. In this project, the retrieved knowledge is not encyclopaedic text but database schema metadata. The same theoretical principle applies: generation is more reliable when the model receives task-specific evidence.

The retrieval design combines **lexical matching**, **synonym expansion**, **character n-gram similarity**, **hashed embedding similarity**, and **foreign-key graph expansion**. Lexical matching resembles BM25-style information retrieval, where term overlap and inverse document frequency help rank relevant schema chunks. Character n-gram and hashed embedding similarities provide approximate semantic and fuzzy matching without depending on a remote embedding service. Foreign-key expansion reflects graph reasoning: if a selected table is linked to another table through a relationship, the neighbour may be necessary for a correct join.

The safety layer is grounded in **formal constraints**. The system conservatively permits only SQL beginning with `SELECT` or `WITH`, blocks dangerous keywords, rejects internal SQLite schema references, optionally parses SQL with `sqlglot` for AST-level validation, opens SQLite using a read-only URI, enables `PRAGMA query_only`, and installs a SQLite authorizer that denies write, DDL, transaction, attach/detach, pragma, analyse, and reindex operations. This layered approach reflects defence in depth: even if one control fails, other controls reduce risk.

### 3.3 Justification of Selected Methods

The selected AI methods are suitable because the problem requires both flexible language understanding and strict operational control. A purely rule-based natural-language interface would be difficult to extend across different schemas and phrasings. A purely generative interface would be too risky because LLMs can produce unsafe or incorrect SQL. The project therefore uses a hybrid architecture in which the LLM handles **semantic flexibility**, RAG handles **schema grounding**, and deterministic validators handle **safety enforcement**.

Schema-only retrieval is particularly justified because it supports privacy minimisation. The LLM receives table definitions, column names, relationships, and low-cardinality hints, but not raw database rows. This follows the principle of data minimisation: only information necessary for query generation should be exposed to the model. For sensitive domains such as healthcare, this design choice is ethically preferable to sending complete records to an external API.

Supporting both Gemini and Ollama is also theoretically and practically justified. Hosted models may provide stronger reasoning and SQL generation, while local models support offline use and stronger data governance. This dual-provider design allows the project to compare trade-offs between **accuracy**, **latency**, **cost**, and **privacy**.

### 3.4 Related Work and Literature Support

The project is informed by established Text-to-SQL and LLM research. Zhong et al. (2017) introduced Seq2SQL for generating SQL from natural language using reinforcement learning, demonstrating that SQL generation can be treated as a structured prediction problem. Yu et al. (2018) introduced Spider, a cross-domain Text-to-SQL benchmark that highlighted the difficulty of generalising across unseen schemas. Brown et al. (2020) demonstrated the few-shot capabilities of large language models, which helps explain why modern LLMs can generate plausible SQL from prompts. Lewis et al. (2020) established retrieval augmented generation as a method for grounding generation in retrieved evidence.

The responsible AI framing is supported by the NIST AI Risk Management Framework, which emphasises validity, reliability, safety, security, accountability, transparency, explainability, privacy, and fairness. Weidinger et al. (2021) also discuss the ethical and social risks of language models, including misinformation, privacy leakage, and over-reliance. These concerns are directly relevant to Text-to-SQL because generated answers may influence decisions and may involve sensitive structured data.

## 4. Workflow and Methodology

### 4.1 System Architecture Overview

The user-facing system architecture consists of six major layers: user input, data preparation, schema retrieval, SQL generation, safety-controlled execution, and answer display. The Streamlit interface allows users to choose a provider and model, connect a SQLite database or upload CSV files, ask a question, and inspect the generated SQL, result table, and retrieval diagnostics.

The backend is organised as a Python package under `text_to_sql_agent/`. The main modules are `ingestion.py` for CSV ingestion, `schema.py` for schema extraction and schema chunk construction, `rag.py` for hybrid schema retrieval, `llm.py` for Gemini and Ollama generation, `safety.py` for SQL validation, `execution.py` for read-only SQLite execution, and `pipeline.py` for orchestration. The file `text_to_sql_agent_mvp.py` remains as a compatibility wrapper for the notebook, tests, and Streamlit app.

The architectural diagrams are stored in `docs/supporting/architecture.drawio`. For the final PDF submission, the `User Tool Workflow` page should be exported as a PNG or PDF and inserted here as Figure 1. This figure should focus only on normal tool usage and should not include the offline evaluation or report-preparation process.

**Figure 1. User Tool Workflow for Natural-Language Database Question Answering.**
This figure should show the live app path: Streamlit question input, sample database or uploaded data selection, schema extraction, Schema RAG, Gemini/Ollama SQL candidate generation, safety validation, read-only SQLite execution, and the answer panel returned to the user.

### 4.2 Data Collection and Preprocessing

The project uses three SQLite benchmark domains: university, retail, and healthcare. These domains were selected because they contain common analytical patterns such as counting, averaging, grouping, filtering, and joining. The university domain includes students, courses, and grades. The retail domain includes customers, regions, orders, order items, products, returns, and support tickets. The healthcare domain includes patients, appointments, doctors, hospitals, and treatments.

CSV uploads are converted into SQLite tables. During preprocessing, table names are sanitised so that uploaded files become valid SQLite identifiers. SQLite databases are read directly, while internal metadata tables are excluded from prompt construction and querying. The system extracts `CREATE TABLE` definitions and foreign-key relationships, which become the primary schema context for retrieval and generation.

This preprocessing strategy supports **reproducibility** and **privacy**. Reproducibility is supported because benchmark cases reference fixed database files and gold SQL queries. Privacy is supported because the LLM prompt is built from schema metadata rather than unrestricted row data.

### 4.3 Feature Engineering

Feature engineering occurs primarily in the Schema RAG layer. Each table is converted into a schema chunk containing its table name, columns, DDL, searchable text, foreign-key neighbours, and selected low-cardinality value hints. The user question is tokenised and expanded using domain synonyms such as mappings from "client" to "customer" and "revenue" to amount or sales-related terms. The `Hybrid Schema RAG Detail` page in `docs/supporting/architecture.drawio` should be exported as Figure 2 to show this retrieval process as its own method flow rather than hiding it inside the full system diagram.

The retrieval layer also decomposes questions into interpretable categories: **entities or metrics**, **aggregations**, **filters or dimensions**, and **comparisons**. For example, a question containing "average" is marked as an average aggregation, while a question containing "completed" or "status" may activate filter and dimension signals. These features do not replace the LLM; they improve retrieval and make the retrieval process more explainable.

Additional engineered signals include BM25-style lexical scores, exact table and column match boosts, character n-gram similarity, local hashed embedding similarity, and foreign-key neighbour expansion. These signals are combined to rank schema chunks before constructing the LLM prompt.

**Figure 2. Hybrid Schema RAG Retrieval Flow for Table Selection and Prompt Construction.**
This figure should show question normalisation, synonym expansion, query-intent decomposition, schema chunk caching, lexical and semantic scoring signals, value-hint matching, foreign-key graph expansion, selected prompt context, and retrieval diagnostics.

### 4.4 Model Design and Algorithmic Approach

The algorithm follows this sequence:

1. The user selects Gemini or Ollama and connects a SQLite database or uploads CSV files.
2. The user asks a natural-language question.
3. The backend extracts and caches table-level schema chunks from the database.
4. The Schema RAG layer retrieves the most relevant tables using lexical, semantic, synonym, value-hint, and foreign-key signals.
5. The retrieved schema context and question are sent to the selected LLM.
6. The LLM returns a candidate SQLite query.
7. The safety layer validates that the query is read-only and does not use prohibited operations.
8. SQLite executes the query using a read-only connection and authorizer.
9. The interface displays the result table, generated SQL, schema context, and retrieval evidence.

The model design deliberately separates **candidate generation** from **execution authority**. The LLM proposes SQL, but the application decides whether it is safe to execute. This separation is central to the reliability and ethics of the system.

**Figure 3. Streamlit Database Selection and Question Input Flow.**
Insert a screenshot of the deployed app showing provider/model controls, Gemini key status, Schema RAG settings, and the demo database selector.

**Figure 4. SQL Candidate, Safety Gate, and Answer Display Flow.**
Insert a screenshot showing a retail or university question, the generated SQL, and the result table. This figure demonstrates transparency because the SQL is visible rather than hidden behind the answer.

**Figure 5. Schema RAG Retrieval Diagnostics in the User Interface.**
Insert a screenshot of the retrieval report showing selected tables, matched terms, graph-neighbour expansion, schema recall, and prompt savings.

### 4.5 Integration of AI Paradigms

The system integrates multiple AI paradigms rather than relying on a single technique. **Knowledge representation** is used to model database schemas as structured entities and relationships. **Information retrieval** is used to select relevant schema context. **Generative AI** is used to translate natural language into SQL. **Symbolic reasoning** is used to enforce safety constraints and validate read-only behaviour. **Evaluation-driven AI engineering** is used to compare generated outputs with gold SQL results.

This integration is important because Text-to-SQL requires both creativity and precision. The LLM provides flexible language understanding, but retrieval and validation make the output more grounded, inspectable, and operationally controlled.

### 4.6 Design Decisions vs Implementation Details

Several design decisions shaped the project. The first design decision was to use **schema-only RAG** rather than sending raw rows to the model. The corresponding implementation detail is the `rag.py` module, which builds and ranks table-level schema chunks using local retrieval signals.

The second design decision was to enforce **read-only querying**. The implementation details include regex-based keyword blocking, optional `sqlglot` AST validation, a read-only SQLite URI, `PRAGMA query_only`, and a SQLite authorizer.

The third design decision was to support both **hosted and local LLMs**. The implementation details are Gemini API integration for hosted generation and Ollama/LangChain integration for local generation.

The fourth design decision was to keep the system reproducible. The implementation details include fixed benchmark cases in `evaluation/cases.json`, an automated evaluator in `scripts/evaluate_text_to_sql.py`, and output summaries in `evaluation/results/`.

## 5. Empirical Analysis and Results

### 5.1 Experimental Setup

The evaluation uses 12 benchmark questions across university, retail, and healthcare databases. Each case contains a natural-language question, database path, gold SQL query, expected relevant tables, and difficulty label. The evaluator executes both the gold SQL and the generated SQL, compares their outputs, measures latency, and records whether the generated query is safe and executable.

The evaluation can be run in gold mode or LLM mode. Gold mode verifies that the benchmark and execution environment are correct. LLM mode evaluates generated SQL from Gemini or Ollama. The current evidence includes a complete gold-baseline run, a complete Gemini 2.5 Flash run using multi-key quota failover, and complete local Ollama runs for `llama3:latest` and `gemma4:latest`. This process is represented separately in the `Offline Evaluation Workflow` page of `docs/supporting/architecture.drawio` because evaluation is a local validation workflow, not part of the normal user-facing tool flow.

### 5.2 Dataset Description

The benchmark covers three domains. The **university** dataset evaluates student majors, course averages, top students by average score, and grade distribution. The **retail** dataset evaluates completed order revenue by region and product category, support satisfaction by priority, and return reason counts. The **healthcare** dataset evaluates appointment status counts, treatment cost by hospital city, completed appointments by doctor specialty, and patient counts by city.

The benchmark includes easy, medium, and hard cases. Easy cases often require a single table and simple grouping. Medium cases require joins or aggregation. Hard cases require multiple joins, filters, and calculated measures such as revenue or treatment cost.

### 5.3 Evaluation Metrics

The evaluation uses the following metrics:

- **Safe SQL rate**: the proportion of generated SQL queries that pass deterministic safety validation.
- **Execution success rate**: the proportion of queries that execute without SQLite errors.
- **Value match**: whether generated result values match the gold result values after canonicalisation.
- **Row match**: whether generated rows match gold rows exactly after normalisation.
- **Exact result match**: whether rows and column names match the gold result exactly.
- **Schema table recall**: the proportion of expected relevant tables retrieved by Schema RAG.
- **Prompt schema saved**: the percentage reduction from full schema context to retrieved schema context.
- **Latency**: total time from evaluation start to result generation and comparison.

These metrics are appropriate because Text-to-SQL quality is not only about whether SQL executes. A query can be safe and executable but still semantically wrong. Therefore, result-based metrics provide stronger evidence than syntax validity alone.

### 5.4 Results

Table 1 summarises the available evaluation results.

| Model / Run | Schema RAG | Cases | Safe SQL | Execution Success | Value Match | Row Match | Exact Match | Avg Schema Recall | Avg Prompt Saved | Avg Latency |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Gold SQL baseline | Yes | 12 | 12/12 | 12/12 | 12/12 | 12/12 | 12/12 | 1.0 | 6.0% | 0.98 ms |
| Gemini 2.5 Flash, multi-key | Yes | 12 | 12/12 | 12/12 | 11/12 | 6/12 | 0/12 | 1.0 | 6.0% | 3.28 s |
| Ollama `llama3:latest` | Yes | 12 | 12/12 | 12/12 | 8/12 | 5/12 | 0/12 | 1.0 | 6.0% | 3.78 s |
| Ollama `gemma4:latest` | Yes | 12 | 10/12 | 10/12 | 8/12 | 3/12 | 0/12 | 1.0 | 6.0% | 5.65 s |

The gold SQL baseline confirms that the evaluation harness, datasets, and safety/execution stack work correctly. All benchmark gold queries passed validation and matched expected results. The Schema RAG layer retrieved all expected tables across the benchmark, giving an average recall of **1.0**.

The Gemini results show the strongest LLM performance in this benchmark, with 11 of 12 cases matching the gold values after canonicalisation. The local-model results show a practical trade-off: `llama3:latest` was safer and faster end-to-end, while `gemma4:latest` matched 8 of the 10 queries it successfully executed but produced two blocked outputs on harder retail revenue questions. Exact match remained **0/12** for all LLM runs because the metric requires values, rows, and column names to match the gold output exactly.

**Figure 6. Offline Evaluation Workflow and Result Summary.**
Insert the `Offline Evaluation Workflow` export from `docs/supporting/architecture.drawio` together with the evaluation summary from `evaluation/results/evaluation_gold.md` and the LLM comparison results from `evaluation/results/evaluation_llm_gemini_gemini_2_5_flash.md`, `evaluation/results/evaluation_llm_ollama_llama3_latest.md`, and `evaluation/results/evaluation_llm_ollama_gemma4_latest.md`. This figure belongs in the empirical results section because it supports the comparison between gold SQL, Gemini, and local Ollama models without mixing evaluation into the live user workflow.

### 5.5 Result Interpretation and Discussion

The strongest evidence of effectiveness is that the project implements a complete, reproducible pipeline: schema extraction, retrieval, generation interface, validation, execution, and result comparison. The gold baseline demonstrates that the benchmark is valid and that the safety and execution layers do not block legitimate analytical SQL.

The Schema RAG results are particularly encouraging because table recall was perfect across the benchmark. This suggests that the retrieval layer successfully identifies relevant schema context for questions involving single-table aggregation, multi-table joins, and domain-specific measures. However, the average prompt saving was modest because the benchmark databases are small. Larger databases would likely show greater benefits from retrieving only selected schema chunks.

The LLM results show that value-level correctness can be easier to achieve than exact structural matching. For example, a generated query may produce correct values but use different column aliases, omit expected rounding, or return rows in a different order, leading to a failed exact match. This highlights why multiple metrics are useful. The Gemini run also shows that external model APIs require operational controls such as quota failover, while local Ollama runs avoid hosted quota limits but may have lower accuracy or require more local compute.

From an ethical perspective, the results support the decision to display generated SQL and retrieval evidence. Users should be able to inspect how an answer was derived, especially when the result may inform decisions in education, retail, or healthcare administration.

## 6. Critical Reflection

### 6.1 Limitations of the Approach

The main limitation is that SQL correctness is not guaranteed. The LLM can generate syntactically valid SQL that answers a subtly different question, uses an incorrect join path, omits a filter, or applies the wrong aggregation. The safety layer can block destructive queries, but it cannot prove semantic correctness.

A second limitation is that the retrieval layer is heuristic. Synonym expansion, lexical scoring, n-gram similarity, hashed embeddings, and foreign-key expansion improve schema selection, but they may fail when the user uses unfamiliar terminology or when the schema uses opaque column names. The system does not yet include a governed semantic layer with formal metric definitions.

A third limitation is benchmark size. The 12-case benchmark covers several domains and difficulty levels, but it is small compared with public Text-to-SQL benchmarks. Therefore, the evaluation demonstrates prototype feasibility rather than broad generalisation.

### 6.2 Failure Cases

Potential failure cases include hallucinated column names, missing joins, incorrect join keys, ambiguous business terms, incorrect filters, and over-broad aggregations. For example, a question about "completed revenue" requires both a revenue calculation and a filter on completed orders. If the model retrieves the right tables but omits the status filter, the SQL may execute successfully but produce misleading results.

Operational failure cases are also important. The Gemini quota errors show that API-based AI systems can fail because of rate limits, billing constraints, or network availability. Local Ollama models avoid some of these constraints but require sufficient local compute and a running model server.

### 6.3 Trade-offs

The project involves several trade-offs. Sending more schema context may improve generation accuracy for small databases, but it increases prompt size, cost, latency, and information exposure. Schema RAG reduces unnecessary context and improves privacy, but it introduces the risk that a relevant table may be omitted.

Hosted LLMs may provide better generation quality and lower local compute requirements, but they raise governance, quota, and external dependency concerns. Local LLMs improve offline operation and data control, but may have lower accuracy and higher hardware requirements.

Strict safety controls reduce risk, but they may also reject legitimate advanced analytical queries if those queries contain keywords or constructs treated conservatively. This is an acceptable trade-off for a prototype intended for read-only decision support.

### 6.4 Scalability and Computational Constraints

The current system is suitable for small to medium SQLite databases. Schema chunk caching improves repeated-query performance by avoiding repeated schema extraction. However, very large schemas would require more robust indexing, persistent embeddings, database-level statistics, and perhaps a formal semantic layer to define measures and relationships.

LLM latency is also a scalability concern. The gold baseline executes in milliseconds, while LLM calls take hundreds or thousands of milliseconds and may be subject to quota limits. For production deployment, batching, caching, request throttling, model selection, and monitoring would be needed.

The current Streamlit Community deployment is best suited to Gemini because Ollama requires a local model server. A production local-LLM deployment would need managed infrastructure capable of serving the selected model reliably.

### 6.5 Alternative Methods and Improvements

Alternative methods may be more suitable in different contexts. A fine-tuned Text-to-SQL model could improve accuracy in a stable domain if sufficient labelled training data were available. A formal semantic layer could define business metrics such as revenue, retention, completion rate, or average treatment cost, reducing ambiguity in generated SQL. A vector database with learned embeddings could improve retrieval for larger and more semantically complex schemas.

Additional improvements include a SQL repair loop, human-in-the-loop confirmation for high-stakes queries, role-based access control, audit logging, de-identification of sensitive fields, query result explanations, chart generation, and evaluation on larger public benchmarks such as Spider. A stronger AST-level policy could also validate query structure more precisely than keyword checks.

## 7. GitHub Repository

### 7.1 Repository Link

The project repository is available at:

`https://github.com/tuannm3812/aipa-text-to-sql-agent`

The live Streamlit demo is available at:

`https://aipa-text-to-sql-agent.streamlit.app/`

### 7.2 Instructions to Run the Project

Set up the Python environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows, use `.venv\Scripts\activate` instead of `source .venv/bin/activate`.

For Gemini, create a `.env` file in the project root:

```bash
GEMINI_API_KEY=your_api_key_here
TEXT_TO_SQL_PROVIDER=gemini
```

For local Ollama:

```bash
ollama pull gemma3
ollama serve
```

Run the Streamlit application:

```bash
streamlit run app.py
```

Run the unit tests:

```bash
python3 -m unittest discover -s tests
```

Run the reproducible evaluation:

```bash
python3 scripts/evaluate_text_to_sql.py --mode gold
python3 scripts/evaluate_text_to_sql.py --mode llm --provider gemini --model gemini-2.5-flash --delay-seconds 15
python3 scripts/evaluate_text_to_sql.py --mode llm --provider ollama --model gemma3
```

Evaluation outputs are written to `evaluation/results/` as CSV and Markdown summaries.

## 8. Conclusion

### 8.1 Summary of Findings

This project demonstrates a functional Text-to-SQL decision support prototype that combines LLM generation with schema retrieval, deterministic validation, and read-only SQL execution. The system addresses a meaningful real-world problem: enabling non-technical users to query structured data while reducing the risks associated with unrestricted AI-generated SQL.

The evaluation shows that the benchmark and execution pipeline are reproducible and internally consistent. The gold baseline achieved complete success across all 12 benchmark cases, and Schema RAG retrieved all expected tables. LLM evaluation was limited by API quotas, which is itself an important finding about real deployment conditions.

### 8.2 Key Insights

The main AI-related insight is that Text-to-SQL systems require hybrid design. **Generative models** are useful for language-to-SQL translation, but they should be grounded by **retrieval**, constrained by **symbolic validation**, and assessed through **result-based evaluation**. The project also shows that privacy-aware design should be included from the beginning: schema-only prompting reduces unnecessary exposure of database content.

### 8.3 Future Work

Future work should focus on improving both accuracy and governance. Technically, the system could add persistent embedding-based retrieval, a formal semantic layer for business metrics, stronger SQL repair, and more comprehensive benchmark coverage. Operationally, it should add role-based access control, audit logs, query history, monitoring, rate-limit handling, and user feedback loops. For sensitive domains such as healthcare, future deployment would require privacy review, de-identification, access control, and human oversight before any real-world use.

## 9. Individual Contributions

The individual contributions were distributed across project framing, implementation, evaluation, documentation, and deployment support.

| Member | Student ID | Contributions |
|---|---:|---|
| Huy Duc Vu | 25728181 | Contributed to project framing, report development, responsible AI discussion, and evaluation interpretation. Supported documentation of problem significance, ethical implications, and future work. |
| Ngoc Bao Tran Nguyen | 25611551 | Contributed to frontend usability, Streamlit workflow, screenshots/demo preparation, and user-facing explanation of generated SQL and retrieval diagnostics. Supported testing of app interactions. |
| Manh Tuan Nguyen | 25739083 | Contributed to backend architecture, Text-to-SQL pipeline, LLM provider integration, Schema RAG design, GitHub repository organisation, and deployment configuration. |
| Nguyen Nghia Doan Dang | 26201968 | Contributed to benchmark dataset preparation, evaluation cases, gold SQL validation, automated evaluation scripts, result analysis, and reproducibility instructions. |

## 10. References

Brown, T. B., Mann, B., Ryder, N., Subbiah, M., Kaplan, J., Dhariwal, P., Neelakantan, A., Shyam, P., Sastry, G., Askell, A., Agarwal, S., Herbert-Voss, A., Krueger, G., Henighan, T., Child, R., Ramesh, A., Ziegler, D. M., Wu, J., Winter, C., ... Amodei, D. (2020). Language models are few-shot learners. *Advances in Neural Information Processing Systems, 33*, 1877-1901.

Lewis, P., Perez, E., Piktus, A., Petroni, F., Karpukhin, V., Goyal, N., Kuttler, H., Lewis, M., Yih, W., Rocktaschel, T., Riedel, S., & Kiela, D. (2020). Retrieval-augmented generation for knowledge-intensive NLP tasks. *Advances in Neural Information Processing Systems, 33*, 9459-9474.

National Institute of Standards and Technology. (2023). *Artificial Intelligence Risk Management Framework (AI RMF 1.0)*. U.S. Department of Commerce.

Weidinger, L., Mellor, J., Rauh, M., Griffin, C., Uesato, J., Huang, P., Cheng, M., Glaese, M., Balle, B., Kasirzadeh, A., Kenton, Z., Brown, S., Hawkins, W., Stepleton, T., Biles, C., Birhane, A., Haas, J., Rimell, L., Hendricks, L. A., ... Gabriel, I. (2021). Ethical and social risks of harm from language models. *arXiv preprint arXiv:2112.04359*.

Yu, T., Zhang, R., Yang, K., Yasunaga, M., Wang, D., Li, Z., Ma, J., Li, I., Yao, Q., Roman, S., Zhang, Z., & Radev, D. (2018). Spider: A large-scale human-labeled dataset for complex and cross-domain semantic parsing and Text-to-SQL task. *Proceedings of the 2018 Conference on Empirical Methods in Natural Language Processing*, 3911-3921.

Zhong, V., Xiong, C., & Socher, R. (2017). Seq2SQL: Generating structured queries from natural language using reinforcement learning. *arXiv preprint arXiv:1709.00103*.
