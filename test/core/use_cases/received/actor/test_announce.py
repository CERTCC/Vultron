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
"""Tests for AnnounceVulnerabilityCaseReceivedUseCase (DR-10 / MV-10-003,004)."""

from typing import Any, cast

import pytest

from test.support.case_owner import (
    CASE_OWNER_ID,
    CONSTRUCTED_CASE_OWNERSHIP,
)
from test.support.inbox_replay import (
    RecordingInboxReplay,
    deliver_replayed,
    held_depth,
    hold_received,
    ledger_announce_event,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.core.models.actor import VultronService
from vultron.core.models.case_ledger import HashChainLedgerRecord
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.pending_case_inbox import VultronPendingCaseInbox
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.models.report_case_link import VultronReportCaseLink
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.use_cases.received.actor.announce import (
    AnnounceVulnerabilityCaseReceivedUseCase,
)
from vultron.core.use_cases.received.sync import (
    AnnounceLedgerEntryReceivedUseCase,
)
from vultron.enums.roles import CVDRole
from vultron.errors import VultronBTInternalError
from vultron.wire.as2.factories import announce_vulnerability_case_activity
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_OWNER_ID = "https://example.org/actors/owner"
_CASE_ACTOR_ID = "https://example.org/actors/case-actor"
_IMPOSTER_ID = "https://example.org/actors/imposter"
# The store every test runs as; the Announce is addressed to it (HP-01-005).
_RECEIVER_ID = "https://test.example/api/v2/actors/test-actor"
_VENDOR_ID = "https://example.org/actors/vendor"
_CASE_ID = "https://example.org/cases/case-ann-001"
_CASE_ID2 = "https://example.org/cases/case-ann-002"
_REPORT_ID = "https://example.org/reports/report-ann-001"
_CASE_ACTOR_PARTICIPANT_ID = f"{_CASE_ID}/participants/case-actor"
_VENDOR_PARTICIPANT_ID = f"{_CASE_ID}/participants/vendor"


@pytest.fixture()
def dl():
    return SqliteDataLayer(
        "sqlite:///:memory:",
        actor_id=_RECEIVER_ID,
    )


@pytest.fixture()
def case():
    return as_VulnerabilityCase(
        attributed_to=CASE_OWNER_ID, id_=_CASE_ID, name="DR-10 Announce Case"
    )


def _owned(case: as_VulnerabilityCase) -> as_VulnerabilityCase:
    """*case* with an owner, so it names a ledger position (SYNC-16-005)."""
    return as_VulnerabilityCase.model_validate(
        {**case.model_dump(exclude_none=True), "attributed_to": _OWNER_ID}
    )


@pytest.fixture()
def case_actor():
    return VultronService(
        id_=_CASE_ACTOR_ID,
        attributed_to=_OWNER_ID,
        context=_CASE_ID,
        name="CaseActor",
    )


def _anchor_expected_authority(
    dl, case_id: str = _CASE_ID, actor_id: str = _CASE_ACTOR_ID
) -> None:
    """Record a locally-derived trust anchor naming *actor_id* for *case_id*.

    PCR-03-004 fails closed, so a test that expects an Announce to be *admitted*
    must establish an anchor first.  These fixtures used to get one for free from
    a case actor ``Service`` whose ``context`` was the case id — the legacy
    ``Service``-hosting scan.  ADR-0088 retired hosting location as a signal of
    anything protocol-salient (ARCH-24-004), so the anchor moves to the invite
    record ``InviteActorToCaseReceivedUseCase`` actually writes: locally derived,
    not forgeable by the sender, and unaffected by where anyone is hosted.
    """
    dl.save(
        VultronPendingCaseInbox(
            case_id=case_id, case_actor_id=actor_id, invite_anchored=True
        )
    )


@pytest.fixture()
def announce_activity(case, case_actor):
    return announce_vulnerability_case_activity(
        case,
        actor=case_actor.id_,
        to=[_RECEIVER_ID],
        context=case.id_,
    )


@pytest.fixture()
def event(make_payload, announce_activity):
    return make_payload(announce_activity)


class TestAnnounceVulnerabilityCaseReceivedUseCase:
    """AnnounceVulnerabilityCaseReceivedUseCase seeds the invitee's DataLayer."""

    def test_creates_case_when_absent(self, dl, event, case):
        """MV-10-003: Announce seeding creates the case in the invitee's DL."""
        _anchor_expected_authority(dl)
        assert dl.read(_CASE_ID) is None

        AnnounceVulnerabilityCaseReceivedUseCase(dl, event).execute()

        result = dl.read(_CASE_ID)
        assert result is not None

    def test_case_fields_preserved(self, dl, event, case, case_actor):
        """The seeded case retains the name from the Announce payload."""
        _anchor_expected_authority(dl)
        AnnounceVulnerabilityCaseReceivedUseCase(dl, event).execute()

        result = cast(Any, dl.read(_CASE_ID))
        assert result.name == "DR-10 Announce Case"

    def test_rejects_announce_when_no_trust_anchor_exists(
        self, dl, event, caplog
    ):
        """PCR-03-004 / PCR-07-010: first-contact Announce with no prior trust record
        is rejected with a WARNING and the case is NOT seeded.

        Neither a completed VultronReportCaseLink nor a VultronPendingCaseInbox
        invite anchor is present, so the authority check MUST fail closed.  A
        hosting case actor `Service` is no longer a third source — ADR-0088
        retired it (ARCH-24-004), which is why it is not set up here.
        """
        import logging

        with caplog.at_level(logging.WARNING):
            AnnounceVulnerabilityCaseReceivedUseCase(dl, event).execute()

        result = dl.read(_CASE_ID)
        assert result is None, "Case must NOT be seeded without a trust anchor"
        assert any(
            "PCR-03-004" in r.getMessage() or "PCR-07-010" in r.getMessage()
            for r in caplog.records
            if r.levelno == logging.WARNING
        ), "Expected a WARNING log citing PCR-03-004 or PCR-07-010"

    @pytest.mark.spec("PCR-05-002")
    def test_updates_report_case_link_when_case_contains_report(
        self, dl, event, case, case_actor, make_payload
    ):
        """A valid Announce links known reports to the seeded case replica."""
        _anchor_expected_authority(dl)
        case.vulnerability_reports.append(_REPORT_ID)
        dl.save(VultronReportCaseLink(report_id=_REPORT_ID))

        linked_event = make_payload(
            announce_vulnerability_case_activity(
                case,
                actor=case_actor.id_,
                to=[_RECEIVER_ID],
                context=case.id_,
            ),
            at=dl,
        )

        AnnounceVulnerabilityCaseReceivedUseCase(dl, linked_event).execute()

        link = dl.read(VultronReportCaseLink.build_id(_REPORT_ID))
        assert isinstance(link, VultronReportCaseLink)
        assert link.case_id == _CASE_ID

    @pytest.mark.spec("MV-10-004")
    @pytest.mark.spec("SYNC-16-006")
    def test_redelivery_of_the_same_announce_is_stable(
        self, dl, make_payload, case
    ):
        """MV-10-004: receiving the same Announce twice leaves the same state.

        Asserts *stability*, which is what idempotency means here — not merely
        that a row survives.  The previous version of this test seeded the case
        itself and then asserted only ``dl.read(_CASE_ID) is not None``, which is
        true by construction: it passed whether the announce was applied,
        ignored, or rejected outright.  Its anchor was a case actor ``Service``
        carrying ``context``, the hosting signal ADR-0088 retires, so once that
        path was removed the announce was in fact being *rejected* on both calls
        and the test still passed.

        Anchored on the invite record instead, so both deliveries are genuinely
        admitted, and asserting the payload's own name so an unapplied announce
        cannot pass.  The copy names its ledger position (SYNC-16-005), so the
        redelivery is judged current and applied again, not refused.
        """
        _anchor_expected_authority(dl)
        event = make_payload(
            announce_vulnerability_case_activity(
                _owned(case),
                actor=_CASE_ACTOR_ID,
                to=[_RECEIVER_ID],
                context=_CASE_ID,
            ),
            at=dl,
        )

        first_result = AnnounceVulnerabilityCaseReceivedUseCase(
            dl, event
        ).execute()
        first = cast(Any, dl.read(_CASE_ID))
        assert first_result.disposition is HandlerDisposition.APPLIED
        assert first is not None
        assert first.name == "DR-10 Announce Case"

        second_result = AnnounceVulnerabilityCaseReceivedUseCase(
            dl, event
        ).execute()
        second = cast(Any, dl.read(_CASE_ID))
        assert second_result.disposition is HandlerDisposition.APPLIED, (
            second_result.reason
        )

        assert second is not None
        assert second.name == first.name
        assert second.id_ == first.id_

    def test_missing_activity_skips_gracefully(self, dl, event):
        """No-op (with a warning log) when event.activity is None."""
        event = event.model_copy(update={"activity": None})

        # Must not raise
        AnnounceVulnerabilityCaseReceivedUseCase(dl, event).execute()

        assert dl.read(_CASE_ID) is None

    def test_non_case_object_skips_gracefully(self, dl, make_payload):
        """No-op when the activity object_ is not a as_VulnerabilityCase."""
        from vultron.wire.as2.factories import (
            announce_vulnerability_case_activity,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_report import (
            as_VulnerabilityReport,
        )

        # Build an Announce that wraps a non-case object; we can't use the typed
        # factory here because it requires as_VulnerabilityCase,
        # so we inject via model_copy to simulate a malformed incoming payload.
        good_case = as_VulnerabilityCase(
            attributed_to=CASE_OWNER_ID, id_=_CASE_ID2, name="Placeholder"
        )
        announce = announce_vulnerability_case_activity(
            good_case, actor=_OWNER_ID, to=[_RECEIVER_ID]
        )
        event = make_payload(announce, at=dl)

        # Replace the object_ on the event's activity with a non-case
        report = as_VulnerabilityReport(name="Not a case")
        patched_activity = event.activity.model_copy(
            update={"object_": report}
        )
        event = event.model_copy(update={"activity": patched_activity})

        result = AnnounceVulnerabilityCaseReceivedUseCase(dl, event).execute()

        assert result.disposition == HandlerDisposition.REFUSED
        assert dl.read(_CASE_ID2) is None
        # CLP-10-018: the refused Announce is still archived.
        assert dl.read(ReceivedActivityRecord.build_id(event.activity_id))

    def test_rejects_announce_from_non_case_actor(
        self, dl, case, make_payload, caplog
    ):
        """PCR-07-003: a sender that is not the expected authority cannot
        seed, and the refusal is logged at WARNING."""
        import logging

        _anchor_expected_authority(dl)
        announce = announce_vulnerability_case_activity(
            case,
            actor=_IMPOSTER_ID,
            to=[_RECEIVER_ID],
            context=case.id_,
        )
        event = make_payload(announce, at=dl)

        with caplog.at_level(logging.WARNING):
            AnnounceVulnerabilityCaseReceivedUseCase(dl, event).execute()

        assert dl.read(_CASE_ID) is None
        assert any(
            r.levelno == logging.WARNING and _IMPOSTER_ID in r.getMessage()
            for r in caplog.records
        ), "Expected a WARNING naming the refused sender (PCR-07-003)"


# ---------------------------------------------------------------------------
# PCR-03-004 / PCR-07-010: invite trust anchor gates first-contact Announce
# ---------------------------------------------------------------------------


class TestAnnounceFirstContactTrustGap:
    """PCR-03-004 / PCR-07-010: first-contact Announce(VulnerabilityCase) is
    rejected unless a prior trust anchor exists."""

    def test_rejects_first_contact_announce_without_any_anchor(
        self, dl, event, caplog
    ):
        """AC-5a / PCR-07-010: no-prior-record Announce rejected with WARNING,
        case NOT seeded."""
        import logging

        with caplog.at_level(logging.WARNING):
            AnnounceVulnerabilityCaseReceivedUseCase(dl, event).execute()

        assert dl.read(_CASE_ID) is None, (
            "Case MUST NOT be seeded when no trust anchor exists (PCR-03-004)"
        )
        assert any(
            "PCR-03-004" in r.getMessage() or "PCR-07-010" in r.getMessage()
            for r in caplog.records
            if r.levelno == logging.WARNING
        ), "Expected WARNING log citing the PCR spec reference"

    @pytest.mark.spec("HP-01-003")
    def test_announce_from_untrusted_sender_is_refused(self, dl, event):
        """#2255: a rejected Announce is REFUSED, not reported as applied.

        APPLIED reads as "processed" in the InboxOutcome and gates the
        post-bootstrap replay, so a refused seed must not look applied.
        """
        result = AnnounceVulnerabilityCaseReceivedUseCase(dl, event).execute()

        assert result.disposition == HandlerDisposition.REFUSED
        assert result.reason is not None
        assert "No CASE_MANAGER is known" in result.reason
        # CLP-10-018: the refused Announce is still archived, and no case row
        # was seeded from it.
        assert dl.read(ReceivedActivityRecord.build_id(event.activity_id))
        assert dl.read(_CASE_ID) is None

    @pytest.mark.spec("HP-01-003")
    def test_admitted_announce_is_applied(self, dl, event):
        _anchor_expected_authority(dl)

        result = AnnounceVulnerabilityCaseReceivedUseCase(dl, event).execute()

        assert result.disposition == HandlerDisposition.APPLIED

    @pytest.mark.spec("HP-01-003")
    def test_announce_without_activity_is_refused(self, dl, event):
        event = event.model_copy(update={"activity": None})

        result = AnnounceVulnerabilityCaseReceivedUseCase(dl, event).execute()

        assert result.disposition == HandlerDisposition.REFUSED

    def test_admits_announce_after_invite_trust_anchor(self, dl, event, case):
        """AC-5b / PCR-03-004: Announce from the invite sender is admitted once
        a VultronPendingCaseInbox trust anchor is stored by the invite path."""
        dl.save(
            VultronPendingCaseInbox(
                case_id=_CASE_ID,
                case_actor_id=_CASE_ACTOR_ID,
                invite_anchored=True,
            )
        )

        AnnounceVulnerabilityCaseReceivedUseCase(dl, event).execute()

        result = dl.read(_CASE_ID)
        assert result is not None, (
            "Case MUST be seeded when an invite trust anchor for the sender exists"
        )

    @pytest.mark.spec("PCR-03-004", "CBT-03-004")
    def test_announce_from_queue_recorded_sender_is_refused(self, dl, event):
        """#4931: the sender the pre-bootstrap queue recorded is no anchor.

        The queue records the sender of the first deferred activity as its
        replay target (CBT-03-004); only a stub Invite anchors trust.
        """
        dl.save(
            VultronPendingCaseInbox(
                case_id=_CASE_ID,
                activity_ids=["https://example.org/activities/queued"],
                case_actor_id=_CASE_ACTOR_ID,
            )
        )

        result = AnnounceVulnerabilityCaseReceivedUseCase(dl, event).execute()

        assert result.disposition == HandlerDisposition.REFUSED
        assert dl.read(_CASE_ID) is None

    def test_rejects_announce_when_pending_record_has_no_case_actor_id(
        self, dl, event
    ):
        """A VultronPendingCaseInbox with case_actor_id=None must NOT admit any sender.

        Protects against None == None evaluation that would let an Announce with
        actor_id=None (or any sender when the queued record lacks a trust anchor)
        pass the PCR-03-004 gate.
        """
        dl.save(
            VultronPendingCaseInbox(
                case_id=_CASE_ID,
                case_actor_id=None,  # no trust anchor set yet
            )
        )

        AnnounceVulnerabilityCaseReceivedUseCase(dl, event).execute()

        assert dl.read(_CASE_ID) is None, (
            "A pending record with case_actor_id=None must NOT admit any Announce"
        )

    def test_rejects_announce_from_wrong_actor_with_trust_anchor(
        self, dl, make_payload, case
    ):
        """AC-1: a trust anchor for actor A does not admit an Announce from actor B."""
        dl.save(
            VultronPendingCaseInbox(
                case_id=_CASE_ID,
                case_actor_id=_CASE_ACTOR_ID,  # trust anchor names expected sender
                invite_anchored=True,
            )
        )
        # Build an announce from a *different* actor (the imposter)
        imposter_announce = announce_vulnerability_case_activity(
            case, actor=_IMPOSTER_ID, to=[_RECEIVER_ID], context=case.id_
        )
        event = make_payload(imposter_announce, at=dl)

        AnnounceVulnerabilityCaseReceivedUseCase(dl, event).execute()

        assert dl.read(_CASE_ID) is None, (
            "Case MUST NOT be seeded when the sender does not match the trust anchor"
        )


# ---------------------------------------------------------------------------
# #2186 / #2180: pre-genesis Announce(CaseLedgerEntry) drains on case seed
# ---------------------------------------------------------------------------


def _genesis_entry_for(case_id: str, genesis_hash: str) -> CaseLedgerEntry:
    """Build a genesis (log_index 0) entry anchored to *genesis_hash*."""
    chain = HashChainLedgerRecord(
        case_id=case_id,
        log_index=0,
        object_id="https://example.org/activities/genesis",
        semantic_type="test_event",
        payload_snapshot={"key": "value"},
        prev_log_hash=genesis_hash,
    )
    return chain.to_ledger_entry()


class TestAnnounceDrainsPreGenesisBuffer:
    """Seeding a VulnerabilityCase replays the held pre-genesis Announces.

    Regression for #2186 (root cause) / #2180 (symptom): an
    ``Announce(CaseLedgerEntry)`` that arrives before the ``VulnerabilityCase``
    is seeded is held as received (SYNC-15-004) instead of being permanently
    dropped.  Once the case seed lands — anchoring the deterministic per-case
    genesis hash — that held ``Announce`` is replayed through the receiving
    actor's own inbox as a delivery of its own, and never applied inside the
    seed's delivery (SYNC-15-005, SYNC-14-009, ADR-0135).
    """

    @pytest.fixture()
    def case_with_actor(self):
        """A case whose attributed_to yields a deterministic genesis hash.

        It embeds its CASE_MANAGER participant, as every seeded replica does
        (CP-09-004), so the replayed Announce from that actor passes its
        sender guard (SYNC-13-006).
        """
        manager = as_CaseParticipant(
            case_roles=[CVDRole.CASE_MANAGER],
            id_=_CASE_ACTOR_PARTICIPANT_ID,
            attributed_to=_CASE_ACTOR_ID,
            context=_CASE_ID,
        )
        return as_VulnerabilityCase(
            id_=_CASE_ID,
            name="DR-10 Announce Case (pre-genesis drain)",
            attributed_to=_CASE_ACTOR_ID,
            case_participants=[manager],
            actor_participant_index={
                _CASE_ACTOR_ID: _CASE_ACTOR_PARTICIPANT_ID
            },
        )

    def _seed(self, dl, make_payload, case_with_actor, **ports: Any):
        # Establish the locally-derived trust anchor so the authority check
        # (PCR-03-004) admits the Announce from _CASE_ACTOR_ID before the case
        # replica exists.  Not a hosting `Service` — ADR-0088 retired that.
        _anchor_expected_authority(dl)
        activity = announce_vulnerability_case_activity(
            case_with_actor,
            actor=_CASE_ACTOR_ID,
            to=[_RECEIVER_ID],
            context=_CASE_ID,
        )
        event = make_payload(activity, at=dl)
        return event, AnnounceVulnerabilityCaseReceivedUseCase(
            dl, event, sync_port=SyncActivityAdapter(dl), **ports
        ).execute()

    @pytest.mark.spec("SYNC-14-009")
    @pytest.mark.spec("SYNC-15-005")
    def test_pre_genesis_announce_is_replayed_when_case_is_announced(
        self, dl, make_payload, case_with_actor
    ):
        genesis_hash = case_with_actor.genesis_hash
        assert genesis_hash, "case must expose a deterministic genesis hash"
        entry = _genesis_entry_for(_CASE_ID, genesis_hash)
        held = ledger_announce_event(
            entry, actor=_CASE_ACTOR_ID, to=_RECEIVER_ID
        )
        hold_received(dl, held)
        assert dl.read(entry.id_) is None  # not yet applicable — case absent
        replay = RecordingInboxReplay()

        _, result = self._seed(
            dl, make_payload, case_with_actor, inbox_replay=replay
        )

        assert result.disposition is HandlerDisposition.APPLIED
        assert dl.read(_CASE_ID) is not None
        # The Announce that was received is replayed once, by its own id ...
        assert replay.replayed == [held.activity_id]
        assert held_depth(dl, _CASE_ID) == 0
        # ... and not applied here: no second tree ran in this delivery.
        assert dl.read(entry.id_) is None

        # Delivered as its own delivery, the entry applies.
        deliver_replayed(
            replay,
            dl,
            _RECEIVER_ID,
            lambda ev: AnnounceLedgerEntryReceivedUseCase(
                dl,
                ev,
                sync_port=SyncActivityAdapter(dl),
                inbox_replay=replay,
            ).execute(),
        )
        assert dl.read(entry.id_) is not None

    @pytest.mark.spec("SYNC-14-009")
    def test_missing_replay_port_is_a_wiring_error(
        self, dl, make_payload, case_with_actor
    ):
        """No port means a composition fault, never an inline apply."""
        entry = _genesis_entry_for(_CASE_ID, case_with_actor.genesis_hash)
        hold_received(
            dl,
            ledger_announce_event(
                entry, actor=_CASE_ACTOR_ID, to=_RECEIVER_ID
            ),
        )

        with pytest.raises(VultronBTInternalError, match="inbox_replay"):
            self._seed(dl, make_payload, case_with_actor)

        assert dl.read(entry.id_) is None
        assert held_depth(dl, _CASE_ID) == 1


# ---------------------------------------------------------------------------
# #566: Embedded participants must be stored during Announce seeding
# ---------------------------------------------------------------------------


class TestAnnounceStoresEmbeddedParticipants:
    """Announce(as_VulnerabilityCase) seeding must store embedded participants.

    Regression tests for #566: ``AnnounceVulnerabilityCaseReceivedUseCase``
    was not calling ``store_embedded_participants`` after saving the case,
    so late-joiner replicas never had independent ``as_CaseParticipant`` records.
    BT nodes (``SenderIsParticipantNode``, ``AppendParticipantStatusNode``)
    would then fail with participant-not-found on the Announce path.
    """

    @pytest.fixture()
    def dl(self):
        """DataLayer with an invite trust anchor naming _CASE_ACTOR_ID.

        Required by PCR-03-004: the authority check rejects an Announce when no
        trust anchor exists.  This used to seed a case actor ``Service`` whose
        ``context`` was the case id and rely on the legacy ``Service`` scan in
        ``_find_case_actor_id``; ADR-0088 retired that path (ARCH-24-004), so the
        anchor is now the locally recorded invite record instead.
        """
        _dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=_RECEIVER_ID,
        )
        _anchor_expected_authority(_dl)
        return _dl

    @pytest.fixture()
    def case_with_participants(self):
        """as_VulnerabilityCase with two embedded participants (inline objects)."""
        case_actor_p = as_CaseParticipant(
            case_roles=[CVDRole.CASE_MANAGER],
            id_=_CASE_ACTOR_PARTICIPANT_ID,
            attributed_to=_CASE_ACTOR_ID,
            context=_CASE_ID,
        )
        vendor_p = as_CaseParticipant(
            id_=_VENDOR_PARTICIPANT_ID,
            attributed_to=_VENDOR_ID,
            context=_CASE_ID,
        )
        case = as_VulnerabilityCase.model_construct(
            **CONSTRUCTED_CASE_OWNERSHIP,
            id_=_CASE_ID,
            name="DR-10 Announce Case with Participants",
            case_participants=[
                case_actor_p,
                vendor_p,
            ],
            actor_participant_index={
                _CASE_ACTOR_ID: _CASE_ACTOR_PARTICIPANT_ID,
                _VENDOR_ID: _VENDOR_PARTICIPANT_ID,
            },
        )
        return case, case_actor_p, vendor_p

    @pytest.fixture()
    def announce_with_participants_event(
        self, make_payload, case_with_participants
    ):
        case, _, _ = case_with_participants
        activity = announce_vulnerability_case_activity(
            case,
            actor=_CASE_ACTOR_ID,
            to=[_RECEIVER_ID],
            context=_CASE_ID,
        )
        return make_payload(activity)

    def test_embedded_case_actor_participant_stored_after_announce(
        self, dl, announce_with_participants_event
    ):
        """CaseActorParticipant embedded in Announce payload is stored
        independently (#566 — Announce path mirrors Create bootstrap path)."""
        AnnounceVulnerabilityCaseReceivedUseCase(
            dl, announce_with_participants_event
        ).execute()

        stored = dl.read(_CASE_ACTOR_PARTICIPANT_ID)
        assert stored is not None, (
            "CaseActorParticipant must be stored as an independent DataLayer "
            "record after Announce seeding (#566)"
        )

    def test_embedded_vendor_participant_stored_after_announce(
        self, dl, announce_with_participants_event
    ):
        """Vendor as_CaseParticipant embedded in Announce payload is stored
        independently — BT nodes can then look it up by UUID (#566)."""
        AnnounceVulnerabilityCaseReceivedUseCase(
            dl, announce_with_participants_event
        ).execute()

        stored = dl.read(_VENDOR_PARTICIPANT_ID)
        assert stored is not None, (
            "Vendor as_CaseParticipant must be stored as an independent DataLayer "
            "record after Announce seeding (#566)"
        )

    def test_string_participant_refs_not_stored_as_objects(
        self, dl, make_payload
    ):
        """String ID refs in case_participants are skipped (no object to store).

        Only inline participant objects are stored; bare ID strings are left
        as-is (they reference objects the receiver doesn't have locally).
        """
        case = as_VulnerabilityCase(
            attributed_to=CASE_OWNER_ID,
            id_=_CASE_ID,
            name="Announce with string participants",
            case_participants=[_VENDOR_PARTICIPANT_ID],  # bare string ref
        )
        activity = announce_vulnerability_case_activity(
            case, actor=_CASE_ACTOR_ID, to=[_RECEIVER_ID], context=_CASE_ID
        )
        event = make_payload(activity, at=dl)

        AnnounceVulnerabilityCaseReceivedUseCase(dl, event).execute()

        # The bare string ref must NOT cause a spurious record to appear
        stored = dl.read(_VENDOR_PARTICIPANT_ID)
        assert stored is None, (
            "String participant refs must not create spurious DataLayer records"
        )

    def test_embedded_participants_stored_when_case_already_exists(
        self,
        dl,
        make_payload,
        case_with_participants,
    ):
        """Participants are stored even when the case already exists locally.

        Regression (#566): a replica that already holds the case, from an
        earlier Announce, takes the existing-case path.  Embedded participants
        must still be persisted on that path.
        """
        case, _, _ = case_with_participants
        # A copy of a held case names its ledger position, so it has an
        # owner (SYNC-16-005).
        case = _owned(case)
        # Pre-seed the case so the use-case hits the existing-case branch.
        dl.create(case)
        announce = make_payload(
            announce_vulnerability_case_activity(
                case,
                actor=_CASE_ACTOR_ID,
                to=[_RECEIVER_ID],
                context=_CASE_ID,
            ),
            at=dl,
        )

        AnnounceVulnerabilityCaseReceivedUseCase(dl, announce).execute()

        stored_ca = dl.read(_CASE_ACTOR_PARTICIPANT_ID)
        stored_vendor = dl.read(_VENDOR_PARTICIPANT_ID)
        assert stored_ca is not None, (
            "CaseActorParticipant must be stored even when the case already "
            "exists (idempotent early-return path, #566)"
        )
        assert stored_vendor is not None, (
            "Vendor as_CaseParticipant must be stored even when the case already "
            "exists (idempotent early-return path, #566)"
        )
