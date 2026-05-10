from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class QueryResult:
    columns: list[str]
    rows: list[tuple[Any, ...]]
    sql: str | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


@dataclass(frozen=True)
class SchemaChunk:
    table_name: str
    ddl: str
    columns: list[str]
    foreign_tables: list[str]
    search_text: str
    score: float = 0.0
    matched_terms: list[str] | None = None
    match_reasons: list[str] | None = None


@dataclass(frozen=True)
class SchemaRetrievalResult:
    chunks: list[SchemaChunk]
    query_tokens: list[str]
    expanded_tokens: list[str]
    top_k: int
    strategy: str = "hybrid-bm25-semantic-graph"

    @property
    def schema_text(self) -> str:
        return "\n\n".join(chunk.ddl for chunk in self.chunks)

    @property
    def report(self) -> str:
        if not self.chunks:
            return "No schema chunks were retrieved."
        lines = [
            f"Schema RAG strategy: {self.strategy}",
            f"Query tokens: {', '.join(self.query_tokens) or '(none)'}",
            f"Expanded tokens: {', '.join(self.expanded_tokens) or '(none)'}",
            "",
            "Retrieved tables:",
        ]
        for chunk in self.chunks:
            terms = ", ".join(chunk.matched_terms or []) or "fallback"
            reasons = "; ".join(chunk.match_reasons or [])
            lines.append(f"- {chunk.table_name} (score={chunk.score:.2f}; terms={terms})")
            if reasons:
                lines.append(f"  {reasons}")
        return "\n".join(lines)
