"""
Entry point. Receives GitHub webhooks, verifies the HMAC signature, and
dispatches a Celery task for PR opened/synchronize events. Keeps the
webhook handler itself fast (<1s) so GitHub doesn't retry/time it out -
all real work happens asynchronously in the worker.
"""
from __future__ import annotations

import hashlib
import hmac
import logging

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.config import get_settings
from app.observability import WEBHOOKS_RECEIVED
from app.tasks import review_pull_request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI PR Reviewer", version="0.1.0")

ELIGIBLE_ACTIONS = {"opened", "synchronize", "reopened"}


def _verify_signature(payload_body: bytes, signature_header: str | None, secret: str) -> None:
    if not secret:
        # Allow running without a secret in local dev; never do this in prod.
        return
    if not signature_header or not signature_header.startswith("sha256="):
        raise HTTPException(status_code=401, detail="Missing/invalid signature header")

    expected = "sha256=" + hmac.new(
        secret.encode(), payload_body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, signature_header):
        raise HTTPException(status_code=401, detail="Signature verification failed")


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/webhook/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None),
    x_github_event: str | None = Header(default=None),
):
    settings = get_settings()
    body = await request.body()
    _verify_signature(body, x_hub_signature_256, settings.github_webhook_secret)

    if x_github_event != "pull_request":
        return {"status": "ignored", "reason": f"event '{x_github_event}' not handled"}

    payload = await request.json()
    action = payload.get("action")
    WEBHOOKS_RECEIVED.labels(event_action=action or "unknown").inc()

    if action not in ELIGIBLE_ACTIONS:
        return {"status": "ignored", "reason": f"action '{action}' not eligible"}

    pr = payload["pull_request"]
    owner = payload["repository"]["owner"]["login"]
    repo = payload["repository"]["name"]
    pr_number = pr["number"]

    review_pull_request.delay(owner, repo, pr_number)
    logger.info("Queued review for %s/%s#%s", owner, repo, pr_number)

    return {"status": "queued", "pr": f"{owner}/{repo}#{pr_number}"}
