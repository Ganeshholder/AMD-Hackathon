"""
Router agent — uses an LLM to decide which DB table answers the user's question.
Returns a list of table names to scope the SQL agent's schema.

Special return value:
- ["AMBIGUOUS"] → model couldn't determine the table; UI should ask the user to clarify.
"""

from config.settings import TABLE_METADATA
from agents.llm_client import get_router_client, chat


def _build_schema_summary() -> str:
    lines = []
    for table, info in TABLE_METADATA.items():
        cols = ", ".join(info["columns"].keys())
        lines.append(f"- {table}: {info['description']} | columns: {cols}")
    return "\n".join(lines)


SYSTEM_PROMPT = """You are a database routing assistant.
Your only job is to read a user question and return the names of the relevant database tables.
Reply with ONLY a comma-separated list of table names — no explanation, no punctuation, no extra words.
If the question is ambiguous and could apply equally to multiple tables, or you cannot confidently identify the right table, reply with exactly: AMBIGUOUS

{active_context}

Available tables:
{schema}"""


def route(question: str, active_tables: list[str] | None = None) -> list[str]:
    """
    Ask the LLM which tables are relevant for the question.

    Args:
        question: The user's natural language question.
        active_tables: Currently active table context. If provided, the router
                       will only switch tables if the question CLEARLY refers
                       to a different table by name or strong context clue.

    Returns:
        - List of valid table names if the model is confident.
        - ["AMBIGUOUS"] if the model cannot determine the right table.
        - All known tables as fallback on any exception.
    """
    known = list(TABLE_METADATA.keys())
    schema_summary = _build_schema_summary()

    # If there's an active table, tell the router to stick with it unless
    # the question explicitly refers to a different table
    if active_tables:
        active_hint = (
            f"IMPORTANT: The user is currently working with table(s): {', '.join(active_tables)}. "
            f"Only switch to a different table if the question EXPLICITLY mentions another table name "
            f"or clearly refers to data that does NOT exist in {', '.join(active_tables)}. "
            f"Otherwise, return: {', '.join(active_tables)}"
        )
    else:
        active_hint = ""

    system = SYSTEM_PROMPT.format(schema=schema_summary, active_context=active_hint)

    try:
        response = chat(
            client=get_router_client(),
            system_prompt=system,
            user_message=question,
            max_tokens=50,
            temperature=0.0,
        )

        # Check if model flagged ambiguity
        if "AMBIGUOUS" in response.upper():
            return ["AMBIGUOUS"]

        # Parse and filter to known table names only
        tables = [t.strip() for t in response.split(",") if t.strip() in known]

        # Safety net: if active table exists and router returned unknown tables,
        # fall back to active table rather than guessing
        if not tables and active_tables:
            return active_tables

        return tables if tables else known

    except Exception:
        # Never block the user — fall back to active table or full schema
        return active_tables if active_tables else known
