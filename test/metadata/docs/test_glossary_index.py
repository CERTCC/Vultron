"""Tests for vultron.metadata.docs.glossary_index.

The index replaces the full glossary read in ``orient-agent``, so its failure
mode that matters is *silent loss*: a term, alias, or section the index drops
is one no agent sees. The corpus test pins that against the real glossary.
"""

from __future__ import annotations

import re

import pytest

from vultron.metadata.base import repo_root
from vultron.metadata.docs.glossary_index import GLOSSARY_PATH, render_index

SAMPLE = """\
# Glossary

## Roles

| Term | Definition | Aliases to avoid |
|------|-----------|-----------------|
| **Vendor** | Maintains the product | Supplier, maintainer |
| **Actor** | A federated peer | — |

## Dimensions

| Abbreviation | Meaning |
|---|---|
| **V/v** | Vendor awareness |

## Relationships

- prose only

```text
## not a heading
```
"""


@pytest.mark.spec("SR-07-016")
def test_terms_carry_aliases_to_avoid():
    out = render_index(SAMPLE)
    assert "Roles: Vendor (not: Supplier, maintainer); Actor\n" in out


@pytest.mark.spec("SR-07-016")
def test_table_without_alias_column_lists_terms():
    assert "Dimensions: V/v\n" in render_index(SAMPLE)


@pytest.mark.spec("SR-07-016")
def test_prose_section_listed_with_line_range():
    lines = render_index(SAMPLE).splitlines()
    assert lines[-1].startswith("L16-")
    assert lines[-1].endswith("Relationships (prose)")
    assert SAMPLE.splitlines()[16 - 1] == "## Relationships"


@pytest.mark.spec("SR-07-016")
def test_heading_inside_fence_is_not_a_section():
    assert "not a heading" not in render_index(SAMPLE)


@pytest.mark.spec("SR-07-016")
def test_real_glossary_loses_no_term_or_section():
    text = (repo_root() / GLOSSARY_PATH).read_text(encoding="utf-8")
    out = render_index(text)
    terms = re.findall(r"^\|\s*\*\*(.+?)\*\*", text, flags=re.MULTILINE)
    headings = re.findall(r"^## (.+?)\s*$", text, flags=re.MULTILINE)
    assert terms and headings
    assert [t for t in terms if t not in out] == []
    assert [h for h in headings if h not in out] == []
    for line in out.splitlines():
        span = re.match(r"L(\d+)-", line)
        assert span, line
        assert text.splitlines()[int(span.group(1)) - 1].startswith("## ")


@pytest.mark.spec("SR-07-016")
def test_heading_at_end_of_file_has_a_line_range():
    """An empty last section carries no body lines, and raised IndexError."""
    out = render_index("# T\n\n## A\n\ntext\n\n## B\n")
    assert out.splitlines() == ["L3-6 A (prose)", "L7-7 B (prose)"]


@pytest.mark.spec("SR-07-016")
def test_adjacent_headings_report_their_own_lines():
    """Deriving the heading line from the body put an empty section at L0."""
    assert render_index("## A\n## B\n").splitlines() == [
        "L1-1 A (prose)",
        "L2-2 B (prose)",
    ]


@pytest.mark.spec("SR-07-016")
def test_sections_sharing_a_heading_keep_their_own_terms():
    """Grouping tables by heading text gave each the other's terms."""
    text = (
        "## A\n\n| Term | Aliases to avoid |\n|---|---|\n| **x** | y |\n"
        "\n## A\n\nprose\n"
    )
    assert render_index(text).splitlines() == [
        "L1-6 A: x (not: y)",
        "L7-9 A (prose)",
    ]
