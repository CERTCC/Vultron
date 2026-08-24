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
``AddParticipantStatusBT`` Sequence, which also killed the StatusAdoptionGate → EmbargoTeardownAuthorizationGate
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
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.lifecycle import (
    BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE,
    _merge_snapshot_object_fields,
)
from vultron.core.behaviors.status.add_participant_status_tree import (
    add_participant_status_tree,
)
from vultron.core.behaviors.status.nodes.dimension_filter import (
    BB_DIMENSION_FILTER,
    FilterParticipantStatusDimensionsNode,
    resolve_dimension_filter,
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
from vultron.core.states.participant_embargo_consent import PEC
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
SECOND_STATUS_ID = f"{PARTICIPANT_ID}/statuses/asserted-2"

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
    entries = [
        cast(VultronCaseLedgerEntry, obj)
        for obj in dl.list_objects("CaseLedgerEntry")
        if isinstance(obj, VultronCaseLedgerEntry)
        and cast(VultronCaseLedgerEntry, obj).case_id == CASE_ID
    ]
    return sorted(entries, key=lambda e: e.log_index)


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
        em_consent_state=PEC.SIGNATORY,
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
    pxa_state: CS_pxa | None,
    status_id: str = ASSERTED_STATUS_ID,
) -> as_ParticipantStatus:
    """The inbound assertion from the sender.

    ``pxa_state=None`` builds a status with **no** ``case_status`` at all — the
    normal shape when the sender has nothing to say about the case-level
    dimensions, not a malformed message.
    """
    case_status = (
        None
        if pxa_state is None
        else as_CaseStatus(
            id_=f"{status_id}/cs",
            context=CASE_ID,
            em_state=EM.NONE,
            pxa_state=pxa_state,
        )
    )
    return as_ParticipantStatus(
        id_=status_id,
        context=CASE_ID,
        rm_state=rm_state,
        vfd_state=vfd_state,
        em_consent_state=PEC.SIGNATORY,
        case_status=case_status,
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
        datalayer=dl,
        trigger_activity=TriggerActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
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
        ), "em is EmbargoTeardownAuthorizationGate's business (#2256)"

    def test_regressive_rm_still_reaches_seam_2_emit(self, dl, make_payload):
        """The StatusAdoptionGate → EmbargoTeardownAuthorizationGate emit must survive a refused dimension.

        This is the concrete failure reported in #2235: aborting the Sequence
        at RM validation skipped ``EmitAddCaseStatusToSelfNode``, so embargo
        teardown in EmbargoTeardownAuthorizationGate never ran (RSH-01-003, RSH-01-004).
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

    def test_ledger_snapshot_keeps_the_wire_shape_of_an_unfiltered_snapshot(
        self, dl, make_payload
    ):
        """Adjudication must rewrite values, never reshape the snapshot.

        ``payload_snapshot['object']`` is consumed by every replica and by the
        invariant harness, which read the flat wire aliases (``rmState``,
        ``vfdState``, ``emConsentState``, ``cvdRole``) and the nested
        ``caseStatus``.  The guard runs in ``vultron.core`` and cannot import
        the wire layer to rebuild the object, so it publishes a *patch* over the
        sender's already-wire-shaped snapshot.  A snapshot built by dumping the
        core model instead would carry nested ``rm``/``vfd`` dimension objects
        and silently drop every field the guard never adjudicated
        (CLP-07-001, CM-18-006, ADR-0009).
        """
        current = _current_status(RM.VALID, CS_vfd.Vfd, CS_pxa.pxa)
        asserted = _asserted_status(RM.RECEIVED, CS_vfd.VFd, CS_pxa.Pxa)
        _seed_case(dl, current, asserted)

        result = _run_tree(dl, asserted, CASE_MANAGER_ID, make_payload)
        assert result.status == Status.SUCCESS

        entries = _ledger_entries(dl)
        assert len(entries) == 1
        snap = entries[0].payload_snapshot["object"]
        assert isinstance(snap, dict)

        # Flat wire aliases, carrying the adjudicated values.
        assert snap["rmState"] == RM.VALID.name
        assert snap["vfdState"] == CS_vfd.VFd.name

        # Fields the guard never adjudicated survive the patch untouched.
        assert (
            snap.get("emConsentState") == PEC.SIGNATORY.name
        ), "emConsentState must survive adjudication (fcvcv invariant harness)"
        assert "cvdRole" in snap, "cvdRole must survive adjudication"
        assert "@context" in snap, "@context must survive adjudication"
        assert snap.get("type") == "ParticipantStatus"

        # No core-model shapes, and no stale snake_case twin of a patched field.
        assert not isinstance(
            snap.get("rm"), dict
        ), f"core 'rm' dimension object leaked into the snapshot: {snap!r}"
        assert not isinstance(
            snap.get("vfd"), dict
        ), f"core 'vfd' dimension object leaked into the snapshot: {snap!r}"
        assert "rm_state" not in snap
        assert "vfd_state" not in snap

        # The nested caseStatus is patched in place, keeping its own identity.
        case_status = snap["caseStatus"]
        assert isinstance(case_status, dict)
        assert case_status["pxaState"] == CS_pxa.Pxa.name
        assert case_status["emState"] == EM.NONE.name
        assert case_status.get("id") == f"{ASSERTED_STATUS_ID}/cs"
        assert "pxa_state" not in case_status


# ---------------------------------------------------------------------------
# An omitted case_status asserts nothing — it must not erase pxa/em
# ---------------------------------------------------------------------------


class TestOmittedCaseStatusIsNotAnAssertion:
    """A status with no ``caseStatus`` says nothing about ``pxa``/``em``.

    Persisting such an assertion verbatim would blank both dimensions on the
    receiver, which is a silent data loss rather than an adjudication: the
    sender never claimed anything to adjudicate (RSH-05-002).
    """

    def test_omitted_case_status_does_not_erase_pxa_and_em(
        self, dl, make_payload
    ):
        """vfd advances; the receiver's own ``case_status`` carries forward."""
        current = _current_status(RM.VALID, CS_vfd.Vfd, CS_pxa.pXa)
        asserted = _asserted_status(RM.VALID, CS_vfd.VFd, None)
        assert asserted.case_status is None
        _seed_case(dl, current, asserted)

        result = _run_tree(dl, asserted, ACTOR_ID, make_payload)
        assert result.status == Status.SUCCESS, (
            "an omitted case_status is not a refusal"
            f" (feedback: {result.feedback_message})"
        )

        latest = _latest_status(dl, PARTICIPANT_ID)
        assert (
            _vfd_of(latest) == CS_vfd.VFd.name
        ), "the vfd advance is accepted"
        assert (
            _pxa_of(latest) == CS_pxa.pXa.name
        ), "an unasserted pxa must be carried forward, not blanked"
        assert (
            _em_of(latest) == EM.NONE.name
        ), "an unasserted em must be carried forward, not blanked"

    def test_omitted_case_status_alone_carries_no_new_state(
        self, dl, make_payload
    ):
        """Nothing asserted but the omission → refused in full, no entry.

        Carrying ``case_status`` forward is not new information, so appending
        the status would grow the history and the hash chain without recording
        a state change (RSH-05-005).  Run as the Case Manager so a commit
        *would* fire if the guards let it through.
        """
        current = _current_status(RM.VALID, CS_vfd.Vfd, CS_pxa.pXa)
        asserted = _asserted_status(RM.VALID, CS_vfd.Vfd, None)
        _seed_case(dl, current, asserted)

        result = _run_tree(dl, asserted, CASE_MANAGER_ID, make_payload)
        assert result.status == Status.FAILURE

        assert ASSERTED_STATUS_ID not in _status_ids(dl, PARTICIPANT_ID)
        assert _ledger_entries(dl) == []
        latest = _latest_status(dl, PARTICIPANT_ID)
        assert _pxa_of(latest) == CS_pxa.pXa.name
        assert _em_of(latest) == EM.NONE.name


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

        bridge = BTBridge(
            datalayer=dl, wire_render_port=As2WireRenderAdapter()
        )
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

    def test_ratchet_holds_when_the_status_object_is_already_stored_locally(
        self, dl
    ):
        """The ratchet must survive a status object already in the DataLayer.

        The node appends the object it *reads back* from the DataLayer, so the
        ratcheted value only reaches ``participant_statuses`` if the ratcheted
        copy is saved.  A status object can already be stored locally without
        being on the participant — an out-of-order ``Announce`` of the object
        itself, or a replayed entry — and skipping the save in that case appends
        the un-ratcheted status while the ratchet's own log line claims the
        local value was carried forward (RSH-05-007, SYNC-02-002).
        """
        current = _current_status(RM.VALID, CS_vfd.Vfd, CS_pxa.pxa)
        _seed_case(dl, current, None)
        # Present as a stored object, absent from participant_statuses.
        dl.create(_asserted_status(RM.RECEIVED, CS_vfd.VFd, CS_pxa.pxa))
        assert ASSERTED_STATUS_ID not in _status_ids(dl, PARTICIPANT_ID)

        entry = _status_snapshot_entry(rm_state="RECEIVED", vfd_state="VFd")
        event = _announce_event(entry)

        bridge = BTBridge(
            datalayer=dl, wire_render_port=As2WireRenderAdapter()
        )
        result = bridge.execute_with_setup(
            tree=ApplyParticipantStatusFromLedgerNode(
                name="ApplyParticipantStatusFromLedger"
            ),
            actor_id=ACTOR_ID,
            activity=event,
        )
        assert result.status == Status.SUCCESS

        latest = _latest_status(dl, PARTICIPANT_ID)
        assert _rm_of(latest) == RM.VALID.name, (
            "the ratcheted rm must be persisted even when the status object"
            " was already present in the local DataLayer"
        )
        assert _vfd_of(latest) == CS_vfd.VFd.name

    def test_unreadable_local_rm_fails_instead_of_skipping_the_ratchet(
        self, dl, monkeypatch
    ):
        """An unreadable RM floor is a shape mismatch, not "no floor".

        The ratchet needs the replica's current RM to know what a regression
        *is*.  Reading that floor with a defaulting accessor turned a
        non-core-shaped local record into ``None``, which made the ratchet a
        no-op and applied the regressing entry unchecked — the #2264 failure
        mode, silent because the ratchet only logs when it refuses something.
        ARCH-15-001 and ARCH-15-002 require FAILURE (ADR-0062).
        """
        current = _current_status(RM.VALID, CS_vfd.Vfd, CS_pxa.pxa)
        _seed_case(dl, current, None)

        # A *core* participant (so the node does not skip it as "not found")
        # whose latest status is wire-shaped: flat ``rmState``, no ``rm``
        # attribute at all.  Pydantic does not validate on list append, which
        # is how such a record survives into a replica in the first place.
        broken = cast(CaseParticipant, dl.read(PARTICIPANT_ID))
        assert isinstance(broken, CaseParticipant)
        broken.participant_statuses[-1] = cast(Any, current)

        real_read = dl.read
        monkeypatch.setattr(
            dl,
            "read",
            lambda object_id: (
                broken if object_id == PARTICIPANT_ID else real_read(object_id)
            ),
        )

        entry = _status_snapshot_entry(rm_state="RECEIVED", vfd_state="VFd")
        event = _announce_event(entry)

        bridge = BTBridge(
            datalayer=dl, wire_render_port=As2WireRenderAdapter()
        )
        result = bridge.execute_with_setup(
            tree=ApplyParticipantStatusFromLedgerNode(
                name="ApplyParticipantStatusFromLedger"
            ),
            actor_id=ACTOR_ID,
            activity=event,
        )
        assert (
            result.status == Status.FAILURE
        ), "an unreadable RM floor must fail, not silently skip the ratchet"

        assert real_read(ASSERTED_STATUS_ID) is None, (
            "the regressing status must not be persisted when the ratchet"
            " cannot be enforced"
        )
        assert ASSERTED_STATUS_ID not in [
            str(getattr(s, "id_", s)) for s in broken.participant_statuses
        ], "the regressing status must not reach participant_statuses"


# ---------------------------------------------------------------------------
# Blackboard hygiene
#
# The py_trees blackboard is process-global and is not cleared between tree
# executions, so every key a node writes is a potential leak into the next run
# (BT-17-003, BT-17-004).  The ledger override is the dangerous one: it rewrites
# what gets hash-chained and replicated to every participant.
# ---------------------------------------------------------------------------


class TestLedgerOverrideDoesNotLeakBetweenExecutions:
    """A stale override must never reach a later commit."""

    def test_second_execution_does_not_inherit_the_first_overrides(
        self, dl, make_payload
    ):
        """Two runs of the same status ID, no blackboard clear in between.

        Run 1 partially accepts and commits the adjudicated snapshot.  Run 2 is
        an idempotent re-delivery: the filter adjudicates nothing, so run 2's
        receipt entry must record the snapshot exactly as it arrived.  Both runs
        carry the same ``object_id``, so the commit node's ID match cannot catch
        this leak — the filter has to clear the key on its no-op path
        (BT-17-003, BT-17-004).
        """
        current = _current_status(RM.VALID, CS_vfd.Vfd, CS_pxa.pxa)
        asserted = _asserted_status(RM.RECEIVED, CS_vfd.VFd, CS_pxa.Pxa)
        _seed_case(dl, current, asserted)

        first = _run_tree(dl, asserted, CASE_MANAGER_ID, make_payload)
        assert first.status == Status.SUCCESS
        assert ASSERTED_STATUS_ID in _status_ids(dl, PARTICIPANT_ID)

        second = _run_tree(dl, asserted, CASE_MANAGER_ID, make_payload)
        assert second.status == Status.SUCCESS

        entries = _ledger_entries(dl)
        assert len(entries) == 2, "each receipt commits its own entry"
        assert (
            entries[0].payload_snapshot["object"]["rmState"] == RM.VALID.name
        ), "run 1 records the adjudicated rm"
        assert (
            entries[1].payload_snapshot["object"]["rmState"]
            == RM.RECEIVED.name
        ), (
            "run 2 adjudicated nothing, so a stale override from run 1 must not"
            " rewrite its snapshot"
        )

    def test_a_distinct_status_id_does_not_inherit_the_override(
        self, dl, make_payload
    ):
        """A leftover override for another object is ignored by the ID match."""
        current = _current_status(RM.VALID, CS_vfd.Vfd, CS_pxa.pxa)
        asserted = _asserted_status(RM.RECEIVED, CS_vfd.VFd, CS_pxa.Pxa)
        _seed_case(dl, current, asserted)

        assert (
            _run_tree(dl, asserted, CASE_MANAGER_ID, make_payload).status
            == Status.SUCCESS
        )

        # Wholly acceptable, so the filter publishes nothing of its own.
        second_status = _asserted_status(
            RM.ACCEPTED, CS_vfd.VFd, CS_pxa.Pxa, status_id=SECOND_STATUS_ID
        )
        dl.create(second_status)
        assert (
            _run_tree(dl, second_status, CASE_MANAGER_ID, make_payload).status
            == Status.SUCCESS
        )

        entries = _ledger_entries(dl)
        assert len(entries) == 2
        second_snap = entries[1].payload_snapshot["object"]
        assert second_snap["id"] == SECOND_STATUS_ID
        assert (
            second_snap["rmState"] == RM.ACCEPTED.name
        ), "the second status must be snapshotted as asserted"

    def test_filter_clears_a_stale_override_when_no_datalayer_is_available(
        self,
    ):
        """The datalayer-missing early return must still clear both keys.

        ``update()`` clears before it checks for the DataLayer, so a node that
        cannot do its job leaves no adjudication behind for the commit node to
        act on.
        """
        reader = py_trees.blackboard.Client(name="override-reader")
        for key in (BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE, BB_DIMENSION_FILTER):
            reader.register_key(key=key, access=py_trees.common.Access.READ)

        node = FilterParticipantStatusDimensionsNode(
            participant_id=PARTICIPANT_ID, status_id=ASSERTED_STATUS_ID
        )
        node.setup()
        stale_writer = py_trees.blackboard.Client(name="stale-override-writer")
        for key in (BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE, BB_DIMENSION_FILTER):
            stale_writer.register_key(
                key=key, access=py_trees.common.Access.WRITE
            )
        stale_writer.set(
            BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE,
            {"object_id": ASSERTED_STATUS_ID, "fields": {"rmState": "CLOSED"}},
            overwrite=True,
        )
        stale_writer.set(
            BB_DIMENSION_FILTER,
            {"status_id": ASSERTED_STATUS_ID, "refused": ("rm",)},
            overwrite=True,
        )

        assert node.datalayer is None
        assert node.update() == Status.FAILURE
        assert reader.get(BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE) is None
        assert reader.get(BB_DIMENSION_FILTER) is None


class TestResolveDimensionFilter:
    """The downstream helper must not read another execution's outcome."""

    def test_returns_none_for_a_mismatched_status_id(self):
        client = py_trees.blackboard.Client(name="filter-writer")
        client.register_key(
            key=BB_DIMENSION_FILTER, access=py_trees.common.Access.WRITE
        )
        payload = {"status_id": ASSERTED_STATUS_ID, "refused": ("rm",)}
        client.set(BB_DIMENSION_FILTER, payload, overwrite=True)

        assert resolve_dimension_filter(client, ASSERTED_STATUS_ID) is payload
        assert resolve_dimension_filter(client, SECOND_STATUS_ID) is None

    def test_returns_none_when_unset_or_not_a_dict(self):
        client = py_trees.blackboard.Client(name="filter-reader")
        client.register_key(
            key=BB_DIMENSION_FILTER, access=py_trees.common.Access.WRITE
        )
        assert resolve_dimension_filter(client, ASSERTED_STATUS_ID) is None

        client.set(BB_DIMENSION_FILTER, None, overwrite=True)
        assert resolve_dimension_filter(client, ASSERTED_STATUS_ID) is None


class TestMergeSnapshotObjectFields:
    """Unit coverage for the patch merge applied to a payload snapshot."""

    def test_patches_flat_fields_and_drops_stale_snake_case_twins(self):
        merged = _merge_snapshot_object_fields(
            {
                "id": ASSERTED_STATUS_ID,
                "rmState": "RECEIVED",
                "rm_state": "RECEIVED",
                "emConsentState": "SIGNATORY",
                "name": "RECEIVED VFd",
            },
            {"rmState": "VALID", "vfdState": "VFd"},
        )
        assert merged["rmState"] == "VALID"
        assert merged["vfdState"] == "VFd"
        assert "rm_state" not in merged, (
            "a stale snake_case twin would let a consumer read the value the"
            " receiver just refused"
        )
        assert merged["emConsentState"] == "SIGNATORY"
        assert merged["id"] == ASSERTED_STATUS_ID
        assert "name" not in merged, "the sender's derived label is dropped"

    def test_merges_one_level_of_nesting_without_replacing_it(self):
        merged = _merge_snapshot_object_fields(
            {
                "id": ASSERTED_STATUS_ID,
                "caseStatus": {
                    "id": f"{ASSERTED_STATUS_ID}/cs",
                    "type": "CaseStatus",
                    "pxaState": "PXA",
                    "pxa_state": "PXA",
                    "emState": "NONE",
                },
            },
            {"caseStatus": {"pxaState": "pxa", "emState": "NONE"}},
        )
        case_status = merged["caseStatus"]
        assert case_status["pxaState"] == "pxa"
        assert "pxa_state" not in case_status
        assert case_status["id"] == f"{ASSERTED_STATUS_ID}/cs"
        assert case_status["type"] == "CaseStatus"

    def test_leaves_a_bare_reference_alone(self):
        """Clobbering a reference string would drop the reference entirely."""
        current = {
            "id": ASSERTED_STATUS_ID,
            "caseStatus": f"{ASSERTED_STATUS_ID}/cs",
        }
        merged = _merge_snapshot_object_fields(
            current, {"rmState": "VALID", "caseStatus": {"pxaState": "pxa"}}
        )
        assert merged["caseStatus"] == f"{ASSERTED_STATUS_ID}/cs"
        assert merged["rmState"] == "VALID"


# ---------------------------------------------------------------------------
# RSH-06: RM anomaly detection (BB_RM_ANOMALY)
# ---------------------------------------------------------------------------


class TestRMGapAnomalyFlag:
    """FilterParticipantStatusDimensionsNode publishes BB_RM_ANOMALY (RSH-06)."""

    def _read_anomaly(self) -> Any:
        from vultron.core.behaviors.status.nodes.dimension_filter import (
            BB_RM_ANOMALY,
        )

        return py_trees.blackboard.Blackboard.storage.get("/" + BB_RM_ANOMALY)

    def test_nonadjacent_forward_jump_sets_gap_anomaly(self, dl, make_payload):
        """RECEIVED → ACCEPTED (non-adjacent) sets BB_RM_ANOMALY='gap' (RSH-06-001)."""
        current = _current_status(RM.RECEIVED, CS_vfd.vfd, CS_pxa.pxa)
        asserted = _asserted_status(RM.ACCEPTED, CS_vfd.vfd, None)
        _seed_case(dl, current, asserted)

        result = _run_tree(dl, asserted, ACTOR_ID, make_payload)

        assert result.status == Status.SUCCESS
        anomaly = self._read_anomaly()
        assert (
            anomaly is not None
        ), "BB_RM_ANOMALY not set for non-adjacent RM gap"
        assert anomaly["anomaly_type"] == "gap"
        assert anomaly["from_rm"] == RM.RECEIVED
        assert anomaly["to_rm"] == RM.ACCEPTED

    def test_adjacent_forward_transition_no_anomaly(self, dl, make_payload):
        """RECEIVED → VALID (adjacent) sets no BB_RM_ANOMALY (happy path)."""
        current = _current_status(RM.RECEIVED, CS_vfd.vfd, CS_pxa.pxa)
        asserted = _asserted_status(RM.VALID, CS_vfd.vfd, None)
        _seed_case(dl, current, asserted)

        _run_tree(dl, asserted, ACTOR_ID, make_payload)

        anomaly = self._read_anomaly()
        assert (
            anomaly is None
        ), f"Expected no anomaly for adjacent transition, got {anomaly}"

    def test_backward_regression_refused_sets_regression_anomaly(
        self, dl, make_payload
    ):
        """ACCEPTED → RECEIVED (backward) sets BB_RM_ANOMALY='regression' (RSH-06-002)."""
        current = _current_status(RM.ACCEPTED, CS_vfd.vfd, CS_pxa.pxa)
        asserted = _asserted_status(RM.RECEIVED, CS_vfd.vfd, None)
        _seed_case(dl, current, asserted)

        _run_tree(dl, asserted, ACTOR_ID, make_payload)

        anomaly = self._read_anomaly()
        assert (
            anomaly is not None
        ), "BB_RM_ANOMALY not set for backward regression"
        assert anomaly["anomaly_type"] == "regression"
        assert anomaly["from_rm"] == RM.ACCEPTED
        assert anomaly["to_rm"] == RM.RECEIVED


# ---------------------------------------------------------------------------
# RSH-05-011: producer_type in ledger_payload_object_override
# ---------------------------------------------------------------------------


class TestOverrideIncludesProducerType:
    """AC-1: FilterParticipantStatusDimensionsNode publishes producer_type (RSH-05-011)."""

    def test_published_override_includes_producer_type(self, dl, make_payload):
        """The override dict written to BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE must carry producer_type."""
        current = _current_status(RM.VALID, CS_vfd.Vfd, CS_pxa.pxa)
        asserted = _asserted_status(RM.RECEIVED, CS_vfd.VFd, CS_pxa.Pxa)
        _seed_case(dl, current, asserted)

        reader = py_trees.blackboard.Client(name="override-shape-reader")
        reader.register_key(
            key=BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE,
            access=py_trees.common.Access.READ,
        )

        result = _run_tree(dl, asserted, ACTOR_ID, make_payload)
        assert result.status == Status.SUCCESS

        override = reader.get(BB_LEDGER_PAYLOAD_OBJECT_OVERRIDE)
        assert isinstance(
            override, dict
        ), "override must be a dict after partial accept"
        assert (
            override.get("producer_type")
            == "FilterParticipantStatusDimensionsNode"
        ), "RSH-05-011: producer_type must identify the producing node"
