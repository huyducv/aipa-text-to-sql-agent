from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import text_to_sql_agent_mvp as agent

RETRYABLE_ERROR_MARKERS = (
    "429",
    "RESOURCE_EXHAUSTED",
    "quota",
    "rate",
)


def _normalise_rows(rows: list[tuple[Any, ...]]) -> list[list[str]]:
    return [[str(value) for value in row] for row in rows]


def _canonical_value(value: Any) -> str:
    if isinstance(value, (int, float)):
        return str(round(float(value), 2))
    text = str(value).strip()
    try:
        return str(round(float(text), 2))
    except ValueError:
        return text.lower()


def _value_rows_match(generated: list[tuple[Any, ...]], gold: list[tuple[Any, ...]]) -> bool:
    generated_rows = sorted(tuple(_canonical_value(value) for value in row) for row in generated)
    gold_rows = sorted(tuple(_canonical_value(value) for value in row) for row in gold)
    return generated_rows == gold_rows


def _run_gold(case: dict[str, Any]) -> tuple[str, agent.QueryResult]:
    sql = case["gold_sql"]
    if not agent.is_safe_query(sql):
        return sql, agent.QueryResult(columns=[], rows=[], sql=sql, error="GOLD_SQL_UNSAFE")
    return sql, agent.execute_query(case["db_path"], sql)


def _run_llm(
    case: dict[str, Any],
    *,
    provider: str,
    model_name: str,
    use_rag: bool,
    rag_top_k: int,
    max_retries: int = 0,
    retry_base_seconds: float = 20.0,
) -> tuple[str, agent.QueryResult]:
    attempt = 0
    while True:
        sql, result = agent.ask_database_with_sql(
            case["question"],
            db_path=case["db_path"],
            model_name=model_name,
            provider=provider,
            use_rag=use_rag,
            rag_top_k=rag_top_k,
        )
        error_text = (result.error or "").lower()
        retryable = any(marker.lower() in error_text for marker in RETRYABLE_ERROR_MARKERS)
        if not retryable or attempt >= max_retries:
            return sql, result
        sleep_for = retry_base_seconds * (2 ** attempt)
        print(f"Retryable LLM error for {case['id']}; sleeping {sleep_for:.0f}s before retry...")
        time.sleep(sleep_for)
        attempt += 1


def evaluate_case(
    case: dict[str, Any],
    *,
    mode: str,
    provider: str,
    model_name: str,
    use_rag: bool,
    rag_top_k: int,
    max_retries: int = 0,
    retry_base_seconds: float = 20.0,
) -> dict[str, Any]:
    started = time.perf_counter()
    gold_sql, gold_result = _run_gold(case)

    if mode == "gold":
        generated_sql, result = gold_sql, gold_result
    else:
        generated_sql, result = _run_llm(
            case,
            provider=provider,
            model_name=model_name,
            use_rag=use_rag,
            rag_top_k=rag_top_k,
            max_retries=max_retries,
            retry_base_seconds=retry_base_seconds,
        )

    latency_ms = round((time.perf_counter() - started) * 1000, 2)
    generated_rows = _normalise_rows(result.rows)
    gold_rows = _normalise_rows(gold_result.rows)
    rows_match = result.error is None and gold_result.error is None and generated_rows == gold_rows
    value_match = (
        result.error is None
        and gold_result.error is None
        and _value_rows_match(result.rows, gold_result.rows)
    )
    exact_result_match = (
        rows_match and result.columns == gold_result.columns
    )
    expected_tables = set(case.get("expected_tables", []))
    retrieved_tables: set[str] = set()
    rag_context = agent.retrieve_schema_context(
        case["db_path"],
        case["question"],
        top_k=rag_top_k,
    )
    if expected_tables:
        retrieved_tables = {chunk.table_name for chunk in rag_context.chunks}
    table_recall = (
        round(len(expected_tables & retrieved_tables) / len(expected_tables), 3)
        if expected_tables
        else ""
    )

    return {
        "id": case["id"],
        "dataset": case["dataset"],
        "difficulty": case["difficulty"],
        "mode": mode,
        "provider": provider if mode == "llm" else "gold",
        "model_name": model_name if mode == "llm" else "gold_sql",
        "use_rag": use_rag if mode == "llm" else "",
        "rag_top_k": rag_top_k if mode == "llm" else "",
        "safe_sql": agent.is_safe_query(generated_sql),
        "execution_ok": result.error is None,
        "row_match": rows_match,
        "value_match": value_match,
        "exact_result_match": exact_result_match,
        "schema_table_recall": table_recall,
        "prompt_saved_pct": rag_context.prompt_savings_pct,
        "cache_hit": rag_context.cache_hit,
        "expected_tables": ", ".join(sorted(expected_tables)),
        "retrieved_tables": ", ".join(sorted(retrieved_tables)),
        "latency_ms": latency_ms,
        "error": result.error or "",
        "generated_sql": generated_sql,
        "gold_sql": gold_sql,
    }


def write_markdown(rows: list[dict[str, Any]], output_path: Path) -> None:
    total = len(rows)
    exact = sum(1 for row in rows if row["exact_result_match"])
    row_match = sum(1 for row in rows if row["row_match"])
    value_match = sum(1 for row in rows if row["value_match"])
    safe = sum(1 for row in rows if row["safe_sql"])
    executed = sum(1 for row in rows if row["execution_ok"])
    avg_latency = round(sum(float(row["latency_ms"]) for row in rows) / total, 2) if total else 0
    recall_values = [float(row["schema_table_recall"]) for row in rows if row["schema_table_recall"] != ""]
    avg_recall = round(sum(recall_values) / len(recall_values), 3) if recall_values else 0
    avg_prompt_saved = round(sum(float(row["prompt_saved_pct"]) for row in rows) / total, 1) if total else 0

    lines = [
        "# Text-to-SQL Evaluation Results",
        "",
        f"- Cases: {total}",
        f"- Safe SQL rate: {safe}/{total}",
        f"- Execution success rate: {executed}/{total}",
        f"- Value match: {value_match}/{total}",
        f"- Row match: {row_match}/{total}",
        f"- Exact result match: {exact}/{total}",
        f"- Average schema table recall: {avg_recall}",
        f"- Average prompt schema saved: {avg_prompt_saved}%",
        f"- Average latency: {avg_latency} ms",
        "",
        "| Case | Dataset | Difficulty | Safe | Executed | Value Match | Row Match | Exact Match | Schema Recall | Prompt Saved | Latency ms |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            "| {id} | {dataset} | {difficulty} | {safe_sql} | {execution_ok} | "
            "{value_match} | {row_match} | {exact_result_match} | {schema_table_recall} | "
            "{prompt_saved_pct}% | {latency_ms} |".format(**row)
        )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate Text-to-SQL generation against gold SQL results.")
    parser.add_argument("--cases", default="evaluation/cases.json")
    parser.add_argument("--mode", choices=["gold", "llm"], default="gold")
    parser.add_argument("--provider", choices=["gemini", "ollama"], default=agent.DEFAULT_PROVIDER)
    parser.add_argument("--model", default=agent.DEFAULT_MODEL_NAME)
    parser.add_argument("--no-rag", action="store_true")
    parser.add_argument("--rag-top-k", type=int, default=agent.DEFAULT_RAG_TOP_K)
    parser.add_argument("--delay-seconds", type=float, default=0.0)
    parser.add_argument("--max-cases", type=int, default=0)
    parser.add_argument("--max-retries", type=int, default=0)
    parser.add_argument("--retry-base-seconds", type=float, default=20.0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--out-dir", default="evaluation/results")
    args = parser.parse_args()

    cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
    if args.max_cases > 0:
        cases = cases[: args.max_cases]
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.mode == "llm":
        safe_model = "".join(ch if ch.isalnum() else "_" for ch in args.model).strip("_")
        stem = f"evaluation_llm_{args.provider}_{safe_model}"
    else:
        stem = "evaluation_gold"
    csv_path = out_dir / f"{stem}.csv"
    md_path = out_dir / f"{stem}.md"

    existing_rows: dict[str, dict[str, Any]] = {}
    if args.resume and csv_path.exists():
        with csv_path.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("execution_ok") == "True":
                    existing_rows[row["id"]] = row

    rows: list[dict[str, Any]] = []
    for index, case in enumerate(cases):
        if case["id"] in existing_rows:
            rows.append(existing_rows[case["id"]])
            continue
        rows.append(
            evaluate_case(
                case,
                mode=args.mode,
                provider=args.provider,
                model_name=args.model,
                use_rag=not args.no_rag,
                rag_top_k=args.rag_top_k,
                max_retries=args.max_retries,
                retry_base_seconds=args.retry_base_seconds,
            )
        )
        if args.mode == "llm" and args.delay_seconds > 0 and index < len(cases) - 1:
            time.sleep(args.delay_seconds)

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    write_markdown(rows, md_path)

    exact = sum(1 for row in rows if row["exact_result_match"])
    print(f"Evaluated {len(rows)} cases. Exact result match: {exact}/{len(rows)}")
    print(f"Wrote {csv_path} and {md_path}")


if __name__ == "__main__":
    main()
