"""Select the targeted test set for a set of changed paths, or the full suite."""

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


#: Repository-root files that configure every test run (PAD-18-003).
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
class FullSuiteTrigger:
    """A changed path that sends the gate to the full suite, and why."""

    path: str
    reason: str


@dataclass
class Selection:
    """The local gate for one branch diff."""

    tests: list[str] = field(default_factory=list)
    triggers: list[FullSuiteTrigger] = field(default_factory=list)
    #: Changed paths that neither escalated nor selected any test.
    unmapped: list[str] = field(default_factory=list)

    @property
    def full(self) -> bool:
        """Whether the diff needs the full unit and integration suites."""
        return bool(self.triggers)


def conflict_suite_trigger(path: str) -> FullSuiteTrigger | None:
    """Why a conflicted *path* needs the full suite, or ``None``.

    The subset of :func:`full_suite_trigger` that applies after a conflict
    merge (``--paths``): files that configure every test run, whose effect no
    import or mirror lookup can bound. A conflict anywhere else is gated by
    its importers and mirror tests; CI runs the rest on the push
    (PAD-18-003, PAD-18-015).
    """
    name = PurePosixPath(path).name
    if name == "conftest.py":
        return FullSuiteTrigger(path, "conftest.py (shared test fixtures)")
    if path in SHARED_CONFIG_FILES:
        return FullSuiteTrigger(path, "test configuration or dependencies")
    if path == PACKAGE_ROOT:
        return FullSuiteTrigger(path, "package root (runs on every import)")
    return None


def full_suite_trigger(path: str) -> FullSuiteTrigger | None:
    """Why *path* needs the full suite (PAD-18-003), or ``None``.

    Test-support files — fixtures, factories, helpers, data files: anything
    under ``test/`` that is not itself a ``test_*.py`` file — escalate because
    tests reach them in ways no import records: a fixture by parameter name,
    a data file by path. Those under :data:`ALWAYS_SELECTED` are the
    exception: those directories are always selected whole, and a test
    elsewhere that imports one of their helpers is selected through the
    index (:func:`build_index`).
    """
    shared = conflict_suite_trigger(path)
    if shared is not None:
        return shared
    if (
        path.startswith(TEST_PREFIX)
        and not path.startswith(ALWAYS_SELECTED)
        and not _is_test_file(path)
        and not path.endswith(_INERT_TEST_SUFFIXES)
    ):
        return FullSuiteTrigger(
            path, "test support file (fixture, factory, helper, or data)"
        )
    return None


def select_tests(
    paths: Iterable[str],
    changes: Iterable[FileChange],
    tests: dict[str, TestFile],
    exists: Callable[[str], bool],
    old_source: Callable[[str], str | None] = _no_history,
    trigger: Callable[[str], FullSuiteTrigger | None] = full_suite_trigger,
) -> Selection:
    """The targeted set for a branch diff, or the triggers that forbid one.

    Args:
        paths: Every path the branch diff changes, of any type.
        changes: The changed ``.py`` files under ``vultron/`` and ``test/``,
            with their changed lines (deleted files carry their old source).
        tests: The test index (:func:`build_index`).
        exists: Whether a repository-relative path exists in the work tree.
        old_source: A changed file's source at the merge base, or ``None``
            when it did not exist there.
        trigger: The escalation rule: :func:`full_suite_trigger` for a
            branch diff, :func:`conflict_suite_trigger` for ``--paths``.
    """
    selection = Selection()
    paths = sorted(set(paths))
    for path in paths:
        escalation = trigger(path)
        if escalation is not None:
            selection.triggers.append(escalation)
    if selection.full:
        return selection
    selected: set[str] = set()
    mapped: set[str] = set()
    for change in changes:
        found = _tests_for(change, tests, exists, old_source)
        if found or change.path.startswith(TEST_PREFIX):
            mapped.add(change.path)
        selected.update(found)
    selection.tests = [
        *ALWAYS_SELECTED,
        *sorted(t for t in selected if not t.startswith(ALWAYS_SELECTED)),
    ]
    selection.unmapped = [
        p
        for p in paths
        if p not in mapped
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
    are not deselected (PAD-18-011). The full suite is the same command with
    no paths. It runs in a heavy-check slot, then under :data:`GATE_CEILING`.
    """
    return list(PYTEST_BASE) + ([] if selection.full else selection.tests)


def overlap(branch: Iterable[str], base: Iterable[str]) -> list[str]:
    """Paths changed on both sides since the merge base (PAD-18-004)."""
    return sorted(set(branch) & set(base))


def branch_overlap(git: GitRunner, start: str, base: str) -> list[str]:
    """Paths the branch and *base* both changed since *start*, their merge base.

    ``targeted-tests --overlap`` reports these paths, and nothing else
    computes them: the overlap decides whether the merger refreshes the
    Pull Request on GitHub before merging it (PAD-18-019). It runs no test.
    """
    return overlap(
        changed_paths(git, start), base_changed_paths(git, start, base)
    )
