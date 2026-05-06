"""
Streamlit UI for the Text-to-SQL agent (`text_to_sql_agent_mvp`).

Run locally:
    streamlit run app.py

Ensure `GEMINI_API_KEY` is set in `.env` in the project root (or in your environment).
"""

from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path

import pandas as pd
import streamlit as st

import text_to_sql_agent_mvp as backend

backend.load_env()

_CLAUDE_CSS = """
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
    }
</style>
"""


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


def _message_history() -> list[dict[str, str]]:
    history: list[dict[str, str]] = []
    for msg in st.session_state.get("messages", []):
        if msg.get("role") != "assistant" or msg.get("kind") != "result":
            continue
        if msg.get("question") and msg.get("sql") and not msg.get("error_text"):
            history.append({"question": msg["question"], "sql": msg["sql"]})
    return history


def _active_db_path() -> str | None:
    """Resolve DB path from sidebar widgets (with caching for uploads)."""
    source = st.session_state.get("sb_source", "Path on disk")

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


def _render_assistant_turn(msg: dict) -> None:
    with st.chat_message("assistant"):
        if msg.get("kind") == "text":
            st.markdown(msg.get("content", ""))
            return
        if msg.get("kind") == "result":
            if msg.get("plan"):
                plan = msg["plan"]
                with st.expander("Analysis plan", expanded=False):
                    st.markdown(f"**Intent:** {plan.get('intent', '')}")
                    if plan.get("tables"):
                        st.markdown(f"**Tables:** {', '.join(map(str, plan['tables']))}")
                    if plan.get("columns"):
                        st.markdown(f"**Columns:** {', '.join(map(str, plan['columns']))}")
                    if plan.get("assumptions"):
                        st.markdown("**Assumptions:**")
                        for item in plan["assumptions"]:
                            st.markdown(f"- {item}")

            if msg.get("answer"):
                st.markdown(msg["answer"])
            if msg.get("sql_explanation"):
                with st.expander("SQL explanation", expanded=False):
                    st.markdown(msg["sql_explanation"])
            if msg.get("sql") and not msg.get("error_text"):
                with st.expander("Generated SQL", expanded=False):
                    st.code(msg["sql"], language="sql")

            if msg.get("error_text"):
                if msg.get("df") is not None:
                    st.warning(msg["error_text"])
                else:
                    st.error(msg["error_text"])
                if msg.get("sql"):
                    st.code(msg["sql"], language="sql")
            if msg.get("df") is not None:
                df = msg["df"]
                if not df.empty:
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    if msg.get("chart"):
                        chart = msg["chart"]
                        try:
                            chart_df = df.set_index(chart["x"])
                            if chart.get("type") == "line":
                                st.line_chart(chart_df[[chart["y"]]])
                            else:
                                st.bar_chart(chart_df[[chart["y"]]])
                        except Exception:
                            pass
                else:
                    st.caption("No rows returned.")
            if msg.get("followups"):
                with st.expander("Suggested follow-up questions", expanded=False):
                    for q in msg["followups"]:
                        st.markdown(f"- {q}")
            if msg.get("repair_attempts"):
                with st.expander("SQL repair attempts", expanded=False):
                    for attempt in msg["repair_attempts"]:
                        st.caption(attempt.get("error", ""))
                        st.code(attempt.get("to", ""), language="sql")
            if msg.get("schema_text"):
                with st.expander("Schema (DDL)", expanded=False):
                    st.code(msg["schema_text"], language="sql")
            if msg.get("audit_path"):
                st.caption(f"Audit log: `{msg['audit_path']}`")


def _append_analyst_response(response: backend.AnalystResponse) -> None:
    result = response.result
    df_out = _result_to_dataframe(result) if result.columns else None
    st.session_state.messages.append(
        {
            "role": "assistant",
            "kind": "result",
            "question": response.question,
            "plan": response.plan,
            "answer": response.answer,
            "sql_explanation": response.sql_explanation,
            "error_text": result.error,
            "sql": result.sql,
            "df": df_out,
            "chart": response.chart,
            "followups": response.followups or [],
            "repair_attempts": response.repair_attempts or [],
            "schema_text": response.schema_text,
            "audit_path": response.audit_path,
        }
    )


def main() -> None:
    st.set_page_config(
        page_title="Text-to-SQL",
        page_icon=":material/database:",
        layout="centered",
        initial_sidebar_state="expanded",
    )
    st.markdown(_CLAUDE_CSS, unsafe_allow_html=True)

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "pending_approval" not in st.session_state:
        st.session_state.pending_approval = None

    with st.sidebar:
        st.markdown("### Text-to-SQL")
        st.caption("Local SQLite | read-only SQL | Gemini")

        key_ok = bool((os.environ.get("GEMINI_API_KEY") or "").strip())
        if key_ok:
            st.success("API key loaded", icon=":material/check_circle:")
        else:
            st.warning("Add `GEMINI_API_KEY` to `.env`", icon=":material/warning:")

        model_name = st.text_input(
            "Model",
            value=backend.DEFAULT_MODEL_NAME,
            key="sb_model",
            help="Must match a model your API key can access.",
        )

        st.divider()
        st.markdown("**Agent controls**")
        approval_mode = st.toggle(
            "Human approval before execution",
            value=False,
            key="sb_approval_mode",
        )
        summarize_mode = st.toggle(
            "Generate answer narrative",
            value=True,
            key="sb_summarize_mode",
        )
        glossary_text = st.text_area(
            "Business glossary",
            value="",
            key="sb_glossary",
            height=96,
            placeholder="Example: revenue means SUM(sales.amount)",
        )
        denied_columns_text = st.text_input(
            "Denied columns",
            value=", ".join(sorted(backend.DEFAULT_DENIED_COLUMNS)),
            key="sb_denied_columns",
            help="Comma-separated columns the agent is not allowed to query.",
        )

        st.divider()
        st.markdown("**Database**")

        st.radio(
            "Source",
            ["Path on disk", "Upload `.db`", "Upload CSV(s)"],
            key="sb_source",
            label_visibility="collapsed",
        )

        if st.session_state.get("sb_source") == "Path on disk":
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

        st.divider()
        if st.button("Clear conversation", use_container_width=True):
            st.session_state.messages = []
            st.session_state.pending_approval = None
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
            with st.chat_message("user"):
                st.markdown(msg["content"])
        else:
            _render_assistant_turn(msg)

    pending = st.session_state.get("pending_approval")
    if pending:
        st.info("Review the generated SQL before execution.")
        st.code(pending["sql"], language="sql")
        col_run, col_cancel = st.columns(2)
        with col_run:
            if st.button("Run approved SQL", type="primary", use_container_width=True):
                response = backend.analyze_database(
                    pending["question"],
                    db_path=pending["db_path"],
                    model_name=pending["model_name"],
                    glossary_text=pending["glossary_text"],
                    history=pending["history"],
                    denied_columns=pending["denied_columns"],
                    require_approval=False,
                    approved_sql=pending["sql"],
                    summarize=pending["summarize"],
                )
                _append_analyst_response(response)
                st.session_state.pending_approval = None
                st.rerun()
        with col_cancel:
            if st.button("Cancel", use_container_width=True):
                st.session_state.pending_approval = None
                st.rerun()

    chat_disabled = db_path_to_query is None or not key_ok or bool(st.session_state.get("pending_approval"))
    placeholder = (
        "Review the pending SQL above..."
        if st.session_state.get("pending_approval")
        else (
            "Connect a database in the sidebar..."
            if db_path_to_query is None
            else "Ask anything about your data..."
        )
    )
    prompt = st.chat_input(placeholder, disabled=chat_disabled)

    if prompt and db_path_to_query and key_ok:
        st.session_state.messages.append({"role": "user", "content": prompt.strip()})

        denied_columns = {
            item.strip().lower()
            for item in (denied_columns_text or "").split(",")
            if item.strip()
        }
        response = backend.analyze_database(
            prompt.strip(),
            db_path=db_path_to_query,
            model_name=(model_name or "").strip() or backend.DEFAULT_MODEL_NAME,
            glossary_text=glossary_text,
            history=_message_history(),
            denied_columns=denied_columns,
            require_approval=approval_mode,
            summarize=summarize_mode,
        )

        if response.result.error == "AWAITING_APPROVAL":
            st.session_state.pending_approval = {
                "question": prompt.strip(),
                "sql": response.result.sql,
                "db_path": db_path_to_query,
                "model_name": (model_name or "").strip() or backend.DEFAULT_MODEL_NAME,
                "glossary_text": glossary_text,
                "history": _message_history(),
                "denied_columns": denied_columns,
                "summarize": summarize_mode,
            }
        else:
            _append_analyst_response(response)
        st.rerun()


if __name__ == "__main__":
    main()
