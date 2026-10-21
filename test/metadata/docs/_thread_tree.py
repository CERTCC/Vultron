"""A throwaway checkout for the reading-path thread tests (DF-11-013..017).

Shared by ``test_threads.py`` and ``test_thread_box.py``: start pages built
from stage dicts, plain member pages, and the tree that holds them.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from vultron.metadata.docs.threads import LISTING_BEGIN, LISTING_END


def member(page: str, blurb: str = "what you get.", **extra: str) -> dict:
    return {"page": page, "blurb": blurb, **extra}


def stage(
    title: str, kind: str, *pages: str, **extra: object
) -> dict[str, object]:
    return {
        "title": title,
        "kind": kind,
        **extra,
        "members": [member(p) for p in pages],
    }


def start_page(title: str, stages: list[dict[str, object]]) -> str:
    """A start page declaring *stages*, with empty listing markers."""
    head = yaml.safe_dump({"thread": stages}, sort_keys=False)
    return (
        f"---\n{head}---\n\n# {title}\n\nFraming.\n\n"
        f"{LISTING_BEGIN}\n\n{LISTING_END}\n"
    )


def page(title: str) -> str:
    return f"# {title}\n"


def tree(
    tmp_path: Path, files: dict[str, str], nav: list[object] | None = None
) -> Path:
    """A checkout with ``docs/`` *files* and an empty nav.

    ``adr/`` is the working record; ``not_in_nav`` covers it so the tree is
    otherwise valid.
    """
    (tmp_path / "mkdocs.yml").write_text(
        yaml.safe_dump({"nav": nav or [], "not_in_nav": "adr/**\n"})
    )
    for rel, text in files.items():
        path = tmp_path / "docs" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp_path
