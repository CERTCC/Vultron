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

"""Regression tests for ISSUE-2235 — per-dimension partial accept (RSH-05).

#2235: "Rejected status updates are dropped silently and all-or-nothing
(violates liberal-accept)."

An inbound ``Add(ParticipantStatus, CaseParticipant)`` carries a *snapshot* of
several independent state machines (``rm``, ``vfd``, ``em``, ``pxa``,
``consent``).  Before this fix, a single refused dimension — a regressive
``rm`` or a status for a participant already at terminal ``RM.CLOSED`` —
caused the receiving Case Actor to discard the entire snapshot and abort the
``AddParticipantStatusBT`` Sequence, which also killed the Seam 1 → Seam 2
emit (``EmitAddCaseStatusToSelfNode``) and therefore embargo teardown
(ADR-0046, RSH-01-003).

The fix accepts each dimension independently: refused dimensions carry
forward the participant's current value, accepted dimensions are recorded,
and the canonical ledger entry snapshots the *accepted* portion rather than
the raw assertion.  The refusal is visible in the canonical ledger (the
accepted portion differs from what was asserted); no new wire message is
emitted.

Per specs/received-status-handling.yaml RSH-05.
"""

from typing import Any, cast

import py_trees
import pytest
from py_trees.common import Status

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.status.add_participant_status_tree import (
    add_participant_status_tree,
)
from vultron.core.behaviors.sync.nodes.participant_status_effect import (
    ApplyParticipantStatusFromLedgerNode,
)
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import VultronCaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.behaviors.sync.nodes.chain import _to_persistable_entry
from vultron.core.models.events.sync import AnnounceLogEntryReceivedEvent
from vultron.core.states.cs import CS_pxa, CS_vfd
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.enums.roles import CVDRole
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import (
    add_status_to_participant_activity,
    announce_log_entry_activity,
)
from vultron.wire.as2.vocab.objects.case_ledger_entry import (
    as_CaseLedgerEntry as WireCaseLedgerEntry,
)
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.case_status import (
    as_CaseStatus,
    as_ParticipantStatus,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ACTOR_ID = "https://example.org/actors/vendor"
CASE_MANAGER_ID = "https://example.org/actors/case-actor"
CASE_ID = "https://example.org/cases/case-2235"
PARTICIPANT_ID = f"{CASE_ID}/participants/vendor"
CM_PARTICIPANT_ID = f"{CASE_ID}/participants/case-actor"
CURRENT_STATUS_ID = f"{PARTICIPANT_ID}/statuses/current"
ASSERTED_STATUS_ID = f"{PARTICIPANT_ID}/statuses/asserted"

_ZERO_HASH = "0" * 64


# ---------------------------------------------------------------------------
# Shape-agnostic accessors
#
# ``SqliteDataLayer.read`` returns *core* models (``rm``/``vfd`` dimension
# objects) while wire objects and wire-shaped ledger snapshots use the flat
# ``rmState``/``vfdState`` form.  These readers accept either and normalize to
# the enum *member name* (``"VALID"``, ``"VFd"``, ``"Pxa"``) — which is also
# what both serializations carry — so the assertions describe protocol state,
# not serialization shape.  Comparing enum members directly would not work for
# ``CS_vfd``/``CS_pxa``, whose ``.value`` is a ``NamedTuple`` rather than the
# string that appears on the wire.
# ---------------------------------------------------------------------------


def _state_name(value: Any) -> str | None:
    """Normalize an enum member or wire string to the member name."""
    if value is None:
        return None
    return getattr(value, "name", None) or str(value)


def _dim_state(obj: Any, core_field: str, flat_field: str) -> str | None:
    """Return a dimension's state name from a core or wire object/dict."""
    if isinstance(obj, dict):
        nested = obj.get(core_field)
        if isinstance(nested, dict):
            return _state_name(nested.get("state"))
        camel = flat_field[0] + flat_field.title().replace("_", "")[1:]
        return _state_name(obj.get(flat_field) or obj.get(camel))
    nested = getattr(obj, core_field, None)
    if nested is not None and hasattr(nested, "state"):
        return _state_name(nested.state)
    return _state_name(getattr(obj, flat_field, None))


def _rm_of(obj: Any) -> str | None:
    return _dim_state(obj, "rm", "rm_state")


def _vfd_of(obj: Any) -> str | None:
    return _dim_state(obj, "vfd", "vfd_state")


def _case_status_of(obj: Any) -> Any:
    if isinstance(obj, dict):
        return obj.get("case_status") or obj.get("caseStatus")
    return getattr(obj, "case_status", None)


def _pxa_of(obj: Any) -> str | None:
    cs = _case_status_of(obj)
    return None if cs is None else _dim_state(cs, "pxa", "pxa_state")


def _em_of(obj: Any) -> str | None:
    cs = _case_status_of(obj)
    return None if cs is None else _dim_state(cs, "em", "em_state")


def _latest_status(dl: SqliteDataLayer, participant_id: str) -> Any:
    participant = cast(CaseParticipant, dl.read(participant_id))
    assert participant is not None
    assert participant.participant_statuses
    return participant.participant_statuses[-1]


def _status_ids(dl: SqliteDataLayer, participant_id: str) -> list[str]:
    participant = cast(CaseParticipant, dl.read(participant_id))
    assert participant is not None
    return [
        str(getattr(s, "id_", s)) for s in participant.participant_statuses
    ]


def _ledger_entries(dl: SqliteDataLayer) -> list[VultronCaseLedgerEntry]:
    return [
        cast(VultronCaseLedgerEntry, obj)
        for obj in dl.list_objects("CaseLedgerEntry")
        if isinstance(obj, VultronCaseLedgerEntry)
        and cast(VultronCaseLedgerEntry, obj).case_id == CASE_ID
    ]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clear_blackboard():
    py_trees.blackboard.Blackboard.storage.clear()
    yield
    py_trees.blackboard.Blackboard.storage.clear()


@pytest.fixture
def dl():
    return SqliteDataLayer("sqlite:///:memory:")


def _current_status(
    rm_state: RM,
    vfd_state: CS_vfd,
    pxa_state: CS_pxa,
) -> as_ParticipantStatus:
    """The participant's status *before* the inbound assertion arrives."""
    return as_ParticipantStatus(
        id_=CURRENT_STATUS_ID,
        context=CASE_ID,
        rm_state=rm_state,
        vfd_state=vfd_state,
        case_status=as_CaseStatus(
            id_=f"{CURRENT_STATUS_ID}/cs",
            context=CASE_ID,
            em_state=EM.NONE,
            pxa_state=pxa_state,
        ),
    )


def _asserted_status(
    rm_state: RM,
    vfd_state: CS_vfd,
    pxa_state: CS_pxa,
) -> as_ParticipantStatus:
    """The inbound assertion from the sender."""
    return as_ParticipantStatus(
        id_=ASSERTED_STATUS_ID,
        context=CASE_ID,
        rm_state=rm_state,
        vfd_state=vfd_state,
        case_status=as_CaseStatus(
            id_=f"{ASSERTED_STATUS_ID}/cs",
            context=CASE_ID,
            em_state=EM.NONE,
            pxa_state=pxa_state,
        ),
    )


def _seed_case(
    dl: SqliteDataLayer,
    current: as_ParticipantStatus,
    asserted: as_ParticipantStatus | None,
) -> None:
    """Seed a two-participant case with *current* as the vendor's latest status."""
    vendor = as_CaseParticipant(
        id_=PARTICIPANT_ID,
        context=CASE_ID,
        attributed_to=ACTOR_ID,
        case_roles=[CVDRole.CASE_OWNER],
    )
    vendor.participant_statuses.append(current)
    manager = as_CaseParticipant(
        id_=CM_PARTICIPANT_ID,
        context=CASE_ID,
        attributed_to=CASE_MANAGER_ID,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    # attributed_to is what seeds the per-case genesis hash (CLP-08-003);
    # without it the ledger sits in the pre-genesis bootstrap window and the
    # guarded commit cannot anchor a chain.
    case = as_VulnerabilityCase(
        id_=CASE_ID,
        name="Issue 2235 Case",
        attributed_to=CASE_MANAGER_ID,
    )
    case.add_participant(vendor)
    case.add_participant(manager)

    dl.create(case)
    dl.create(vendor)
    dl.create(manager)
    dl.create(current)
    if asserted is not None:
        dl.create(asserted)


def _run_tree(
    dl: SqliteDataLayer,
    asserted: as_ParticipantStatus,
    executing_actor_id: str,
    make_payload: Any,
) -> Any:
    """Run the full ``add_participant_status_tree`` for *asserted*."""
    activity = add_status_to_participant_activity(
        status=asserted,
        target=as_CaseParticipant(
            id_=PARTICIPANT_ID, context=CASE_ID, attributed_to=ACTOR_ID
        ),
        actor=ACTOR_ID,
        context=as_VulnerabilityCase(id_=CASE_ID, name="Issue 2235 Case"),
    )
    event = make_payload(activity)
    bridge = BTBridge(
        datalayer=dl, trigger_activity=TriggerActivityAdapter(dl)
    )
    tree = add_participant_status_tree(request=event, case_id=CASE_ID)
    # Production passes the parsed event as ``activity`` (see
    # SvcAddParticipantStatusToParticipantReceivedUseCase); the guarded commit
    # needs it on the blackboard to build a payload snapshot.
    return bridge.execute_with_setup(
        tree=tree, actor_id=executing_actor_id, activity=event
    )


# ---------------------------------------------------------------------------
# A refused rm must not discard accepted vfd / pxa
# ---------------------------------------------------------------------------


class TestRefusedDimensionDoesNotDiscardAcceptedDimensions:
    """A regressive ``rm`` must not throw away the rest of the snapshot."""

    def test_regressive_rm_carried_forward_accepted_vfd_and_pxa_recorded(
        self, dl, make_payload
    ):
        """VALID + rm=RECEIVED (refused) + vfd=VFd + pxa=Pxa (both accepted).

        The status is appended with the participant's current ``rm`` carried
        forward and the two forward dimensions applied (RSH-05).
        """
        current = _current_status(RM.VALID, CS_vfd.Vfd, CS_pxa.pxa)
        asserted = _asserted_status(RM.RECEIVED, CS_vfd.VFd, CS_pxa.Pxa)
        _seed_case(dl, current, asserted)

        result = _run_tree(dl, asserted, ACTOR_ID, make_payload)
        assert result.status == Status.SUCCESS, (
            "a refused rm dimension must not abort the whole update"
            f" (feedback: {result.feedback_message})"
        )

        assert ASSERTED_STATUS_ID in _status_ids(dl, PARTICIPANT_ID)
        latest = _latest_status(dl, PARTICIPANT_ID)
        assert _rm_of(latest) == RM.VALID.name, "refused rm must carry forward"
        assert (
            _vfd_of(latest) == CS_vfd.VFd.name
        ), "accepted vfd must be recorded"
        assert (
            _pxa_of(latest) == CS_pxa.Pxa.name
        ), "accepted pxa must be recorded"
        assert (
            _em_of(latest) == EM.NONE.name
        ), "em is Seam 2's business (#2256)"

    def test_regressive_rm_still_reaches_seam_2_emit(self, dl, make_payload):
        """The Seam 1 → Seam 2 emit must survive a refused dimension.

        This is the concrete failure reported in #2235: aborting the Sequence
        at RM validation skipped ``EmitAddCaseStatusToSelfNode``, so embargo
        teardown in Seam 2 never ran (RSH-01-003, RSH-01-004).
        """
        current = _current_status(RM.VALID, CS_vfd.Vfd, CS_pxa.pxa)
        asserted = _asserted_status(RM.RECEIVED, CS_vfd.VFd, CS_pxa.Pxa)
        _seed_case(dl, current, asserted)

        result = _run_tree(dl, asserted, ACTOR_ID, make_payload)
        assert result.status == Status.SUCCESS

        outbox = dl.outbox_list_for_actor(ACTOR_ID)
        assert len(outbox) > 0, (
            "EmitAddCaseStatusToSelfNode must still queue Add(CaseStatus)"
            " when one dimension was refused"
        )


# ---------------------------------------------------------------------------
# The canonical ledger records the accepted portion
# ---------------------------------------------------------------------------


class TestCanonicalLedgerRecordsAcceptedPortion:
    """The refusal is made visible by what the canonical ledger records."""

    def test_ledger_snapshot_carries_accepted_rm_not_asserted_rm(
        self, dl, make_payload
    ):
        """Run as CASE_MANAGER so the guarded commit fires (CLP-10-006).

        The committed ``payload_snapshot['object']`` must describe the
        *accepted* status, not the sender's raw assertion — otherwise the
        refused value is replicated to every participant.
        """
        current = _current_status(RM.VALID, CS_vfd.Vfd, CS_pxa.pxa)
        asserted = _asserted_status(RM.RECEIVED, CS_vfd.VFd, CS_pxa.Pxa)
        _seed_case(dl, current, asserted)

        result = _run_tree(dl, asserted, CASE_MANAGER_ID, make_payload)
        assert result.status == Status.SUCCESS

        entries = _ledger_entries(dl)
        assert len(entries) == 1, "exactly one canonical entry expected"
        snapshot_object = entries[0].payload_snapshot.get("object")
        assert isinstance(snapshot_object, dict), (
            "the ledger snapshot must inline the status object,"
            f" got {snapshot_object!r}"
        )
        assert _rm_of(snapshot_object) == RM.VALID.name, (
            "ledger must record the accepted rm (VALID), not the refused"
            f" assertion — got {_rm_of(snapshot_object)!r}"
        )
        assert _vfd_of(snapshot_object) == CS_vfd.VFd.name
        assert _pxa_of(snapshot_object) == CS_pxa.Pxa.name


# ---------------------------------------------------------------------------
# Terminal RM.CLOSED
# ---------------------------------------------------------------------------


class TestTerminalClosedParticipant:
    """``RM.CLOSED`` freezes ``rm`` only — not the other dimensions."""

    def test_closed_participant_still_accepts_vfd_advance(
        self, dl, make_payload
    ):
        """A CLOSED vendor deploying its fix must still be recorded.

        ``rm`` stays CLOSED (terminal); ``vfd`` advances Vfd → VFd.
        """
        current = _current_status(RM.CLOSED, CS_vfd.Vfd, CS_pxa.pxa)
        asserted = _asserted_status(RM.CLOSED, CS_vfd.VFd, CS_pxa.pxa)
        _seed_case(dl, current, asserted)

        result = _run_tree(dl, asserted, ACTOR_ID, make_payload)
        assert result.status == Status.SUCCESS, (
            "a CLOSED participant may still report vfd/pxa progress"
            f" (feedback: {result.feedback_message})"
        )

        latest = _latest_status(dl, PARTICIPANT_ID)
        assert _rm_of(latest) == RM.CLOSED.name
        assert _vfd_of(latest) == CS_vfd.VFd.name

    def test_wholly_refused_update_is_not_appended_and_commits_no_entry(
        self, dl, make_payload
    ):
        """CLOSED + duplicate CLOSED with no other change → refused outright.

        Nothing is appended and no canonical ledger entry is committed: the
        assertion carried no acceptable information.  Executed as the Case
        Manager so a commit *would* fire if the guards let it through.
        """
        current = _current_status(RM.CLOSED, CS_vfd.Vfd, CS_pxa.pxa)
        asserted = _asserted_status(RM.CLOSED, CS_vfd.Vfd, CS_pxa.pxa)
        _seed_case(dl, current, asserted)

        result = _run_tree(dl, asserted, CASE_MANAGER_ID, make_payload)
        assert result.status == Status.FAILURE

        assert ASSERTED_STATUS_ID not in _status_ids(dl, PARTICIPANT_ID)
        assert _ledger_entries(dl) == []


# ---------------------------------------------------------------------------
# Ledger-apply path (replica side)
# ---------------------------------------------------------------------------


def _status_snapshot_entry(
    rm_state: str, vfd_state: str
) -> VultronCaseLedgerEntry:
    """A canonical ``add_participant_status_to_participant`` entry."""
    return _to_persistable_entry(
        HashChainLedgerRecord(
            case_id=CASE_ID,
            log_index=0,
            object_id="https://example.org/activities/add-status-2235",
            event_type="add_participant_status_to_participant",
            payload_snapshot={
                "object": {
                    "id": ASSERTED_STATUS_ID,
                    "type": "ParticipantStatus",
                    "context": CASE_ID,
                    "rmState": rm_state,
                    "vfdState": vfd_state,
                },
                "target": {"id": PARTICIPANT_ID},
            },
            prev_log_hash=_ZERO_HASH,
        )
    )


def _announce_event(
    entry: VultronCaseLedgerEntry,
) -> AnnounceLogEntryReceivedEvent:
    wire_entry = WireCaseLedgerEntry.model_validate(
        entry.model_dump(mode="json")
    )
    activity = announce_log_entry_activity(
        entry=wire_entry, actor=CASE_MANAGER_ID
    )
    return cast(AnnounceLogEntryReceivedEvent, extract_event(activity))


class TestLedgerApplyRmRatchet:
    """A replicated entry must not regress a replica's derived RM state."""

    def test_regressive_rm_in_ledger_entry_does_not_regress_replica(self, dl):
        """Replica at VALID; entry asserts RECEIVED + vfd=VFd.

        Monotonic visibility (see notes/sync-ledger-replication.md): the
        replica keeps ``rm`` at VALID while still applying the accepted
        ``vfd`` advance.
        """
        current = _current_status(RM.VALID, CS_vfd.Vfd, CS_pxa.pxa)
        _seed_case(dl, current, None)

        entry = _status_snapshot_entry(rm_state="RECEIVED", vfd_state="VFd")
        event = _announce_event(entry)

        bridge = BTBridge(datalayer=dl)
        result = bridge.execute_with_setup(
            tree=ApplyParticipantStatusFromLedgerNode(
                name="ApplyParticipantStatusFromLedger"
            ),
            actor_id=ACTOR_ID,
            activity=event,
        )
        assert result.status == Status.SUCCESS

        latest = _latest_status(dl, PARTICIPANT_ID)
        assert (
            _rm_of(latest) == RM.VALID.name
        ), "a replicated entry must not regress the replica's rm state"
        assert (
            _vfd_of(latest) == CS_vfd.VFd.name
        ), "the accepted vfd advance must still be applied"
