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
Available tables:
{schema}"""


def route(question: str) -> list[str]:
    """
    Ask the LLM which tables are relevant for the question.

    Returns:
        - List of valid table names if the model is confident.
        - ["AMBIGUOUS"] if the model cannot determine the right table.
        - All known tables as fallback on any exception.
    """
    known = list(TABLE_METADATA.keys())
    schema_summary = _build_schema_summary()

    system = SYSTEM_PROMPT.format(schema=schema_summary)

    try:
        response = chat(
            client=get_router_client(),
            system_prompt=system,
            user_message=question,
            max_tokens=50,       # table names are short
            temperature=0.0,     # deterministic
        )

        # Check if model flagged ambiguity
        if "AMBIGUOUS" in response.upper():
            return ["AMBIGUOUS"]

        # Parse and filter to known table names only
        tables = [t.strip() for t in response.split(",") if t.strip() in known]
        return tables if tables else known

    except Exception:
        # Never block the user — fall back to full schema
        return known
