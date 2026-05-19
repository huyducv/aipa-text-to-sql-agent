from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from pathlib import Path

import pandas as pd


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


def ingest_csvs_to_db(csv_file_paths: list[str], output_db_path: str = "dynamic_agent.db") -> str:
    """Ingest one or more CSV files into a fresh local SQLite database."""
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
            pd.read_csv(csv_path).to_sql(table_name, conn, if_exists="replace", index=False)
        conn.commit()
    return str(out_path)
