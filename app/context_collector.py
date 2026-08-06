"""
Context Collector: turns raw GitHub 'files' payloads into a normalized,
size-bounded context blob the agents can reason over. Does light AST
parsing for Python files to extract function/class signatures touched by
the diff, which gives the agents structural context beyond the raw patch.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass, field

from app.config import get_settings


@dataclass
class FileContext:
    filename: str
    status: str          # added / modified / removed / renamed
    patch: str            # unified diff (truncated)
    additions: int
    deletions: int
    python_symbols: list[str] = field(default_factory=list)


@dataclass
class PRContext:
    owner: str
    repo: str
    pr_number: int
    title: str
    body: str
    files: list[FileContext]

    def as_prompt_block(self) -> str:
        parts = [f"PR #{self.pr_number}: {self.title}\n{self.body or ''}\n"]
        for f in self.files:
            symbol_note = f" | symbols: {', '.join(f.python_symbols)}" if f.python_symbols else ""
            parts.append(
                f"\n--- {f.filename} ({f.status}, +{f.additions}/-{f.deletions}){symbol_note} ---\n"
                f"{f.patch}"
            )
        return "\n".join(parts)


def _extract_python_symbols(source_fragment: str) -> list[str]:
    """Best-effort symbol extraction. Diff patches aren't valid standalone
    Python, so this only succeeds for hunks that happen to parse; failures
    are swallowed since this is a context enrichment, not a correctness
    requirement."""
    symbols: list[str] = []
    try:
        tree = ast.parse(source_fragment)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                symbols.append(node.name)
    except SyntaxError:
        pass
    return symbols


def build_pr_context(
    owner: str, repo: str, pr_number: int, metadata: dict, raw_files: list[dict]
) -> PRContext:
    settings = get_settings()
    files: list[FileContext] = []

    for raw in raw_files[: settings.max_files_per_pr]:
        patch = (raw.get("patch") or "")[: settings.max_diff_chars_per_file]

        # Pull only the '+' added lines out of the patch to attempt a parse -
        # this catches new function/class defs without needing the full file.
        added_lines = "\n".join(
            line[1:] for line in patch.splitlines() if line.startswith("+") and not line.startswith("+++")
        )
        symbols = _extract_python_symbols(added_lines) if raw["filename"].endswith(".py") else []

        files.append(
            FileContext(
                filename=raw["filename"],
                status=raw.get("status", "modified"),
                patch=patch,
                additions=raw.get("additions", 0),
                deletions=raw.get("deletions", 0),
                python_symbols=symbols,
            )
        )

    return PRContext(
        owner=owner,
        repo=repo,
        pr_number=pr_number,
        title=metadata.get("title", ""),
        body=metadata.get("body", "") or "",
        files=files,
    )
