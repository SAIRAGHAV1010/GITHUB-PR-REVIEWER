"""
Thin wrapper around the GitHub REST API for the two things this service needs:
1. Pulling the file-level diff for a PR
2. Posting the aggregated review back as a PR comment
"""
from __future__ import annotations

import httpx
from app.config import get_settings

GITHUB_API = "https://api.github.com"


class GitHubClient:
    def __init__(self, token: str | None = None):
        settings = get_settings()
        self.token = token or settings.github_token
        self._headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def get_pr_files(self, owner: str, repo: str, pr_number: int) -> list[dict]:
        """Returns the list of changed files with their unified diff ('patch')."""
        url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}/files"
        files: list[dict] = []
        page = 1
        async with httpx.AsyncClient(timeout=30) as client:
            while True:
                resp = await client.get(
                    url, headers=self._headers, params={"per_page": 100, "page": page}
                )
                resp.raise_for_status()
                batch = resp.json()
                if not batch:
                    break
                files.extend(batch)
                page += 1
                if len(batch) < 100:
                    break
        return files

    async def get_pr_metadata(self, owner: str, repo: str, pr_number: int) -> dict:
        url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls/{pr_number}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=self._headers)
            resp.raise_for_status()
            return resp.json()

    async def post_review_comment(
        self, owner: str, repo: str, pr_number: int, body: str
    ) -> dict:
        """Posts a single top-level PR comment containing the aggregated review.
        (Line-level comments can be added later via the /comments endpoint using
        the 'path' + 'position' fields returned per-file from get_pr_files.)
        """
        url = f"{GITHUB_API}/repos/{owner}/{repo}/issues/{pr_number}/comments"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, headers=self._headers, json={"body": body})
            resp.raise_for_status()
            return resp.json()
