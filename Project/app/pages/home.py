"""
Home page — ChatGPT-style layout:
  - User message: RIGHT side, pill bubble
  - LLM answer:   LEFT side
  - Input bar:    fixed at bottom
  - Active table badge: below the input bar, always visible
  - "Steps Planned" expander: between user question and bot answer
"""

import streamlit as st

from agents.router_agent import route
from agents.sql_agent import generate_sql
from agents.summariser_agent import summarise
from agents.history_agent import find_in_history
from database.db_client import execute_query
from config.settings import TABLE_METADATA


_CHAT_CSS = """
<style>

/* ── Bottom padding so content clears the input + badge bar ── */
section.main > div.block-container {
    padding-bottom: 110px !important;
    max-width: 100% !important;
}

/* ── st.chat_input container ── */
div[data-testid="stBottom"] {
    left: 0 !important;
    right: 0 !important;
    background-color: #0e1117 !important;
    border-top: 1px solid rgba(255,255,255,0.08) !important;
    padding: 8px 24px 6px 24px !important;
    z-index: 999 !important;
}

/* ── Hide avatars ── */
[data-testid="chatAvatarIcon-user"],
[data-testid="chatAvatarIcon-assistant"] { display: none !important; }

/* ── User bubble: RIGHT ── */
.user-row {
    display: flex;
    justify-content: flex-end;
    margin: 10px 0 4px 0;
}
.user-pill {
    background: #2f2f2f;
    border-radius: 18px 18px 4px 18px;
    padding: 10px 18px;
    max-width: 60%;
    color: #f0f0f0;
    font-size: 15px;
    line-height: 1.5;
    word-wrap: break-word;
}

/* ── Bot bubble: LEFT ── */
.bot-row {
    display: flex;
    justify-content: flex-start;
    margin: 4px 0 20px 0;
}
.bot-bubble { max-width: 95%; width: 100%; }

</style>
"""


# ─── Session state ─────────────────────────────────────────────────────────────
def _init_state() -> None:
    defaults = {
        "chat_history":       [],
        "active_tables":      None,
        "ambiguous_question": None,
        "resolved_tables":    None,
        "pending_question":   None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


# ─── History lookup ────────────────────────────────────────────────────────────
def _find_in_history(question: str) -> dict | None:
    history = st.session_state.chat_history
    if not history:
        return None
    q = question.strip().lower()
    for entry in history:
        if entry["question"].strip().lower() == q:
            return entry
    idx = find_in_history(question, history)
    return history[idx] if idx >= 0 else None


# ─── Bubbles ──────────────────────────────────────────────────────────────────
def _user_bubble(text: str) -> None:
    st.markdown(
        f'<div class="user-row"><div class="user-pill">{text}</div></div>',
        unsafe_allow_html=True,
    )


def _bot_bubble(summary: str, sql: str, df, dl_key: str,
                from_cache: bool = False, original_q: str = "") -> None:
    st.markdown('<div class="bot-row"><div class="bot-bubble">', unsafe_allow_html=True)
    if from_cache:
        st.caption(f"📂 From history — originally: *\"{original_q}\"*")
    st.markdown(summary)
    with st.expander("🗃 SQL & Data", expanded=True):
        st.code(sql, language="sql")
        st.dataframe(df, use_container_width=True)
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇ Download CSV", data=csv,
                           file_name="results.csv", mime="text/csv", key=dl_key)
    st.markdown('</div></div>', unsafe_allow_html=True)


# ─── Steps Planned expander ───────────────────────────────────────────────────
def _steps_expander(steps: list[str]) -> None:
    """Show a collapsed 'Steps Planned' dropdown between question and answer."""
    with st.expander("🧠 Steps Planned", expanded=False):
        for i, step in enumerate(steps, 1):
            st.markdown(f"**{i}.** {step}")


# ─── History render (top, always expanded) ────────────────────────────────────
def _render_history() -> None:
    for i, entry in enumerate(st.session_state.chat_history):
        _user_bubble(entry["question"])
        # Show steps for history entries too
        if "steps" in entry:
            _steps_expander(entry["steps"])
        _bot_bubble(
            summary=entry["summary"],
            sql=entry["sql"],
            df=entry["df"],
            dl_key=f"dl_hist_{i}",
        )


# ─── Active badge + reset button (below chat input) ───────────────────────────
def _active_badge() -> None:
    if st.session_state.active_tables:
        tables_str = ", ".join(st.session_state.active_tables)
        col_badge, col_btn = st.columns([5, 1])
        with col_badge:
            st.markdown(
                f'<p style="color:#4a9eff; font-size:12px; margin:2px 0 0 0;">'
                f'📌 Active table: <strong>{tables_str}</strong></p>',
                unsafe_allow_html=True,
            )
        with col_btn:
            if st.button("🔄 Reset", key="reset_ctx", use_container_width=True):
                st.session_state.active_tables = None
                st.rerun()
    else:
        st.markdown(
            '<p style="color:#666; font-size:12px; margin:2px 0 0 0;">'
            '💡 No active table — ask a question to get started</p>',
            unsafe_allow_html=True,
        )


# ─── Pipeline ─────────────────────────────────────────────────────────────────
def _run_pipeline(question: str, tables: list[str], steps: list[str]) -> None:
    """Generate SQL → execute → summarise → save to history."""

    steps.append(f"🔧 Generating SQL for table(s): **{', '.join(tables)}**")
    with st.spinner("Generating SQL..."):
        try:
            sql = generate_sql(question, tables)
        except Exception as e:
            st.error(f"❌ SQL generation error: {e}")
            return

    steps.append("🗄 Executing query against the database")
    with st.spinner("Running query..."):
        try:
            df = execute_query(sql)
            steps.append(f"✅ Query returned **{len(df):,}** rows")
        except Exception as e:
            st.error(f"❌ Query error: {e}")
            return

    steps.append("✍️ Summarising results with LLM")
    with st.spinner("Summarising..."):
        try:
            summary = summarise(question, df)
            steps.append("✅ Summary ready")
        except Exception as e:
            st.error(f"❌ Summariser error: {e}")
            return

    # Show steps expander then bot answer
    _steps_expander(steps)
    _bot_bubble(summary=summary, sql=sql, df=df, dl_key="dl_current")

    st.session_state.chat_history.append({
        "question": question,
        "tables":   tables,
        "sql":      sql,
        "df":       df,
        "summary":  summary,
        "steps":    steps,
    })
    # Update active table BEFORE rerun so badge reflects new table immediately
    st.session_state.active_tables = tables
    st.rerun()


# ─── Main render ──────────────────────────────────────────────────────────────
def render() -> None:
    st.markdown(_CHAT_CSS, unsafe_allow_html=True)
    _init_state()

    st.title("🔍 Text-to-SQL Analytics")
    st.divider()

    # ── History (top, always visible) ─────────────────────────────
    _render_history()

    # ── Ambiguous picker (unchanged) ──────────────────────────────
    if (
        st.session_state.ambiguous_question
        and st.session_state.ambiguous_question == st.session_state.pending_question
        and st.session_state.resolved_tables is None
    ):
        st.warning("Which table should I query?")
        selected = st.selectbox("Choose a table", list(TABLE_METADATA.keys()), key="manual_table_select")
        if st.button("Run with selected table", key="run_with_table"):
            st.session_state.resolved_tables = [selected]
            st.rerun()
        return

    # ── Chat input (native — pins itself to bottom) ────────────────
    question = st.chat_input("Ask anything about your data...")
    if question and question.strip():
        st.session_state.pending_question = question.strip()

    # ── Active table badge — rendered after chat_input so it sits below it ──
    _active_badge()

    # ── Gate ──────────────────────────────────────────────────────
    resolved_run = st.session_state.resolved_tables is not None
    has_pending  = st.session_state.pending_question is not None
    if not has_pending and not resolved_run:
        return

    active_question = st.session_state.pending_question or ""
    if not active_question.strip():
        return
    st.session_state.pending_question = None

    # Show user bubble
    _user_bubble(active_question)

    # Build steps list — will be populated as we go
    steps: list[str] = []

    # ── Route FIRST — always, before history check ─────────────────
    # We need the target table before validating any cached answer.
    if resolved_run:
        tables = st.session_state.resolved_tables
        st.session_state.resolved_tables    = None
        st.session_state.ambiguous_question = None
        steps.append(f"📋 Table selected manually by user: **{', '.join(tables)}**")

    else:
        steps.append("🤖 Asking Router LLM to identify the relevant table")
        with st.spinner("Identifying relevant table..."):
            try:
                tables = route(active_question)
            except Exception as e:
                st.error(f"❌ Router error: {e}")
                return

        if tables == ["AMBIGUOUS"]:
            if st.session_state.active_tables:
                tables = st.session_state.active_tables
                steps.append(f"⚠️ Router was uncertain — staying on active table: **{', '.join(tables)}**")
            else:
                steps.append("⚠️ Router could not determine table — asking user to choose")
                st.session_state.ambiguous_question = active_question
                st.session_state.pending_question   = active_question
                st.session_state.resolved_tables    = None
                st.rerun()
        else:
            if st.session_state.active_tables and tables != st.session_state.active_tables:
                steps.append(f"🔄 Switching context: **{', '.join(st.session_state.active_tables)}** → **{', '.join(tables)}**")
            else:
                steps.append(f"✅ Router identified table(s): **{', '.join(tables)}**")

    # ── History cache — validated against the routed table ─────────
    # A cached answer is only reused if it queried the SAME table(s).
    steps.append("🔍 Checking conversation history for a matching answer")
    with st.spinner("Checking history..."):
        cached = _find_in_history(active_question)

    if cached and set(cached["tables"]) == set(tables):
        steps.append(f"✅ Found in history — originally asked: \"{cached['question']}\"")
        steps.append("⚡ Returning cached answer — no DB call needed")
        _steps_expander(steps)
        _bot_bubble(
            summary=cached["summary"],
            sql=cached["sql"],
            df=cached["df"],
            dl_key="dl_cached",
            from_cache=True,
            original_q=cached["question"],
        )
        # Update active table and rerun so badge reflects immediately
        st.session_state.active_tables = tables
        st.rerun()

    if cached and set(cached["tables"]) != set(tables):
        steps.append(f"⚠️ History match for different table ({', '.join(cached['tables'])}) — querying DB for **{', '.join(tables)}**")
    else:
        steps.append("❌ No match in history — will query the database")

    # ── Run pipeline ──────────────────────────────────────────────
    _run_pipeline(active_question, tables, steps)
