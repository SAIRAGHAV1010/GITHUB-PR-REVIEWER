"""
Shared helper all agents use to call the LLM. Kept in one place so
model choice, retries, and (optional) Langfuse tracing only need to be
wired once.
"""
from __future__ import annotations

import anthropic

from app.config import get_settings

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        settings = get_settings()
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


def run_agent(system_prompt: str, user_content: str, max_tokens: int = 1024) -> str:
    """Synchronous single-turn call. Celery tasks are sync by default, so
    agents stay sync too rather than mixing event loops."""
    settings = get_settings()
    client = _get_client()

    response = client.messages.create(
        model=settings.llm_model,
        max_tokens=max_tokens,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )
    return "".join(block.text for block in response.content if block.type == "text")
