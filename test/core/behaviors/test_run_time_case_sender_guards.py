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

"""Who the trees whose case is resolved at run time admit (#4696, AC-4).

The Engage, Invalidate(Report), Announce(CaseLedgerEntry) and
Reject(CaseLedgerEntry) trees take their sender guard from the receive-tree
factory, composed from the use case's declared rule (HP-01-008).  Each case
below builds the real tree, finds the guard the factory placed in it, and
runs that guard at a store holding the case, once for a sender the rule
entitles and once for one it does not.

A Close(Report) on a case entitles no sender (CM-23-019), so it has no
entitled sender to run here; ``test_close_report_on_case.py`` drives its
refusal.
"""

from collections.abc import Callable
from dataclasses import dataclass
from types import SimpleNamespace

import py_trees
import pytest
from py_trees.common import Status

from test.core.behaviors.bt_harness import BTTestScenario
from test.core.use_cases.received.conftest import (
    seed_case_manager_participant,
    seed_case_participant,
)
from test.support.case_owner import CASE_OWNER_ID
from vultron.core.behaviors.report.prioritize_tree import (
    create_engage_case_tree,
)
from vultron.core.behaviors.report.received_report_trees import (
    create_invalidate_report_received_tree,
)
from vultron.core.behaviors.sync.announce_tree import (
    create_announce_log_entry_tree,
)
from vultron.core.behaviors.sync.nodes.chain import _to_persistable_entry
from vultron.core.behaviors.sync.reject_tree import (
    create_reject_log_entry_tree,
)
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.use_cases.received.case.engage_defer import (
    EngageCaseReceivedUseCase,
)
from vultron.core.use_cases.received.report import (
    InvalidateReportReceivedUseCase,
)
from vultron.core.use_cases.received.sync import (
    AnnounceLedgerEntryReceivedUseCase,
    RejectLedgerEntryReceivedUseCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

CASE_ID = "https://example.org/cases/run-time-case"
MANAGER = "https://example.org/actors/case-manager"
VENDOR = "https://example.org/actors/vendor"
REPLICA = "https://example.org/actors/replica"
STRANGER = "https://example.org/actors/stranger"
REPORT_ID = "https://example.org/reports/run-time-case"


def _store(receiver: str) -> BTTestScenario:
    """*receiver*'s store holding the case: MANAGER, VENDOR and REPLICA."""
    scenario = BTTestScenario(actor_id=receiver)
    case = as_VulnerabilityCase(
        attributed_to=CASE_OWNER_ID, id_=CASE_ID, name="Run-time case"
    )
    seed_case_manager_participant(scenario.dl, case, MANAGER)
    seed_case_participant(scenario.dl, case, VENDOR)
    seed_case_participant(scenario.dl, case, REPLICA)
    scenario.dl.create(case)
    return scenario


def _entry() -> CaseLedgerEntry:
    return _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=0,
            object_id="https://example.org/activities/log-0",
            semantic_type="test_event",
            payload_snapshot={"log_index": 0},
            prev_log_hash="0" * 64,
        )
    )


def _report_request(sender: str) -> SimpleNamespace:
    return SimpleNamespace(
        actor_id=sender,
        report_id=REPORT_ID,
        activity_id="https://example.org/activities/report-verdict",
    )


@dataclass(frozen=True)
class TreeCase:
    """One tree: how to build it for a sender, and whom its rule admits."""

    build: Callable[[str], py_trees.behaviour.Behaviour]
    activity: Callable[[str], object]
    receiver: str
    entitled: str
    unentitled: str


TREES: dict[str, TreeCase] = {
    "engage": TreeCase(
        build=lambda sender: create_engage_case_tree(
            CASE_ID,
            sender,
            sender_rule=EngageCaseReceivedUseCase.sender_entitlement,
        ),
        activity=lambda sender: SimpleNamespace(actor_id=sender),
        receiver=MANAGER,
        entitled=VENDOR,
        unentitled=STRANGER,
    ),
    "invalidate-report": TreeCase(
        build=lambda sender: create_invalidate_report_received_tree(
            _report_request(sender),  # type: ignore[arg-type]
            CASE_ID,
            sender_rule=InvalidateReportReceivedUseCase.sender_entitlement,
        ),
        activity=lambda sender: SimpleNamespace(actor_id=sender),
        receiver=MANAGER,
        entitled=VENDOR,
        unentitled=STRANGER,
    ),
    "announce-ledger-entry": TreeCase(
        build=lambda _sender: create_announce_log_entry_tree(
            sender_rule=AnnounceLedgerEntryReceivedUseCase.sender_entitlement
        ),
        activity=lambda sender: SimpleNamespace(
            actor_id=sender, log_entry=_entry()
        ),
        receiver=REPLICA,
        entitled=MANAGER,
        unentitled=VENDOR,
    ),
    "reject-ledger-entry": TreeCase(
        build=lambda _sender: create_reject_log_entry_tree(
            CASE_ID,
            sender_rule=RejectLedgerEntryReceivedUseCase.sender_entitlement,
        ),
        activity=lambda sender: SimpleNamespace(
            actor_id=sender, rejected_entry=_entry()
        ),
        receiver=MANAGER,
        entitled=VENDOR,
        unentitled=STRANGER,
    ),
}


def _guard(tree: py_trees.behaviour.Behaviour) -> py_trees.behaviour.Behaviour:
    """The sender guard the factory placed among the tree's stages."""
    guards = [
        child
        for child in tree.children
        if getattr(child, "guards_kind", None) is not None
    ]
    assert len(guards) == 1, [child.name for child in tree.children]
    return guards[0]


def _admits(label: str, sender: str) -> bool:
    case = TREES[label]
    guard = _guard(case.build(sender))
    result = _store(case.receiver).run(guard, activity=case.activity(sender))
    assert not result.internal_error, result.feedback_message
    return result.status == Status.SUCCESS


@pytest.mark.spec("HP-01-006", "HP-01-008")
@pytest.mark.parametrize("label", list(TREES))
def test_the_factory_guard_admits_the_entitled_sender(label: str) -> None:
    assert _admits(label, TREES[label].entitled)


@pytest.mark.spec("HP-01-006", "HP-01-008")
@pytest.mark.parametrize("label", list(TREES))
def test_the_factory_guard_refuses_the_unentitled_sender(label: str) -> None:
    assert not _admits(label, TREES[label].unentitled)
