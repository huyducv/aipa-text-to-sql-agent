from __future__ import annotations

import os
import re
from typing import Any

from .config import DEFAULT_MODEL_NAME, DEFAULT_OLLAMA_MODEL, DEFAULT_PROVIDER
from .env import load_env
from .gemini_manager import get_default_gemini_manager

SQL_TRANSLATION_SYSTEM_PROMPT = """\
You are an expert data analyst and SQL translator.
Your ONLY job is to translate the user's question into a SINGLE SQLite SELECT query.

SQLITE DIALECT (must follow):
- Generate SQLite-compatible SQL only.
- Do NOT use EXTRACT, DATE_TRUNC, ILIKE, INTERVAL, FILTER, DISTINCT ON.
- For dates/timestamps use SQLite functions like: strftime('%Y', col), strftime('%Y-%m', col), date(col), datetime(col).

If the question cannot be answered using the schema, output exactly:
SELECT 'UNANSWERABLE_WITH_GIVEN_SCHEMA' AS error;

If the user requests any data modification (update/insert/delete/drop/alter/create/etc), output exactly:
SELECT 'BLOCKED_UNSAFE_SQL' AS error;

If the user asks for ambigious/ unclear/ not relevant questions and there is no relevant  column in the schema to answer it, output exactly
SELECT 'UNANSWERABLE_WITH_GIVEN_SCHEMA' AS error;

Rules (must follow):
- Output ONLY the SQL query text. No markdown fences, no explanations.
- Use ONLY the tables and columns that exist in the provided schema.
- Generate READ-ONLY SQL: SELECT queries only.
- Do NOT use any data-modifying statements: INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, REPLACE, TRUNCATE, VACUUM, PRAGMA, ATTACH, DETACH.
- Do NOT repeat or restate the schema/DDL. Never output CREATE TABLE or column lists.
- Output must start with SELECT (or WITH) and contain exactly one query.
- Do NOT reference sqlite_master or any internal SQLite tables.
- Prefer simple SQL compatible with SQLite.

*** CRITICAL TEXT SEARCHING RULES ***
1. CASE INSENSITIVITY: SQLite '=' is case-sensitive. Whenever you filter by text, you MUST make it case-insensitive. Use `LOWER(column) = LOWER('value')` or `LIKE`.
2. PARTIAL MATCHES: When a user searches for a location, venue, or keyword (e.g., 'bathurst' or 'marine rescue'), assume it is a partial match. ALWAYS use `LIKE '%keyword%'` to search within fields like addresses, names, or descriptions.

ADDITIONAL RULES - DIFFERENCE / DELTA QUESTIONS (must follow):
- The word "difference" can mean either:
  (A) show both groups for comparison, OR
  (B) return a single numeric delta (X - Y).
- If the question asks "What is the difference ..." and does NOT ask to "show/compare both", default to returning a single delta value.
- If the question asks "Do A incur higher than B" or "compare A vs B", return both groups (and optionally the delta).

ADDITONAL RULES - COMPARATIVE QUESTIONS (must follow):
- If the question compares groups/ objects (keywords: "than", "versus", "vs", "compared to", "difference between", "higher/lower than"),
  you MUST return results for ALL compared groups/ objects in one query (not just one side).
- Prefer a single query using CASE buckets + GROUP BY to compute the metric per group.
- If a numeric difference is requested/implicit, you may additionally output (or compute) the difference, but still include both group values.
- Do NOT answer only one cohort unless the user explicitly asks for only that cohort.
"""


def _load_gemini_sdk() -> tuple[str, Any, Any | None]:
    try:
        from google import genai  # type: ignore
        from google.genai import types  # type: ignore
        return "google-genai", genai, types
    except ModuleNotFoundError as e:  # pragma: no cover
        try:
            import google.generativeai as legacy_genai  # type: ignore
        except ModuleNotFoundError:
            raise ModuleNotFoundError(
                "Gemini support requires google-genai. Run: pip install google-genai"
            ) from e
        return "google-generativeai", legacy_genai, None


def _load_ollama_sdk() -> tuple[Any, Any, Any]:
    try:
        from langchain_ollama import ChatOllama  # type: ignore
        from langchain_core.messages import HumanMessage, SystemMessage  # type: ignore
    except ModuleNotFoundError as e:  # pragma: no cover
        raise ModuleNotFoundError(
            "Ollama support requires langchain-ollama and langchain-core. "
            "Run: pip install langchain-ollama langchain-core"
        ) from e
    return ChatOllama, HumanMessage, SystemMessage


def _extract_sql_from_text(raw_output: str) -> str:
    raw_output = raw_output.strip()
    blocks = re.findall(
        r"```(?:sql)?\s*(.*?)\s*```",
        raw_output,
        flags=re.IGNORECASE | re.DOTALL,
    )
    for block in blocks:
        if re.search(r"(?is)^\s*(SELECT|WITH)\b", block):
            return block.strip()
    if blocks:
        return blocks[0].strip()

    match = re.search(r"(?is)\b(SELECT|WITH)\b.*?;?$", raw_output)
    if match:
        return raw_output[match.start():].strip()
    return raw_output


def generate_sql(
    user_question: str,
    schema_text: str,
    *,
    model_name: str = DEFAULT_MODEL_NAME,
    provider: str | None = None,
) -> str:
    """Call Gemini or Ollama to generate SQLite SQL from a question and schema."""
    load_env()
    selected_provider = (provider or os.environ.get("TEXT_TO_SQL_PROVIDER") or DEFAULT_PROVIDER).strip().lower()
    prompt = f"""\
### SQLite schema (DDL)
{schema_text}

### User question
{user_question}
"""

    if selected_provider == "gemini":
        sdk_name, genai, genai_types = _load_gemini_sdk()
        key_manager = get_default_gemini_manager()

        def generate_with_key(api_key: str) -> str:
            if sdk_name == "google-genai":
                client = genai.Client(api_key=api_key)
                response = client.models.generate_content(
                    model=model_name or DEFAULT_MODEL_NAME,
                    contents=prompt,
                    config=genai_types.GenerateContentConfig(
                        temperature=0.0,
                        max_output_tokens=512,
                        system_instruction=SQL_TRANSLATION_SYSTEM_PROMPT,
                    ),
                )
            else:
                genai.configure(api_key=api_key)
                model = genai.GenerativeModel(
                    model_name or DEFAULT_MODEL_NAME,
                    system_instruction=SQL_TRANSLATION_SYSTEM_PROMPT,
                )
                response = model.generate_content(
                    contents=prompt,
                    generation_config={"temperature": 0.0, "max_output_tokens": 512},
                )
            return _extract_sql_from_text(str(response.text or ""))

        return key_manager.run(generate_with_key)

    if selected_provider == "ollama":
        ChatOllama, HumanMessage, SystemMessage = _load_ollama_sdk()
        model = ChatOllama(
            model=model_name or DEFAULT_OLLAMA_MODEL,
            temperature=0.0,
            num_predict=512,
        )
        response = model.invoke(
            [
                SystemMessage(content=SQL_TRANSLATION_SYSTEM_PROMPT),
                HumanMessage(content=prompt),
            ]
        )
        return _extract_sql_from_text(str(response.content or ""))

    raise ValueError("Unsupported provider. Use 'gemini' or 'ollama'.")
