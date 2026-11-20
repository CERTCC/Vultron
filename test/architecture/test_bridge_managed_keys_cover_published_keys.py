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

A node publishes a key in three ways, and the scans read each:

- An output port bound to an absolute key through the ports hooks
  (``PortRemappingHooks``, BTND-03-019).  The class scan reads every node
  class's ``_domain_port_remappings()``; the tree scan reads the bindings
  of every node of every built received tree (``_received_tree_builds``),
  which adds what ``_instance_port_remappings()`` computes.
- ``published_act_keys()`` of a :class:`PublishesActKeys` node.  An
  :class:`ActKeyScope` restores the keys it seeds when its child's tick
  ends, on every outcome, so a key it publishes needs no bridge entry; any
  other node publishing that key still does.
- A key a node registers to write on its own blackboard client.  A call-out
  seam (``SynchronousCallOut``, ADR-0183) writes its answer this way, and a
  later sibling reads it, so ``execute_with_setup`` restores every key
  ``call_out_written_keys()`` finds in the tree it runs.  A key the runner
  restores that way is covered; any other client write must be restored
  like a port binding.  The scans read clients as built and call no
  ``setup()``, so a key a node registers only in ``setup()`` is not seen;
  the seam registers its keys when it is built.  The tree scan reads the
  clients of every built received tree, and
  :func:`_call_out_contract_trees` holds one seam per capability
  declaration, so a contract no received tree builds is read too.

Both scans reuse the act-key vocabulary ratchet's walkers.  The tree scan
builds received trees only; a trigger tree, or a tree a node builds and
runs nested (the commit tree), is read through the class scan, which
reads every node class.  That leaves bindings an instance hook computes
outside the received trees, and the vocabulary ratchet already fails on a
class with an instance hook that no received tree builds unless it lists
it (``_INSTANCE_HOOKS_OUTSIDE_RECEIVED_TREES``).  Each class it lists must
have a publish-side reason here too.

A published key is covered when ``managed_keys`` names it, when its name
carries an act object's id (a scoped handoff, BTND-03-004, each noun with
the reason in :data:`_SCOPED_HANDOFF_REASONS`), or when
:data:`_NOT_RESTORED` lists it with the reason no later run can read its
value.  Anything else fails: add it to ``managed_keys``, or list it here
with the audit that shows a writer of the same run precedes every reader.
The inbox pipeline's nodes never run under the bridge; ``process_payload``
restores ``ALL_INBOX_KEYS``, and a separate test holds their
published keys to that list.
"""

import ast
from collections.abc import Iterable

import py_trees
import pytest
from py_trees.common import Access
from py_trees.ports import PortInformation

from test.architecture import _corpus
from test.architecture._received_tree_builds import built_received_trees
from test.architecture.test_act_key_vocabulary import (
    _INSTANCE_HOOKS_OUTSIDE_RECEIVED_TREES,
    _SCOPED_HANDOFF_NOUNS,
    _class_bindings,
    _instance_bindings,
    _node_classes,
    _scoped_handoff,
)
from test.architecture.test_bridge_managed_keys_cover_setup_writes import (
    _bridge_tree,
    _function,
    _managed_keys,
)
from vultron.core.behaviors.act_inputs import PublishesActKeys
from vultron.core.behaviors.act_key_scope import ActKeyScope
from vultron.core.behaviors.act_keys import SENDER_ID
from vultron.core.behaviors.call_out.answer import (
    CallOutAnswer,
    CallOutContract,
)
from vultron.core.behaviors.call_out.backend import CallOutBackend
from vultron.core.behaviors.call_out.capabilities import (
    capability_declarations,
)
from vultron.core.behaviors.call_out.guard import (
    SynchronousCallOut,
    call_out_written_keys,
)
from vultron.core.behaviors.call_out.nodes import always_succeed_as
from vultron.core.behaviors.helpers.ports_base import (
    DataLayerActionWithPorts,
)
from vultron.core.behaviors.inbox.nodes.pipeline import ALL_INBOX_KEYS

_FIRST = (
    "a writer of the same run ticks, and writes the key or a None sentinel,"
    " before any reader on every path, and no nested run between them"
    " writes the key"
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
        " stores before it fails on the pre-genesis path.  Its only other"
        " FAILURE, a missing datalayer, makes that arm raise before it sends,"
        " and an unresolvable case id raises"
    ),
    "/tail_index": f"{_FIRST}: as /tail_hash, with the -1 sentinel",
    "/log_entry": (
        f"{_FIRST}: CreateLogEntryNode (both arms write it) ->"
        " PersistLogEntryNode and FanOutLogEntryNode, its later siblings in"
        " the commit tree, the only tree that builds FanOutLogEntryNode"
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
        "no node reads it; the ledger-position stage's FindCaseActorNode"
        " writes this scoped copy, kept off /case_id so the act's own nodes"
        " never read it.  ReplayMissingEntriesNode, its next sibling, reads"
        " /case_id, which the stage's act-key scope seeds"
    ),
    "/ledger_position/case_actor_id": (
        f"{_FIRST}: the ledger-position stage's FindCaseActorNode (written"
        " only on its SUCCESS) -> SendMissingEntriesNode inside"
        " ReplayMissingEntriesNode, its next sibling in that stage"
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

#: The reason each scoped-handoff noun of the vocabulary ratchet
#: (``_SCOPED_HANDOFF_NOUNS``) needs no ``managed_keys`` entry: a key
#: ``/{noun}_{id segment}`` has a name no fixed list can hold.
_SCOPED_HANDOFF_REASONS: dict[str, str] = {
    "recorded_offer_answer": (
        "named for the answer's id, so another act's answer reads another"
        " key; RequireRecordedOfferAnswerNode, a precondition guard, writes"
        " it before any effect reads it and refuses the act when it cannot"
    ),
    "suggested_roles": (
        "named for the recommendation's id, so another recommendation reads"
        " another key; EvaluateDefaultRolesNode writes it, and its only"
        " reader, EmitOfferCaseParticipantToOwnerNode, is its next sibling in"
        " a Sequence that stops when the writer fails"
    ),
}

#: A publishing site, and whether that publisher restores the key itself.
_Site = tuple[str, bool]

_INBOX_MODULE = "vultron.core.behaviors.inbox."


def _bare(key: str) -> str:
    return key.removeprefix("/")


def _bridge_classes() -> list[type]:
    """The node classes of trees the bridge runs: all but the inbox's."""
    return [
        c
        for c in _node_classes()
        if not c.__module__.startswith(_INBOX_MODULE)
    ]


def _class_publications(classes: Iterable[type]) -> dict[str, list[_Site]]:
    """Each absolute key a class binds an output port to, with the classes."""
    return {
        key: [(site, False) for site in sites]
        for key, sites in _class_bindings(classes, "OUTPUT_PORTS").items()
    }


def _tree_publications(
    roots: Iterable[py_trees.behaviour.Behaviour],
) -> dict[str, list[_Site]]:
    """Each key a node of a built tree publishes, with the nodes.

    Output-port bindings come from the vocabulary ratchet's walker; the
    keys a :class:`PublishesActKeys` node names come from
    ``published_act_keys()``; and every key a node registers to write on
    its own blackboard client is read from the client.  A site is
    self-restoring when the node is an :class:`ActKeyScope`, which puts
    back every key it seeds, or when its client key is one the runner
    restores for every call-out seam of the tree (``call_out_written_keys``).
    """
    roots = list(roots)
    found: dict[str, list[_Site]] = {
        key: [(site, False) for site in sites]
        for key, sites in _instance_bindings(roots, "OUTPUT_PORTS").items()
    }
    for root in roots:
        by_seams = set(call_out_written_keys(root))
        for node in root.iterate():
            where = f"{type(node).__qualname__} in {root.name}"
            if isinstance(node, PublishesActKeys):
                restores = isinstance(node, ActKeyScope)
                for key in node.published_act_keys():
                    found.setdefault(key.path, []).append((where, restores))
            for path in _client_writes(node):
                site = (f"{where} (client)", _bare(path) in by_seams)
                found.setdefault(path, []).append(site)
    return found


def _client_writes(node: py_trees.behaviour.Behaviour) -> set[str]:
    """Every absolute key *node* registered to write on its own clients."""
    return {
        key
        for client in node.blackboards
        for key in (*client.write, *client.exclusive)
    }


def _call_out_contract_trees() -> list[py_trees.behaviour.Behaviour]:
    """One tree per capability declaration, holding its ceiling seam.

    Most call-outs sit in trigger trees, which the tree scan does not
    build; every contract is declared once, so a tree per declaration
    reads them all.
    """
    return [
        py_trees.composites.Sequence(
            name=declaration.__name__,
            memory=False,
            children=[
                SynchronousCallOut(
                    always_succeed_as(declaration)(declaration.__name__)
                )
            ],
        )
        for declaration in capability_declarations()
    ]


def _bridge_managed() -> set[str]:
    return _managed_keys(_function(_bridge_tree(), "execute_with_setup"))


def _covered(key: str, managed: set[str]) -> bool:
    return (
        _bare(key) in managed or key in _NOT_RESTORED or _scoped_handoff(key)
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


class _ProbeBackend(CallOutBackend):
    """A backend declaring one output and its refusal reason."""

    contract = CallOutContract(outputs={"widget_verdict": str})

    def answer(self) -> CallOutAnswer:
        return CallOutAnswer.yes({"widget_verdict": "yes"})


class _UnreportedSeam(SynchronousCallOut):
    """A seam that writes its contract but reports none of it."""

    def written_keys(self) -> tuple[str, ...]:
        return ()


class _SelfWritingBackend(_ProbeBackend):
    """A backend writing a key on its own client, which no seam reports."""

    def __init__(self, name: str = "") -> None:
        super().__init__(name)
        self._own = self.attach_blackboard_client(name="SelfWriting")
        self._own.register_key("widget_cache", Access.WRITE)


@pytest.mark.spec("BT-17-020")
def test_the_scans_find_the_publications_they_check() -> None:
    """Guards the ratchet against passing vacuously."""
    managed = _bridge_managed()
    assert {"case_id", "refused_entry", "announce_id"} <= managed
    by_class = _class_publications(_bridge_classes())
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
    # The tree scan reads the call-out seams' clients.
    assert {
        "/evaluate_case_proposal_verdict",
        "/report_validity_verdict",
        "/call_out_refusal_reason",
    } <= scoped
    by_contract = _tree_publications(_call_out_contract_trees())
    declared = {
        f"/{key}"
        for declaration in capability_declarations()
        for key in (
            *declaration.contract.outputs,
            *declaration.contract.refusal_ports,
        )
    }
    assert declared <= set(by_contract)
    assert len(declared) > 40


@pytest.mark.spec("BT-17-020")
def test_every_key_a_node_class_publishes_is_restored() -> None:
    unrestored = _unrestored(
        _class_publications(_bridge_classes()), _bridge_managed()
    )
    assert unrestored == [], _FAILURE + "\n  ".join(unrestored)


@pytest.mark.spec("BT-17-020")
def test_every_key_a_built_received_tree_publishes_is_restored() -> None:
    unrestored = _unrestored(
        _tree_publications(built_received_trees().values()),
        _bridge_managed(),
    )
    assert unrestored == [], _FAILURE + "\n  ".join(unrestored)


def _restores_call_out_keys(fn: ast.FunctionDef) -> bool:
    """Whether *fn* extends ``managed_keys`` with the seams' keys in time.

    The extension must read ``call_out_written_keys(tree)``, the tree the
    run executes, and come before ``snapshot_keys`` reads ``managed_keys``,
    or the snapshot would not hold the keys it restores.
    """
    extensions = [
        node.lineno
        for node in ast.walk(fn)
        if isinstance(node, ast.AugAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "managed_keys"
        and isinstance(node.value, ast.List)
        and any(
            isinstance(elt, ast.Starred)
            and isinstance(elt.value, ast.Call)
            and isinstance(elt.value.func, ast.Name)
            and elt.value.func.id == call_out_written_keys.__name__
            and [ast.dump(a) for a in elt.value.args]
            == [ast.dump(ast.Name(id="tree", ctx=ast.Load()))]
            for elt in node.value.elts
        )
    ]
    snapshots = [
        node.lineno
        for node in ast.walk(fn)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "snapshot_keys"
    ]
    return bool(extensions and snapshots) and max(extensions) < min(snapshots)


@pytest.mark.spec("BT-17-020")
def test_the_bridge_restores_every_seams_written_keys() -> None:
    """The coverage below counts a seam's keys as restored only because
    ``execute_with_setup`` adds them to ``managed_keys``."""
    assert _restores_call_out_keys(
        _function(_bridge_tree(), "execute_with_setup")
    ), (
        "execute_with_setup no longer extends managed_keys with"
        " call_out_written_keys(tree), so a call-out's answer outlives its"
        " run (BT-17-020)"
    )


_BRIDGE_SHAPES = {
    "restores": (
        "managed_keys += [*call_out_written_keys(tree)]\n"
        "snapshot_keys(storage, managed_keys)"
    ),
    "no extension": (
        "managed_keys += ['activity']\nsnapshot_keys(storage, managed_keys)"
    ),
    "another tree": (
        "managed_keys += [*call_out_written_keys(activity)]\n"
        "snapshot_keys(storage, managed_keys)"
    ),
    "after the snapshot": (
        "snapshot_keys(storage, managed_keys)\n"
        "managed_keys += [*call_out_written_keys(tree)]"
    ),
}


@pytest.mark.spec("BT-17-020")
@pytest.mark.parametrize("shape", list(_BRIDGE_SHAPES))
def test_a_bridge_that_does_not_restore_the_seams_keys_fails_the_check(
    shape: str,
) -> None:
    """The AST check passes only the shape that snapshots the seams' keys."""
    module = _corpus.parse_inline(
        "def execute_with_setup(tree, activity, storage, managed_keys):\n"
        + "".join(
            f"    {line}\n" for line in _BRIDGE_SHAPES[shape].split("\n")
        )
    )
    assert isinstance(module, ast.Module)
    fn = module.body[0]
    assert isinstance(fn, ast.FunctionDef)
    assert _restores_call_out_keys(fn) is (shape == "restores")


@pytest.mark.spec("BT-17-020")
def test_every_key_a_call_out_contract_writes_is_restored() -> None:
    """Every declared contract, built or not: ``call_out_written_keys``
    returns exactly the contract's outputs and refusal ports for a tree
    holding its seam, and the seam's client writes no other key.  That the
    bridge restores those keys is the AST check's half."""
    trees = _call_out_contract_trees()
    for tree, declaration in zip(
        trees, capability_declarations(), strict=True
    ):
        contract = declaration.contract
        assert call_out_written_keys(tree) == sorted(
            {*contract.outputs, *contract.refusal_ports}
        ), declaration.__name__
    unrestored = _unrestored(_tree_publications(trees), _bridge_managed())
    assert unrestored == [], _FAILURE + "\n  ".join(unrestored)


@pytest.mark.spec("BT-17-020")
def test_a_call_out_whose_written_keys_are_not_restored_fails_the_check() -> (
    None
):
    """The scan reads the seam's client, not what the seam reports."""
    reported = py_trees.composites.Sequence(
        name="ProbeBT",
        memory=False,
        children=[SynchronousCallOut(_ProbeBackend(name="Reported"))],
    )
    managed = _bridge_managed()
    assert _unrestored(_tree_publications([reported]), managed) == []

    unreported = py_trees.composites.Sequence(
        name="ProbeBT",
        memory=False,
        children=[_UnreportedSeam(_ProbeBackend(name="Unreported"))],
    )
    assert _unrestored(_tree_publications([unreported]), managed) == [
        "_UnreportedSeam in ProbeBT (client) -> /call_out_refusal_reason",
        "_UnreportedSeam in ProbeBT (client) -> /widget_verdict",
    ]


@pytest.mark.spec("BT-17-020")
def test_a_backend_writing_its_own_key_fails_the_check() -> None:
    probe = py_trees.composites.Sequence(
        name="ProbeBT",
        memory=False,
        children=[SynchronousCallOut(_SelfWritingBackend(name="Writes"))],
    )
    assert _unrestored(_tree_publications([probe]), _bridge_managed()) == [
        "_SelfWritingBackend in ProbeBT (client) -> /widget_cache"
    ]


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
        "_PublishesUnmanagedKey.widget_id in ProbeBT -> /widget_id"
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
        f"_PublishesSender.sender in ProbeBT -> {SENDER_ID.path}"
    ]


@pytest.mark.spec("BT-17-020")
def test_every_listed_key_is_still_published_and_not_restored() -> None:
    """No exemption goes stale: a key no node publishes any more, or one
    the bridge now restores, must leave the list."""
    managed = _bridge_managed()
    published = {
        **_class_publications(_bridge_classes()),
        **_tree_publications(built_received_trees().values()),
    }
    stale = sorted(
        key
        for key in _NOT_RESTORED
        if key not in published or _bare(key) in managed
    )
    assert stale == []
    for reasons in (
        _NOT_RESTORED,
        _PUBLISHERS_OUTSIDE_RECEIVED_TREES,
        _SCOPED_HANDOFF_REASONS,
    ):
        assert all(reason.strip() for reason in reasons.values())


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


@pytest.mark.spec("BT-17-020")
def test_every_scoped_handoff_noun_has_a_publish_side_reason() -> None:
    assert set(_SCOPED_HANDOFF_REASONS) == set(_SCOPED_HANDOFF_NOUNS)


def _unrestored_by_inbox(classes: Iterable[type]) -> list[str]:
    """Each inbox publishing site whose key ``ALL_INBOX_KEYS`` leaves out."""
    return sorted(
        f"{site} -> {key}"
        for key, sites in _class_bindings(classes, "OUTPUT_PORTS").items()
        if _bare(key) not in ALL_INBOX_KEYS
        for site in sites
    )


@pytest.mark.spec("BT-17-020")
def test_every_key_an_inbox_node_publishes_is_restored_by_the_pipeline() -> (
    None
):
    """The inbox pipeline, not the bridge, runs these nodes, and restores
    exactly ``ALL_INBOX_KEYS`` when ``process_payload`` returns."""
    inbox = [
        c for c in _node_classes() if c.__module__.startswith(_INBOX_MODULE)
    ]
    assert "/inbox_event" in _class_bindings(inbox, "OUTPUT_PORTS")
    unrestored = _unrestored_by_inbox(inbox)
    assert unrestored == [], (
        "These inbox nodes publish a key process_payload does not restore;"
        " add it to ALL_INBOX_KEYS:\n  " + "\n  ".join(unrestored)
    )


@pytest.mark.spec("BT-17-020")
def test_an_inbox_node_publishing_an_unrestored_key_fails_the_check() -> None:
    assert _unrestored_by_inbox([_PublishesUnmanagedKey]) == [
        f"{__name__}.{_PublishesUnmanagedKey.__qualname__}.widget_id"
        " -> /widget_id"
    ]
