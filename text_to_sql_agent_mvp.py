"""
Text-to-SQL Enterprise Agent (1-week MVP)
========================================

This module contains the core backend pipeline for a local, safe Text-to-SQL agent:
- Local SQLite only
- No RAG: static schema injection (extract CREATE TABLE DDL and inject into prompt)
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
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from dotenv import load_dotenv  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    load_dotenv = None


DEFAULT_MODEL_NAME = "gemini-2.5-flash"
DEFAULT_MAX_ROWS = 1_000
DEFAULT_SQLITE_PROGRESS_STEPS = 100_000


def _load_gemini_sdk() -> Any:
    try:
        import google.generativeai as genai  # type: ignore
    except ModuleNotFoundError as e:  # pragma: no cover
        raise ModuleNotFoundError(
            "google-generativeai is not installed. Run: pip install google-generativeai"
        ) from e
    return genai


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
    """
    Convert a filename stem into a conservative SQLite table name.

    SQLite can quote unusual identifiers, but clean table names make schema prompts
    easier for the LLM and avoid surprises with spaces, punctuation, and duplicates.
    """
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


SQL_TRANSLATION_SYSTEM_PROMPT = """\
You are an expert data analyst and SQL translator.
Your ONLY job is to translate the user's question into a SINGLE SQLite SELECT query.

Rules (must follow):
- Output ONLY the SQL query text. No markdown fences, no explanations.
- Use ONLY the tables and columns that exist in the provided schema.
- Generate READ-ONLY SQL: SELECT queries only.
- Do NOT use any data-modifying statements: INSERT, UPDATE, DELETE, DROP, ALTER, CREATE, REPLACE, TRUNCATE, VACUUM, PRAGMA, ATTACH, DETACH.
- Do NOT reference sqlite_master or any internal SQLite tables.
- Prefer simple SQL compatible with SQLite.

If the question cannot be answered using the schema, output exactly:
SELECT 'UNANSWERABLE_WITH_GIVEN_SCHEMA' AS error;
"""


def generate_sql(user_question: str, schema_text: str, *, model_name: str = DEFAULT_MODEL_NAME) -> str:
    """
    Call Gemini (google-generativeai) to generate SQL from a question + schema.

    Strict separation guarantee:
    - The LLM sees ONLY the schema DDL (no row data).
    - The LLM returns ONLY SQL text; Python decides if/when to execute.

    Trade-offs / reporting notes:
    - LLM output can be invalid SQL, or reference non-existent columns.
      We handle this with execution-time error handling and safety checks.
    - Prompt-injection risk exists (e.g., user asks to "DROP TABLE"). We still
      deterministically block dangerous tokens before execution.
    """
    genai = _load_gemini_sdk()

    # Load from `.env` (gitignored) if present. Safe to call repeatedly.
    load_env()

    api_key = (os.environ.get("GEMINI_API_KEY") or "").strip()
    if not api_key:
        raise ValueError("GEMINI_API_KEY is missing. Set it in `.env` or environment variables.")

    genai.configure(api_key=api_key)

    model = genai.GenerativeModel(
        model_name,
        system_instruction=SQL_TRANSLATION_SYSTEM_PROMPT,
    )

    prompt = f"""\
### SQLite schema (DDL)
{schema_text}

### User question
{user_question}
"""

    response = model.generate_content(
        contents=prompt,
        generation_config={
            "temperature": 0.0,
            "max_output_tokens": 512,
        },
    )

    sql = (response.text or "").strip()

    # Defensive cleanup: if the model "helpfully" returns code fences, remove them.
    sql = re.sub(r"^```(?:sql)?\s*", "", sql, flags=re.IGNORECASE).strip()
    sql = re.sub(r"\s*```$", "", sql).strip()

    return sql


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
    if action in denied_actions:
        return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


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
    - Query execution is read-only at both the validation layer and SQLite layer.
    - Results are capped to keep accidental full-table scans from overwhelming the UI.
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
        result = QueryResult(columns=columns, rows=[tuple(r) for r in capped_rows], sql=sql_string)
        if len(rows) > max_rows:
            return QueryResult(
                columns=result.columns,
                rows=result.rows,
                sql=sql_string,
                error=f"RESULT_TRUNCATED_TO_{max_rows}_ROWS",
            )
        return result


# ============================================================
# Step 3: Master Function
# ============================================================

def ask_database(
    question: str,
    *,
    db_path: str = "university_agent.db",
    model_name: str = DEFAULT_MODEL_NAME,
) -> QueryResult:
    """
    End-to-end Text-to-SQL agent wrapper:
    schema extraction -> LLM SQL generation -> safety validation -> execution.

    Error handling principles:
    - Fail closed: if unsafe or invalid SQL, do not execute.
    - Return readable errors via a 1-row result to keep notebook UX simple.
      (Alternative: raise exceptions and let UI handle them.)
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError("input database not found")

    try:
        schema_text = get_schema(db_path)
        sql = generate_sql(question, schema_text, model_name=model_name)

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


def ask_from_files(
    question: str,
    file_paths: list[str] | str,
    *,
    output_db_path: str = "dynamic_agent.db",
    model_name: str = DEFAULT_MODEL_NAME,
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
        return ask_database(question, db_path=paths[0], model_name=model_name)

    if exts == {".csv"}:
        db_path = ingest_csvs_to_db(paths, output_db_path=output_db_path)
        return ask_database(question, db_path=db_path, model_name=model_name)

    raise ValueError(f"Unsupported or mixed file types: {sorted(exts)}")


# ============================================================
# Quick demo (optional when running as a script)
# ============================================================

if __name__ == "__main__":
    # 1) Build a demo university DB (synthetic)
    demo_db = write_university_db("university_agent.db")
    print(f"Created demo DB: {demo_db}")

    # 2) Query it (requires GEMINI_API_KEY in `.env` or env vars)
    print(ask_database("How many students are enrolled in each major?", db_path=demo_db))
