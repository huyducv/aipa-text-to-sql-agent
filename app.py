"""
Streamlit UI for the Text-to-SQL agent (`text_to_sql_agent_mvp`).

Run locally:
    streamlit run app.py

Ensure `GEMINI_API_KEY` is set in `.env` in the project root (or in your environment).
"""

from __future__ import annotations

import html
import json
import os
import tempfile
import time
import uuid
from pathlib import Path

import pandas as pd
import streamlit as st

import text_to_sql_agent_mvp as backend

backend.load_env()

GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "Custom",
]

OLLAMA_MODELS = [
    "gemma3",
    "llama3.1",
    "llama3",
    "mistral",
    "qwen2.5",
    "Custom",
]

DEMO_DATABASES = {
    "University": {
        "path": "data/university_agent.db",
        "description": "Students, courses, grades, majors",
        "questions": [
            "How many students are enrolled in each major?",
            "What is the average score for each course?",
            "Which students have the highest average score?",
        ],
    },
    "Retail Analytics": {
        "path": "data/retail_analytics.db",
        "description": "Customers, orders, products, returns, stores",
        "questions": [
            "Show total completed sales revenue by customer region.",
            "Which return reasons occur most often?",
            "Which product categories generate the most revenue?",
        ],
    },
    "Healthcare Analytics": {
        "path": "data/healthcare_analytics.db",
        "description": "Patients, doctors, hospitals, appointments, treatments",
        "questions": [
            "How many appointments are there for each status?",
            "What is the average treatment cost by hospital city?",
            "Which specialties have the most completed appointments?",
        ],
    },
}

_CHAT_CSS = """
<style>
    .stApp {
        background: #faf9f5;
    }
    [data-testid="stSidebar"] {
        background: #f0efe9 !important;
        border-right: 1px solid #e8e6e1;
    }
    [data-testid="stHeader"] {
        background: #faf9f5;
    }
    section[data-testid="stSidebar"] .block-container {
        padding-top: 1.5rem;
    }
    .main .block-container {
        max-width: 52rem;
        padding-top: 1.25rem;
        padding-bottom: 4rem;
    }
    .stMarkdown, [data-testid="stChatMessage"] {
        font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
        color: #1f1f1f;
    }
    [data-testid="stChatInput"] textarea {
        border-radius: 1rem !important;
        border: 1px solid #e3e0d8 !important;
        background: #fff !important;
        padding-left: 1rem !important;
    }

    /* Right-align user messages (content we wrap in .chat-user-wrap) */
    .chat-user-wrap {
        display: flex;
        justify-content: flex-end;
        width: 100%;
    }
    .chat-user-row {
        display: flex;
        justify-content: flex-end;
        align-items: flex-start;
        gap: 0.55rem;
        width: 100%;
    }
    .chat-user-bubble {
        max-width: min(42rem, 85%);
        background: #e9f2ff;
        border: 1px solid #d7e6ff;
        padding: 0.55rem 0.8rem;
        border-radius: 1rem;
        margin-left: auto;
        word-wrap: break-word;
        white-space: pre-wrap;
    }
    .chat-user-avatar {
        width: 2rem;
        height: 2rem;
        border-radius: 999px;
        background: #ff4b4b;
        display: flex;
        align-items: center;
        justify-content: center;
        color: #ffffff;
        font-weight: 700;
        font-size: 0.95rem;
        flex: 0 0 auto;
        border: 1px solid rgba(0,0,0,0.06);
    }
</style>
"""


def _streamlit_secret(name: str) -> str:
    try:
        return str(st.secrets.get(name, "") or "")
    except Exception:
        return ""


def _active_gemini_key(typed_key: str) -> str:
    return (
        (typed_key or "").strip()
        or (os.environ.get("GEMINI_API_KEY") or "").strip()
        or _streamlit_secret("GEMINI_API_KEY").strip()
    )


def _model_name_for_provider(provider: str) -> str:
    selected = st.session_state.get("sb_model_choice", "")
    if selected == "Custom":
        return (st.session_state.get("sb_custom_model") or "").strip()
    return str(selected or (backend.DEFAULT_MODEL_NAME if provider == "gemini" else backend.DEFAULT_OLLAMA_MODEL))


def _write_uploaded_db(uploaded) -> str:
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    Path(path).write_bytes(uploaded.getbuffer())
    return path


def _write_uploaded_csvs(uploaded_list: list) -> list[str]:
    d = Path(tempfile.mkdtemp(prefix="streamlit_csv_"))
    paths: list[str] = []
    for uf in uploaded_list:
        p = d / uf.name
        p.write_bytes(uf.getbuffer())
        paths.append(str(p))
    return paths


def _result_to_dataframe(result: backend.QueryResult) -> pd.DataFrame | None:
    if not result.columns:
        return None
    return pd.DataFrame(result.rows, columns=result.columns)


def _active_db_path() -> str | None:
    """Resolve DB path from sidebar widgets (with caching for uploads)."""
    source = st.session_state.get("sb_source", "Demo database")

    if source == "Demo database":
        demo_name = st.session_state.get("sb_demo_db", "University")
        demo = DEMO_DATABASES.get(demo_name)
        if not demo:
            return None
        p = Path(demo["path"])
        return str(p.resolve()) if p.is_file() else None

    if source == "Path on disk":
        raw = (st.session_state.get("sb_path_db") or "").strip()
        if not raw:
            return None
        p = Path(raw).expanduser()
        return str(p.resolve()) if p.is_file() else None

    if source == "Upload `.db`":
        uf = st.session_state.get("sb_upload_db")
        if uf is None:
            return None
        sig = ("db", uf.name, getattr(uf, "size", 0))
        key = f"_db_upload_{hash(sig)}"
        if key not in st.session_state:
            st.session_state[key] = _write_uploaded_db(uf)
        return st.session_state[key]

    # CSV(s)
    files = st.session_state.get("sb_upload_csv")
    if not files:
        return None
    sig = tuple(sorted((f.name, getattr(f, "size", 0)) for f in files))
    if st.session_state.get("_csv_sig") != sig:
        try:
            csv_paths = _write_uploaded_csvs(list(files))
            out_db = Path(tempfile.gettempdir()) / f"ingested_{uuid.uuid4().hex}.db"
            st.session_state["_csv_db_path"] = backend.ingest_csvs_to_db(
                csv_paths, str(out_db)
            )
            st.session_state["_csv_sig"] = sig
        except Exception:
            st.session_state["_csv_db_path"] = None
            st.session_state["_csv_sig"] = None
            raise
    return st.session_state.get("_csv_db_path")


def _load_evaluation_cases() -> list[dict]:
    path = Path("evaluation/cases.json")
    if not path.is_file():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _normalise_rows(rows: list[tuple]) -> list[list[str]]:
    return [[str(value) for value in row] for row in rows]


def _canonical_value(value: object) -> str:
    if isinstance(value, (int, float)):
        return str(round(float(value), 2))
    text = str(value).strip()
    try:
        return str(round(float(text), 2))
    except ValueError:
        return text.lower()


def _value_rows_match(generated: list[tuple], gold: list[tuple]) -> bool:
    generated_rows = sorted(tuple(_canonical_value(value) for value in row) for row in generated)
    gold_rows = sorted(tuple(_canonical_value(value) for value in row) for row in gold)
    return generated_rows == gold_rows


def _evaluate_cases(
    *,
    mode: str,
    provider: str,
    model_name: str,
    use_rag: bool,
    rag_top_k: int,
) -> pd.DataFrame:
    rows: list[dict] = []
    for case in _load_evaluation_cases():
        started = time.perf_counter()
        gold_sql = case["gold_sql"]
        gold_result = backend.execute_query(case["db_path"], gold_sql)

        if mode == "Gold SQL baseline":
            generated_sql = gold_sql
            result = gold_result
        else:
            generated_sql, result = backend.ask_database_with_sql(
                case["question"],
                db_path=case["db_path"],
                model_name=model_name,
                provider=provider,
                use_rag=use_rag,
                rag_top_k=rag_top_k,
            )

        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        exact_match = (
            result.error is None
            and result.columns == gold_result.columns
            and _normalise_rows(result.rows) == _normalise_rows(gold_result.rows)
        )
        expected_tables = set(case.get("expected_tables", []))
        rag_context = backend.retrieve_schema_context(
            case["db_path"],
            case["question"],
            top_k=rag_top_k,
        )
        retrieved_tables = {chunk.table_name for chunk in rag_context.chunks}
        schema_recall = (
            round(len(expected_tables & retrieved_tables) / len(expected_tables), 3)
            if expected_tables
            else None
        )
        rows.append(
            {
                "case": case["id"],
                "dataset": case["dataset"],
                "difficulty": case["difficulty"],
                "safe_sql": backend.is_safe_query(generated_sql),
                "executed": result.error is None,
                "row_match": _normalise_rows(result.rows) == _normalise_rows(gold_result.rows),
                "value_match": _value_rows_match(result.rows, gold_result.rows),
                "exact_match": exact_match,
                "schema_recall": schema_recall,
                "prompt_saved_pct": rag_context.prompt_savings_pct,
                "cache_hit": rag_context.cache_hit,
                "expected_tables": ", ".join(sorted(expected_tables)),
                "retrieved_tables": ", ".join(sorted(retrieved_tables)),
                "latency_ms": latency_ms,
                "error": result.error or "",
            }
        )
    return pd.DataFrame(rows)


def _render_assistant_turn(msg: dict) -> None:
    with st.chat_message("assistant"):
        if msg.get("kind") == "text":
            st.markdown(msg.get("content", ""))
            return
        if msg.get("kind") == "result":
            if msg.get("error_text"):
                if msg.get("df") is not None:
                    st.warning(msg["error_text"])
                else:
                    st.error(msg["error_text"])
                if msg.get("blocked_sql"):
                    st.code(msg["blocked_sql"], language="sql")
            if msg.get("df") is not None:
                df = msg["df"]
                if not df.empty:
                    st.dataframe(df, use_container_width=True, hide_index=True)
                else:
                    st.caption("No rows returned.")
            if msg.get("sql_text"):
                with st.expander("Generated SQL", expanded=False):
                    st.code(msg["sql_text"], language="sql")
            if msg.get("schema_text"):
                with st.expander("Schema (DDL)", expanded=False):
                    st.code(msg["schema_text"], language="sql")
            if msg.get("rag_report"):
                with st.expander("Schema RAG retrieval report", expanded=False):
                    st.text(msg["rag_report"])


def main() -> None:
    st.set_page_config(
        page_title="Text-to-SQL",
        page_icon=":material/database:",
        layout="centered",
        initial_sidebar_state="expanded",
    )
    st.markdown(_CHAT_CSS, unsafe_allow_html=True)

    if "messages" not in st.session_state:
        st.session_state.messages = []

    with st.sidebar:
        st.markdown("### Text-to-SQL")
        st.caption("Local SQLite | read-only SQL | Gemini or Ollama")

        provider = st.selectbox(
            "LLM provider",
            ["gemini", "ollama"],
            key="sb_provider",
            help="Use Gemini API or a local Ollama model.",
        )

        model_options = GEMINI_MODELS if provider == "gemini" else OLLAMA_MODELS
        default_model = backend.DEFAULT_MODEL_NAME if provider == "gemini" else backend.DEFAULT_OLLAMA_MODEL
        default_index = model_options.index(default_model) if default_model in model_options else 0
        st.selectbox(
            "Model",
            model_options,
            index=default_index,
            key="sb_model_choice",
            help="Choose a known model or select Custom to type another model name.",
        )
        if st.session_state.get("sb_model_choice") == "Custom":
            st.text_input(
                "Custom model name",
                value=default_model,
                key="sb_custom_model",
                help="Use the exact provider model identifier.",
            )
        model_name = _model_name_for_provider(provider)

        gemini_key = ""
        if provider == "gemini":
            with st.expander("Gemini API key", expanded=False):
                typed_key = st.text_input(
                    "API key",
                    type="password",
                    key="sb_gemini_key",
                    placeholder="Leave blank to use Streamlit secrets or local .env",
                    help="Session-only input. Do not commit API keys to GitHub.",
                )
                gemini_key = _active_gemini_key(typed_key)
                if gemini_key:
                    os.environ["GEMINI_API_KEY"] = gemini_key

        key_ok = provider == "ollama" or bool(gemini_key)
        if provider == "gemini" and key_ok:
            st.success("Gemini API key loaded", icon=":material/check_circle:")
        elif provider == "gemini":
            st.warning("Add a key above, in `.env`, or in Streamlit secrets.", icon=":material/warning:")
        else:
            st.info("Using local Ollama. Make sure Ollama is running.")

        use_rag = st.toggle(
            "Use schema RAG",
            value=True,
            key="sb_use_rag",
            help="Retrieve only the most relevant table schemas before prompting.",
        )
        rag_top_k = st.slider(
            "Schema tables to retrieve",
            min_value=1,
            max_value=12,
            value=backend.DEFAULT_RAG_TOP_K,
            key="sb_rag_top_k",
            disabled=not use_rag,
        )


        st.divider()
        st.markdown("**Database**")

        st.radio(
            "Source",
            ["Demo database", "Path on disk", "Upload `.db`", "Upload CSV(s)"],
            key="sb_source",
            label_visibility="collapsed",
        )

        if st.session_state.get("sb_source") == "Demo database":
            demo_name = st.selectbox(
                "Demo database",
                list(DEMO_DATABASES),
                key="sb_demo_db",
            )
            demo = DEMO_DATABASES[demo_name]
            st.caption(demo["description"])
            st.caption(f"Using `{Path(demo['path']).name}`")

        elif st.session_state.get("sb_source") == "Path on disk":
            st.text_input(
                "Path to `.db`",
                value="data/university_agent.db",
                key="sb_path_db",
            )
            p = Path(st.session_state.get("sb_path_db", "")).expanduser()
            if st.session_state.get("sb_path_db") and p.is_file():
                st.caption(f"Using `{p.name}`")
            elif st.session_state.get("sb_path_db"):
                st.caption("File not found - adjust path or create demo below.")

        elif st.session_state.get("sb_source") == "Upload `.db`":
            st.file_uploader("SQLite file", type=["db"], key="sb_upload_db")
            uf = st.session_state.get("sb_upload_db")
            if uf is not None:
                st.caption(f"Uploaded `{uf.name}`")

        else:
            st.file_uploader(
                "CSV files",
                type=["csv"],
                accept_multiple_files=True,
                key="sb_upload_csv",
            )
            if st.session_state.get("sb_upload_csv"):
                st.caption("Tables use the CSV file names (without `.csv`).")

        with st.expander("Demo data"):
            st.text_input(
                "Write demo university DB to",
                value="data/university_agent.db",
                key="sb_demo_path",
            )
            if st.button("Create demo `.db`", use_container_width=True):
                demo_out = st.session_state.get("sb_demo_path", "data/university_agent.db")
                Path(demo_out).parent.mkdir(parents=True, exist_ok=True)
                try:
                    backend.write_university_db(demo_out)
                    st.success("Saved.")
                except Exception as e:
                    st.error(str(e))

        with st.expander("Evaluation"):
            eval_mode = st.selectbox(
                "Mode",
                ["Gold SQL baseline", "Selected LLM"],
                key="sb_eval_mode",
                help="Gold SQL validates the benchmark. Selected LLM compares model output with gold query results.",
            )
            if st.button("Run benchmark", use_container_width=True):
                if eval_mode == "Selected LLM" and not key_ok:
                    st.error("Add an API key or choose Ollama before running LLM evaluation.")
                else:
                    with st.spinner("Evaluating demo databases..."):
                        st.session_state["evaluation_df"] = _evaluate_cases(
                            mode=eval_mode,
                            provider=provider,
                            model_name=model_name,
                            use_rag=use_rag,
                            rag_top_k=rag_top_k,
                        )
                        st.session_state["evaluation_mode"] = eval_mode

        st.divider()
        if st.button("Clear conversation", use_container_width=True):
            st.session_state.messages = []
            st.rerun()

    db_path_to_query: str | None = None
    try:
        db_path_to_query = _active_db_path()
    except Exception as e:
        st.sidebar.error(f"Ingestion failed: {e}")

    st.markdown(
        "<p style='font-size:1.65rem;font-weight:600;margin-bottom:0.15rem;color:#141413;'>Text-to-SQL</p>"
        "<p style='font-size:0.95rem;color:#6b6b6b;margin-top:0;'>Ask questions about your connected database.</p>",
        unsafe_allow_html=True,
    )

    if st.session_state.get("sb_source") == "Demo database":
        demo_name = st.session_state.get("sb_demo_db", "University")
        demo = DEMO_DATABASES.get(demo_name, DEMO_DATABASES["University"])
        st.markdown(f"**Active demo:** {demo_name} - {demo['description']}")
        sample_prompt = st.selectbox(
            "Try a sample question",
            [""] + demo["questions"],
            key="main_sample_question",
            label_visibility="collapsed",
        )
        if sample_prompt and st.button("Use sample question", type="secondary", disabled=not key_ok):
            st.session_state.messages.append({"role": "user", "content": sample_prompt})
            sql_text, result = backend.ask_database_with_sql(
                sample_prompt,
                db_path=str(Path(demo["path"]).resolve()),
                model_name=model_name,
                provider=provider,
                use_rag=use_rag,
                rag_top_k=rag_top_k,
            )
            df_out = _result_to_dataframe(result) if result.columns else None
            rag_report = None
            schema_text = None
            try:
                rag_context = backend.retrieve_schema_context(
                    str(Path(demo["path"]).resolve()),
                    sample_prompt,
                    top_k=rag_top_k,
                )
                rag_report = rag_context.report
                schema_text = rag_context.schema_text
            except Exception:
                pass
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "kind": "result",
                    "error_text": result.error,
                    "blocked_sql": result.sql if result.error else None,
                    "df": df_out,
                    "sql_text": sql_text,
                    "schema_text": schema_text,
                    "rag_report": rag_report,
                }
            )
            st.rerun()

    eval_df = st.session_state.get("evaluation_df")
    if isinstance(eval_df, pd.DataFrame) and not eval_df.empty:
        with st.expander(f"Evaluation summary - {st.session_state.get('evaluation_mode', 'Benchmark')}", expanded=True):
            total = len(eval_df)
            safe = int(eval_df["safe_sql"].sum())
            executed = int(eval_df["executed"].sum())
            value = int(eval_df["value_match"].sum())
            exact = int(eval_df["exact_match"].sum())
            avg_latency = float(eval_df["latency_ms"].mean())
            avg_recall = float(eval_df["schema_recall"].mean())
            avg_saved = float(eval_df["prompt_saved_pct"].mean())
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Safe SQL", f"{safe}/{total}")
            c2.metric("Executed", f"{executed}/{total}")
            c3.metric("Value match", f"{value}/{total}")
            c4.metric("Schema recall", f"{avg_recall:.2f}")
            c5.metric("Prompt saved", f"{avg_saved:.1f}%")
            st.caption(f"Average latency: {avg_latency:.0f} ms")
            st.dataframe(eval_df, use_container_width=True, hide_index=True)
            recall_df = eval_df[
                ["case", "dataset", "schema_recall", "prompt_saved_pct", "expected_tables", "retrieved_tables"]
            ]
            st.bar_chart(recall_df.set_index("case")["schema_recall"])
            with st.expander("Schema recall details", expanded=False):
                st.dataframe(recall_df, use_container_width=True, hide_index=True)

    if not st.session_state.messages:
        st.session_state.messages.append(
            {
                "role": "assistant",
                "kind": "text",
                "content": (
                    "Choose a database in the **sidebar**, then ask a question below. "
                    "I generate read-only SQL and show results as a table."
                ),
            }
        )

    for msg in st.session_state.messages:
        if msg["role"] == "user":
            safe = html.escape(str(msg.get("content", "")))
            st.markdown(
                "<div class='chat-user-wrap'>"
                "<div class='chat-user-row'>"
                f"<div class='chat-user-bubble'>{safe}</div>"
                "<div class='chat-user-avatar'>You</div>"
                "</div>"
                "</div>",
                unsafe_allow_html=True,
            )
        else:
            _render_assistant_turn(msg)

    chat_disabled = db_path_to_query is None or not key_ok
    placeholder = (
        "Connect a database in the sidebar..."
        if db_path_to_query is None
        else "Ask anything about your data..."
    )
    prompt = st.chat_input(placeholder, disabled=chat_disabled)

    if prompt and db_path_to_query and key_ok:
        st.session_state.messages.append({"role": "user", "content": prompt.strip()})

        sql_text, result = backend.ask_database_with_sql(
            prompt.strip(),
            db_path=db_path_to_query,
            model_name=(model_name or "").strip() or (
                backend.DEFAULT_MODEL_NAME if provider == "gemini" else backend.DEFAULT_OLLAMA_MODEL
            ),
            provider=provider,
            use_rag=use_rag,
            rag_top_k=rag_top_k,
        )

        error_text = None
        blocked_sql = None
        df_out: pd.DataFrame | None = None

        if result.error:
            error_text = result.error
            blocked_sql = result.sql

        if result.columns:
            df_out = _result_to_dataframe(result)

        schema_text: str | None = None
        rag_report: str | None = None
        try:
            if use_rag:
                rag_context = backend.retrieve_schema_context(
                    db_path_to_query,
                    prompt.strip(),
                    top_k=rag_top_k,
                )
                schema_text = rag_context.schema_text
                rag_report = rag_context.report
            else:
                schema_text = backend.get_schema(db_path_to_query)
        except Exception:
            pass

        st.session_state.messages.append(
            {
                "role": "assistant",
                "kind": "result",
                "error_text": error_text,
                "blocked_sql": blocked_sql,
                "df": df_out,
                "sql_text": sql_text,
                "schema_text": schema_text,
                "rag_report": rag_report,
            }
        )
        st.rerun()


if __name__ == "__main__":
    main()
