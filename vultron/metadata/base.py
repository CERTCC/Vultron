"""Shared type aliases and helpers for the vultron.metadata tooling layer."""

import json
import subprocess
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import Annotated

import pathspec
import yaml
from pathspec.gitignore import GitIgnoreSpec
from pydantic import StringConstraints

from vultron.metadata.file_loading import (
    MetadataLoadError,
    load_yaml,
    loads_yaml,
)

NonEmptyStr = Annotated[str, StringConstraints(min_length=1)]
NonEmptyStrList = list[NonEmptyStr]

#: What a single-issue ``gh`` lookup can raise: ``gh`` missing
#: (:class:`OSError`), ``gh`` failing (:class:`subprocess.CalledProcessError`),
#: or output that is not JSON or lacks the expected field (:class:`KeyError`,
#: :class:`TypeError`, :class:`ValueError`). A caller that catches these
#: treats the lookup as failed, never as a pass.
GH_LOOKUP_ERRORS: tuple[type[Exception], ...] = (
    OSError,
    subprocess.CalledProcessError,
    KeyError,
    TypeError,
    ValueError,
)

#: What ``gh`` prints when the number names no issue or pull request.
_GH_NOT_FOUND = "Could not resolve to an issue or pull request"


def issue_number(ref: str) -> int:
    """The number in an ``#N`` issue reference."""
    return int(ref.removeprefix("#"))


def gh_issue_state(ref: str) -> str:
    """The GitHub state (``OPEN``/``CLOSED``) of issue *ref* (``#N``).

    Uses the ``gh`` CLI against the current repository, so it needs ``gh`` on
    ``PATH`` and a token (``GH_TOKEN`` in CI). Raises one of
    :data:`GH_LOOKUP_ERRORS` when the lookup cannot be made;
    :func:`gh_issue_missing` tells a number that names no issue apart.
    """
    result = subprocess.run(
        ["gh", "issue", "view", str(issue_number(ref)), "--json", "state"],
        capture_output=True,
        text=True,
        check=True,
    )
    return str(json.loads(result.stdout)["state"])


def gh_issue_missing(exc: Exception) -> bool:
    """Whether *exc*, raised by :func:`gh_issue_state`, says no such issue."""
    stderr = getattr(exc, "stderr", None)
    return isinstance(stderr, str) and _GH_NOT_FOUND in stderr


def gh_lookup_failure(exc: Exception) -> str:
    """*exc* as text, with ``gh``'s stderr when it is the reason.

    ``str(CalledProcessError)`` names only the exit status; the cause (a
    missing token scope, an unresolvable repository) is in its stderr.
    """
    stderr = getattr(exc, "stderr", None)
    if isinstance(stderr, str) and stderr.strip():
        return f"{exc}: {stderr.strip()}"
    return str(exc)


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


def iter_tree_texts(
    root: Path, dirs: Iterable[str], pattern: str
) -> Iterator[tuple[str, str]]:
    """Yield ``(relative_path, text)`` for each *pattern* file under *dirs*.

    *dirs* are relative to *root*; a missing one is skipped. Files are visited
    in sorted order, ``__pycache__`` is skipped, and a file that cannot be read
    as UTF-8 is skipped rather than failing the scan, so a tree-wide check
    reports on what it can read. Paths are POSIX and relative to *root*.
    """
    for directory in dirs:
        for path in sorted((root / directory).rglob(pattern)):
            if "__pycache__" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            yield path.relative_to(root).as_posix(), text


def markdown_files(top: Path, prune: Callable[[Path], bool]) -> list[Path]:
    """Return every ``*.md`` file under *top*, sorted, outside pruned directories.

    *prune* is asked of each directory below *top*; one it answers true for is
    not descended. Pruning during the walk, rather than filtering an ``rglob``
    afterwards, is the point: a repository-wide ``rglob`` reads all of
    ``.git`` and ``.venv`` before a filter discards them, which made that walk
    most of a pre-commit hook's run time. Symlinked directories are not
    followed, as ``rglob`` does not follow them.
    """
    found: list[Path] = []
    for directory, dirnames, filenames in top.walk():
        dirnames[:] = [
            name for name in dirnames if not prune(directory / name)
        ]
        found.extend(
            directory / name for name in filenames if name.endswith(".md")
        )
    return sorted(found)


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

    Raises:
        MetadataLoadError: If ``mkdocs.yml`` is missing, or is not valid YAML
            or UTF-8, naming ``mkdocs.yml`` and, for a YAML fault, its
            ``line:col`` (MS-17-001).
    """
    base = root or repo_root()
    path = base / "mkdocs.yml"
    if not path.is_file():
        raise MetadataLoadError(
            "does not exist; every docs check reads the nav from it",
            path="mkdocs.yml",
        )
    config = load_yaml(path, root=base, loader=MkDocsYamlLoader)
    return config if isinstance(config, dict) else {}


def parse_mkdocs_config(
    text: str, shown: str = "mkdocs.yml"
) -> dict[str, object]:
    """Return ``mkdocs.yml`` content *text* parsed with :class:`MkDocsYamlLoader`.

    For a config that is not a file in this checkout, such as the
    ``mkdocs.yml`` on another git ref; a fault is attributed to *shown*.

    Raises:
        MetadataLoadError: If *text* is not valid YAML, naming
            ``shown:line:col`` (MS-17-001).
    """
    # mkdocs.yml carries !!python/name tags; the text is the repository's own.
    config = loads_yaml(text, Path(shown), loader=MkDocsYamlLoader)
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
    return _docs_spec(config, ("draft_docs", "exclude_docs"))


def excluded_docs_spec(
    config: dict[str, object],
) -> pathspec.gitignore.GitIgnoreSpec:
    """Return a matcher for the ``docs/``-relative paths in ``exclude_docs``.

    Such a file is not processed by ``mkdocs build`` or ``serve``, so it is
    no page; it can still be an ``include-markdown`` fragment, which the
    plugin reads from disk.  ``draft_docs`` pages are not matched: ``serve``
    renders them.
    """
    return _docs_spec(config, ("exclude_docs",))


def _docs_spec(
    config: dict[str, object], keys: tuple[str, ...]
) -> pathspec.gitignore.GitIgnoreSpec:
    lines: list[str] = []
    for key in keys:
        value = config.get(key)
        if isinstance(value, str):
            lines.extend(value.splitlines())
    return pathspec.gitignore.GitIgnoreSpec.from_lines(lines)


def walk_nav(nav: object) -> list[str]:
    """Every string file path anywhere in a mkdocs ``nav`` tree, in order."""
    if isinstance(nav, str):
        return [nav]
    if isinstance(nav, list):
        return [path for item in nav for path in walk_nav(item)]
    if isinstance(nav, dict):
        return [path for value in nav.values() for path in walk_nav(value)]
    return []


def nav_paths(root: Path | None = None) -> frozenset[str]:
    """Return every ``docs/``-relative path the mkdocs nav references.

    The nav is walked structurally rather than matched as a substring: a path
    that appears only in a comment or an unrelated key would otherwise satisfy
    a completeness check while leaving the page genuinely un-navved, which then
    fails ``mkdocs build --strict`` instead (DEMOCI-11-007).

    Shared by every consumer that checks nav placement rather than
    regenerating the nav: scenario narrative pages must be present
    (DEMOCI-11-007), while ADR pages (MS-14-006) and other working-record pages
    (DF-11-003, ``docs-frontmatter``) must be absent. The nav's labels are
    hand-written prose, so only the *set* of files is derivable.
    """
    return frozenset(walk_nav(mkdocs_config(root).get("nav")))


def not_in_nav_spec(root: Path | None = None) -> GitIgnoreSpec:
    """Return ``mkdocs.yml``'s ``not_in_nav`` patterns as MkDocs matches them.

    MkDocs parses the value as gitignore-style lines, so this does too; a
    hand-rolled glob would disagree with the build on ``**`` and on patterns
    without a slash, which match at any depth.
    """
    value = mkdocs_config(root).get("not_in_nav")
    lines = value.splitlines() if isinstance(value, str) else []
    return GitIgnoreSpec.from_lines(lines)


def nav_exclusion_fault(
    docs_path: str, navved: frozenset[str], not_in_nav: GitIgnoreSpec
) -> str | None:
    """Say why a page that must stay out of the nav is misplaced, if it is.

    A page kept out of the reader-facing nav (DF-11-003) must be absent from
    the ``nav:`` tree *and* matched by ``not_in_nav``: absent alone makes
    ``mkdocs build --strict`` fail on an omitted-file warning, which is slow to
    find and names no rule.

    Args:
        docs_path: The page's ``docs/``-relative POSIX path.
        navved: Every path the nav references (:func:`nav_paths`).
        not_in_nav: The ``not_in_nav`` patterns (:func:`not_in_nav_spec`).

    Returns:
        The fault as a sentence fragment, or ``None`` when the page is placed
        correctly.
    """
    if docs_path in navved:
        return "is listed in the mkdocs.yml nav; remove it from the nav"
    if not not_in_nav.match_file(docs_path):
        return "is not matched by not_in_nav in mkdocs.yml; add a pattern"
    return None
