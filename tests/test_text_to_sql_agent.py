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
    def test_is_safe_query_allows_select_and_cte(self) -> None:
        self.assertTrue(agent.is_safe_query("SELECT name FROM customers;"))
        self.assertTrue(
            agent.is_safe_query(
                "WITH totals AS (SELECT customer_id, SUM(amount) AS total FROM sales GROUP BY customer_id) SELECT * FROM totals"
            )
        )

    def test_is_safe_query_blocks_unsafe_sql(self) -> None:
        unsafe = [
            "DELETE FROM customers",
            "DROP TABLE customers",
            "UPDATE customers SET name = 'x'",
            "PRAGMA table_info(customers)",
            "SELECT * FROM sqlite_master",
        ]
        for sql in unsafe:
            with self.subTest(sql=sql):
                self.assertFalse(agent.is_safe_query(sql))

    def test_normalize_table_name(self) -> None:
        existing = {"sales_report"}
        self.assertEqual(agent.normalize_table_name("Sales Report", existing), "sales_report_2")
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

    def test_get_schema_excludes_sqlite_internal_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            with closing(sqlite3.connect(db_path)) as conn:
                conn.execute("CREATE TABLE customers (customer_id INTEGER PRIMARY KEY, name TEXT)")
                conn.commit()

            schema = agent.get_schema(str(db_path))

            self.assertIn("CREATE TABLE customers", schema)
            self.assertNotIn("sqlite_", schema)

    def test_execute_query_uses_read_only_connection_and_caps_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            with closing(sqlite3.connect(db_path)) as conn:
                conn.execute("CREATE TABLE numbers (n INTEGER)")
                conn.executemany("INSERT INTO numbers VALUES (?)", [(1,), (2,), (3,)])
                conn.commit()

            result = agent.execute_query(str(db_path), "SELECT n FROM numbers ORDER BY n", max_rows=2)
            self.assertEqual(result.rows, [(1,), (2,)])
            self.assertEqual(result.error, "RESULT_TRUNCATED_TO_2_ROWS")

            with self.assertRaises(sqlite3.DatabaseError):
                agent.execute_query(str(db_path), "DELETE FROM numbers")

    def test_ask_database_fails_closed_for_unsafe_generated_sql(self) -> None:
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

    def test_denied_columns_in_query_detects_policy_violation(self) -> None:
        blocked = agent.denied_columns_in_query(
            "SELECT customer_id, email FROM customers",
            {"email", "salary"},
        )
        self.assertEqual(blocked, ["email"])

    def test_suggest_chart_returns_bar_for_category_and_numeric_column(self) -> None:
        chart = agent.suggest_chart(
            ["segment", "revenue"],
            [("SMB", 120.0), ("Enterprise", 550.0)],
        )
        self.assertEqual(chart, {"type": "bar", "x": "segment", "y": "revenue"})

    def test_analyze_database_can_pause_for_human_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            with closing(sqlite3.connect(db_path)) as conn:
                conn.execute("CREATE TABLE customers (customer_id INTEGER PRIMARY KEY, name TEXT)")
                conn.commit()

            with patch.object(
                agent,
                "generate_analysis_plan",
                return_value={
                    "intent": "list",
                    "tables": ["customers"],
                    "columns": ["name"],
                    "assumptions": [],
                },
            ), patch.object(agent, "generate_sql", return_value="SELECT name FROM customers"):
                response = agent.analyze_database(
                    "list customers",
                    db_path=str(db_path),
                    require_approval=True,
                    summarize=False,
                )

            self.assertEqual(response.result.error, "AWAITING_APPROVAL")
            self.assertEqual(response.result.sql, "SELECT name FROM customers")

    def test_analyze_database_executes_and_writes_audit_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test.db"
            audit_path = Path(tmp) / "audit.jsonl"
            with closing(sqlite3.connect(db_path)) as conn:
                conn.execute("CREATE TABLE customers (customer_id INTEGER PRIMARY KEY, name TEXT)")
                conn.execute("INSERT INTO customers VALUES (1, 'Alice')")
                conn.commit()

            with patch.object(
                agent,
                "generate_analysis_plan",
                return_value={
                    "intent": "list",
                    "tables": ["customers"],
                    "columns": ["name"],
                    "assumptions": [],
                },
            ), patch.object(agent, "generate_sql", return_value="SELECT name FROM customers"):
                response = agent.analyze_database(
                    "list customers",
                    db_path=str(db_path),
                    audit_log_path=str(audit_path),
                    summarize=False,
                )

            self.assertTrue(response.ok)
            self.assertEqual(response.result.rows, [("Alice",)])
            self.assertTrue(audit_path.exists())
            self.assertIn("\"question\": \"list customers\"", audit_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
