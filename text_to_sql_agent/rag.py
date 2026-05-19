from __future__ import annotations

import math
import re
from collections import Counter
from hashlib import blake2b

from .config import (
    DEFAULT_RAG_EMBEDDING_WEIGHT,
    DEFAULT_RAG_NEIGHBORS,
    DEFAULT_RAG_SEMANTIC_WEIGHT,
    DEFAULT_RAG_TOP_K,
    RAG_SYNONYMS,
    STOPWORDS,
)
from .schema import get_schema_chunk_cache_info, get_schema_chunks
from .types import SchemaChunk, SchemaRetrievalResult


def _tokenize_for_rag(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", text.lower())
    expanded: list[str] = []
    for token in tokens:
        if token not in STOPWORDS:
            expanded.append(token)
        for part in token.split("_"):
            if part and part not in STOPWORDS:
                expanded.append(part)
    return expanded


def _expand_query_tokens(tokens: list[str]) -> list[str]:
    expanded = list(tokens)
    for token in tokens:
        expanded.extend(RAG_SYNONYMS.get(token, []))
    return expanded


def _char_ngrams(text: str, *, n: int = 3) -> Counter[str]:
    normalized = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    compact = f" {normalized} "
    if len(compact) <= n:
        return Counter([compact])
    return Counter(compact[i : i + n] for i in range(len(compact) - n + 1))


def _cosine_counter_similarity(left: Counter[str], right: Counter[str]) -> float:
    if not left or not right:
        return 0.0
    shared = set(left) & set(right)
    dot = sum(left[token] * right[token] for token in shared)
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def _hashed_embedding(text: str, *, dimensions: int = 256) -> list[float]:
    vector = [0.0] * dimensions
    tokens = _tokenize_for_rag(text)
    tokens.extend(_char_ngrams(text).keys())
    for token in tokens:
        digest = blake2b(token.encode("utf-8"), digest_size=4).digest()
        raw = int.from_bytes(digest, "little")
        index = raw % dimensions
        sign = 1.0 if raw & 1 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def _cosine_vector_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    return sum(l * r for l, r in zip(left, right))


def _schema_prompt_chars(chunks: list[SchemaChunk]) -> int:
    parts: list[str] = []
    for chunk in chunks:
        parts.append(chunk.ddl)
        for column, values in (chunk.value_hints or {}).items():
            parts.append(f"-- {column}: {', '.join(values)}")
    return len("\n\n".join(parts))


def decompose_question(question: str) -> dict[str, list[str]]:
    tokens = _tokenize_for_rag(question)
    aggregations = []
    if any(token in tokens for token in ("count", "many", "number")):
        aggregations.append("count")
    if any(token in tokens for token in ("average", "avg", "mean")):
        aggregations.append("average")
    if any(token in tokens for token in ("sum", "total", "revenue", "sales")):
        aggregations.append("sum")
    if any(token in tokens for token in ("highest", "top", "most", "best")):
        aggregations.append("top")
    if any(token in tokens for token in ("lowest", "least", "bottom")):
        aggregations.append("bottom")

    filters = [
        token
        for token in tokens
        if token
        in {
            "completed",
            "cancelled",
            "pending",
            "region",
            "city",
            "status",
            "grade",
            "priority",
            "category",
        }
    ]
    comparison = [
        token
        for token in tokens
        if token in {"than", "versus", "vs", "compare", "difference", "higher", "lower"}
    ]
    return {
        "entities_or_metrics": sorted(set(tokens)),
        "aggregations": sorted(set(aggregations)),
        "filters_or_dimensions": sorted(set(filters)),
        "comparisons": sorted(set(comparison)),
    }


def retrieve_schema_chunks(
    db_path: str,
    question: str,
    *,
    top_k: int = DEFAULT_RAG_TOP_K,
    include_neighbors: int = DEFAULT_RAG_NEIGHBORS,
) -> list[SchemaChunk]:
    return retrieve_schema_context(
        db_path,
        question,
        top_k=top_k,
        include_neighbors=include_neighbors,
    ).chunks


def retrieve_schema_context(
    db_path: str,
    question: str,
    *,
    top_k: int = DEFAULT_RAG_TOP_K,
    include_neighbors: int = DEFAULT_RAG_NEIGHBORS,
    semantic_weight: float = DEFAULT_RAG_SEMANTIC_WEIGHT,
    embedding_weight: float = DEFAULT_RAG_EMBEDDING_WEIGHT,
) -> SchemaRetrievalResult:
    before_cache = get_schema_chunk_cache_info()
    chunks = get_schema_chunks(db_path)
    after_cache = get_schema_chunk_cache_info()
    cache_hit = after_cache.hits > before_cache.hits
    query_tokens = _tokenize_for_rag(question)
    expanded_tokens = _expand_query_tokens(query_tokens)
    decomposed_terms = decompose_question(question)
    full_schema_chars = _schema_prompt_chars(chunks)

    if not chunks:
        return SchemaRetrievalResult(
            [],
            query_tokens,
            expanded_tokens,
            top_k,
            decomposed_terms=decomposed_terms,
            full_schema_chars=full_schema_chars,
            cache_hit=cache_hit,
        )
    if top_k <= 0:
        retrieved_schema_chars = _schema_prompt_chars(chunks)
        return SchemaRetrievalResult(
            chunks,
            query_tokens,
            expanded_tokens,
            top_k,
            decomposed_terms=decomposed_terms,
            full_schema_chars=full_schema_chars,
            retrieved_schema_chars=retrieved_schema_chars,
            cache_hit=cache_hit,
        )

    doc_tokens = [_tokenize_for_rag(chunk.search_text) for chunk in chunks]
    doc_lengths = [len(tokens) or 1 for tokens in doc_tokens]
    avg_doc_len = sum(doc_lengths) / len(doc_lengths)
    query_ngrams = _char_ngrams(" ".join(expanded_tokens) or question)

    doc_freq: Counter[str] = Counter()
    for tokens in doc_tokens:
        doc_freq.update(set(tokens))

    query_counter = Counter(expanded_tokens)
    query_embedding = _hashed_embedding(" ".join(expanded_tokens) or question)
    scored: list[SchemaChunk] = []
    for chunk, tokens, doc_len in zip(chunks, doc_tokens, doc_lengths):
        token_counts = Counter(tokens)
        table_tokens = set(_tokenize_for_rag(chunk.table_name))
        column_tokens = set(_tokenize_for_rag(" ".join(chunk.columns)))
        text_token_set = set(tokens)

        score = 0.0
        matched_terms: set[str] = set()
        reasons: list[str] = []

        for token, query_weight in query_counter.items():
            if token not in token_counts:
                continue
            matched_terms.add(token)
            idf = math.log(1 + (len(chunks) - doc_freq[token] + 0.5) / (doc_freq[token] + 0.5))
            tf = token_counts[token]
            denominator = tf + 1.5 * (1 - 0.75 + 0.75 * doc_len / avg_doc_len)
            score += idf * ((tf * 2.5) / denominator) * max(1, query_weight)

        table_matches = sorted(set(expanded_tokens) & table_tokens)
        column_matches = sorted(set(expanded_tokens) & column_tokens)
        weak_matches = sorted(set(expanded_tokens) & text_token_set)
        if table_matches:
            score += 8.0 * len(table_matches)
            reasons.append(f"table match: {', '.join(table_matches)}")
            matched_terms.update(table_matches)
        if column_matches:
            score += 4.0 * len(column_matches)
            reasons.append(f"column match: {', '.join(column_matches)}")
            matched_terms.update(column_matches)
        if weak_matches and not (table_matches or column_matches):
            reasons.append(f"schema text match: {', '.join(weak_matches[:6])}")

        semantic_score = _cosine_counter_similarity(query_ngrams, _char_ngrams(chunk.search_text))
        if semantic_score > 0:
            score += semantic_weight * semantic_score
            reasons.append(f"semantic similarity: {semantic_score:.2f}")

        embedding_score = _cosine_vector_similarity(query_embedding, _hashed_embedding(chunk.search_text))
        if embedding_score > 0:
            score += embedding_weight * embedding_score
            reasons.append(f"embedding similarity: {embedding_score:.2f}")

        scored.append(
            SchemaChunk(
                table_name=chunk.table_name,
                ddl=chunk.ddl,
                columns=chunk.columns,
                foreign_tables=chunk.foreign_tables,
                search_text=chunk.search_text,
                value_hints=chunk.value_hints,
                score=score,
                matched_terms=sorted(matched_terms),
                match_reasons=reasons,
            )
        )

    selected = sorted(scored, key=lambda c: (-c.score, c.table_name))[:top_k]
    if all(chunk.score == 0 for chunk in selected):
        selected = sorted(scored, key=lambda c: c.table_name)[:top_k]

    selected_names = {chunk.table_name for chunk in selected}
    if include_neighbors > 0:
        chunk_by_name = {chunk.table_name: chunk for chunk in scored}
        frontier = list(selected)
        for depth in range(include_neighbors):
            next_frontier: list[SchemaChunk] = []
            for chunk in frontier:
                for neighbor in chunk.foreign_tables:
                    if neighbor in chunk_by_name and neighbor not in selected_names:
                        selected_names.add(neighbor)
                        neighbor_chunk = chunk_by_name[neighbor]
                        next_frontier.append(
                            SchemaChunk(
                                table_name=neighbor_chunk.table_name,
                                ddl=neighbor_chunk.ddl,
                                columns=neighbor_chunk.columns,
                                foreign_tables=neighbor_chunk.foreign_tables,
                                search_text=neighbor_chunk.search_text,
                                value_hints=neighbor_chunk.value_hints,
                                score=max(neighbor_chunk.score, chunk.score * (0.35 / (depth + 1))),
                                matched_terms=neighbor_chunk.matched_terms or [],
                                match_reasons=[
                                    *(neighbor_chunk.match_reasons or []),
                                    f"foreign-key neighbor of {chunk.table_name}",
                                ],
                            )
                        )
            selected.extend(next_frontier)
            frontier = next_frontier

    selected = sorted(selected, key=lambda c: (-c.score, c.table_name))
    retrieved_schema_chars = _schema_prompt_chars(selected)
    return SchemaRetrievalResult(
        selected,
        query_tokens,
        expanded_tokens,
        top_k,
        decomposed_terms=decomposed_terms,
        full_schema_chars=full_schema_chars,
        retrieved_schema_chars=retrieved_schema_chars,
        cache_hit=cache_hit,
    )


def retrieve_relevant_schema(
    db_path: str,
    question: str,
    *,
    top_k: int = DEFAULT_RAG_TOP_K,
) -> str:
    return retrieve_schema_context(db_path, question, top_k=top_k).schema_text
