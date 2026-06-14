"""
HuggingFace InferenceClient wrapper.

Provider mapping:
- Qwen/Qwen2.5-72B-Instruct  → Novita       (chat_completion)
- defog/sqlcoder-7b-2         → Featherless AI (text_generation)
"""

from huggingface_hub import InferenceClient
from config.settings import HF_TOKEN, ROUTER_MODEL, SUMMARISER_MODEL, SQL_MODEL

# Provider per model
_MODEL_PROVIDER: dict[str, str] = {
    "Qwen/Qwen2.5-72B-Instruct": "novita",
    "defog/sqlcoder-7b-2":        "featherless-ai",
}


def _build_client(model: str) -> InferenceClient:
    if not HF_TOKEN:
        raise EnvironmentError("HF_TOKEN is not set. Add it to your .env file.")
    provider = _MODEL_PROVIDER.get(model, "novita")
    return InferenceClient(model=model, token=HF_TOKEN, provider=provider)


# Singletons
_clients: dict[str, InferenceClient] = {}


def _get(model: str) -> InferenceClient:
    if model not in _clients:
        _clients[model] = _build_client(model)
    return _clients[model]


def get_router_client() -> InferenceClient:
    return _get(ROUTER_MODEL)


def get_sql_client() -> InferenceClient:
    return _get(SQL_MODEL)


def get_summariser_client() -> InferenceClient:
    return _get(SUMMARISER_MODEL)


def chat(
    client: InferenceClient,
    system_prompt: str,
    user_message: str,
    max_tokens: int = 300,
    temperature: float = 0.1,
) -> str:
    """
    chat_completion for instruct/chat models (Qwen2.5 etc.).
    Returns the assistant reply as plain text.
    """
    response = client.chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message},
        ],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    return response.choices[0].message.content.strip()


def generate(
    client: InferenceClient,
    prompt: str,
    max_new_tokens: int = 300,
    temperature: float = 0.0,
    do_sample: bool = False,
) -> str:
    """
    text_generation for raw-prompt models (sqlcoder-7b-2).
    Use do_sample=False as recommended by defog for deterministic output.
    """
    response = client.text_generation(
        prompt,
        max_new_tokens=max_new_tokens,
        temperature=temperature,
        do_sample=do_sample,
    )
    return response.strip()
