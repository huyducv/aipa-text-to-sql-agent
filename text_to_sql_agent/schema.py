from __future__ import annotations

import sqlite3
from contextlib import closing

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


def get_schema_chunks(db_path: str) -> list[SchemaChunk]:
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
            columns = [row[1] for row in conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()]
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
