from __future__ import annotations

import os
import sqlite3
from contextlib import closing
from typing import Any

import pandas as pd


def create_dummy_university_data(seed: int = 7) -> dict[str, pd.DataFrame]:
    """Create deterministic synthetic university tables for demos and tests."""
    _ = seed
    rng = pd.Series(range(1, 21))
    students = pd.DataFrame(
        {
            "student_id": rng,
            "full_name": [f"Student {i:02d}" for i in rng],
            "email": [f"student{i:02d}@example.edu" for i in rng],
            "enrollment_year": [2022 + (i % 4) for i in rng],
            "major": [["CS", "DS", "IT", "Business", "Math"][i % 5] for i in rng],
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
    grade_scale = ["HD", "D", "C", "P", "F"]
    enroll_rows: list[dict[str, Any]] = []
    for student_id in students["student_id"].tolist():
        course_choices = [courses.loc[(student_id + k) % len(courses), "course_id"] for k in (0, 2, 4)]
        for course_id in course_choices:
            enroll_rows.append(
                {
                    "student_id": int(student_id),
                    "course_id": int(course_id),
                    "semester": ["2024S1", "2024S2"][student_id % 2],
                    "grade": grade_scale[(student_id + int(course_id)) % len(grade_scale)],
                    "score": int(55 + ((student_id * 7 + int(course_id)) % 46)),
                }
            )
    grades = pd.DataFrame(enroll_rows).sort_values(["student_id", "course_id"]).reset_index(drop=True)
    return {"students": students, "courses": courses, "grades": grades}


def write_university_db(db_path: str = "university_agent.db") -> str:
    """Create or overwrite the synthetic university SQLite database."""
    data = create_dummy_university_data()
    if os.path.exists(db_path):
        os.remove(db_path)

    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        data["students"].to_sql("students", conn, index=False)
        data["courses"].to_sql("courses", conn, index=False)
        data["grades"].to_sql("grades", conn, index=False)
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
