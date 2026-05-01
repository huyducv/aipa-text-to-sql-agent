"""
Text-to-SQL Enterprise Agent (1-week MVP)
========================================

This file is intentionally "notebook-friendly":
- You can run it as a script: `python text_to_sql_agent_mvp.py`
- Or copy/paste each section into a Jupyter Notebook as separate cells.

Architectural guardrails implemented here:
- Local SQLite only (university_agent.db)
- No RAG / embeddings: we use static schema injection (extract CREATE TABLE DDL and inject into prompt)
- Strict separation: LLM generates SQL text only; Python executes it
- Safety first: deterministic safety gate blocks data-modifying SQL keywords
"""

from __future__ import annotations

import os
import re
import sqlite3
from dataclasses import dataclass
from typing import Any, Iterable, Optional

import pandas as pd


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

    with sqlite3.connect(db_path) as conn:
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

    return db_path


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
    with sqlite3.connect(db_path) as conn:
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


def generate_sql(user_question: str, schema_text: str, *, model_name: str = "gemini-1.5-flash") -> str:
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
    # Lazy import so the rest of the notebook can run without the dependency installed.
    import google.generativeai as genai  # type: ignore

    # Placeholder key: replace with environment variable in real use.
    # For assignment submission, never hardcode real secrets into Git.
    genai.configure(api_key=os.environ.get("GEMINI_API_KEY", "PASTE_YOUR_API_KEY_HERE"))

    model = genai.GenerativeModel(model_name)

    prompt = f"""\
### SQLite schema (DDL)
{schema_text}

### User question
{user_question}
"""

    resp = model.generate_content(
        prompt,
        generation_config={
            "temperature": 0.0,  # deterministic-ish for reproducibility
            "max_output_tokens": 512,
        },
        system_instruction=SQL_TRANSLATION_SYSTEM_PROMPT,
    )

    # Gemini SDK returns structured parts; `.text` is the simplest.
    sql = (resp.text or "").strip()

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


def execute_query(db_path: str, sql_string: str) -> QueryResult:
    """
    Execute a SQL query against SQLite and return all rows.

    Trade-offs / reporting notes:
    - `fetchall()` is fine for MVP/small results. For large outputs you'd paginate
      or stream results.
    """
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(sql_string)
        rows = cur.fetchall()
        columns = [d[0] for d in cur.description] if cur.description else []
        return QueryResult(columns=columns, rows=[tuple(r) for r in rows])


# ============================================================
# Step 3: Master Function
# ============================================================

def ask_database(
    question: str,
    *,
    db_path: str = "university_agent.db",
    model_name: str = "gemini-1.5-flash",
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
        # Auto-initialize for notebook convenience.
        write_university_db(db_path)

    try:
        schema_text = get_schema(db_path)
        sql = generate_sql(question, schema_text, model_name=model_name)

        if "UNANSWERABLE_WITH_GIVEN_SCHEMA" in sql:
            return QueryResult(columns=["error"], rows=[("UNANSWERABLE_WITH_GIVEN_SCHEMA",)])

        if not is_safe_query(sql):
            return QueryResult(
                columns=["error", "sql"],
                rows=[("BLOCKED_UNSAFE_SQL", sql)],
            )

        return execute_query(db_path, sql)

    except Exception as e:
        # For an MVP, we return a compact message.
        # In production you'd log full stack traces and implement retries/timeouts.
        return QueryResult(columns=["error"], rows=[(f"{type(e).__name__}: {e}",)])


# ============================================================
# Quick demo (optional when running as a script)
# ============================================================

if __name__ == "__main__":
    db = write_university_db("university_agent.db")
    print(f"Created DB: {db}")
    print("Schema:\n", get_schema(db))

    # Note: requires GEMINI_API_KEY to actually generate SQL.
    # Example questions you can try in a notebook:
    # - "List the top 5 students by average score."
    # - "How many students are enrolled in each major?"
    # - "Show each course and the number of distinct students who took it."
    res = ask_database("How many students are enrolled in each major?", db_path=db)
    print(res.columns)
    for r in res.rows[:10]:
        print(r)
