"""Enforce that no Markdown files exist in specs/ except README.md and AGENTS.md.

This test prevents regression: once all spec content lives in YAML files,
no new .md files should be introduced into the specs/ directory.
AGENTS.md is a per-directory agent-guidance file and is intentionally allowed.
"""

from pathlib import Path

SPECS_DIR = Path(__file__).parents[2] / "specs"

ALLOWED_MD_FILES = {"README.md", "AGENTS.md"}


def test_no_markdown_in_specs_except_readme():
    """specs/ MUST contain no .md files other than README.md and AGENTS.md."""
    md_files = sorted(SPECS_DIR.glob("*.md"))
    unexpected = [f for f in md_files if f.name not in ALLOWED_MD_FILES]
    assert unexpected == [], (
        f"Unexpected Markdown files in specs/: {[str(f) for f in unexpected]}. "
        "Spec content must live in YAML files."
    )
