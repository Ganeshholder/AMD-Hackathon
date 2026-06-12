"""
Streamlit entry point.

Run with:
    streamlit run main.py
"""

import streamlit as st

from app.pages import home, explorer

# --- Page config ---
st.set_page_config(
    page_title="Text-to-SQL Analytics",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --- Sidebar navigation --
with st.sidebar:
    st.title("🔍 Analytics App")
    st.divider()
    page = st.radio(
        "Navigation",
        ["Query", "Table Explorer"],
        label_visibility="collapsed",
    )
    st.divider()
    st.caption("AMD Hackathon 2026")

# --- Route to page ---
if page == "Query":
    home.render()
elif page == "Table Explorer":
    explorer.render()
