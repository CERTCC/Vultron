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

"""Every input port bound to a flat key reads a key the vocabulary names.

BTND-03-022: every blackboard key that carries a per-act value is named in
``vultron/core/behaviors/act_keys.py``, with its type and meaning.  This
ratchet reads the input ports of every node class under
``vultron/core/behaviors/`` and fails on any port bound to an absolute key
that the vocabulary does not name, unless the key is on
:data:`_NOT_PER_ACT`: keys that are no tree input, such as an intra-tree
handoff, each with the reason.

Two scans read the bindings, both through the ports hooks
(``PortRemappingHooks``, BTND-03-019), so a further test fails on a ports
node that binds a port outside them.  The class scan reads every node
class's ``_domain_port_remappings()``.  A binding an instance computes
(``_instance_port_remappings()``) needs the instance, so the tree scan reads
the nodes of every received tree, built once from its factory
(``_received_tree_builds``); a class with an instance hook that no received
tree builds is listed in :data:`_INSTANCE_HOOKS_OUTSIDE_RECEIVED_TREES` with
the reason.  A namespaced key (``/scope/key``) is not a flat key and is
skipped.

A key that is neither named nor listed is a decision: name it in the
vocabulary when its value varies with the act and a tree takes it as an
input (BTND-01-008), or list it here with the reason it is not one.
"""

import importlib
import inspect
import pkgutil
from collections.abc import Iterable, Mapping

import py_trees
import pytest
from py_trees.ports import PortInformation, PortsMixin

import vultron.core.behaviors
import vultron.core.models.events
import vultron.core.use_cases.triggers.requests
from test.architecture._act_seeding_table import SEEDING_TABLE
from test.architecture._received_tree_builds import built_received_trees
from vultron.core.behaviors.act_inputs import (
    act_key_bindings,
    seeding_declaration,
)
from vultron.core.behaviors.act_keys import (
    ACT_KEYS,
    CASE_ID,
    RUN_KEYS,
    SENDER_ID,
    vocabulary_key,
)
from vultron.core.behaviors.helpers.ports_base import (
    DataLayerConditionWithPorts,
    PortRemappingHooks,
)
from vultron.core.models.events.base import VultronEvent
from vultron.core.use_cases.triggers.requests import (
    CaseTriggerRequest,
    TriggerRequest,
)
from vultron.subclasses import all_subclasses

_HANDOFF = (
    "an intra-tree handoff: a node of the same tree publishes it for a later"
    " sibling (BTND-03-004), so it is never a tree input the runner seeds"
)
_UNWIRED = (
    "read by a CVE-id-assignment gate as state of an earlier run, but written"
    " by no node or runner today: not a declared tree input"
)
_INBOX = (
    "an inbox-pipeline key, placed and restored by the inbox pipeline"
    " (IO-02-001), not an input of a received or trigger tree"
)

#: Bound keys that are no tree input the vocabulary must name, with the
#: reason.
_NOT_PER_ACT: dict[str, str] = {
    "/abandoned_proposals": _HANDOFF,
    "/actor_roles": _UNWIRED,
    "/advisory_review_decision": _HANDOFF,
    "/publication_intent_decision": _HANDOFF,
    "/publication_intent_set": _UNWIRED,
    "/resolved_actor": _HANDOFF,
    "/accept_activity_id": _HANDOFF,
    "/activity_id": _HANDOFF,
    "/activity_ids": _HANDOFF,
    "/actor_default_embargo_duration": _HANDOFF,
    "/admission_record_was_prior": _HANDOFF,
    "/append_status_participant": _HANDOFF,
    "/append_status_status_obj": _HANDOFF,
    "/case_copy_replaces": _HANDOFF,
    "/create_case_activity_id": _HANDOFF,
    "/creation_time_revision_candidate": _HANDOFF,
    "/default_embargo": _HANDOFF,
    "/embargo_invite_recipients": _HANDOFF,
    "/excluded_actor_ids": _HANDOFF,
    "/fanout_recipients": _HANDOFF,
    "/fanout_withheld": _HANDOFF,
    "/initial_embargo_duration": _HANDOFF,
    "/invitee_case": _HANDOFF,
    "/invitee_vf_status_id": _HANDOFF,
    "/ledger_position_standing": _HANDOFF,
    "/log_entry": _HANDOFF,
    "/log_entry_preexisting": _HANDOFF,
    "/new_invite_participant": _HANDOFF,
    "/report_case_inputs": _HANDOFF,
    "/rm_transition_anomaly": _HANDOFF,
    "/tail_hash": _HANDOFF,
    "/tail_index": _HANDOFF,
    "/replay_case_id": (
        "a work-list value: the replay stage's scoped copy of the case it"
        " replays, kept off ``/case_id`` so the act's own nodes never read it"
    ),
    "/replay_case_ledger_entries": _HANDOFF,
    "/replay_from_index": _HANDOFF,
    "/replay_peer_id": (
        "a work-list value: the replay stage's scoped copy of the peer it"
        " replays to"
    ),
    "/inbox_activity": _INBOX,
    "/inbox_context_id": _INBOX,
    "/inbox_dereference": _INBOX,
    "/inbox_dispatch": _INBOX,
    "/inbox_event": _INBOX,
    "/inbox_ingress": _INBOX,
    "/inbox_payload": _INBOX,
    "/inbox_queue": _INBOX,
    "/inbox_replay": _INBOX,
}


#: Nouns of execution-scoped handoff keys, ``/{noun}_{id_segment}``
#: (BTND-03-004), whose physical name varies with the run, with the reason.
_SCOPED_HANDOFF_NOUNS: dict[str, str] = {
    "recorded_offer_answer": (
        "a handoff the recommendation answer's lookup node publishes for its"
        " later siblings, scoped by the answer's id"
    ),
    "suggested_roles": (
        "a handoff the recommendation's role reader publishes for the invite"
        " emitters, scoped by the recommendation's id"
    ),
}


def _scoped_handoff(key: str) -> bool:
    """Whether *key* is an execution-scoped handoff key of a listed noun."""
    return any(key.startswith(f"/{noun}_") for noun in _SCOPED_HANDOFF_NOUNS)


def _import_all(package: object) -> None:
    for info in pkgutil.walk_packages(
        package.__path__,  # type: ignore[attr-defined]
        f"{package.__name__}.",  # type: ignore[attr-defined]
    ):
        importlib.import_module(info.name)


def _node_classes() -> list[type]:
    _import_all(vultron.core.behaviors)
    root: type[object] = PortsMixin
    return sorted(
        (
            c
            for c in all_subclasses(root)
            if c.__module__.startswith("vultron.")
        ),
        key=lambda c: f"{c.__module__}.{c.__qualname__}",
    )


def _input_bindings(classes: Iterable[type]) -> dict[str, list[str]]:
    """Each absolute key an input port is bound to, with the classes."""
    found: dict[str, list[str]] = {}
    for cls in classes:
        remaps = getattr(cls, "_domain_port_remappings", None)
        if not callable(remaps):
            continue
        inputs = getattr(cls, "INPUT_PORTS", {})
        bound = remaps()
        if not isinstance(bound, Mapping):
            continue
        for port, target in bound.items():
            if (
                port in inputs
                and isinstance(target, str)
                and target.startswith("/")
            ):
                found.setdefault(target, []).append(
                    f"{cls.__module__}.{cls.__qualname__}.{port}"
                )
    return found


def _instance_input_bindings(
    roots: Iterable[py_trees.behaviour.Behaviour],
) -> dict[str, list[str]]:
    """Each flat key an input port of a built node is bound to."""
    found: dict[str, list[str]] = {}
    for root in roots:
        for node in root.iterate():
            inputs = getattr(type(node), "INPUT_PORTS", {})
            for port, target in act_key_bindings(node).items():
                if port in inputs and target.count("/") == 1:
                    found.setdefault(target, []).append(
                        f"{type(node).__qualname__}.{port} in {root.name}"
                    )
    return found


def _unnamed_in(bindings: dict[str, list[str]]) -> list[str]:
    """Every binding in *bindings* to a key neither named nor listed."""
    return sorted(
        f"{site} -> {key}"
        for key, sites in bindings.items()
        if vocabulary_key(key) is None
        and key not in _NOT_PER_ACT
        and not _scoped_handoff(key)
        for site in sites
    )


def _unnamed(classes: Iterable[type]) -> list[str]:
    """Every class-level input binding to a key neither named nor listed."""
    return _unnamed_in(_input_bindings(classes))


class _ReadsUnnamedKey(DataLayerConditionWithPorts, register=False):
    """A node reading a per-act key the vocabulary does not name."""

    INPUT_PORTS = {
        **DataLayerConditionWithPorts.INPUT_PORTS,
        "widget_id": PortInformation(data_type=str, required=True),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"widget_id": "/widget_id"}


@pytest.mark.spec("BTND-03-022")
def test_the_scan_finds_the_bindings_it_checks() -> None:
    """Guards the ratchet against passing vacuously."""
    bindings = _input_bindings(_node_classes())
    assert "/case_id" in bindings
    assert len(bindings) > 20


@pytest.mark.spec("BTND-03-022")
def test_every_bound_input_key_is_named_in_the_vocabulary() -> None:
    unnamed = _unnamed(_node_classes())
    assert unnamed == [], (
        "These input ports read a key the act-key vocabulary does not name."
        " Name the key in vultron/core/behaviors/act_keys.py when its value"
        " varies with the act (BTND-01-008), or list it in _NOT_PER_ACT with"
        " the reason it does not:\n  " + "\n  ".join(unnamed)
    )


@pytest.mark.spec("BTND-03-022")
def test_a_port_bound_to_an_unnamed_per_act_key_fails_the_check() -> None:
    assert _unnamed([_ReadsUnnamedKey]) == [
        f"{__name__}.{_ReadsUnnamedKey.__qualname__}.widget_id -> /widget_id"
    ]


@pytest.mark.spec("BTND-03-022")
def test_every_instance_bound_input_key_in_a_received_tree_is_named() -> None:
    bindings = _instance_input_bindings(built_received_trees().values())
    assert "/case_id" in bindings  # the scan reads built nodes
    # Each listed noun is still bound somewhere, so the list only shrinks.
    for noun in _SCOPED_HANDOFF_NOUNS:
        assert any(k.startswith(f"/{noun}_") for k in bindings), noun
    unnamed = _unnamed_in(bindings)
    assert unnamed == [], (
        "These built nodes read a key the act-key vocabulary does not name"
        " (BTND-03-022):\n  " + "\n  ".join(unnamed)
    )


@pytest.mark.spec("BTND-03-022")
def test_an_instance_binding_to_an_unnamed_key_fails_the_check() -> None:
    probe = py_trees.composites.Sequence(name="ProbeBT", memory=True)
    probe.add_child(_ReadsUnnamedKey(name="Reads"))
    assert _unnamed_in(_instance_input_bindings([probe])) == [
        "_ReadsUnnamedKey.widget_id in ProbeBT -> /widget_id"
    ]


@pytest.mark.spec("BTND-03-022")
def test_every_listed_key_is_still_bound_and_not_in_the_vocabulary() -> None:
    """The exemption list only shrinks: a key no port reads, or one the
    vocabulary now names, must leave it.  Both scans count as reading it."""
    bindings = {
        **_input_bindings(_node_classes()),
        **_instance_input_bindings(built_received_trees().values()),
    }
    stale = sorted(
        key
        for key in _NOT_PER_ACT
        if key not in bindings or vocabulary_key(key) is not None
    )
    assert stale == []


@pytest.mark.spec("BTND-03-022")
def test_every_vocabulary_key_states_its_type_and_meaning() -> None:
    assert ACT_KEYS.keys().isdisjoint(RUN_KEYS.keys())
    for key in (*ACT_KEYS.values(), *RUN_KEYS.values()):
        assert key.meaning.strip(), key.name
        assert key.value_type is not None, key.name
        assert key.path == f"/{key.name}"


#: Classes with their own instance hook that no built received tree holds,
#: so the tree scan never reads their instance bindings, with the reason.
_INSTANCE_HOOKS_OUTSIDE_RECEIVED_TREES: dict[str, str] = {
    "vultron.core.behaviors.helpers.object_nodes.ReadObject": (
        "the instance hook binds only the object_data output port"
    ),
    "vultron.core.behaviors.helpers.object_nodes.UpdateObject": (
        "the instance hook binds object_data to an object-id-scoped handoff"
        " key (/object_<id segment>), never a flat per-act key"
    ),
    "vultron.core.behaviors.helpers.participant_lookup."
    "FindParticipantByActorIdNode": (
        "the instance hook binds only the participant output port"
    ),
}


def _qualified(cls: type) -> str:
    return f"{cls.__module__}.{cls.__qualname__}"


def _bound_outside_hooks(classes: Iterable[type]) -> list[str]:
    """Every class in *classes* that binds a port outside the hooks."""

    def binds_in_setup(cls: type) -> bool:
        setup = vars(cls).get("setup")
        if setup is None:
            return False
        source = inspect.getsource(setup)
        return (
            "setup_ports(" in source
            and "bound_port_remappings()" not in source
        )

    return sorted(
        _qualified(cls)
        for cls in classes
        if not issubclass(cls, PortRemappingHooks) or binds_in_setup(cls)
    )


class _BindsInSetup(py_trees.ports.BehaviourWithPorts, register=False):
    """A ports node that wires its port in ``setup()``, not the hooks."""

    INPUT_PORTS = {"widget_id": PortInformation(data_type=str)}
    OUTPUT_PORTS: dict[str, PortInformation] = {}

    def setup(self, **kwargs: object) -> None:
        self.setup_ports(port_remappings={"widget_id": "/widget_id"})


class _HookedButBindsInSetup(DataLayerConditionWithPorts, register=False):
    """A hooked node whose own ``setup()`` still bypasses the hooks."""

    def setup(self, **kwargs: object) -> None:
        self.setup_ports(port_remappings={"datalayer": "/datalayer"})


@pytest.mark.spec("BTND-03-022")
def test_a_node_binding_outside_the_hooks_fails_the_check() -> None:
    assert _bound_outside_hooks(
        [_BindsInSetup, _HookedButBindsInSetup, DataLayerConditionWithPorts]
    ) == sorted(_qualified(c) for c in (_BindsInSetup, _HookedButBindsInSetup))


@pytest.mark.spec("BTND-03-022")
def test_every_ports_node_binds_its_ports_through_the_hooks() -> None:
    """Both scans and the BT-25-011 publisher check read the hooks
    (``bound_port_remappings``), never ``setup()``, so a ports node that
    binds a port anywhere else is invisible to all three."""
    outside = _bound_outside_hooks(_node_classes())
    assert outside == [], (
        "These ports nodes bind ports outside the PortRemappingHooks hooks;"
        " subclass a ports base (or BehaviourWithPortHooks) and move the"
        " bindings into _domain_port_remappings or _instance_port_remappings:"
        "\n  " + "\n  ".join(outside)
    )


@pytest.mark.spec("BTND-03-022")
def test_every_instance_hook_is_read_by_the_tree_scan_or_listed() -> None:
    built = {
        type(node)
        for root in built_received_trees().values()
        for node in root.iterate()
    }
    unread = sorted(
        _qualified(cls)
        for cls in _node_classes()
        if "_instance_port_remappings" in vars(cls)
        and not any(issubclass(b, cls) for b in built)
    )
    assert unread == sorted(_INSTANCE_HOOKS_OUTSIDE_RECEIVED_TREES), (
        "A class with an instance hook is neither built in a received tree"
        " nor listed in _INSTANCE_HOOKS_OUTSIDE_RECEIVED_TREES (or a listed"
        " one now is built, or is gone)"
    )


def _concrete(base: type[object]) -> list[type[object]]:
    """*base*'s project subclasses, less pydantic's parametrised aliases."""
    found: list[type[object]] = list(all_subclasses(base))
    return [
        c
        for c in found
        if "[" not in c.__name__ and c.__module__.startswith("vultron.")
    ]


def _act_types() -> list[type[object]]:
    _import_all(vultron.core.models.events)
    _import_all(vultron.core.use_cases.triggers.requests)
    return [*_concrete(VultronEvent), *_concrete(TriggerRequest)]


def _seeding_row(act_type: type) -> str:
    return " ".join(
        sorted(
            key.name if attribute == key.name else f"{key.name}<-{attribute}"
            for key, attribute in seeding_declaration(act_type).items()
        )
    )


@pytest.mark.spec("BT-25-007")
def test_every_seeding_declaration_matches_its_reviewed_row() -> None:
    """A seed matched by attribute name is a choice someone reviewed: a new
    property on an act, or a new vocabulary key, changes a row here."""
    types = _act_types()
    assert len(types) > 50
    rows = {t.__name__: _seeding_row(t) for t in types}
    assert len(rows) == len(types), "two act types share a name"
    changed = sorted(
        f"{name}: {rows.get(name)!r}, reviewed {SEEDING_TABLE.get(name)!r}"
        for name in rows.keys() | SEEDING_TABLE.keys()
        if rows.get(name) != SEEDING_TABLE.get(name)
    )
    assert changed == [], (
        "These seeding declarations differ from"
        " test/architecture/_act_seeding_table.py. Check that each attribute"
        " means what its key's meaning says, then update the row (or withhold"
        " the key with declare_seeds):\n  " + "\n  ".join(changed)
    )


@pytest.mark.spec("BT-25-007")
def test_every_event_seeds_its_sender_and_every_case_request_its_case() -> (
    None
):
    """The two seeds every act of a family carries, by type."""
    wrong = sorted(
        t.__name__
        for t in _act_types()
        if (
            issubclass(t, VultronEvent)
            and seeding_declaration(t).get(SENDER_ID) != "actor_id"
        )
        or (
            issubclass(t, CaseTriggerRequest)
            and seeding_declaration(t).get(CASE_ID) != "case_id"
        )
        or (
            issubclass(t, TriggerRequest)
            and "actor_id" in seeding_declaration(t).values()
        )
    )
    assert wrong == []
