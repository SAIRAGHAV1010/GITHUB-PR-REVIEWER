from app.context_collector import build_pr_context

RAW_FILES = [
    {
        "filename": "app/utils.py",
        "status": "modified",
        "additions": 3,
        "deletions": 0,
        "patch": "@@ -1,2 +1,5 @@\n def existing():\n     pass\n+\n+def new_helper(x):\n+    return x * 2",
    }
]

METADATA = {"title": "Add helper function", "body": "Adds new_helper for reuse."}


def test_build_pr_context_extracts_symbols():
    ctx = build_pr_context("acme", "widgets", 42, METADATA, RAW_FILES)

    assert ctx.pr_number == 42
    assert ctx.files[0].filename == "app/utils.py"
    assert "new_helper" in ctx.files[0].python_symbols


def test_prompt_block_includes_title_and_patch():
    ctx = build_pr_context("acme", "widgets", 42, METADATA, RAW_FILES)
    block = ctx.as_prompt_block()

    assert "Add helper function" in block
    assert "new_helper" in block
