from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "pr_reviewer",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_track_started=True,
    task_time_limit=600,   # hard cap: a stuck LLM call shouldn't hang a worker forever
)

# Ensures tasks module is registered with this app when the worker starts
# (celery -A app.celery_app worker ...)
import app.tasks  # noqa: E402,F401
