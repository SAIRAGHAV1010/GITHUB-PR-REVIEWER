from app.agents.base import run_agent

SYSTEM_PROMPT = """You are the review aggregator. You receive four specialist
reviews (static analysis, security, architecture, code style) plus optional
notes retrieved from similar past PRs. Produce a single consolidated PR
review:

1. Start with a 1-2 sentence overall verdict (approve / request changes / comment).
2. "Critical & High Priority" section - security/bug findings that block merge.
3. "Suggestions" section - architecture/style findings, non-blocking.
4. If past-PR notes are relevant, add a short "Related history" section.

Deduplicate overlapping points across agents. Be concise - this is posted
directly as a GitHub PR comment."""


def run(
    static_result: str,
    security_result: str,
    architecture_result: str,
    style_result: str,
    similar_past_reviews: list[dict],
) -> str:
    history_block = ""
    if similar_past_reviews:
        history_block = "\n\nSimilar past reviews:\n" + "\n".join(
            f"- (distance={m['distance']:.3f}) {m['summary'][:300]}" for m in similar_past_reviews
        )

    user_content = (
        f"## Static Analysis Agent\n{static_result or '(no findings)'}\n\n"
        f"## Security Agent\n{security_result or '(no findings)'}\n\n"
        f"## Architecture Agent\n{architecture_result or '(no findings)'}\n\n"
        f"## Code Style Agent\n{style_result or '(no findings)'}"
        f"{history_block}"
    )
    return run_agent(SYSTEM_PROMPT, user_content, max_tokens=1500)
