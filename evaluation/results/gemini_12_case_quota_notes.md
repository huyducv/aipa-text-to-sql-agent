# Gemini 12-Case Evaluation Notes

Run command:

```bash
python3 scripts/evaluate_text_to_sql.py --mode llm --provider gemini --max-cases 12 --max-retries 1 --retry-base-seconds 5
```

Output files:

- `evaluation/results/evaluation_llm_gemini_gemini_2_5_flash.csv`
- `evaluation/results/evaluation_llm_gemini_gemini_2_5_flash.md`

## Key Rotation

At the time of this run, `.env` contained one configured Gemini key source:

- `GOOGLE_API_KEY`

No multi-key variable such as `GOOGLE_API_KEYS` or `GEMINI_API_KEYS` was configured, so the Gemini manager did not have another key available for failover. The quota failures were retried, but the retry used the same configured key.

Key rotation belongs in the Gemini manager/LLM layer rather than only in the evaluation script. That way the evaluator, Streamlit app, notebooks, and any direct `generate_sql` calls all get the same quota handling. The manager now persists for the Python process, so once a quota-limited key is skipped it can continue from the next key on later cases instead of restarting from the first key each time.

To test key rotation, configure multiple keys like this:

```env
GOOGLE_API_KEYS="KEY_1,KEY_2,KEY_3"
```

Indexed key variables are also supported:

```env
GOOGLE_API_KEY="KEY_0"
GOOGLE_API_KEY_1="KEY_1"
GOOGLE_API_KEY_2="KEY_2"
```

The manager will then move to the next key on `429` or `492`, and retry/reset the current key once on `503`.

## 12-Case Gemini Results

- Safe SQL: `9/12`
- Execution OK: `9/12`
- Value match: `8/12`
- Row match: `5/12`
- Exact result match: `0/12`
- Average latency: `5146.77 ms`

Quota-error cases:

- `retail_support_satisfaction_by_priority`
- `retail_return_reason_counts`
- `healthcare_appointments_by_status`

Each quota-error row reported `429 RESOURCE_EXHAUSTED`.

## Comparison With Local LLM Runs

For the same first 12 cases:

| Provider/model | Value match |
|---|---:|
| Gemini `gemini-2.5-flash` | `8/12` |
| Ollama `gemma4_latest` | `8/12` |
| Ollama `llama3_latest` | `8/12` |

Exact match was `0/12` across these runs, which appears to reflect strict comparison of SQL/result shape such as aliases, ordering, or column names. Value match is the more useful signal for answer correctness in this slice.

## Should We Rerun?

Yes, but only after adding multiple Gemini keys. Rerunning now with the same single quota-exhausted key is likely to hit the same quota failures.

Recommended rerun command after adding keys:

```bash
python3 scripts/evaluate_text_to_sql.py --mode llm --provider gemini --max-cases 12 --max-retries 1 --retry-base-seconds 5
```

## Rerun With 10 Keys

After adding indexed keys in `.env`, the manager detected 10 Gemini keys and the 12-case run was repeated with the same command.

Rerun results:

- Safe SQL: `12/12`
- Execution OK: `12/12`
- Value match: `11/12`
- Row match: `6/12`
- Exact result match: `0/12`
- Quota errors: `0`
- Average latency: `3277.83 ms`

The previous quota-error cases all executed successfully on rerun:

- `retail_support_satisfaction_by_priority`
- `retail_return_reason_counts`
- `healthcare_appointments_by_status`
