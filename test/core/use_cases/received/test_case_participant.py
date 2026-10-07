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
"""Tests for case participant use-case classes."""

from typing import cast

import pytest

from test.core.use_cases.received.conftest import (
    seed_case_manager_participant,
    seed_case_owner_participant,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.received_activity_record import (
    ReceivedActivityRecord,
)
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.use_cases.received.case_participant import (
    AddCaseParticipantToCaseReceivedUseCase,
    CreateCaseParticipantReceivedUseCase,
    RemoveCaseParticipantFromCaseReceivedUseCase,
)


class TestCaseParticipantUseCases:
    """Tests for add/remove case participant use cases."""

    @pytest.mark.spec("CM-31-001")
    def test_remove_case_participant_from_case(self, make_payload):
        """Inverted from the deletion pin: the record stays, the fact is set.

        Removal withdraws entitlement, not membership (ADR-0116).
        """
        dl, case_id, participant = _removal_store()
        event = make_payload(_owner_removes(participant, case_id))

        result = _remove(dl, event)

        assert result.disposition == HandlerDisposition.APPLIED
        case = cast(VulnerabilityCase, dl.read(case_id))
        assert participant.id_ in [
            getattr(p, "id_", p) for p in case.case_participants
        ]
        record = cast(CaseParticipant, dl.read(participant.id_))
        assert record.removal_activity == event.activity_id

    @pytest.mark.spec("CM-31-004")
    def test_remove_case_participant_not_on_the_case_is_refused(
        self, make_payload
    ):
        """A removal naming no participant of the case is refused, not skipped.

        It used to be an idempotent no-op; CM-31-004 makes it a refusal.  The
        tree still ran, so intake archived the delivery (CLP-10-017).
        """
        dl, case_id, _ = _removal_store()
        stranger = CaseParticipant(
            id_=f"{case_id}/participants/stranger",
            attributed_to="https://example.org/users/stranger",
            context=case_id,
        )
        dl.create(stranger)
        event = make_payload(_owner_removes(stranger, case_id))

        result = _remove(dl, event)

        assert result.disposition == HandlerDisposition.REFUSED
        assert dl.read(ReceivedActivityRecord.build_id(event.activity_id))

    def test_add_case_participant_updates_index(
        self, monkeypatch, make_payload
    ):
        """AddCaseParticipantToCaseReceivedUseCase updates actor_participant_index (SC-PRE-2)."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.base.objects.activities.transitive import (
            as_Add,
        )
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        actor_id = "https://example.org/users/coordinator"
        case = as_VulnerabilityCase(
            id_="https://example.org/cases/caseAP1",
            name="TEST-ADD-INDEX",
        )
        participant = as_CaseParticipant(
            id_="https://example.org/cases/caseAP1/participants/coord",
            attributed_to=actor_id,
            context=case.id_,
        )
        dl.create(case)
        dl.create(participant)

        add_activity = as_Add(
            actor="https://example.org/users/owner",
            object_=participant,
            target=case.id_,
        )

        event = make_payload(add_activity)

        result = AddCaseParticipantToCaseReceivedUseCase(dl, event).execute()

        assert result.disposition == HandlerDisposition.APPLIED
        case = cast(as_VulnerabilityCase, dl.read(case.id_))
        assert case is not None
        assert actor_id in case.actor_participant_index
        assert case.actor_participant_index[actor_id] == participant.id_

    @pytest.mark.spec("HP-01-003")
    def test_add_unknown_participant_is_refused(self, make_payload):
        """A participant the receiver has no record of cannot be added.

        This used to raise ``VultronValidationError``; it is a rejection of
        the message, so it is now reported as REFUSED (#2255).
        """
        from vultron.wire.as2.vocab.base.objects.activities.transitive import (
            as_Add,
        )
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case = as_VulnerabilityCase(
            id_="https://example.org/cases/caseRaise1",
            name="TEST-RAISE",
        )
        participant = as_CaseParticipant(
            id_="https://example.org/cases/caseRaise1/participants/coord",
            attributed_to="https://example.org/users/coordinator",
            context=case.id_,
        )
        dl.create(case)  # participant deliberately not stored

        add_activity = as_Add(
            actor="https://example.org/users/owner",
            object_=participant,
            target=case.id_,
        )
        event = make_payload(add_activity)

        result = AddCaseParticipantToCaseReceivedUseCase(dl, event).execute()

        assert result.disposition == HandlerDisposition.REFUSED
        assert result.reason is not None and "not found" in result.reason
        # A refused delivery is still archived (CLP-10-017, CLP-10-018).
        assert dl.read(ReceivedActivityRecord.build_id(event.activity_id))

    @pytest.mark.spec("HP-01-003")
    def test_remove_participant_from_unknown_case_is_refused(
        self, make_payload
    ):
        from vultron.wire.as2.vocab.base.objects.activities.transitive import (
            as_Remove,
        )
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        case_id = "https://example.org/cases/no-such-case"
        participant = as_CaseParticipant(
            id_=f"{case_id}/participants/coord",
            attributed_to="https://example.org/users/coordinator",
            context=case_id,
        )
        event = make_payload(
            as_Remove(
                actor="https://example.org/users/owner",
                object_=participant,
                target=case_id,
            )
        )

        result = RemoveCaseParticipantFromCaseReceivedUseCase(
            dl, event
        ).execute()

        assert result.disposition == HandlerDisposition.REFUSED
        assert dl.read(ReceivedActivityRecord.build_id(event.activity_id))

    @pytest.mark.spec("HP-01-003")
    @pytest.mark.parametrize(
        "use_case, activity_name",
        [
            (AddCaseParticipantToCaseReceivedUseCase, "as_Add"),
            (RemoveCaseParticipantFromCaseReceivedUseCase, "as_Remove"),
        ],
    )
    def test_membership_change_without_ids_is_refused(
        self, use_case, activity_name, make_payload
    ):
        from vultron.wire.as2.vocab.base.objects.activities import transitive
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        event = make_payload(
            getattr(transitive, activity_name)(
                actor="https://example.org/users/owner",
                object_=as_CaseParticipant(
                    id_="https://example.org/cases/c/participants/p",
                    attributed_to="https://example.org/users/coordinator",
                    context="https://example.org/cases/c",
                ),
                target="https://example.org/cases/c",
            )
        ).model_copy(update={"object_": None, "object_id": None})
        assert event.participant_id is None

        result = use_case(dl, event).execute()

        assert result.disposition == HandlerDisposition.REFUSED
        # The refusal came before the real tree could be built, but the
        # delivery is still archived (CLP-10-018).
        assert dl.read(ReceivedActivityRecord.build_id(event.activity_id))

    @pytest.mark.spec("HP-01-003")
    def test_create_participant_redelivery_is_skipped(self, make_payload):
        from vultron.wire.as2.factories import create_participant_activity
        from vultron.wire.as2.vocab.objects.case_participant import (
            as_CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        dl = SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id="https://test.example/api/v2/actors/test-actor",
        )
        participant = as_CaseParticipant(
            id_="https://example.org/cases/caseCP/participants/coord",
            attributed_to="https://example.org/users/coordinator",
            context="https://example.org/cases/caseCP",
        )
        event = make_payload(
            create_participant_activity(
                participant,
                target="https://example.org/cases/caseCP",
                actor="https://example.org/users/coordinator",
                context=as_VulnerabilityCase(
                    id_="https://example.org/cases/caseCP", name="CP"
                ),
            )
        )

        first = CreateCaseParticipantReceivedUseCase(dl, event).execute()
        again = CreateCaseParticipantReceivedUseCase(dl, event).execute()

        assert first.disposition == HandlerDisposition.APPLIED
        assert again.disposition == HandlerDisposition.SKIPPED

    @pytest.mark.spec("CM-19-002")
    def test_remove_case_participant_keeps_index(self, make_payload):
        """Inverted from the index-clearing pin: the index entry stays."""
        dl, case_id, participant = _removal_store()
        event = make_payload(_owner_removes(participant, case_id))

        _remove(dl, event)

        case = cast(VulnerabilityCase, dl.read(case_id))
        assert case.actor_participant_index[_COORDINATOR] == participant.id_


_MANAGER = "https://test.example/api/v2/actors/test-actor"
_OWNER = "https://example.org/users/owner"
_COORDINATOR = "https://example.org/users/coordinator"


def _removal_store() -> tuple[SqliteDataLayer, str, CaseParticipant]:
    """A CASE_MANAGER store: the manager, the Case Owner and a coordinator."""
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=_MANAGER)
    case = VulnerabilityCase(
        id_="https://example.org/cases/caseRM1",
        name="TEST-REMOVE",
        attributed_to=_OWNER,
    )
    seed_case_manager_participant(dl, case, _MANAGER)
    seed_case_owner_participant(dl, case, _OWNER)
    participant = CaseParticipant(
        id_=f"{case.id_}/participants/coord",
        attributed_to=_COORDINATOR,
        context=case.id_,
    )
    dl.create(participant)
    case.add_participant(participant)
    dl.create(case)
    return dl, case.id_, participant


def _owner_removes(participant: CaseParticipant, case_id: str):
    from vultron.wire.as2.factories import (
        remove_participant_from_case_activity,
    )

    return remove_participant_from_case_activity(
        participant, target=case_id, actor=_OWNER
    )


def _remove(dl: SqliteDataLayer, event):
    from vultron.adapters.driven.sync_activity_adapter import (
        SyncActivityAdapter,
    )
    from vultron.adapters.driven.trigger_activity_adapter import (
        TriggerActivityAdapter,
    )
    from vultron.adapters.driven.wire_render import As2WireRenderAdapter

    return RemoveCaseParticipantFromCaseReceivedUseCase(
        dl,
        event,
        sync_port=SyncActivityAdapter(dl),
        trigger_activity=TriggerActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()
