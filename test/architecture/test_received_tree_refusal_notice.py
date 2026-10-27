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

"""Every received tree answers a precondition refusal, or says why not.

When a precondition guard at the CASE_MANAGER refuses an assertion, the
CASE_MANAGER sends the asserter the refusal notice (CLP-02-005, CLP-05-001).
``create_receive_activity_tree`` adds it to every tree that commits to a case
and has precondition guards; a tree goes without it only by passing a
registered ``RefusalNoticeExemption`` (#4756).  These checks keep that the
only way out, and keep the exception set closed and reasoned:

1. **Pinned exemption set** ``REFUSAL_NOTICE_EXEMPTION_USES``: which tree
   passes each exemption, held to equality in both directions (ARCH-18-001,
   ARCH-18-002), and every registered exemption is used by some tree.  A tree
   with a diversion takes the notice like any other: the refusal stage skips
   it for a diverted delivery, which its diversion answered (CLP-10-026).
2. The registry is the module's whole list: every ``RefusalNoticeExemption``
   constant in ``refusal_notice.py`` is registered, each with its own reason.
3. Every received tree, built as it runs, that commits to a case and has a
   precondition guard holds exactly one refusal notice among the refusal
   effects of its guard stage, unless it was built with an exemption; an
   exempt tree holds none, and holds what its reason says answers instead
   (:data:`STAND_INS`).
4. **Pinned exemption set** ``NO_COMMIT_TREES``: a received tree that commits
   nothing adjudicates no assertion for the ledger, so it refuses none at the
   CASE_MANAGER before a commit; each one is pinned with the reason, so a new
   one is a decision.
"""

import ast
import inspect

import py_trees
import pytest

from test.architecture._received_tree_builds import built_received_trees
from test.architecture.test_received_tree_case_manager_gate import (
    _receive_calls,
)
from vultron.core.behaviors.case.nodes import refusal_notice
from vultron.core.behaviors.case.nodes.clock_decision_stage import (
    ClockDecisionStage,
)
from vultron.core.behaviors.case.nodes.intake import (
    IntakeReceivedActivityNode,
)
from vultron.core.behaviors.case.nodes.leave.decline import (
    EmitRejectCloseCaseNode,
)
from vultron.core.behaviors.case.nodes.refusal_notice import (
    REFUSAL_NOTICE_EXEMPTIONS,
    EmitRefusalNoticeNode,
    RefusalNoticeExemption,
)
from vultron.core.behaviors.case.nodes.refusal_stage import (
    PreconditionGuardStage,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    ReceivedActivityTree,
    received_stages,
)

_KEYWORD = "refusal_notice_exemption"
_COMMIT = "GuardedCommitCaseLedgerEntryBT"
_C = "vultron/core/behaviors/case"
_E = "vultron/core/behaviors/embargo"
_R = "vultron/core/behaviors/report"

_Site = tuple[str, str]

# ---------------------------------------------------------------------------
# 1. Which tree passes which exemption: (constant, module, top-level function).
# ---------------------------------------------------------------------------
# permanent: CM-23-011 (the decline arm's Reject(Leave) answers the close arm)
REFUSAL_NOTICE_EXEMPTION_USES: frozenset[tuple[str, str, str]] = frozenset(
    {
        (
            "OWNER_CLOSE_DECLINE",
            f"{_C}/receive_close_case_tree.py",
            "create_close_case_received_tree",
        ),
    }
)

#: The exemptions whose reason names a node that answers the refusal instead,
#: and that node: the built tree must hold it.
STAND_INS: dict[str, type[py_trees.behaviour.Behaviour]] = {
    "owner-close-decline": EmitRejectCloseCaseNode,
}

# ---------------------------------------------------------------------------
# 4. Received trees that commit nothing, and why none refuses an assertion at
#    the CASE_MANAGER before a commit.
# ---------------------------------------------------------------------------
_PARTICIPANT_SIDE = (
    "the receiver is a participant taking an activity only the CASE_MANAGER"
    " sends, so no CASE_MANAGER adjudicates it (CLP-02-013)"
)
_BEFORE_ANY_CASE = (
    "the activity comes before any case exists, so there is no case whose"
    " CASE_MANAGER answers it"
)
_NOT_UNDERSTOOD = (
    "the receiver did not understand the activity, which MSM-05-001 answers"
    " with a ProcessingFault, never a Reject"
)

# permanent: CLP-02-005 (each entry records why a no-commit tree sends no notice)
NO_COMMIT_TREES: dict[_Site, str] = {
    (
        f"{_C}/accept_case_proposal_received_tree.py",
        "create_accept_case_proposal_received_tree",
    ): _PARTICIPANT_SIDE,
    (
        f"{_C}/announce_case_received_tree.py",
        "create_announce_vulnerability_case_received_tree",
    ): _PARTICIPANT_SIDE,
    (
        f"{_C}/case_proposal_received_tree.py",
        "create_case_proposal_received_tree",
    ): (
        "a case proposal comes before its case exists; the CASE_MANAGER"
        " answers a declined one with Reject(CaseProposal) (CP-05-002,"
        " CP-05-006)"
    ),
    (
        f"{_C}/create_case_received_tree.py",
        "create_create_case_received_tree",
    ): _PARTICIPANT_SIDE,
    (
        f"{_C}/intake_only_received_tree.py",
        "create_incomplete_activity_received_tree",
    ): _NOT_UNDERSTOOD,
    (
        f"{_C}/intake_only_received_tree.py",
        "create_intake_only_received_tree",
    ): "the tree only archives what arrived and judges nothing (CLP-10-017)",
    (
        f"{_C}/receive_report_case_tree.py",
        "create_offer_received_without_report_tree",
    ): _BEFORE_ANY_CASE,
    (
        f"{_C}/receive_report_case_tree.py",
        "create_receive_report_case_tree",
    ): _BEFORE_ANY_CASE,
    (
        f"{_C}/refusal_notice_received_tree.py",
        "refusal_notice_received_tree",
    ): _PARTICIPANT_SIDE,
    (
        f"{_C}/reject_case_proposal_received_tree.py",
        "create_reject_case_proposal_received_tree",
    ): _PARTICIPANT_SIDE,
    (
        f"{_C}/suggest_actor_tree.py",
        "create_recommendation_answer_received_tree",
    ): _PARTICIPANT_SIDE,
    (
        "vultron/core/behaviors/dead_letter/dead_letter_tree.py",
        "create_store_dead_letter_tree",
    ): _NOT_UNDERSTOOD,
    (
        f"{_E}/announce_received_tree.py",
        "announce_embargo_received_tree",
    ): _PARTICIPANT_SIDE,
    (f"{_E}/invite_received_tree.py", "embargo_invite_fault_tree"): (
        _NOT_UNDERSTOOD
    ),
    (f"{_R}/received_report_trees.py", "create_ack_report_received_tree"): (
        "RK goes to the reporter, never to the CASE_MANAGER (RMB-08-003)"
    ),
    (f"{_R}/received_report_trees.py", "create_report_received_tree"): (
        _BEFORE_ANY_CASE
    ),
    (
        "vultron/core/behaviors/sync/announce_tree.py",
        "create_announce_log_entry_tree",
    ): _PARTICIPANT_SIDE,
    (
        "vultron/core/behaviors/sync/reject_tree.py",
        "create_reject_log_entry_tree",
    ): (
        "a replica's resync request is ledger mechanics, answered by a replay"
        " of the entries it asks for, never by a refusal (SYNC-03-005)"
    ),
    (
        "vultron/core/behaviors/sync/read_tree.py",
        "create_read_log_entry_tree",
    ): (
        "a participant's stated ledger position is ledger mechanics, answered"
        " by a replay of the entries after it, never by a refusal"
        " (SYNC-17-002, SYNC-17-006)"
    ),
    (
        "vultron/core/behaviors/sync/divergence_tree.py",
        "create_case_diverged_fault_tree",
    ): (
        "a replica's divergence fault is replication signalling, answered by"
        " a fresh case copy, never ledgered or refused (SYNC-16-002,"
        " SYNC-16-003)"
    ),
    (
        "vultron/core/behaviors/sync/hash_mismatch_tree.py",
        "create_hash_mismatch_fault_tree",
    ): (
        "a replica's hash-mismatch fault is replication signalling, logged"
        " with a self-check and never ledgered or refused (SYNC-03-008,"
        " SYNC-03-010)"
    ),
}


def _branches(value: ast.expr) -> list[ast.expr]:
    """The values *value* may take: both arms of a conditional, recursively."""
    if isinstance(value, ast.IfExp):
        return _branches(value.body) + _branches(value.orelse)
    return [value]


def _exemption_uses() -> frozenset[tuple[str, str, str]]:
    """Each registered exemption constant a received tree passes."""
    uses: set[tuple[str, str, str]] = set()
    for rel, scope, call in _receive_calls():
        for kw in call.keywords:
            if kw.arg != _KEYWORD:
                continue
            for value in _branches(kw.value):
                if isinstance(value, ast.Constant) and value.value is None:
                    continue
                assert isinstance(value, ast.Name), (
                    f"{rel}:{scope}: pass a registered exemption constant"
                    " from refusal_notice.py (or None), not an inline value"
                )
                uses.add((value.id, rel, scope))
    return frozenset(uses)


def _registered_constants() -> dict[str, RefusalNoticeExemption]:
    """The ``RefusalNoticeExemption`` constants ``refusal_notice.py`` defines."""
    return {
        name: value
        for name, value in inspect.getmembers(refusal_notice)
        if isinstance(value, RefusalNoticeExemption)
    }


def _received_trees(
    tree: py_trees.behaviour.Behaviour,
) -> list[ReceivedActivityTree]:
    """Every factory-built tree in *tree*: itself and any it nests."""
    return [n for n in tree.iterate() if isinstance(n, ReceivedActivityTree)]


def _commits(tree: ReceivedActivityTree) -> bool:
    return any(child.name == _COMMIT for child in received_stages(tree))


def _guards(tree: ReceivedActivityTree) -> list[py_trees.behaviour.Behaviour]:
    """The precondition guards of a committing tree, as it runs them.

    The children between the door guards (and the clock decisions) and the
    commit; a guard stage contributes the guards it wraps.
    """
    doors = {id(guard) for guard in tree.door_guards}
    guards: list[py_trees.behaviour.Behaviour] = []
    for child in received_stages(tree):
        if child.name == _COMMIT:
            break
        if id(child) in doors or any(
            isinstance(n, ClockDecisionStage) for n in child.iterate()
        ):
            continue
        if isinstance(child, PreconditionGuardStage):
            guards.extend(child.guards.children)
        else:
            guards.append(child)
    return guards


def _notices(tree: ReceivedActivityTree) -> list[EmitRefusalNoticeNode]:
    """The refusal notices among the refusal effects of *tree*'s guards."""
    return [
        n
        for child in tree.children
        if isinstance(child, PreconditionGuardStage)
        for n in child.refusal.iterate()
        if isinstance(n, EmitRefusalNoticeNode)
    ]


@pytest.mark.spec("CLP-02-005")
@pytest.mark.spec("ARCH-18-001")
def test_refusal_notice_exemption_uses_are_pinned() -> None:
    actual = _exemption_uses()
    expected = REFUSAL_NOTICE_EXEMPTION_USES
    assert actual == expected, (
        f"NEW: {sorted(actual - expected)}; a new exemption use is a"
        " decision — pin it here with its reason."
        f" STALE: {sorted(expected - actual)}; remove it (ARCH-18-002)"
    )


@pytest.mark.spec("CLP-02-005")
def test_the_exemption_set_is_closed_and_reasoned() -> None:
    """Every constant is registered, used, and carries its own reason."""
    constants = _registered_constants()
    assert {c.name for c in constants.values()} == set(
        REFUSAL_NOTICE_EXEMPTIONS
    )
    for exemption in constants.values():
        assert REFUSAL_NOTICE_EXEMPTIONS[exemption.name] is exemption
    reasons = [c.reason for c in constants.values()]
    assert len(set(reasons)) == len(reasons), "each exemption has its reason"
    used = {constant for constant, _, _ in REFUSAL_NOTICE_EXEMPTION_USES}
    assert used == set(constants), (
        f"registered but unused: {sorted(set(constants) - used)};"
        f" used but not registered: {sorted(used - set(constants))}"
    )


def _classify(
    trees: dict[str, py_trees.behaviour.Behaviour],
) -> tuple[list[str], list[str], list[str]]:
    """Sort the guarded commit trees in *trees* that break the rule.

    Returns the labels of trees that send no notice and name no exemption,
    of trees that send more than one, and of exempt trees that send one.
    """
    unanswered: list[str] = []
    doubled: list[str] = []
    exempt_with_notice: list[str] = []
    for label, tree in sorted(trees.items()):
        for received in _received_trees(tree):
            if not _commits(received) or not _guards(received):
                continue
            where = f"{label} [{received.name}]"
            notices = len(_notices(received))
            if received.refusal_notice_exemption is not None:
                if notices:
                    exempt_with_notice.append(where)
            elif notices == 0:
                unanswered.append(where)
            elif notices > 1:
                doubled.append(where)
    return unanswered, doubled, exempt_with_notice


@pytest.mark.spec("CLP-02-005")
@pytest.mark.spec("CLP-05-001")
@pytest.mark.spec("CLP-10-022")
def test_every_guarded_commit_tree_answers_a_refusal_unless_exempt() -> None:
    """A tree that can refuse before its commit holds one notice, or none
    and the exemption that says why."""
    unanswered, doubled, exempt_with_notice = _classify(
        {
            f"{rel}:{scope}": tree
            for (rel, scope), tree in built_received_trees().items()
        }
    )
    assert unanswered == [], (
        f"trees whose precondition refusals send no refusal notice:"
        f" {unanswered}; pass a registered refusal_notice_exemption that"
        " says what answers them instead (CLP-02-005)"
    )
    assert doubled == [], f"trees answering a refusal twice: {doubled}"
    assert exempt_with_notice == [], (
        f"exempt trees that still send the notice: {exempt_with_notice}"
    )


@pytest.mark.spec("CLP-02-005")
@pytest.mark.parametrize("name", sorted(STAND_INS))
def test_an_exempt_tree_holds_what_answers_it_instead(name: str) -> None:
    stand_in = STAND_INS[name]
    exempt = [
        tree
        for tree in built_received_trees().values()
        if any(
            received.refusal_notice_exemption is not None
            and received.refusal_notice_exemption.name == name
            for received in _received_trees(tree)
        )
    ]
    assert exempt, f"no built tree uses the {name} exemption"
    for tree in exempt:
        assert any(isinstance(n, stand_in) for n in tree.iterate()), (
            f"{tree.name} is exempt as {name} but holds no {stand_in.__name__}"
        )


@pytest.mark.spec("CLP-02-005")
@pytest.mark.spec("ARCH-18-001")
def test_every_tree_that_commits_nothing_is_pinned_with_its_reason() -> None:
    actual = {
        site
        for site, tree in built_received_trees().items()
        if not any(_commits(received) for received in _received_trees(tree))
    }
    assert actual == set(NO_COMMIT_TREES), (
        f"NEW: {sorted(actual - set(NO_COMMIT_TREES))}; a received tree that"
        " commits nothing is a decision — pin it with the reason it refuses"
        " no assertion at the CASE_MANAGER."
        f" STALE: {sorted(set(NO_COMMIT_TREES) - actual)} (ARCH-18-002)"
    )


def _hand_built(
    name: str,
    *,
    notices: int = 0,
    exemption: RefusalNoticeExemption | None = None,
) -> ReceivedActivityTree:
    """A tree shaped like the factory's: a guard stage, then the commit."""
    from py_trees.behaviours import Success
    from py_trees.composites import Sequence

    stage = PreconditionGuardStage(
        name=f"{name}Guards",
        guards=Sequence(
            name=f"{name}GuardSeq", memory=False, children=[Success("Guard")]
        ),
        refusal=Sequence(
            name=f"{name}Refusal",
            memory=False,
            children=[
                EmitRefusalNoticeNode(case_id="urn:case", name=f"Notice{i}")
                for i in range(notices)
            ],
        ),
        intake=IntakeReceivedActivityNode(),
    )
    return ReceivedActivityTree(
        name=name,
        children=[stage, Success(name=_COMMIT)],
        door_guards=[],
        refusal_notice_exemption=exemption,
    )


@pytest.mark.spec("CLP-02-005")
def test_the_scan_sees_a_tree_that_breaks_the_rule() -> None:
    """The check sorts a silent, a doubled and an exempt-but-noisy tree."""
    exemption = next(iter(REFUSAL_NOTICE_EXEMPTIONS.values()))
    unanswered, doubled, exempt_with_notice = _classify(
        {
            "silent": _hand_built("Silent"),
            "answered": _hand_built("Answered", notices=1),
            "doubled": _hand_built("Doubled", notices=2),
            "exempt": _hand_built("Exempt", exemption=exemption),
            "exempt-noisy": _hand_built(
                "ExemptNoisy", notices=1, exemption=exemption
            ),
        }
    )

    assert unanswered == ["silent [Silent]"]
    assert doubled == ["doubled [Doubled]"]
    assert exempt_with_notice == ["exempt-noisy [ExemptNoisy]"]
