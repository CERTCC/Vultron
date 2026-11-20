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
"""Ratchet: no ledger ``Add`` carries a ``result`` (SYNC-02-009, ADR-0204).

The ``Add(CaseLedgerEntry)`` that commits an act is that act's positive
acknowledgement and names it in ``inReplyTo``.  It lists nothing in
``result``: an act a commit causes names its cause in its own ``inReplyTo``,
so no ``Add`` needs the ids of follow-on acts before they exist.

Three checks hold the rule.  The activity class refuses a ``result``, so no
path can build one.  ``vultron/`` builds the class only through its factory,
so that refusal is the only way in.  And no call of the factory names a
``result``, or forwards keyword arguments that could carry one.
"""

import ast

import pytest

from test.architecture import _corpus
from test.support.act_clock import ACT_AT
from test.support.objects import authored_at, make
from vultron.wire.as2.factories import (
    VultronActivityConstructionError,
    add_log_entry_activity,
)
from vultron.wire.as2.vocab.objects.case_ledger_entry import as_CaseLedgerEntry

_VULTRON = _corpus.REPO_ROOT / "vultron"
_FACTORY = "add_log_entry_activity"
_CLASS = "_AddLogEntryActivity"
#: The class's own module and the factory module that builds it.
_CLASS_HOMES = {
    "vultron/wire/as2/vocab/activities/sync.py",
    "vultron/wire/as2/factories/sync.py",
}


def _called_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _calls(name: str) -> list[tuple[str, ast.Call]]:
    found = []
    for path, tree in _corpus.files_mentioning(name, under=_VULTRON):
        rel = path.relative_to(_corpus.REPO_ROOT).as_posix()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _called_name(node) == name:
                found.append((rel, node))
    return found


@pytest.mark.spec("SYNC-02-009")
def test_the_ledger_add_refuses_a_result() -> None:
    entry = make(
        as_CaseLedgerEntry,
        context="https://example.org/cases/case-001",
        log_object_id="https://example.org/activities/act-001",
        semantic_type="test_event",
        payload_snapshot={"id": "https://example.org/activities/act-001"},
        received_at=ACT_AT,
        published=ACT_AT,
    )
    with pytest.raises(VultronActivityConstructionError) as exc_info:
        add_log_entry_activity(
            entry,
            actor="https://example.org/actors/case-manager",
            result="https://example.org/activities/follow-on",
            at=authored_at(),
        )
    assert "result" in str(exc_info.value.__cause__)


@pytest.mark.spec("SYNC-02-009")
def test_only_the_factory_builds_the_ledger_add() -> None:
    builders = {rel for rel, _ in _calls(_CLASS)} - _CLASS_HOMES
    assert builders == set(), (
        f"{_CLASS} is built outside its factory in {sorted(builders)};"
        f" build it with {_FACTORY}() (AF-01-001)"
    )


@pytest.mark.spec("SYNC-02-009")
def test_no_factory_call_names_a_result() -> None:
    calls = _calls(_FACTORY)
    assert calls, f"no call of {_FACTORY}() found; the check would be vacuous"
    offenders = sorted(
        f"{rel}:{node.lineno}"
        for rel, node in calls
        if any(kw.arg in (None, "result") for kw in node.keywords)
    )
    assert offenders == [], (
        f"{_FACTORY}() is called with a result or forwarded keyword arguments"
        f" at {offenders}; a ledger Add lists no result (SYNC-02-009)"
    )
