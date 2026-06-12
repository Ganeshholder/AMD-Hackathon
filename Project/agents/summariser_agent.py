"""
Summariser agent — takes the DB query results and explains them in plain English.
"""

import pandas as pd
from agents.llm_client import get_summariser_client, chat


SYSTEM_PROMPT = """You are a helpful data analyst assistant.
The user asked a question and a SQL query was run against a database.
Your job is to summarise the query results in clear, concise plain English.
- Highlight key numbers, trends, or patterns.
- Keep the summary to 3-5 sentences max.
- Do not repeat the raw data row by row.
- If the result is empty, say so clearly."""


def summarise(question: str, df: pd.DataFrame) -> str:
    """
    Summarise the DataFrame results in the context of the original question.

    Args:
        question: The original user question.
        df: The DataFrame returned by executing the SQL query.

    Returns:
        A plain English summary string.
    """
    if df.empty:
        return "The query returned no results. Try rephrasing your question or check the filters."

    # Send a compact representation — cap at 20 rows to stay within token limits
    row_count = len(df)
    sample = df.head(20).to_string(index=False)

    user_message = f"""User question: {question}

Total rows returned: {row_count}
{"(showing first 20 rows)" if row_count > 20 else ""}

Data:
{sample}

Please summarise the above results."""

    try:
        return chat(
            client=get_summariser_client(),
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            max_tokens=300,
            temperature=0.3,
        )
    except Exception as e:
        return f"Could not generate summary: {e}"
