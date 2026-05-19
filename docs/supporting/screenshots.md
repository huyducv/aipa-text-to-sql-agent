# Screenshot Review Notes

Use screenshots from the deployed Streamlit app and local evaluation output as evidence in the report and presentation. The screenshots should show the current workflow: database selection, Schema RAG, generated SQL, local execution results, and evaluation evidence.

## Recommended Captions

1. **Application UI and demo database workflow**
   - Shows the deployed Streamlit interface, Gemini model selection, API key status, Schema RAG toggle, demo database selector, and sample question workflow.
   - Use in the presentation when introducing the prototype.

2. **Natural-language query result and generated SQL**
   - Shows the Retail Analytics demo answering: "Which return reasons occur most often?"
   - Result table: Changed Mind, Other, Late Delivery, Damaged, Wrong Size.
   - Generated SQL demonstrates transparent LLM output before/after execution.
   - Use in the report methodology/results section.

3. **Retrieved schema context**
   - Shows only selected relevant schema snippets, such as `returns`, `customer_support_tickets`, and `customers`.
   - This demonstrates schema grounding and RAG-based context reduction.
   - Use when explaining the difference between static schema injection and RAG.

4. **Evaluation dashboard**
   - Shows Gold SQL baseline metrics:
     - Safe SQL: 12/12
     - Executed: 12/12
     - Value match: 12/12
     - Row match: 12/12
     - Exact match: 12/12
     - Schema recall: 1.00
   - Use in the empirical evaluation section.

5. **LLM evaluation comparison**
   - Shows or reproduces the model comparison from the project README:
     - Gemini 2.5 Flash multi-key: 11/12 value match.
     - Ollama `llama3:latest`: 8/12 value match, 12/12 safe and executed.
     - Ollama `gemma4:latest`: 8/12 value match overall, 8/10 among executed queries.
   - Use to explain hosted vs local model trade-offs.

6. **Safety or error handling example**
   - Optional but useful if time allows.
   - Show an unsafe or invalid generated query being blocked, or a quota/API error being displayed without executing SQL.
   - Use in the limitations or ethics section to show that the project handles failure visibly.

## Notes

- The current local verification command is `python3 scripts/evaluate_text_to_sql.py --mode gold`, which writes `evaluation/results/evaluation_gold.md` and `evaluation/results/evaluation_gold.csv`.
- If the RAG report appears stale after deployment, refresh/redeploy and ask a new question so Streamlit loads the latest code.
- The screenshots should be inserted into the final PDF and slide deck rather than referenced only as external files.
- Avoid showing real API keys, local filesystem paths that are not relevant, or private uploaded data in screenshots.
