#!/usr/bin/env python

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
"""Architecture invariants: one BT execution per inbox delivery (CLP-10-005).

Five tests enforce the single-BT-execution contract for the ``execute()``
methods under ``vultron/core/use_cases/``.

**Proxy ratchet** (``test_received_use_cases_do_not_dispatch_guarded_commit_directly``)
  Detects direct imports of ``create_guarded_commit_case_ledger_entry_tree``
  in use-case files — a structural proxy for the "double BT execution"
  anti-pattern. Uses a ``KNOWN_VIOLATIONS`` escape hatch to track pre-existing
  sites awaiting migration. A reviewer MUST still confirm no other
  domain-significant code remains in ``execute()`` when closing each migration;
  this test alone does not guarantee that. See ADR-0022 for the per-site
  breakdown.

**Hard invariant** (``test_no_execute_method_calls_execute_with_setup_more_than_once``)
  Counts every ``execute_with_setup()`` call that a received-side ``execute()``
  (a use case under ``vultron/core/use_cases/received/``) reaches, written in
  its own body or reached through any function or method defined under
  ``vultron/core/use_cases/`` or ``vultron/core/services/``, resolved
  transitively (ADR-0135).  Calls on alternative branches are summed, so
  Python that chooses between two trees, or runs a door check or a refusal as
  a tree of its own, counts as two.  Resolution stops at the package
  boundary: a nested ``BTBridge`` hop inside a BT node the tree runs is the
  tree's business.  Asserts **≤ 1** for every ``execute()`` with **no**
  exemption set.  The walk is shared with ``test_no_dl_mutations_in_execute.py``
  and lives in ``_use_case_call_graph.py``, whose docstring lists the call
  shapes it does and does not follow.

**Lower bound** (``test_every_received_execute_runs_a_tree``)
  The other half of "exactly one": a received ``execute()`` that reaches no
  tree run is listed in the exact ``RUNS_NO_TREE`` set (ARCH-18-001).  It also
  keeps the hard invariant from passing vacuously if the count stops seeing
  calls at all.

**Coverage** (``test_every_routed_received_use_case_is_counted``)
  Every class ``use_case_map()`` routes to appears in the count, so a use case
  whose inherited ``execute()`` the walk failed to resolve cannot drop out of
  both bounds unseen.

**Trigger side** (``test_no_trigger_execute_body_calls_execute_with_setup_twice``)
  Trigger-side ``execute()`` bodies are governed by BT-15-001, which lets a
  trigger run ``send_case_actor_activity`` beside its own tree, so helpers are
  not followed there; only the calls written in the body itself count.

A received-side use case's ``execute()`` method MUST do exactly three
things: build one BT via a tree-factory function in
``vultron/core/behaviors/``, call ``BTBridge.execute_with_setup()`` exactly
once under ``actor_id=receiving_actor_id``, and handle the result.

Spec: CLP-10-005, CLP-10-008. Decision records: ADR-0022, ADR-0135.
"""

import ast
from collections.abc import Mapping
from pathlib import Path

import pytest

from test.architecture import _corpus
from test.architecture._use_case_call_graph import (
    INDEXED_ROOTS,
    RECEIVED_ROOT,
    USE_CASES_ROOT,
    _UseCaseCorpus,
    build_use_case_corpus,
)
from vultron.semantic_registry import use_case_map

_GUARDED_COMMIT_FACTORY = "create_guarded_commit_case_ledger_entry_tree"


def _imports_guarded_commit_factory(tree: ast.AST) -> bool:
    """Return True if *tree* imports the guarded-commit factory.

    Detects both top-level and deferred (local) ``from ... import`` of
    ``create_guarded_commit_case_ledger_entry_tree``.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == _GUARDED_COMMIT_FACTORY:
                    return True
    return False


def _collect_violations() -> frozenset[str]:
    """Return repo-relative paths of use-case files importing the factory."""
    violations: set[str] = set()
    for py_file, tree in _corpus.files_mentioning(
        _GUARDED_COMMIT_FACTORY, under=USE_CASES_ROOT
    ):
        if _imports_guarded_commit_factory(tree):
            violations.add(py_file.relative_to(_corpus.REPO_ROOT).as_posix())
    return frozenset(violations)


# ---------------------------------------------------------------------------
# Known pre-existing violations awaiting migration (issue #1036, ADR-0022).
# Remove entries one by one as each use case migrates to a single
# `execute_with_setup()` call with the guarded commit composed as a child
# subtree of the use case's own tree-factory function.
# ---------------------------------------------------------------------------
KNOWN_VIOLATIONS: frozenset[str] = frozenset()


def test_received_use_cases_do_not_dispatch_guarded_commit_directly():
    """vultron/core/use_cases/ must not import the guarded-commit factory.

    Spec: CLP-10-005. Decision record: ADR-0022.

    See module docstring for the ratchet strategy.
    """
    actual = _collect_violations()
    new_violations = actual - KNOWN_VIOLATIONS
    resolved = KNOWN_VIOLATIONS - actual

    diff_lines: list[str] = []
    if new_violations:
        diff_lines.append(
            "NEW violations (use cases must not import the guarded-commit"
            " factory directly):"
        )
        diff_lines.extend(f"  + {v}" for v in sorted(new_violations))
    if resolved:
        diff_lines.append(
            "RESOLVED violations (remove these entries from KNOWN_VIOLATIONS):"
        )
        diff_lines.extend(f"  - {v}" for v in sorted(resolved))

    assert actual == KNOWN_VIOLATIONS, "\n\n" + "\n".join(diff_lines)


# ---------------------------------------------------------------------------
# Hard invariant: no received execute() reaches execute_with_setup() more than
# once, through helpers or on alternative branches.  No exemption set.
# Spec: CLP-10-005, CLP-10-008. Decision records: ADR-0022, ADR-0135.
# ---------------------------------------------------------------------------


def _received_tree_runs(
    corpus: _UseCaseCorpus, received_root: Path
) -> dict[str, int]:
    """``module.Class`` → tree runs, for every received ``execute()``."""
    return {
        f"{module}.{cls}": runs
        for module, _ in corpus.modules_under(received_root)
        for cls, runs in corpus.tree_runs_per_execute(module).items()
    }


def _over_one(runs: Mapping[str, int]) -> dict[str, int]:
    return {name: n for name, n in runs.items() if n > 1}


@pytest.mark.spec("CLP-10-005")
def test_no_execute_method_calls_execute_with_setup_more_than_once() -> None:
    """No received execute() reaches execute_with_setup() more than once.

    Hard invariant (CLP-10-005, ADR-0135) with no exemption set: a call
    reached through a use-case or core-services helper counts, and calls on
    alternative branches are summed.
    """
    violations = _over_one(
        _received_tree_runs(build_use_case_corpus(), RECEIVED_ROOT)
    )

    assert not violations, (
        "received execute() methods reaching execute_with_setup() more than"
        " once — compose the work into the one tree (CLP-10-005,"
        " ADR-0135):\n"
        + "\n".join(
            f"  {name}: {count} run(s)"
            for name, count in sorted(violations.items())
        )
    )


# ---------------------------------------------------------------------------
# Lower bound: a received execute() that runs no tree is named here.
# Exact set (ARCH-18-001): add an entry only for a use case that answers
# without a tree by design; remove one in the commit that gives it a tree.
# ---------------------------------------------------------------------------
RUNS_NO_TREE: frozenset[str] = frozenset(
    {
        # Unrecognized semantics: refused before any case is known (HP-01).
        "vultron.core.use_cases.received.unknown.UnknownUseCase",
    }
)


def test_every_routed_received_use_case_is_counted() -> None:
    """Every class ``use_case_map()`` routes to appears in the count.

    A received use case the walk failed to resolve (an inherited
    ``execute()`` behind a base spelled some way the walk does not follow)
    would drop out of both bounds silently; this pins that it cannot.
    """
    counted = _received_tree_runs(build_use_case_corpus(), RECEIVED_ROOT)
    routed = {
        f"{uc.__module__}.{uc.__qualname__}" for uc in use_case_map().values()
    }
    assert routed, "use_case_map() routed nothing"
    assert not routed - counted.keys(), sorted(routed - counted.keys())


@pytest.mark.spec("CLP-10-005")
def test_every_received_execute_runs_a_tree() -> None:
    """Every received execute() outside ``RUNS_NO_TREE`` reaches a tree run."""
    runs = _received_tree_runs(build_use_case_corpus(), RECEIVED_ROOT)
    assert len(runs) > len(RUNS_NO_TREE), "corpus drifted: no handlers found"
    no_tree = frozenset(name for name, n in runs.items() if n == 0)
    assert no_tree == RUNS_NO_TREE, (
        f"added: {sorted(no_tree - RUNS_NO_TREE)}; "
        f"resolved (remove from RUNS_NO_TREE): {sorted(RUNS_NO_TREE - no_tree)}"
    )


# ---------------------------------------------------------------------------
# Trigger side: body-only count (BT-15-001 governs what a trigger's helpers do)
# ---------------------------------------------------------------------------


def test_no_trigger_execute_body_calls_execute_with_setup_twice() -> None:
    """No non-received execute() body calls execute_with_setup() twice itself."""
    corpus = build_use_case_corpus()
    checked = 0
    violations: dict[str, int] = {}
    for module, path in corpus.modules_under(USE_CASES_ROOT):
        if path.is_relative_to(RECEIVED_ROOT):
            continue
        for cls, n in corpus.tree_runs_per_execute(
            module, transitive=False
        ).items():
            checked += 1
            if n > 1:
                violations[f"{module}.{cls}"] = n
    assert checked, "corpus drifted: no trigger execute() found"
    assert not violations, violations


# ---------------------------------------------------------------------------
# Detector self-tests on synthetic sources
# ---------------------------------------------------------------------------

_CORE = _corpus.REPO_ROOT / "vultron" / "core"
_SYNTHETIC_MODULE = "vultron.core.use_cases.received.synthetic"


def _synthetic_corpus(files: Mapping[str, str]) -> _UseCaseCorpus:
    """A corpus of *files*: paths relative to ``vultron/core/`` → source."""
    return _UseCaseCorpus(
        {_CORE / rel: _corpus.parse_inline(src) for rel, src in files.items()},
        roots=INDEXED_ROOTS,
    )


def _synthetic_runs(
    source: str, others: Mapping[str, str] | None = None
) -> dict[str, int]:
    """Tree runs per ``execute()`` in a synthetic received module.

    *others* adds modules beside it, keyed by path relative to
    ``vultron/core/``.
    """
    files = {"use_cases/received/synthetic.py": source, **(others or {})}
    return _synthetic_corpus(files).tree_runs_per_execute(_SYNTHETIC_MODULE)


@pytest.mark.parametrize(
    ("source", "runs"),
    [
        pytest.param(
            "class UC:\n"
            "    def execute(self):\n"
            "        return self._b.execute_with_setup(tree=t)\n",
            1,
            id="one-run",
        ),
        pytest.param(
            "class UC:\n"
            "    def execute(self):\n"
            "        self._b.execute_with_setup(tree=a)\n"
            "        return self._b.execute_with_setup(tree=b)\n",
            2,
            id="two-direct-runs",
        ),
        pytest.param(
            "def _door(b):\n"
            "    return b.execute_with_setup(tree=d)\n"
            "class UC:\n"
            "    def execute(self):\n"
            "        _door(self._b)\n"
            "        return self._b.execute_with_setup(tree=t)\n",
            2,
            id="helper-one-call-deep",
        ),
        pytest.param(
            "def _run(b):\n"
            "    return b.execute_with_setup(tree=d)\n"
            "def _door(b):\n"
            "    return _run(b)\n"
            "class UC:\n"
            "    def execute(self):\n"
            "        _door(self._b)\n"
            "        return self._b.execute_with_setup(tree=t)\n",
            2,
            id="helper-two-calls-deep",
        ),
        pytest.param(
            "class UC:\n"
            "    def _route(self):\n"
            "        self._b.execute_with_setup(tree=r)\n"
            "    def execute(self):\n"
            "        if late:\n"
            "            return self._route()\n"
            "        return self._b.execute_with_setup(tree=t)\n",
            2,
            id="alternative-branches",
        ),
        pytest.param(
            # The helper's own run counts once; its call to itself is a
            # cycle and is not entered again.
            "def _helper(b):\n"
            "    b.execute_with_setup(tree=d)\n"
            "    return _helper(b)\n"
            "class UC:\n"
            "    def execute(self):\n"
            "        _helper(self._b)\n"
            "        return self._b.execute_with_setup(tree=t)\n",
            2,
            id="recursive-helper",
        ),
        pytest.param(
            # The factory is followed; the node's update() is not, because a
            # BT node is an instance the tree runs, never a call execute()
            # makes.
            "class _Hop(Behaviour):\n"
            "    def update(self):\n"
            "        self._b.execute_with_setup(tree=nested)\n"
            "def _tree(b):\n"
            "    return Sequence(children=[_Hop(b)])\n"
            "class UC:\n"
            "    def execute(self):\n"
            "        return self._b.execute_with_setup(tree=_tree(self._b))\n",
            1,
            id="bt-node-call-not-counted",
        ),
        pytest.param(
            "class UC:\n"
            "    def execute(self):\n"
            "        def _retry():\n"
            "            self._b.execute_with_setup(tree=r)\n"
            "        return self._b.execute_with_setup(tree=t)\n",
            1,
            id="uncalled-nested-function",
        ),
        pytest.param(
            "class UC:\n"
            "    def execute(self):\n"
            "        def _door():\n"
            "            self._b.execute_with_setup(tree=d)\n"
            "        _door()\n"
            "        return self._b.execute_with_setup(tree=t)\n",
            2,
            id="called-nested-function",
        ),
    ],
)
def test_the_count_follows_helpers_and_sums_branches(
    source: str, runs: int
) -> None:
    assert _synthetic_runs(source) == {"UC": runs}


def test_the_count_follows_a_services_helper_through_a_reexport() -> None:
    """A ``services/`` helper reached through a package re-export counts."""
    runs = _synthetic_runs(
        "from vultron.core.services import door\n"
        "class UC:\n"
        "    def execute(self):\n"
        "        door(self._b)\n"
        "        return self._b.execute_with_setup(tree=t)\n",
        {
            "services/__init__.py": (
                "from vultron.core.services.doors import door\n"
            ),
            "services/doors.py": (
                "def door(b):\n    return b.execute_with_setup(tree=d)\n"
            ),
        },
    )
    assert runs == {"UC": 2}


def test_the_count_follows_a_relative_reexport_in_a_package_init() -> None:
    """``from .doors import door`` in ``services/__init__.py`` names
    ``services.doors``, not a sibling of ``services``."""
    runs = _synthetic_runs(
        "from vultron.core.services import door\n"
        "class UC:\n"
        "    def execute(self):\n"
        "        door(self._b)\n"
        "        return self._b.execute_with_setup(tree=t)\n",
        {
            "services/__init__.py": "from .doors import door\n",
            "services/doors.py": (
                "def door(b):\n    return b.execute_with_setup(tree=d)\n"
            ),
        },
    )
    assert runs == {"UC": 2}


_HELPERS = {
    "use_cases/received/_helpers.py": (
        "def door(b):\n    return b.execute_with_setup(tree=d)\n"
    ),
}


@pytest.mark.parametrize(
    ("imports", "call"),
    [
        pytest.param("from ._helpers import door\n", "door", id="relative"),
        pytest.param(
            "import vultron.core.use_cases.received._helpers as h\n",
            "h.door",
            id="module-import",
        ),
        pytest.param(
            "from vultron.core.use_cases.received import _helpers\n",
            "_helpers.door",
            id="submodule-from-import",
        ),
    ],
)
def test_the_count_follows_an_imported_helper(imports: str, call: str) -> None:
    runs = _synthetic_runs(
        f"{imports}"
        "class UC:\n"
        "    def execute(self):\n"
        f"        {call}(self._b)\n"
        "        return self._b.execute_with_setup(tree=t)\n",
        _HELPERS,
    )
    assert runs == {"UC": 2}


def test_the_count_follows_a_deferred_module_import() -> None:
    runs = _synthetic_runs(
        "class UC:\n"
        "    def execute(self):\n"
        "        import vultron.core.use_cases.received._helpers as h\n"
        "        h.door(self._b)\n"
        "        return self._b.execute_with_setup(tree=t)\n",
        _HELPERS,
    )
    assert runs == {"UC": 2}


_FRAME = {
    "use_cases/received/_frame.py": (
        "class Frame:\n"
        "    def _build_tree(self):\n"
        "        return t\n"
        "    def execute(self):\n"
        "        return self._b.execute_with_setup(tree=self._build_tree())\n"
    ),
}


def test_an_inherited_execute_counts_the_subclass_override() -> None:
    """``self._hook()`` dispatches on the subclass, across modules."""
    runs = _synthetic_runs(
        "from vultron.core.use_cases.received._frame import Frame\n"
        "class Plain(Frame):\n"
        "    pass\n"
        "class Sneaky(Frame):\n"
        "    def _build_tree(self):\n"
        "        self._b.execute_with_setup(tree=refusal)\n"
        "        return t\n",
        _FRAME,
    )
    assert runs == {"Plain": 1, "Sneaky": 2}


@pytest.mark.parametrize(
    ("imports", "base"),
    [
        pytest.param(
            "from ._frame import Frame\n", "Frame[int]", id="generic"
        ),
        pytest.param(
            "import vultron.core.use_cases.received._frame as f\n",
            "f.Frame",
            id="module-import",
        ),
        pytest.param(
            "from vultron.core.use_cases.received import _frame\n",
            "_frame.Frame",
            id="submodule-from-import",
        ),
        pytest.param(
            "from vultron.core.use_cases.received import Frame\n",
            "Frame",
            id="package-reexport",
        ),
    ],
)
def test_an_indexed_base_is_resolved(imports: str, base: str) -> None:
    """However the base is spelled, the subclass is counted, not dropped."""
    runs = _synthetic_runs(
        f"{imports}class UC({base}):\n    pass\n",
        {
            **_FRAME,
            "use_cases/received/__init__.py": "from ._frame import Frame\n",
        },
    )
    assert runs == {"UC": 1}


def test_super_calls_the_next_class_in_the_mro() -> None:
    runs = _synthetic_runs(
        "from ._frame import Frame\n"
        "class UC(Frame):\n"
        "    def execute(self):\n"
        "        super().execute()\n"
        "        return self._b.execute_with_setup(tree=t)\n",
        _FRAME,
    )
    assert runs == {"UC": 2}


def test_self_dispatch_follows_the_c3_order() -> None:
    """In ``UC(B, C)`` with ``B(Base)`` and ``C(Base)``, Python looks in
    ``C`` before ``Base``; a depth-first walk would look in ``Base``."""
    runs = _synthetic_runs(
        "from ._frame import Frame\n"
        "class B(Frame):\n"
        "    pass\n"
        "class C(Frame):\n"
        "    def _build_tree(self):\n"
        "        self._b.execute_with_setup(tree=refusal)\n"
        "        return t\n"
        "class UC(B, C):\n"
        "    pass\n",
        _FRAME,
    )
    assert runs == {"B": 1, "C": 2, "UC": 2}


def test_the_count_stops_at_the_package_boundary() -> None:
    """``vultron/core/behaviors/`` is never indexed, so a BT factory there
    (which may build nodes that run nested trees) is not followed."""
    behaviors = _CORE / "behaviors"
    assert not any(
        behaviors.is_relative_to(root) or root.is_relative_to(behaviors)
        for root in INDEXED_ROOTS
    )
    with pytest.raises(ValueError, match="lies under none of"):
        _synthetic_corpus({"behaviors/synthetic.py": "def f():\n    pass\n"})
    source = (
        "from vultron.core.behaviors.synthetic import build_and_run\n"
        "class UC:\n"
        "    def execute(self):\n"
        "        build_and_run(self._b)\n"
        "        return self._b.execute_with_setup(tree=t)\n"
    )
    assert _synthetic_runs(source) == {"UC": 1}


def test_a_module_without_execute_counts_nothing() -> None:
    assert _synthetic_runs("def helper():\n    pass\n") == {}


def test_a_body_only_count_ignores_helpers() -> None:
    corpus = _synthetic_corpus(
        {
            "use_cases/triggers/synthetic.py": (
                "def _send(b):\n"
                "    return b.execute_with_setup(tree=s)\n"
                "class Svc:\n"
                "    def execute(self):\n"
                "        self._b.execute_with_setup(tree=t)\n"
                "        return _send(self._b)\n"
            )
        }
    )
    module = "vultron.core.use_cases.triggers.synthetic"
    assert corpus.tree_runs_per_execute(module, transitive=False) == {"Svc": 1}
    assert corpus.tree_runs_per_execute(module) == {"Svc": 2}


def test_the_received_report_names_each_handler() -> None:
    corpus = _synthetic_corpus(
        {
            "use_cases/received/synthetic.py": (
                "class Ok:\n"
                "    def execute(self):\n"
                "        return self._b.execute_with_setup(tree=t)\n"
                "class Bad:\n"
                "    def execute(self):\n"
                "        if x:\n"
                "            return self._b.execute_with_setup(tree=a)\n"
                "        return self._b.execute_with_setup(tree=b)\n"
                "class Idle:\n"
                "    def execute(self):\n"
                "        return refused\n"
            )
        }
    )
    runs = _received_tree_runs(corpus, RECEIVED_ROOT)
    assert runs == {
        f"{_SYNTHETIC_MODULE}.Ok": 1,
        f"{_SYNTHETIC_MODULE}.Bad": 2,
        f"{_SYNTHETIC_MODULE}.Idle": 0,
    }
    assert _over_one(runs) == {f"{_SYNTHETIC_MODULE}.Bad": 2}
