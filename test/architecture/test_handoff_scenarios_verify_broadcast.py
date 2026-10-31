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
thought to check is exactly what slipped through: ``rvcv_handoff_demo`` gained
this check in #2789 while its sibling ``rccv_handoff_demo`` — same phase, same
topology, same protocol hop — did not, and every test stayed green.

The subject is therefore **every function that offers the transfer**, found by
the trigger call it makes rather than by a phase name: a handoff written as a
story fragment carries no ``_phase_`` function, and a ratchet keyed on that name
would have narrowed to one scenario the moment ``rccv-handoff`` was composed
(#5535).  Keying it on the trigger also covers handoff scenarios that do not
exist yet, and the shared continuation several of them reach through.

Related: ``notes/git-workflow-pitfalls.md`` § "Fix One, Miss the Siblings: Scan
Peer Files Before Closing a Bug"; ``notes/ownership-transfer.md``; CM-21-007;
EDF-06-002.
"""

import ast

import pytest

from test.architecture import _corpus

#: Where a handoff is written: as a scenario's own phase, or as a story
#: fragment the scenarios of a family share.
HANDOFF_DIRS = (
    _corpus.REPO_ROOT / "vultron/demo/scenario",
    _corpus.REPO_ROOT / "vultron/demo/helpers",
)

#: The trigger that offers the transfer (TRIG-11-001).  The function that calls
#: it is the handoff, whatever it is named.
OFFER_TRIGGER = "offer_case_ownership_transfer"

#: The ledger event a completed transfer commits (CM-21-007).
TRANSFER_SEMANTIC_TYPE = "accept_case_ownership_transfer"

#: The gate helper that reads a named actor's ledger replica.
LEDGER_WAIT_FN = "wait_for_semantic_type_in_ledger"

#: Identifiers that name a *party* to the transfer, in either form: the
#: offerer's and the transferee's clients in a phase, and the two parts a
#: shared continuation is handed.  The non-party read must mention none of
#: them.
PARTY_NAMES = frozenset(
    {
        "vendor_client",
        "coordinator_client",
        "c1_client",
        "c2_client",
        "owner",
        "new_owner",
    }
)


def _called_name(node: ast.Call) -> str | None:
    """The bare name of *node*'s callee, attribute access or not."""
    fn = node.func
    if isinstance(fn, ast.Attribute):
        return fn.attr
    return getattr(fn, "id", None)


def _handoff_functions() -> list[tuple[str, ast.FunctionDef]]:
    """Return ``(<module>::<function>, node)`` for every handoff written.

    Uses the shared corpus so the sources and ASTs are read once at import time
    rather than per ratchet (TB-13-001 through TB-13-003).  A handoff is a
    function that calls the offer trigger: that is what the ADR-0053 criterion
    attaches to, and it holds whether the handoff is a scenario's phase or a
    story fragment shared by several (#5535).  Only the modules that drive a
    demo are scanned, so the trigger's own definition and the session method
    that posts it are out of scope.
    """
    found: list[tuple[str, ast.FunctionDef]] = []
    for directory in HANDOFF_DIRS:
        for path, tree in _corpus.files_mentioning(
            f".{OFFER_TRIGGER}(", under=directory
        ):
            for node in ast.walk(tree):
                if not isinstance(node, ast.FunctionDef):
                    continue
                if any(
                    _called_name(call) == OFFER_TRIGGER
                    for call in ast.walk(node)
                    if isinstance(call, ast.Call)
                ):
                    found.append((f"{path.name}::{node.name}", node))
    assert found, (
        f"no demo function calls {OFFER_TRIGGER} — the ratchet would pass"
        " vacuously. If the trigger was renamed, update OFFER_TRIGGER."
    )
    return found


def _keyword(call: ast.Call, name: str) -> ast.expr | None:
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    return None


#: Every handoff written, derived once at import time (TB-13-001).
_HANDOFF_FUNCTIONS = _handoff_functions()


def _identifiers(node: ast.expr | None) -> set[str]:
    """Every identifier *node* mentions, however deeply."""
    if node is None:
        return set()
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            names.add(child.id)
        elif isinstance(child, ast.Attribute):
            names.add(child.attr)
    return names


def _transfer_ledger_waits(phase: ast.FunctionDef) -> list[ast.Call]:
    """Return the ledger waits in *phase* that name the transfer semantic type."""
    calls = []
    for node in ast.walk(phase):
        if not isinstance(node, ast.Call):
            continue
        if _called_name(node) != LEDGER_WAIT_FN:
            continue
        semantic_type = _keyword(node, "semantic_type")
        if (
            isinstance(semantic_type, ast.Constant)
            and semantic_type.value == TRANSFER_SEMANTIC_TYPE
        ):
            calls.append(node)
    return calls


def test_the_ratchet_has_a_handoff_of_both_shapes() -> None:
    """One subject of each shape, not merely a non-empty set.

    A non-empty guard cannot tell one subject from two, so the silent
    narrowing this ratchet was rewritten to prevent would pass it: the scan
    must find a handoff written as a scenario phase **and** one written as a
    shared story fragment, because the scenarios are mid-migration (#5535,
    ``notes/architecture-ratchet-corpus.md`` § "Key a Ratchet on the Act, Not
    on the Name of What Performs It").  The last phase-written handoff going
    away is then the signal to retire that arm here on purpose, as its
    sibling does (``test_demo_scenario_waits_in_demo_context.py``
    § ``test_the_check_has_subjects_of_both_shapes``).
    """
    modules = {name.split("::", 1)[0] for name, _ in _HANDOFF_FUNCTIONS}
    assert any(name.endswith("_demo.py") for name in modules), (
        "no scenario module performs a handoff of its own, so the"
        " phase-written arm checks nothing; if the last one has been composed,"
        " retire this arm deliberately. Found: " + repr(sorted(modules))
    )
    assert any(not name.endswith("_demo.py") for name in modules), (
        "no shared helper performs a handoff, so the composed arm checks"
        " nothing. Found: " + repr(sorted(modules))
    )


@pytest.mark.spec("CM-21-007")
@pytest.mark.parametrize(
    "handoff_name, handoff",
    _HANDOFF_FUNCTIONS,
    ids=lambda v: v if isinstance(v, str) else "",
)
def test_a_handoff_verifies_the_transfer_reached_a_non_party_replica(
    handoff_name: str, handoff: ast.FunctionDef
) -> None:
    """A handoff must gate on a non-party actor's own ledger replica."""
    waits = _transfer_ledger_waits(handoff)
    assert waits, (
        f"{handoff_name} never waits for a {TRANSFER_SEMANTIC_TYPE!r} ledger"
        " entry. ADR-0053's validation criterion is that an actor outside the"
        " negotiation learns of the transfer from the CM-21-007 broadcast;"
        " asserting attributed_to on the old and new owners does not establish"
        " that, because both are parties to it."
    )

    # The observable has to be read on a non-party's container.  Reading it on
    # the offerer's or the transferee's proves only that a party to the exchange
    # caught up, which the offer/accept round-trip already guarantees
    # (EDF-06-002).  The client is named, so an unnamed one (a literal, a call
    # on nothing) counts as no non-party read at all.
    reads = [_identifiers(_keyword(call, "client")) for call in waits]

    assert any(read and not (read & PARTY_NAMES) for read in reads), (
        f"{handoff_name} waits for {TRANSFER_SEMANTIC_TYPE!r} but only on a"
        f" party to the transfer (clients={[sorted(r) for r in reads]!r}). Read"
        " it on a non-party's own container — the Reporter — so the assertion"
        " tests the broadcast rather than the exchange (EDF-06-002)."
    )
