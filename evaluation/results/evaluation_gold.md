# Text-to-SQL Evaluation Results

- Cases: 12
- Safe SQL rate: 12/12
- Execution success rate: 12/12
- Value match: 12/12
- Row match: 12/12
- Exact result match: 12/12
- Average schema table recall: 1.0
- Average prompt schema saved: 6.0%
- Average latency: 0.98 ms

| Case | Dataset | Difficulty | Safe | Executed | Value Match | Row Match | Exact Match | Schema Recall | Prompt Saved | Latency ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| university_major_counts | university | easy | True | True | True | True | True | 1.0 | 0.0% | 3.54 |
| university_average_score_by_course | university | medium | True | True | True | True | True | 1.0 | 0.0% | 0.66 |
| university_top_students_by_average_score | university | medium | True | True | True | True | True | 1.0 | 0.0% | 0.6 |
| university_grade_distribution | university | easy | True | True | True | True | True | 1.0 | 0.0% | 0.33 |
| retail_revenue_by_region | retail | hard | True | True | True | True | True | 1.0 | 25.7% | 1.62 |
| retail_revenue_by_category | retail | hard | True | True | True | True | True | 1.0 | 4.1% | 0.96 |
| retail_support_satisfaction_by_priority | retail | medium | True | True | True | True | True | 1.0 | 22.9% | 0.45 |
| retail_return_reason_counts | retail | easy | True | True | True | True | True | 1.0 | 19.0% | 0.38 |
| healthcare_appointments_by_status | healthcare | easy | True | True | True | True | True | 1.0 | 0.0% | 1.25 |
| healthcare_treatment_cost_by_city | healthcare | hard | True | True | True | True | True | 1.0 | 0.0% | 0.7 |
| healthcare_completed_appointments_by_specialty | healthcare | medium | True | True | True | True | True | 1.0 | 0.0% | 0.53 |
| healthcare_patient_count_by_city | healthcare | easy | True | True | True | True | True | 1.0 | 0.0% | 0.78 |
