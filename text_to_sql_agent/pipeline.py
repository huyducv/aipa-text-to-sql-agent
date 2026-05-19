from __future__ import annotations

import os
from pathlib import Path

from .config import DEFAULT_MODEL_NAME, DEFAULT_RAG_TOP_K
from .execution import execute_query
from .ingestion import ingest_csvs_to_db
from .llm import generate_sql
from .rag import retrieve_relevant_schema
from .safety import is_safe_query
from .schema import get_schema
from .types import QueryResult


def ask_database(
    question: str,
    *,
    db_path: str = "university_agent.db",
    model_name: str = DEFAULT_MODEL_NAME,
    provider: str | None = None,
    use_rag: bool = True,
    rag_top_k: int = DEFAULT_RAG_TOP_K,
    max_repair_attempts: int = 1,
) -> QueryResult:
    """End-to-end Text-to-SQL wrapper: schema retrieval, generation, safety, execution."""
    if not os.path.exists(db_path):
        raise FileNotFoundError("input database not found")

    try:
        schema_text = (
            retrieve_relevant_schema(db_path, question, top_k=rag_top_k)
            if use_rag
            else get_schema(db_path)
        )
        sql = generate_sql(question, schema_text, model_name=model_name, provider=provider)

        if "UNANSWERABLE_WITH_GIVEN_SCHEMA" in sql:
            return QueryResult(columns=[], rows=[], sql=sql, error="UNANSWERABLE_WITH_GIVEN_SCHEMA")
        if not is_safe_query(sql):
            return QueryResult(columns=[], rows=[], sql=sql, error="BLOCKED_UNSAFE_SQL")
        try:
            return execute_query(db_path, sql)
        except Exception as e:
            repaired_sql = _repair_sql(
                question,
                schema_text,
                sql,
                f"{type(e).__name__}: {e}",
                model_name=model_name,
                provider=provider,
                max_repair_attempts=max_repair_attempts,
            )
            if repaired_sql and is_safe_query(repaired_sql):
                return execute_query(db_path, repaired_sql)
            raise
    except Exception as e:
        return QueryResult(columns=[], rows=[], error=f"{type(e).__name__}: {e}")


def ask_database_with_sql(
    question: str,
    *,
    db_path: str = "university_agent.db",
    model_name: str = DEFAULT_MODEL_NAME,
    provider: str | None = None,
    use_rag: bool = True,
    rag_top_k: int = DEFAULT_RAG_TOP_K,
    max_repair_attempts: int = 1,
) -> tuple[str, QueryResult]:
    """Same as `ask_database`, but also returns the generated SQL for UI display."""
    if not os.path.exists(db_path):
        raise FileNotFoundError("input database not found")

    schema_text = (
        retrieve_relevant_schema(db_path, question, top_k=rag_top_k)
        if use_rag
        else get_schema(db_path)
    )
    try:
        sql = generate_sql(question, schema_text, model_name=model_name, provider=provider)
    except Exception as e:
        return "", QueryResult(columns=[], rows=[], error=f"{type(e).__name__}: {e}")

    if "UNANSWERABLE_WITH_GIVEN_SCHEMA" in sql:
        return sql, QueryResult(columns=[], rows=[], sql=sql, error="UNANSWERABLE_WITH_GIVEN_SCHEMA")
    if not is_safe_query(sql):
        return sql, QueryResult(columns=[], rows=[], sql=sql, error="BLOCKED_UNSAFE_SQL")

    try:
        return sql, execute_query(db_path, sql)
    except Exception as e:
        error_text = f"{type(e).__name__}: {e}"
        repaired_sql = _repair_sql(
            question,
            schema_text,
            sql,
            error_text,
            model_name=model_name,
            provider=provider,
            max_repair_attempts=max_repair_attempts,
        )
        if repaired_sql and is_safe_query(repaired_sql):
            try:
                return repaired_sql, execute_query(db_path, repaired_sql)
            except Exception as repaired_error:
                error_text = f"{type(repaired_error).__name__}: {repaired_error}"
        return sql, QueryResult(columns=[], rows=[], sql=sql, error=error_text)


def ask_from_files(
    question: str,
    file_paths: list[str] | str,
    *,
    output_db_path: str = "dynamic_agent.db",
    model_name: str = DEFAULT_MODEL_NAME,
    provider: str | None = None,
    use_rag: bool = True,
    rag_top_k: int = DEFAULT_RAG_TOP_K,
    max_repair_attempts: int = 1,
) -> QueryResult:
    """Route a `.db` file directly or ingest CSV files before querying."""
    paths = [file_paths] if isinstance(file_paths, str) else list(file_paths)
    if not paths:
        raise ValueError("file_paths must contain at least one path")

    exts = {Path(p).suffix.lower() for p in paths}
    if exts == {".db"}:
        if len(paths) != 1:
            raise ValueError("Provide exactly one .db file path")
        return ask_database(
            question,
            db_path=paths[0],
            model_name=model_name,
            provider=provider,
            use_rag=use_rag,
            rag_top_k=rag_top_k,
            max_repair_attempts=max_repair_attempts,
        )

    if exts == {".csv"}:
        db_path = ingest_csvs_to_db(paths, output_db_path=output_db_path)
        return ask_database(
            question,
            db_path=db_path,
            model_name=model_name,
            provider=provider,
            use_rag=use_rag,
            rag_top_k=rag_top_k,
            max_repair_attempts=max_repair_attempts,
        )

    raise ValueError(f"Unsupported or mixed file types: {sorted(exts)}")


def _repair_sql(
    question: str,
    schema_text: str,
    failed_sql: str,
    error_text: str,
    *,
    model_name: str,
    provider: str | None,
    max_repair_attempts: int,
) -> str | None:
    if max_repair_attempts < 1:
        return None
    repair_question = f"""\
Repair the SQL for the original question.

Original question:
{question}

Failed SQL:
{failed_sql}

SQLite error:
{error_text}

Return only one corrected SQLite SELECT query.
"""
    try:
        return generate_sql(repair_question, schema_text, model_name=model_name, provider=provider)
    except Exception:
        return None
