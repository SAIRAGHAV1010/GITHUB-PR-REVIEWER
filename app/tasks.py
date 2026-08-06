"""
The Celery task dispatched for every PR opened/synchronize webhook event.
This is the async worker side of the pipeline: fetch PR data -> build
context -> run the LangGraph agent graph -> post the review -> index it
for future retrieval.
"""
from __future__ import annotations

import asyncio
import logging
import time

from app.celery_app import celery_app
from app.context_collector import build_pr_context
from app.github_client import GitHubClient
from app.graph import get_review_graph
from app.observability import PIPELINE_LATENCY, REVIEWS_COMPLETED
from app.vector_store import index_review

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Celery workers are sync; this runs a one-off event loop per task
    invocation for the async GitHub API calls."""
    return asyncio.run(coro)


@celery_app.task(name="app.tasks.review_pull_request", bind=True, max_retries=2)
def review_pull_request(self, owner: str, repo: str, pr_number: int):
    start = time.perf_counter()
    try:
        client = GitHubClient()

        metadata = _run_async(client.get_pr_metadata(owner, repo, pr_number))
        raw_files = _run_async(client.get_pr_files(owner, repo, pr_number))

        pr_context = build_pr_context(owner, repo, pr_number, metadata, raw_files)
        context_block = pr_context.as_prompt_block()

        graph = get_review_graph()
        final_state = graph.invoke({"pr_context_block": context_block})

        review_body = final_state["aggregated_result"]
        review_body += f"\n\n---\n*Automated review by the multi-agent PR reviewer covering {len(pr_context.files)} file(s).*"

        _run_async(client.post_review_comment(owner, repo, pr_number, review_body))

        index_review(
            pr_id=f"{owner}/{repo}#{pr_number}",
            summary_text=review_body,
            metadata={"owner": owner, "repo": repo, "pr_number": pr_number, "title": pr_context.title},
        )

        REVIEWS_COMPLETED.labels(status="success").inc()
        return {"status": "success", "pr": f"{owner}/{repo}#{pr_number}"}

    except Exception as exc:
        logger.exception("Review pipeline failed for %s/%s#%s", owner, repo, pr_number)
        REVIEWS_COMPLETED.labels(status="failure").inc()
        raise self.retry(exc=exc, countdown=30)
    finally:
        PIPELINE_LATENCY.observe(time.perf_counter() - start)
