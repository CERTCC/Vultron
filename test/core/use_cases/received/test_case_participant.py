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
        from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
        from vultron.wire.as2.vocab.base.objects.activities.transitive import (
            as_Remove,
        )
        from vultron.wire.as2.vocab.objects.case_participant import (
            CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = TinyDbDataLayer(db_path=None)
        case = VulnerabilityCase(
            as_id="https://example.org/cases/case2",
            name="TEST-REMOVE",
        )
        participant = CaseParticipant(
            as_id="https://example.org/cases/case2/participants/coord",
            attributed_to="https://example.org/users/coordinator",
            context=case.as_id,
        )
        case.case_participants.append(participant.as_id)
        dl.create(case)
        dl.create(participant)

        remove_activity = as_Remove(
            actor="https://example.org/users/owner",
            as_object=participant,
            target=case,
        )

        event = make_payload(remove_activity)

        RemoveCaseParticipantFromCaseReceivedUseCase(dl, event).execute()

        case = cast(VulnerabilityCase, dl.read(case.as_id))
        assert case is not None
        assert participant.as_id not in [
            getattr(p, "as_id", p) for p in case.case_participants
        ]

    def test_remove_case_participant_idempotent(
        self, monkeypatch, make_payload
    ):
        """RemoveCaseParticipantFromCaseReceivedUseCase is idempotent when participant absent."""
        from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
        from vultron.wire.as2.vocab.base.objects.activities.transitive import (
            as_Remove,
        )
        from vultron.wire.as2.vocab.objects.case_participant import (
            CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = TinyDbDataLayer(db_path=None)

        case = VulnerabilityCase(
            as_id="https://example.org/cases/case3",
            name="TEST-REMOVE-IDEMPOTENT",
        )
        participant = CaseParticipant(
            as_id="https://example.org/cases/case3/participants/coord",
            attributed_to="https://example.org/users/coordinator",
            context=case.as_id,
        )
        # participant NOT added to case
        dl.create(case)
        dl.create(participant)

        remove_activity = as_Remove(
            actor="https://example.org/users/owner",
            as_object=participant,
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
        from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
        from vultron.wire.as2.vocab.base.objects.activities.transitive import (
            as_Add,
        )
        from vultron.wire.as2.vocab.objects.case_participant import (
            CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = TinyDbDataLayer(db_path=None)
        actor_id = "https://example.org/users/coordinator"
        case = VulnerabilityCase(
            as_id="https://example.org/cases/caseAP1",
            name="TEST-ADD-INDEX",
        )
        participant = CaseParticipant(
            as_id="https://example.org/cases/caseAP1/participants/coord",
            attributed_to=actor_id,
            context=case.as_id,
        )
        dl.create(case)
        dl.create(participant)

        add_activity = as_Add(
            actor="https://example.org/users/owner",
            as_object=participant,
            target=case,
        )

        event = make_payload(add_activity)

        AddCaseParticipantToCaseReceivedUseCase(dl, event).execute()

        case = cast(VulnerabilityCase, dl.read(case.as_id))
        assert case is not None
        assert actor_id in case.actor_participant_index
        assert case.actor_participant_index[actor_id] == participant.as_id

    def test_remove_case_participant_clears_index(
        self, monkeypatch, make_payload
    ):
        """RemoveCaseParticipantFromCaseReceivedUseCase clears actor_participant_index (SC-PRE-2)."""
        from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
        from vultron.wire.as2.vocab.base.objects.activities.transitive import (
            as_Remove,
        )
        from vultron.wire.as2.vocab.objects.case_participant import (
            CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            VulnerabilityCase,
        )

        dl = TinyDbDataLayer(db_path=None)
        actor_id = "https://example.org/users/coordinator"
        case = VulnerabilityCase(
            as_id="https://example.org/cases/caseRM1",
            name="TEST-REMOVE-INDEX",
        )
        participant = CaseParticipant(
            as_id="https://example.org/cases/caseRM1/participants/coord",
            attributed_to=actor_id,
            context=case.as_id,
        )
        case.add_participant(participant)
        dl.create(case)
        dl.create(participant)

        assert actor_id in case.actor_participant_index

        remove_activity = as_Remove(
            actor="https://example.org/users/owner",
            as_object=participant,
            target=case,
        )

        event = make_payload(remove_activity)

        RemoveCaseParticipantFromCaseReceivedUseCase(dl, event).execute()

        case = cast(VulnerabilityCase, dl.read(case.as_id))
        assert case is not None
        assert actor_id not in case.actor_participant_index
