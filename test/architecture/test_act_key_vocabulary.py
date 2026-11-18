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
:data:`_NOT_PER_ACT`: keys that carry no per-act value, each with the
reason.

The bindings read are the class-level ones, ``_domain_port_remappings()``
(BTND-03-019); a binding an instance computes needs the instance, and the
runner's own check (``seed_act_inputs``) reads those on the built tree.

A key that is neither named nor listed is a decision: name it in the
vocabulary when its value varies with the act (BTND-01-008), or list it here
with the reason it does not.
"""

import importlib
import pkgutil
from collections.abc import Iterable

import pytest
from py_trees.ports import PortInformation, PortsMixin

import vultron.core.behaviors
import vultron.core.models.events
import vultron.core.use_cases.triggers.requests
from vultron.core.behaviors.act_inputs import seeding_declaration
from vultron.core.behaviors.act_keys import (
    ACT_KEYS,
    RUN_KEYS,
    vocabulary_key,
)
from vultron.core.behaviors.helpers.ports_base import (
    DataLayerConditionWithPorts,
)
from vultron.core.models.events.base import VultronEvent
from vultron.core.use_cases.triggers.requests import TriggerRequest
from vultron.subclasses import all_subclasses

_HANDOFF = (
    "an inter-node handoff: a node of the same tree publishes it for a later"
    " sibling (BTND-03-004)"
)
_INBOX = (
    "an inbox-pipeline key, placed and restored by the inbox pipeline"
    " (IO-02-001), not an input of a received or trigger tree"
)

#: Bound keys that carry no per-act value, with the reason.
_NOT_PER_ACT: dict[str, str] = {
    "/abandoned_proposals": _HANDOFF,
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
        for port, target in remaps().items():
            if port in inputs and target.startswith("/"):
                found.setdefault(target, []).append(
                    f"{cls.__module__}.{cls.__qualname__}.{port}"
                )
    return found


def _unnamed(classes: Iterable[type]) -> list[str]:
    """Every input binding to a key neither named nor listed."""
    return sorted(
        f"{site} -> {key}"
        for key, sites in _input_bindings(classes).items()
        if vocabulary_key(key) is None and key not in _NOT_PER_ACT
        for site in sites
    )


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
    class _ReadsUnnamedKey(DataLayerConditionWithPorts, register=False):
        INPUT_PORTS = {
            **DataLayerConditionWithPorts.INPUT_PORTS,
            "widget_id": PortInformation(data_type=str, required=True),
        }

        @classmethod
        def _domain_port_remappings(cls) -> dict[str, str]:
            return {"widget_id": "/widget_id"}

    assert _unnamed([_ReadsUnnamedKey]) == [
        f"{__name__}.{_ReadsUnnamedKey.__qualname__}.widget_id -> /widget_id"
    ]


@pytest.mark.spec("BTND-03-022")
def test_every_listed_key_is_still_bound_and_not_in_the_vocabulary() -> None:
    """The exemption list only shrinks: a key no port reads, or one the
    vocabulary now names, must leave it."""
    bindings = _input_bindings(_node_classes())
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


def _concrete(base: type[object]) -> list[type[object]]:
    """*base*'s subclasses, less pydantic's parametrised generic aliases."""
    found: list[type[object]] = list(all_subclasses(base))
    return [c for c in found if "[" not in c.__name__]


@pytest.mark.spec("BT-25-007")
def test_every_seeding_declaration_names_an_attribute_of_its_type() -> None:
    """One seeding declaration per received event and trigger request type,
    each naming attributes the type has."""
    _import_all(vultron.core.models.events)
    _import_all(vultron.core.use_cases.triggers.requests)
    types = [*_concrete(VultronEvent), *_concrete(TriggerRequest)]
    assert len(types) > 50
    missing = sorted(
        f"{t.__name__}: {key.path} <- {attribute}"
        for t in types
        for key, attribute in seeding_declaration(t).items()
        if attribute not in getattr(t, "model_fields", {})
        and not hasattr(t, attribute)
    )
    assert missing == []
