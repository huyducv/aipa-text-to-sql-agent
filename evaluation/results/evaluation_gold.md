# Text-to-SQL Evaluation Results

- Cases: 2
- Safe SQL rate: 2/2
- Execution success rate: 2/2
- Value match: 2/2
- Row match: 2/2
- Exact result match: 2/2
- Average schema table recall: 1.0
- Average prompt schema saved: 0.0%
- Average latency: 1.55 ms

| Case | Dataset | Difficulty | Safe | Executed | Value Match | Row Match | Exact Match | Schema Recall | Prompt Saved | Latency ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| university_major_counts | university | easy | True | True | True | True | True | 1.0 | 0.0% | 2.48 |
| university_average_score_by_course | university | medium | True | True | True | True | True | 1.0 | 0.0% | 0.62 |
