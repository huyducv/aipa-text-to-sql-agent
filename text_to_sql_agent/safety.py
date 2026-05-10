from __future__ import annotations

import re

_DANGEROUS_SQL_PATTERN = re.compile(
    r"""
    (?ix)
    \b(
        insert|update|delete|drop|alter|create|replace|truncate|
        vacuum|pragma|attach|detach|reindex|analyze|
        begin|commit|rollback|savepoint|release
    )\b
    """.strip()
)


def is_safe_query(sql_string: str) -> bool:
    """Conservatively allow only read-only SELECT/CTE queries."""
    if not sql_string or not sql_string.strip():
        return False
    s = sql_string.strip().rstrip(";").strip()
    if not re.match(r"(?is)^(select|with)\b", s):
        return False
    if _DANGEROUS_SQL_PATTERN.search(s) is not None:
        return False
    if re.search(r"(?is)\bsqlite_master\b|\bsqlite_schema\b", s):
        return False
    return True
