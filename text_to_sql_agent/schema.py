from __future__ import annotations

import sqlite3
from contextlib import closing
from functools import lru_cache
from pathlib import Path

from .config import DEFAULT_VALUE_HINT_LIMIT, DEFAULT_VALUE_HINT_MAX_CARDINALITY
from .types import SchemaChunk


def get_schema(db_path: str) -> str:
    """Extract CREATE TABLE statements for all user tables in SQLite."""
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
    return "\n\n".join(r[0].strip().rstrip(";") + ";" for r in rows)


def _quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _value_hints_for_table(
    conn: sqlite3.Connection,
    table_name: str,
    columns: list[tuple[str, str]],
    *,
    max_cardinality: int = DEFAULT_VALUE_HINT_MAX_CARDINALITY,
    limit: int = DEFAULT_VALUE_HINT_LIMIT,
) -> dict[str, list[str]]:
    hints: dict[str, list[str]] = {}
    quoted_table = _quote_identifier(table_name)
    for column_name, column_type in columns:
        if column_type and not any(token in column_type.upper() for token in ("CHAR", "TEXT", "CLOB")):
            continue
        quoted_column = _quote_identifier(column_name)
        cardinality = conn.execute(
            f"SELECT COUNT(DISTINCT {quoted_column}) FROM {quoted_table} WHERE {quoted_column} IS NOT NULL"
        ).fetchone()[0]
        if cardinality is None or cardinality < 1 or cardinality > max_cardinality:
            continue
        rows = conn.execute(
            f"""
            SELECT {quoted_column}, COUNT(*) AS n
            FROM {quoted_table}
            WHERE {quoted_column} IS NOT NULL
            GROUP BY {quoted_column}
            ORDER BY n DESC, {quoted_column}
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        values = [str(row[0])[:60] for row in rows if str(row[0]).strip()]
        if values:
            hints[column_name] = values
    return hints


def _db_cache_key(db_path: str) -> tuple[str, int, int]:
    path = Path(db_path).resolve()
    stat = path.stat()
    return str(path), int(stat.st_mtime_ns), int(stat.st_size)


@lru_cache(maxsize=32)
def _cached_schema_chunks(path: str, _mtime_ns: int, _size: int) -> tuple[SchemaChunk, ...]:
    return tuple(_build_schema_chunks(path))


def _build_schema_chunks(db_path: str) -> list[SchemaChunk]:
    """Build table-level schema chunks for retrieval without reading row data."""
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
            table_info = conn.execute(f"PRAGMA table_info({_quote_identifier(table_name)})").fetchall()
            columns = [row[1] for row in table_info]
            typed_columns = [(row[1], row[2] or "") for row in table_info]
            foreign_tables = sorted(
                {
                    row[2]
                    for row in conn.execute(f"PRAGMA foreign_key_list({_quote_identifier(table_name)})").fetchall()
                    if row[2]
                }
            )
            value_hints = _value_hints_for_table(conn, table_name, typed_columns)
            value_text = " ".join(value for values in value_hints.values() for value in values)
            search_text = " ".join([table_name, ddl or "", *columns, *foreign_tables, value_text])
            chunks.append(
                SchemaChunk(
                    table_name=table_name,
                    ddl=ddl.strip().rstrip(";") + ";",
                    columns=columns,
                    foreign_tables=foreign_tables,
                    search_text=search_text,
                    value_hints=value_hints,
                )
            )
    return chunks


def get_schema_chunks(db_path: str) -> list[SchemaChunk]:
    """Return cached table-level schema chunks for retrieval."""
    path, mtime_ns, size = _db_cache_key(db_path)
    return list(_cached_schema_chunks(path, mtime_ns, size))


def get_schema_chunk_cache_info():
    return _cached_schema_chunks.cache_info()
