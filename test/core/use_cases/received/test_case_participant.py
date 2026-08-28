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

from vultron.core.use_cases.received.case_participant import (
    AddCaseParticipantToCaseReceivedUseCase,
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
            target=case,
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
            target=case,
        )

        event = make_payload(remove_activity)

        result = RemoveCaseParticipantFromCaseReceivedUseCase(
            dl, event
        ).execute()
        assert result is None

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
            target=case,
        )

        event = make_payload(add_activity)

        AddCaseParticipantToCaseReceivedUseCase(dl, event).execute()

        case = cast(as_VulnerabilityCase, dl.read(case.id_))
        assert case is not None
        assert actor_id in case.actor_participant_index
        assert case.actor_participant_index[actor_id] == participant.id_

    def test_add_case_participant_bt_failure_raises(
        self, monkeypatch, make_payload
    ):
        """AddCaseParticipantToCaseReceivedUseCase must raise when the BT fails."""
        from unittest.mock import MagicMock, patch

        from py_trees.common import Status

        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.errors import VultronValidationError
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
        dl.create(case)
        dl.create(participant)

        add_activity = as_Add(
            actor="https://example.org/users/owner",
            object_=participant,
            target=case,
        )
        event = make_payload(add_activity)

        failure_result = MagicMock()
        failure_result.status = Status.FAILURE

        with patch(
            "vultron.core.use_cases.received.case_participant.BTBridge"
        ) as MockBridge:
            bridge_instance = MockBridge.return_value
            bridge_instance.execute_with_setup.return_value = failure_result
            MockBridge.get_failure_reason.return_value = "tree failed"

            with pytest.raises(VultronValidationError):
                AddCaseParticipantToCaseReceivedUseCase(dl, event).execute()

    def test_remove_case_participant_clears_index(
        self, monkeypatch, make_payload
    ):
        """RemoveCaseParticipantFromCaseReceivedUseCase clears actor_participant_index (SC-PRE-2)."""
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
        from vultron.wire.as2.vocab.base.objects.activities.transitive import (
            as_Remove,
        )
        from vultron.core.models.case import VulnerabilityCase
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
        case.add_participant(participant)
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
