"""Tests for the nodes that keep what a received case snapshot carries."""

import py_trees
import pytest
from py_trees.common import Status

from test.support.case_owner import (
    CASE_OWNER_ID,
    CONSTRUCTED_CASE_OWNERSHIP,
)
from test.support.embargo_register import register
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.carried_snapshot import (
    CheckCarriedEmbargoNode,
    HoldCarriedEmbargoNode,
    StoreEmbeddedParticipantsNode,
)
from vultron.core.behaviors.case.nodes.refusal_stage import (
    PreconditionGuardStage,
)
from vultron.core.behaviors.case.nodes.role_gates import (
    CaseManagerGate,
)
from vultron.core.behaviors.case.receive_activity_tree import (
    received_stages,
)
from vultron.core.behaviors.report.prioritize_tree import (
    create_engage_case_tree,
)
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.embargo_event import EmbargoEvent
from vultron.core.use_cases.received.case.engage_defer import (
    EngageCaseReceivedUseCase,
)
from vultron.wire.as2.vocab.objects.case_participant import (
    as_CaseParticipant,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_RECEIVER = "https://example.org/actors/receiver"
_SENDER = "https://example.org/actors/sender"
_CASE_ID = "https://example.org/cases/snapshot"


@pytest.fixture
def dl() -> SqliteDataLayer:
    return SqliteDataLayer("sqlite:///:memory:", actor_id=_RECEIVER)


def _participant() -> as_CaseParticipant:
    return as_CaseParticipant(
        id_=f"{_CASE_ID}/participants/sender",
        attributed_to=_SENDER,
        context=_CASE_ID,
    )


def _run(dl, node: py_trees.behaviour.Behaviour):
    return BTBridge(datalayer=dl).execute_with_setup(
        tree=node, actor_id=_RECEIVER
    )


def test_inline_participants_are_stored_as_their_own_records(dl):
    participant = _participant()
    case = as_VulnerabilityCase.model_construct(
        **CONSTRUCTED_CASE_OWNERSHIP,
        id_=_CASE_ID,
        name="snapshot",
        case_participants=[participant],
    )

    result = _run(dl, StoreEmbeddedParticipantsNode(case, _CASE_ID))

    assert result.status == Status.SUCCESS
    assert dl.read(participant.id_) is not None


def test_a_case_naming_an_unheld_embargo_is_refused(dl):
    case = as_VulnerabilityCase(
        attributed_to=CASE_OWNER_ID,
        id_=_CASE_ID,
        name="snapshot",
        embargo_register=register(active=f"{_CASE_ID}/embargo_events/unheld"),
    )
    node = HoldCarriedEmbargoNode(case, _CASE_ID)

    result = _run(dl, node)

    assert result.status == Status.FAILURE
    assert "EMB-18-003" in node.feedback_message


@pytest.mark.spec("EMB-18-003")
def test_the_check_refuses_a_case_naming_an_unheld_embargo(dl):
    case = as_VulnerabilityCase(
        attributed_to=CASE_OWNER_ID,
        id_=_CASE_ID,
        name="snapshot",
        embargo_register=register(active=f"{_CASE_ID}/embargo_events/unheld"),
    )
    node = CheckCarriedEmbargoNode(case, _CASE_ID)

    result = _run(dl, node)

    assert result.status == Status.FAILURE
    assert "EMB-18-003" in node.feedback_message


@pytest.mark.spec("CLP-10-006")
def test_the_check_admits_an_inline_embargo_and_stores_nothing(dl):
    """The guard half writes nothing; the hold is the effect's (#5395)."""
    embargo = EmbargoEvent(
        id_=f"{_CASE_ID}/embargo_events/inline",
        context=_CASE_ID,
        end_time=days_from_now_utc(45),
    )
    case = as_VulnerabilityCase(
        attributed_to=CASE_OWNER_ID,
        id_=_CASE_ID,
        name="snapshot",
        embargo_register=register(active=embargo),
    )

    result = _run(dl, CheckCarriedEmbargoNode(case, _CASE_ID))

    assert result.status == Status.SUCCESS
    assert dl.read(embargo.id_) is None


def test_a_case_naming_no_embargo_passes(dl):
    case = as_VulnerabilityCase(
        attributed_to=CASE_OWNER_ID, id_=_CASE_ID, name="snapshot"
    )

    result = _run(dl, HoldCarriedEmbargoNode(case, _CASE_ID))

    assert result.status == Status.SUCCESS


def _node_types(tree: py_trees.behaviour.Behaviour) -> list[type]:
    return [type(n) for n in tree.iterate()]


def test_engage_tree_checks_the_snapshot_embargo_then_holds_it_after_commit():
    """An Engage's carried case yields its embargo, never its records.

    The embargo is checked among the guards, which write nothing, and held
    only by the CASE_MANAGER's effects, after the act's commit (CLP-10-006,
    CLP-10-010).  The CASE_MANAGER already holds every record the snapshot
    names, and a participant's view of them is no entry a replica can copy
    (CLP-07-013, CM-23-016).
    """
    case = as_VulnerabilityCase(
        attributed_to=CASE_OWNER_ID, id_=_CASE_ID, name="snapshot"
    )

    with_case = create_engage_case_tree(
        _CASE_ID,
        _SENDER,
        case_obj=case,
        sender_rule=EngageCaseReceivedUseCase.sender_entitlement,
    )
    without = create_engage_case_tree(
        _CASE_ID,
        _SENDER,
        sender_rule=EngageCaseReceivedUseCase.sender_entitlement,
    )

    stages = received_stages(with_case)
    guards = next(s for s in stages if isinstance(s, PreconditionGuardStage))
    gate = next(
        s
        for s in stages
        if isinstance(s, CaseManagerGate)
        and s.name == "EngageEffectsIfCaseManager"
    )
    assert CheckCarriedEmbargoNode in _node_types(guards)
    assert HoldCarriedEmbargoNode not in _node_types(guards)
    assert HoldCarriedEmbargoNode in _node_types(gate)
    assert StoreEmbeddedParticipantsNode not in _node_types(with_case)
    for cls in (
        CheckCarriedEmbargoNode,
        HoldCarriedEmbargoNode,
        StoreEmbeddedParticipantsNode,
    ):
        assert cls not in _node_types(without)
