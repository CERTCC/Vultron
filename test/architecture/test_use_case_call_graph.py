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
"""Self-tests for the call-graph resolver behind the mutation ratchet (CLP-10-020).

The ratchet itself, its ``KNOWN_VIOLATIONS`` set, and the direct-rule
self-tests live in ``test_no_dl_mutations_in_execute.py``; the resolver in
``_use_case_call_graph.py``.  These tests lay out a synthetic use-case package
under ``tmp_path`` and run both rules over it, so each call shape the resolver
follows (or deliberately does not) is pinned by a case here.  Split out of the
ratchet module to keep it under the CS-18 module cap.
"""

import ast
from collections.abc import Mapping
from pathlib import Path

from test.architecture import _corpus
from test.architecture._use_case_call_graph import _UseCaseCorpus
from test.architecture.test_no_dl_mutations_in_execute import _violations_in

_SYNTHETIC_PKG = "vultron.core.use_cases"


def _synthetic_violations(
    tmp_path: Path, files: Mapping[str, str]
) -> frozenset[str]:
    """Run both rules over a synthetic use-case package laid out in *tmp_path*.

    *files* maps a path relative to the package root (``received/x.py``,
    ``_helpers.py``, ``../behaviors/node.py`` for an out-of-package module) to
    its source.  Returns the violation set relative to *tmp_path*.
    """
    root = tmp_path / "vultron" / "core" / "use_cases"
    trees: dict[Path, ast.AST] = {}
    for rel, source in files.items():
        path = (root / rel).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
        trees[path] = _corpus.parse_inline(source, filename=str(path))
    in_package = {
        p: t for p, t in trees.items() if p.is_relative_to(root.resolve())
    }
    corpus = _UseCaseCorpus(
        in_package, root=root.resolve(), package=_SYNTHETIC_PKG
    )
    return _violations_in(
        corpus,
        in_package,
        received_root=(root / "received").resolve(),
        repo_root=tmp_path.resolve(),
    )


_RECEIVED = "vultron/core/use_cases/received/uc.py"


def test_transitive_rule_flags_helper_one_call_deep(tmp_path: Path) -> None:
    """execute() → module helper → dl.save() is a violation of the caller."""
    found = _synthetic_violations(
        tmp_path,
        {
            "received/uc.py": (
                "from vultron.core.use_cases._helpers import store\n"
                "class UC:\n"
                "    def execute(self):\n"
                "        store(self._dl, self._obj)\n"
            ),
            "_helpers.py": ("def store(dl, obj):\n    dl.save(obj)\n"),
        },
    )
    assert found == frozenset({_RECEIVED})


def test_transitive_rule_flags_helper_two_calls_deep(tmp_path: Path) -> None:
    """execute() → helper → helper → dl.create() is still the caller's."""
    found = _synthetic_violations(
        tmp_path,
        {
            "received/uc.py": (
                "from vultron.core.use_cases.received.glue import prepare\n"
                "class UC:\n"
                "    def execute(self):\n"
                "        prepare(self._dl, self._obj)\n"
            ),
            "received/glue.py": (
                "from vultron.core.use_cases._helpers import store\n"
                "def prepare(dl, obj):\n"
                "    store(dl, obj)\n"
            ),
            "_helpers.py": ("def store(dl, obj):\n    dl.create(obj)\n"),
        },
    )
    assert found == frozenset({_RECEIVED})


def test_transitive_rule_flags_self_method_helper(tmp_path: Path) -> None:
    """execute() → self._persist() → self._dl.save() is a violation."""
    found = _synthetic_violations(
        tmp_path,
        {
            "received/uc.py": (
                "class UC:\n"
                "    def execute(self):\n"
                "        self._persist()\n"
                "    def _persist(self):\n"
                "        self._dl.save(self._obj)\n"
            ),
        },
    )
    assert found == frozenset({_RECEIVED})


def test_transitive_rule_follows_relative_imports(tmp_path: Path) -> None:
    """``from ._helpers import store`` resolves like its absolute form."""
    found = _synthetic_violations(
        tmp_path,
        {
            "received/case/uc.py": (
                "from ._helpers import store\n"
                "class UC:\n"
                "    def execute(self):\n"
                "        store(self._dl, self._obj)\n"
            ),
            "received/case/_helpers.py": (
                "def store(dl, obj):\n    dl.save(obj)\n"
            ),
        },
    )
    assert found == frozenset({"vultron/core/use_cases/received/case/uc.py"})


def test_transitive_rule_stops_at_the_package_boundary(
    tmp_path: Path,
) -> None:
    """A write in a module outside use_cases/ reached from execute() is not flagged.

    That is the tree's business: a BT node the handler runs writes through
    the bridge, which is exactly where CLP-10-005 wants the write.
    """
    found = _synthetic_violations(
        tmp_path,
        {
            "received/uc.py": (
                "from vultron.core.behaviors.node import run_tree\n"
                "class UC:\n"
                "    def execute(self):\n"
                "        run_tree(self._dl, self._obj)\n"
            ),
            "../behaviors/node.py": (
                "def run_tree(dl, obj):\n    dl.save(obj)\n"
            ),
        },
    )
    assert found == frozenset()


def test_transitive_rule_ignores_uncalled_helpers(tmp_path: Path) -> None:
    """A writing helper that execute() never calls is nobody's violation."""
    found = _synthetic_violations(
        tmp_path,
        {
            "received/uc.py": (
                "from vultron.core.use_cases._helpers import store\n"
                "class UC:\n"
                "    def execute(self):\n"
                "        self._dl.read(self._id)\n"
                "    def _later(self):\n"
                "        store(self._dl, self._obj)\n"
            ),
            "_helpers.py": ("def store(dl, obj):\n    dl.save(obj)\n"),
        },
    )
    assert found == frozenset()


def test_transitive_rule_is_received_side_only(tmp_path: Path) -> None:
    """A trigger-side execute() reaching a helper write is out of scope.

    Trigger-side bodies are governed by BT-15-001; only a *direct* write in
    their execute() is this ratchet's business.
    """
    found = _synthetic_violations(
        tmp_path,
        {
            "triggers/uc.py": (
                "from vultron.core.use_cases._helpers import store\n"
                "class UC:\n"
                "    def execute(self):\n"
                "        store(self._dl, self._obj)\n"
            ),
            "triggers/direct.py": (
                "class UC:\n"
                "    def execute(self):\n"
                "        self._dl.save(self._obj)\n"
            ),
            "_helpers.py": ("def store(dl, obj):\n    dl.save(obj)\n"),
        },
    )
    assert found == frozenset({"vultron/core/use_cases/triggers/direct.py"})


def test_transitive_rule_survives_recursive_helpers(tmp_path: Path) -> None:
    """Mutually recursive helpers terminate and are judged on their writes."""
    found = _synthetic_violations(
        tmp_path,
        {
            "received/uc.py": (
                "from vultron.core.use_cases._helpers import ping\n"
                "class UC:\n"
                "    def execute(self):\n"
                "        ping(self._dl)\n"
            ),
            "_helpers.py": (
                "def ping(dl):\n    pong(dl)\ndef pong(dl):\n    ping(dl)\n"
            ),
        },
    )
    assert found == frozenset()


def test_transitive_rule_follows_a_module_imported_by_name(
    tmp_path: Path,
) -> None:
    """``from pkg import helpers; helpers.store(...)`` binds a module, not a name."""
    found = _synthetic_violations(
        tmp_path,
        {
            "received/uc.py": (
                "from vultron.core.use_cases import _helpers\n"
                "class UC:\n"
                "    def execute(self):\n"
                "        _helpers.store(self._dl, self._obj)\n"
            ),
            "_helpers.py": ("def store(dl, obj):\n    dl.save(obj)\n"),
        },
    )
    assert found == frozenset({_RECEIVED})


def test_transitive_rule_flags_datalayer_receiver_spelling(
    tmp_path: Path,
) -> None:
    """A write through ``self._datalayer`` in a ``self._method()`` is a write."""
    found = _synthetic_violations(
        tmp_path,
        {
            "received/uc.py": (
                "class UC:\n"
                "    def execute(self):\n"
                "        self._store()\n"
                "    def _store(self):\n"
                "        self._datalayer.save(self._obj)\n"
            ),
        },
    )
    assert found == frozenset({_RECEIVED})
