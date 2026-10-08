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
"""Tests for CaseActor lazy invite expiry (#2212, ADR-0118) and late-Accept
compatibility (#2213)."""

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Literal, cast

import pytest

from test.core.use_cases.received.conftest import (
    seed_case_manager_participant,
    seed_store_owner_as_case_manager,
)
from test.support.embargo_register import (
    activate,
    propose,
    reject,
    terminate,
    write_consent_rows,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.adapters.outbox_sealed_body import read_sealed_body_dict
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.rsvp_deadline import (
    INVITE_EXPIRED_EVENT_TYPE,
    INVITE_EXPIRED_NOOP_EVENT_TYPE,
)
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.services.embargo_lifecycle import EmbargoLifecycle
from vultron.core.states.em import EM
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
    PEC_Trigger,
)
from vultron.core.use_cases.received.embargo import (
    AcceptInviteToEmbargoOnCaseReceivedUseCase,
    InviteToEmbargoOnCaseReceivedUseCase,
    RejectInviteToEmbargoOnCaseReceivedUseCase,
    resolve_invitee_id,
)
from vultron.enums.roles import CVDRole
from vultron.errors import (
    VultronProtocolViolationError,
)
from vultron.wire.as2.factories import (
    em_accept_embargo_activity,
    em_propose_embargo_activity,
    em_reject_embargo_activity,
)
from vultron.wire.as2.vocab.objects.case_participant import (
    as_CaseParticipant as WireCP,
)
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (  # noqa: F401
    as_VulnerabilityCase,
)

CoreCase = VulnerabilityCase

_NOW = datetime.now(tz=UTC).replace(microsecond=0)
_PAST = _NOW - timedelta(days=1)
# _FUTURE must stay above the EP-07-002 minimum window floor (~3 days from
# datetime.now()).  The original hardcoded date (2026-09-03) has since fallen
# within the floor; use a rolling offset instead.
_FUTURE = datetime.now(tz=UTC) + timedelta(days=7)

_COORD = "https://example.org/actors/coordinator"
_INVITEE = "https://example.org/actors/invitee"
_OTHER = "https://example.org/actors/other-vendor"


def _answers_in_outbox(dl: SqliteDataLayer, actor_id: str) -> list[str]:
    """Types of the Accept/Reject answers *actor_id* queued to the manager."""
    answers = []
    for activity_id in dl.outbox_list():
        activity = dl.read(activity_id)
        type_ = getattr(activity, "type_", None)
        if (
            type_ in ("Accept", "Reject")
            and getattr(activity, "actor", None) == actor_id
        ):
            assert getattr(activity, "to", None) == [_COORD]
            answers.append(str(type_))
    return answers


def _relayed_deadline_to(dl: SqliteDataLayer, invitee_id: str) -> datetime:
    """The ``end_time`` the CASE_MANAGER stamped on its Invite to *invitee_id*.

    The manager authors the deadline (CM-28-012), so the record it keeps is
    the one its outbound Invite carries — not the proposer's ``endTime``.
    """
    deadlines = [
        getattr(activity, "end_time", None)
        for activity in (dl.read(i) for i in dl.outbox_list())
        if getattr(activity, "type_", None) == "Invite"
        and getattr(activity, "to", None) == [invitee_id]
    ]
    assert len(deadlines) == 1, deadlines
    deadline = deadlines[0]
    assert isinstance(deadline, datetime)
    return deadline


def _rows(
    consents: dict[str, EmbargoConsentState | None],
    rsvp_deadline: datetime | None = None,
) -> list[EmbargoConsent]:
    """Consent rows for the embargoes in *consents* (ADR-0122).

    A ``None`` state is a never-asked ``UNINVITED`` row: every register entry
    has a row on every participant.  *rsvp_deadline* goes on each ``INVITED``
    row, the only state that carries one (CM-28-013).
    """
    return [
        EmbargoConsent(
            embargo_id=embargo_id,
            state=state or EmbargoConsentState.UNINVITED,
            rsvp_deadline=(
                rsvp_deadline if state == EmbargoConsentState.INVITED else None
            ),
        )
        for embargo_id, state in consents.items()
    ]


def _make_dl(actor_id: str = _COORD) -> SqliteDataLayer:
    return SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)


def _make_active_embargo_case(
    dl: SqliteDataLayer,
    case_id: str,
    embargo_id: str,
    invitee_consent: EmbargoConsentState | None = EmbargoConsentState.INVITED,
    invitee_deadline: datetime | None = None,
    *,
    em_active: bool = True,
):
    """Create and persist a case with an active embargo and one invitee participant.

    With ``em_active=False`` the embargo record is stored but the case's
    register holds no entry for it (EM NONE).

    ``_COORD`` holds the CASE_MANAGER role in every store, since the role is
    never unfilled (CM-24-006) and only its holder evaluates lapse (CM-28-014).

    Returns (case, embargo, invitee_participant_id).
    """
    case = VulnerabilityCase(
        id_=case_id,
        name="Expiry Test Case",
        attributed_to=_COORD,
    )
    embargo = as_EmbargoEvent(
        id_=embargo_id, context=case_id, end_time=days_from_now_utc(45)
    )
    if em_active:
        activate(case, embargo_id)

    # The invitee holds a row only for an embargo the register holds; the
    # deadline belongs to the INVITED row (CM-28-013).
    invitee_cp = WireCP(
        attributed_to=_INVITEE,
        context=case_id,
        embargo_consents=(
            _rows({embargo_id: invitee_consent}, invitee_deadline)
            if em_active
            else []
        ),
        case_roles=[CVDRole.VENDOR],
    )
    invitee_cp_core = invitee_cp

    seed_case_manager_participant(dl, case, _COORD)
    dl.create(case)
    dl.create(embargo)
    dl.create(invitee_cp_core)
    case.actor_participant_index[_INVITEE] = invitee_cp_core.id_
    case.case_participants.append(invitee_cp_core.id_)
    dl.save(case)
    return case, embargo, invitee_cp_core.id_


# ---------------------------------------------------------------------------
# Unit tests — EmbargoLifecycle.detect_and_apply_expiry
# ---------------------------------------------------------------------------


class TestDetectAndApplyExpiry:
    """Direct unit tests for EmbargoLifecycle.detect_and_apply_expiry."""

    @pytest.mark.spec("CM-18-002")
    @pytest.mark.spec("CM-28-005")
    def test_expiry_invited_past_deadline(self):
        """INVITED times out to TIMED_OUT, not DECLINED, past its deadline."""
        dl = _make_dl()
        case_id = "https://example.org/cases/lapse1"
        embargo_id = "https://example.org/cases/lapse1/embargos/e1"
        _make_active_embargo_case(
            dl,
            case_id,
            embargo_id,
            invitee_consent=EmbargoConsentState.INVITED,
            invitee_deadline=_PAST,
        )

        service = EmbargoLifecycle(persistence=dl)
        result = service.detect_and_apply_expiry(
            case_id=case_id,
            actor_id=_INVITEE,
            embargo_id=embargo_id,
            now=_NOW,
        )

        assert result.is_expired is True
        assert len(result.participant_changes) == 1
        change = result.participant_changes[0]
        assert change.embargo_id == embargo_id
        assert change.consent_before == EmbargoConsentState.INVITED.value
        assert change.consent_after == EmbargoConsentState.TIMED_OUT.value

        # Verify persistence
        case = dl.read(case_id)
        assert isinstance(case, CoreCase)
        participant_id = case.actor_participant_index[_INVITEE]
        participant = dl.read(participant_id)
        assert isinstance(participant, CaseParticipant)
        assert (
            participant.consent_for(embargo_id)
            == EmbargoConsentState.TIMED_OUT
        )

    def test_no_expiry_future_deadline(self):
        """Participant does NOT expire when deadline is in the future."""
        dl = _make_dl()
        case_id = "https://example.org/cases/lapse2"
        embargo_id = "https://example.org/cases/lapse2/embargos/e2"
        _make_active_embargo_case(
            dl,
            case_id,
            embargo_id,
            invitee_consent=EmbargoConsentState.INVITED,
            invitee_deadline=_FUTURE,
        )

        service = EmbargoLifecycle(persistence=dl)
        result = service.detect_and_apply_expiry(
            case_id=case_id,
            actor_id=_INVITEE,
            embargo_id=embargo_id,
            now=_NOW,
        )

        assert result.is_expired is False
        assert result.participant_changes == []

        case = dl.read(case_id)
        assert isinstance(case, CoreCase)
        participant_id = case.actor_participant_index[_INVITEE]
        participant = dl.read(participant_id)
        assert isinstance(participant, CaseParticipant)
        assert (
            participant.consent_for(embargo_id) == EmbargoConsentState.INVITED
        )

    def test_no_expiry_no_deadline(self):
        """Participant never times out when its INVITED row has no deadline."""
        dl = _make_dl()
        case_id = "https://example.org/cases/lapse3"
        embargo_id = "https://example.org/cases/lapse3/embargos/e3"
        _make_active_embargo_case(
            dl,
            case_id,
            embargo_id,
            invitee_consent=EmbargoConsentState.INVITED,
            invitee_deadline=None,
        )

        service = EmbargoLifecycle(persistence=dl)
        result = service.detect_and_apply_expiry(
            case_id=case_id,
            actor_id=_INVITEE,
            embargo_id=embargo_id,
            now=_NOW,
        )

        assert result.is_expired is False
        assert result.participant_changes == []

    @pytest.mark.parametrize(
        "settled",
        [EmbargoConsentState.DECLINED, EmbargoConsentState.TIMED_OUT],
    )
    def test_expiry_idempotent_once_settled(self, settled):
        """detect_and_apply_expiry changes nothing once DECLINED or TIMED_OUT.

        The deadline belongs to the INVITED row and leaves with it
        (CM-28-013), so a settled row has no deadline left to pass.
        """
        dl = _make_dl()
        case_id = "https://example.org/cases/lapse4"
        embargo_id = "https://example.org/cases/lapse4/embargos/e4"
        _make_active_embargo_case(
            dl,
            case_id,
            embargo_id,
            invitee_consent=settled,
            invitee_deadline=_PAST,
        )

        service = EmbargoLifecycle(persistence=dl)
        result = service.detect_and_apply_expiry(
            case_id=case_id,
            actor_id=_INVITEE,
            embargo_id=embargo_id,
            now=_NOW,
        )

        # The settled row carries no deadline, so nothing is judged expired
        # and nothing moves.
        assert result.is_expired is False
        assert result.participant_changes == []

    def test_expiry_no_background_task(self):
        """Expiry is derived on read without any background scheduler (AC-6)."""
        dl = _make_dl()
        case_id = "https://example.org/cases/lapse5"
        embargo_id = "https://example.org/cases/lapse5/embargos/e5"
        _make_active_embargo_case(
            dl,
            case_id,
            embargo_id,
            invitee_consent=EmbargoConsentState.INVITED,
            invitee_deadline=_PAST,
        )

        # No scheduler; call detect_and_apply_expiry directly to expire it.
        service = EmbargoLifecycle(persistence=dl)
        result = service.detect_and_apply_expiry(
            case_id=case_id,
            actor_id=_INVITEE,
            embargo_id=embargo_id,
            now=_NOW,
        )

        assert result.is_expired is True
        # The row changed without any background task.
        assert any(
            c.consent_after == EmbargoConsentState.TIMED_OUT.value
            for c in result.participant_changes
        )


# ---------------------------------------------------------------------------
# Integration tests — InviteToEmbargoOnCaseReceivedUseCase stores no deadline
# ---------------------------------------------------------------------------


class TestInviteReceiptStoresNoDeadline:
    """Receiving an Invite stores no RSVP deadline (CM-28-013, ADR-0113).

    The CASE_MANAGER records the deadline it stamped at its relay commit, and
    a replica records that same value when it replays the entry.  The Invite
    arriving in an invitee's inbox writes nothing.
    """

    @pytest.mark.spec("CM-28-013")
    def test_invite_with_deadline_stores_no_rsvp_deadline(self, make_payload):
        """An Invite carrying ``endTime`` leaves the invitee's record bare."""
        dl = _make_dl(actor_id=_INVITEE)
        case_id = "https://example.org/cases/store1"
        embargo_id = "https://example.org/cases/store1/embargos/e1"

        case = VulnerabilityCase(
            id_=case_id, name="Store Deadline", attributed_to=_COORD
        )
        embargo = as_EmbargoEvent(
            id_=embargo_id, context=case_id, end_time=days_from_now_utc(45)
        )
        propose(case, embargo_id)

        invitee_cp = WireCP(
            attributed_to=_INVITEE,
            context=case_id,
            case_roles=[CVDRole.VENDOR],
        )
        invitee_cp_core = invitee_cp

        # The CASE_MANAGER role is never unfilled (CM-24-006); the invitee
        # addresses its answer to the holder.
        coord_cp = WireCP(
            attributed_to=_COORD,
            context=case_id,
            case_roles=[CVDRole.CASE_MANAGER],
        )

        dl.create(case)
        dl.create(embargo)
        dl.create(invitee_cp_core)
        dl.create(coord_cp)
        case.actor_participant_index[_INVITEE] = invitee_cp_core.id_
        case.actor_participant_index[_COORD] = coord_cp.id_
        dl.save(case)

        # Propose with a deadline
        invite = em_propose_embargo_activity(
            embargo=embargo,
            context=case.id_,
            actor=_COORD,
            to=[_INVITEE],
            rsvp_deadline=_FUTURE,
        )
        event = make_payload(invite, receiving_actor_id=_INVITEE)

        InviteToEmbargoOnCaseReceivedUseCase(
            dl,
            event,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        # Receipt is not a record: the deadline arrives with the ledger entry.
        fresh_case = dl.read(case_id)
        assert isinstance(fresh_case, CoreCase)
        p_id = fresh_case.actor_participant_index.get(_INVITEE)
        assert p_id is not None
        participant = dl.read(p_id)
        assert isinstance(participant, CaseParticipant)
        assert all(
            r.rsvp_deadline is None for r in participant.embargo_consents
        )


class TestInviteeIsTheAddressee:
    """The invitee is the activity's ``to:`` recipient, not the receiving actor.

    ``receiving_actor_id`` answers "whose replica is this?"; the Invite's
    ``to:`` field answers "who is being invited?".  ADR-0022 requires the
    second to be threaded into the tree as leaf-node data rather than reused
    as the BT execution identity.  Conflating them writes the consent row
    and the RSVP deadline (CM-28-001, CM-28-003) onto the wrong participant
    record, so the CaseActor records an invitation it never received and the
    real invitee is left with no deadline for expiry detection to find.
    """

    def _seed_case(
        self,
        dl,
        case_id: str,
        embargo_id: str,
        invitee_consent: EmbargoConsentState | None = None,
        extra_actors: tuple[str, ...] = (),
        *,
        embargo_is: Literal["proposed", "active", "unknown"] = "proposed",
        invitee_accepted: tuple[str, ...] = (),
    ):
        """Case with the coordinator as CASE_MANAGER and a separate invitee.

        ``extra_actors`` seeds additional VENDOR participants with
        ``UNINVITED`` rows; their participant IDs are returned in a dict keyed
        by actor ID so multi-recipient tests can assert on them.

        ``embargo_is`` places the embargo on the case: ``"proposed"`` (EM
        PROPOSED, an open proposal), ``"active"`` (EM ACTIVE, the embargo
        in force) or ``"unknown"`` (EM NONE, the case has never seen
        it).  ``invitee_accepted`` seeds AGREED rows for the invitee.
        """
        case = VulnerabilityCase(
            id_=case_id, name="Addressee Test", attributed_to=_COORD
        )
        embargo = as_EmbargoEvent(
            id_=embargo_id, context=case_id, end_time=days_from_now_utc(45)
        )
        if embargo_is == "active":
            activate(case, embargo_id)
        elif embargo_is == "proposed":
            propose(case, embargo_id)

        coord_cp = WireCP(
            attributed_to=_COORD,
            context=case_id,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        invitee_rows = {
            **dict.fromkeys(invitee_accepted, EmbargoConsentState.AGREED),
            embargo_id: invitee_consent
            or (
                EmbargoConsentState.AGREED
                if embargo_id in invitee_accepted
                else None
            ),
        }
        if embargo_is == "unknown" and invitee_rows[embargo_id] is None:
            # The register holds no entry for it, so nobody has a row.
            del invitee_rows[embargo_id]
        invitee_cp = WireCP(
            attributed_to=_INVITEE,
            context=case_id,
            embargo_consents=_rows(invitee_rows),
            case_roles=[CVDRole.VENDOR],
        )
        # Every participant holds a row for every register entry (ADR-0122).
        register_ids = [e.embargo_id for e in case.embargo_register]
        coord_cp.write_uninvited_rows(register_ids)

        dl.create(case)
        dl.create(embargo)
        dl.create(coord_cp)
        dl.create(invitee_cp)
        case.actor_participant_index[_COORD] = coord_cp.id_
        case.actor_participant_index[_INVITEE] = invitee_cp.id_
        case.case_participants.extend([coord_cp.id_, invitee_cp.id_])

        self.extra_participant_ids: dict[str, str] = {}
        for actor in extra_actors:
            extra_cp = WireCP(
                attributed_to=actor,
                context=case_id,
                case_roles=[CVDRole.VENDOR],
            )
            extra_cp.write_uninvited_rows(register_ids)
            dl.create(extra_cp)
            case.actor_participant_index[actor] = extra_cp.id_
            case.case_participants.append(extra_cp.id_)
            self.extra_participant_ids[actor] = extra_cp.id_

        dl.save(case)
        return case, embargo, coord_cp.id_, invitee_cp.id_

    def _read_participant(self, dl, participant_id: str) -> CaseParticipant:
        participant = dl.read(participant_id)
        assert isinstance(participant, CaseParticipant)
        return participant

    def test_case_actor_receipt_targets_the_addressee(self, make_payload):
        """CaseActor processing an Invite addressed to someone else."""
        dl = _make_dl(actor_id=_COORD)
        case_id = "https://example.org/cases/addressee1"
        embargo_id = "https://example.org/cases/addressee1/embargos/e1"
        case, embargo, coord_p_id, invitee_p_id = self._seed_case(
            dl, case_id, embargo_id
        )

        # actor is the coordinator, to: is the invitee — the CLP-10-001 shape.
        # Keeping them distinct is what makes this test discriminating: an
        # implementation reading the subject from `activity.actor` instead of
        # `to:` fails here rather than passing by coincidence.
        invite = em_propose_embargo_activity(
            embargo=embargo,
            context=case.id_,
            actor=_COORD,
            to=[_INVITEE],
            rsvp_deadline=_FUTURE,
        )
        event = make_payload(invite, receiving_actor_id=_COORD)

        InviteToEmbargoOnCaseReceivedUseCase(
            dl,
            event,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        # The CASE_MANAGER adjudicates its own proposal and relays it: the
        # invitee's INVITED is written at the manager's commit of the relayed
        # Invite (EP-09-002, AC-3); the proposer records only its own AGREED
        # row (proposing is consenting).
        invitee = self._read_participant(dl, invitee_p_id)
        assert invitee.consent_for(embargo_id) == EmbargoConsentState.INVITED
        assert invitee.rsvp_deadline_for(embargo_id) == _relayed_deadline_to(
            dl, _INVITEE
        )

        coord = self._read_participant(dl, coord_p_id)
        assert coord.consent_for(embargo_id) == EmbargoConsentState.AGREED
        assert all(r.rsvp_deadline is None for r in coord.embargo_consents)

    def test_absent_receiving_actor_targets_the_addressee(self, make_payload):
        """CLI/replay dispatch: no receiving_actor_id, store owned by CaseActor."""
        dl = _make_dl(actor_id=_COORD)
        case_id = "https://example.org/cases/addressee2"
        embargo_id = "https://example.org/cases/addressee2/embargos/e2"
        case, embargo, coord_p_id, invitee_p_id = self._seed_case(
            dl, case_id, embargo_id
        )

        invite = em_propose_embargo_activity(
            embargo=embargo,
            context=case.id_,
            actor=_COORD,
            to=[_INVITEE],
            rsvp_deadline=_FUTURE,
        )
        event = make_payload(invite)
        assert event.receiving_actor_id is None

        InviteToEmbargoOnCaseReceivedUseCase(
            dl,
            event,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        invitee = self._read_participant(dl, invitee_p_id)
        assert invitee.consent_for(embargo_id) == EmbargoConsentState.INVITED
        assert invitee.rsvp_deadline_for(embargo_id) == _relayed_deadline_to(
            dl, _INVITEE
        )

        coord = self._read_participant(dl, coord_p_id)
        assert coord.consent_for(embargo_id) == EmbargoConsentState.AGREED
        assert all(r.rsvp_deadline is None for r in coord.embargo_consents)

    @pytest.mark.spec("EP-09-010")
    @pytest.mark.spec("HP-01-005")
    def test_missing_to_field_is_refused(self, make_payload):
        """An Invite with no ``to:`` names no invitee and is refused.

        It is malformed upstream (OX-08-001); the receiving actor is not a
        stand-in for the invitee it fails to name (EP-09-010).
        """
        dl = _make_dl(actor_id=_INVITEE)
        case_id = "https://example.org/cases/addressee3"
        embargo_id = "https://example.org/cases/addressee3/embargos/e3"
        case, embargo, _, invitee_p_id = self._seed_case(
            dl, case_id, embargo_id
        )

        invite = em_propose_embargo_activity(
            embargo=embargo,
            context=case.id_,
            actor=_COORD,
            rsvp_deadline=_FUTURE,
        )
        event = make_payload(invite, receiving_actor_id=_INVITEE)
        assert event.invitee_id is None

        result = InviteToEmbargoOnCaseReceivedUseCase(
            dl,
            event,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert result.disposition is HandlerDisposition.REFUSED
        assert "names 0 'to' recipients" in (result.reason or "")
        assert dl.read(invite.id_) is None
        invitee = self._read_participant(dl, invitee_p_id)
        assert invitee.consent_for(embargo_id) == EmbargoConsentState.UNINVITED
        assert all(r.rsvp_deadline is None for r in invitee.embargo_consents)
        assert _answers_in_outbox(dl, _INVITEE) == []

    def test_reject_declines_the_rejecting_actor_not_the_receiver(
        self, make_payload
    ):
        """The DECLINE lands on the actor who rejected, not the CaseActor.

        ``reject_invite_to_embargo_tree`` takes ``rejecting_actor_id`` but only
        logged it, so the participant lookup fell through to the BT execution
        actor and the CaseActor declined its own embargo on the rejecter's
        behalf.
        """
        dl = _make_dl(actor_id=_COORD)
        case_id = "https://example.org/cases/addressee4"
        embargo_id = "https://example.org/cases/addressee4/embargos/e4"
        case, embargo, coord_p_id, invitee_p_id = self._seed_case(
            dl,
            case_id,
            embargo_id,
            invitee_consent=EmbargoConsentState.INVITED,
        )

        proposal = em_propose_embargo_activity(
            embargo=embargo,
            context=case.id_,
            actor=_COORD,
            to=[_INVITEE],
            id_=f"{case_id}/proposals/p1",
        )
        dl.create(proposal)
        reject = em_reject_embargo_activity(
            proposal=proposal, context=case.id_, actor=_INVITEE, to=[_COORD]
        )
        event = make_payload(reject, receiving_actor_id=_COORD)

        RejectInviteToEmbargoOnCaseReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        invitee = self._read_participant(dl, invitee_p_id)
        assert invitee.consent_for(embargo_id) == EmbargoConsentState.DECLINED

        coord = self._read_participant(dl, coord_p_id)
        assert coord.consent_for(embargo_id) == EmbargoConsentState.UNINVITED

    @pytest.mark.spec("EP-09-010")
    @pytest.mark.spec("HP-01-005")
    @pytest.mark.spec("CLP-10-016")
    def test_multi_recipient_invite_is_refused_at_a_recipient(
        self, make_payload
    ):
        """An Invite naming several recipients is refused, even at one of them.

        Every emitter sends a single-recipient Invite (EP-09-002), so several
        recipients is a misrouting: no recipient's replica answers it or
        stores a deadline, rather than each one resolving itself by
        membership (EP-09-010).
        """
        dl = _make_dl(actor_id=_INVITEE)
        case_id = "https://example.org/cases/addressee5"
        embargo_id = "https://example.org/cases/addressee5/embargos/e5"
        case, embargo, coord_p_id, invitee_p_id = self._seed_case(
            dl, case_id, embargo_id, extra_actors=(_OTHER,)
        )
        other_p_id = self.extra_participant_ids[_OTHER]

        invite = em_propose_embargo_activity(
            embargo=embargo,
            context=case.id_,
            actor=_COORD,
            to=[_OTHER, _INVITEE],
            rsvp_deadline=_FUTURE,
        )
        event = make_payload(invite, receiving_actor_id=_INVITEE)
        assert event.invitee_id is None
        assert event.to_recipients == [_OTHER, _INVITEE]

        result = InviteToEmbargoOnCaseReceivedUseCase(
            dl,
            event,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert result.disposition is HandlerDisposition.REFUSED
        assert "names 2 'to' recipients" in (result.reason or "")
        assert dl.read(invite.id_) is None
        assert _answers_in_outbox(dl, _INVITEE) == []
        for participant_id in (invitee_p_id, other_p_id, coord_p_id):
            participant = self._read_participant(dl, participant_id)
            assert (
                participant.consent_for(embargo_id)
                == EmbargoConsentState.UNINVITED
            )
            assert all(
                r.rsvp_deadline is None for r in participant.embargo_consents
            )

    def test_trailing_slash_recipient_is_this_replica(self, make_payload):
        """A recipient spelled with a trailing slash still names this replica.

        The sole recipient resolves in its canonical spelling (#2667), so the
        participant lookup hits ``actor_participant_index`` rather than
        missing on the slash.
        """
        dl = _make_dl(actor_id=_INVITEE)
        case_id = "https://example.org/cases/addressee-slash"
        embargo_id = "https://example.org/cases/addressee-slash/embargos/e"
        case, embargo, _coord_p_id, invitee_p_id = self._seed_case(
            dl, case_id, embargo_id, extra_actors=(_OTHER,)
        )

        invite = em_propose_embargo_activity(
            embargo=embargo,
            context=case.id_,
            actor=_COORD,
            to=[_INVITEE + "/"],
            rsvp_deadline=_FUTURE,
        )
        event = make_payload(invite, receiving_actor_id=_INVITEE)

        InviteToEmbargoOnCaseReceivedUseCase(
            dl,
            event,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        invitee = self._read_participant(dl, invitee_p_id)
        assert invitee.consent_for(embargo_id) == EmbargoConsentState.UNINVITED
        # Receipt stores no deadline (CM-28-013).
        assert all(r.rsvp_deadline is None for r in invitee.embargo_consents)
        assert _answers_in_outbox(dl, _INVITEE) == ["Accept"]

    @pytest.mark.spec("EP-09-010")
    @pytest.mark.spec("PCR-08-001")
    @pytest.mark.spec("HP-01-005")
    def test_multi_recipient_invite_is_refused_at_the_case_manager(
        self, make_payload
    ):
        """The CASE_MANAGER refuses a several-recipient Invite and relays none.

        A proposal goes to the CASE_MANAGER alone (PCR-08-001); one naming
        several recipients is a misrouting the manager neither adjudicates
        nor relays (EP-09-010), so no participant is INVITED.
        """
        dl = _make_dl(actor_id=_COORD)
        case_id = "https://example.org/cases/addressee6"
        embargo_id = "https://example.org/cases/addressee6/embargos/e6"
        case, embargo, coord_p_id, invitee_p_id = self._seed_case(
            dl, case_id, embargo_id, extra_actors=(_OTHER,)
        )
        other_p_id = self.extra_participant_ids[_OTHER]

        invite = em_propose_embargo_activity(
            embargo=embargo,
            context=case.id_,
            actor=_COORD,
            to=[_INVITEE, _OTHER],
            rsvp_deadline=_FUTURE,
        )
        event = make_payload(invite, receiving_actor_id=_COORD)

        result = InviteToEmbargoOnCaseReceivedUseCase(
            dl,
            event,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert result.disposition is HandlerDisposition.REFUSED
        assert "names 2 'to' recipients" in (result.reason or "")
        # Only the ProcessingFault answers it: no Invite is relayed (MSM-05-001).
        (queued,) = dl.outbox_list()
        sealed = read_sealed_body_dict(dl, queued)
        assert sealed is not None
        assert sealed["object"]["type"] == "ProcessingFault"
        assert sealed["object"]["failureClass"].endswith(
            "MisroutedEmbargoInvite"
        )
        for participant_id in (invitee_p_id, other_p_id, coord_p_id):
            participant = self._read_participant(dl, participant_id)
            assert (
                participant.consent_for(embargo_id)
                == EmbargoConsentState.UNINVITED
            )

    @pytest.mark.spec("EP-09-010")
    @pytest.mark.spec("CM-28-003")
    def test_proposal_to_the_case_manager_puts_no_deadline_on_its_record(
        self, make_payload
    ):
        """The CASE_MANAGER adjudicates a proposal addressed to it; it is no invitee.

        Its record never carries the proposal's RSVP deadline: the enforcer
        of invite expiry is not the record expiry is evaluated on (CM-28-003,
        ISSUE-2762).
        """
        dl = _make_dl(actor_id=_COORD)
        case_id = "https://example.org/cases/addressee-manager"
        embargo_id = "https://example.org/cases/addressee-manager/embargos/e"
        case, embargo, coord_p_id, _ = self._seed_case(dl, case_id, embargo_id)

        proposal = em_propose_embargo_activity(
            embargo=embargo,
            context=case.id_,
            actor=_INVITEE,
            to=[_COORD],
            rsvp_deadline=_FUTURE,
        )
        event = make_payload(proposal, receiving_actor_id=_COORD)

        result = InviteToEmbargoOnCaseReceivedUseCase(
            dl,
            event,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert result.disposition is HandlerDisposition.APPLIED
        coord = self._read_participant(dl, coord_p_id)
        assert all(r.rsvp_deadline is None for r in coord.embargo_consents)

    @pytest.mark.spec("HP-01-005")
    @pytest.mark.spec("EMB-01-002")
    def test_unaddressed_copy_is_refused_at_the_door(
        self, make_payload, caplog
    ):
        """A misrouted copy in a third store is refused before any tree runs.

        The third participant is neither the sender nor named in ``to`` or
        ``cc``, so the door check refuses it (ADR-0118, #4132): no tree
        runs, so ``CanAnswerEmbargoInviteNode`` never warns "is not the
        invitee", nothing is written and no ER is sent — EMB-01-002's ER
        duty binds only the addressee.  The reason names the receiver and
        the recipients the sender chose, so the misrouting can be traced.
        """
        dl = _make_dl(actor_id=_OTHER)
        case_id = "https://example.org/cases/addressee7"
        embargo_id = "https://example.org/cases/addressee7/embargos/e7"
        case, embargo, coord_p_id, invitee_p_id = self._seed_case(
            dl, case_id, embargo_id, extra_actors=(_OTHER,)
        )

        invite = em_propose_embargo_activity(
            embargo=embargo,
            context=case.id_,
            actor=_COORD,
            to=[_INVITEE + "/"],  # non-canonical: trailing slash
            rsvp_deadline=_FUTURE,
        )
        event = make_payload(invite, receiving_actor_id=_OTHER)

        caplog.set_level("WARNING")
        result = InviteToEmbargoOnCaseReceivedUseCase(
            dl,
            event,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert result.disposition is HandlerDisposition.REFUSED
        reason = result.reason or ""
        assert "neither the sender nor a recipient" in reason
        assert _OTHER in reason and _INVITEE in reason
        assert not any(
            "is not the invitee" in record.message for record in caplog.records
        )
        # Nothing is written to any participant, and nothing answers.
        assert dl.read(invite.id_) is None
        assert _answers_in_outbox(dl, _OTHER) == []
        invitee = self._read_participant(dl, invitee_p_id)
        assert invitee.consent_for(embargo_id) == EmbargoConsentState.UNINVITED
        assert all(r.rsvp_deadline is None for r in invitee.embargo_consents)
        other = self._read_participant(dl, self.extra_participant_ids[_OTHER])
        assert other.consent_for(embargo_id) == EmbargoConsentState.UNINVITED
        coord = self._read_participant(dl, coord_p_id)
        assert coord.consent_for(embargo_id) == EmbargoConsentState.UNINVITED
        other = self._read_participant(dl, self.extra_participant_ids[_OTHER])
        assert other.consent_for(embargo_id) == EmbargoConsentState.UNINVITED

    def test_reject_tree_threads_subject_to_participant_lookup(self):
        """``reject_invite_to_embargo_tree`` wires its subject to the node.

        Guards the tree factory directly: the original defect was a
        ``rejecting_actor_id`` that reached only a ``logger.info`` call, which
        is indistinguishable from never supplying one.
        """
        from vultron.core.behaviors.embargo.announce_teardown_tree import (
            reject_invite_to_embargo_tree,
        )
        from vultron.core.behaviors.embargo.nodes.proposal import (
            RecordParticipantRejectionNode,
        )

        tree = reject_invite_to_embargo_tree(
            case_id="https://example.org/cases/wiring",
            rejecting_actor_id=_INVITEE,
            invite_id="https://example.org/cases/wiring/proposals/p1",
            embargo_id="https://example.org/cases/wiring/embargos/e1",
        )

        recorders = [
            node
            for node in tree.iterate()
            if isinstance(node, RecordParticipantRejectionNode)
        ]
        assert recorders, (
            "no RecordParticipantRejectionNode in the reject tree"
        )
        assert all(node.rejecting_actor_id == _INVITEE for node in recorders)

    @pytest.mark.spec("MSM-07-004")
    @pytest.mark.spec("CM-18-003")
    def test_reject_from_signatory_transitions_to_declined(self, make_payload):
        """A signatory rejecting the *active* embargo withdraws → DECLINED (ADR-0093).

        ``DECLINE`` is valid from ``AGREED``; the received side applies it
        when the Reject names the embargo in force.  The case-level EM state
        is not changed (VP-13-009); only the invitee's own consent record is.
        """
        dl = _make_dl(actor_id=_COORD)
        case_id = "https://example.org/cases/addressee8"
        embargo_id = "https://example.org/cases/addressee8/embargos/e8"
        case, embargo, coord_p_id, invitee_p_id = self._seed_case(
            dl,
            case_id,
            embargo_id,
            invitee_consent=EmbargoConsentState.AGREED,
            embargo_is="active",
            invitee_accepted=(embargo_id,),
        )

        proposal = em_propose_embargo_activity(
            embargo=embargo,
            context=case.id_,
            actor=_COORD,
            to=[_INVITEE],
            id_=f"{case_id}/proposals/p1",
        )
        dl.create(proposal)
        reject = em_reject_embargo_activity(
            proposal=proposal, context=case.id_, actor=_INVITEE, to=[_COORD]
        )
        event = make_payload(reject, receiving_actor_id=_COORD)

        result = RejectInviteToEmbargoOnCaseReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()
        assert result.disposition is HandlerDisposition.APPLIED

        # Invitee's consent withdrawal is recorded as DECLINED.
        invitee = self._read_participant(dl, invitee_p_id)
        assert invitee.consent_for(embargo_id) == EmbargoConsentState.DECLINED
        assert not invitee.is_signatory(embargo_id)
        # CASE_MANAGER's own consent is unaffected.
        coord = self._read_participant(dl, coord_p_id)
        assert coord.consent_for(embargo_id) == EmbargoConsentState.UNINVITED
        assert (
            cast(VulnerabilityCase, dl.read(case_id)).current_status.em.state
            == EM.ACTIVE
        )

    @pytest.mark.spec("MSM-07-004")
    def test_reject_of_a_proposed_revision_leaves_a_signatory_bound(
        self, make_payload
    ):
        """The received tree applies the same rule as the trigger side.

        A signatory to active embargo A rejecting proposed revision B refuses
        B only: B leaves its list, its state stays AGREED (ADR-0093), and
        the handler reports the Reject as applied.
        """
        dl = _make_dl(actor_id=_COORD)
        case_id = "https://example.org/cases/addressee10"
        active_id = f"{case_id}/embargos/active"
        _case, _active, _coord_p_id, invitee_p_id = self._seed_case(
            dl,
            case_id,
            active_id,
            invitee_consent=EmbargoConsentState.AGREED,
            embargo_is="active",
        )
        revision = as_EmbargoEvent(
            id_=f"{case_id}/embargos/revision",
            context=case_id,
            end_time=days_from_now_utc(90),
        )
        dl.create(revision)
        case_obj = cast(VulnerabilityCase, dl.read(case_id))
        propose(case_obj, revision.id_)
        dl.save(case_obj)
        write_consent_rows(dl, case_obj)
        invitee = self._read_participant(dl, invitee_p_id)
        invitee.apply_pec_transition(
            revision.id_,
            PEC_Trigger.AGREE,
            entry_status=case_obj.embargo_register_status(revision.id_),
        )
        dl.save(invitee)

        proposal = em_propose_embargo_activity(
            embargo=revision,
            context=case_id,
            actor=_COORD,
            to=[_INVITEE],
            id_=f"{case_id}/proposals/revision",
        )
        dl.create(proposal)
        reject = em_reject_embargo_activity(
            proposal=proposal, context=case_id, actor=_INVITEE, to=[_COORD]
        )
        event = make_payload(reject, receiving_actor_id=_COORD)

        result = RejectInviteToEmbargoOnCaseReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert result.disposition is HandlerDisposition.APPLIED
        invitee = self._read_participant(dl, invitee_p_id)
        assert invitee.is_signatory(active_id)
        assert invitee.consent_for(active_id) == EmbargoConsentState.AGREED
        assert (
            invitee.consent_for(revision.id_) == EmbargoConsentState.DECLINED
        )
        # A participant's Reject is consent, not a decision (EP-08-003).
        case_after = cast(VulnerabilityCase, dl.read(case_id))
        assert case_after.proposed_embargo_ids == [revision.id_]

    @pytest.mark.spec("MSM-07-004")
    def test_owner_reject_of_a_revision_changes_no_record_on_receipt(
        self, make_payload
    ):
        """The owner's EJ received here decides the proposal and moves no consent.

        The coordinator owns the case (``attributed_to``): its Reject of
        proposed B prunes B from the open-proposal records, returns EM
        ``REVISE → ACTIVE`` (EJ), and leaves every participant's state and
        list as they were — the owner's included.
        """
        dl = _make_dl(actor_id=_COORD)
        case_id = "https://example.org/cases/addressee11"
        active_id = f"{case_id}/embargos/active"
        _case, _active, coord_p_id, invitee_p_id = self._seed_case(
            dl,
            case_id,
            active_id,
            invitee_consent=EmbargoConsentState.AGREED,
            embargo_is="active",
            invitee_accepted=(active_id,),
        )
        revision = as_EmbargoEvent(
            id_=f"{case_id}/embargos/revision",
            context=case_id,
            end_time=days_from_now_utc(90),
        )
        dl.create(revision)
        case_obj = cast(VulnerabilityCase, dl.read(case_id))
        # An open revision of the active embargo puts the case in REVISE.
        propose(case_obj, revision.id_)
        case_obj.pending_embargo_proposal_index = {
            revision.id_: f"{case_id}/proposals/revision"
        }
        dl.save(case_obj)
        write_consent_rows(dl, case_obj)
        coord = self._read_participant(dl, coord_p_id)
        coord.apply_pec_transition(
            active_id,
            PEC_Trigger.AGREE,
            entry_status=case_obj.embargo_register_status(active_id),
        )
        dl.save(coord)

        proposal = em_propose_embargo_activity(
            embargo=revision,
            context=case_id,
            actor=_INVITEE,
            to=[_COORD],
            id_=f"{case_id}/proposals/revision",
        )
        dl.create(proposal)
        reject = em_reject_embargo_activity(
            proposal=proposal, context=case_id, actor=_COORD, to=[_INVITEE]
        )
        event = make_payload(reject, receiving_actor_id=_COORD)

        result = RejectInviteToEmbargoOnCaseReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert result.disposition is HandlerDisposition.APPLIED
        coord = self._read_participant(dl, coord_p_id)
        assert coord.embargo_consents == [
            EmbargoConsent(
                embargo_id=active_id, state=EmbargoConsentState.AGREED
            ),
            EmbargoConsent(
                embargo_id=revision.id_, state=EmbargoConsentState.UNINVITED
            ),
        ]
        invitee = self._read_participant(dl, invitee_p_id)
        assert invitee.embargo_consents == [
            EmbargoConsent(
                embargo_id=active_id, state=EmbargoConsentState.AGREED
            ),
            EmbargoConsent(
                embargo_id=revision.id_, state=EmbargoConsentState.UNINVITED
            ),
        ]
        case_after = cast(VulnerabilityCase, dl.read(case_id))
        assert case_after.proposed_embargo_ids == []
        assert case_after.pending_embargo_proposal_index == {}
        assert case_after.active_embargo_id == active_id
        # EJ: the owner keeps the prior terms (MSM-07-004).
        assert case_after.current_status.em.state == EM.ACTIVE

    def test_reject_naming_an_unknown_embargo_is_refused(self, make_payload):
        """A Reject of an embargo the case has never seen is a protocol error.

        Neither active nor proposed: no consent changes and the handler
        reports a refusal rather than guessing which terms were meant.
        """
        dl = _make_dl(actor_id=_COORD)
        case_id = "https://example.org/cases/addressee12"
        embargo_id = f"{case_id}/embargos/stranger"
        _case, embargo, _coord_p_id, invitee_p_id = self._seed_case(
            dl,
            case_id,
            embargo_id,
            invitee_consent=EmbargoConsentState.INVITED,
            embargo_is="unknown",
        )

        proposal = em_propose_embargo_activity(
            embargo=embargo,
            context=case_id,
            actor=_COORD,
            to=[_INVITEE],
            id_=f"{case_id}/proposals/p1",
        )
        dl.create(proposal)
        reject = em_reject_embargo_activity(
            proposal=proposal, context=case_id, actor=_INVITEE, to=[_COORD]
        )
        event = make_payload(reject, receiving_actor_id=_COORD)

        result = RejectInviteToEmbargoOnCaseReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert result.disposition is HandlerDisposition.REFUSED
        assert "neither the active" in (result.reason or "")
        invitee = self._read_participant(dl, invitee_p_id)
        assert invitee.consent_for(embargo_id) == EmbargoConsentState.INVITED

    @pytest.mark.spec("HP-01-003")
    def test_reject_of_an_unknown_embargo_from_a_declined_invitee_is_still_refused(
        self, make_payload
    ):
        """SKIPPED is keyed on the node's repeat verdict, not on the store.

        A DECLINED invitee's Reject of an embargo the case has never seen is
        a protocol error, not a duplicate of its earlier decline.
        """
        dl = _make_dl(actor_id=_COORD)
        case_id = "https://example.org/cases/addressee13"
        embargo_id = f"{case_id}/embargos/stranger"
        _case, embargo, _coord_p_id, invitee_p_id = self._seed_case(
            dl,
            case_id,
            embargo_id,
            invitee_consent=EmbargoConsentState.DECLINED,
            embargo_is="unknown",
        )

        proposal = em_propose_embargo_activity(
            embargo=embargo,
            context=case_id,
            actor=_COORD,
            to=[_INVITEE],
            id_=f"{case_id}/proposals/p1",
        )
        dl.create(proposal)
        reject = em_reject_embargo_activity(
            proposal=proposal, context=case_id, actor=_INVITEE, to=[_COORD]
        )
        event = make_payload(reject, receiving_actor_id=_COORD)

        result = RejectInviteToEmbargoOnCaseReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert result.disposition is HandlerDisposition.REFUSED
        assert "neither the active" in (result.reason or "")
        invitee = self._read_participant(dl, invitee_p_id)
        assert invitee.consent_for(embargo_id) == EmbargoConsentState.DECLINED

    @pytest.mark.spec("HP-01-003")
    def test_reject_from_declined_is_skipped(self, make_payload):
        """A second Reject from an already-DECLINED invitee changes nothing.

        DECLINE is not a legal consent trigger from DECLINED, so the tree fails.
        That failure is a duplicate, not a refusal of the message (#2255).
        """
        dl = _make_dl(actor_id=_COORD)
        case_id = "https://example.org/cases/addressee9"
        embargo_id = "https://example.org/cases/addressee9/embargos/e9"
        case, embargo, _, invitee_p_id = self._seed_case(
            dl,
            case_id,
            embargo_id,
            invitee_consent=EmbargoConsentState.DECLINED,
        )

        proposal = em_propose_embargo_activity(
            embargo=embargo,
            context=case.id_,
            actor=_COORD,
            to=[_INVITEE],
            id_=f"{case_id}/proposals/p1",
        )
        dl.create(proposal)
        reject = em_reject_embargo_activity(
            proposal=proposal, context=case.id_, actor=_INVITEE, to=[_COORD]
        )
        event = make_payload(reject, receiving_actor_id=_COORD)

        result = RejectInviteToEmbargoOnCaseReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert result.disposition is HandlerDisposition.SKIPPED
        assert "already declined" in (result.reason or "")
        invitee = self._read_participant(dl, invitee_p_id)
        assert invitee.consent_for(embargo_id) == EmbargoConsentState.DECLINED

    @pytest.mark.spec("HP-01-003")
    @pytest.mark.spec("EP-09-003")
    def test_a_second_invite_to_an_invited_participant_is_answered(
        self, make_payload
    ):
        """A new Invite to an already-INVITED invitee is answered, not skipped.

        The replica writes no consent on receipt (EP-09-003), so there is no
        "already invited" no-op to report: a different Invite — a re-proposal
        or counter — is a new question, and the invitee answers it.  A
        redelivery of the *same* Invite is still a SKIPPED repeat
        (CLP-13-001).  Delivered into the invitee's store: at the CASE_MANAGER
        the same message is a proposal to adjudicate and relay (EP-09-001).
        """
        dl = _make_dl(actor_id=_INVITEE)
        case_id = "https://example.org/cases/addressee10"
        embargo_id = "https://example.org/cases/addressee10/embargos/e10"
        case, embargo, _, invitee_p_id = self._seed_case(
            dl,
            case_id,
            embargo_id,
            invitee_consent=EmbargoConsentState.INVITED,
        )

        invite = em_propose_embargo_activity(
            embargo=embargo,
            context=case.id_,
            actor=_COORD,
            to=[_INVITEE],
            rsvp_deadline=_FUTURE,
        )
        event = make_payload(invite, receiving_actor_id=_INVITEE)

        result = InviteToEmbargoOnCaseReceivedUseCase(
            dl,
            event,
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        assert result.disposition is HandlerDisposition.APPLIED
        invitee = self._read_participant(dl, invitee_p_id)
        assert invitee.consent_for(embargo_id) == EmbargoConsentState.INVITED
        assert _answers_in_outbox(dl, _INVITEE) == ["Accept"]

        again = InviteToEmbargoOnCaseReceivedUseCase(
            dl,
            make_payload(invite, receiving_actor_id=_INVITEE),
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        assert again.disposition is HandlerDisposition.SKIPPED
        assert _answers_in_outbox(dl, _INVITEE) == ["Accept"]


class TestInviteeIdProperty:
    """Unit tests for the ``to:``-derived invitee accessors."""

    def _event(self, make_payload, to):
        embargo = as_EmbargoEvent(
            id_="https://example.org/cases/prop/embargos/e1",
            context="https://example.org/cases/prop",
            end_time=days_from_now_utc(45),
        )
        invite = em_propose_embargo_activity(
            embargo=embargo,
            context="https://example.org/cases/prop",
            actor=_COORD,
            to=to,
        )
        return make_payload(invite)

    @pytest.mark.spec("EP-09-010")
    def test_sole_recipient_is_the_invitee(self, make_payload):
        """The invitee is the Invite's sole ``to`` recipient (EP-09-010)."""
        event = self._event(make_payload, [_INVITEE])
        assert event.to_recipients == [_INVITEE]
        assert event.invitee_id == _INVITEE

    def test_multiple_recipients_are_a_misrouting(self, make_payload):
        event = self._event(make_payload, [_INVITEE, _OTHER])
        assert event.to_recipients == [_INVITEE, _OTHER]
        # A misrouting (EP-09-010): no invitee, never a guess.
        assert event.invitee_id is None

    def test_no_recipient_yields_none(self, make_payload):
        event = self._event(make_payload, None)
        assert event.to_recipients == []
        assert event.invitee_id is None

    @pytest.mark.spec("EP-09-010")
    @pytest.mark.parametrize(
        "to",
        [[_INVITEE, _INVITEE], [_INVITEE, _INVITEE + "/"]],
        ids=["repeated", "two-spellings"],
    )
    def test_one_actor_named_twice_is_one_recipient(self, make_payload, to):
        """Two entries naming one actor are one recipient, not a misrouting."""
        event = self._event(make_payload, to)
        assert event.to_recipients == [_INVITEE]
        assert event.invitee_id == _INVITEE
        assert resolve_invitee_id(event, "invite") == _INVITEE

    def test_falsy_recipients_are_dropped(self, make_payload):
        event = self._event(make_payload, ["", _INVITEE])
        assert event.to_recipients == [_INVITEE]
        assert event.invitee_id == _INVITEE

    @pytest.mark.spec("EP-09-010")
    def test_resolver_returns_the_canonical_sole_recipient(self, make_payload):
        event = self._event(make_payload, [_INVITEE + "/"])
        assert resolve_invitee_id(event, "invite") == _INVITEE

    @pytest.mark.spec("EP-09-010")
    @pytest.mark.parametrize(
        ("to", "count"),
        [(None, 0), ([_INVITEE, _OTHER], 2)],
        ids=["no-recipient", "two-recipients"],
    )
    def test_resolver_raises_naming_the_recipient_count(
        self, make_payload, to, count
    ):
        event = self._event(make_payload, to)
        with pytest.raises(
            VultronProtocolViolationError,
            match=f"names {count} 'to' recipients",
        ):
            resolve_invitee_id(event, "invite")


# ---------------------------------------------------------------------------
# Integration tests — AcceptInviteToEmbargoOnCaseReceivedUseCase (EMB-17)
# ---------------------------------------------------------------------------


def _make_accept_event(proposal, case, accepting_actor_id: str, make_payload):
    accept = em_accept_embargo_activity(
        proposal=proposal,
        context=case.id_,
        actor=accepting_actor_id,
        to=[_COORD],
    )
    return make_payload(accept, receiving_actor_id=_COORD)


class TestAcceptWhenTheReplacedEmbargoIsUnreadable:
    """A store missing embargo A breaks EMB-18-003: the Accept is refused."""

    @pytest.mark.spec("HP-01-003")
    @pytest.mark.spec("EMB-18-003")
    @pytest.mark.spec("EP-05-001")
    def test_owner_accept_of_a_revision_is_refused_as_an_invariant_violation(
        self, make_payload, caplog: pytest.LogCaptureFixture
    ):
        """No path may leave a case naming an unreadable embargo (EMB-18-003).

        Nothing would re-drive a parked Accept, so the handler refuses it
        (never DEFERRED), the node logs the broken invariant at ERROR naming
        the case and the missing embargo, and EM and the active embargo are
        left as they were.
        """
        dl = _make_dl(actor_id=_COORD)
        case_id = "https://example.org/cases/ea-gap"
        missing_id = f"{case_id}/embargos/not-replicated"
        case = VulnerabilityCase(
            id_=case_id, name="Replica gap", attributed_to=_COORD
        )
        activate(case, missing_id)
        revision = as_EmbargoEvent(
            id_=f"{case_id}/embargos/e2",
            context=case_id,
            end_time=days_from_now_utc(90),
        )
        propose(case, revision.id_)
        coord_cp = WireCP(
            attributed_to=_COORD,
            context=case_id,
            embargo_consents=_rows({missing_id: EmbargoConsentState.AGREED}),
            case_roles=[CVDRole.CASE_MANAGER],
        )
        dl.create(case)
        dl.create(revision)
        dl.create(coord_cp)
        case.actor_participant_index[_COORD] = coord_cp.id_
        dl.save(case)

        proposal = em_propose_embargo_activity(
            embargo=revision,
            context=case_id,
            actor=_INVITEE,
            to=[_COORD],
            id_=f"{case_id}/proposals/p2",
        )
        dl.create(proposal)
        event = _make_accept_event(proposal, case, _COORD, make_payload)

        with caplog.at_level(logging.ERROR):
            result = AcceptInviteToEmbargoOnCaseReceivedUseCase(
                dl,
                event,
                wire_render_port=As2WireRenderAdapter(),
                sync_port=SyncActivityAdapter(dl),
            ).execute()

        assert result.disposition is HandlerDisposition.REFUSED
        assert "Invariant violation" in (result.reason or "")
        errors = [
            r.getMessage()
            for r in caplog.records
            if r.levelno == logging.ERROR
            and "Invariant violation" in r.getMessage()
        ]
        assert len(errors) == 1
        assert case_id in errors[0]
        assert missing_id in errors[0]
        fresh = cast(CoreCase, dl.read(case_id))
        assert fresh.current_status.em.state == EM.REVISE
        assert fresh.active_embargo_id == missing_id
        assert fresh.proposed_embargo_ids == [revision.id_]


class TestAssessAndRecordInviteExpiry:
    """``assess_invite_expiry`` is read-only; ``record_invite_expiry`` is the effect.

    The guard → commit → effect pattern (CLP-10-006) requires that the assess
    step make no writes and the record step only run after a successful commit.
    """

    @pytest.mark.spec("CLP-10-006", "BT-06-006")
    def test_assess_returns_is_expired_needs_apply_for_invited_past_deadline(
        self,
    ):
        """assess_invite_expiry returns (True, True) for an INVITED invitee past deadline."""
        dl = _make_dl()
        case_id = "https://example.org/cases/assess1"
        embargo_id = f"{case_id}/embargos/e1"
        _make_active_embargo_case(
            dl,
            case_id,
            embargo_id,
            invitee_consent=EmbargoConsentState.INVITED,
            invitee_deadline=_PAST,
        )
        is_expired, needs_apply = EmbargoLifecycle(
            persistence=dl
        ).assess_invite_expiry(
            case_id=case_id,
            actor_id=_INVITEE,
            embargo_id=embargo_id,
            now=_NOW,
        )
        assert is_expired is True
        assert needs_apply is True
        # No participant write happened
        case = dl.read(case_id)
        assert isinstance(case, CoreCase)
        p = dl.read(case.actor_participant_index[_INVITEE])
        assert isinstance(p, CaseParticipant)
        assert (
            p.consent_for(embargo_id) == EmbargoConsentState.INVITED
        )  # unchanged

    @pytest.mark.spec("CLP-10-006", "BT-06-006")
    def test_assess_returns_is_expired_false_for_invited_future_deadline(self):
        """assess_invite_expiry returns (False, False) when deadline is in the future."""
        dl = _make_dl()
        case_id = "https://example.org/cases/assess2"
        embargo_id = f"{case_id}/embargos/e1"
        _make_active_embargo_case(
            dl,
            case_id,
            embargo_id,
            invitee_consent=EmbargoConsentState.INVITED,
            invitee_deadline=_FUTURE,
        )
        is_expired, needs_apply = EmbargoLifecycle(
            persistence=dl
        ).assess_invite_expiry(
            case_id=case_id,
            actor_id=_INVITEE,
            embargo_id=embargo_id,
            now=_NOW,
        )
        assert is_expired is False
        assert needs_apply is False

    @pytest.mark.spec("CLP-10-006", "BT-06-006", "ADR-0118")
    def test_assess_reads_nothing_expired_on_a_timed_out_row(
        self,
    ):
        """assess_invite_expiry returns (False, False) for a row already TIMED_OUT.

        The deadline belongs to the INVITED row and is dropped when the row
        times out (CM-28-013, ADR-0122), so there is no invitation left to
        judge and nothing to apply.
        """
        dl = _make_dl()
        case_id = "https://example.org/cases/assess3"
        embargo_id = f"{case_id}/embargos/e1"
        _make_active_embargo_case(
            dl,
            case_id,
            embargo_id,
            invitee_consent=EmbargoConsentState.TIMED_OUT,
            invitee_deadline=_PAST,
        )
        is_expired, needs_apply = EmbargoLifecycle(
            persistence=dl
        ).assess_invite_expiry(
            case_id=case_id,
            actor_id=_INVITEE,
            embargo_id=embargo_id,
            now=_NOW,
        )
        assert is_expired is False
        assert needs_apply is False  # already timed out, nothing to apply

    @pytest.mark.spec("CLP-10-006", "BT-06-006")
    def test_record_invite_expiry_applies_after_assess(self):
        """record_invite_expiry moves INVITED → TIMED_OUT (the effect step)."""
        dl = _make_dl()
        case_id = "https://example.org/cases/record1"
        embargo_id = f"{case_id}/embargos/e1"
        _make_active_embargo_case(
            dl,
            case_id,
            embargo_id,
            invitee_consent=EmbargoConsentState.INVITED,
            invitee_deadline=_PAST,
        )
        svc = EmbargoLifecycle(persistence=dl)
        result = svc.record_invite_expiry(
            case_id=case_id, actor_id=_INVITEE, embargo_id=embargo_id
        )
        assert result.is_expired is True
        assert len(result.participant_changes) == 1
        change = result.participant_changes[0]
        assert change.embargo_id == embargo_id
        assert change.consent_before == EmbargoConsentState.INVITED.value
        assert change.consent_after == EmbargoConsentState.TIMED_OUT.value
        # Persisted
        case = dl.read(case_id)
        assert isinstance(case, CoreCase)
        p = dl.read(case.actor_participant_index[_INVITEE])
        assert isinstance(p, CaseParticipant)
        assert p.consent_for(embargo_id) == EmbargoConsentState.TIMED_OUT

    @pytest.mark.spec("CLP-10-006", "BT-06-006")
    def test_failed_commit_leaves_invitee_invited(self, monkeypatch):
        """A failed commit in create_invite_expiry_tree leaves the invitee INVITED.

        The tree uses guard → commit → effect.  If the commit node fails, the
        effect node (RecordInviteExpiryNode) must not run, so the invitee stays
        in INVITED state rather than TIMED_OUT (CLP-10-006, BT-06-006).
        """
        from unittest.mock import patch

        from vultron.core.behaviors.bridge import BTBridge
        from vultron.core.behaviors.embargo.expiry_tree import (
            create_invite_expiry_tree,
        )

        dl = _make_dl()
        case_id = "https://example.org/cases/fail-commit"
        embargo_id = f"{case_id}/embargos/e1"
        _make_active_embargo_case(
            dl,
            case_id,
            embargo_id,
            invitee_consent=EmbargoConsentState.INVITED,
            invitee_deadline=_PAST,
        )

        # Simulate a commit failure by making the ledger write raise.
        from vultron.core.behaviors.sync import commit_tree as _ct_module

        def _failing_commit(*args, **kwargs):
            """Return a tree whose only node always fails."""
            import py_trees

            class _Fail(py_trees.behaviour.Behaviour):
                def update(self):
                    return py_trees.common.Status.FAILURE

            return _Fail(name="FailingCommitSim")

        with patch.object(
            _ct_module, "create_commit_log_entry_tree", _failing_commit
        ):
            # Rebuild tree with patched commit
            result_out2: dict = {}
            tree2 = create_invite_expiry_tree(
                case_id=case_id,
                invitee_id=_INVITEE,
                invite_id=f"{case_id}/invites/i1",
                embargo_id=embargo_id,
                published="2026-01-01T00:00:00Z",
                now=_NOW,
                result_out=result_out2,
            )
            BTBridge(datalayer=dl).execute_with_setup(
                tree=tree2, actor_id=_COORD
            )

        # The invitee must still be INVITED — no effect was applied.
        case2 = dl.read(case_id)
        assert isinstance(case2, CoreCase)
        p = dl.read(case2.actor_participant_index[_INVITEE])
        assert isinstance(p, CaseParticipant)
        assert p.consent_for(embargo_id) == EmbargoConsentState.INVITED, (
            "Failed commit must leave invitee INVITED, not TIMED_OUT (CLP-10-006)"
        )


class TestHonourLateAcceptService:
    """``honour_late_accept`` applies TIMED_OUT/DECLINED → AGREED via the service."""

    @pytest.mark.spec("EMB-17-001", "ADR-0118")
    def test_expired_participant_becomes_signatory(self):
        """TIMED_OUT → AGREED in a single step; the invitee is then a signatory."""
        dl = _make_dl()
        case_id = "https://example.org/cases/honour-expired"
        embargo_id = f"{case_id}/embargos/e1"
        _make_active_embargo_case(
            dl,
            case_id,
            embargo_id,
            invitee_consent=EmbargoConsentState.TIMED_OUT,
            invitee_deadline=_PAST,
        )
        result = EmbargoLifecycle(persistence=dl).honour_late_accept(
            case_id=case_id, actor_id=_INVITEE, embargo_id=embargo_id
        )
        assert any(
            c.embargo_id == embargo_id
            and c.consent_after == EmbargoConsentState.AGREED.value
            for c in result.participant_changes
        )
        case = dl.read(case_id)
        assert isinstance(case, CoreCase)
        p = dl.read(case.actor_participant_index[_INVITEE])
        assert isinstance(p, CaseParticipant)
        assert p.consent_for(embargo_id) == EmbargoConsentState.AGREED

    @pytest.mark.spec("EMB-17-001", "CM-18-003", "ADR-0118")
    def test_declined_participant_becomes_signatory_via_invite(self):
        """DECLINED → INVITED → AGREED (CM-18-003: AGREE not legal from DECLINED)."""
        dl = _make_dl()
        case_id = "https://example.org/cases/honour-declined"
        embargo_id = f"{case_id}/embargos/e1"
        _make_active_embargo_case(
            dl,
            case_id,
            embargo_id,
            invitee_consent=EmbargoConsentState.DECLINED,
            invitee_deadline=_PAST,
        )
        result = EmbargoLifecycle(persistence=dl).honour_late_accept(
            case_id=case_id, actor_id=_INVITEE, embargo_id=embargo_id
        )
        consent_states = [
            c.consent_before for c in result.participant_changes
        ] + [c.consent_after for c in result.participant_changes]
        assert EmbargoConsentState.DECLINED.value in consent_states
        case = dl.read(case_id)
        assert isinstance(case, CoreCase)
        p = dl.read(case.actor_participant_index[_INVITEE])
        assert isinstance(p, CaseParticipant)
        assert p.consent_for(embargo_id) == EmbargoConsentState.AGREED

    @pytest.mark.spec("EMB-17-001", "ADR-0118")
    def test_signatory_is_unchanged_idempotent(self):
        """A participant already AGREED is not changed by honour_late_accept."""
        dl = _make_dl()
        case_id = "https://example.org/cases/honour-signatory"
        embargo_id = f"{case_id}/embargos/e1"
        _make_active_embargo_case(
            dl,
            case_id,
            embargo_id,
            invitee_consent=EmbargoConsentState.AGREED,
        )
        result = EmbargoLifecycle(persistence=dl).honour_late_accept(
            case_id=case_id, actor_id=_INVITEE, embargo_id=embargo_id
        )
        # No state change — already AGREED
        assert result.participant_changes == []
        case = dl.read(case_id)
        assert isinstance(case, CoreCase)
        p = dl.read(case.actor_participant_index[_INVITEE])
        assert isinstance(p, CaseParticipant)
        assert p.consent_for(embargo_id) == EmbargoConsentState.AGREED


class TestLateAcceptHandling:
    """EMB-17: late-Accept compatibility routing."""

    def test_late_accept_honored_when_embargo_current(self, make_payload):
        """Late Accept with matching active embargo → the invitee a signatory (AC-2 #2213)."""
        dl = _make_dl(actor_id=_COORD)
        case_id = "https://example.org/cases/ea1"
        embargo_id = "https://example.org/cases/ea1/embargos/e1"

        case, embargo, _ = _make_active_embargo_case(
            dl,
            case_id,
            embargo_id,
            invitee_consent=EmbargoConsentState.INVITED,
            invitee_deadline=_PAST,
        )

        proposal = em_propose_embargo_activity(
            embargo=embargo,
            context=case.id_,
            actor=_COORD,
            to=[_INVITEE],
            id_=f"{case_id}/proposals/p1",
        )
        dl.create(proposal)

        event = _make_accept_event(proposal, case, _INVITEE, make_payload)
        AcceptInviteToEmbargoOnCaseReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        fresh_case = dl.read(case_id)
        assert isinstance(fresh_case, CoreCase)
        p_id = fresh_case.actor_participant_index[_INVITEE]
        participant = dl.read(p_id)
        assert isinstance(participant, CaseParticipant)
        assert (
            participant.consent_for(embargo_id) == EmbargoConsentState.AGREED
        )

    @pytest.mark.spec("EMB-17-002", "CM-18-003")
    @pytest.mark.parametrize(
        "start, triggers",
        [
            (EmbargoConsentState.TIMED_OUT, [PEC_Trigger.AGREE]),
        ],
        ids=["timed-out-agrees-directly"],
    )
    def test_late_accept_reaches_signatory_by_the_legal_path(
        self, make_payload, monkeypatch, start, triggers
    ):
        """A TIMED_OUT participant agrees directly, with no INVITE first.

        ``AGREE`` is legal from ``TIMED_OUT`` (ADR-0118).  A ``DECLINED`` row
        carries no outstanding invitation, so its Accept is not a late one;
        see :meth:`test_accept_from_a_declined_row_records_nothing`.
        """
        from vultron.core.models.case_participant import (
            CaseParticipant as _CoreParticipant,
        )

        applied: list[PEC_Trigger] = []
        original = _CoreParticipant.apply_pec_transition

        def _spy(self, embargo_id, trigger, *args, **kwargs):
            applied.append(trigger)
            return original(self, embargo_id, trigger, *args, **kwargs)

        monkeypatch.setattr(_CoreParticipant, "apply_pec_transition", _spy)

        dl = _make_dl(actor_id=_COORD)
        case_id = f"https://example.org/cases/late-{start.value.lower()}"
        embargo_id = f"{case_id}/embargos/e1"
        case, embargo, _ = _make_active_embargo_case(
            dl,
            case_id,
            embargo_id,
            invitee_consent=start,
            invitee_deadline=_PAST,
        )
        proposal = em_propose_embargo_activity(
            embargo=embargo,
            context=case.id_,
            actor=_COORD,
            to=[_INVITEE],
            id_=f"{case_id}/proposals/p1",
        )
        dl.create(proposal)

        event = _make_accept_event(proposal, case, _INVITEE, make_payload)
        applied.clear()
        AcceptInviteToEmbargoOnCaseReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        fresh_case = dl.read(case_id)
        assert isinstance(fresh_case, CoreCase)
        participant = dl.read(fresh_case.actor_participant_index[_INVITEE])
        assert isinstance(participant, CaseParticipant)
        assert (
            participant.consent_for(embargo_id) == EmbargoConsentState.AGREED
        )
        assert [t for t in applied if t in triggers] == triggers
        if start is EmbargoConsentState.TIMED_OUT:
            assert PEC_Trigger.INVITE not in applied

    @pytest.mark.spec("CM-18-003")
    def test_accept_from_a_declined_row_records_nothing(self, make_payload):
        """A participant that declined is invited again before it can agree.

        ``AGREE`` refuses ``DECLINED`` (ADR-0122), and a declined row carries
        no RSVP deadline, so its Accept is not routed as a late one (EMB-17):
        the row stays ``DECLINED`` and the participant is not a signatory.
        """
        dl = _make_dl(actor_id=_COORD)
        case_id = "https://example.org/cases/late-declined"
        embargo_id = f"{case_id}/embargos/e1"
        case, embargo, _ = _make_active_embargo_case(
            dl,
            case_id,
            embargo_id,
            invitee_consent=EmbargoConsentState.DECLINED,
        )
        proposal = em_propose_embargo_activity(
            embargo=embargo,
            context=case.id_,
            actor=_COORD,
            to=[_INVITEE],
            id_=f"{case_id}/proposals/p1",
        )
        dl.create(proposal)

        AcceptInviteToEmbargoOnCaseReceivedUseCase(
            dl,
            _make_accept_event(proposal, case, _INVITEE, make_payload),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        fresh_case = cast(CoreCase, dl.read(case_id))
        participant = cast(
            CaseParticipant,
            dl.read(fresh_case.actor_participant_index[_INVITEE]),
        )
        assert (
            participant.consent_for(embargo_id) == EmbargoConsentState.DECLINED
        )
        assert not participant.is_signatory(fresh_case.active_embargo_id)

    @pytest.mark.spec("EMB-17-003")
    @pytest.mark.parametrize(
        "stale_deadline",
        [_PAST, _FUTURE],
        ids=["deadline-passed", "deadline-open"],
    )
    def test_late_accept_reinvite_when_stale_embargo(
        self, make_payload, stale_deadline
    ):
        """An Accept of stale terms → re-invite with the current embargo.

        AC-3 of #2213, and AC-5 of #4291: the stale entry is final, so its
        invitation is closed whether or not its own deadline has passed.
        """
        from unittest.mock import MagicMock

        dl = _make_dl(actor_id=_COORD)
        case_id = "https://example.org/cases/ea2"
        current_embargo_id = "https://example.org/cases/ea2/embargos/current"
        stale_embargo_id = "https://example.org/cases/ea2/embargos/stale"

        # The invitee was invited to the stale embargo, which a revision
        # (the current one) has since superseded: its row for the stale entry
        # is frozen at INVITED with the passed deadline (ADR-0122).
        case, stale_embargo, _ = _make_active_embargo_case(
            dl,
            case_id,
            stale_embargo_id,
            invitee_consent=EmbargoConsentState.INVITED,
            invitee_deadline=stale_deadline,
        )
        activate(case, current_embargo_id)
        dl.save(case)
        write_consent_rows(dl, case)
        dl.create(
            as_EmbargoEvent(
                id_=current_embargo_id,
                context=case_id,
                end_time=days_from_now_utc(30),
            )
        )

        # Proposal was for the stale embargo
        stale_proposal = em_propose_embargo_activity(
            embargo=stale_embargo,
            context=case.id_,
            actor=_COORD,
            to=[_INVITEE],
            id_=f"{case_id}/proposals/stale",
        )
        dl.create(stale_proposal)

        # Mock trigger_activity to capture re-invite call
        trigger_mock = MagicMock()
        new_invite_id = f"{case_id}/proposals/reinvite"

        def _sealed_invite(**kwargs: Any) -> tuple[str, str]:
            """What the factory returns: the id and the sealed Invite body."""
            return new_invite_id, json.dumps(
                {
                    "id": new_invite_id,
                    "type": "Invite",
                    "actor": kwargs["actor"],
                    "to": kwargs["to"],
                    "context": kwargs["case_id"],
                    "published": kwargs["published"].isoformat(),
                    "endTime": kwargs["rsvp_deadline"].isoformat(),
                    "object": {
                        "type": "EmbargoEvent",
                        "id": kwargs["embargo_id"],
                    },
                }
            )

        trigger_mock.propose_embargo.side_effect = _sealed_invite

        event = _make_accept_event(
            stale_proposal, case, _INVITEE, make_payload
        )
        AcceptInviteToEmbargoOnCaseReceivedUseCase(
            dl,
            event,
            trigger_activity=trigger_mock,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        # propose_embargo should have been called with the CURRENT embargo
        trigger_mock.propose_embargo.assert_called_once()
        call_kwargs = trigger_mock.propose_embargo.call_args
        assert (
            call_kwargs.kwargs.get("embargo_id") == current_embargo_id
            or call_kwargs.args[0] == current_embargo_id
        )

        # The re-invite carries its own fresh deadline (ASK-03-004, CM-28-012).
        stamped = call_kwargs.kwargs.get("rsvp_deadline")
        published = call_kwargs.kwargs.get("published")
        assert isinstance(stamped, datetime)
        assert isinstance(published, datetime)
        assert stamped - published == timedelta(days=7)

        # Invitee consent should be INVITED (re-invited to current embargo), and
        # its record takes the re-invite's deadline, not the lapsed one.
        fresh_case = dl.read(case_id)
        assert isinstance(fresh_case, CoreCase)
        p_id = fresh_case.actor_participant_index[_INVITEE]
        participant = dl.read(p_id)
        assert isinstance(participant, CaseParticipant)
        assert (
            participant.consent_for(current_embargo_id)
            == EmbargoConsentState.INVITED
        )
        assert participant.rsvp_deadline_for(current_embargo_id) == stamped

    @pytest.mark.spec("EMB-17-004")
    def test_late_accept_noop_when_em_exited(self, make_payload):
        """Late Accept after EM EXITED → ack no-op, actor stays in case (AC-4 #2213).

        Termination writes no consent (ADR-0122) and, with no embargo in
        force, nobody is a signatory; once EM is EXITED a late Accept records
        no acceptance, so the invitee never becomes a signatory.
        """
        dl = _make_dl(actor_id=_COORD)
        case_id = "https://example.org/cases/ea3"
        embargo_id = "https://example.org/cases/ea3/embargos/e3"

        case, embargo, _participant_id = _make_active_embargo_case(
            dl,
            case_id,
            embargo_id,
            invitee_consent=EmbargoConsentState.INVITED,
            invitee_deadline=_PAST,
        )
        # Simulate EM EXITED (embargo terminated)
        terminate(case)
        dl.save(case)

        proposal = em_propose_embargo_activity(
            embargo=embargo,
            context=case.id_,
            actor=_COORD,
            to=[_INVITEE],
            id_=f"{case_id}/proposals/p3",
        )
        dl.create(proposal)

        event = _make_accept_event(proposal, case, _INVITEE, make_payload)
        AcceptInviteToEmbargoOnCaseReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        # Actor must still be a case participant (not removed)
        fresh_case = dl.read(case_id)
        assert isinstance(fresh_case, CoreCase)
        assert _INVITEE in fresh_case.actor_participant_index

        # Consent is unchanged and nobody is bound (no embargo in force).
        p_id = fresh_case.actor_participant_index[_INVITEE]
        participant = dl.read(p_id)
        assert isinstance(participant, CaseParticipant)
        # The embargo is TERMINATED, so its rows accept no trigger (ADR-0122):
        # the overdue invitation is not timed out, nor honoured; the late
        # Accept signs nothing, and nobody is bound.
        assert (
            participant.consent_for(embargo_id) == EmbargoConsentState.INVITED
        )
        assert not participant.is_signatory(fresh_case.active_embargo_id)

    @pytest.mark.spec("EMB-17-004")
    @pytest.mark.spec("CM-28-004")
    def test_late_accept_with_no_embargo_leaves_the_invitee_row_frozen(
        self, make_payload
    ):
        """Late Accept with EM NONE → an ack no-op, and the frozen row is kept.

        The invitee was invited to a proposal the owner then rejected, so EM
        is ``NONE`` and nothing is in force: the late Accept has nothing to
        sign.  The rejected entry is final, so its rows accept no trigger
        (ADR-0122): the invitation is not timed out and no expiry entry is
        committed; the no-op acknowledgement is (EMB-17-004, EMB-17-010).
        """
        dl = _make_dl(actor_id=_COORD)
        case_id = "https://example.org/cases/ea-none"
        embargo_id = "https://example.org/cases/ea-none/embargos/e1"

        case, embargo, invitee_p_id = _make_active_embargo_case(
            dl,
            case_id,
            embargo_id,
            em_active=False,
        )
        propose(case, embargo_id)
        reject(case, embargo_id)
        dl.save(case)
        invitee = cast(CaseParticipant, dl.read(invitee_p_id))
        invitee.embargo_consents = _rows(
            {embargo_id: EmbargoConsentState.INVITED}, _PAST
        )
        dl.save(invitee)
        assert case.em_state == EM.NONE

        proposal = em_propose_embargo_activity(
            embargo=embargo,
            context=case.id_,
            actor=_COORD,
            to=[_INVITEE],
            id_=f"{case_id}/proposals/p1",
        )
        dl.create(proposal)

        event = _make_accept_event(proposal, case, _INVITEE, make_payload)
        AcceptInviteToEmbargoOnCaseReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        fresh_case = dl.read(case_id)
        assert isinstance(fresh_case, CoreCase)
        participant = dl.read(fresh_case.actor_participant_index[_INVITEE])
        assert isinstance(participant, CaseParticipant)
        assert (
            participant.consent_for(embargo_id) == EmbargoConsentState.INVITED
        )
        event_types = [
            obj.event_type
            for obj in dl.list_objects("CaseLedgerEntry")
            if isinstance(obj, CaseLedgerEntry) and obj.case_id == case_id
        ]
        assert INVITE_EXPIRED_EVENT_TYPE not in event_types
        assert event_types.count(INVITE_EXPIRED_NOOP_EVENT_TYPE) == 1

    def test_late_accept_honored_when_em_revise_with_matching_embargo(
        self, make_payload
    ):
        """Late Accept with matching embargo in EM.REVISE → the invitee a signatory (EMB-17-001/issue #2875).

        When the active embargo ID matches and EM is REVISE (renegotiation in
        progress), the late Accept must be honored (consent recorded, actor
        transitions to AGREED) — not wrongly rerouted as a stale-embargo.
        """
        dl = _make_dl(actor_id=_COORD)
        case_id = "https://example.org/cases/ea-revise"
        embargo_id = "https://example.org/cases/ea-revise/embargos/e1"

        case, embargo, _ = _make_active_embargo_case(
            dl,
            case_id,
            embargo_id,
            invitee_consent=EmbargoConsentState.INVITED,
            invitee_deadline=_PAST,
        )
        # An open revision puts EM in REVISE; the same embargo stays active.
        revision = as_EmbargoEvent(
            id_=f"{case_id}/embargos/e2",
            context=case_id,
            end_time=days_from_now_utc(90),
        )
        dl.create(revision)
        propose(case, revision.id_)
        assert case.em_state == EM.REVISE
        dl.save(case)

        proposal = em_propose_embargo_activity(
            embargo=embargo,
            context=case.id_,
            actor=_COORD,
            to=[_INVITEE],
            id_=f"{case_id}/proposals/p1",
        )
        dl.create(proposal)

        event = _make_accept_event(proposal, case, _INVITEE, make_payload)
        AcceptInviteToEmbargoOnCaseReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        fresh_case = dl.read(case_id)
        assert isinstance(fresh_case, CoreCase)
        p_id = fresh_case.actor_participant_index[_INVITEE]
        participant = dl.read(p_id)
        assert isinstance(participant, CaseParticipant)
        assert (
            participant.consent_for(embargo_id) == EmbargoConsentState.AGREED
        )

    def test_accept_within_deadline_uses_normal_path(self, make_payload):
        """Accept before deadline → normal BT path, signatory without expiry."""
        dl = _make_dl(actor_id=_COORD)
        case_id = "https://example.org/cases/ea4"
        embargo_id = "https://example.org/cases/ea4/embargos/e4"

        # Set up case with PROPOSED EM and vendor participant
        case = VulnerabilityCase(
            id_=case_id, name="Normal Accept", attributed_to=_COORD
        )
        embargo = as_EmbargoEvent(
            id_=embargo_id, context=case_id, end_time=days_from_now_utc(45)
        )
        propose(case, embargo_id)

        invitee_cp = WireCP(
            attributed_to=_INVITEE,
            context=case_id,
            embargo_consents=_rows(
                {embargo_id: EmbargoConsentState.INVITED}, _FUTURE
            ),
            case_roles=[CVDRole.VENDOR],
        )
        invitee_cp_core = invitee_cp

        # The receiver is the CASE_MANAGER (CM-24-006, BT-17-005).
        seed_store_owner_as_case_manager(dl, case)
        dl.create(case)
        dl.create(embargo)
        dl.create(invitee_cp_core)
        case.actor_participant_index[_INVITEE] = invitee_cp_core.id_
        dl.save(case)

        proposal = em_propose_embargo_activity(
            embargo=embargo,
            context=case.id_,
            actor=_INVITEE,
            to=[_COORD],
            id_=f"{case_id}/proposals/p4",
        )
        dl.create(proposal)
        case.pending_embargo_proposal_index[embargo_id] = proposal.id_
        dl.save(case)

        event = _make_accept_event(proposal, case, _COORD, make_payload)
        AcceptInviteToEmbargoOnCaseReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        # Normal path: coordinator accepted → EM ACTIVE
        fresh_case = dl.read(case_id)
        assert isinstance(fresh_case, CoreCase)
        assert fresh_case.current_status.em.state == EM.ACTIVE

    def test_accept_no_deadline_uses_normal_path(self, make_payload):
        """Accept with no deadline → policy window fallback, normal path."""
        dl = _make_dl(actor_id=_COORD)
        case_id = "https://example.org/cases/ea5"
        embargo_id = "https://example.org/cases/ea5/embargos/e5"

        case = VulnerabilityCase(
            id_=case_id, name="No Deadline Accept", attributed_to=_COORD
        )
        embargo = as_EmbargoEvent(
            id_=embargo_id, context=case_id, end_time=days_from_now_utc(45)
        )
        propose(case, embargo_id)

        invitee_cp = WireCP(
            attributed_to=_INVITEE,
            context=case_id,
            embargo_consents=_rows({embargo_id: EmbargoConsentState.INVITED}),
            case_roles=[CVDRole.VENDOR],
        )
        invitee_cp_core = invitee_cp
        # No deadline set — the INVITED row carries none

        # The receiver is the CASE_MANAGER (CM-24-006, BT-17-005).
        seed_store_owner_as_case_manager(dl, case)
        dl.create(case)
        dl.create(embargo)
        dl.create(invitee_cp_core)
        case.actor_participant_index[_INVITEE] = invitee_cp_core.id_
        dl.save(case)

        proposal = em_propose_embargo_activity(
            embargo=embargo,
            context=case.id_,
            actor=_INVITEE,
            to=[_COORD],
            id_=f"{case_id}/proposals/p5",
        )
        dl.create(proposal)
        case.pending_embargo_proposal_index[embargo_id] = proposal.id_
        dl.save(case)

        event = _make_accept_event(proposal, case, _COORD, make_payload)
        AcceptInviteToEmbargoOnCaseReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        # Normal path: no expiry, acceptance proceeds
        fresh_case = dl.read(case_id)
        assert isinstance(fresh_case, CoreCase)
        assert fresh_case.current_status.em.state == EM.ACTIVE

    def test_expiry_creates_distinct_ledger_entry(self, make_payload):
        """Late Accept after expiry creates a ledger entry distinct from Reject (CM-28-009)."""

        dl = _make_dl(actor_id=_COORD)
        case_id = "https://example.org/cases/ea6"
        embargo_id = "https://example.org/cases/ea6/embargos/e6"

        case, embargo, _ = _make_active_embargo_case(
            dl,
            case_id,
            embargo_id,
            invitee_consent=EmbargoConsentState.INVITED,
            invitee_deadline=_PAST,
        )

        proposal = em_propose_embargo_activity(
            embargo=embargo,
            context=case.id_,
            actor=_COORD,
            to=[_INVITEE],
            id_=f"{case_id}/proposals/p6",
        )
        dl.create(proposal)

        event = _make_accept_event(proposal, case, _INVITEE, make_payload)
        AcceptInviteToEmbargoOnCaseReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        # A CaseLedgerEntry with the expiry event type must exist
        # (CM-28-005, CM-28-009, ADR-0118).
        ledger_entries = [
            obj
            for obj in dl.list_objects("CaseLedgerEntry")
            if isinstance(obj, CaseLedgerEntry) and obj.case_id == case_id
        ]
        expiry_entries = [
            e
            for e in ledger_entries
            if e.event_type == INVITE_EXPIRED_EVENT_TYPE
        ]
        assert expiry_entries, (
            "Expected a CaseLedgerEntry with event_type"
            f" '{INVITE_EXPIRED_EVENT_TYPE}' but none found"
        )
        expiry_entry = expiry_entries[0]
        # Entry must be distinguishable from an explicit Reject
        assert expiry_entry.event_type != "reject_invite_to_embargo_on_case"
        # payloadSnapshot must be non-empty (CLP-02-003)
        assert expiry_entry.payload_snapshot

    def test_late_accept_ac2_signatory_participant_no_crash(
        self, make_payload
    ):
        """AC-2: late Accept for current embargo on an AGREED participant must not crash.

        If the participant is already AGREED (reached that state without
        passing through INVITED since the last invite), calling
        record_participant_consent(PEC_Trigger.INVITE) on them would raise
        VultronInvalidStateTransitionError (AGREED → INVITED is illegal,
        CM-18-004).  The use case must guard the INVITE call and stay
        idempotent — participant remains AGREED (issue #3358).
        """
        dl = _make_dl(actor_id=_COORD)
        case_id = "https://example.org/cases/ea-sig-ac2"
        embargo_id = "https://example.org/cases/ea-sig-ac2/embargos/e1"

        # Seed case with an AGREED participant (already accepted the embargo).
        case, embargo, _ = _make_active_embargo_case(
            dl,
            case_id,
            embargo_id,
            invitee_consent=EmbargoConsentState.AGREED,
            invitee_deadline=_PAST,
        )

        proposal = em_propose_embargo_activity(
            embargo=embargo,
            context=case.id_,
            actor=_COORD,
            to=[_INVITEE],
            id_=f"{case_id}/proposals/p-sig-ac2",
        )
        dl.create(proposal)

        event = _make_accept_event(proposal, case, _INVITEE, make_payload)
        # Must not raise VultronInvalidStateTransitionError (bug #3358).
        AcceptInviteToEmbargoOnCaseReceivedUseCase(
            dl,
            event,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        fresh_case = dl.read(case_id)
        assert isinstance(fresh_case, CoreCase)
        p_id = fresh_case.actor_participant_index[_INVITEE]
        participant = dl.read(p_id)
        assert isinstance(participant, CaseParticipant)
        # Idempotent: still AGREED (no state change for already-consenting actor).
        assert (
            participant.consent_for(embargo_id) == EmbargoConsentState.AGREED
        )

    def test_late_accept_ac3_signatory_participant_no_crash(
        self, make_payload
    ):
        """AC-3: late Accept for stale embargo on an AGREED participant must not crash.

        When the participant is already AGREED for the current active embargo
        and sends an Accept for a stale (replaced) embargo, calling
        record_participant_consent(PEC_Trigger.INVITE) on them would crash
        (AGREED → INVITED is illegal).  The use case must skip the re-invite
        and leave the participant AGREED (issue #3358).
        """
        from unittest.mock import MagicMock

        dl = _make_dl(actor_id=_COORD)
        case_id = "https://example.org/cases/ea-sig-ac3"
        current_embargo_id = (
            "https://example.org/cases/ea-sig-ac3/embargos/current"
        )
        stale_embargo_id = (
            "https://example.org/cases/ea-sig-ac3/embargos/stale"
        )

        # Participant is AGREED on the current embargo.
        case, _current_embargo, _ = _make_active_embargo_case(
            dl,
            case_id,
            current_embargo_id,
            invitee_consent=EmbargoConsentState.AGREED,
            invitee_deadline=_PAST,
        )

        stale_embargo = as_EmbargoEvent(
            id_=stale_embargo_id,
            context=case_id,
            end_time=days_from_now_utc(45),
        )
        dl.create(stale_embargo)

        stale_proposal = em_propose_embargo_activity(
            embargo=stale_embargo,
            context=case.id_,
            actor=_COORD,
            to=[_INVITEE],
            id_=f"{case_id}/proposals/stale-sig",
        )
        dl.create(stale_proposal)

        trigger_mock = MagicMock()
        trigger_mock.propose_embargo.return_value = (
            f"{case_id}/proposals/reinvite-sig",
            {},
        )

        event = _make_accept_event(
            stale_proposal, case, _INVITEE, make_payload
        )
        # Must not raise VultronInvalidStateTransitionError (bug #3358).
        AcceptInviteToEmbargoOnCaseReceivedUseCase(
            dl,
            event,
            trigger_activity=trigger_mock,
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        fresh_case = dl.read(case_id)
        assert isinstance(fresh_case, CoreCase)
        p_id = fresh_case.actor_participant_index[_INVITEE]
        participant = dl.read(p_id)
        assert isinstance(participant, CaseParticipant)
        # Already AGREED for current embargo — no re-invite needed.
        assert (
            participant.consent_for(current_embargo_id)
            == EmbargoConsentState.AGREED
        )


class TestExpiryIsTheManagersAlone:
    """CM-28-014: only the CASE_MANAGER evaluates expiry and commits its entry."""

    @pytest.mark.spec("CM-28-014")
    def test_non_manager_commits_no_expiry_entry(self, make_payload):
        """A replica that sees a late Accept writes no expiry entry."""

        dl = _make_dl(actor_id=_OTHER)
        case_id = "https://example.org/cases/lapse-replica"
        embargo_id = f"{case_id}/embargos/e1"
        case, embargo, _participant_id = _make_active_embargo_case(
            dl,
            case_id,
            embargo_id,
            invitee_consent=EmbargoConsentState.INVITED,
            invitee_deadline=_PAST,
        )

        proposal = em_propose_embargo_activity(
            embargo=embargo,
            context=case.id_,
            actor=_COORD,
            to=[_INVITEE],
            id_=f"{case_id}/proposals/p1",
        )
        dl.create(proposal)
        # The replica holds an addressed copy, so the door check (HP-01-005)
        # admits it and the expiry path is what is under test.
        accept = em_accept_embargo_activity(
            proposal=proposal,
            context=case.id_,
            actor=_INVITEE,
            to=[_COORD],
            cc=[_OTHER],
        )
        event = make_payload(accept, receiving_actor_id=_OTHER)

        result = AcceptInviteToEmbargoOnCaseReceivedUseCase(
            dl,
            event,
            sync_port=SyncActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
        ).execute()

        expiry_entries = [
            e
            for e in dl.list_objects("CaseLedgerEntry")
            if isinstance(e, CaseLedgerEntry)
            and e.event_type == INVITE_EXPIRED_EVENT_TYPE
        ]
        assert expiry_entries == []
        # Nor does it compute one: the invitee's consent is left as it was,
        # and the answer is refused as the manager's to adjudicate (HP-01-005).
        participant = dl.read(_participant_id)
        assert isinstance(participant, CaseParticipant)
        assert (
            participant.consent_for(embargo_id) == EmbargoConsentState.INVITED
        )
        assert result.disposition is HandlerDisposition.REFUSED


class TestLapseIsDerived:
    """A lapse is read from the rows and the case, never stored (CM-18-016).

    A signatory to embargo A that holds no AGREED row for the longer
    embargo B activated after it has lapsed: ``has_lapsed`` says so and the
    content gate (``is_active_participant``) excludes it.  Asking it again
    (INVITE) and its acceptance (ACCEPT) make it a signatory to B.
    """

    @staticmethod
    def _case_with_signatory(dl: SqliteDataLayer, active_id: str, a_id: str):
        case_id = "https://example.org/cases/derived-lapse"
        case = VulnerabilityCase(
            id_=case_id, name="Derived lapse", attributed_to=_COORD
        )
        activate(case, active_id)
        signatory = WireCP(
            attributed_to=_INVITEE,
            context=case_id,
            case_roles=[CVDRole.VENDOR],
            embargo_consents=_rows({a_id: EmbargoConsentState.AGREED}),
        )
        dl.create(case)
        dl.create(signatory)
        case.actor_participant_index[_INVITEE] = signatory.id_
        case.case_participants.append(signatory.id_)
        dl.save(case)
        return case, signatory.id_

    @pytest.mark.spec("CM-18-001")
    @pytest.mark.spec("CM-18-016")
    def test_activating_a_longer_embargo_lapses_the_silent_signatory(self):
        """No row for B is written, yet the signatory to A has lapsed and is inert."""
        dl = _make_dl()
        a_id = "https://example.org/cases/derived-lapse/embargos/a"
        b_id = "https://example.org/cases/derived-lapse/embargos/b"
        case, participant_id = self._case_with_signatory(dl, a_id, a_id)
        participant = cast(CaseParticipant, dl.read(participant_id))
        assert participant.is_signatory(case.active_embargo_id)
        assert case.is_active_participant(participant)

        # B is proposed (every participant gets its UNINVITED row, ADR-0122)
        # and activated; the activation writes nothing for the silent
        # signatory.
        participant.write_uninvited_rows([b_id])
        before = list(participant.embargo_consents)
        activate(case, b_id)

        assert participant.embargo_consents == before
        assert participant.consent_for(b_id) == EmbargoConsentState.UNINVITED
        assert participant.has_lapsed(case.embargo_register)
        assert not participant.is_signatory(case.active_embargo_id)
        assert not case.is_active_participant(participant)

    @pytest.mark.spec("CM-18-001")
    @pytest.mark.spec("EP-09-004")
    def test_reinvite_keeps_the_old_row_and_accept_makes_it_signatory_again(
        self,
    ):
        """INVITE to B keeps AGREED(A); AGREE of B ends the lapse."""
        dl = _make_dl()
        a_id = "https://example.org/cases/derived-lapse/embargos/a"
        b_id = "https://example.org/cases/derived-lapse/embargos/b"
        case, participant_id = self._case_with_signatory(dl, a_id, a_id)
        activate(case, b_id)
        dl.save(case)
        write_consent_rows(dl, case)

        change = EmbargoLifecycle(persistence=dl).record_embargo_invite(
            case_id=case.id_,
            invitee_id=_INVITEE,
            embargo_id=b_id,
        )
        participant = cast(CaseParticipant, dl.read(participant_id))
        assert participant.consent_for(a_id) == EmbargoConsentState.AGREED
        assert participant.consent_for(b_id) == EmbargoConsentState.INVITED
        assert [
            (c.embargo_id, c.consent_before, c.consent_after)
            for c in change.participant_changes
        ] == [
            (
                b_id,
                EmbargoConsentState.UNINVITED.value,
                EmbargoConsentState.INVITED.value,
            )
        ]
        # Asked but not yet answered: still lapsed, still inert.
        assert participant.has_lapsed(case.embargo_register)
        assert not case.is_active_participant(participant)

        assert participant.sign_embargo(b_id) is True
        assert not participant.has_lapsed(case.embargo_register)
        assert participant.is_signatory(b_id)
        assert case.is_active_participant(participant)
        # The earlier acceptance is history, not undone.
        assert participant.consent_for(a_id) == EmbargoConsentState.AGREED

    @pytest.mark.spec("CM-18-001")
    def test_declining_the_longer_embargo_is_a_refusal_not_a_lapse(self):
        """A DECLINED row for B is an answer: not lapsed, but inert all the same."""
        dl = _make_dl()
        a_id = "https://example.org/cases/derived-lapse/embargos/a"
        b_id = "https://example.org/cases/derived-lapse/embargos/b"
        case, participant_id = self._case_with_signatory(dl, a_id, a_id)
        activate(case, b_id)
        participant = cast(CaseParticipant, dl.read(participant_id))
        participant.write_uninvited_rows([b_id])
        participant.apply_pec_transition(
            b_id,
            PEC_Trigger.DECLINE,
            entry_status=case.embargo_register_status(b_id),
        )

        assert not participant.has_lapsed(case.embargo_register)
        assert not participant.is_signatory(b_id)
        assert not case.is_active_participant(participant)


class TestOwnerAnswerToRelayedInvite:
    """The case owner's answer to a relayed embargo Invite is its own (EP-09-005/006).

    The protocol never requires an automatic answer.  The prototype keeps one
    bounded auto-accept: the owner accepts on its own only at ``EM.NONE`` and
    only for terms no longer than its own policy duration; in every other
    case — above all a revision Invite while an embargo is active — it holds
    the answer.  A non-owner participant's default accept is unchanged.
    """

    def _seed(
        self,
        dl,
        case_id: str,
        *,
        em_state: EM,
        roles: list[CVDRole],
        proposal_days: int,
        policy_days: int | None,
    ):
        from vultron.core.models.actor import VultronOrganization
        from vultron.core.models.embargo_policy import EmbargoPolicy

        case = VulnerabilityCase(
            id_=case_id, name="Owner Answer", attributed_to=_COORD
        )
        embargo = as_EmbargoEvent(
            id_=f"{case_id}/embargos/e1",
            context=case_id,
            end_time=days_from_now_utc(proposal_days),
        )
        dl.create(embargo)
        # ACTIVE: a prior embargo is in force, so e1 is a revision.  REVISE:
        # another revision of it is already open as well.
        if em_state in (EM.ACTIVE, EM.REVISE):
            prior = as_EmbargoEvent(
                id_=f"{case_id}/embargos/e0",
                context=case_id,
                end_time=days_from_now_utc(30),
            )
            dl.create(prior)
            activate(case, prior.id_)
        if em_state == EM.REVISE:
            other = as_EmbargoEvent(
                id_=f"{case_id}/embargos/e-other",
                context=case_id,
                end_time=days_from_now_utc(20),
            )
            dl.create(other)
            propose(case, other.id_)
        assert case.em_state == em_state
        coord_cp = WireCP(
            attributed_to=_COORD,
            context=case_id,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        invitee_cp = WireCP(
            attributed_to=_INVITEE,
            context=case_id,
            case_roles=roles,
        )
        dl.create(coord_cp)
        dl.create(invitee_cp)
        case.actor_participant_index[_COORD] = coord_cp.id_
        case.actor_participant_index[_INVITEE] = invitee_cp.id_
        dl.create(case)
        profile = VultronOrganization(
            id_=_INVITEE,
            embargo_policy=(
                None
                if policy_days is None
                else EmbargoPolicy(
                    actor_id=_INVITEE,
                    inbox=f"{_INVITEE}/inbox",
                    preferred_duration=timedelta(days=policy_days),
                )
            ),
        )
        dl.create(profile)
        return case, embargo

    def _deliver(self, dl, case, embargo, make_payload):
        invite = em_propose_embargo_activity(
            embargo=embargo,
            context=case.id_,
            actor=_COORD,
            to=[_INVITEE],
        )
        return InviteToEmbargoOnCaseReceivedUseCase(
            dl,
            make_payload(invite, receiving_actor_id=_INVITEE),
            trigger_activity=TriggerActivityAdapter(dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(dl),
        ).execute()

    @pytest.mark.parametrize(
        ("em_state", "roles", "proposal_days", "policy_days", "answers"),
        [
            # The regression: a revision Invite at an active embargo.
            (EM.ACTIVE, [CVDRole.CASE_OWNER], 60, 30, []),
            (EM.ACTIVE, [CVDRole.CASE_OWNER], 10, 30, []),
            (EM.REVISE, [CVDRole.CASE_OWNER], 10, 30, []),
            # The bounded auto-accept: no embargo yet, within own policy.
            (EM.NONE, [CVDRole.CASE_OWNER], 10, 30, ["Accept"]),
            # Beyond the owner's policy, or no policy to bound against.
            (EM.NONE, [CVDRole.CASE_OWNER], 60, 30, []),
            (EM.NONE, [CVDRole.CASE_OWNER], 10, None, []),
            # A non-owner's default accept records its own consent only.
            (EM.ACTIVE, [CVDRole.VENDOR], 60, 30, ["Accept"]),
        ],
        ids=[
            "owner-active-longer-holds",
            "owner-active-shorter-holds",
            "owner-revise-holds",
            "owner-none-within-policy-accepts",
            "owner-none-beyond-policy-holds",
            "owner-none-no-policy-holds",
            "non-owner-active-accepts",
        ],
    )
    @pytest.mark.spec("EP-09-005", "EP-09-006")
    def test_owner_answer_is_bounded(
        self,
        make_payload,
        em_state,
        roles,
        proposal_days,
        policy_days,
        answers,
    ):
        dl = _make_dl(actor_id=_INVITEE)
        case, embargo = self._seed(
            dl,
            "https://example.org/cases/owner-answer",
            em_state=em_state,
            roles=roles,
            proposal_days=proposal_days,
            policy_days=policy_days,
        )

        result = self._deliver(dl, case, embargo, make_payload)

        assert result.disposition is HandlerDisposition.APPLIED
        assert _answers_in_outbox(dl, _INVITEE) == answers
