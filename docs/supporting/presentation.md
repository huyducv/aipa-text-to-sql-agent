# AT3 Presentation: Enterprise Text-to-SQL Agent

Target length: 7 minutes presentation plus 1 minute Q&A.

## Slide Content

### Slide 1: Enterprise Text-to-SQL Agent

**Natural-language analytics for safe SQLite decision support**

- Live demo: `https://aipa-text-to-sql-agent.streamlit.app/`
- Repository: `https://github.com/tuannm3812/aipa-text-to-sql-agent`
- Group Number: to be confirmed by the submission portal

| Member | Student ID |
|---|---:|
| Huy Duc Vu | 25728181 |
| Ngoc Bao Tran Nguyen | 25611551 |
| Manh Tuan Nguyen | 25739083 |
| Nguyen Nghia Doan Dang | 26201968 |

### Slide 2: Problem and Goal

**Problem:** useful data is stored in databases, but many users cannot write SQL.

| Current workflow | Risk or cost |
|---|---|
| Ask analyst for SQL | Slow decision cycle |
| Copy data into spreadsheets | Error-prone and hard to govern |
| Let LLM query directly | Unsafe without validation |
| Hide generated SQL | Low transparency |

**Goal:** let users ask questions in natural language while keeping query generation grounded, visible, evaluated, and read-only.

### Slide 3: AI Methods Used

| AI paradigm | Role in the system |
|---|---|
| Knowledge representation | SQLite schemas are represented as tables, columns, DDL, and foreign-key relationships |
| Retrieval augmented generation | Schema RAG selects the most relevant table context before prompting |
| Generative AI | Gemini or Ollama translates the question into SQLite SQL |
| Logic-based reasoning | Safety validators and SQLite authorizer enforce read-only execution |
| Empirical evaluation | Generated results are compared with gold SQL answers |

### Slide 4: System Workflow

Use exported diagram: `docs/supporting/architecture.drawio` -> `Presentation Architecture`.

```text
User question
  -> Streamlit interface
  -> SQLite DB or CSV upload
  -> Schema extraction
  -> Hybrid Schema RAG
  -> Gemini / Ollama SQL generation
  -> SQL safety validation
  -> Read-only SQLite execution
  -> Result table + generated SQL + retrieval evidence
```

**Key design point:** the LLM proposes SQL, but Python decides whether it is safe to execute.

### Slide 5: Prototype Features

Use app screenshots: database selector, generated SQL answer, retrieved schema context.

| Feature | Evidence to show |
|---|---|
| Streamlit chat-style interface | User asks a natural-language question |
| Demo databases | University, retail, healthcare |
| Gemini and Ollama support | Provider/model controls |
| Schema RAG | Selected tables, matched terms, prompt savings |
| Transparent SQL | Generated query is displayed |
| Read-only execution | Safety layer blocks unsafe SQL |

### Slide 6: Evaluation Design

| Item | Design |
|---|---|
| Benchmark size | 12 cases |
| Domains | University, retail, healthcare |
| Difficulty | Easy, medium, hard |
| Reference answer | Gold SQL for every question |
| Main correctness metric | Value match |
| Strict metric | Exact result match |
| Safety metrics | Safe SQL and execution success |
| RAG metric | Schema table recall |

**Evaluation command examples**

```bash
python3 scripts/evaluate_text_to_sql.py --mode gold
python3 scripts/evaluate_text_to_sql.py --mode llm --provider gemini --model gemini-2.5-flash --max-cases 12 --max-retries 1 --retry-base-seconds 5
python3 scripts/evaluate_text_to_sql.py --mode llm --provider ollama --model llama3:latest --resume
python3 scripts/evaluate_text_to_sql.py --mode llm --provider ollama --model gemma4:latest --resume
```

### Slide 7: Results Overview

| Run | Cases | Safe SQL | Executed | Value Match | Row Match | Exact Match | Avg Latency |
|---|---:|---:|---:|---:|---:|---:|---:|
| Gold SQL baseline | 12 | 12/12 | 12/12 | 12/12 | 12/12 | 12/12 | 0.98 ms |
| Gemini 2.5 Flash, multi-key | 12 | 12/12 | 12/12 | 11/12 | 6/12 | 0/12 | 3.28 s |
| Ollama `llama3:latest` | 12 | 12/12 | 12/12 | 8/12 | 5/12 | 0/12 | 3.78 s |
| Ollama `gemma4:latest` | 12 | 10/12 | 10/12 | 8/12 | 3/12 | 0/12 | 5.65 s |

### Slide 8: Chart 1 - Value Match

Use this chart as the main accuracy plot.

```text
Value match out of 12

Gold SQL baseline        12/12 | ############
Gemini 2.5 Flash         11/12 | ###########.
Ollama llama3:latest      8/12 | ########....
Ollama gemma4:latest      8/12 | ########....
```

**Takeaway:** Gemini was strongest on value correctness. Local models still answered many cases correctly, but with lower reliability.

### Slide 9: Chart 2 - Safety and Execution

Use this chart to show why safety evaluation matters.

```text
Safe SQL / Executed queries out of 12

Gold SQL baseline        12 / 12 | ############
Gemini 2.5 Flash         12 / 12 | ############
Ollama llama3:latest     12 / 12 | ############
Ollama gemma4:latest     10 / 10 | ##########..
```

**Blocked cases:** `gemma4:latest` produced unsafe/truncated SQL for two hard retail revenue questions.

### Slide 10: Chart 3 - Latency

```text
Average latency

Gold SQL baseline        0.001 s | .
Gemini 2.5 Flash         3.28  s | ######
Ollama llama3:latest     3.78  s | #######
Ollama gemma4:latest     5.65  s | ##########
```

**Takeaway:** LLM quality must be judged together with latency and operational constraints.

### Slide 11: Interpretation

| Finding | Meaning |
|---|---|
| Gold baseline reached 12/12 exact match | Benchmark, gold SQL, and evaluator are valid |
| Schema recall was 1.0 across runs | RAG retrieved expected relevant tables |
| Gemini reached 11/12 value match | Hosted LLM gave the strongest generated-SQL result |
| Exact match was 0/12 for LLMs | Exact matching is strict about aliases, row order, and column names |
| Multi-key Gemini removed quota failures | Deployment reliability needs operational engineering |
| Llama 3 executed all cases safely | Stronger local default than Gemma 4 for this benchmark |

### Slide 12: Ethics, Limits, and Future Work

| Area | Current control | Future improvement |
|---|---|---|
| Privacy | Send schema metadata, not raw rows | Role-based access and de-identification |
| Safety | Read-only SQL validation and authorizer | Stronger AST policy and audit logging |
| Correctness | Gold SQL benchmark | Larger benchmark and user feedback loop |
| Reliability | Gemini key failover | Monitoring, caching, retry policy |
| Usability | SQL and retrieval evidence shown | Charts, explanations, query history |

### Slide 13: Contributions

| Member | Main contribution areas |
|---|---|
| Huy Duc Vu | Project framing, report development, responsible AI discussion, evaluation interpretation |
| Ngoc Bao Tran Nguyen | Frontend usability, Streamlit workflow, screenshots/demo preparation, user-facing explanation |
| Manh Tuan Nguyen | Backend pipeline, LLM integration, Schema RAG, repository organisation, deployment configuration |
| Nguyen Nghia Doan Dang | Benchmark datasets, evaluation cases, gold SQL validation, evaluation scripts, reproducibility instructions |

### Slide 14: Closing

**Conclusion:** Text-to-SQL is useful only when generation is grounded, visible, safe, and evaluated.

**Project evidence**

- Working Streamlit demo
- Refactored backend package
- Schema RAG and safety validation
- 12-case benchmark across three domains
- Gemini and Ollama evaluation results
- Reproducible docs and deployment checklist

## Presentation Transcript

### Slide 1

Good morning. Our project is the Enterprise Text-to-SQL Agent, a decision-support prototype that lets users ask questions about SQLite data in natural language. The application is deployed with Streamlit, and the repository contains the app, backend package, evaluation cases, results, and documentation.

### Slide 2

The problem we address is that valuable organisational data is often stored in relational databases, but many users cannot write SQL. The usual workaround is to ask analysts, copy data into spreadsheets, or rely on direct LLM outputs. Each option has a problem: it can be slow, error-prone, unsafe, or difficult to audit. Our goal is not just to make a chat interface. Our goal is to make natural-language analytics safer, more transparent, and empirically evaluated.

### Slide 3

The system combines several AI paradigms. First, it treats the database schema as structured knowledge: tables, columns, DDL, and relationships. Second, it uses retrieval augmented generation to select only the schema context relevant to the question. Third, it uses a large language model, either Gemini or a local Ollama model, to generate SQL. Finally, it uses deterministic safety rules and SQLite controls to decide whether that SQL can execute.

### Slide 4

The workflow starts with a user question in Streamlit. The user chooses a demo SQLite database, uploads a database, or uploads CSV files. The backend extracts schema metadata and uses hybrid Schema RAG to retrieve relevant tables. The selected schema and question are sent to the LLM, which proposes a SQLite query. That query is validated before execution. Only read-only SQL is allowed. If it passes, SQLite executes locally and the app displays the result table, generated SQL, and retrieval evidence.

### Slide 5

The prototype supports university, retail, and healthcare demo data. It also supports Gemini as a hosted model and Ollama for local inference. The app shows the generated SQL rather than hiding it, because users need to inspect how an answer was produced. It also shows retrieval diagnostics, such as selected tables, matched terms, schema recall, and prompt savings.

### Slide 6

For evaluation, we created 12 benchmark questions across the three domains. Each question has a gold SQL query, expected relevant tables, and a difficulty label. We evaluate not only whether SQL runs, but whether the result matches the gold query. The most useful correctness metric is value match. Exact match is stricter because it also checks result shape, row order, and column names.

### Slide 7

The results show four runs. The gold SQL baseline achieved 12 out of 12 on every metric, which validates the benchmark and evaluator. Gemini 2.5 Flash achieved 11 out of 12 value match after multi-key quota failover. Local Llama 3 and Gemma 4 both reached 8 out of 12 value match, but Llama 3 produced safe executable SQL for all 12 cases, while Gemma 4 had two blocked outputs.

### Slide 8

This value-match chart is the clearest accuracy comparison. The gold baseline is perfect by design. Gemini is strongest among the generated-SQL runs, with 11 of 12 cases matching the gold values. Both local models are useful but less reliable on this benchmark, each matching 8 of 12.

### Slide 9

Safety and execution tell a different story. Gemini and Llama 3 both produced safe executable SQL for all cases. Gemma 4 produced two unsafe or incomplete outputs on harder retail revenue questions, and the safety layer blocked them. This is exactly why the LLM should not have direct execution authority.

### Slide 10

Latency is also important. The gold SQL baseline runs in about one millisecond because it is just SQLite execution. LLM calls take seconds. Gemini averaged about 3.28 seconds, Llama 3 about 3.78 seconds, and Gemma 4 about 5.65 seconds. This means production systems need caching, monitoring, retry policies, and careful model selection.

### Slide 11

The main interpretation is that Text-to-SQL cannot rely on generation alone. The benchmark and gold baseline prove that the evaluation stack works. Schema recall of 1.0 shows that RAG retrieved the expected relevant tables. Gemini gave the strongest value correctness. Exact match remained zero for LLM runs because generated SQL often used different aliases, rounding, or order while still returning useful values.

### Slide 12

There are also ethical and operational limits. The system reduces privacy risk by sending schema metadata rather than raw rows to the LLM. It reduces safety risk by allowing only read-only SQL. However, generated SQL can still be semantically wrong, so high-stakes use would need human review, access control, audit logs, larger benchmarks, and stronger monitoring.

### Slide 13

Our team contributions covered the full project lifecycle: project framing and report writing, frontend usability and screenshots, backend pipeline and deployment, and benchmark/evaluation design. The final repository connects those contributions through code, results, documentation, and the live app.

### Slide 14

To conclude, this project shows that a practical Text-to-SQL assistant needs four things: grounding, transparency, safety, and evaluation. The LLM translates language into SQL, but the surrounding system makes that translation usable and responsible. Thank you.

## Likely Q&A

**Q: Why not send all data to the LLM?**
A: The system sends schema metadata only, reducing privacy exposure and prompt size.

**Q: Is the SQL always correct?**
A: No. The model can be wrong, so the app exposes generated SQL and the project evaluates results against gold SQL.

**Q: Why is exact match 0/12 for LLMs if value match is high?**
A: Exact match checks column names, row structure, and ordering. A generated query can return the right values but fail exact shape comparison.

**Q: Why support Ollama?**
A: Ollama enables local/offline inference and stronger data-governance options, although it needs local compute.

**Q: How is this AI rather than simple software?**
A: It combines schema representation, retrieval augmented generation, LLM semantic parsing, and logic-based safety reasoning.
