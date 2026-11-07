"""Select the targeted test set for a set of changed paths."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from vultron.metadata.git_runner import GitRunner
from vultron.metadata.planning.heavy_lock import under_heavy_lock
from vultron.metadata.planning.targeted_tests.index import (
    _is_test_file,
    _no_history,
    _tests_for,
)
from vultron.metadata.specs.backstop import (
    TEST_PREFIX,
    FileChange,
    TestFile,
    base_changed_paths,
    changed_paths,
)

#: Always part of the targeted set (PAD-18-002): the layering and ratchet
#: tests are cheap and catch the change shapes an import index cannot see.
ARCHITECTURE_TESTS = "test/architecture/"


#: Always part of the targeted set (PAD-18-002): the generated-file sync
#: checks and size ratchets, which read the tree rather than import a symbol.
METADATA_TESTS = "test/metadata/"


#: The directories every targeted set selects whole, in output order.
ALWAYS_SELECTED = (ARCHITECTURE_TESTS, METADATA_TESTS)


#: Repository-root files that configure every test run (PAD-18-012).
SHARED_CONFIG_FILES = ("pyproject.toml", "uv.lock")


#: The package root runs on every ``vultron`` import, and no import of a
#: name from it can say which tests depend on what it does.
PACKAGE_ROOT = "vultron/__init__.py"


#: Files under ``test/`` that no test run reads.
_INERT_TEST_SUFFIXES = (".md",)


#: The wall-clock ceiling on every local gate run, and its exit status 124.
#: ``-k 30`` follows the ``SIGTERM`` with a ``SIGKILL`` should pytest not exit.
#: A run that hits it hung where no per-test timeout reaches, such as a C
#: call holding the GIL or a stuck xdist controller (#4809).
#: Stock macOS has no ``timeout``; there the command exits 127.
GATE_CEILING = ("timeout", "-k", "30", "1800")


#: The gate command: in one of the host's heavy-check slots, then under
#: :data:`GATE_CEILING`, so time spent waiting for a slot is not charged
#: to the run (#5947).
PYTEST_BASE = under_heavy_lock(
    (
        *GATE_CEILING,
        *("uv", "run", "pytest", "-n", "auto", "--tb=short", "-m", ""),
    )
)


@dataclass(frozen=True)
class UnboundedPath:
    """A changed path no targeted set bounds, and why (PAD-18-012)."""

    path: str
    reason: str


@dataclass
class Selection:
    """The local gate for one branch diff.

    Every selection is a file list: no diff sends the gate to the full unit
    and integration suites, whatever paths it touches (PAD-18-003).
    """

    tests: list[str] = field(default_factory=list)
    #: Changed paths whose reach the selection cannot bound (PAD-18-012).
    #: Reported, never acted on: CI's required full run covers them.
    unbounded: list[UnboundedPath] = field(default_factory=list)
    #: Changed paths that selected no test at all.
    unmapped: list[str] = field(default_factory=list)


def shared_infrastructure(path: str) -> UnboundedPath | None:
    """Why no targeted set bounds *path* (PAD-18-012), or ``None``.

    Shared test infrastructure is ``conftest.py``,
    :data:`SHARED_CONFIG_FILES`, :data:`PACKAGE_ROOT`, and the test-support
    files — fixtures, factories, helpers, data files: anything under
    ``test/`` that is not itself a ``test_*.py`` file. Tests reach these in
    ways no import records: a fixture by parameter name, a data file by
    path, a configuration key by every run reading it.

    Anything under :data:`ALWAYS_SELECTED` is the exception, whatever kind of
    file it is, ``conftest.py`` included: those directories are always
    selected whole, so the set does bound them, and a test elsewhere that
    imports one of their helpers is selected through the index
    (:func:`build_index`). The exclusion comes first for that reason — an arm
    that fired ahead of it would report a path the gate already runs.

    The answer is a report, not a verdict. The gate still runs the set it
    can select plus :data:`ALWAYS_SELECTED`, and CI's required full run
    covers the reach beyond it (PAD-18-003, PAD-18-012).
    """
    if path.startswith(ALWAYS_SELECTED):
        return None
    if PurePosixPath(path).name == "conftest.py":
        return UnboundedPath(path, "conftest.py (shared test fixtures)")
    if path in SHARED_CONFIG_FILES:
        return UnboundedPath(path, "test configuration or dependencies")
    if path == PACKAGE_ROOT:
        return UnboundedPath(path, "package root (runs on every import)")
    if (
        path.startswith(TEST_PREFIX)
        and not _is_test_file(path)
        and not path.endswith(_INERT_TEST_SUFFIXES)
    ):
        return UnboundedPath(
            path, "test support file (fixture, factory, helper, or data)"
        )
    return None


def select_tests(
    paths: Iterable[str],
    changes: Iterable[FileChange],
    tests: dict[str, TestFile],
    exists: Callable[[str], bool],
    old_source: Callable[[str], str | None] = _no_history,
) -> Selection:
    """The targeted set for a branch diff.

    The set is always the always-selected directories plus whatever the
    import index maps: no path escalates it to the full suite
    (PAD-18-003). A path whose reach the index cannot bound is reported in
    :attr:`Selection.unbounded` instead, and CI covers it (PAD-18-012).

    Args:
        paths: Every path the branch diff changes, of any type.
        changes: The changed ``.py`` files under ``vultron/`` and ``test/``,
            with their changed lines (deleted files carry their old source).
        tests: The test index (:func:`build_index`).
        exists: Whether a repository-relative path exists in the work tree.
        old_source: A changed file's source at the merge base, or ``None``
            when it did not exist there.
    """
    selection = Selection()
    paths = sorted(set(paths))
    selection.unbounded = [
        found
        for found in (shared_infrastructure(p) for p in paths)
        if found is not None
    ]
    reported = {u.path for u in selection.unbounded}
    selected: set[str] = set()
    mapped: set[str] = set()
    for change in changes:
        found_tests = _tests_for(change, tests, exists, old_source)
        if found_tests or change.path.startswith(TEST_PREFIX):
            mapped.add(change.path)
        selected.update(found_tests)
    selection.tests = [
        *ALWAYS_SELECTED,
        *sorted(t for t in selected if not t.startswith(ALWAYS_SELECTED)),
    ]
    selection.unmapped = [
        p
        for p in paths
        if p not in mapped
        and p not in reported
        and not (
            p.startswith(TEST_PREFIX) and p.endswith(_INERT_TEST_SUFFIXES)
        )
        and not p.startswith(ALWAYS_SELECTED)
    ]
    return selection


def pytest_argv(selection: Selection) -> list[str]:
    """The pytest command for *selection*, integration marker enabled.

    ``-m ""`` replaces the ``-m 'not integration'`` in ``addopts``: pytest
    keeps the last ``-m``, so marker-bearing tests among the selected files
    are not deselected (PAD-18-011). It runs in a heavy-check slot, then
    under :data:`GATE_CEILING`.

    Raises:
        ValueError: when *selection* names no test. A path-free command runs
            the whole suite, which no local gate does (PAD-18-003), so an
            empty selection has no command rather than a dangerous one.
            :func:`select_tests` always prepends :data:`ALWAYS_SELECTED`, so
            this is unreachable through the CLI; it is enforced here because
            the invariant belongs to the function that would break it.
    """
    if not selection.tests:
        raise ValueError(
            "a selection with no test has no gate command: a path-free "
            "pytest call runs the whole suite, which no local gate does "
            "(PAD-18-003)"
        )
    return list(PYTEST_BASE) + selection.tests


def overlap(branch: Iterable[str], base: Iterable[str]) -> list[str]:
    """Paths changed on both sides since the merge base (PAD-18-004)."""
    return sorted(set(branch) & set(base))


def branch_overlap(git: GitRunner, start: str, base: str) -> list[str]:
    """Paths the branch and *base* both changed since *start*, their merge base.

    ``targeted-tests --overlap`` reports these paths and nothing else
    computes them. Two callers read that report, and neither runs a test on
    the overlap: ``sync-decision.sh``, whose ``no-merge`` verdict with
    ``merge_reason=deferred`` tells ``pr-execute`` the overlap is no reason
    to merge the base in (PAD-18-004), and the merger, which refreshes the
    Pull Request on GitHub instead (PAD-18-019).
    """
    return overlap(
        changed_paths(git, start), base_changed_paths(git, start, base)
    )
