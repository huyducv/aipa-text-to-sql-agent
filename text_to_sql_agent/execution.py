from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

from .config import DEFAULT_MAX_ROWS, DEFAULT_SQLITE_PROGRESS_STEPS
from .types import QueryResult


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


def _read_only_sqlite_connection(db_path: str) -> sqlite3.Connection:
    resolved = Path(db_path).resolve()
    uri = f"{resolved.as_uri()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON;")
    conn.set_authorizer(_sqlite_read_only_authorizer)
    return conn


def execute_query(
    db_path: str,
    sql_string: str,
    *,
    max_rows: int = DEFAULT_MAX_ROWS,
    progress_steps: int = DEFAULT_SQLITE_PROGRESS_STEPS,
) -> QueryResult:
    """Execute safe SQL against SQLite using read-only protections."""
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
