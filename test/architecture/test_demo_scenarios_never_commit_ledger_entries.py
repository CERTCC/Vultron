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

"""Architecture ratchet (PCR-08-004): no demo scenario starts a ledger commit.

The CASE_MANAGER commits a ``CaseLedgerEntry`` and broadcasts it only as part
of processing a received activity (PCR-08-003, PCR-08-013).  The
prototype-only ``POST /actors/{actor_id}/demo/sync-log-entry`` endpoint
(TRIG-09, TRIG-10-004) places a known entry for replication tests; a demo
scenario that called it would show a ledger the protocol path never built.

So no module under ``vultron/demo/scenario/`` may call or import the
endpoint's client (``ActorSession.sync_log_entry``) or its helper
(``vultron.demo.helpers.ledger_commit.trigger_log_commit``).

Spec: ``specs/participant-case-replica.yaml`` PCR-08-004.
"""

import ast
from pathlib import Path

import pytest

from test.architecture import _corpus

_SCENARIO_DIR = _corpus.REPO_ROOT / "vultron" / "demo" / "scenario"

#: The names that start a ledger commit from outside the CASE_MANAGER.
_COMMIT_STARTERS = frozenset({"trigger_log_commit", "sync_log_entry"})


def _name_of(node: ast.AST) -> str:
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


def _commit_starters(tree: ast.AST) -> list[tuple[int, str]]:
    """Return ``(line, name)`` for each call, reference or import of a starter."""
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            found.extend(
                (node.lineno, alias.name.rsplit(".", 1)[-1])
                for alias in node.names
                if alias.name.rsplit(".", 1)[-1] in _COMMIT_STARTERS
            )
        elif isinstance(node, (ast.Attribute, ast.Name)):
            name = _name_of(node)
            if name in _COMMIT_STARTERS:
                found.append((node.lineno, name))
    return found


def _scenario_trees() -> list[tuple[Path, ast.AST]]:
    return list(_corpus.all_trees(_SCENARIO_DIR))


def test_scenario_corpus_is_non_empty() -> None:
    """A zero-target gate proves nothing."""
    assert _scenario_trees(), f"no scenario files under {_SCENARIO_DIR}"


@pytest.mark.spec("PCR-08-004")
@pytest.mark.parametrize(
    ("path", "tree"), _scenario_trees(), ids=lambda v: getattr(v, "name", "")
)
def test_scenario_never_starts_a_ledger_commit(
    path: Path, tree: ast.AST
) -> None:
    offenders = _commit_starters(tree)
    assert not offenders, (
        f"{path.name} starts a ledger commit directly at "
        + ", ".join(f"line {ln} ({name})" for ln, name in offenders)
        + "; a demo scenario drives the protocol through triggers and lets"
        " the CASE_MANAGER commit (PCR-08-004)."
    )


def test_ratchet_detects_each_commit_starter() -> None:
    """The detector fires on every shape it exists to forbid."""
    source = (
        "from vultron.demo.helpers.ledger_commit import trigger_log_commit\n"
        "def phase(c):\n"
        "    trigger_log_commit(c, actor_id=a, object_id=o)\n"
        "    ActorSession(c).sync_log_entry(object_id=o)\n"
    )
    found = _commit_starters(_corpus.parse_inline(source))
    assert sorted(set(found)) == [
        (1, "trigger_log_commit"),
        (3, "trigger_log_commit"),
        (4, "sync_log_entry"),
    ]
