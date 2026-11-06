"""Phantom-path checks: path citations in specs that resolve to no file
(SR-04).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from vultron.metadata.base import relative_posix
from vultron.metadata.specs.registry import SpecRegistry
from vultron.metadata.specs.schema import (
    BehavioralSpec,
    LintWarningCode,
    StatementSpec,
)

#: MS-15: a backticked token in a spec statement that looks like a
#: repo-relative file path (has a directory separator and a known extension).
SPEC_PATH_RE = re.compile(
    r"`([A-Za-z0-9_./-]+/[A-Za-z0-9_.-]+\.(?:py|ya?ml|md|json|toml))`"
)

#: MS-15: a backticked token that looks like a repo-relative directory path
#: (two or more path segments with a trailing slash).  Single-segment forms
#: (e.g. ``devlogs/``) are excluded because they are frequently conceptual or
#: context-specific (CI runner refs, runtime output dirs) and carry high
#: false-positive risk.
SPEC_DIR_RE = re.compile(r"`((?:[A-Za-z0-9_.][A-Za-z0-9_.-]*/){2,})`")

#: Placeholder tokens that name a *shape* of path rather than a real one
#: (e.g. `test_XXX_invariants.py`, `plan/history/YYMM/README.md`,
#: `docs/adr/ADR-XXXX-foo.md`). Uppercase by convention, so a collision with a
#: real path segment is implausible. Bracketed forms (`{YYMM}`, `<repo>`) need
#: no entry here — :data:`SPEC_PATH_RE` cannot match them in the first place.
_PATH_PLACEHOLDER_RE = re.compile(r"XXX|YYMM|NNNN")

#: Placeholder *basenames* used in spec prose to illustrate a new file being
#: created. Matched whole-segment, not as substrings: `notes/new-spec.md` is
#: exempt but `notes/new-spec-workflow.md` is a real path and is checked.
_PLACEHOLDER_BASENAMES = frozenset({"new-topic.md", "new-spec.md"})

#: Top-level repository directories that a spec statement may reference
#: repo-relatively. Enumerated explicitly rather than read from the working
#: tree so the check behaves identically in a developer checkout (where
#: gitignored directories such as ``devlogs/`` and ``site/`` exist) and in a
#: fresh CI clone (where they do not). Add a directory here when the repo grows
#: one that specs cite.
_REPO_TOP_LEVEL_DIRS = frozenset(
    {
        ".agents",
        ".claude",
        ".devcontainer",
        ".github",
        "archived_notes",
        "docker",
        "docs",
        "integration_tests",
        "notes",
        "ontology",
        "overrides",
        "plan",
        "prompts",
        "scripts",
        "specs",
        "test",
        "vultron",
    }
)

#: Directories (relative to repo root) whose Python files legitimately cite
#: synthetic fixture IDs and are therefore excluded from the phantom-ID scan.
#: Use a trailing ``/`` to match the directory exactly and avoid silently
#: exempting a sibling directory that shares the same prefix.
_PHANTOM_ID_ALLOWLIST_DIRS = frozenset(["test/metadata/specs"])

#: Directories skipped when resolving a package-relative path suffix — build
#: artifacts and virtualenvs would otherwise satisfy a reference that no
#: tracked file does.
_IGNORED_TREE_DIRS = frozenset(
    {
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".venv",
        "__pycache__",
        "devlogs",
        "node_modules",
        "site",
        "vultron.egg-info",
    }
)


def _check_phantom_paths(registry: SpecRegistry, repo_root: Path) -> list[str]:
    """Hard error when a spec field names a file or directory that does not exist (MS-15-001).

    A normative statement or verification criterion that points at a
    non-existent path is a stale-premise landmine: an agent reads the MUST,
    cannot find the infrastructure, and either invents something inconsistent
    or silently ignores the requirement.
    DEMOMA-19-008 (issue #2004) named a ``test/ci/invariants/conftest.py`` that
    had never existed on any branch.

    Scanned fields: ``statement``, ``verification``, ``BehavioralSpec`` step
    ``action``, precondition ``description``, and postcondition ``description``.
    ``rationale`` is excluded: it states the problem a requirement prevents
    (MS-10-012), and that problem may be a path or symbol that must not
    return, so naming one that no longer exists is legitimate there.

    File references (backticked path with extension and ``/`` separator) use
    :data:`SPEC_PATH_RE`.  Directory references (two or more path segments
    with a trailing ``/``) use :data:`SPEC_DIR_RE`.  Single-segment directory
    forms (e.g. ``devlogs/``) are excluded from the directory check because
    they are frequently conceptual or CI-context references with high
    false-positive risk.

    A match whose first segment is a known top-level directory
    (:data:`_REPO_TOP_LEVEL_DIRS`) is resolved repo-relatively. Any other match
    is a package-relative illustration such as ``vocab/activities/embargo.py``
    and is resolved as a path *suffix* anywhere in the tree. Suffix resolution
    is deliberate rather than a blanket exemption: it is what catches a
    mistyped leading segment (``tests/ci/...`` for ``test/ci/...``), which is
    the most common shape of a stale reference.

    Exemptions:

    - Placeholder forms (:data:`_PATH_PLACEHOLDER_RE`,
      :data:`_PLACEHOLDER_BASENAMES`) that describe a path shape rather than a
      specific file.
    - Per-spec opt-out via ``lint_suppress: [phantom_path_ref]``, for a
      spec-first requirement that deliberately names a file yet to be created.

    Absolute paths and paths containing a ``..`` segment are rejected outright
    rather than exempted: neither is a valid repo-relative reference, and
    ``..`` would otherwise resolve outside the repository.
    """
    resolver = PathResolver(repo_root)

    errors: list[str] = []
    for spec_id, spec in registry.all_specs.items():
        if LintWarningCode.PHANTOM_PATH_REF in set(spec.lint_suppress or []):
            continue
        for field_label, text in _scanned_texts(spec):
            for match in SPEC_PATH_RE.findall(text):
                problem = resolver.problem_with(match)
                if problem is not None:
                    errors.append(
                        f"{spec_id}: {field_label} references {problem}"
                    )
            for match in SPEC_DIR_RE.findall(text):
                problem = resolver.problem_with_dir(match)
                if problem is not None:
                    errors.append(
                        f"{spec_id}: {field_label} references {problem}"
                    )

    return errors


def _scanned_texts(
    spec: BehavioralSpec | StatementSpec,
) -> list[tuple[str, str]]:
    """Return ``(field_label, text)`` pairs for all fields scanned by MS-15-001.

    ``rationale`` is deliberately excluded — the problem it names (MS-10-012)
    may legitimately be a path that no longer exists.
    """
    texts: list[tuple[str, str]] = [
        ("statement", spec.statement or ""),
        ("verification", spec.verification or ""),
    ]
    if isinstance(spec, BehavioralSpec):
        for step in spec.steps or []:
            texts.append(("behavioral step", step.action))
        for pre in spec.preconditions or []:
            texts.append(("precondition", pre.description))
        for post in spec.postconditions or []:
            texts.append(("postcondition", post.description))
    return texts


class PathResolver:
    """Classifies a single backticked path match for :func:`_check_phantom_paths`.

    Holds the lazily-built tree-path index so it is walked at most once per
    lint run rather than once per match.
    """

    def __init__(self, repo_root: Path) -> None:
        self._repo_root = repo_root
        self._tree_paths: set[str] | None = None
        self._tree_dirs: set[str] | None = None

    def problem_with(self, match: str) -> str | None:
        """Return an error fragment for ``match``, or ``None`` if it resolves."""
        segments = match.split("/")

        if match.startswith("/") or ".." in segments:
            return (
                f"'{match}', which is not a valid repo-relative path "
                f"(MS-15-001). Absolute paths and '..' segments are not "
                f"permitted."
            )

        if _PATH_PLACEHOLDER_RE.search(match):
            return None
        if segments[-1] in _PLACEHOLDER_BASENAMES:
            return None

        if segments[0] in _REPO_TOP_LEVEL_DIRS:
            if (self._repo_root / match).exists():
                return None
            hint = "Point at the real path"
        else:
            if self._resolves_as_suffix(match):
                return None
            hint = (
                "Point at the real path (this is not a repo-relative path, "
                "and no file in the tree ends with it)"
            )

        return (
            f"'{match}' which does not exist (MS-15-001). {hint}, or — if the "
            f"file is intentionally yet to be created — suppress with "
            f"lint_suppress: [phantom_path_ref]."
        )

    def problem_with_dir(self, match: str) -> str | None:
        """Return an error fragment for directory ``match``, or ``None`` if it resolves.

        ``match`` is expected to have a trailing ``/`` as captured by
        :data:`SPEC_DIR_RE`.
        """
        path = match.rstrip("/")
        segments = path.split("/")

        if ".." in segments:
            return (
                f"'{match}', which is not a valid repo-relative path "
                f"(MS-15-001). '..' segments are not permitted."
            )

        if _PATH_PLACEHOLDER_RE.search(match):
            return None

        if segments[0] in _REPO_TOP_LEVEL_DIRS:
            if (self._repo_root / path).is_dir():
                return None
            hint = "Point at the real path"
        else:
            if self._resolves_as_dir_suffix(path):
                return None
            hint = (
                "Point at the real path (this is not a repo-relative "
                "directory, and no directory in the tree ends with it)"
            )

        return (
            f"'{match}' which does not exist (MS-15-001). {hint}, or — if "
            f"the directory is intentionally yet to be created — suppress "
            f"with lint_suppress: [phantom_path_ref]."
        )

    def _resolves_as_suffix(self, match: str) -> bool:
        """True when some file in the tree has ``match`` as a path suffix."""
        if self._tree_paths is None:
            self._tree_paths = _collect_tree_paths(self._repo_root)
        suffix = "/" + match
        return match in self._tree_paths or any(
            p.endswith(suffix) for p in self._tree_paths
        )

    def _resolves_as_dir_suffix(self, path: str) -> bool:
        """True when some directory in the tree has ``path`` as a path suffix."""
        if self._tree_dirs is None:
            self._tree_dirs = _collect_tree_dirs(self._repo_root)
        suffix = "/" + path
        return path in self._tree_dirs or any(
            d.endswith(suffix) for d in self._tree_dirs
        )


def _collect_tree_paths(repo_root: Path) -> set[str]:
    """Return every file path in the repo, repo-relative, as a POSIX string.

    Specs illustrate package-relative paths (``vocab/activities/embargo.py`` for
    ``vultron/wire/as2/vocab/activities/embargo.py``), so a match that is not
    rooted at a top-level directory is resolved against this set as a path
    suffix rather than exempted outright.

    :data:`_IGNORED_TREE_DIRS` is pruned during the walk, not filtered
    afterwards — descending into ``.venv/`` would dominate the runtime and let a
    vendored file satisfy a reference that no repo file does. Built lazily and
    at most once per lint run.
    """
    paths: set[str] = set()
    for dirpath, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = [d for d in dirnames if d not in _IGNORED_TREE_DIRS]
        rel_dir = relative_posix(Path(dirpath), repo_root)
        prefix = "" if rel_dir == "." else rel_dir + "/"
        for name in filenames:
            paths.add(prefix + name)
    return paths


def _collect_tree_dirs(repo_root: Path) -> set[str]:
    """Return every directory path in the repo, repo-relative, as a POSIX string.

    Same walk rules as :func:`_collect_tree_paths` — :data:`_IGNORED_TREE_DIRS`
    is pruned during the walk so build artifacts and virtualenvs do not satisfy
    a reference that no tracked directory does.  Built lazily and at most once
    per lint run.
    """
    dirs: set[str] = set()
    for dirpath, dirnames, _ in os.walk(repo_root):
        dirnames[:] = [d for d in dirnames if d not in _IGNORED_TREE_DIRS]
        rel_dir = relative_posix(Path(dirpath), repo_root)
        if rel_dir != ".":
            dirs.add(rel_dir)
    return dirs
