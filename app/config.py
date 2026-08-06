"""
Centralized configuration. All values are read from environment variables
(see .env.example). Uses pydantic-settings so misconfiguration fails fast
at startup instead of silently at request time.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- GitHub ---
    github_token: str = ""            # PAT or GitHub App installation token, needs repo + pull_requests scope
    github_webhook_secret: str = ""   # used to verify X-Hub-Signature-256

    # --- LLM ---
    anthropic_api_key: str = ""
    llm_model: str = "claude-sonnet-4-5"

    # --- Redis / Celery ---
    redis_url: str = "redis://localhost:6379/0"

    # --- Vector store ---
    chroma_persist_dir: str = "./chroma_data"
    chroma_collection: str = "pr_review_history"

    # --- Observability ---
    prometheus_port: int = 9100
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # --- App ---
    max_diff_chars_per_file: int = 6000   # truncate huge files before sending to the LLM
    max_files_per_pr: int = 25


@lru_cache
def get_settings() -> Settings:
    return Settings()
