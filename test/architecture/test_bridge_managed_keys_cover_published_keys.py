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

"""Every key a tree node publishes is one ``execute_with_setup`` restores.

BT-17-020.  ``Blackboard.storage`` is process-global, so a key a node
publishes outlives the run that wrote it unless ``BTBridge`` restores it
(BT-17-007, BT-17-013).  A later act whose writer does not tick then reads
the earlier act's value: PR #6770 found ``/refused_entry`` and
``/announce_id`` published and not restored, and nothing tied the node to
the list (#6771).

A node publishes a key in two ways, and the scans read both:

- An output port bound to an absolute key through the ports hooks
  (``PortRemappingHooks``, BTND-03-019).  The class scan reads every node
  class's ``_domain_port_remappings()``; the tree scan reads the bindings
  of every node of every built received tree (``_received_tree_builds``),
  which adds what ``_instance_port_remappings()`` computes.
- ``published_act_keys()`` of a :class:`PublishesActKeys` node.  An
  :class:`ActKeyScope` restores the keys it seeds when its child's tick
  ends, on every outcome, so a key it publishes needs no bridge entry; any
  other node publishing that key still does.

The scans share the act-key vocabulary ratchet's helpers: it already
fails on a ports node that binds a port outside the hooks, and on a class
with an instance hook that no received tree builds unless it is listed
(``_INSTANCE_HOOKS_OUTSIDE_RECEIVED_TREES``).  Each class it lists must
have a publish-side reason here too.

A published key is covered when ``managed_keys`` names it, when the inbox
pipeline restores it (``ALL_INBOX_KEYS``, IO-02-001), when its name carries
the act's object id (a scoped handoff, BTND-03-004), or when
:data:`_NOT_RESTORED` lists it with the reason no later run can read its
value.  Anything else fails: add it to ``managed_keys``, or list it here
with the audit that shows a writer of the same run precedes every reader.

A key a call-out seam writes (``SynchronousCallOut``, ADR-0183) is no port
binding, and is not read here.
"""

from collections.abc import Iterable

import py_trees
import pytest
from py_trees.ports import PortInformation

from test.architecture._received_tree_builds import built_received_trees
from test.architecture.test_act_key_vocabulary import (
    _INSTANCE_HOOKS_OUTSIDE_RECEIVED_TREES,
    _node_classes,
    _scoped_handoff,
)
from test.architecture.test_bridge_managed_keys_cover_setup_writes import (
    _bridge_tree,
    _function,
    _managed_keys,
)
from vultron.core.behaviors.act_inputs import (
    PublishesActKeys,
    act_key_bindings,
)
from vultron.core.behaviors.act_key_scope import ActKeyScope
from vultron.core.behaviors.act_keys import SENDER_ID
from vultron.core.behaviors.helpers.ports_base import (
    DataLayerActionWithPorts,
)
from vultron.core.behaviors.inbox.nodes.pipeline import ALL_INBOX_KEYS

_FIRST = (
    "a writer of the same run ticks, and writes the key or a None sentinel,"
    " before any reader on every path, and no nested run sits between them"
)

#: Published keys ``execute_with_setup`` deliberately does not restore,
#: each with the audit that shows no reader can see an earlier run's value.
#: Adding a reader that a writer does not precede on every path means
#: moving the key to ``managed_keys``.
_NOT_RESTORED: dict[str, str] = {
    "/activity_ids": (
        f"{_FIRST}: ConstructActivitiesNode (None on its failure arms) ->"
        " QueueToOutboxNode, its next sibling in the send tree and the"
        " embargo proposal and termination trees"
    ),
    "/tail_hash": (
        f"{_FIRST}: ReconstructChainTailNode -> CreateLogEntryNode in the"
        " commit tree, and CheckHashMatchesNode, BufferOutOfOrderEntryNode"
        " and SendRejectLogEntryNode in the announce tree.  The one reader"
        " that runs after the writer fails, the genesis-reject arm of"
        " ReconstructOrRejectOnMissingCase, reads the '' sentinel the writer"
        " stores before it fails on the pre-genesis path"
    ),
    "/tail_index": f"{_FIRST}: as /tail_hash, with the -1 sentinel",
    "/log_entry": (
        f"{_FIRST}: CreateLogEntryNode (both arms write it) ->"
        " PersistLogEntryNode and FanOutLogEntryNode, its later siblings in"
        " the commit tree.  A tree that runs FanOutLogEntryNode with no"
        " CreateLogEntryNode before it passes the key as context_data, which"
        " the bridge restores"
    ),
    "/log_entry_preexisting": f"{_FIRST}: as /log_entry",
    "/invitee_case": (
        f"{_FIRST}: CheckInviteeNotAlreadyParticipantNode (None on its"
        " duplicate arm), a precondition guard of the accept-invite tree ->"
        " _CheckEmbargoActiveStateNode and _SignEmbargoConsentLeafNode,"
        " manager effects that run only after every guard has passed"
    ),
    "/admission_record_was_prior": (
        f"{_FIRST}: RecordProposalAdmissionNode (both SUCCESS arms write it)"
        " -> LoadExistingCaseNode, right after it in the same ActTransaction"
        " of the case-proposal tree"
    ),
    "/activity_id": (
        f"{_FIRST}: _BuildCreateCaseActivityNode -> UpdateActorOutbox, its"
        " next sibling in the create-case trigger tree; the other writer,"
        " CreateCaseActivity, is in no tree"
    ),
    "/participant": (
        "no node reads /participant; LookupParticipantNode publishes it, and"
        " FindParticipantByActorIdNode by default"
    ),
    "/ledger_position/case_id": (
        f"{_FIRST}: the ledger-position stage's FindCaseActorNode writes this"
        " scoped copy -> ReplayMissingEntriesNode, its next sibling in that"
        " stage.  It is kept off /case_id so the act's own nodes never read"
        " it"
    ),
    "/ledger_position/case_actor_id": (
        f"{_FIRST}: as /ledger_position/case_id"
    ),
}

#: The publish-side reason for each class the vocabulary ratchet lists as
#: having an instance hook that no built received tree holds, so the tree
#: scan never reads what it publishes.
_PUBLISHERS_OUTSIDE_RECEIVED_TREES: dict[str, str] = {
    "vultron.core.behaviors.helpers.object_nodes.ReadObject": (
        "publishes object_data to the key its caller names, and no tree"
        " builds it"
    ),
    "vultron.core.behaviors.helpers.object_nodes.UpdateObject": (
        "publishes object_data to an object-id-scoped handoff key"
        " (/object_<id segment>), and no tree builds it"
    ),
    "vultron.core.behaviors.helpers.participant_lookup."
    "FindParticipantByActorIdNode": (
        "publishes the participant port to its caller's participant_key:"
        " /participant (listed in _NOT_RESTORED) or /sender_participant,"
        " which SenderIsParticipantNode publishes and no node reads"
    ),
}

#: Where a key comes from, and whether that publisher restores it itself.
_Site = tuple[str, bool]


def _bare(key: str) -> str:
    return key.removeprefix("/")


def _class_publications(classes: Iterable[type]) -> dict[str, list[_Site]]:
    """Each absolute key a class binds an output port to, with the classes."""
    found: dict[str, list[_Site]] = {}
    for cls in classes:
        remaps = getattr(cls, "_domain_port_remappings", None)
        if not callable(remaps):
            continue
        outputs = getattr(cls, "OUTPUT_PORTS", {})
        for port, target in remaps().items():
            if (
                port in outputs
                and isinstance(target, str)
                and target.startswith("/")
            ):
                site = f"{cls.__module__}.{cls.__qualname__}.{port}"
                found.setdefault(target, []).append((site, False))
    return found


def _tree_publications(
    roots: Iterable[py_trees.behaviour.Behaviour],
) -> dict[str, list[_Site]]:
    """Each key a node of a built tree publishes, with the nodes.

    A site is marked self-restoring when the node is an
    :class:`ActKeyScope`, which puts back every key it seeds.
    """
    found: dict[str, list[_Site]] = {}
    for root in roots:
        for node in root.iterate():
            where = f"{type(node).__qualname__} in {root.name}"
            outputs = getattr(type(node), "OUTPUT_PORTS", {})
            for port, target in act_key_bindings(node).items():
                if port in outputs:
                    found.setdefault(target, []).append(
                        (f"{where}.{port}", False)
                    )
            if isinstance(node, PublishesActKeys):
                restores = isinstance(node, ActKeyScope)
                for key in node.published_act_keys():
                    found.setdefault(key.path, []).append((where, restores))
    return found


def _bridge_managed() -> set[str]:
    return _managed_keys(_function(_bridge_tree(), "execute_with_setup"))


def _covered(key: str, managed: set[str]) -> bool:
    return (
        _bare(key) in managed
        or _bare(key) in ALL_INBOX_KEYS
        or key in _NOT_RESTORED
        or _scoped_handoff(key)
    )


def _unrestored(
    publications: dict[str, list[_Site]], managed: set[str]
) -> list[str]:
    """Every publishing site whose key nothing restores, as ``site -> key``."""
    return sorted(
        f"{site} -> {key}"
        for key, sites in publications.items()
        if not _covered(key, managed)
        for site, restores in sites
        if not restores
    )


_FAILURE = (
    "These nodes publish a blackboard key that BTBridge.execute_with_setup"
    " does not restore, so its value outlives the run that wrote it and a"
    " later act can read it (BT-17-020).  Add the key to managed_keys in"
    " vultron/core/behaviors/bridge/bt_bridge.py, or list it in"
    " _NOT_RESTORED with the audit that shows no reader can see an earlier"
    " run's value:\n  "
)


class _PublishesUnmanagedKey(DataLayerActionWithPorts, register=False):
    """A node publishing a key the bridge does not restore."""

    OUTPUT_PORTS = {
        **DataLayerActionWithPorts.OUTPUT_PORTS,
        "widget_id": PortInformation(data_type=str),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"widget_id": "/widget_id"}


class _PublishesManagedKey(DataLayerActionWithPorts, register=False):
    """A node publishing a key the bridge restores."""

    OUTPUT_PORTS = {
        **DataLayerActionWithPorts.OUTPUT_PORTS,
        "found_case": PortInformation(data_type=str),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"found_case": "/case_id"}


class _PublishesSender(DataLayerActionWithPorts, register=False):
    """A node publishing a key that a scope also seeds."""

    OUTPUT_PORTS = {
        **DataLayerActionWithPorts.OUTPUT_PORTS,
        "sender": PortInformation(data_type=str),
    }

    @classmethod
    def _domain_port_remappings(cls) -> dict[str, str]:
        return {"sender": SENDER_ID.path}


@pytest.mark.spec("BT-17-020")
def test_the_scans_find_the_publications_they_check() -> None:
    """Guards the ratchet against passing vacuously."""
    managed = _bridge_managed()
    assert {"case_id", "refused_entry", "announce_id"} <= managed
    by_class = _class_publications(_node_classes())
    assert "/case_id" in by_class
    assert len(by_class) > 20
    by_tree = _tree_publications(built_received_trees().values())
    assert "/case_id" in by_tree
    scoped = {
        key
        for key, sites in by_tree.items()
        if any(restores for _, restores in sites)
    }
    assert SENDER_ID.path in scoped  # the tree scan reads the scopes


@pytest.mark.spec("BT-17-020")
def test_every_key_a_node_class_publishes_is_restored() -> None:
    unrestored = _unrestored(
        _class_publications(_node_classes()), _bridge_managed()
    )
    assert unrestored == [], _FAILURE + "\n  ".join(unrestored)


@pytest.mark.spec("BT-17-020")
def test_every_key_a_built_received_tree_publishes_is_restored() -> None:
    unrestored = _unrestored(
        _tree_publications(built_received_trees().values()),
        _bridge_managed(),
    )
    assert unrestored == [], _FAILURE + "\n  ".join(unrestored)


@pytest.mark.spec("BT-17-020")
def test_a_class_publishing_an_unrestored_key_fails_the_check() -> None:
    publications = _class_publications(
        [_PublishesUnmanagedKey, _PublishesManagedKey]
    )
    assert _unrestored(publications, _bridge_managed()) == [
        f"{__name__}.{_PublishesUnmanagedKey.__qualname__}.widget_id"
        " -> /widget_id"
    ]


@pytest.mark.spec("BT-17-020")
def test_a_built_node_publishing_an_unrestored_key_fails_the_check() -> None:
    probe = py_trees.composites.Sequence(name="ProbeBT", memory=True)
    probe.add_child(_PublishesUnmanagedKey(name="Publishes"))
    probe.add_child(_PublishesManagedKey(name="Finds"))
    assert _unrestored(_tree_publications([probe]), _bridge_managed()) == [
        "_PublishesUnmanagedKey in ProbeBT.widget_id -> /widget_id"
    ]


@pytest.mark.spec("BT-17-020")
def test_a_key_only_a_scope_publishes_needs_no_bridge_entry() -> None:
    """The scope restores what it seeds; a node publishing the same key
    still needs the bridge."""
    managed = _bridge_managed()
    assert SENDER_ID.name not in managed
    probe = py_trees.composites.Sequence(name="ProbeBT", memory=True)
    probe.add_child(
        ActKeyScope(_PublishesManagedKey(name="Finds"), {SENDER_ID: "x"})
    )
    assert _unrestored(_tree_publications([probe]), managed) == []

    probe.add_child(_PublishesSender(name="Sends"))
    assert _unrestored(_tree_publications([probe]), managed) == [
        f"_PublishesSender in ProbeBT.sender -> {SENDER_ID.path}"
    ]


@pytest.mark.spec("BT-17-020")
def test_every_listed_key_is_still_published_and_not_restored() -> None:
    """The exemption list only shrinks: a key no node publishes, or one the
    bridge now restores, must leave it."""
    managed = _bridge_managed()
    published = {
        **_class_publications(_node_classes()),
        **_tree_publications(built_received_trees().values()),
    }
    stale = sorted(
        key
        for key in _NOT_RESTORED
        if key not in published or _bare(key) in managed
    )
    assert stale == []
    assert all(reason.strip() for reason in _NOT_RESTORED.values())


@pytest.mark.spec("BT-17-020")
def test_every_publisher_the_tree_scan_misses_has_a_reason() -> None:
    assert set(_PUBLISHERS_OUTSIDE_RECEIVED_TREES) == set(
        _INSTANCE_HOOKS_OUTSIDE_RECEIVED_TREES
    ), (
        "_INSTANCE_HOOKS_OUTSIDE_RECEIVED_TREES in test_act_key_vocabulary.py"
        " changed: give each class it lists the reason here that what it"
        " publishes needs no managed_keys entry, or add the key to"
        " managed_keys"
    )
