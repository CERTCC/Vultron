"""Tests for the nodes that keep what a received case snapshot carries."""

import py_trees
import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.carried_snapshot import (
    HoldCarriedEmbargoNode,
    StoreEmbeddedParticipantsNode,
)
from vultron.core.behaviors.report.prioritize_tree import (
    create_engage_case_tree,
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
        id_=_CASE_ID, name="snapshot", case_participants=[participant]
    )

    result = _run(dl, StoreEmbeddedParticipantsNode(case, _CASE_ID))

    assert result.status == Status.SUCCESS
    assert dl.read(participant.id_) is not None


def test_a_case_naming_an_unheld_embargo_is_refused(dl):
    case = as_VulnerabilityCase(
        id_=_CASE_ID,
        name="snapshot",
        active_embargo=f"{_CASE_ID}/embargo_events/unheld",
    )
    node = HoldCarriedEmbargoNode(case, _CASE_ID)

    result = _run(dl, node)

    assert result.status == Status.FAILURE
    assert "EMB-18-003" in node.feedback_message


def test_a_case_naming_no_embargo_passes(dl):
    case = as_VulnerabilityCase(id_=_CASE_ID, name="snapshot")

    result = _run(dl, HoldCarriedEmbargoNode(case, _CASE_ID))

    assert result.status == Status.SUCCESS


def _node_types(tree: py_trees.behaviour.Behaviour) -> list[type]:
    return [type(n) for n in tree.iterate()]


def test_engage_tree_keeps_the_snapshot_only_when_one_arrived():
    case = as_VulnerabilityCase(id_=_CASE_ID, name="snapshot")

    with_case = create_engage_case_tree(_CASE_ID, _SENDER, case_obj=case)
    without = create_engage_case_tree(_CASE_ID, _SENDER)

    assert HoldCarriedEmbargoNode in _node_types(with_case)
    assert StoreEmbeddedParticipantsNode in _node_types(with_case)
    assert HoldCarriedEmbargoNode not in _node_types(without)
    assert StoreEmbeddedParticipantsNode not in _node_types(without)
