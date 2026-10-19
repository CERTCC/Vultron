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

Two complementary tests enforce the single-BT-execution contract for all
``execute()`` methods under ``vultron/core/use_cases/``.

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
  exemption set.  Trigger-side ``execute()`` bodies, which may run
  ``send_case_actor_activity`` beside their own tree, are governed by
  BT-15-001 and are out of scope.  The walk is shared with
  ``test_no_dl_mutations_in_execute.py`` and lives in
  ``_use_case_call_graph.py``, whose docstring lists the call shapes it does
  not follow.

A received-side use case's ``execute()`` method MUST do exactly three
things: build one BT via a tree-factory function in
``vultron/core/behaviors/``, call ``BTBridge.execute_with_setup()`` exactly
once under ``actor_id=receiving_actor_id``, and handle the result.

Spec: CLP-10-005, CLP-10-008. Decision records: ADR-0022, ADR-0135.
"""

import ast
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


def _tree_runs_over_one(
    corpus: _UseCaseCorpus, received_root: Path
) -> dict[str, int]:
    """``module.Class`` → tree runs, for each received ``execute()`` over one."""
    return {
        f"{module}.{cls}": runs
        for module, _ in corpus.modules_under(received_root)
        for cls, runs in corpus.tree_runs_per_execute(module).items()
        if runs > 1
    }


@pytest.mark.spec("CLP-10-005")
def test_no_execute_method_calls_execute_with_setup_more_than_once() -> None:
    """No received execute() reaches execute_with_setup() more than once.

    Hard invariant (CLP-10-005, ADR-0135) with no exemption set: a call
    reached through a use-case or core-services helper counts, and calls on
    alternative branches are summed.
    """
    corpus = build_use_case_corpus()
    assert any(
        corpus.tree_runs_per_execute(module)
        for module, _ in corpus.modules_under(RECEIVED_ROOT)
    ), "no received execute() found — corpus drifted?"
    violations = _tree_runs_over_one(corpus, RECEIVED_ROOT)

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
# Detector self-tests on synthetic sources
# ---------------------------------------------------------------------------

_SYNTHETIC_MODULE = "vultron.core.use_cases.received.synthetic"


def _synthetic_runs(source: str) -> dict[str, int]:
    """Tree runs per ``execute()`` in one synthetic received module."""
    path = RECEIVED_ROOT / "synthetic.py"
    corpus = _UseCaseCorpus(
        {path: _corpus.parse_inline(source)}, roots=INDEXED_ROOTS
    )
    return corpus.tree_runs_per_execute(_SYNTHETIC_MODULE)


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
            "class _Hop(Behaviour):\n"
            "    def update(self):\n"
            "        self._b.execute_with_setup(tree=nested)\n"
            "class UC:\n"
            "    def execute(self):\n"
            "        tree = Sequence(children=[_Hop()])\n"
            "        return self._b.execute_with_setup(tree=tree)\n",
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
    ],
)
def test_the_count_follows_helpers_and_sums_branches(
    source: str, runs: int
) -> None:
    assert _synthetic_runs(source) == {"UC": runs}


def test_the_count_stops_at_the_package_boundary() -> None:
    """A helper outside the indexed packages (a BT factory) is not followed."""
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


def test_the_violation_report_names_each_offender() -> None:
    """The hard invariant's report lists every execute() over one run."""
    path = RECEIVED_ROOT / "synthetic.py"
    corpus = _UseCaseCorpus(
        {
            path: _corpus.parse_inline(
                "class Ok:\n"
                "    def execute(self):\n"
                "        return self._b.execute_with_setup(tree=t)\n"
                "class Bad:\n"
                "    def execute(self):\n"
                "        if x:\n"
                "            return self._b.execute_with_setup(tree=a)\n"
                "        return self._b.execute_with_setup(tree=b)\n"
            )
        },
        roots=INDEXED_ROOTS,
    )
    assert _tree_runs_over_one(corpus, RECEIVED_ROOT) == {
        f"{_SYNTHETIC_MODULE}.Bad": 2
    }
