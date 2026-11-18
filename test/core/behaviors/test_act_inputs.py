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

"""A tree's declared per-act inputs, and the runners' seeding of them.

BT-25-006 (a tree declares its keys), BT-25-007 (both runners seed the
declared keys from the act before the first tick), BT-25-008 (a declared
key with no source raises with nothing ticked) and BT-25-011 (one source per
key per tree).
"""

from dataclasses import dataclass
from typing import Any
from unittest.mock import MagicMock

import py_trees
import pytest
from py_trees.common import Status
from py_trees.ports import PortInformation

from test.support.act_clock import ACT_AT
from test.support.act_runner import FixedClock, run_in_act
from test.support.objects import make
from test.support.received import (
    TEST_SENDER_POSITION,
    named_case,
    with_evidence,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.behaviors.act_inputs import (
    KeySource,
    declare_inputs,
    declare_seeds,
    published_act_keys,
    seed_act_inputs,
    seeding_declaration,
    tree_inputs,
)
from vultron.core.behaviors.act_keys import (
    CASE_ID,
    EMBARGO_ID,
    NOTE_ID,
    OBJECT_ID,
    REPORT_ID,
    SENDER_ID,
    ActKey,
)
from vultron.core.behaviors.case.received_run import run_received_tree
from vultron.core.behaviors.case_id_scope import with_case_id
from vultron.core.behaviors.helpers.ports_base import (
    DataLayerActionWithPorts,
    DataLayerConditionWithPorts,
)
from vultron.core.models.activity import VultronActivity
from vultron.core.models.events.note import AddNoteToCaseReceivedEvent
from vultron.core.models.note import VultronNote
from vultron.core.models.use_case_result import HandlerResult
from vultron.core.use_cases.triggers._base import SvcActivityTriggerBase
from vultron.core.use_cases.triggers.requests import EngageCaseTriggerRequest
from vultron.errors import VultronWiringError

_RECEIVER = "https://example.org/actors/receiver"
_SENDER = "https://example.org/actors/sender"
_CASE_ID = "https://example.org/cases/seeded"
_NOTE_ID = "https://example.org/notes/seeded"

_READ_KEYS = ("case_id", "note_id", "sender_id")


class _Probe(DataLayerConditionWithPorts, register=False):
    """Reads ``/case_id`` through its port, and records the seeded keys."""

    INPUT_PORTS = {
        **DataLayerConditionWithPorts.INPUT_PORTS,
        "case_id": PortInformation(data_type=str, required=True),
    }

    def __init__(self, name: str = "Probe") -> None:
        super().__init__(name=name)
        self.seen: dict[str, object] = {}
        self.ticks = 0

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"case_id": CASE_ID.path}

    def update(self) -> Status:
        self.ticks += 1
        self.seen["port case_id"] = self.get_input("case_id")
        storage = py_trees.blackboard.Blackboard.storage
        for key in _READ_KEYS:
            self.seen[key] = storage.get(f"/{key}")
        return Status.SUCCESS


class _PublishesCaseId(DataLayerActionWithPorts, register=False):
    """A lookup node that publishes ``/case_id`` (BT-25-009)."""

    OUTPUT_PORTS = {"case_id": PortInformation(data_type=str, required=True)}

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"case_id": CASE_ID.path}

    def update(self) -> Status:
        self._set_output("case_id", _CASE_ID)
        return Status.SUCCESS


def _sequence(
    *children: py_trees.behaviour.Behaviour,
) -> py_trees.behaviour.Behaviour:
    root = py_trees.composites.Sequence(name="SeededBT", memory=True)
    root.add_children(list(children))
    return root


def _note_event() -> AddNoteToCaseReceivedEvent:
    note = make(VultronNote, id_=_NOTE_ID, content="x", context=_CASE_ID)
    activity = make(
        VultronActivity,
        id_="https://example.org/activities/add-note-seeded",
        type_="Add",
        actor=_SENDER,
        object_=note,
        target=_CASE_ID,
        to=[_RECEIVER],
    )
    return with_evidence(
        AddNoteToCaseReceivedEvent(
            ledger_position=TEST_SENDER_POSITION,
            target=named_case(_CASE_ID),
            activity_id=activity.id_,
            actor_id=_SENDER,
            object_=note,
            activity=activity,
            receiving_actor_id=_RECEIVER,
        )
    )


def _run_received(
    tree: py_trees.behaviour.Behaviour, **context: Any
) -> HandlerResult:
    return run_received_tree(
        tree,
        dl=SqliteDataLayer("sqlite:///:memory:", actor_id=_RECEIVER),
        request=_note_event(),
        label="SeededBT",
        **context,
    )


# --- The declaration (BT-25-006) ---------------------------------------------


@pytest.mark.spec("BT-25-006")
def test_a_tree_carries_its_declaration_and_a_parent_collects_its_childrens():
    inner = declare_inputs(_Probe(), seeded=[CASE_ID])
    root = declare_inputs(_sequence(inner), seeded=[NOTE_ID])
    assert tree_inputs(root).sources == {
        CASE_ID: KeySource.SEEDED,
        NOTE_ID: KeySource.SEEDED,
    }
    assert tree_inputs(root).seeded == {CASE_ID, NOTE_ID}
    assert tree_inputs(root).published == frozenset()


@pytest.mark.spec("BT-25-006")
def test_an_undeclared_tree_needs_nothing_and_seeds_nothing():
    assert seed_act_inputs(_sequence(_Probe()), _note_event()) == {}


@pytest.mark.spec("BTND-03-022")
def test_a_key_outside_the_vocabulary_cannot_be_declared():
    stray = ActKey(name="case_id", value_type=str, meaning="a lookalike")
    with pytest.raises(TypeError, match="vocabulary"):
        declare_inputs(_Probe(), seeded=[stray])


@pytest.mark.spec("BT-25-011")
def test_one_key_cannot_be_declared_with_both_sources():
    with pytest.raises(VultronWiringError, match="/case_id"):
        declare_inputs(_Probe(), seeded=[CASE_ID], published=[CASE_ID])


@pytest.mark.spec("BT-25-011")
def test_two_subtrees_that_give_one_key_different_sources_conflict():
    root = _sequence(
        declare_inputs(_Probe("A"), seeded=[CASE_ID]),
        declare_inputs(_Probe("B"), published=[CASE_ID]),
    )
    with pytest.raises(VultronWiringError, match=r"/case_id.*BT-25-011"):
        tree_inputs(root)


# --- Which nodes publish a key -----------------------------------------------


def test_a_node_publishes_the_vocabulary_keys_its_output_ports_bind():
    assert published_act_keys(_PublishesCaseId(name="Lookup")) == {CASE_ID}
    assert published_act_keys(_Probe()) == frozenset()


def test_the_case_id_scope_counts_as_a_source_of_case_id():
    assert published_act_keys(with_case_id(_Probe(), _CASE_ID)) == {CASE_ID}


class _RelativeBinding:
    """A node whose output port is bound relative to its subtree namespace."""

    OUTPUT_PORTS = {"case_id": PortInformation(data_type=str)}

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"case_id": "case_id"}


def test_a_relative_binding_publishes_no_flat_key():
    assert published_act_keys(_RelativeBinding()) == frozenset()


# --- The seeding declaration (BT-25-007) -------------------------------------


@pytest.mark.spec("BT-25-007")
def test_a_received_event_seeds_its_same_named_attributes_and_its_sender():
    assert seeding_declaration(AddNoteToCaseReceivedEvent) == {
        CASE_ID: "case_id",
        NOTE_ID: "note_id",
        OBJECT_ID: "object_id",
        SENDER_ID: "actor_id",
    }


@pytest.mark.spec("BT-25-007")
def test_a_trigger_request_seeds_its_case_but_never_its_executing_actor():
    """``actor_id`` on a request is the executing actor, a run key."""
    assert seeding_declaration(EngageCaseTriggerRequest) == {
        CASE_ID: "case_id"
    }


@dataclass
class _Act:
    case_id: str | None = None


@pytest.mark.spec("BT-25-007")
def test_an_explicit_entry_renames_or_withholds_and_subclasses_inherit_it():
    # Types local to the test, so their entries reach no other test.
    @dataclass
    class _Renamed:
        case_id: str | None = None
        widget: str | None = None

    @dataclass
    class _Narrower(_Renamed):
        report_id: str | None = None

    declare_seeds(_Renamed, {REPORT_ID: "widget", CASE_ID: None})
    assert seeding_declaration(_Renamed) == {REPORT_ID: "widget"}
    # The subclass's same-named report_id loses to the inherited entry.
    assert seeding_declaration(_Narrower) == {REPORT_ID: "widget"}


def test_an_explicit_entry_must_name_an_attribute_of_the_type():
    with pytest.raises(ValueError, match="no attribute 'nothing'"):
        declare_seeds(_Act, {EMBARGO_ID: "nothing"})
    assert seeding_declaration(_Act) == {CASE_ID: "case_id"}


# --- seed_act_inputs (BT-25-008, BT-25-011) ----------------------------------


@pytest.mark.spec("BT-25-007")
def test_seeded_keys_are_read_off_the_act():
    tree = declare_inputs(_Probe(), seeded=[CASE_ID, NOTE_ID, SENDER_ID])
    assert seed_act_inputs(tree, _note_event()) == {
        "case_id": _CASE_ID,
        "note_id": _NOTE_ID,
        "sender_id": _SENDER,
    }


@pytest.mark.spec("BT-25-008")
def test_a_seeded_key_the_act_does_not_carry_raises_naming_it():
    tree = declare_inputs(_Probe(), seeded=[EMBARGO_ID])
    with pytest.raises(VultronWiringError, match=r"'/embargo_id'.*BT-25-008"):
        seed_act_inputs(tree, _note_event())


@pytest.mark.spec("BT-25-008")
def test_a_seeded_key_whose_attribute_is_empty_raises_naming_it():
    tree = declare_inputs(_Probe(), seeded=[CASE_ID])
    with pytest.raises(VultronWiringError, match="'/case_id' has no value"):
        seed_act_inputs(tree, _Act(case_id=None))


class _UnreadableAct:
    """An act whose ``case_id`` raises when read."""

    @property
    def case_id(self) -> str:
        raise ValueError("the activity names no case")


@pytest.mark.spec("BT-25-008")
def test_a_seeded_key_whose_attribute_raises_is_a_wiring_fault_naming_it():
    tree = declare_inputs(_Probe(), seeded=[CASE_ID])
    with pytest.raises(VultronWiringError, match="names no case") as raised:
        seed_act_inputs(tree, _UnreadableAct())
    assert "'/case_id' could not be read" in str(raised.value)


@pytest.mark.spec("BTND-03-022")
def test_a_seeded_value_of_the_wrong_type_raises_naming_the_key():
    tree = declare_inputs(_Probe(), seeded=[CASE_ID])
    with pytest.raises(VultronWiringError, match="'/case_id' got a int"):
        seed_act_inputs(tree, _Act(case_id=7))  # type: ignore[arg-type]


@pytest.mark.spec("BT-25-011")
def test_a_seeded_key_a_node_also_publishes_fails_the_one_source_check():
    tree = declare_inputs(
        _sequence(_PublishesCaseId(name="Lookup"), _Probe()),
        seeded=[CASE_ID],
    )
    with pytest.raises(VultronWiringError, match="also published by Lookup"):
        seed_act_inputs(tree, _note_event())


@pytest.mark.spec("BT-25-011")
def test_a_seeded_key_under_a_case_id_scope_fails_the_one_source_check():
    tree = declare_inputs(
        _sequence(with_case_id(_Probe(), _CASE_ID)), seeded=[CASE_ID]
    )
    with pytest.raises(VultronWiringError, match="BT-25-011"):
        seed_act_inputs(tree, _note_event())


@pytest.mark.spec("BT-25-011")
def test_a_published_key_with_one_publisher_needs_no_seed():
    tree = declare_inputs(
        _sequence(_PublishesCaseId(name="Lookup"), _Probe()),
        published=[CASE_ID],
    )
    assert seed_act_inputs(tree, _note_event()) == {}


@pytest.mark.spec("BT-25-008")
def test_a_published_key_no_node_publishes_raises_naming_it():
    tree = declare_inputs(_sequence(_Probe()), published=[CASE_ID])
    with pytest.raises(
        VultronWiringError, match="'/case_id' is published by no"
    ):
        seed_act_inputs(tree, _note_event())


@pytest.mark.spec("BT-25-011")
def test_a_published_key_two_nodes_publish_fails_the_one_source_check():
    tree = declare_inputs(
        _sequence(
            _PublishesCaseId(name="LookupA"),
            _PublishesCaseId(name="LookupB"),
        ),
        published=[CASE_ID],
    )
    with pytest.raises(VultronWiringError, match="2 nodes"):
        seed_act_inputs(tree, _note_event())


@pytest.mark.spec("BT-25-011")
def test_a_declared_key_the_caller_also_passes_fails_the_one_source_check():
    tree = declare_inputs(_Probe(), seeded=[CASE_ID])
    with pytest.raises(VultronWiringError, match="also passed by the caller"):
        seed_act_inputs(tree, _note_event(), context={"case_id": _CASE_ID})


# --- The received-tree runner ------------------------------------------------


@pytest.mark.spec("BT-25-007")
def test_the_received_runner_seeds_each_declared_key_from_the_event():
    probe = _Probe()
    verdict = _run_received(
        declare_inputs(_sequence(probe), seeded=[CASE_ID, NOTE_ID, SENDER_ID])
    )
    assert verdict == HandlerResult.applied()
    assert probe.seen == {
        "port case_id": _CASE_ID,
        "case_id": _CASE_ID,
        "note_id": _NOTE_ID,
        "sender_id": _SENDER,
    }


@pytest.mark.spec("BT-17-007")
def test_the_received_runner_restores_the_seeded_keys_after_the_run():
    storage = py_trees.blackboard.Blackboard.storage
    _run_received(
        declare_inputs(_sequence(_Probe()), seeded=[CASE_ID, NOTE_ID])
    )
    for key in ("case_id", "note_id"):
        assert key not in storage
        assert f"/{key}" not in storage


@pytest.mark.spec("BT-25-008")
def test_the_received_runner_raises_with_no_node_ticked_on_a_missing_key():
    probe = _Probe()
    with pytest.raises(VultronWiringError, match="'/report_id'"):
        _run_received(declare_inputs(_sequence(probe), seeded=[REPORT_ID]))
    assert probe.ticks == 0


@pytest.mark.spec("BT-25-011")
def test_the_received_runner_refuses_a_declared_key_passed_as_context():
    probe = _Probe()
    with pytest.raises(VultronWiringError, match="BT-25-011"):
        _run_received(
            declare_inputs(_sequence(probe), seeded=[CASE_ID]),
            case_id=_CASE_ID,
        )
    assert probe.ticks == 0


# --- The trigger-tree runner -------------------------------------------------


class _SeededTrigger(SvcActivityTriggerBase):
    """Builds a tree that declares its keys; takes no clock decision."""

    _takes_case_clock_decisions = False

    def __init__(
        self,
        request: EngageCaseTriggerRequest,
        tree: py_trees.behaviour.Behaviour,
        context: dict[str, object] | None = None,
    ) -> None:
        super().__init__(
            MagicMock(), request, MagicMock(), clock=FixedClock(ACT_AT)
        )
        self._tree = tree
        self._context = context or {}

    def _prepare(self) -> None:
        self._actor_id = _RECEIVER

    def _build_tree(self) -> py_trees.behaviour.Behaviour:
        return self._tree

    def _handle_result(self) -> None:
        return None

    def _extra_execute_kwargs(self) -> dict[str, object]:
        return dict(self._context)


def _engage() -> EngageCaseTriggerRequest:
    return EngageCaseTriggerRequest(actor_id=_RECEIVER, case_id=_CASE_ID)


@pytest.mark.spec("BT-25-007")
def test_the_trigger_runner_seeds_each_declared_key_from_the_request():
    probe = _Probe()
    run_in_act(
        _SeededTrigger(
            _engage(), declare_inputs(_sequence(probe), seeded=[CASE_ID])
        )
    )
    assert probe.seen["port case_id"] == _CASE_ID
    assert probe.seen["case_id"] == _CASE_ID


@pytest.mark.spec("BT-25-008")
def test_the_trigger_runner_raises_with_no_node_ticked_on_a_missing_key():
    probe = _Probe()
    trigger = _SeededTrigger(
        _engage(), declare_inputs(_sequence(probe), seeded=[REPORT_ID])
    )
    with pytest.raises(VultronWiringError, match="'/report_id'"):
        run_in_act(trigger)
    assert probe.ticks == 0


@pytest.mark.spec("BT-25-011")
def test_the_trigger_runner_refuses_a_declared_key_its_context_passes():
    probe = _Probe()
    trigger = _SeededTrigger(
        _engage(),
        declare_inputs(_sequence(probe), seeded=[CASE_ID]),
        context={"case_id": _CASE_ID},
    )
    with pytest.raises(VultronWiringError, match="also passed by the caller"):
        run_in_act(trigger)
    assert probe.ticks == 0
