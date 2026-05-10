"""
Text-to-SQL Enterprise Agent (MVP)
========================================

This module contains the core backend pipeline for a local, safe Text-to-SQL agent:
- Local SQLite only
- Schema RAG: retrieve the most relevant table DDL before prompting
- Strict separation: LLM generates SQL text only; Python executes
- Safety first: deterministic gate blocks data-modifying SQL keywords

It also includes:
- A synthetic "university" dataset builder (useful for demos/tests)
- A CSV ingestion utility to create a SQLite DB from user-provided CSVs
- A convenience router that chooses DB vs CSV workflow automatically

Notes:
- Nothing executes at import time; use `__main__` or call functions from a notebook.
- API keys should be stored in `.env` (gitignored) and loaded into `GEMINI_API_KEY`.
"""

from __future__ import annotations

import os
import re
import sqlite3
import math
from collections import Counter
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from langchain_community.chat_models import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage

import pandas as pd

try:
    from dotenv import load_dotenv  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    load_dotenv = None


DEFAULT_MODEL_NAME = "gemini-2.5-flash"
DEFAULT_OLLAMA_MODEL = "gemma3"
DEFAULT_PROVIDER = "gemini"
DEFAULT_MAX_ROWS = 1_000
DEFAULT_SQLITE_PROGRESS_STEPS = 100_000
DEFAULT_RAG_TOP_K = 6
DEFAULT_RAG_NEIGHBORS = 1

RAG_SYNONYMS = {
    "client": ["customer", "customers"],
    "clients": ["customer", "customers"],
    "buyer": ["customer", "customers"],
    "buyers": ["customer", "customers"],
    "income": ["revenue", "amount", "sales"],
    "revenue": ["amount", "sales", "total"],
    "sale": ["sales", "amount"],
    "sales": ["sale", "amount", "revenue"],
    "spend": ["amount", "sales"],
    "course": ["courses", "class"],
    "classes": ["courses", "course"],
    "student": ["students", "learner"],
    "patients": ["patient", "healthcare"],
    "patient": ["patients", "healthcare"],
    "region": ["location", "area"],
}


_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "by", "for", "from", "how", "in",
    "is", "it", "me", "of", "on", "or", "per", "show", "the", "to", "total",
    "what", "which", "with",
}


def _load_gemini_sdk() -> Any:
    try:
        import google.generativeai as genai  # type: ignore
    except ModuleNotFoundError as e:  # pragma: no cover
        raise ModuleNotFoundError(
            "google-generativeai is not installed. Run: pip install google-generativeai"
        ) from e
    return genai


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


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:sql)?\s*", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"\s*```$", "", text).strip()
    return text


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


def load_env(env_path: str | None = None) -> None:
    """
    Load environment variables from a `.env` file.

    Default behavior:
    - If `env_path` is provided, load from that exact path.
    - Otherwise, load from `<project_root>/.env` (same folder as this file).
    """
    if load_dotenv is None:
        return

    if env_path is not None:
        load_dotenv(env_path)
        return

    here = Path(__file__).resolve().parent
    load_dotenv(here / ".env")


# ============================================================
# Step 1: Project Initialization & Data Setup
# ============================================================

def create_dummy_university_data(seed: int = 7) -> dict[str, pd.DataFrame]:
    """
    Create small, realistic, relational "University" tables using pandas.

    Trade-offs / reporting notes:
    - This is synthetic data. It is great for demos, reproducibility, and safety.
    - The schema is intentionally small for a 1-week MVP; enterprise schemas often
      have hundreds of tables, which makes static schema injection expensive.
    """
    rng = pd.Series(range(1, 21))  # 20 students

    students = pd.DataFrame(
        {
            "student_id": rng,
            "full_name": [f"Student {i:02d}" for i in rng],
            "email": [f"student{i:02d}@example.edu" for i in rng],
            "enrollment_year": [2022 + (i % 4) for i in rng],
            "major": [
                ["CS", "DS", "IT", "Business", "Math"][i % 5]
                for i in rng
            ],
        }
    )

    courses = pd.DataFrame(
        {
            "course_id": [101, 102, 103, 201, 202, 301],
            "course_code": ["CS101", "DS102", "IT103", "CS201", "BUS202", "MATH301"],
            "course_name": [
                "Intro to Programming",
                "Data Fundamentals",
                "Networks Basics",
                "Databases",
                "Business Analytics",
                "Linear Algebra",
            ],
            "credits": [6, 6, 6, 6, 6, 6],
        }
    )

    # Enrollments / grades: many-to-many between students and courses.
    # We keep it simple: each student takes 3 courses.
    enroll_rows: list[dict[str, Any]] = []
    grade_scale = ["HD", "D", "C", "P", "F"]
    for student_id in students["student_id"].tolist():
        # Deterministic course choices (simple, reproducible)
        course_choices = [
            courses.loc[(student_id + k) % len(courses), "course_id"]
            for k in (0, 2, 4)
        ]
        for course_id in course_choices:
            # Deterministic-ish grade distribution
            grade = grade_scale[(student_id + int(course_id)) % len(grade_scale)]
            score = int(55 + ((student_id * 7 + int(course_id)) % 46))  # 55..100
            enroll_rows.append(
                {
                    "student_id": int(student_id),
                    "course_id": int(course_id),
                    "semester": ["2024S1", "2024S2"][student_id % 2],
                    "grade": grade,
                    "score": score,
                }
            )

    grades = pd.DataFrame(enroll_rows).sort_values(["student_id", "course_id"]).reset_index(drop=True)

    return {"students": students, "courses": courses, "grades": grades}


def write_university_db(db_path: str = "university_agent.db") -> str:
    """
    Create (or overwrite) a local SQLite DB and populate it.

    Trade-offs / reporting notes:
    - For MVP speed, we use pandas `to_sql`. In production you'd likely use
      migrations, constraints, and more careful transaction handling.
    - We also add basic PK/FK constraints after write via explicit DDL to make
      schema extraction meaningful for the LLM.
    """
    data = create_dummy_university_data()

    if os.path.exists(db_path):
        os.remove(db_path)

    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")

        # Write tables (initially without constraints)
        data["students"].to_sql("students", conn, index=False)
        data["courses"].to_sql("courses", conn, index=False)
        data["grades"].to_sql("grades", conn, index=False)

        # Re-create tables with constraints (SQLite limitation: ALTER TABLE is limited).
        # We do the standard pattern: rename -> create -> insert -> drop old.
        conn.executescript(
            """
            PRAGMA foreign_keys = OFF;

            ALTER TABLE students RENAME TO students_old;
            CREATE TABLE students (
                student_id INTEGER PRIMARY KEY,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                enrollment_year INTEGER NOT NULL,
                major TEXT NOT NULL
            );
            INSERT INTO students SELECT * FROM students_old;
            DROP TABLE students_old;

            ALTER TABLE courses RENAME TO courses_old;
            CREATE TABLE courses (
                course_id INTEGER PRIMARY KEY,
                course_code TEXT NOT NULL UNIQUE,
                course_name TEXT NOT NULL,
                credits INTEGER NOT NULL
            );
            INSERT INTO courses SELECT * FROM courses_old;
            DROP TABLE courses_old;

            ALTER TABLE grades RENAME TO grades_old;
            CREATE TABLE grades (
                student_id INTEGER NOT NULL,
                course_id INTEGER NOT NULL,
                semester TEXT NOT NULL,
                grade TEXT NOT NULL,
                score INTEGER NOT NULL,
                PRIMARY KEY (student_id, course_id, semester),
                FOREIGN KEY (student_id) REFERENCES students(student_id),
                FOREIGN KEY (course_id) REFERENCES courses(course_id)
            );
            INSERT INTO grades SELECT * FROM grades_old;
            DROP TABLE grades_old;

            PRAGMA foreign_keys = ON;
            """
        )
        conn.commit()

    return db_path


# ============================================================
# Task 1: CSV ingestion utility (CSV -> SQLite)
# ============================================================

def ingest_csvs_to_db(csv_file_paths: list[str], output_db_path: str = "dynamic_agent.db") -> str:
    """
    Ingest one or more CSV files into a local SQLite database.

    Behavior:
    - For each CSV path: read with pandas, write to SQLite using table name = file stem.
      Example: `data/financials.csv` -> table `financials`
    - Replaces the table if it already exists.
    - Creates a fresh DB file each run (overwrites `output_db_path`).

    Trade-offs / report notes:
    - `to_sql(if_exists="replace")` is convenient but doesn't preserve constraints or
      strong typing. For an MVP it's acceptable; for production add explicit DDL.
    """
    if not csv_file_paths:
        raise ValueError("csv_file_paths must contain at least one CSV path")

    out_path = Path(output_db_path)
    if out_path.exists():
        out_path.unlink()

    used_table_names: set[str] = set()

    with closing(sqlite3.connect(str(out_path))) as conn:
        for csv_path_str in csv_file_paths:
            csv_path = Path(csv_path_str)
            if not csv_path.exists():
                raise FileNotFoundError(f"CSV not found: {csv_path}")
            if csv_path.suffix.lower() != ".csv":
                raise ValueError(f"Not a .csv file: {csv_path}")

            table_name = normalize_table_name(csv_path.stem, used_table_names)
            used_table_names.add(table_name)
            df = pd.read_csv(csv_path)
            df.to_sql(table_name, conn, if_exists="replace", index=False)
        conn.commit()

    return str(out_path)


def normalize_table_name(raw_name: str, existing_names: set[str] | None = None) -> str:
    """Convert a CSV filename stem into a conservative SQLite table name."""
    cleaned = re.sub(r"[^0-9a-zA-Z_]+", "_", raw_name).strip("_").lower()
    if not cleaned:
        cleaned = "table"
    if cleaned[0].isdigit():
        cleaned = f"table_{cleaned}"
    if existing_names is None or cleaned not in existing_names:
        return cleaned

    i = 2
    candidate = f"{cleaned}_{i}"
    while candidate in existing_names:
        i += 1
        candidate = f"{cleaned}_{i}"
    return candidate


# ============================================================
# Step 2: Core Backend Pipeline
# ============================================================

def get_schema(db_path: str) -> str:
    """
    Extract CREATE TABLE statements for all user tables in SQLite.

    Trade-offs / reporting notes:
    - Static schema injection is simple and deterministic (no retrieval system).
    - It scales poorly: as schema grows, prompt length grows and costs/latency rise.
    - Still, for small-to-medium schemas in an MVP, it's a strong baseline.
    """
    with closing(sqlite3.connect(db_path)) as conn:
        rows = conn.execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE type='table'
              AND name NOT LIKE 'sqlite_%'
              AND sql IS NOT NULL
            ORDER BY name;
            """
        ).fetchall()

    ddl_statements = [r[0].strip().rstrip(";") + ";" for r in rows]
    return "\n\n".join(ddl_statements)


def _tokenize_for_rag(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", text.lower())
    expanded: list[str] = []
    for token in tokens:
        if token not in _STOPWORDS:
            expanded.append(token)
        for part in token.split("_"):
            if part and part not in _STOPWORDS:
                expanded.append(part)
    return expanded


def _expand_query_tokens(tokens: list[str]) -> list[str]:
    expanded = list(tokens)
    for token in tokens:
        expanded.extend(RAG_SYNONYMS.get(token, []))
    return expanded


def get_schema_chunks(db_path: str) -> list[SchemaChunk]:
    """
    Build table-level schema chunks for retrieval.

    Each chunk includes the table DDL, column names, and foreign-key neighbors.
    No row data is read or embedded.
    """
    with closing(sqlite3.connect(db_path)) as conn:
        table_rows = conn.execute(
            """
            SELECT name, sql
            FROM sqlite_master
            WHERE type='table'
              AND name NOT LIKE 'sqlite_%'
              AND sql IS NOT NULL
            ORDER BY name;
            """
        ).fetchall()

        chunks: list[SchemaChunk] = []
        for table_name, ddl in table_rows:
            columns = [
                row[1]
                for row in conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()
            ]
            foreign_tables = sorted(
                {
                    row[2]
                    for row in conn.execute(f'PRAGMA foreign_key_list("{table_name}")').fetchall()
                    if row[2]
                }
            )
            search_text = " ".join([table_name, ddl or "", *columns, *foreign_tables])
            chunks.append(
                SchemaChunk(
                    table_name=table_name,
                    ddl=ddl.strip().rstrip(";") + ";",
                    columns=columns,
                    foreign_tables=foreign_tables,
                    search_text=search_text,
                )
            )
    return chunks


def retrieve_schema_chunks(
    db_path: str,
    question: str,
    *,
    top_k: int = DEFAULT_RAG_TOP_K,
    include_neighbors: int = DEFAULT_RAG_NEIGHBORS,
) -> list[SchemaChunk]:
    """
    Retrieve the most relevant schema chunks for a natural-language question.

    This is a deterministic hybrid retriever:
    - BM25-style scoring over schema text
    - extra boosts for table and column matches
    - synonym expansion for common business terms
    - foreign-key graph expansion for joinable neighbor tables
    """
    return retrieve_schema_context(
        db_path,
        question,
        top_k=top_k,
        include_neighbors=include_neighbors,
    ).chunks


def retrieve_schema_context(
    db_path: str,
    question: str,
    *,
    top_k: int = DEFAULT_RAG_TOP_K,
    include_neighbors: int = DEFAULT_RAG_NEIGHBORS,
) -> SchemaRetrievalResult:
    chunks = get_schema_chunks(db_path)
    query_tokens = _tokenize_for_rag(question)
    expanded_tokens = _expand_query_tokens(query_tokens)

    if not chunks:
        return SchemaRetrievalResult([], query_tokens, expanded_tokens, top_k)
    if top_k <= 0:
        return SchemaRetrievalResult(chunks, query_tokens, expanded_tokens, top_k)

    doc_tokens = [_tokenize_for_rag(chunk.search_text) for chunk in chunks]
    doc_lengths = [len(tokens) or 1 for tokens in doc_tokens]
    avg_doc_len = sum(doc_lengths) / len(doc_lengths)

    doc_freq: Counter[str] = Counter()
    for tokens in doc_tokens:
        doc_freq.update(set(tokens))

    query_counter = Counter(expanded_tokens)
    scored: list[SchemaChunk] = []
    for chunk, tokens, doc_len in zip(chunks, doc_tokens, doc_lengths):
        token_counts = Counter(tokens)
        table_tokens = set(_tokenize_for_rag(chunk.table_name))
        column_tokens = set(_tokenize_for_rag(" ".join(chunk.columns)))
        text_token_set = set(tokens)

        score = 0.0
        matched_terms: set[str] = set()
        reasons: list[str] = []

        for token, query_weight in query_counter.items():
            if token not in token_counts:
                continue
            matched_terms.add(token)
            idf = math.log(1 + (len(chunks) - doc_freq[token] + 0.5) / (doc_freq[token] + 0.5))
            tf = token_counts[token]
            denominator = tf + 1.5 * (1 - 0.75 + 0.75 * doc_len / avg_doc_len)
            score += idf * ((tf * 2.5) / denominator) * max(1, query_weight)

        table_matches = sorted(set(expanded_tokens) & table_tokens)
        column_matches = sorted(set(expanded_tokens) & column_tokens)
        weak_matches = sorted(set(expanded_tokens) & text_token_set)
        if table_matches:
            score += 8.0 * len(table_matches)
            reasons.append(f"table match: {', '.join(table_matches)}")
            matched_terms.update(table_matches)
        if column_matches:
            score += 4.0 * len(column_matches)
            reasons.append(f"column match: {', '.join(column_matches)}")
            matched_terms.update(column_matches)
        if weak_matches and not (table_matches or column_matches):
            reasons.append(f"schema text match: {', '.join(weak_matches[:6])}")

        scored.append(
            SchemaChunk(
                table_name=chunk.table_name,
                ddl=chunk.ddl,
                columns=chunk.columns,
                foreign_tables=chunk.foreign_tables,
                search_text=chunk.search_text,
                score=score,
                matched_terms=sorted(matched_terms),
                match_reasons=reasons,
            )
        )

    selected = sorted(scored, key=lambda c: (-c.score, c.table_name))[:top_k]
    if all(chunk.score == 0 for chunk in selected):
        selected = sorted(scored, key=lambda c: c.table_name)[:top_k]

    selected_names = {chunk.table_name for chunk in selected}
    if include_neighbors > 0:
        chunk_by_name = {chunk.table_name: chunk for chunk in scored}
        frontier = list(selected)
        for depth in range(include_neighbors):
            next_frontier: list[SchemaChunk] = []
            for chunk in frontier:
                for neighbor in chunk.foreign_tables:
                    if neighbor in chunk_by_name and neighbor not in selected_names:
                        selected_names.add(neighbor)
                        neighbor_chunk = chunk_by_name[neighbor]
                        next_frontier.append(
                            SchemaChunk(
                                table_name=neighbor_chunk.table_name,
                                ddl=neighbor_chunk.ddl,
                                columns=neighbor_chunk.columns,
                                foreign_tables=neighbor_chunk.foreign_tables,
                                search_text=neighbor_chunk.search_text,
                                score=max(neighbor_chunk.score, chunk.score * (0.35 / (depth + 1))),
                                matched_terms=neighbor_chunk.matched_terms or [],
                                match_reasons=[
                                    *(neighbor_chunk.match_reasons or []),
                                    f"foreign-key neighbor of {chunk.table_name}",
                                ],
                            )
                        )
            selected.extend(next_frontier)
            frontier = next_frontier

    selected = sorted(selected, key=lambda c: (-c.score, c.table_name))
    return SchemaRetrievalResult(selected, query_tokens, expanded_tokens, top_k)


def retrieve_relevant_schema(
    db_path: str,
    question: str,
    *,
    top_k: int = DEFAULT_RAG_TOP_K,
) -> str:
    """Return retrieved DDL snippets for the prompt."""
    return retrieve_schema_context(db_path, question, top_k=top_k).schema_text


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


def generate_sql(
    user_question: str,
    schema_text: str,
    *,
    model_name: str = DEFAULT_MODEL_NAME,
    provider: str | None = None,
) -> str:
    """
    Call an LLM to generate SQL from a question + schema.

    Strict separation guarantee:
    - The LLM sees ONLY the schema DDL (no row data).
    - The LLM returns ONLY SQL text; Python decides if/when to execute.
    """
    load_env()
    selected_provider = (provider or os.environ.get("TEXT_TO_SQL_PROVIDER") or DEFAULT_PROVIDER).strip().lower()

    prompt = f"""\
### SQLite schema (DDL)
{schema_text}

### User question
{user_question}
"""

    if selected_provider == "gemini":
        genai = _load_gemini_sdk()
        api_key = (os.environ.get("GEMINI_API_KEY") or "").strip()
        if not api_key:
            raise ValueError("GEMINI_API_KEY is missing. Set it in `.env` or environment variables.")

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name or DEFAULT_MODEL_NAME,
            system_instruction=SQL_TRANSLATION_SYSTEM_PROMPT,
        )
        response = model.generate_content(
            contents=prompt,
            generation_config={
                "temperature": 0.0,
                "max_output_tokens": 512,
            },
        )
        return _extract_sql_from_text(str(response.text or ""))

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


_DANGEROUS_SQL_PATTERN = re.compile(
    r"""
    (?ix)                       # i=case-insensitive, x=verbose
    \b(
        insert|update|delete|drop|alter|create|replace|truncate|
        vacuum|pragma|attach|detach|reindex|analyze|
        begin|commit|rollback|savepoint|release
    )\b
    """.strip()
)


def is_safe_query(sql_string: str) -> bool:
    """
    Deterministic rule-based safety filter.

    Security stance:
    - Default deny for anything that *looks* like write/DDL/transactional SQL.
    - Allow only read-only queries (SELECT / WITH ... SELECT).

    Trade-offs / reporting notes:
    - Keyword blocking is intentionally conservative. It may reject some benign
      queries (false positives) but greatly reduces risk for an MVP.
    - You can strengthen this using a SQL parser, but that adds dependencies and
      still may not be perfectly safe without a full AST + policy engine.
    """
    if not sql_string or not sql_string.strip():
        return False

    s = sql_string.strip().rstrip(";").strip()

    # Must start with SELECT or WITH (CTE) for a read-only query.
    if not re.match(r"(?is)^(select|with)\b", s):
        return False

    # Block dangerous tokens anywhere in the query text.
    if _DANGEROUS_SQL_PATTERN.search(s) is not None:
        return False

    # Block common internal table access.
    if re.search(r"(?is)\bsqlite_master\b|\bsqlite_schema\b", s):
        return False

    return True


@dataclass(frozen=True)
class QueryResult:
    columns: list[str]
    rows: list[tuple[Any, ...]]
    sql: str | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


@dataclass(frozen=True)
class SchemaChunk:
    table_name: str
    ddl: str
    columns: list[str]
    foreign_tables: list[str]
    search_text: str
    score: float = 0.0
    matched_terms: list[str] | None = None
    match_reasons: list[str] | None = None


@dataclass(frozen=True)
class SchemaRetrievalResult:
    chunks: list[SchemaChunk]
    query_tokens: list[str]
    expanded_tokens: list[str]
    top_k: int
    strategy: str = "hybrid-bm25-graph"

    @property
    def schema_text(self) -> str:
        return "\n\n".join(chunk.ddl for chunk in self.chunks)

    @property
    def report(self) -> str:
        if not self.chunks:
            return "No schema chunks were retrieved."
        lines = [
            f"Schema RAG strategy: {self.strategy}",
            f"Query tokens: {', '.join(self.query_tokens) or '(none)'}",
            f"Expanded tokens: {', '.join(self.expanded_tokens) or '(none)'}",
            "",
            "Retrieved tables:",
        ]
        for chunk in self.chunks:
            terms = ", ".join(chunk.matched_terms or []) or "fallback"
            reasons = "; ".join(chunk.match_reasons or [])
            lines.append(f"- {chunk.table_name} (score={chunk.score:.2f}; terms={terms})")
            if reasons:
                lines.append(f"  {reasons}")
        return "\n".join(lines)


def _read_only_sqlite_connection(db_path: str) -> sqlite3.Connection:
    resolved = Path(db_path).resolve()
    uri = f"{resolved.as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON;")
    conn.set_authorizer(_sqlite_read_only_authorizer)
    return conn


def _sqlite_read_only_authorizer(action: int, *_args: Any) -> int:
    denied_actions = {
        sqlite3.SQLITE_INSERT,
        sqlite3.SQLITE_UPDATE,
        sqlite3.SQLITE_DELETE,
        sqlite3.SQLITE_TRANSACTION,
        sqlite3.SQLITE_ATTACH,
        sqlite3.SQLITE_DETACH,
        sqlite3.SQLITE_ALTER_TABLE,
        sqlite3.SQLITE_DROP_TABLE,
        sqlite3.SQLITE_DROP_INDEX,
        sqlite3.SQLITE_DROP_TRIGGER,
        sqlite3.SQLITE_DROP_VIEW,
        sqlite3.SQLITE_CREATE_INDEX,
        sqlite3.SQLITE_CREATE_TABLE,
        sqlite3.SQLITE_CREATE_TRIGGER,
        sqlite3.SQLITE_CREATE_VIEW,
        sqlite3.SQLITE_CREATE_TEMP_INDEX,
        sqlite3.SQLITE_CREATE_TEMP_TABLE,
        sqlite3.SQLITE_CREATE_TEMP_TRIGGER,
        sqlite3.SQLITE_CREATE_TEMP_VIEW,
        sqlite3.SQLITE_DROP_TEMP_INDEX,
        sqlite3.SQLITE_DROP_TEMP_TABLE,
        sqlite3.SQLITE_DROP_TEMP_TRIGGER,
        sqlite3.SQLITE_DROP_TEMP_VIEW,
        sqlite3.SQLITE_PRAGMA,
        sqlite3.SQLITE_REINDEX,
        sqlite3.SQLITE_ANALYZE,
    }
    return sqlite3.SQLITE_DENY if action in denied_actions else sqlite3.SQLITE_OK


def execute_query(
    db_path: str,
    sql_string: str,
    *,
    max_rows: int = DEFAULT_MAX_ROWS,
    progress_steps: int = DEFAULT_SQLITE_PROGRESS_STEPS,
) -> QueryResult:
    """
    Execute a SQL query against SQLite and return all rows.

    Trade-offs / reporting notes:
    - `fetchall()` is fine for MVP/small results. For large outputs you'd paginate
      or stream results.
    """
    if max_rows < 1:
        raise ValueError("max_rows must be at least 1")

    with closing(_read_only_sqlite_connection(db_path)) as conn:
        if progress_steps > 0:
            conn.set_progress_handler(lambda: 1, progress_steps)
        cur = conn.execute(sql_string)
        rows = cur.fetchmany(max_rows + 1)
        columns = [d[0] for d in cur.description] if cur.description else []
        capped_rows = rows[:max_rows]
        if len(rows) > max_rows:
            return QueryResult(
                columns=columns,
                rows=[tuple(r) for r in capped_rows],
                sql=sql_string,
                error=f"RESULT_TRUNCATED_TO_{max_rows}_ROWS",
            )
        return QueryResult(columns=columns, rows=[tuple(r) for r in capped_rows], sql=sql_string)


# ============================================================
# Step 3: Master Function
# ============================================================

def ask_database(
    question: str,
    *,
    db_path: str = "university_agent.db",
    model_name: str = DEFAULT_MODEL_NAME,
    provider: str | None = None,
    use_rag: bool = True,
    rag_top_k: int = DEFAULT_RAG_TOP_K,
) -> QueryResult:
    """
    End-to-end Text-to-SQL agent wrapper:
    schema retrieval -> LLM SQL generation -> safety validation -> execution.

    Error handling principles:
    - Fail closed: if unsafe or invalid SQL, do not execute.
    - Return readable errors via a 1-row result to keep notebook UX simple.
      (Alternative: raise exceptions and let UI handle them.)
    """
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
            return QueryResult(
                columns=[],
                rows=[],
                sql=sql,
                error="BLOCKED_UNSAFE_SQL",
            )

        return execute_query(db_path, sql)

    except Exception as e:
        # For an MVP, we return a compact message.
        # In production you'd log full stack traces and implement retries/timeouts.
        return QueryResult(columns=[], rows=[], error=f"{type(e).__name__}: {e}")


def ask_database_with_sql(
    question: str,
    *,
    db_path: str = "university_agent.db",
    model_name: str = DEFAULT_MODEL_NAME,
    provider: str | None = None,
    use_rag: bool = True,
    rag_top_k: int = DEFAULT_RAG_TOP_K,
) -> tuple[str, QueryResult]:
    """
    Same as `ask_database`, but also returns the generated SQL string for UI display.

    Returns:
      (sql_text, QueryResult)
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError("input database not found")

    schema_text = (
        retrieve_relevant_schema(db_path, question, top_k=rag_top_k)
        if use_rag
        else get_schema(db_path)
    )
    sql = generate_sql(question, schema_text, model_name=model_name, provider=provider)

    if "UNANSWERABLE_WITH_GIVEN_SCHEMA" in sql:
        return sql, QueryResult(columns=[], rows=[], sql=sql, error="UNANSWERABLE_WITH_GIVEN_SCHEMA")

    if not is_safe_query(sql):
        return sql, QueryResult(
            columns=[],
            rows=[],
            sql=sql,
            error="BLOCKED_UNSAFE_SQL",
        )

    try:
        return sql, execute_query(db_path, sql)
    except Exception as e:
        return sql, QueryResult(columns=[], rows=[], sql=sql, error=f"{type(e).__name__}: {e}")


def ask_from_files(
    question: str,
    file_paths: list[str] | str,
    *,
    output_db_path: str = "dynamic_agent.db",
    model_name: str = DEFAULT_MODEL_NAME,
    provider: str | None = None,
    use_rag: bool = True,
    rag_top_k: int = DEFAULT_RAG_TOP_K,
) -> QueryResult:
    """
    Auto-select workflow:
    - single `.db` -> query directly
    - one or more `.csv` -> ingest to SQLite then query

    Mixed file types are rejected.
    """
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
        )

    raise ValueError(f"Unsupported or mixed file types: {sorted(exts)}")


# ============================================================
# Quick demo (optional when running as a script)
# ============================================================

# if __name__ == "__main__":
#     # 1) Build a demo university DB (synthetic)
#     demo_db = write_university_db("university_agent.db")
#     print(f"Created demo DB: {demo_db}")

    # 2) Query it (requires GEMINI_API_KEY in `.env` or env vars)
    # print(ask_database("How many students are enrolled in each major?", db_path=demo_db))
