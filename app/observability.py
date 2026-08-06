"""
Cross-cutting observability. Prometheus metrics are exposed via a
/metrics endpoint on the FastAPI app (scraped by the Prometheus container
in docker-compose). Langfuse tracing is optional - if keys aren't set,
the tracer is a no-op so the app still runs without it.
"""
from __future__ import annotations

import time
from contextlib import contextmanager

from prometheus_client import Counter, Histogram

from app.config import get_settings

WEBHOOKS_RECEIVED = Counter(
    "pr_reviewer_webhooks_received_total", "PR webhooks received", ["event_action"]
)
REVIEWS_COMPLETED = Counter(
    "pr_reviewer_reviews_completed_total", "Reviews completed", ["status"]
)
AGENT_LATENCY = Histogram(
    "pr_reviewer_agent_latency_seconds", "Per-agent LLM call latency", ["agent_name"]
)
PIPELINE_LATENCY = Histogram(
    "pr_reviewer_pipeline_latency_seconds", "End-to-end review pipeline latency"
)


@contextmanager
def track_agent_latency(agent_name: str):
    start = time.perf_counter()
    try:
        yield
    finally:
        AGENT_LATENCY.labels(agent_name=agent_name).observe(time.perf_counter() - start)


def get_langfuse_client():
    """Returns a Langfuse client if configured, else None. Callers should
    guard usage with `if client:` so tracing is fully optional."""
    settings = get_settings()
    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        return None
    from langfuse import Langfuse

    return Langfuse(
        public_key=settings.langfuse_public_key,
        secret_key=settings.langfuse_secret_key,
        host=settings.langfuse_host,
    )
