# Text-to-SQL Evaluation Results

- Cases: 12
- Safe SQL rate: 12/12
- Execution success rate: 12/12
- Value match: 11/12
- Row match: 6/12
- Exact result match: 0/12
- Average schema table recall: 1.0
- Average prompt schema saved: 6.0%
- Average latency: 3277.83 ms

| Case | Dataset | Difficulty | Safe | Executed | Value Match | Row Match | Exact Match | Schema Recall | Prompt Saved | Latency ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| university_major_counts | university | easy | True | True | True | True | False | 1.0 | 0.0% | 5425.83 |
| university_average_score_by_course | university | medium | True | True | False | False | False | 1.0 | 0.0% | 2914.75 |
| university_top_students_by_average_score | university | medium | True | True | True | False | False | 1.0 | 0.0% | 2913.02 |
| university_grade_distribution | university | easy | True | True | True | True | False | 1.0 | 0.0% | 3012.55 |
| retail_revenue_by_region | retail | hard | True | True | True | True | False | 1.0 | 25.7% | 3383.32 |
| retail_revenue_by_category | retail | hard | True | True | True | True | False | 1.0 | 4.1% | 3180.44 |
| retail_support_satisfaction_by_priority | retail | medium | True | True | True | False | False | 1.0 | 22.9% | 4703.23 |
| retail_return_reason_counts | retail | easy | True | True | True | False | False | 1.0 | 19.0% | 3183.7 |
| healthcare_appointments_by_status | healthcare | easy | True | True | True | True | False | 1.0 | 0.0% | 2004.02 |
| healthcare_treatment_cost_by_city | healthcare | hard | True | True | True | False | False | 1.0 | 0.0% | 3628.14 |
| healthcare_completed_appointments_by_specialty | healthcare | medium | True | True | True | True | False | 1.0 | 0.0% | 3130.9 |
| healthcare_patient_count_by_city | healthcare | easy | True | True | True | False | False | 1.0 | 0.0% | 1854.1 |
