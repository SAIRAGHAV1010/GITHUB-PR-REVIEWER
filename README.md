# AI Multi-Agent GitHub PR Reviewer

A multi-agent code review system that listens for GitHub pull-request
webhooks, runs four specialist LLM agents in parallel over the diff via
LangGraph, aggregates their findings into a single consensus review, posts
it back as a PR comment, and indexes it into a vector store so future PRs
benefit from a self-learning RAG layer.

## Architecture

```
GitHub Webhook → FastAPI + Celery/Redis → LangGraph Multi-Agent Engine
                                              ├─ Static Analysis Agent
                                              ├─ Security Agent        ─┐
                                              ├─ Architecture Agent     ├─→ Review Aggregator → GitHub API
                                              └─ Code Style Agent      ─┘         │
                                                                                   ↓
                                                                         PostgreSQL/Vector DB
                                                                        (indexed for next PR)

Observability (Prometheus, Grafana, Langfuse) — cross-cutting
```

## Stack

- **API**: FastAPI (webhook receiver, `/metrics` endpoint)
- **Queue**: Celery + Redis (async task dispatch, so webhook responses stay fast)
- **Orchestration**: LangGraph (fan-out to 4 agents, fan-in to aggregator)
- **LLM**: Anthropic Claude (`app/agents/base.py` — swap models via `.env`)
- **Vector store**: ChromaDB, persisted locally, for self-learning RAG
- **Observability**: Prometheus metrics + optional Langfuse tracing

## Setup

```bash
git clone <this-repo>
cd pr-reviewer
cp .env.example .env   # fill in GITHUB_TOKEN, GITHUB_WEBHOOK_SECRET, ANTHROPIC_API_KEY
docker compose up --build
```

This starts:
| Service | Port |
|---|---|
| API (webhook + `/metrics`) | `8000` |
| Redis | `6379` |
| Prometheus | `9090` |
| Grafana | `3000` |

Point a GitHub webhook (repo → Settings → Webhooks) at:
```
https://<your-public-url>/webhook/github
Content type: application/json
Secret: same value as GITHUB_WEBHOOK_SECRET
Events: Pull requests
```

For local testing without a public URL, use `ngrok http 8000` and use the
forwarding URL as the webhook target.

## Running without Docker

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload &
celery -A app.celery_app worker --loglevel=info &
```

## Testing

```bash
pip install pytest
pytest tests/ -v
```

## How a review runs

1. GitHub sends a `pull_request` webhook (`opened`/`synchronize`/`reopened`).
2. `app/main.py` verifies the HMAC signature and enqueues
   `app.tasks.review_pull_request` on Celery — the HTTP response returns
   immediately so GitHub doesn't time out the webhook.
3. The Celery worker fetches PR metadata + file diffs via
   `app/github_client.py`, and `app/context_collector.py` builds a
   size-bounded context block (with light AST symbol extraction for
   Python files).
4. `app/graph.py` runs the LangGraph pipeline: four agents execute
   concurrently, plus a `retrieve_history` node pulls similar past reviews
   from ChromaDB; all five feed into `aggregate`.
5. The aggregated review is posted back to the PR via the GitHub Issues
   Comments API, then indexed into ChromaDB for future retrieval.
6. Prometheus counters/histograms track webhook volume, per-agent latency,
   and pipeline latency throughout.

## Known limitations (prototype scope)

- Posts one top-level PR comment rather than line-level review comments
  (the GitHub Files API response already has what's needed to extend this —
  see the docstring in `github_client.post_review_comment`).
- No GitHub App / installation-token flow yet — uses a personal access token.
- ChromaDB runs embedded/local rather than as a separate service; swap for
  a hosted Chroma/PostgreSQL+pgvector instance for multi-instance deployments.
- No rate-limiting/backoff on the GitHub API beyond Celery's built-in retry.

## License

MIT
