"""
SQL agent — converts a natural language question into a SQLite SQL query.
Uses defog/sqlcoder-7b-2 via text_generation on Featherless AI provider.

Prompt format follows the official sqlcoder-7b-2 recommendation:
  do_sample=False  (deterministic)
  Prompt: ### Task / ### Database Schema / ### Answer [QUESTION]...[/QUESTION] [SQL]

Schema reference JSON (schema_reference.json) is loaded at startup and injected
into every prompt so the model sees exact column names and valid values —
preventing hallucinated tables, columns, and values.
"""

import re
import json
import os
from config.settings import TABLE_METADATA, SQL_MAX_NEW_TOKENS
from agents.llm_client import get_sql_client, generate
from agents.sql_validator import validate_and_fix

# ── Load schema reference JSON once at module load ────────────────────────────
_SCHEMA_REF_PATH = os.path.join(os.path.dirname(__file__), "..", "schema_reference.json")

def _load_schema_ref() -> dict:
    try:
        with open(_SCHEMA_REF_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

SCHEMA_REF = _load_schema_ref()


# ── Build the value guide from schema_reference.json ─────────────────────────
def _build_value_guide(tables: list[str]) -> str:
    """
    Build a compact column → valid values guide from the reference JSON.
    Only includes TEXT columns with known unique values.
    """
    lines = []
    for table in tables:
        if table not in SCHEMA_REF:
            continue
        lines.append(f"Valid column values for {table}:")
        for col, info in SCHEMA_REF[table]["columns"].items():
            vals = info.get("unique_values", [])
            if vals:
                vals_str = ", ".join(f'"{v}"' for v in vals[:20])
                lines.append(f"  {col}: {vals_str}")
        lines.append("")
    return "\n".join(lines)


# ── Build DDL schema ───────────────────────────────────────────────────────────
def _build_schema_ddl(tables: list[str]) -> str:
    """Build DDL-style schema with column descriptions for the given tables."""
    lines = []
    for table in tables:
        if table not in TABLE_METADATA:
            continue
        info = TABLE_METADATA[table]
        col_defs = ",\n".join(
            f"    {col}  -- {desc}"
            for col, desc in info["columns"].items()
        )
        lines.append(
            f"-- {info['description']}\n"
            f"CREATE TABLE {table} (\n{col_defs}\n);"
        )
    return "\n\n".join(lines)


# ── Extract SQL from model output ─────────────────────────────────────────────
def _extract_sql(raw: str) -> str:
    """Pull the SELECT statement out of the model output."""
    raw = re.sub(r"```(?:sql)?", "", raw, flags=re.IGNORECASE).strip("`").strip()
    match = re.search(r"(SELECT\b.*?)(?:;|$)", raw, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return raw.strip()


# ── Main generate function ────────────────────────────────────────────────────
def generate_sql(question: str, tables: list[str]) -> str:
    """
    Generate a SQLite3 SQL query using the official sqlcoder-7b-2 prompt format.

    Args:
        question: Natural language question from the user.
        tables:   Table names identified by the router agent.

    Returns:
        A SQL query string.
    """
    schema_ddl  = _build_schema_ddl(tables)
    value_guide = _build_value_guide(tables)
    all_tables  = list(TABLE_METADATA.keys())
    target      = tables[0] if len(tables) == 1 else ", ".join(tables)

    prompt = f"""### Task
Generate a SQL query to answer [QUESTION]{question}[/QUESTION]

The database contains ONLY these tables: {', '.join(all_tables)}
Use ONLY table: {target}
Do NOT use any table not listed above.
Use ONLY the columns listed in the schema below — no other columns exist.

### Column Value Reference
Use this to match filter values to the correct column.
If a value appears in a column's list below, use THAT column in the WHERE clause.
{value_guide}
### Database Schema
The query will run on a database with the following schema:
{schema_ddl}

### Answer
Given the database schema, here is the SQL query that [QUESTION]{question}[/QUESTION]
[SQL]"""

    raw = generate(
        client=get_sql_client(),
        prompt=prompt,
        max_new_tokens=SQL_MAX_NEW_TOKENS,
        do_sample=False,
    )
    sql = _extract_sql(raw)

    # Cross-check with Qwen — fix hallucinated tables/columns/values before hitting DB
    sql = validate_and_fix(sql, tables, question)

    return sql
