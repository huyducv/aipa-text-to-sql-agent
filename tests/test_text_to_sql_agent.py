from __future__ import annotations

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import text_to_sql_agent_mvp as agent


class TextToSqlAgentTests(unittest.TestCase):
    def test_is_safe_query_allows_read_only_queries(self) -> None:
        self.assertTrue(agent.is_safe_query("SELECT name FROM customers;"))
        self.assertTrue(
            agent.is_safe_query(
                "WITH totals AS (SELECT customer_id, SUM(amount) AS total FROM sales GROUP BY customer_id) SELECT * FROM totals"
            )
        )

    def test_is_safe_query_blocks_unsafe_sql(self) -> None:
        for sql in [
            "DELETE FROM customers",
            "DROP TABLE customers",
            "UPDATE customers SET name = 'x'",
            "PRAGMA table_info(customers)",
            "SELECT * FROM sqlite_master",
        ]:
            with self.subTest(sql=sql):
                self.assertFalse(agent.is_safe_query(sql))

    def test_normalize_table_name(self) -> None:
        self.assertEqual(agent.normalize_table_name("Sales Report", {"sales_report"}), "sales_report_2")
        self.assertEqual(agent.normalize_table_name("2024 Sales!", set()), "table_2024_sales")
        self.assertEqual(agent.normalize_table_name("!!!", set()), "table")

    def test_ingest_csvs_to_db_sanitizes_table_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "2024 Sales Report.csv"
            pd.DataFrame({"amount": [10, 20]}).to_csv(csv_path, index=False)
            db_path = Path(tmp) / "out.db"

            agent.ingest_csvs_to_db([str(csv_path)], str(db_path))

            with closing(sqlite3.connect(db_path)) as conn:
                tables = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
                rows = conn.execute("SELECT amount FROM table_2024_sales_report").fetchall()

            self.assertEqual(tables, [("table_2024_sales_report",)])
            self.assertEqual(rows, [(10,), (20,)])

    def test_get_schema_excludes_internal_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            with closing(sqlite3.connect(db_path)) as conn:
                conn.execute("CREATE TABLE customers (customer_id INTEGER PRIMARY KEY, name TEXT)")
                conn.commit()

            schema = agent.get_schema(str(db_path))

            self.assertIn("CREATE TABLE customers", schema)
            self.assertNotIn("sqlite_", schema)

    def test_retrieve_schema_chunks_selects_relevant_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            with closing(sqlite3.connect(db_path)) as conn:
                conn.execute("CREATE TABLE customers (customer_id INTEGER PRIMARY KEY, name TEXT)")
                conn.execute(
                    "CREATE TABLE sales (sale_id INTEGER PRIMARY KEY, customer_id INTEGER, amount REAL, "
                    "FOREIGN KEY(customer_id) REFERENCES customers(customer_id))"
                )
                conn.execute("CREATE TABLE courses (course_id INTEGER PRIMARY KEY, course_name TEXT)")
                conn.commit()

            chunks = agent.retrieve_schema_chunks(
                str(db_path),
                "total sales amount by customer",
                top_k=1,
            )
            names = {chunk.table_name for chunk in chunks}

            self.assertIn("sales", names)
            self.assertIn("customers", names)
            self.assertNotIn("courses", names)

    def test_ask_database_uses_retrieved_schema_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            with closing(sqlite3.connect(db_path)) as conn:
                conn.execute("CREATE TABLE customers (customer_id INTEGER PRIMARY KEY, name TEXT)")
                conn.execute("CREATE TABLE courses (course_id INTEGER PRIMARY KEY, course_name TEXT)")
                conn.execute("INSERT INTO customers VALUES (1, 'Alice')")
                conn.commit()

            captured_schema: dict[str, str] = {}

            def fake_generate_sql(_question: str, schema_text: str, **_kwargs: object) -> str:
                captured_schema["text"] = schema_text
                return "SELECT name FROM customers"

            with patch.object(agent, "generate_sql", side_effect=fake_generate_sql):
                result = agent.ask_database(
                    "list customer names",
                    db_path=str(db_path),
                    rag_top_k=1,
                )

            self.assertTrue(result.ok)
            self.assertIn("CREATE TABLE customers", captured_schema["text"])
            self.assertNotIn("CREATE TABLE courses", captured_schema["text"])

    def test_execute_query_caps_rows_and_reports_truncation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            with closing(sqlite3.connect(db_path)) as conn:
                conn.execute("CREATE TABLE numbers (n INTEGER)")
                conn.executemany("INSERT INTO numbers VALUES (?)", [(1,), (2,), (3,)])
                conn.commit()

            result = agent.execute_query(str(db_path), "SELECT n FROM numbers ORDER BY n", max_rows=2)

            self.assertEqual(result.rows, [(1,), (2,)])
            self.assertEqual(result.error, "RESULT_TRUNCATED_TO_2_ROWS")

    def test_execute_query_opens_database_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            with closing(sqlite3.connect(db_path)) as conn:
                conn.execute("CREATE TABLE numbers (n INTEGER)")
                conn.commit()

            with self.assertRaises(sqlite3.DatabaseError):
                agent.execute_query(str(db_path), "DELETE FROM numbers")

    def test_ask_database_blocks_unsafe_generated_sql(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            with closing(sqlite3.connect(db_path)) as conn:
                conn.execute("CREATE TABLE customers (customer_id INTEGER PRIMARY KEY, name TEXT)")
                conn.commit()

            with patch.object(agent, "generate_sql", return_value="DROP TABLE customers"):
                result = agent.ask_database("remove customers", db_path=str(db_path))

            self.assertFalse(result.ok)
            self.assertEqual(result.error, "BLOCKED_UNSAFE_SQL")
            self.assertEqual(result.sql, "DROP TABLE customers")

    def test_ask_database_executes_safe_generated_sql(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            with closing(sqlite3.connect(db_path)) as conn:
                conn.execute("CREATE TABLE customers (customer_id INTEGER PRIMARY KEY, name TEXT)")
                conn.execute("INSERT INTO customers VALUES (1, 'Alice')")
                conn.commit()

            with patch.object(agent, "generate_sql", return_value="SELECT name FROM customers"):
                result = agent.ask_database("list customers", db_path=str(db_path))

            self.assertTrue(result.ok)
            self.assertEqual(result.columns, ["name"])
            self.assertEqual(result.rows, [("Alice",)])


if __name__ == "__main__":
    unittest.main()
