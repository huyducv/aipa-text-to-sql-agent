# Text-to-SQL Evaluation Results

- Cases: 12
- Safe SQL rate: 12/12
- Execution success rate: 12/12
- Value match: 8/12
- Row match: 5/12
- Exact result match: 0/12
- Average schema table recall: 1.0
- Average prompt schema saved: 6.0%
- Average latency: 3782.75 ms

| Case | Dataset | Difficulty | Safe | Executed | Value Match | Row Match | Exact Match | Schema Recall | Prompt Saved | Latency ms |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| university_major_counts | university | easy | True | True | True | True | False | 1.0 | 0.0% | 12148.99 |
| university_average_score_by_course | university | medium | True | True | True | True | False | 1.0 | 0.0% | 2028.16 |
| university_top_students_by_average_score | university | medium | True | True | True | False | False | 1.0 | 0.0% | 1793.31 |
| university_grade_distribution | university | easy | True | True | True | True | False | 1.0 | 0.0% | 2831.22 |
| retail_revenue_by_region | retail | hard | True | True | False | False | False | 1.0 | 25.7% | 6643.74 |
| retail_revenue_by_category | retail | hard | True | True | False | False | False | 1.0 | 4.1% | 4709.26 |
| retail_support_satisfaction_by_priority | retail | medium | True | True | False | False | False | 1.0 | 22.9% | 3087.05 |
| retail_return_reason_counts | retail | easy | True | True | True | False | False | 1.0 | 19.0% | 2890.41 |
| healthcare_appointments_by_status | healthcare | easy | True | True | True | True | False | 1.0 | 0.0% | 1296.77 |
| healthcare_treatment_cost_by_city | healthcare | hard | True | True | False | False | False | 1.0 | 0.0% | 4352.99 |
| healthcare_completed_appointments_by_specialty | healthcare | medium | True | True | True | True | False | 1.0 | 0.0% | 2285.11 |
| healthcare_patient_count_by_city | healthcare | easy | True | True | True | False | False | 1.0 | 0.0% | 1325.97 |
