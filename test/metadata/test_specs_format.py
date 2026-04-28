"""Enforce that no Markdown files exist in specs/ except README.md (SPECMD.3).

This test prevents regression: once all spec content lives in YAML files,
no new .md files should be introduced into the specs/ directory.
"""

from pathlib import Path

SPECS_DIR = Path(__file__).parents[2] / "specs"


def test_no_markdown_in_specs_except_readme():
    """specs/ MUST contain no .md files other than README.md."""
    md_files = sorted(SPECS_DIR.glob("*.md"))
    unexpected = [f for f in md_files if f.name != "README.md"]
    assert unexpected == [], (
        f"Unexpected Markdown files in specs/: {[str(f) for f in unexpected]}. "
        "Spec content must live in YAML files."
    )
