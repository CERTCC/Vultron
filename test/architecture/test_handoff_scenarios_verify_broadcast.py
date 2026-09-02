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

"""Every ownership-handoff scenario must verify the CM-21-007 broadcast.

ADR-0053's stated validation criterion is that an actor *outside* the
ownership negotiation learns of the completed transfer from
``Announce(CaseLedgerEntry)`` alone.  Verifying ``attributed_to`` on the old and
new owners' replicas does **not** establish that: both are parties to the
transfer and would see the change through the offer/accept exchange itself.

This is a structural ratchet rather than a per-scenario behavioural test because
the defect it guards is an *omission*, and an omission in a scenario nobody
thought to check is exactly what slipped through: ``fvcv_handoff_demo`` gained
this check in #2789 while its sibling ``fccv_handoff_demo`` — same phase, same
topology, same protocol hop — did not, and every test stayed green.  A ratchet
over "all scenarios defining this phase" also covers handoff scenarios that do
not exist yet.

Related: AGENTS.md § "Fix One, Miss the Siblings: Scan Peer Files Before Closing
a Bug"; ``notes/ownership-transfer.md``; CM-21-007; EDF-06-002.
"""

import ast

import pytest

from test.architecture import _corpus

SCENARIO_DIR = _corpus.REPO_ROOT / "vultron/demo/scenario"

#: The phase that performs the ownership transfer.
PHASE_NAME = "_phase_ownership_handoff"

#: The ledger event a completed transfer commits (CM-21-007).
TRANSFER_EVENT_TYPE = "accept_case_ownership_transfer"

#: The gate helper that reads a named actor's ledger replica.
LEDGER_WAIT_FN = "wait_for_event_type_in_ledger"


def _scenarios_with_handoff_phase() -> list[tuple[str, ast.AST]]:
    """Return ``(module name, tree)`` for scenarios defining the handoff phase.

    Uses the shared corpus so the sources and ASTs are read once at import time
    rather than per ratchet (TB-13-001 through TB-13-003).
    """
    found = [
        (path.name, tree)
        for path, tree in _corpus.files_mentioning(
            f"def {PHASE_NAME}(", under=SCENARIO_DIR
        )
    ]
    assert found, (
        f"no scenario defines {PHASE_NAME} — the ratchet would pass vacuously."
        " If the phase was renamed, update PHASE_NAME."
    )
    return found


def _handoff_phase(tree: ast.AST) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == PHASE_NAME:
            return node
    raise AssertionError(f"{PHASE_NAME} not found after source-level match")


def _keyword(call: ast.Call, name: str) -> ast.expr | None:
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    return None


def _transfer_ledger_waits(phase: ast.FunctionDef) -> list[ast.Call]:
    """Return the ledger waits in *phase* that name the transfer event type."""
    calls = []
    for node in ast.walk(phase):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        fn_name = (
            fn.attr
            if isinstance(fn, ast.Attribute)
            else getattr(fn, "id", None)
        )
        if fn_name != LEDGER_WAIT_FN:
            continue
        event_type = _keyword(node, "event_type")
        if (
            isinstance(event_type, ast.Constant)
            and event_type.value == TRANSFER_EVENT_TYPE
        ):
            calls.append(node)
    return calls


@pytest.mark.spec("CM-21-007")
@pytest.mark.parametrize(
    "scenario_name, tree",
    _scenarios_with_handoff_phase(),
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_handoff_phase_verifies_transfer_reached_a_non_party_replica(
    scenario_name: str, tree: ast.AST
) -> None:
    """The handoff phase must gate on a non-party actor's own ledger replica."""
    phase = _handoff_phase(tree)

    waits = _transfer_ledger_waits(phase)
    assert waits, (
        f"{scenario_name}::{PHASE_NAME} never waits for a"
        f" {TRANSFER_EVENT_TYPE!r} ledger entry. ADR-0053's validation criterion"
        " is that an actor outside the negotiation learns of the transfer from"
        " the CM-21-007 broadcast; asserting attributed_to on the old and new"
        " owners does not establish that, because both are parties to it."
    )

    # The observable has to be read on a non-party's container.  Reading it on
    # the offerer's or the transferee's proves only that a party to the exchange
    # caught up, which the offer/accept round-trip already guarantees
    # (EDF-06-002).
    party_hints = (
        "vendor_client",
        "coordinator_client",
        "c1_client",
        "c2_client",
    )
    clients = []
    for call in waits:
        client = _keyword(call, "client")
        clients.append(client.id if isinstance(client, ast.Name) else None)

    assert any(c is not None and c not in party_hints for c in clients), (
        f"{scenario_name}::{PHASE_NAME} waits for {TRANSFER_EVENT_TYPE!r} but"
        f" only on a party to the transfer (clients={clients!r}). Read it on a"
        " non-party's own container — the reporter/finder — so the assertion"
        " tests the broadcast rather than the exchange (EDF-06-002)."
    )
