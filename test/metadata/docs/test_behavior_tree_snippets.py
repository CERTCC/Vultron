"""Every tree snippet on the behavior reference pages runs (#4978, #4993).

The ``docs/reference/behaviors/*.md`` pages render each behavior tree with a
``markdown-exec`` block that calls the tree's factory.  When a factory's
signature changes, the block raises at build time and the page silently
renders no tree.  This test executes each block as written on the page, so a
signature change fails here instead.
"""

import contextlib
import io
import re

import pytest

from vultron.metadata.base import repo_root

_PAGES_DIR = repo_root() / "docs" / "reference" / "behaviors"
_EXEC_BLOCK = re.compile(
    r'^```python exec="true"[^\n]*\n(?P<code>.*?)^```[ \t]*$',
    re.MULTILINE | re.DOTALL,
)


def _snippets() -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for page in sorted(_PAGES_DIR.glob("*.md")):
        text = page.read_text(encoding="utf-8")
        for index, match in enumerate(_EXEC_BLOCK.finditer(text)):
            found.append((f"{page.name}#{index}", match.group("code")))
    return found


_SNIPPETS = _snippets()


def test_the_pages_carry_tree_snippets() -> None:
    """A changed fence format must not turn the check below into a no-op."""
    pages = {label.split("#")[0] for label, _ in _SNIPPETS}
    assert {"case_handlers.md", "cs_handlers.md"} <= pages


@pytest.mark.spec("HP-01-008")
@pytest.mark.parametrize(
    "code",
    [code for _, code in _SNIPPETS],
    ids=[label for label, _ in _SNIPPETS],
)
def test_snippet_renders_a_tree(code: str) -> None:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        # The code is this repository's own docs, exactly as mkdocs runs it.
        exec(compile(code, "<snippet>", "exec"), {"__name__": "__snippet__"})  # noqa: S102
    rendered = out.getvalue().strip().strip("`").strip()
    assert rendered, "snippet printed no tree"
