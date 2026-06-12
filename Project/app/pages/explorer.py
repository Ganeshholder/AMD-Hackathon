"""
Table Explorer page — browse raw table data and basic stats.
"""

import streamlit as st

from database.db_client import get_table_names, get_table_preview, execute_query
from config.settings import TABLE_METADATA


def render() -> None:
    st.title("📊 Table Explorer")
    st.caption("Browse your database tables and preview the data.")

    st.divider()

    tables = get_table_names()
    if not tables:
        st.warning("No tables found in the database. Run `python -m database.seed` to seed it.")
        return

    selected = st.selectbox("Select a table", tables)

    if not selected:
        return

    # Table metadata card
    if selected in TABLE_METADATA:
        meta = TABLE_METADATA[selected]
        with st.expander("Table Info", expanded=False):
            st.write(f"**Description:** {meta['description']}")
            st.write(f"**Columns:** {', '.join(meta['columns'].keys())}")

    # Row count
    try:
        count_df = execute_query(f"SELECT COUNT(*) AS total FROM {selected}")
        total = int(count_df["total"].iloc[0])
        st.metric("Total Rows", f"{total:,}")
    except Exception as e:
        st.error(f"Could not count rows: {e}")

    # Preview
    st.subheader("Preview (first 100 rows)")
    try:
        preview = execute_query(f"SELECT * FROM {selected} LIMIT 100")
        st.dataframe(preview, use_container_width=True)
    except Exception as e:
        st.error(f"Could not load preview: {e}")
