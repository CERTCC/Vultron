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

"""Builders for participants, notes, statuses, faults and the unmatched."""

import json
from typing import Any, cast

from test.support.act_clock import ACT_AT
from test.support.received import received_event
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.outbox_sealed_body import (
    dump_outbound_body,
    read_sealed_body_dict,
)
from vultron.core.models._helpers import now_utc
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.dimensions import EmDimension, RmDimension
from vultron.core.models.events.base import MessageSemantics
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.models.pending_assertion import (
    get_pending_assertion_store,
    record_pending_assertion,
)
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.cs import CS_pxa
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.wire.as2.factories import (
    add_note_to_case_activity,
    add_participant_to_case_activity,
    add_status_to_case_activity,
    add_status_to_participant_activity,
    remove_participant_from_case_activity,
)
from vultron.wire.as2.parser import parse_activity
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Accept,
    as_Like,
    as_Remove,
)
from vultron.wire.as2.vocab.base.objects.object_types import as_Note

from .._ledger_network import (
    BYSTANDER,
    MANAGER,
    OWNER,
    LedgerNetwork,
)
from ..test_case_diverged_reseed import _diverged
from ..test_case_manager_note_replay import _set_rm
from ..test_participant_removal_planned import (
    CASE_ID as _REMOVAL_CASE_ID,
    MANAGER as _REMOVAL_MANAGER,
    OTHER as _REMOVAL_OTHER,
    OWNER as _REMOVAL_OWNER,
    VENDOR as _REMOVAL_VENDOR,
    _RemovalCase,
    _seed,
)
from . import Scenario, applied, no_tree, refused
from ._net import deliver
from .sync import at_replica

_BASE = "https://example.org/cases/rerun-sweep"


def _rm_declaration(net: LedgerNetwork, member: str, rm: RM) -> Scenario:
    participant = cast(
        CaseParticipant,
        net.stores[MANAGER].read(
            net.case(MANAGER).actor_participant_index[member]
        ),
    )
    status = ParticipantStatus(
        context=net.case_id, attributed_to=member, rm=RmDimension(state=rm)
    )
    return deliver(
        net,
        add_status_to_participant_activity(
            status, target=participant, actor=member, to=[MANAGER]
        ),
    )


@applied(MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT)
def add_participant_status() -> Scenario:
    """A participant reports the exploit public: committed and announced."""
    net = LedgerNetwork(f"{_BASE}/add-participant-status", em_state=EM.NONE)
    return deliver(net, net.pxa_report(OWNER, CS_pxa.pXa))


@refused(MessageSemantics.ADD_PARTICIPANT_STATUS_TO_PARTICIPANT)
def add_participant_status_regression() -> Scenario:
    """A backward RM step: refused, with a notice and the RSH-06-004 note."""
    net = LedgerNetwork(
        f"{_BASE}/add-participant-status-refused", em_state=EM.NONE
    )
    _set_rm(net, BYSTANDER, RM.ACCEPTED)
    return _rm_declaration(net, BYSTANDER, RM.VALID)


_UNMATCHED_RECEIVER = "https://example.org/users/rerun-sweep-receiver"


def _unmatched_store() -> SqliteDataLayer:
    return SqliteDataLayer("sqlite:///:memory:", actor_id=_UNMATCHED_RECEIVER)


def _dead_letters(dl: SqliteDataLayer) -> str | None:
    if dl.by_type("DeadLetterRecord"):
        return None
    return "no dead-letter record was stored"


@applied(MessageSemantics.UNKNOWN_UNRESOLVABLE_OBJECT)
def unresolvable_object() -> Scenario:
    """An Accept of an object nothing resolves: dead-lettered (SE-04-007)."""
    activity = as_Accept(
        actor="https://example.org/users/rerun-sweep-sender",
        to=[_UNMATCHED_RECEIVER],
        object_="urn:uuid:rerun-sweep-unresolvable",
    )
    return Scenario(
        dl=_unmatched_store(),
        event=received_event(activity, receiving_actor_id=_UNMATCHED_RECEIVER),
        reached=_dead_letters,
        disposition=HandlerDisposition.REFUSED,
    )


@no_tree(
    MessageSemantics.UNKNOWN,
    "an activity with no recognized semantics is refused in execute(),"
    " with nothing written, committed or sent",
)
def unknown() -> Scenario:
    """A ``Like`` of a note: no pattern matches it."""
    activity = as_Like(
        actor="https://example.org/users/rerun-sweep-sender",
        to=[_UNMATCHED_RECEIVER],
        object_=as_Note(
            id_="https://example.org/notes/rerun-sweep-liked", content="liked"
        ),
    )
    return Scenario(
        dl=_unmatched_store(),
        event=received_event(activity, receiving_actor_id=_UNMATCHED_RECEIVER),
    )


# ---------------------------------------------------------------------------
# Participants: the Case Owner's removal and reinstatement (CM-31)
# ---------------------------------------------------------------------------


def _removal_case() -> _RemovalCase:
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_REMOVAL_MANAGER)
    return _RemovalCase(dl=dl, case=_seed(dl))


def _at_removal_manager(case: _RemovalCase, activity: Any) -> Scenario:
    return Scenario(
        dl=case.dl,
        event=received_event(
            activity, at=case.dl, receiving_actor_id=_REMOVAL_MANAGER
        ),
    )


def _owner_moves(
    case: _RemovalCase, factory: Any, actor_id: str, *, tag: str
) -> Scenario:
    return _at_removal_manager(
        case,
        factory(
            case.participant(actor_id),
            target=_REMOVAL_CASE_ID,
            actor=_REMOVAL_OWNER,
            to=[_REMOVAL_MANAGER],
            id_=f"https://example.org/activities/rerun-sweep-{tag}",
        ),
    )


@applied(MessageSemantics.REMOVE_CASE_PARTICIPANT_FROM_CASE)
def remove_case_participant() -> Scenario:
    """The Case Owner removes a vendor: committed, announced and noticed."""
    return _owner_moves(
        _removal_case(),
        remove_participant_from_case_activity,
        _REMOVAL_VENDOR,
        tag="remove",
    )


@refused(MessageSemantics.REMOVE_CASE_PARTICIPANT_FROM_CASE)
def remove_case_owner() -> Scenario:
    """A removal naming the Case Owner: refused (CM-31-004), with a notice."""
    return _owner_moves(
        _removal_case(),
        remove_participant_from_case_activity,
        _REMOVAL_OWNER,
        tag="remove-refused",
    )


@applied(MessageSemantics.ADD_CASE_PARTICIPANT_TO_CASE)
def add_case_participant() -> Scenario:
    """The Case Owner reinstates a removed vendor (CM-31-011)."""
    case = _removal_case()
    removed = case.remove(_REMOVAL_VENDOR)
    assert removed.disposition is HandlerDisposition.APPLIED, removed.reason
    return _owner_moves(
        case, add_participant_to_case_activity, _REMOVAL_VENDOR, tag="add"
    )


@refused(MessageSemantics.ADD_CASE_PARTICIPANT_TO_CASE)
def add_case_participant_not_removed() -> Scenario:
    """An Add of a participant never removed: refused, with a notice."""
    return _owner_moves(
        _removal_case(),
        add_participant_to_case_activity,
        _REMOVAL_OTHER,
        tag="add-refused",
    )


# ---------------------------------------------------------------------------
# Notes (HP-08, CM-30)
# ---------------------------------------------------------------------------


def _note(net: LedgerNetwork, author: str, content: str) -> as_Note:
    return as_Note(
        id_=f"{author}/notes/rerun-sweep",
        content=content,
        attributed_to=author,
        context=net.case_id,
    )


def _note_activity(
    net: LedgerNetwork, author: str, content: str, *, tag: str
) -> Any:
    return add_note_to_case_activity(
        _note(net, author, content),
        target=net.case_id,
        actor=author,
        to=[MANAGER],
        id_=f"{author}/adds/rerun-sweep-{tag}",
    )


def _noted(slug: str) -> LedgerNetwork:
    """A network whose CASE_MANAGER has applied the bystander's note."""
    net = LedgerNetwork(f"{_BASE}/{slug}", em_state=EM.NONE)
    first = net.receive(
        MANAGER,
        json.loads(
            dump_outbound_body(
                _note_activity(net, BYSTANDER, "first", tag="1")
            )
        ),
    )
    assert first.disposition is HandlerDisposition.APPLIED, first.reason
    return net


@applied(MessageSemantics.ADD_NOTE_TO_CASE)
def add_note_to_case() -> Scenario:
    """A participant's note: committed and announced."""
    net = LedgerNetwork(f"{_BASE}/add-note", em_state=EM.NONE)
    return deliver(net, _note_activity(net, BYSTANDER, "a note", tag="1"))


@refused(MessageSemantics.ADD_NOTE_TO_CASE)
def add_note_conflicting() -> Scenario:
    """A second note under the first one's id: refused (HP-08-006)."""
    net = _noted("add-note-refused")
    return deliver(net, _note_activity(net, BYSTANDER, "different", tag="2"))


def _remove_note(net: LedgerNetwork, sender: str) -> Scenario:
    return deliver(
        net,
        as_Remove(
            actor=sender,
            object_=_note(net, BYSTANDER, "first"),
            target=net.case_id,
            to=[MANAGER],
        ),
    )


@applied(MessageSemantics.REMOVE_NOTE_FROM_CASE)
def remove_note_from_case() -> Scenario:
    """The note's author removes it: committed and announced (CM-30-001)."""
    return _remove_note(_noted("remove-note"), BYSTANDER)


# ---------------------------------------------------------------------------
# Case status (RSH-04-005)
# ---------------------------------------------------------------------------


def _replica_writes_nothing(dl: SqliteDataLayer) -> str | None:
    """The replica path of ``Add(CaseStatus)`` writes, commits and sends
    nothing: the replica takes the status from the ledger fan-out
    (RSH-04-005, RSH-08-003).  Its ``APPLIED`` verdict is the evidence the
    tree ran past its doors; there is no effect to repeat."""
    del dl
    return None


@applied(MessageSemantics.ADD_CASE_STATUS_TO_CASE)
def add_case_status_to_case() -> Scenario:
    """The CASE_MANAGER's Add(CaseStatus), at a participant's replica."""
    net = LedgerNetwork(f"{_BASE}/add-case-status", em_state=EM.NONE)
    status = CaseStatus(
        context=net.case_id,
        attributed_to=MANAGER,
        em=EmDimension(state=EM.NONE),
    )
    activity = add_status_to_case_activity(
        status, target=net.case_id, actor=MANAGER, to=[BYSTANDER]
    )
    return at_replica(
        net,
        json.loads(dump_outbound_body(activity)),
        BYSTANDER,
        reached=_replica_writes_nothing,
    )


# ---------------------------------------------------------------------------
# Faults and refusal notices
# ---------------------------------------------------------------------------


@applied(MessageSemantics.CREATE_PROCESSING_FAULT)
def create_processing_fault() -> Scenario:
    """A replica's case-diverged fault: the CASE_MANAGER re-seeds it."""
    net, _ = _diverged("rerun-sweep-processing-fault")
    (fault, *_) = net.processing_faults(BYSTANDER)
    return Scenario(
        dl=net.stores[MANAGER],
        event=received_event(
            parse_activity(net.delivered_body(fault, receiver=MANAGER)),
            as_sent=True,
            receiving_actor_id=MANAGER,
        ),
    )


def _assertion_cleared(case_id: str, refused_id: str) -> Any:
    def _reached(dl: SqliteDataLayer) -> str | None:
        del dl
        if get_pending_assertion_store(BYSTANDER).is_suppressed(
            case_id, "add_note_to_case", refused_id, at=now_utc()
        ):
            return "the refused note's pending assertion was not cleared"
        return None

    return _reached


@applied(MessageSemantics.REFUSAL_NOTICE)
def refusal_notice() -> Scenario:
    """The bystander reads the notice refusing its note: its ask is cleared."""
    net = _noted("refusal-notice")
    refused_add = _note_activity(net, BYSTANDER, "different", tag="2")
    record_pending_assertion(
        BYSTANDER, net.case_id, "add_note_to_case", refused_add.id_, at=ACT_AT
    )
    verdict = net.receive(MANAGER, json.loads(dump_outbound_body(refused_add)))
    assert verdict.disposition is HandlerDisposition.REFUSED, verdict.reason
    (notice, *_) = net.queued(MANAGER, to=BYSTANDER, type_="Reject")
    body = read_sealed_body_dict(net.stores[MANAGER], notice.id_)
    assert body is not None
    return at_replica(
        net,
        cast(dict[str, Any], body),
        BYSTANDER,
        reached=_assertion_cleared(net.case_id, refused_add.id_),
    )
