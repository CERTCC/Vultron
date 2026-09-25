"""Shared type aliases and helpers for the vultron.metadata tooling layer."""

from pathlib import Path
from typing import Annotated

import pathspec
import yaml
from pydantic import StringConstraints

NonEmptyStr = Annotated[str, StringConstraints(min_length=1)]
NonEmptyStrList = list[NonEmptyStr]


def repo_root(start: Path | None = None) -> Path:
    """Return the repository root by searching upward for ``pyproject.toml``.

    Every loader and generator in this package needs the repo root and none of
    them can assume the caller's working directory (NF-03-005), so this lives
    here rather than being re-derived per module.

    Args:
        start: Directory to search upward from. Defaults to the current working
            directory. Resolved first, so a relative ``start`` still yields
            absolute parents to walk.

    Raises:
        FileNotFoundError: If ``pyproject.toml`` is in no parent directory,
            which means the tool was invoked outside a Vultron checkout.
    """
    origin = (start or Path.cwd()).resolve()
    for parent in [origin, *origin.parents]:
        if (parent / "pyproject.toml").exists():
            return parent
    raise FileNotFoundError(
        f"Could not locate repository root (pyproject.toml) starting from "
        f"{origin}"
    )


class MkDocsYamlLoader(yaml.SafeLoader):
    """SafeLoader that tolerates the custom YAML tags in ``mkdocs.yml``.

    ``mkdocs.yml`` carries ``!ENV`` and ``!!python/name:`` tags that a plain
    ``yaml.safe_load`` refuses to construct.  Callers here only ever want plain
    config values (the ``nav:`` tree, ``use_directory_urls``), so permissive
    constructors discard the tag and keep the underlying node rather than
    executing anything.
    """


MkDocsYamlLoader.add_multi_constructor("!", lambda _l, _s, _n: None)
MkDocsYamlLoader.add_multi_constructor(
    "tag:yaml.org,2002:python/name:", lambda _l, _s, _n: None
)


def mkdocs_config(root: Path | None = None) -> dict[str, object]:
    """Return ``mkdocs.yml`` parsed with :class:`MkDocsYamlLoader`.

    Args:
        root: Repository root. Defaults to the enclosing checkout.
    """
    base = root or repo_root()
    return parse_mkdocs_config(
        (base / "mkdocs.yml").read_text(encoding="utf-8")
    )


def parse_mkdocs_config(text: str) -> dict[str, object]:
    """Return ``mkdocs.yml`` content *text* parsed with :class:`MkDocsYamlLoader`.

    For a config that is not a file in this checkout, such as the
    ``mkdocs.yml`` on another git ref.
    """
    config = yaml.load(text, Loader=MkDocsYamlLoader)  # noqa: S506
    return config if isinstance(config, dict) else {}


def unbuilt_docs_spec(
    config: dict[str, object],
) -> pathspec.gitignore.GitIgnoreSpec:
    """Return a matcher for the ``docs/``-relative paths *config* does not build.

    Reads ``draft_docs`` and ``exclude_docs``, with the same ``GitIgnoreSpec``
    matcher MkDocs applies in ``mkdocs.structure.files.set_exclusions``, so the
    semantics cannot drift from the build's. Pages in ``not_in_nav`` are **not**
    matched: they are built and reachable by URL, just absent from the nav.
    """
    lines: list[str] = []
    for key in ("draft_docs", "exclude_docs"):
        value = config.get(key)
        if isinstance(value, str):
            lines.extend(value.splitlines())
    return pathspec.gitignore.GitIgnoreSpec.from_lines(lines)


def _walk_nav(nav: object) -> list[str]:
    """Collect every string file path anywhere in a mkdocs ``nav`` tree."""
    if isinstance(nav, str):
        return [nav]
    if isinstance(nav, list):
        return [path for item in nav for path in _walk_nav(item)]
    if isinstance(nav, dict):
        return [path for value in nav.values() for path in _walk_nav(value)]
    return []


def nav_paths(root: Path | None = None) -> frozenset[str]:
    """Return every ``docs/``-relative path the mkdocs nav references.

    The nav is walked structurally rather than matched as a substring: a path
    that appears only in a comment or an unrelated key would otherwise satisfy
    a completeness check while leaving the page genuinely un-navved, which then
    fails ``mkdocs build --strict`` instead (MS-14-006).

    Shared by every consumer that checks nav completeness rather than
    regenerating the nav — ADR pages (MS-14-006) and scenario narrative pages
    (DEMOCI-11-007) — because the nav's labels are hand-written prose in both
    cases and only the *set* of files is derivable.
    """
    return frozenset(_walk_nav(mkdocs_config(root).get("nav")))
