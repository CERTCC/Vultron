#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can make use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University
"""The local test gate for a pushed Pull Request (``targeted-tests``).

After a Pull Request's first push, CI is the full-suite authority (ADR-0126,
ADR-0138); a fix commit is gated locally by a *targeted* set derived from the
branch diff. This command derives that set, or says the diff needs the full
suite, derives the narrower gate after a conflict merge, and answers the "did
the base touch my files?" question that decides whether the merger refreshes
the Pull Request on GitHub before merging it::

    targeted-tests                     # file list, or `full` + its triggers
    targeted-tests --pytest            # the pytest command line to run
    targeted-tests --json
    targeted-tests --overlap           # files changed on both sides
    targeted-tests --paths F [F ...]   # the gate after a conflict merge

Output contract (stable; pipeline skills parse it):

- **Selection mode** (default) exits 0 and prints either the targeted set,
  one path per line (``test/architecture/`` and ``test/metadata/`` are always
  among them), or the
  word ``full`` on the first line followed by one ``<path>: <reason>`` line
  per path that forced the full suite. ``--pytest`` prints instead a single
  runnable command line; it carries ``-m ""`` to override the
  ``-m 'not integration'`` default in ``addopts``, so integration-marked tests
  among the selected files still run (PAD-18-011). ``--json`` prints
  ``{"mode", "tests", "triggers", "unmapped", "pytest"}``.
- **Overlap mode** (``--overlap``) prints the paths the base changed since
  the merge base that this branch also changes, one per line, and exits 1
  when there are any and 0 when there are none (PAD-18-009). ``--json``
  prints ``{"base", "merge_base", "overlap"}``.
- **Paths mode** (``--paths``) prints the same selection output for the
  named files instead of the branch diff: the gate after resolving a merge
  conflict, run on the conflicted files (PAD-18-015). Each file counts as
  wholly changed, since both sides edited it, and only
  :func:`conflict_suite_trigger` paths force the full suite: CI runs the full
  suite on the push, so the test-support trigger that guards a fix commit
  is not repeated here (PAD-18-003). ``--base`` is
  not read. A conflicted non-Python file under ``test/`` (a data file) maps
  to no test and is named on stderr like any other unmapped path.
- Exit 2 is a setup error (not a repository, unknown base ref).

Changed paths no rule maps to a test (a docs page, a script outside
``vultron/``, a module nothing imports) are named on stderr, so an empty set
is never mistaken for a clean one. The command does not fetch: run
``git fetch origin`` first so ``--base`` is current.

**The branch diff is the key** (PAD-18-003): the merge base with ``--base``
against the working tree, so a fix commit landing on top of an earlier
``conftest.py`` change still escalates, and uncommitted and untracked work
counts. Overlap mode reads the same branch side on purpose: the gate runs
before a push, so work not yet committed is about to be part of the PR.

Escalation is for shared test infrastructure only (PAD-18-003, PAD-18-012): files whose
effect no import or mirror lookup can bound. A change to an integration-bearing
layer (``vultron/core/behaviors/``, ``vultron/adapters/``, …) is gated by its
importers like any other change, integration-marked ones included; the reach
beyond them is CI's, which runs the full suite on the push faster than a slot
does (ADR-0143). "Full" means the pytest suite with every marker enabled; the
docker-driven scripts under ``integration_tests/`` are not pytest tests and
stay CI's to run.

**Hub and monolith demotion do not apply.** ``spec-backstop`` demotes a symbol
imported by more than ``HUB_THRESHOLD`` test files, and a test file marking
more than ``MONOLITH_GROUP_SPAN`` spec groups, because there they would put
nearly every spec group in the blocking tier — a *precision* problem in
choosing what to read. Test selection has the opposite failure mode: a test
left out is a regression the gate cannot see, and a widely imported symbol is
exactly the change most likely to break many tests. So every importer of a
changed symbol is selected, however many there are, and spec markers play no
part. The cost of a large set is run time, which the full suite bounds.

**What "imports" means.** A test imports what its own file imports, plus
what every test-side module it imports (a ``test/support`` helper, another
test module) imports in turn, so a change reached through a helper still
selects the test, and a changed helper or test module selects its
importers. Imports *inside* ``vultron`` are not followed: a test of
``vultron.b`` is not selected for a change to ``vultron.a`` that ``b`` calls,
unless it imports ``a`` too. That reach is CI's (ADR-0126). Changed symbols
are read from both sides of the diff, so a deleted or renamed function
selects the tests that imported its old name.

PAD-18-013 — a CI failure in a test the targeted set does not
include joins the gate — is the caller's to apply: this command cannot see CI.

Requirements: specs/parallel-development.yaml PAD-18-002, PAD-18-003,
PAD-18-004, PAD-18-009, PAD-18-011 to PAD-18-015, PAD-18-019.
"""

from __future__ import annotations

import argparse
import ast
import json
import shlex
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field, replace
from pathlib import Path, PurePosixPath

from vultron.metadata.specs.backstop import (
    SOURCE_PREFIX,
    TEST_PREFIX,
    BackstopError,
    FileChange,
    GitRunner,
    TestFile,
    base_changed_paths,
    build_test_index,
    changed_nodes,
    changed_paths,
    changed_symbols,
    changes_from_paths,
    collect_git_changes,
    git_toplevel,
    imported_symbols,
    index_test_file,
    merge_base,
    mirror_tests,
    module_name,
    owner_modules,
    run_git,
    symbol_names,
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

PYTEST_BASE = (
    *GATE_CEILING,
    *("uv", "run", "pytest", "-n", "auto", "--tb=short", "-m", ""),
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


def _is_test_file(path: str) -> bool:
    return PurePosixPath(path).name.startswith("test_") and path.endswith(
        ".py"
    )


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


def _parse(source: str | None) -> ast.Module | None:
    try:
        return ast.parse(source or "")
    except SyntaxError:
        return None


def _no_history(path: str) -> str | None:
    return None


def _imports_whole_module(test: TestFile, module: str) -> bool:
    """Whether *test* reaches every name of *module*, not just some.

    ``import vultron.a.mod``, ``from vultron.a import mod`` and
    ``from vultron import a`` all reach a change to ``vultron.a.mod`` by
    attribute access, which no imported name records; a star import from
    the module or a re-exporting package binds names no import lists.
    ``vultron`` itself is not a package that counts (:func:`owner_modules`).
    """
    owners = owner_modules(module)
    for owner in owners:
        parent, _, leaf = owner.rpartition(".")
        if (parent, leaf) in test.names or owner in test.plain_imports:
            return True
    return any(name == "*" and m in owners for m, name in test.names)


def _imports_anything_from(test: TestFile, module: str, package: bool) -> bool:
    """Whether *test* imports any name from *module* or a re-exporting package.

    For a *package* (an ``__init__.py``), importing any submodule counts
    too: importing ``vultron.a.sub`` executes ``vultron/a/__init__.py``.
    """
    owners = owner_modules(module)
    return (
        _imports_whole_module(test, module)
        or any(m in owners for m, _ in test.names)
        or (package and any(m.startswith(f"{module}.") for m in test.modules))
    )


def _module_level_change(
    tree: ast.Module, lines: Iterable[int] | None
) -> bool:
    """Whether *lines* touch a top-level statement that defines no symbol.

    An import, a re-export, a registration call or an ``if TYPE_CHECKING:``
    block can break or change every importer of the module, not just the
    importers of one name. The module docstring is not such a statement.
    """
    if lines is None:
        return True
    symbols = {id(n) for n in changed_nodes(tree, None)}
    spans = [
        range(node.lineno, (node.end_lineno or node.lineno) + 1)
        for i, node in enumerate(tree.body)
        if id(node) not in symbols and not (i == 0 and _is_docstring(node))
    ]
    return any(n in span for n in lines for span in spans)


def _is_docstring(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def _top_level(tree: ast.Module) -> tuple[dict[str, str], list[str]]:
    """Each top-level symbol's AST, and the statements that define none."""
    symbols: dict[str, str] = {}
    statements: list[str] = []
    for i, node in enumerate(tree.body):
        names = symbol_names(node)
        for name in names:
            symbols[name] = ast.dump(node)
        if not names and not (i == 0 and _is_docstring(node)):
            statements.append(ast.dump(node))
    return symbols, statements


def _rewritten(old: ast.Module, new: ast.Module) -> tuple[set[str], bool]:
    """Symbols added, removed or rewritten, and whether module code changed.

    A ``-U0`` hunk names only new-side lines, so a deleted function, a
    renamed one's old name, or a removed import line leaves no changed line
    inside any symbol. Comparing the two trees catches them.
    """
    old_symbols, old_statements = _top_level(old)
    new_symbols, new_statements = _top_level(new)
    changed = {
        name
        for name in old_symbols.keys() | new_symbols.keys()
        if old_symbols.get(name) != new_symbols.get(name)
    }
    return changed, old_statements != new_statements


def importers(
    change: FileChange,
    tests: dict[str, TestFile],
    old_source: str | None = None,
) -> list[str]:
    """Test files that import a symbol *change* touched (PAD-18-002).

    A test that imports the module object is selected for any change to it.
    A change outside every top-level symbol (an import line, a re-export),
    a whole-file change (new or deleted module), or a module that no longer
    parses selects every test importing anything from it. *old_source*, the
    file at the merge base, adds the symbols the diff removed or renamed.
    """
    module = module_name(change.path)
    package = PurePosixPath(change.path).name == "__init__.py"
    tree = _parse(change.source)
    module_level = tree is None or _module_level_change(tree, change.lines)
    symbols: set[str] = set()
    old = None if old_source is None else _parse(old_source)
    if tree is not None:
        symbols = changed_symbols(tree, change.lines)
        if old is not None:
            rewritten, statements_changed = _rewritten(old, tree)
            symbols |= rewritten
            module_level = module_level or statements_changed
    if module_level:
        return sorted(
            p
            for p, t in tests.items()
            if _imports_anything_from(t, module, package)
        )
    return sorted(
        path
        for path, test in tests.items()
        if imported_symbols(test, module, symbols)
        or _imports_whole_module(test, module)
    )


def _test_side_importers(path: str, tests: dict[str, TestFile]) -> list[str]:
    """Test files that import the test-side module at *path*."""
    module = module_name(path)
    return sorted(p for p, t in tests.items() if module in t.test_imports)


def _tests_for(
    change: FileChange,
    tests: dict[str, TestFile],
    exists: Callable[[str], bool],
    old_source: Callable[[str], str | None],
) -> list[str]:
    if change.path.startswith(TEST_PREFIX):
        # A changed test file is selected explicitly: no ``vultron`` symbol
        # changed, and the mirror lookup maps only ``vultron/`` paths. So are
        # the test files importing it (a helper, or another test module).
        keep = _is_test_file(change.path) and exists(change.path)
        own = [change.path] if keep else []
        return own + _test_side_importers(change.path, tests)
    if change.path.startswith(SOURCE_PREFIX):
        return importers(
            change, tests, old_source(change.path)
        ) + mirror_tests(change.path, tests)
    return []


def _widen(
    test: TestFile, helpers: dict[str, TestFile], seen: set[str]
) -> TestFile:
    """*test* with the imports of every test-side module it reaches folded in."""
    modules, names = set(test.modules), set(test.names)
    plain, reached = set(test.plain_imports), set(test.test_imports)
    pending = [m for m in test.test_imports if m in helpers]
    while pending:
        module = pending.pop()
        if module in seen:
            continue
        seen.add(module)
        helper = helpers[module]
        modules |= helper.modules
        names |= helper.names
        plain |= helper.plain_imports
        reached |= helper.test_imports
        pending += [m for m in helper.test_imports if m in helpers]
    return replace(
        test,
        modules=frozenset(modules),
        names=frozenset(names),
        plain_imports=frozenset(plain),
        test_imports=frozenset(reached),
    )


def widen_index(
    tests: dict[str, TestFile], helpers: dict[str, TestFile]
) -> dict[str, TestFile]:
    """Fold each test's test-side imports, transitively, into its entry.

    *helpers* maps a dotted module name (``test.support.ledger``) to the
    index entry of that module, test file or not. A test that reaches
    ``vultron`` only through a helper then counts as importing what the
    helper imports, and its ``test_imports`` lists every test-side module it
    reaches, so a changed helper or test module selects it.
    """
    return {p: _widen(t, helpers, set()) for p, t in tests.items()}


def build_index(root: Path) -> dict[str, TestFile]:
    """The test index with test-side imports followed (:func:`widen_index`)."""
    tests = build_test_index(root)
    helpers = {module_name(p): t for p, t in tests.items()}
    for file in sorted((root / TEST_PREFIX).rglob("*.py")):
        rel = file.relative_to(root).as_posix()
        if rel in tests:
            continue
        indexed = index_test_file(rel, file.read_text(encoding="utf-8"))
        if indexed is not None:
            helpers[module_name(rel)] = indexed
    return widen_index(tests, helpers)


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
    no paths. It runs under :data:`GATE_CEILING`.
    """
    return list(PYTEST_BASE) + ([] if selection.full else selection.tests)


def overlap(branch: Iterable[str], base: Iterable[str]) -> list[str]:
    """Paths changed on both sides since the merge base (PAD-18-004)."""
    return sorted(set(branch) & set(base))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="targeted-tests",
        description=(
            "Derive the local test gate for the branch diff (PAD-18-002, "
            "PAD-18-003), or list the files the base and the branch both "
            "changed (PAD-18-004)."
        ),
    )
    parser.add_argument(
        "--base", default="origin/main", help="base ref (default origin/main)"
    )
    parser.add_argument(
        "--overlap",
        action="store_true",
        help=(
            "list files changed on both the base and this branch since the "
            "merge base; exit 1 when there are any"
        ),
    )
    parser.add_argument(
        "--paths",
        nargs="+",
        metavar="PATH",
        help=(
            "derive the gate for these files (the conflicted files after a "
            "base merge) instead of the branch diff; each counts as wholly "
            "changed"
        ),
    )
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="JSON output")
    output.add_argument(
        "--pytest",
        action="store_true",
        help="print the pytest command line instead of the file list",
    )
    return parser


def _render_selection(selection: Selection, args: argparse.Namespace) -> str:
    argv = pytest_argv(selection)
    if args.json:
        return json.dumps(
            {
                "mode": "full" if selection.full else "targeted",
                "tests": selection.tests,
                "triggers": [
                    {"path": t.path, "reason": t.reason}
                    for t in selection.triggers
                ],
                "unmapped": selection.unmapped,
                "pytest": argv,
            },
            indent=2,
        )
    if args.pytest:
        return shlex.join(argv)
    if selection.full:
        lines = [f"{t.path}: {t.reason}" for t in selection.triggers]
        return "\n".join(["full", *lines])
    return "\n".join(selection.tests)


def _source_at(git: GitRunner, commit: str) -> Callable[[str], str | None]:
    """A reader of a file's source at *commit*; ``None`` when it is absent."""

    def read(path: str) -> str | None:
        if not git(["ls-tree", "--name-only", commit, "--", path]).strip():
            return None
        return git(["show", f"{commit}:{path}"])

    return read


def _run_selection(args: argparse.Namespace, root: Path) -> int:
    git = run_git(root)
    # One merge base for both reads, so a fetch between them cannot split
    # the diff across two starting points.
    start = merge_base(git, args.base)
    selection = select_tests(
        changed_paths(git, start),
        collect_git_changes(git, root, start),
        build_index(root),
        lambda p: (root / p).is_file(),
        _source_at(git, start),
    )
    return _report_selection(selection, args)


def _report_selection(selection: Selection, args: argparse.Namespace) -> int:
    print(_render_selection(selection, args))
    if args.pytest and selection.full:
        for trigger in selection.triggers:
            print(
                f"targeted-tests: full suite: {trigger.path}: "
                f"{trigger.reason}",
                file=sys.stderr,
            )
    if selection.unmapped:
        print(
            "targeted-tests: no test maps to: "
            f"{', '.join(selection.unmapped)} — CI covers these",
            file=sys.stderr,
        )
    return 0


def _run_paths(args: argparse.Namespace, root: Path) -> int:
    changes = changes_from_paths(root, args.paths)
    selection = select_tests(
        [c.path for c in changes],
        [c for c in changes if c.path.endswith(".py")],
        build_index(root),
        lambda p: (root / p).is_file(),
        trigger=conflict_suite_trigger,
    )
    return _report_selection(selection, args)


def _run_overlap(args: argparse.Namespace, root: Path) -> int:
    git = run_git(root)
    start = merge_base(git, args.base)
    both = overlap(
        changed_paths(git, start), base_changed_paths(git, start, args.base)
    )
    if args.json:
        payload = {"base": args.base, "merge_base": start, "overlap": both}
        print(json.dumps(payload, indent=2))
    elif both:
        print("\n".join(both))
    if both:
        print(
            f"targeted-tests: {len(both)} file(s) changed on both "
            f"{args.base} and this branch since {start[:12]}",
            file=sys.stderr,
        )
    return 1 if both else 0


def main() -> int:
    """CLI entry point for ``targeted-tests``."""
    parser = _build_parser()
    args = parser.parse_args()
    if args.overlap and args.pytest:
        parser.error("--pytest does not apply to --overlap")
    if args.overlap and args.paths:
        parser.error("--paths does not apply to --overlap")
    try:
        root = git_toplevel(Path.cwd()).resolve()
        if args.overlap:
            return _run_overlap(args, root)
        if args.paths:
            return _run_paths(args, root)
        return _run_selection(args, root)
    except (BackstopError, OSError) as exc:
        print(f"targeted-tests: error: {exc}", file=sys.stderr)
        return 2
