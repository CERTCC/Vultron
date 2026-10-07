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

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
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

    def test_remove_case_participant_from_case(
        self, monkeypatch, make_payload
    ):
        """RemoveCaseParticipantFromCaseReceivedUseCase removes the participant from case."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.base.objects.activities.transitive import (
            as_Remove,
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
            id_="https://example.org/cases/case2",
            name="TEST-REMOVE",
        )
        participant = as_CaseParticipant(
            id_="https://example.org/cases/case2/participants/coord",
            attributed_to="https://example.org/users/coordinator",
            context=case.id_,
        )
        case.case_participants.append(participant.id_)
        dl.create(case)
        dl.create(participant)

        remove_activity = as_Remove(
            actor="https://example.org/users/owner",
            object_=participant,
            target=case.id_,
        )

        event = make_payload(remove_activity)

        RemoveCaseParticipantFromCaseReceivedUseCase(dl, event).execute()

        case = cast(as_VulnerabilityCase, dl.read(case.id_))
        assert case is not None
        assert participant.id_ not in [
            getattr(p, "id_", p) for p in case.case_participants
        ]

    def test_remove_case_participant_idempotent(
        self, monkeypatch, make_payload
    ):
        """RemoveCaseParticipantFromCaseReceivedUseCase is idempotent when participant absent."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.base.objects.activities.transitive import (
            as_Remove,
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
            id_="https://example.org/cases/case3",
            name="TEST-REMOVE-IDEMPOTENT",
        )
        participant = as_CaseParticipant(
            id_="https://example.org/cases/case3/participants/coord",
            attributed_to="https://example.org/users/coordinator",
            context=case.id_,
        )
        # participant NOT added to case
        dl.create(case)
        dl.create(participant)

        remove_activity = as_Remove(
            actor="https://example.org/users/owner",
            object_=participant,
            target=case.id_,
        )

        event = make_payload(remove_activity)

        result = RemoveCaseParticipantFromCaseReceivedUseCase(
            dl, event
        ).execute()
        # HP-01-003: an idempotent re-removal is a no-op.
        assert result.disposition == HandlerDisposition.SKIPPED
        # The tree still ran, so intake archived the delivery (CLP-10-017).
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

    def test_remove_case_participant_clears_index(
        self, monkeypatch, make_payload
    ):
        """RemoveCaseParticipantFromCaseReceivedUseCase clears actor_participant_index (SC-PRE-2)."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.core.models.case import VulnerabilityCase
        from vultron.core.models.case_participant import CaseParticipant
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
        actor_id = "https://example.org/users/coordinator"
        case = VulnerabilityCase(
            id_="https://example.org/cases/caseRM1",
            name="TEST-REMOVE-INDEX",
            attributed_to=actor_id,
        )
        participant = as_CaseParticipant(
            id_="https://example.org/cases/caseRM1/participants/coord",
            attributed_to=actor_id,
            context=case.id_,
        )
        case.add_participant(cast(CaseParticipant, participant))
        dl.create(case)
        dl.create(participant)

        assert actor_id in case.actor_participant_index

        remove_activity = as_Remove(
            actor="https://example.org/users/owner",
            object_=participant,
            target=case.id_,
        )

        event = make_payload(remove_activity)

        RemoveCaseParticipantFromCaseReceivedUseCase(dl, event).execute()

        case = cast(VulnerabilityCase, dl.read(case.id_))
        assert case is not None
        assert actor_id not in case.actor_participant_index
