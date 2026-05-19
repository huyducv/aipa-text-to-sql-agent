# Text-to-SQL Evaluation Results

- Cases: 12
- Safe SQL rate: 10/12
- Execution success rate: 10/12
- Value match: 8/12
- Row match: 3/12
- Exact result match: 0/12
- Average schema table recall: 1.0
- Average prompt schema saved: 6.0%
- Average latency: 5651.83 ms

| Case | Dataset | Difficulty | Safe | Executed | Value Match | Row Match | Exact Match | Schema Recall | Prompt Saved | Latency ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| university_major_counts | university | easy | True | True | True | True | False | 1.0 | 0.0% | 7079.67 |
| university_average_score_by_course | university | medium | True | True | False | False | False | 1.0 | 0.0% | 1770.44 |
| university_top_students_by_average_score | university | medium | True | True | True | False | False | 1.0 | 0.0% | 6610.16 |
| university_grade_distribution | university | easy | True | True | True | True | False | 1.0 | 0.0% | 2557.61 |
| retail_revenue_by_region | retail | hard | False | False | False | False | False | 1.0 | 25.7% | 11095.24 |
| retail_revenue_by_category | retail | hard | False | False | False | False | False | 1.0 | 4.1% | 11603.88 |
| retail_support_satisfaction_by_priority | retail | medium | True | True | False | False | False | 1.0 | 22.9% | 4058.18 |
| retail_return_reason_counts | retail | easy | True | True | True | False | False | 1.0 | 19.0% | 5381.16 |
| healthcare_appointments_by_status | healthcare | easy | True | True | True | True | False | 1.0 | 0.0% | 915.13 |
| healthcare_treatment_cost_by_city | healthcare | hard | True | True | True | False | False | 1.0 | 0.0% | 8323.35 |
| healthcare_completed_appointments_by_specialty | healthcare | medium | True | True | True | False | False | 1.0 | 0.0% | 7526.97 |
| healthcare_patient_count_by_city | healthcare | easy | True | True | True | False | False | 1.0 | 0.0% | 900.21 |
