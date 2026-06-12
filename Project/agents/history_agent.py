"""
History agent — checks if a new question can be answered from conversation history.

Uses an LLM to semantically match the new question against previous questions,
so rephrased or follow-up questions still hit the cache instead of the DB.

Returns the index of the matching history entry, or -1 if no match found.
"""

from agents.llm_client import get_summariser_client, chat


SYSTEM_PROMPT = """You are a conversation history checker.

You are given a list of previously answered questions (with their summaries) and a new question.
Your job is to decide if the new question is already answered — fully or partially — by any previous question.

Rules:
- Consider rephrased questions, synonyms, and follow-up questions as matches.
- Only return a match if the previous answer would fully satisfy the new question.
- If the new question asks for something more specific or different, it is NOT a match.
- Reply with ONLY the index number (0-based) of the matching question, or -1 if no match.
- No explanation. Just the number."""


def find_in_history(new_question: str, history: list[dict]) -> int:
    """
    Semantically check if new_question is already answered in history.

    Args:
        new_question: The question the user just asked.
        history: List of previous entries, each with 'question' and 'summary' keys.

    Returns:
        Index of the matching history entry, or -1 if none found.
        Returns -1 immediately if history is empty (no LLM call made).
    """
    if not history:
        return -1

    # Build a compact history list for the prompt
    history_text = "\n".join(
        f"[{i}] Q: {entry['question']}\n    A summary: {entry['summary']}"
        for i, entry in enumerate(history)
    )

    user_message = f"""Previous questions and answers:
{history_text}

New question: {new_question}

Which index answers the new question? Reply with only the number (-1 if none):"""

    try:
        response = chat(
            client=get_summariser_client(),   # reuse the Qwen client
            system_prompt=SYSTEM_PROMPT,
            user_message=user_message,
            max_tokens=10,        # just a number
            temperature=0.0,
        )
        # Parse just the integer out of the response
        for token in response.strip().split():
            try:
                idx = int(token)
                if -1 <= idx < len(history):
                    return idx
            except ValueError:
                continue
        return -1

    except Exception:
        # On any failure, fall through to DB — never block the user
        return -1
