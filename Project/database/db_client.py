"""
SQLite database access layer.
All queries go through this module — no raw sqlite3 calls elsewhere.
"""

import sqlite3
import pandas as pd
from config.settings import DB_PATH


def get_connection() -> sqlite3.Connection:
    """Return a new SQLite connection to the configured DB path."""
    return sqlite3.connect(DB_PATH)


def execute_query(sql: str) -> pd.DataFrame:
    """
    Execute a SELECT query and return results as a DataFrame.

    Args:
        sql: Valid SQLite SELECT statement.

    Returns:
        DataFrame with query results.

    Raises:
        ValueError: If the SQL string is empty.
        Exception: Propagates SQLite errors to the caller for UI handling.
    """
    if not sql or not sql.strip():
        raise ValueError("SQL query cannot be empty.")

    conn = get_connection()
    try:
        df = pd.read_sql_query(sql, conn)
        return df
    finally:
        conn.close()


def get_table_names() -> list[str]:
    """Return all user-defined table names in the database."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
        )
        return [row[0] for row in cursor.fetchall()]
    finally:
        conn.close()


def get_table_preview(table_name: str, limit: int = 5) -> pd.DataFrame:
    """Return the first N rows of a table for preview purposes."""
    # Table name is not user-supplied at runtime, but sanitize anyway
    allowed = get_table_names()
    if table_name not in allowed:
        raise ValueError(f"Unknown table: {table_name}")
    return execute_query(f"SELECT * FROM {table_name} LIMIT {limit}")
