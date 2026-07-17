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
"""Tests for status-related use-case classes."""

import json
from typing import cast

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.core.models.case_actor import VultronCaseActor
from vultron.core.models.case_ledger_entry import VultronCaseLedgerEntry
from vultron.core.models.protocols import is_log_entry_model
from vultron.core.states.em import EM
from vultron.core.states.rm import RM
from vultron.core.use_cases.received.status import (
    AddCaseStatusToCaseReceivedUseCase,
    AddParticipantStatusToParticipantReceivedUseCase,
    CreateCaseStatusReceivedUseCase,
    CreateParticipantStatusReceivedUseCase,
)
from vultron.wire.as2.factories import (
    add_status_to_case_activity,
    add_status_to_participant_activity,
    create_case_status_activity,
    create_status_for_participant_activity,
)
from vultron.wire.as2.vocab.objects.case_participant import as_CaseParticipant
from vultron.wire.as2.vocab.objects.case_status import (
    as_CaseStatus,
    as_ParticipantStatus,
)
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)


class TestStatusUseCases:
    """Tests for case status and participant status handlers."""

    def test_create_case_status_stores_status(self, monkeypatch, make_payload):
        """create_case_status persists the as_CaseStatus to the DataLayer."""

        dl = SqliteDataLayer("sqlite:///:memory:")

        case = as_VulnerabilityCase(
            id_="https://example.org/cases/case_cs1",
            name="Case Status Test",
        )
        status = as_CaseStatus(
            id_="https://example.org/cases/case_cs1/statuses/s1",
            context=case.id_,
        )
        activity = create_case_status_activity(
            status, actor="https://example.org/users/vendor", context=case.id_
        )

        event = make_payload(activity)

        CreateCaseStatusReceivedUseCase(dl, event).execute()

        stored = dl.get(status.type_.value, status.id_)
        assert stored is not None

    def test_create_case_status_idempotent(self, monkeypatch, make_payload):
        """create_case_status skips storing a duplicate as_CaseStatus."""
        dl = SqliteDataLayer("sqlite:///:memory:")

        case = as_VulnerabilityCase(
            id_="https://example.org/cases/case_cs2",
            name="Case Status Idempotent",
        )
        status = as_CaseStatus(
            id_="https://example.org/cases/case_cs2/statuses/s2",
            context=case.id_,
        )
        dl.create(status)

        activity = create_case_status_activity(
            status, actor="https://example.org/users/vendor", context=case.id_
        )
        event = make_payload(activity)

        CreateCaseStatusReceivedUseCase(dl, event).execute()

        stored = dl.get(status.type_.value, status.id_)
        assert stored is not None

    def test_add_case_status_to_case_appends_status(
        self, monkeypatch, make_payload
    ):
        """add_case_status_to_case appends status ID to case.case_statuses."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case = as_VulnerabilityCase(
            id_="https://example.org/cases/case_cs3",
            name="Add Status Case",
        )
        status = as_CaseStatus(
            id_="https://example.org/cases/case_cs3/statuses/s3",
            context=case.id_,
        )
        dl.create(case)
        dl.create(status)

        activity = add_status_to_case_activity(
            status, target=case, actor="https://example.org/users/vendor"
        )
        event = make_payload(activity)

        AddCaseStatusToCaseReceivedUseCase(dl, event).execute()

        case = dl.read(case.id_)
        assert case is not None
        case = cast(as_VulnerabilityCase, case)
        status_ids = [getattr(s, "id_", s) for s in case.case_statuses]
        assert status.id_ in status_ids

    def test_add_case_status_blocks_invalid_em_transition(
        self, monkeypatch, make_payload
    ):
        """Invalid EM transition is blocked; status is not appended."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case = as_VulnerabilityCase(
            id_="https://example.org/cases/case_em_guard",
            name="EM Guard Test Case",
        )
        # Seed an existing status with EM.NONE (the initial embargo state)
        initial_status = as_CaseStatus(
            id_="https://example.org/cases/case_em_guard/statuses/s_init",
            context=case.id_,
            em_state=EM.NONE,
        )
        case.case_statuses.append(initial_status)
        dl.create(case)

        # Try to add a status with EM.ACTIVE — invalid: NONE → ACTIVE
        # skips the required PROPOSED intermediate state
        bad_status = as_CaseStatus(
            id_="https://example.org/cases/case_em_guard/statuses/s_bad",
            context=case.id_,
            em_state=EM.ACTIVE,
        )
        dl.create(bad_status)

        activity = add_status_to_case_activity(
            bad_status, target=case, actor="https://example.org/users/vendor"
        )
        event = make_payload(activity)

        AddCaseStatusToCaseReceivedUseCase(dl, event).execute()

        updated_case = dl.read(case.id_)
        assert updated_case is not None
        updated_case = cast(as_VulnerabilityCase, updated_case)
        status_ids = [getattr(s, "id_", s) for s in updated_case.case_statuses]
        assert (
            bad_status.id_ not in status_ids
        ), "Bad status should not have been appended"

    def test_add_case_status_allows_valid_em_transition(
        self, monkeypatch, make_payload
    ):
        """Valid EM transition is permitted; status is appended."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        case = as_VulnerabilityCase(
            id_="https://example.org/cases/case_em_valid",
            name="EM Valid Transition Case",
        )
        initial_status = as_CaseStatus(
            id_="https://example.org/cases/case_em_valid/statuses/s_init",
            context=case.id_,
            em_state=EM.NONE,
        )
        case.case_statuses.append(initial_status)
        dl.create(case)

        # NONE → PROPOSED is a valid transition
        good_status = as_CaseStatus(
            id_="https://example.org/cases/case_em_valid/statuses/s_good",
            context=case.id_,
            em_state=EM.PROPOSED,
        )
        dl.create(good_status)

        activity = add_status_to_case_activity(
            good_status, target=case, actor="https://example.org/users/vendor"
        )
        event = make_payload(activity)

        AddCaseStatusToCaseReceivedUseCase(dl, event).execute()

        updated_case = dl.read(case.id_)
        assert updated_case is not None
        updated_case = cast(as_VulnerabilityCase, updated_case)
        status_ids = [getattr(s, "id_", s) for s in updated_case.case_statuses]
        assert good_status.id_ in status_ids

    def test_create_participant_status_stores_status(
        self, monkeypatch, make_payload
    ):
        """create_participant_status persists the as_ParticipantStatus."""
        dl = SqliteDataLayer("sqlite:///:memory:")

        pstatus = as_ParticipantStatus(
            id_="https://example.org/cases/case_ps1/participants/p1/statuses/s1",
            context="https://example.org/cases/case_ps1",
        )
        case_ps1 = as_VulnerabilityCase(
            id_="https://example.org/cases/case_ps1",
            name="PS Case 1",
        )
        activity = create_status_for_participant_activity(
            pstatus, actor="https://example.org/users/vendor", context=case_ps1
        )

        event = make_payload(activity)

        CreateParticipantStatusReceivedUseCase(dl, event).execute()

        stored = dl.get(pstatus.type_.value, pstatus.id_)
        assert stored is not None

    def test_add_participant_status_to_participant_appends_status(
        self, monkeypatch, make_payload
    ):
        """add_participant_status_to_participant appends status to participant."""
        dl = SqliteDataLayer("sqlite:///:memory:")
        participant = as_CaseParticipant(
            id_="https://example.org/cases/case_ps2/participants/p2",
            context="https://example.org/cases/case_ps2",
            attributed_to="https://example.org/users/vendor",
        )
        pstatus = as_ParticipantStatus(
            id_="https://example.org/cases/case_ps2/participants/p2/statuses/s2",
            context="https://example.org/cases/case_ps2",
        )
        case_ps2 = as_VulnerabilityCase(
            id_="https://example.org/cases/case_ps2",
            name="PS Case 2",
        )
        # Register the vendor actor as a participant so step 1 passes
        case_ps2.case_participants.append(participant.id_)
        case_ps2.actor_participant_index[
            "https://example.org/users/vendor"
        ] = participant.id_
        dl.create(participant)
        dl.create(pstatus)
        dl.create(case_ps2)

        activity = add_status_to_participant_activity(
            pstatus,
            target=participant,
            actor="https://example.org/users/vendor",
            context=case_ps2,
        )
        event = make_payload(
            activity,
            receiving_actor_id="https://example.org/users/vendor",
        )

        AddParticipantStatusToParticipantReceivedUseCase(dl, event).execute()

        participant = dl.read(participant.id_)
        assert participant is not None
        participant = cast(as_CaseParticipant, participant)
        status_ids = [
            getattr(s, "id_", s) for s in participant.participant_statuses
        ]
        assert pstatus.id_ in status_ids


# ---------------------------------------------------------------------------
# CaseLedgerEntry cascade tests (PCR-08-003, PCR-08-004) — AC-2
# ---------------------------------------------------------------------------


class TestParticipantStatusLogEntryCascade:
    """CaseLedgerEntry cascade for AddParticipantStatusToParticipantReceivedUseCase."""

    def _make_dl(self, case_id: str, actor_id: str) -> tuple:
        from vultron.enums.roles import CVDRole

        dl = SqliteDataLayer("sqlite:///:memory:")
        case_actor_id = f"{case_id}/actor"
        case_actor = VultronCaseActor(
            id_=case_actor_id,
            name=f"CaseActor for {case_id}",
            attributed_to=actor_id,
            context=case_id,
        )
        dl.create(case_actor)

        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        case = as_VulnerabilityCase(
            id_=case_id,
            name="Status Cascade Case",
            attributed_to=actor_id,
        )
        case_manager_participant_id = f"{case_id}/participants/case-actor-p"
        case.case_participants.append(case_manager_participant_id)
        case.actor_participant_index[case_actor_id] = (
            case_manager_participant_id
        )
        case.case_participants.append(f"{case_id}/participants/p1")
        case.actor_participant_index[actor_id] = f"{case_id}/participants/p1"
        # Add Case Manager participant so FindCaseManagerNode can succeed.
        cm_participant_id = f"{case_id}/participants/cm"
        case.case_participants.append(cm_participant_id)
        case.actor_participant_index[case_actor_id] = cm_participant_id
        dl.create(case)

        case_manager_participant = as_CaseParticipant(
            id_=case_manager_participant_id,
            context=case_id,
            attributed_to=case_actor_id,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        dl.create(case_manager_participant)

        participant = as_CaseParticipant(
            id_=f"{case_id}/participants/p1",
            context=case_id,
            attributed_to=actor_id,
        )
        dl.create(participant)

        cm_participant = as_CaseParticipant(
            id_=cm_participant_id,
            context=case_id,
            attributed_to=case_actor_id,
            case_roles=[CVDRole.CASE_MANAGER],
        )
        dl.create(cm_participant)

        pstatus = as_ParticipantStatus(
            id_=f"{case_id}/participants/p1/statuses/s1",
            context=case_id,
        )
        dl.create(pstatus)

        return dl, case_actor_id, participant, pstatus

    def test_cascade_commits_log_entry_on_success(self, make_payload):
        """Cascade commits a CaseLedgerEntry when BT succeeds (AC-2)."""
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        actor_id = "https://example.org/users/vendor"
        case_id = "https://example.org/cases/st_le1"
        dl, case_actor_id, participant, pstatus = self._make_dl(
            case_id, actor_id
        )
        case = cast(as_VulnerabilityCase, dl.read(case_id))
        assert case is not None

        activity = add_status_to_participant_activity(
            pstatus,
            target=participant,
            actor=actor_id,
            context=case,
        )
        event = make_payload(activity, receiving_actor_id=case_actor_id)
        sync_port = SyncActivityAdapter(dl)
        AddParticipantStatusToParticipantReceivedUseCase(
            dl, event, sync_port=sync_port
        ).execute()

        entries = [
            obj
            for obj in dl.list_objects("CaseLedgerEntry")
            if is_log_entry_model(obj)
            and cast(VultronCaseLedgerEntry, obj).case_id == case_id
        ]
        assert len(entries) == 1
        assert cast(VultronCaseLedgerEntry, entries[0]).event_type == (
            "add_participant_status_to_participant"
        )

    def test_no_fanout_without_sync_port(self, make_payload):
        """No fan-out Announce(CaseLedgerEntry) is sent when sync_port is None.

        The log entry IS committed locally, but no outbox messages are queued
        for delivery to participants.
        """
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        actor_id = "https://example.org/users/vendor"
        case_id = "https://example.org/cases/st_le2"
        dl, case_actor_id, participant, pstatus = self._make_dl(
            case_id, actor_id
        )
        case = cast(as_VulnerabilityCase, dl.read(case_id))
        assert case is not None

        activity = add_status_to_participant_activity(
            pstatus,
            target=participant,
            actor=actor_id,
            context=case,
        )
        event = make_payload(activity, receiving_actor_id=case_actor_id)
        AddParticipantStatusToParticipantReceivedUseCase(
            dl, event, sync_port=None
        ).execute()

        # Log entry MUST be committed locally even without a sync_port.
        entries = [
            obj
            for obj in dl.list_objects("CaseLedgerEntry")
            if is_log_entry_model(obj)
            and cast(VultronCaseLedgerEntry, obj).case_id == case_id
        ]
        assert len(entries) == 1

        # But no outbox activities should be queued for fan-out.
        assert dl.outbox_list() == []

    def test_terminal_closed_update_does_not_commit_log_entry(
        self, make_payload
    ) -> None:
        """CLOSED->CLOSED rewrites are rejected before log cascade."""
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        actor_id = "https://example.org/users/vendor"
        case_id = "https://example.org/cases/st_le3"
        dl, case_actor_id, participant, _ = self._make_dl(case_id, actor_id)
        case = cast(as_VulnerabilityCase, dl.read(case_id))
        assert case is not None

        closed_status = as_ParticipantStatus(
            id_=f"{case_id}/participants/p1/statuses/closed-existing",
            context=case_id,
            rm_state=RM.CLOSED,
        )
        participant.participant_statuses.append(closed_status)
        dl.save(participant)
        dl.create(closed_status)

        duplicate_closed_status = as_ParticipantStatus(
            id_=f"{case_id}/participants/p1/statuses/closed-duplicate",
            context=case_id,
            rm_state=RM.CLOSED,
        )
        dl.create(duplicate_closed_status)

        activity = add_status_to_participant_activity(
            duplicate_closed_status,
            target=participant,
            actor=actor_id,
            context=case,
        )
        event = make_payload(activity, receiving_actor_id=case_actor_id)
        sync_port = SyncActivityAdapter(dl)

        before_count = len(participant.participant_statuses)
        AddParticipantStatusToParticipantReceivedUseCase(
            dl, event, sync_port=sync_port
        ).execute()

        entries = [
            obj
            for obj in dl.list_objects("CaseLedgerEntry")
            if is_log_entry_model(obj)
            and cast(VultronCaseLedgerEntry, obj).case_id == case_id
        ]
        assert entries == []

        updated_participant = dl.read(participant.id_)
        assert updated_participant is not None
        assert len(updated_participant.participant_statuses) == before_count

    def test_duplicate_assertion_reuses_existing_log_entry(
        self, make_payload
    ) -> None:
        """Two equivalent assertions append only one canonical log entry."""
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        actor_id = "https://example.org/users/vendor"
        case_id = "https://example.org/cases/st_le4"
        dl, case_actor_id, participant, pstatus = self._make_dl(
            case_id, actor_id
        )
        case = cast(as_VulnerabilityCase, dl.read(case_id))
        assert case is not None

        activity = add_status_to_participant_activity(
            pstatus,
            target=participant,
            actor=actor_id,
            context=case,
        )
        event = make_payload(activity, receiving_actor_id=case_actor_id)
        sync_port = SyncActivityAdapter(dl)
        uc = AddParticipantStatusToParticipantReceivedUseCase(
            dl, event, sync_port=sync_port
        )

        uc.execute()
        uc.execute()

        entries = [
            obj
            for obj in dl.list_objects("CaseLedgerEntry")
            if is_log_entry_model(obj)
            and cast(VultronCaseLedgerEntry, obj).case_id == case_id
        ]
        assert len(entries) == 1

    def test_non_case_actor_receiver_does_not_commit_log_entry(
        self, make_payload
    ) -> None:
        """Peer-side replay of broadcast status must not append canonical entries."""
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        actor_id = "https://example.org/users/vendor"
        non_case_actor_id = "https://example.org/users/finder"
        case_id = "https://example.org/cases/st_le5"
        dl, case_actor_id, participant, pstatus = self._make_dl(
            case_id, actor_id
        )
        case = cast(as_VulnerabilityCase, dl.read(case_id))
        assert case is not None

        peer = as_CaseParticipant(
            id_=f"{case_id}/participants/p2",
            context=case_id,
            attributed_to=non_case_actor_id,
        )
        dl.create(peer)
        case.case_participants.append(peer.id_)
        case.actor_participant_index[non_case_actor_id] = peer.id_
        dl.save(case)

        activity = add_status_to_participant_activity(
            pstatus,
            target=participant,
            actor=case_actor_id,
            context=case,
        )
        event = make_payload(activity, receiving_actor_id=non_case_actor_id)
        AddParticipantStatusToParticipantReceivedUseCase(
            dl, event, sync_port=SyncActivityAdapter(dl)
        ).execute()

        entries = [
            obj
            for obj in dl.list_objects("CaseLedgerEntry")
            if is_log_entry_model(obj)
            and cast(VultronCaseLedgerEntry, obj).case_id == case_id
        ]
        assert entries == []

    def test_commit_path_preserves_snapshot_actor_and_fanout_payload_identity(
        self, make_payload
    ) -> None:
        """Stored snapshot keeps asserter actor and announce payload is identical."""
        from unittest.mock import MagicMock

        from vultron.wire.as2.enums import as_TransitiveActivityType
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        reporter_actor_id = "https://example.org/users/vendor"
        finder_actor_id = "https://example.org/users/finder"
        case_id = "https://example.org/cases/st_le6"
        dl, case_actor_id, participant, pstatus = self._make_dl(
            case_id, reporter_actor_id
        )
        case = cast(as_VulnerabilityCase, dl.read(case_id))
        assert case is not None

        finder_participant = as_CaseParticipant(
            id_=f"{case_id}/participants/finder",
            context=case_id,
            attributed_to=finder_actor_id,
        )
        dl.create(finder_participant)
        case.case_participants.append(finder_participant.id_)
        case.actor_participant_index[finder_actor_id] = finder_participant.id_
        dl.save(case)

        activity = add_status_to_participant_activity(
            pstatus,
            target=participant,
            actor=reporter_actor_id,
            context=case,
        )
        event = make_payload(activity, receiving_actor_id=case_actor_id)
        # Supply a trigger_activity mock so AutoCloseBranchNode can emit
        # close_case if all participants close (BT step 5).
        mock_trigger = MagicMock()
        mock_trigger.add_participant_status_to_participant.return_value = (
            "urn:uuid:broadcast-1"
        )
        AddParticipantStatusToParticipantReceivedUseCase(
            dl,
            event,
            trigger_activity=mock_trigger,
            sync_port=SyncActivityAdapter(dl),
        ).execute()

        entries = [
            cast(VultronCaseLedgerEntry, obj)
            for obj in dl.list_objects("CaseLedgerEntry")
            if is_log_entry_model(obj)
            and cast(VultronCaseLedgerEntry, obj).case_id == case_id
        ]
        assert len(entries) == 1
        assert entries[0].payload_snapshot.get("actor") == reporter_actor_id

        announce_ids = []
        announce_payloads = []
        announce_actors = []
        for activity_id in dl.outbox_list_for_actor(case_actor_id):
            queued = dl.read(activity_id)
            if (
                queued is None
                or getattr(queued, "type_", None)
                != as_TransitiveActivityType.ANNOUNCE
            ):
                continue
            queued_object = getattr(queued, "object_", None)
            if (
                queued_object is None
                or getattr(queued_object, "type_", None) != "CaseLedgerEntry"
            ):
                continue
            announce_ids.append(activity_id)
            announce_actors.append(getattr(queued, "actor", None))
            announce_payloads.append(
                json.dumps(
                    queued_object.model_dump(
                        mode="json",
                        by_alias=True,
                        exclude_none=True,
                        serialize_as_any=True,
                    ),
                    sort_keys=True,
                    separators=(",", ":"),
                )
            )

        assert len(announce_ids) == 2
        assert all(actor == case_actor_id for actor in announce_actors)
        assert len(set(announce_payloads)) == 1
