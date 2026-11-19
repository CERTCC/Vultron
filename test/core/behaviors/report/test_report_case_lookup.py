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

"""The report verdict trees find their case with a lookup node (BT-25-009).

``Accept``, ``TentativeReject`` and ``Reject`` of ``Offer(VulnerabilityReport)``
name a report, never its case.  Each tree finds the case with
:class:`FindCaseForReport` ahead of its path stage, which is then the one
source of ``/case_id`` in the tree (BT-25-011), and the use case reads no
store (ADR-0195).  A miss publishes nothing; the tree refuses it with the
reason the trees gave when the case was read before the run (BT-25-010).
"""

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import py_trees
import pytest
from py_trees.common import Status

from test.support.act_runner import run_in_act, run_tree
from test.support.case_owner import CASE_OWNER_ID
from test.support.objects import make
from test.support.received import with_evidence
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.act_inputs import (
    KeySource,
    published_act_keys,
    tree_inputs,
)
from vultron.core.behaviors.act_key_scope import unscoped, with_act_keys
from vultron.core.behaviors.act_keys import (
    CASE_ID as CASE_KEY,
    REPORT_ID as REPORT_KEY,
)
from vultron.core.behaviors.act_transaction import (
    ActTransaction,
    received_act_stage,
)
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.case_lookup import (
    CaseFoundForReport,
    FindCaseForReport,
)
from vultron.core.behaviors.case.nodes.diversion_stage import (
    Diversion,
    DiversionStage,
)
from vultron.core.behaviors.case.nodes.held_case import CaseNamedByReference
from vultron.core.behaviors.case.nodes.received_path import (
    ReceivedPath,
    ReceivedPathNode,
)
from vultron.core.behaviors.case.nodes.refusal_notice import (
    EmitRefusalNoticeNode,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    create_receive_activity_tree,
)
from vultron.core.behaviors.report.received_report_trees import (
    create_close_report_received_tree,
    create_invalidate_report_received_tree,
    create_validate_report_received_tree,
)
from vultron.core.behaviors.sender_check_context import (
    LedgerActivityContext,
    SenderCheckContext,
)
from vultron.core.behaviors.sender_entitlement import (
    SenderEntitlementKind,
    SenderRule,
)
from vultron.core.behaviors.state_write_capable import StateWriteCapable
from vultron.core.models.activity import VultronActivity
from vultron.core.models.events import MessageSemantics
from vultron.core.models.events.report import (
    CloseReportReceivedEvent,
    InvalidateReportReceivedEvent,
    ValidateReportReceivedEvent,
)
from vultron.core.models.report import VulnerabilityReport
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.use_cases.received.report import (
    CloseReportReceivedUseCase,
    InvalidateReportReceivedUseCase,
    ValidateReportReceivedUseCase,
)
from vultron.errors import VultronWiringError
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

ACTOR_ID = "https://example.org/actors/vendor"
REPORT_ID = "https://example.org/reports/lookup-01"
OFFER_ID = "https://example.org/activities/offer-lookup-01"
ACTIVITY_ID = "https://example.org/activities/verdict-lookup-01"
CASE_ID = "https://example.org/cases/lookup-01"


def _request() -> SimpleNamespace:
    return SimpleNamespace(
        actor_id=ACTOR_ID,
        report_id=REPORT_ID,
        offer_id=OFFER_ID,
        activity_id=ACTIVITY_ID,
    )


_TREES: dict[str, Callable[[], py_trees.behaviour.Behaviour]] = {
    "validate": lambda: create_validate_report_received_tree(
        report_id=REPORT_ID,
        offer_id=OFFER_ID,
        sender_actor_id=ACTOR_ID,
        sender_rule=ValidateReportReceivedUseCase.sender_entitlement,
    ),
    "invalidate": lambda: create_invalidate_report_received_tree(
        _request(),  # type: ignore[arg-type]
        sender_rule=InvalidateReportReceivedUseCase.sender_entitlement,
    ),
    "close": lambda: create_close_report_received_tree(
        _request(),  # type: ignore[arg-type]
        sender_rule=CloseReportReceivedUseCase.sender_entitlement,
    ),
}


@pytest.mark.spec("BT-25-009", "BT-25-011")
@pytest.mark.parametrize("label", list(_TREES))
def test_the_lookup_is_the_one_source_of_the_case(label: str) -> None:
    """The tree declares ``/case_id`` published, and the lookup alone
    publishes it: no node holds a case built in (BTND-01-009)."""
    tree = _TREES[label]()
    assert tree_inputs(tree).sources == {CASE_KEY: KeySource.PUBLISHED}
    publishers = [
        type(unscoped(n)).__name__
        for n in tree.iterate()
        if CASE_KEY in published_act_keys(n)
    ]
    assert publishers == ["FindCaseForReport"]


@pytest.mark.spec("BT-25-009")
@pytest.mark.parametrize("label", list(_TREES))
def test_the_lookup_runs_ahead_of_the_path_stage_and_is_no_door(
    label: str,
) -> None:
    tree = _TREES[label]()
    names = [type(unscoped(c)).__name__ for c in tree.children]
    assert names.index("FindCaseForReport") < names.index("ReceivedPathNode")
    assert not any(
        isinstance(unscoped(d), FindCaseForReport)
        for d in tree.door_guards  # type: ignore[attr-defined]
    )


def _store_with_case() -> SqliteDataLayer:
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=ACTOR_ID)
    dl.save(make(VulnerabilityReport, id_=REPORT_ID))
    case = make(
        as_VulnerabilityCase,
        attributed_to=CASE_OWNER_ID,
        id_=CASE_ID,
        name="Lookup case",
    )
    case.vulnerability_reports.append(REPORT_ID)
    dl.save(case)
    return dl


class _ReadCase(py_trees.behaviour.Behaviour):
    """Record the ``/case_id`` an earlier node published."""

    def __init__(self) -> None:
        super().__init__(name="ReadCase")
        self.seen: object = None

    def update(self) -> Status:
        storage = py_trees.blackboard.Blackboard.storage
        self.seen = storage.get(CASE_KEY.path)
        return Status.SUCCESS


def _lookup_then_read(
    dl: SqliteDataLayer, report_id: str | None
) -> tuple[Status, _ReadCase]:
    reader = _ReadCase()
    tree = py_trees.composites.Sequence(
        name="LookupThenRead",
        memory=False,
        children=[
            with_act_keys(FindCaseForReport(), {REPORT_KEY: report_id}),
            reader,
        ],
    )
    result = run_tree(BTBridge(datalayer=dl), tree=tree, actor_id=ACTOR_ID)
    return result.status, reader


@pytest.mark.spec("BT-25-009")
def test_the_lookup_publishes_the_case_it_finds() -> None:
    status, reader = _lookup_then_read(_store_with_case(), REPORT_ID)
    assert status is Status.SUCCESS
    assert reader.seen == CASE_ID


@pytest.mark.spec("BT-25-009")
@pytest.mark.parametrize("report_id", [REPORT_ID, None])
def test_a_miss_publishes_nothing_and_never_refuses(
    report_id: str | None,
) -> None:
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=ACTOR_ID)
    status, reader = _lookup_then_read(dl, report_id)
    assert status is Status.SUCCESS
    assert reader.seen is None


@pytest.mark.spec("BT-25-010")
@pytest.mark.parametrize(
    ("report_id", "reason"),
    [
        (
            REPORT_ID,
            f"no VulnerabilityCase for report '{REPORT_ID}' in this"
            " actor's store",
        ),
        (None, "no report_id — no case to resolve"),
    ],
)
def test_the_miss_is_refused_naming_the_report(
    report_id: str | None, reason: str
) -> None:
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=ACTOR_ID)
    node = CaseFoundForReport()
    result = run_tree(
        BTBridge(datalayer=dl),
        tree=with_act_keys(node, {REPORT_KEY: report_id}),
        actor_id=ACTOR_ID,
    )
    assert result.status is Status.FAILURE
    assert node.feedback_message == reason
    assert node.declared_refusal == f"{reason} (BT-25-010)"


def _rule() -> SenderRule:
    return SenderRule.at_case_manager_only(SenderEntitlementKind.PARTICIPANT)


@pytest.mark.spec("BT-25-011")
def test_a_lookup_beside_a_build_time_case_is_refused() -> None:
    with pytest.raises(VultronWiringError, match="BT-25-011"):
        create_receive_activity_tree(
            name="TwoSourcesBT",
            case_id=CASE_ID,
            precondition_guards=[],
            paths={ReceivedPath.CASE_MANAGER},
            sender_rule=_rule(),
            sender_context=SenderCheckContext(
                sender_id=ACTOR_ID, case_id=CASE_ID
            ),
            case_lookup=FindCaseForReport(),
        )


@pytest.mark.spec("BT-25-009")
def test_a_lookup_that_publishes_no_case_is_refused() -> None:
    with pytest.raises(VultronWiringError, match="BT-25-009"):
        create_receive_activity_tree(
            name="NoPublisherBT",
            case_id=None,
            precondition_guards=[],
            paths={ReceivedPath.CASE_MANAGER},
            sender_rule=_rule(),
            sender_context=SenderCheckContext(sender_id=ACTOR_ID),
            case_lookup=CaseFoundForReport(),
        )


@pytest.mark.spec("BT-25-009", "HP-01-036")
def test_the_in_case_side_reads_the_case_the_lookup_published() -> None:
    """With the case found at run time, the in-case sender check reads it,
    so no check is composed that has no case to read."""
    tree = _TREES["validate"]()
    (stage,) = [n for n in tree.iterate() if isinstance(n, ReceivedPathNode)]
    assert stage.declared == frozenset({ReceivedPath.CASE_MANAGER})
    checks = [
        unscoped(n)
        for n in tree.door_guards  # type: ignore[attr-defined]
        if type(unscoped(n)).__name__ == "SenderIsParticipantNode"
    ]
    assert len(checks) == 1
    # Seeded with the sender only: the case comes from the lookup.
    scope = next(
        n
        for n in tree.door_guards  # type: ignore[attr-defined]
        if unscoped(n) is checks[0]
    )
    assert CASE_KEY not in published_act_keys(scope)


# --- The verdicts with no case, read through the use cases (AC-2) ------------


def _activity(type_: str) -> VultronActivity:
    return make(VultronActivity, id_=ACTIVITY_ID, type_=type_, actor=ACTOR_ID)


def _event(kind: type, semantic: MessageSemantics, type_: str) -> Any:
    return with_evidence(
        kind(
            semantic_type=semantic,
            activity_id=ACTIVITY_ID,
            actor_id=ACTOR_ID,
            object_=make(VulnerabilityReport, id_=OFFER_ID),
            inner_object=make(VulnerabilityReport, id_=REPORT_ID),
            activity=_activity(type_),
        )
    )


_NO_CASE_VERDICTS = {
    # The path stage refuses it: the tree declares the manager path alone
    # (HP-01-039).
    "validate": (
        ValidateReportReceivedUseCase,
        ValidateReportReceivedEvent,
        MessageSemantics.VALIDATE_REPORT,
        "Accept",
        "holds no replica of the case this activity names",
    ),
    "invalidate": (
        InvalidateReportReceivedUseCase,
        InvalidateReportReceivedEvent,
        MessageSemantics.INVALIDATE_REPORT,
        "TentativeReject",
        f"no VulnerabilityCase for report '{REPORT_ID}' in this actor's"
        " store (BT-25-010)",
    ),
}


@pytest.mark.spec("BT-25-010", "HP-01-039")
@pytest.mark.parametrize("label", list(_NO_CASE_VERDICTS))
def test_a_report_with_no_case_is_refused_with_todays_reason(
    label: str,
) -> None:
    use_case, kind, semantic, type_, reason = _NO_CASE_VERDICTS[label]
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=ACTOR_ID)
    result = run_in_act(use_case(dl, _event(kind, semantic, type_)))
    assert result.disposition is HandlerDisposition.REFUSED
    assert reason in (result.reason or "")


@pytest.mark.spec("BT-25-010", "CM-23-019")
def test_a_close_with_no_case_is_refused_by_a_guard() -> None:
    """Close declares the no-case path, so its sender guard runs first; a
    sender the Offer was not addressed to is refused there, as before."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=ACTOR_ID)
    event = _event(
        CloseReportReceivedEvent, MessageSemantics.CLOSE_REPORT, "Reject"
    )
    result = run_in_act(CloseReportReceivedUseCase(dl, event))
    assert result.disposition is HandlerDisposition.REFUSED


# --- The factory's wiring refusals and run-time-case stages ------------------


class _WritingLookup(FindCaseForReport, StateWriteCapable):
    """A lookup that would write state, which a lookup may not."""


@pytest.mark.spec("BT-25-009", "HP-01-024", "AKM-03-006")
@pytest.mark.parametrize(
    ("label", "arguments", "match"),
    [
        (
            "ledger-activity",
            {"sender_context": LedgerActivityContext()},
            "HP-01-024",
        ),
        (
            "held-case",
            {
                "sender_context": SenderCheckContext(sender_id=ACTOR_ID),
                "held_case": CaseNamedByReference.JOIN,
            },
            "AKM-03-006",
        ),
        (
            "writing-lookup",
            {
                "sender_context": SenderCheckContext(sender_id=ACTOR_ID),
                "lookup": _WritingLookup(),
            },
            "BT-25-009",
        ),
    ],
)
def test_the_factory_refuses_a_lookup_it_cannot_place(
    label: str, arguments: dict[str, Any], match: str
) -> None:
    lookup = arguments.pop("lookup", FindCaseForReport())
    with pytest.raises(VultronWiringError, match=match):
        create_receive_activity_tree(
            name=f"Refused{label}BT",
            case_id=None,
            precondition_guards=[],
            paths={ReceivedPath.CASE_MANAGER},
            sender_rule=_rule(),
            case_lookup=lookup,
            **arguments,
        )


@pytest.mark.spec("BT-25-009", "CLP-10-026")
def test_a_manager_only_diversion_takes_the_lookups_case() -> None:
    """A diversion that may commit needs its tree's case; the lookup's case
    is one, so the tree builds where a tree with no case is refused."""
    diversion = Diversion(
        name="Answered",
        condition=py_trees.behaviours.Failure(name="NeverDiverts"),
        effects=(py_trees.behaviours.Success(name="Answer"),),
    )
    tree = create_receive_activity_tree(
        name="DivertedLookupBT",
        case_id=None,
        precondition_guards=[diversion],
        paths={ReceivedPath.CASE_MANAGER},
        sender_rule=_rule(),
        sender_context=SenderCheckContext(sender_id=ACTOR_ID),
        case_lookup=FindCaseForReport(),
    )
    assert any(isinstance(n, DiversionStage) for n in tree.iterate())


@pytest.mark.spec("CLP-07-015", "CLP-02-005", "BT-25-009")
def test_a_lookup_tree_commits_as_one_act_and_owes_the_refusal_notice() -> (
    None
):
    """With the case found at run time the tree still commits in one act
    and answers a guard's refusal with the notice."""
    tree = _TREES["invalidate"]()
    assert any(isinstance(n, ActTransaction) for n in tree.children)
    assert any(isinstance(n, EmitRefusalNoticeNode) for n in tree.iterate())
    act = received_act_stage("T", [], None, None, commits=True)
    assert [type(n) for n in act] == [ActTransaction]
    assert received_act_stage("T", [], None, None) == []
