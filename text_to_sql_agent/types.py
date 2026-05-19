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
    value_hints: dict[str, list[str]] | None = None
    score: float = 0.0
    matched_terms: list[str] | None = None
    match_reasons: list[str] | None = None


@dataclass(frozen=True)
class SchemaRetrievalResult:
    chunks: list[SchemaChunk]
    query_tokens: list[str]
    expanded_tokens: list[str]
    top_k: int
    decomposed_terms: dict[str, list[str]] | None = None
    full_schema_chars: int = 0
    retrieved_schema_chars: int = 0
    cache_hit: bool = False
    strategy: str = "hybrid-bm25-embedding-semantic-values-graph"

    @property
    def schema_text(self) -> str:
        parts: list[str] = []
        for chunk in self.chunks:
            parts.append(chunk.ddl)
            if chunk.value_hints:
                parts.append(
                    "\n".join(
                        f"-- {column} sample values: {', '.join(values)}"
                        for column, values in sorted(chunk.value_hints.items())
                    )
                )
        return "\n\n".join(parts)

    @property
    def prompt_savings_pct(self) -> float:
        if self.full_schema_chars <= 0:
            return 0.0
        saved = max(0, self.full_schema_chars - self.retrieved_schema_chars)
        return round((saved / self.full_schema_chars) * 100, 1)

    @property
    def report(self) -> str:
        if not self.chunks:
            return "No schema chunks were retrieved."
        lines = [
            f"Schema RAG strategy: {self.strategy}",
            f"Query tokens: {', '.join(self.query_tokens) or '(none)'}",
            f"Expanded tokens: {', '.join(self.expanded_tokens) or '(none)'}",
            f"Prompt schema chars: {self.retrieved_schema_chars}/{self.full_schema_chars} saved={self.prompt_savings_pct}%",
            f"Cache hit: {self.cache_hit}",
            "",
            "Query decomposition:",
        ]
        for key, values in (self.decomposed_terms or {}).items():
            lines.append(f"- {key}: {', '.join(values) or '(none)'}")
        lines += [
            "",
            "Retrieved tables:",
        ]
        for chunk in self.chunks:
            terms = ", ".join(chunk.matched_terms or []) or "fallback"
            reasons = "; ".join(chunk.match_reasons or [])
            lines.append(f"- {chunk.table_name} (score={chunk.score:.2f}; terms={terms})")
            if reasons:
                lines.append(f"  {reasons}")
            if chunk.value_hints:
                for column, values in sorted(chunk.value_hints.items()):
                    lines.append(f"  value hints {column}: {', '.join(values)}")
        return "\n".join(lines)
