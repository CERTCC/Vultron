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
"""Architecture ratchet: no DataLayer mutations reachable from execute().

Each ``execute()`` method in ``vultron/core/use_cases/`` MUST delegate all
DataLayer mutations (``save``, ``create``, ``update``, ``delete``) to a BT
leaf node via ``BTBridge.execute_with_setup()``.  A call like
``self._dl.save(...)`` inside ``execute()`` bypasses the BT audit trail,
skips the hash-chained ledger-commit path, and constitutes protocol-significant
behavior outside the tree — the exact anti-pattern BT-06-001 and BT-15-001
prohibit.

Two rules, one ratchet:

1. **Direct writes, every use case.**  A mutation call whose receiver is
   ``self._dl``, ``self.dl``, or a local ``dl`` inside the body of any
   ``execute()`` under ``vultron/core/use_cases/`` is a violation of that
   file.  Nested functions and lambdas defined inside ``execute()`` are their
   own scope and are not counted here.

2. **Writes reached through helpers, received side (CLP-10-020).**  For an
   ``execute()`` under ``vultron/core/use_cases/received/``, a mutation that
   the body reaches through any function or method defined under
   ``vultron/core/use_cases/`` — a module-level helper, a ``self._method()``,
   a helper imported from a sibling module, and so on transitively — is a
   violation of the file that holds the ``execute()``.  Resolution stops at
   the use-case package boundary: a write inside a BT node the tree runs is
   the tree's business, not a violation.  A helper is named as a violation of
   its *caller*, never of the module that defines it, because the rule is
   about what ``execute()`` does (CLP-10-005), not where code lives.
   Trigger-side ``execute()`` and ``_prepare()`` bodies are governed by
   BT-15-001 and are not resolved transitively here.

Resolution lives in ``_use_case_call_graph.py``; that module's docstring
lists the call shapes it does not follow (an inline-built instance's method, an
inherited method from another module, a lambda or nested function handed to a
helper — the last for the same reason the direct rule skips them — and a
receiver not spelled ``dl``/``datalayer``).  Its self-tests for the transitive
rule are in ``test_use_case_call_graph.py``; the direct rule's are below.

The helper rule exists because eleven received ``execute()`` bodies in nine
files once stored the received object through one shared ``_idempotent_create``
helper and a few bespoke ones, invisible to a body-only scan (ISSUE-3339,
ADR-0111).  Intake — the first stage of every received tree — now archives the
activity (CLP-10-017), and the core record goes to an effect node, so every
entry below is a migration the issue named on it owes.

A ``KNOWN_VIOLATIONS`` ratchet tracks pre-existing sites awaiting migration.
The set is **exact** (ARCH-18-001): new violations fail the test immediately,
and resolved violations (entries in ``KNOWN_VIOLATIONS`` that no longer appear
in the scan) also fail — prompting the entry to be removed (ARCH-18-002).

Spec: CLP-10-005, CLP-10-020 (``specs/case-ledger-processing.yaml``); HP-08-002
(``specs/handler-protocol.yaml``) — a handler's ``execute()`` MUST NOT mutate the
DataLayer directly; the write runs inside a BT leaf node reached through
``BTBridge``.
BT specs: BT-06-001, BT-15-001 (``specs/behavior-tree-integration.yaml``).
Corpus: TB-13-001, TB-13-003 (``specs/testability.yaml``).
"""

import ast
from collections.abc import Mapping
from pathlib import Path

from test.architecture import _corpus
from test.architecture._use_case_call_graph import (
    _UseCaseCorpus,
    _has_dl_mutation_in_execute,
    _has_dl_mutation_in_execute_tree,
)

_USE_CASES_ROOT = _corpus.REPO_ROOT / "vultron" / "core" / "use_cases"
_RECEIVED_ROOT = _USE_CASES_ROOT / "received"
_USE_CASES_PKG = "vultron.core.use_cases"


def _build_corpus() -> _UseCaseCorpus:
    """Index every module of the real use-case package.

    ``all_trees`` rather than a fragment prefilter (TB-13-002's escape
    hatch): a helper chain can pass through a module that never spells
    ``dl.`` itself, and dropping that module would break the chain.
    """
    return _UseCaseCorpus(
        dict(_corpus.all_trees(under=_USE_CASES_ROOT)),
        root=_USE_CASES_ROOT,
        package=_USE_CASES_PKG,
    )


def _violations_in(
    corpus: _UseCaseCorpus,
    direct_trees: Mapping[Path, ast.AST],
    *,
    received_root: Path,
    repo_root: Path,
) -> frozenset[str]:
    """Repo-relative paths whose ``execute()`` writes, directly or via helpers."""
    violations: set[str] = set()
    for path, tree in direct_trees.items():
        if _has_dl_mutation_in_execute_tree(tree):
            violations.add(path.relative_to(repo_root).as_posix())
    for module, path in corpus.modules_under(received_root):
        if corpus.execute_reaches_mutation(module):
            violations.add(path.relative_to(repo_root).as_posix())
    return frozenset(violations)


def _collect_violations() -> frozenset[str]:
    """Return repo-relative paths of use-case files with DL mutations in execute()."""
    return _violations_in(
        _build_corpus(),
        dict(_corpus.files_mentioning("dl.", under=_USE_CASES_ROOT)),
        received_root=_RECEIVED_ROOT,
        repo_root=_corpus.REPO_ROOT,
    )


# ---------------------------------------------------------------------------
# Known pre-existing violations awaiting migration to BT leaf nodes.
#
# Each file's execute() reaches self._dl.save/create/update/delete — directly
# or through a use-case helper — bypassing the BT audit trail and the
# hash-chained ledger-commit path (BT-06-001, BT-15-001, CLP-10-005,
# CLP-10-020).  Most store the received object before the tree runs; intake
# now archives the activity (CLP-10-017), and the core record each handler
# wrote from the inlined object becomes an effect node of its tree (ADR-0111
# as amended).
#
# Remove an entry in the same commit that migrates it (ARCH-18-002).  The
# issue named beside each entry owns its removal.
# ---------------------------------------------------------------------------
KNOWN_VIOLATIONS: frozenset[str] = frozenset(
    {
        # #3871 — participant status, case participant, participant role
        "vultron/core/use_cases/received/status.py",
        "vultron/core/use_cases/received/case_participant.py",
        "vultron/core/use_cases/received/actor/accept_reject_case_participant_role.py",
        # #3872 — report, embargo, invite, ownership
        "vultron/core/use_cases/received/report.py",
        "vultron/core/use_cases/received/embargo.py",
        "vultron/core/use_cases/received/actor/invite.py",
        "vultron/core/use_cases/received/actor/ownership.py",
        # #3873 — case lifecycle (add report) and note (remove note): direct
        # writes with no tree at all
        "vultron/core/use_cases/received/case/lifecycle.py",
        "vultron/core/use_cases/received/note.py",
        # #3874 — case create and engage/defer: embedded participants and
        # the case replica
        "vultron/core/use_cases/received/case/create.py",
        "vultron/core/use_cases/received/case/engage_defer.py",
    }
)


def test_no_dl_mutations_in_execute():
    """execute() methods in use_cases/ must not reach DataLayer mutations.

    Spec: CLP-10-005, CLP-10-020, HP-08-002. BT specs: BT-06-001, BT-15-001.

    See module docstring for the ratchet strategy.
    """
    actual = _collect_violations()
    new_violations = actual - KNOWN_VIOLATIONS
    resolved = KNOWN_VIOLATIONS - actual

    diff_lines: list[str] = []
    if new_violations:
        diff_lines.append(
            "NEW violations (execute() must not reach self._dl.save/create/"
            "update/delete, directly or through a use-case helper — delegate"
            " to a BT leaf node instead, CLP-10-005 / CLP-10-020 /"
            " BT-15-001):"
        )
        diff_lines.extend(f"  + {v}" for v in sorted(new_violations))
    if resolved:
        diff_lines.append(
            "RESOLVED violations (remove these entries from KNOWN_VIOLATIONS"
            " in this commit — ARCH-18-002):"
        )
        diff_lines.extend(f"  - {v}" for v in sorted(resolved))

    assert actual == KNOWN_VIOLATIONS, "\n\n" + "\n".join(diff_lines)


# ---------------------------------------------------------------------------
# Synthetic detector-validation tests — direct rule
# ---------------------------------------------------------------------------


def test_detector_catches_self_dl_save_in_execute(tmp_path: Path) -> None:
    """Confirm the scanner flags self._dl.save() directly in execute()."""
    violation_file = tmp_path / "synthetic_violation.py"
    violation_file.write_text(
        "class FakeUseCase:\n"
        "    def execute(self):\n"
        "        self._dl.save(self._obj)\n",
        encoding="utf-8",
    )
    assert _has_dl_mutation_in_execute(
        violation_file
    ), "Detector did not flag self._dl.save() in execute()"


def test_detector_catches_all_mutation_methods(tmp_path: Path) -> None:
    """Confirm the scanner flags all four mutation methods."""
    for method in ("save", "create", "update", "delete"):
        f = tmp_path / f"synthetic_{method}.py"
        f.write_text(
            "class FakeUseCase:\n"
            "    def execute(self):\n"
            f"        self._dl.{method}(self._obj)\n",
            encoding="utf-8",
        )
        assert _has_dl_mutation_in_execute(
            f
        ), f"Detector did not flag self._dl.{method}() in execute()"


def test_detector_does_not_flag_reads(tmp_path: Path) -> None:
    """Read-only DataLayer calls (read, list, etc.) must not be flagged."""
    clean_file = tmp_path / "synthetic_read_only.py"
    clean_file.write_text(
        "class FakeUseCase:\n"
        "    def execute(self):\n"
        "        obj = self._dl.read(self._id)\n"
        "        items = self._dl.list()\n",
        encoding="utf-8",
    )
    assert not _has_dl_mutation_in_execute(
        clean_file
    ), "Detector falsely flagged read-only DataLayer calls"


def test_direct_rule_does_not_flag_mutations_in_uncalled_helper_methods(
    tmp_path: Path,
) -> None:
    """The direct rule sees only execute()'s own body.

    A helper method that writes is not a direct violation; whether execute()
    *reaches* it is the transitive rule's question (see below).
    """
    clean_file = tmp_path / "synthetic_helper_mutation.py"
    clean_file.write_text(
        "class FakeUseCase:\n"
        "    def execute(self):\n"
        "        self._persist()\n"
        "    def _persist(self):\n"
        "        self._dl.save(self._obj)\n",
        encoding="utf-8",
    )
    assert not _has_dl_mutation_in_execute(
        clean_file
    ), "Direct rule flagged a mutation inside a non-execute helper method"


def test_detector_does_not_flag_mutations_in_inner_function(
    tmp_path: Path,
) -> None:
    """Mutations inside a nested function defined in execute() must not be flagged.

    Only direct (own-scope) calls inside execute() are violations; calls
    inside inner helpers are excluded by _walk_own_scope.
    """
    clean_file = tmp_path / "synthetic_inner_fn.py"
    clean_file.write_text(
        "class FakeUseCase:\n"
        "    def execute(self):\n"
        "        def _inner():\n"
        "            self._dl.save(self._obj)\n"
        "        _inner()\n",
        encoding="utf-8",
    )
    assert not _has_dl_mutation_in_execute(
        clean_file
    ), "Detector produced false positive for mutation inside nested function"


def test_detector_does_not_flag_mutations_in_lambda(tmp_path: Path) -> None:
    """Mutations inside a lambda defined in execute() must not be flagged.

    ``ast.Lambda`` is a nested scope just like ``FunctionDef``; the mutation
    belongs to the lambda's body, not to ``execute()`` directly.
    """
    clean_file = tmp_path / "synthetic_lambda.py"
    clean_file.write_text(
        "class FakeUseCase:\n"
        "    def execute(self):\n"
        "        fn = lambda: self._dl.save(self._obj)\n"
        "        fn()\n",
        encoding="utf-8",
    )
    assert not _has_dl_mutation_in_execute(
        clean_file
    ), "Detector produced false positive for mutation inside lambda"


def test_detector_catches_local_dl_variable(tmp_path: Path) -> None:
    """Confirm the scanner flags dl.save() via a local variable named dl."""
    violation_file = tmp_path / "synthetic_local_dl.py"
    violation_file.write_text(
        "class FakeUseCase:\n"
        "    def execute(self):\n"
        "        dl = self._dl\n"
        "        dl.save(self._obj)\n",
        encoding="utf-8",
    )
    assert _has_dl_mutation_in_execute(
        violation_file
    ), "Detector did not flag dl.save() via local dl variable"
