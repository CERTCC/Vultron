#  Copyright (c) 2025-2026 Carnegie Mellon University and Contributors.
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
"""Tests for case-related use-case update handlers.

BT structure tests (tree shape and no-post-BT-broadcast contract) have been
extracted to ``test_update_bt.py`` to separate use-case behavior assertions
from tree-structure assertions.
"""

import logging
from typing import cast

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.core.models._helpers import days_from_now_utc
from vultron.core.models.activity import VultronActivity
from vultron.core.models.case_actor import CaseActor
from vultron.core.models.embargo_consent import EmbargoConsent
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.participant_embargo_consent import (
    EmbargoConsentState,
)
from vultron.core.use_cases.received.case.update import (
    UpdateCaseReceivedUseCase,
)
from vultron.wire.as2.factories import (
    update_case_activity,
)
from vultron.wire.as2.rehydration import rehydrate as real_rehydrate
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.embargo_event import as_EmbargoEvent
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

#: The actor receiving these Update(VulnerabilityCase) messages.
#:
#: A received-side use case applies an inbound update to the *receiver's* own
#: replica, and the tree executes under the receiving actor (BT-17-005), which
#: under ADR-0073 also selects the store. So this names both the store's owner
#: and the ``receiving_actor_id`` on every event below. The sender stays a
#: separate identity — the owner-gating tests depend on that distinction.
RECEIVER_ID = "https://example.org/actors/update-receiver"


def _seat(dl, case, actor_id, participant_id, **fields):
    """Store a participant record for *actor_id* and index it on *case*.

    The case-update broadcast reads each roster entry's record to decide
    whether it is active (CM-10-004, CM-10-007); an index entry with no
    record behind it is not provably entitled and gets nothing.
    """
    from vultron.core.models.case_participant import CaseParticipant

    dl.create(
        CaseParticipant(
            id_=participant_id,
            attributed_to=actor_id,
            context=case.id_,
            **fields,
        )
    )
    case.actor_participant_index[actor_id] = participant_id


def _make_receiver_the_case_manager(dl, case, receiver_id=None):
    """Give *receiver_id* the CASE_MANAGER role on *case*, in ``dl``.

    ``GuardedBroadcastCaseUpdateBT`` gates the announce on
    ``CheckIsCaseManagerNode``, which reads the **role** resolved from the case —
    not the presence of a ``CaseActor`` service entity. A service-only
    fixture makes the gate correctly *skip*, so nothing is announced and the test
    proves nothing (BT-17-005).

    Because the gate passes only when the executing actor holds the role, the
    announce is authored as that actor and ``outbox_append()`` puts it in that
    actor's own store — which is the point of the Phase 3b role gate: both halves
    of the emit land in one store.
    """
    from vultron.core.models.case_participant import CaseParticipant
    from vultron.enums.roles import CVDRole

    receiver_id = receiver_id or RECEIVER_ID
    manager = CaseParticipant(
        id_=f"{case.id_}/participants/case-manager",
        attributed_to=receiver_id,
        context=case.id_,
        case_roles=[CVDRole.CASE_MANAGER],
    )
    dl.create(manager)
    case.actor_participant_index[receiver_id] = manager.id_
    return manager


class TestCaseUseCases:
    """Tests for update_case handler."""

    def test_update_case_applies_scalar_updates(
        self, monkeypatch, caplog, make_payload
    ):
        """update_case applies name/summary/content updates from a full object."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=RECEIVER_ID,
        )
        owner_id = "https://example.org/users/owner"
        case = as_VulnerabilityCase(
            id_="https://example.org/cases/uc1",
            name="Original Name",
            attributed_to=owner_id,
        )
        dl.create(case)

        updated_case = as_VulnerabilityCase(
            id_=case.id_,
            name="Updated Name",
            content="New content",
            attributed_to=owner_id,
        )
        activity = update_case_activity(updated_case, actor=owner_id)
        event = make_payload(activity, receiving_actor_id=RECEIVER_ID)

        def _mock_rehydrate_applies(obj, **kwargs):
            if obj == case.id_:
                return updated_case
            return real_rehydrate(obj, **kwargs)

        monkeypatch.setattr(
            "vultron.wire.as2.rehydration.rehydrate",
            _mock_rehydrate_applies,
        )

        with caplog.at_level(logging.INFO):
            result = UpdateCaseReceivedUseCase(
                dl, event, trigger_activity=TriggerActivityAdapter(dl)
            ).execute()

        stored = dl.read(case.id_)
        assert stored is not None
        stored = cast(as_VulnerabilityCase, stored)
        assert stored.name == "Updated Name"
        assert stored.content == "New content"
        assert result.disposition == HandlerDisposition.APPLIED

    def test_update_case_rejects_non_owner(
        self, monkeypatch, caplog, make_payload
    ):
        """update_case ledgers a warning and skips if actor is not the case owner."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=RECEIVER_ID,
        )
        owner_id = "https://example.org/users/owner"
        non_owner_id = "https://example.org/users/other"
        case = as_VulnerabilityCase(
            id_="https://example.org/cases/uc2",
            name="Original Name",
            attributed_to=owner_id,
        )
        dl.create(case)

        updated_case = as_VulnerabilityCase(
            id_=case.id_,
            name="Hijacked Name",
            attributed_to=owner_id,
        )
        activity = update_case_activity(updated_case, actor=non_owner_id)
        event = make_payload(activity, receiving_actor_id=RECEIVER_ID)

        with caplog.at_level(logging.WARNING):
            result = UpdateCaseReceivedUseCase(
                dl, event, trigger_activity=TriggerActivityAdapter(dl)
            ).execute()

        stored = dl.read(case.id_)
        assert stored is not None
        stored = cast(as_VulnerabilityCase, stored)
        assert stored.name == "Original Name"
        assert any("not the owner" in r.message for r in caplog.records)
        # HP-01-003: a non-owner update is refused, not reported as applied.
        assert result.disposition == HandlerDisposition.REFUSED
        assert result.reason is not None and "not the owner" in result.reason

    def test_update_case_without_case_id_is_refused(self, make_payload):
        """HP-01-003: an Update with no case id is malformed, so REFUSED."""
        from unittest.mock import MagicMock

        dl = SqliteDataLayer("sqlite:///:memory:", actor_id=RECEIVER_ID)
        event = MagicMock()
        event.case_id = None

        result = UpdateCaseReceivedUseCase(
            dl, event, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        assert result.disposition == HandlerDisposition.REFUSED

    def test_update_case_idempotent(self, monkeypatch, make_payload):
        """update_case with same data produces the same result (last-write-wins)."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=RECEIVER_ID,
        )
        owner_id = "https://example.org/users/owner"
        case = as_VulnerabilityCase(
            id_="https://example.org/cases/uc3",
            name="Original",
            attributed_to=owner_id,
        )
        dl.create(case)

        updated_case = as_VulnerabilityCase(
            id_=case.id_,
            name="Updated",
            attributed_to=owner_id,
        )
        activity = update_case_activity(updated_case, actor=owner_id)
        event = make_payload(activity, receiving_actor_id=RECEIVER_ID)

        def _mock_rehydrate_idempotent(obj, **kwargs):
            if obj == case.id_:
                return updated_case
            return real_rehydrate(obj, **kwargs)

        monkeypatch.setattr(
            "vultron.wire.as2.rehydration.rehydrate",
            _mock_rehydrate_idempotent,
        )

        UpdateCaseReceivedUseCase(
            dl, event, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()
        UpdateCaseReceivedUseCase(
            dl, event, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        stored = dl.read(case.id_)
        assert stored is not None
        stored = cast(as_VulnerabilityCase, stored)
        assert stored.name == "Updated"

    def test_update_case_reports_participant_not_signatory_to_embargo(
        self, monkeypatch, caplog, make_payload
    ):
        """update_case reports a participant not a signatory to the active embargo as inert (CM-10-004)."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=RECEIVER_ID,
        )
        owner_id = "https://example.org/users/owner"
        actor_id = "https://example.org/users/alice"
        embargo = as_EmbargoEvent(
            id_="https://example.org/embargoes/em1",
            context="https://example.org/cases/uc4",
            end_time=days_from_now_utc(45),
        )
        dl.create(embargo)

        participant = as_CaseParticipant(
            id_="https://example.org/participants/p1",
            attributed_to=actor_id,
            context="https://example.org/cases/uc4",
        )
        dl.create(participant)

        case = as_VulnerabilityCase(
            id_="https://example.org/cases/uc4",
            name="Original",
            attributed_to=owner_id,
            active_embargo=embargo.id_,
        )
        case.actor_participant_index[actor_id] = participant.id_
        dl.create(case)

        updated_case = as_VulnerabilityCase(
            id_=case.id_,
            name="Updated",
            attributed_to=owner_id,
        )
        activity = update_case_activity(updated_case, actor=owner_id)
        event = make_payload(activity, receiving_actor_id=RECEIVER_ID)

        with caplog.at_level(logging.INFO):
            UpdateCaseReceivedUseCase(
                dl, event, trigger_activity=TriggerActivityAdapter(dl)
            ).execute()

        assert any(
            actor_id in r.message
            and "not active" in r.message
            and "CM-10-004" in r.message
            for r in caplog.records
        )

    def test_update_case_logs_no_withholding_when_all_participants_accepted_embargo(
        self, monkeypatch, caplog, make_payload
    ):
        """update_case reports nobody inert when every participant is a signatory (CM-10-004)."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=RECEIVER_ID,
        )
        owner_id = "https://example.org/users/owner"
        actor_id = "https://example.org/users/bob"
        embargo = as_EmbargoEvent(
            id_="https://example.org/embargoes/em2",
            context="https://example.org/cases/uc5",
            end_time=days_from_now_utc(45),
        )
        dl.create(embargo)

        participant = as_CaseParticipant(
            id_="https://example.org/participants/p2",
            attributed_to=actor_id,
            context="https://example.org/cases/uc5",
            embargo_consents=[
                EmbargoConsent(
                    embargo_id=embargo.id_, state=EmbargoConsentState.ACCEPTED
                )
            ],
        )
        dl.create(participant)

        case = as_VulnerabilityCase(
            id_="https://example.org/cases/uc5",
            name="Original",
            attributed_to=owner_id,
            active_embargo=embargo.id_,
        )
        case.actor_participant_index[actor_id] = participant.id_
        dl.create(case)

        updated_case = as_VulnerabilityCase(
            id_=case.id_,
            name="Updated",
            attributed_to=owner_id,
        )
        activity = update_case_activity(updated_case, actor=owner_id)
        event = make_payload(activity, receiving_actor_id=RECEIVER_ID)

        with caplog.at_level(logging.INFO):
            UpdateCaseReceivedUseCase(
                dl, event, trigger_activity=TriggerActivityAdapter(dl)
            ).execute()

        assert not any("not active" in r.message for r in caplog.records)

    def test_update_case_logs_no_withholding_when_no_active_embargo(
        self, monkeypatch, caplog, make_payload
    ):
        """update_case reports nobody inert when there is no active embargo (CM-10-004)."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=RECEIVER_ID,
        )
        owner_id = "https://example.org/users/owner"
        actor_id = "https://example.org/users/carol"

        participant = as_CaseParticipant(
            id_="https://example.org/participants/p3",
            attributed_to=actor_id,
            context="https://example.org/cases/uc6",
        )
        dl.create(participant)

        case = as_VulnerabilityCase(
            id_="https://example.org/cases/uc6",
            name="Original",
            attributed_to=owner_id,
            active_embargo=None,
        )
        case.actor_participant_index[actor_id] = participant.id_
        dl.create(case)

        updated_case = as_VulnerabilityCase(
            id_=case.id_,
            name="Updated",
            attributed_to=owner_id,
        )
        activity = update_case_activity(updated_case, actor=owner_id)
        event = make_payload(activity, receiving_actor_id=RECEIVER_ID)

        with caplog.at_level(logging.INFO):
            UpdateCaseReceivedUseCase(
                dl, event, trigger_activity=TriggerActivityAdapter(dl)
            ).execute()

        assert not any("not active" in r.message for r in caplog.records)

    @pytest.mark.parametrize(
        "inert", ["no-record", "not-signatory", "not-joined"]
    )
    @pytest.mark.spec("CM-10-004")
    def test_update_case_withholds_from_inert_participant(
        self, make_payload, inert
    ):
        """An inert roster entry gets no case update; a signatory does.

        Entitlement is read from the record (CM-10-004).  An entry pointing at
        some other object cannot show the actor is active, so the shared
        selection leaves it out rather than leaking content (CM-10-007); a
        record that is not a signatory to the active embargo, or that never
        joined, is inert (ADR-0114).
        """
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=RECEIVER_ID,
        )
        owner_id = "https://example.org/users/owner"
        actor_id = "https://example.org/users/alice"
        case_id = "https://example.org/cases/uc6b"
        embargo = as_EmbargoEvent(
            id_="https://example.org/embargoes/em6b",
            context=case_id,
            end_time=days_from_now_utc(45),
        )
        dl.create(embargo)

        bogus_ref = VultronActivity(
            type_="Announce",
            actor=owner_id,
            object_=case_id,
        )
        dl.create(bogus_ref)

        case_actor = CaseActor(
            id_=f"{case_id}/actor",
            name=f"CaseActor for {case_id}",
            attributed_to=owner_id,
            context=case_id,
        )
        dl.create(case_actor)

        case = as_VulnerabilityCase(
            id_=case_id,
            name="Original",
            attributed_to=owner_id,
            active_embargo=embargo.id_,
        )
        if inert == "no-record":
            case.actor_participant_index[actor_id] = bogus_ref.id_
        else:
            _seat(
                dl,
                case,
                actor_id,
                f"{case_id}/participants/alice",
                embargo_consents=[
                    EmbargoConsent(
                        embargo_id=embargo.id_,
                        state=(
                            EmbargoConsentState.INVITED
                            if inert == "not-signatory"
                            else EmbargoConsentState.ACCEPTED
                        ),
                    )
                ],
                joined=inert != "not-joined",
            )
        signatory = "https://example.org/users/dave"
        _seat(
            dl,
            case,
            signatory,
            f"{case_id}/participants/dave",
            embargo_consents=[
                EmbargoConsent(
                    embargo_id=embargo.id_, state=EmbargoConsentState.ACCEPTED
                )
            ],
        )
        _make_receiver_the_case_manager(dl, case)
        dl.create(case)

        updated_case = as_VulnerabilityCase(
            id_=case_id,
            name="Updated",
            attributed_to=owner_id,
        )
        activity = update_case_activity(updated_case, actor=owner_id)
        event = make_payload(activity, receiving_actor_id=RECEIVER_ID)

        UpdateCaseReceivedUseCase(
            dl, event, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        outbox_items = dl.outbox_list()
        assert len(outbox_items) == 1
        broadcast = cast(VultronActivity, dl.read(outbox_items[0]))
        assert broadcast.to == [signatory]

    # ------------------------------------------------------------------
    # Broadcast tests (CM-06-001, CM-06-002)
    # ------------------------------------------------------------------

    @pytest.mark.parametrize(
        "receiving_actor_id",
        [RECEIVER_ID, None],
        ids=["explicit-receiver", "store-owner-fallback"],
    )
    def test_update_case_broadcasts_announce_to_participants(
        self, make_payload, receiving_actor_id
    ):
        """After a case update, the CaseActor outbox contains an Announce.

        With no ``receiving_actor_id`` the tree runs as the store's owner, never
        the sender, so the CASE_MANAGER gate still passes (BT-17-006, #2667).
        """
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=RECEIVER_ID,
        )
        owner_id = "https://example.org/users/owner"
        participant_id = "https://example.org/users/alice"
        case_id = "https://example.org/cases/bc1"

        case_actor = CaseActor(
            id_=f"{case_id}/actor",
            name=f"CaseActor for {case_id}",
            attributed_to=owner_id,
            context=case_id,
        )
        dl.create(case_actor)

        case = as_VulnerabilityCase(
            id_=case_id,
            name="Original",
            attributed_to=owner_id,
        )
        _seat(
            dl, case, participant_id, "https://example.org/participants/p-bc1"
        )
        _make_receiver_the_case_manager(dl, case)
        dl.create(case)

        updated_case = as_VulnerabilityCase(
            id_=case_id, name="Updated", attributed_to=owner_id
        )
        activity = update_case_activity(updated_case, actor=owner_id)
        event = make_payload(activity, receiving_actor_id=receiving_actor_id)

        UpdateCaseReceivedUseCase(
            dl, event, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        # The announce is authored by the actor holding CASE_MANAGER — the
        # receiver — and queued in that same actor's store, so both halves of the
        # emit are readable through the one DataLayer (ADR-0073).
        queued_ids = dl.outbox_list()
        assert len(queued_ids) == 1

        broadcast_id = queued_ids[0]
        broadcast = dl.read(broadcast_id)
        assert broadcast is not None
        broadcast = cast(VultronActivity, broadcast)
        assert broadcast.type_ == "Announce"
        assert broadcast.actor == RECEIVER_ID
        assert broadcast.to is not None
        assert participant_id in broadcast.to

    def test_update_case_no_broadcast_when_no_case_actor(self, make_payload):
        """Broadcast is skipped gracefully when no CaseActor exists."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=RECEIVER_ID,
        )
        owner_id = "https://example.org/users/owner"
        case_id = "https://example.org/cases/bc2"

        case = as_VulnerabilityCase(
            id_=case_id, name="Original", attributed_to=owner_id
        )
        dl.create(case)

        updated_case = as_VulnerabilityCase(
            id_=case_id, name="Updated", attributed_to=owner_id
        )
        activity = update_case_activity(updated_case, actor=owner_id)
        event = make_payload(activity, receiving_actor_id=RECEIVER_ID)

        # Should not raise
        UpdateCaseReceivedUseCase(
            dl, event, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        stored = dl.read(case_id)
        assert stored is not None
        stored = cast(as_VulnerabilityCase, stored)
        assert stored.name == "Updated"

    def test_update_case_no_broadcast_when_no_participants(self, make_payload):
        """Broadcast is skipped gracefully when the case has no participants."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=RECEIVER_ID,
        )
        owner_id = "https://example.org/users/owner"
        case_id = "https://example.org/cases/bc3"

        case_actor = CaseActor(
            id_=f"{case_id}/actor",
            name=f"CaseActor for {case_id}",
            attributed_to=owner_id,
            context=case_id,
        )
        dl.create(case_actor)

        case = as_VulnerabilityCase(
            id_=case_id, name="Original", attributed_to=owner_id
        )
        dl.create(case)

        updated_case = as_VulnerabilityCase(
            id_=case_id, name="Updated", attributed_to=owner_id
        )
        activity = update_case_activity(updated_case, actor=owner_id)
        event = make_payload(activity, receiving_actor_id=RECEIVER_ID)

        UpdateCaseReceivedUseCase(
            dl, event, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        queued_ids = dl.clone_for_actor(case_actor.id_).outbox_list()
        assert queued_ids == []

    def test_update_case_broadcast_includes_all_participants(
        self, make_payload
    ):
        """Broadcast Announce.to includes every participant actor ID."""
        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=RECEIVER_ID,
        )
        owner_id = "https://example.org/users/owner"
        case_id = "https://example.org/cases/bc4"
        alice = "https://example.org/users/alice"
        bob = "https://example.org/users/bob"

        case_actor = CaseActor(
            id_=f"{case_id}/actor",
            name=f"CaseActor for {case_id}",
            attributed_to=owner_id,
            context=case_id,
        )
        dl.create(case_actor)

        case = as_VulnerabilityCase(
            id_=case_id, name="Original", attributed_to=owner_id
        )
        _seat(dl, case, alice, "https://example.org/participants/p-bc4-alice")
        _seat(dl, case, bob, "https://example.org/participants/p-bc4-bob")
        _make_receiver_the_case_manager(dl, case)
        dl.create(case)

        updated_case = as_VulnerabilityCase(
            id_=case_id, name="Updated", attributed_to=owner_id
        )
        activity = update_case_activity(updated_case, actor=owner_id)
        event = make_payload(activity, receiving_actor_id=RECEIVER_ID)

        UpdateCaseReceivedUseCase(
            dl, event, trigger_activity=TriggerActivityAdapter(dl)
        ).execute()

        queued_ids = dl.outbox_list()
        broadcast_id = queued_ids[0]
        broadcast = dl.read(broadcast_id)
        assert broadcast is not None
        broadcast = cast(VultronActivity, broadcast)
        assert broadcast.to is not None
        # RECEIVER_ID is in the set because holding CASE_MANAGER makes it a
        # participant too — the role is held *in the case*, so its holder is
        # necessarily indexed there. Kept exact rather than loosened to a subset,
        # so a future change to the recipient set still fails here.
        assert set(broadcast.to) == {alice, bob, RECEIVER_ID}
