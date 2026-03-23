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
"""Tests for case-related use-case classes."""

from vultron.core.use_cases.case import UpdateCaseReceivedUseCase
from vultron.wire.as2.vocab.objects.vulnerability_case import VulnerabilityCase


def _make_payload(activity, **extra_fields):
    from vultron.wire.as2.extractor import extract_intent

    event = extract_intent(activity)
    if extra_fields:
        return event.model_copy(update=extra_fields)
    return event


class TestCaseUseCases:
    """Tests for update_case handler."""

    def test_update_case_applies_scalar_updates(self, monkeypatch, caplog):
        """update_case applies name/summary/content updates from a full object."""
        import logging

        from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.case import UpdateCaseActivity

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.wire.as2.rehydration.get_datalayer",
            lambda **_: dl,
        )

        owner_id = "https://example.org/users/owner"
        case = VulnerabilityCase(
            id="https://example.org/cases/uc1",
            name="Original Name",
            attributed_to=owner_id,
        )
        dl.create(case)

        updated_case = VulnerabilityCase(
            id=case.as_id,
            name="Updated Name",
            content="New content",
            attributed_to=owner_id,
        )
        activity = UpdateCaseActivity(
            actor=owner_id,
            object=updated_case,
        )
        event = _make_payload(activity)

        from vultron.wire.as2.rehydration import rehydrate as real_rehydrate

        def _mock_rehydrate(obj, **kwargs):
            if obj == case.as_id:
                return updated_case
            return real_rehydrate(obj, **kwargs)

        monkeypatch.setattr(
            "vultron.wire.as2.rehydration.rehydrate",
            _mock_rehydrate,
        )

        with caplog.at_level(logging.INFO):
            UpdateCaseReceivedUseCase(dl, event).execute()

        stored = dl.read(case.as_id)
        assert stored is not None
        assert stored.name == "Updated Name"
        assert stored.content == "New content"

    def test_update_case_rejects_non_owner(self, monkeypatch, caplog):
        """update_case logs a warning and skips if actor is not the case owner."""
        import logging

        from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.case import UpdateCaseActivity

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.wire.as2.rehydration.get_datalayer",
            lambda **_: dl,
        )

        owner_id = "https://example.org/users/owner"
        non_owner_id = "https://example.org/users/other"
        case = VulnerabilityCase(
            id="https://example.org/cases/uc2",
            name="Original Name",
            attributed_to=owner_id,
        )
        dl.create(case)

        updated_case = VulnerabilityCase(
            id=case.as_id,
            name="Hijacked Name",
            attributed_to=owner_id,
        )
        activity = UpdateCaseActivity(
            actor=non_owner_id,
            object=updated_case,
        )
        event = _make_payload(activity)

        with caplog.at_level(logging.WARNING):
            UpdateCaseReceivedUseCase(dl, event).execute()

        stored = dl.read(case.as_id)
        assert stored is not None
        assert stored.name == "Original Name"
        assert any("not the owner" in r.message for r in caplog.records)

    def test_update_case_idempotent(self, monkeypatch):
        """update_case with same data produces the same result (last-write-wins)."""
        from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.case import UpdateCaseActivity

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.wire.as2.rehydration.get_datalayer",
            lambda **_: dl,
        )

        owner_id = "https://example.org/users/owner"
        case = VulnerabilityCase(
            id="https://example.org/cases/uc3",
            name="Original",
            attributed_to=owner_id,
        )
        dl.create(case)

        updated_case = VulnerabilityCase(
            id=case.as_id,
            name="Updated",
            attributed_to=owner_id,
        )
        activity = UpdateCaseActivity(
            actor=owner_id,
            object=updated_case,
        )
        event = _make_payload(activity)

        from vultron.wire.as2.rehydration import rehydrate as real_rehydrate

        def _mock_rehydrate(obj, **kwargs):
            if obj == case.as_id:
                return updated_case
            return real_rehydrate(obj, **kwargs)

        monkeypatch.setattr(
            "vultron.wire.as2.rehydration.rehydrate",
            _mock_rehydrate,
        )

        UpdateCaseReceivedUseCase(dl, event).execute()
        UpdateCaseReceivedUseCase(dl, event).execute()

        stored = dl.read(case.as_id)
        assert stored is not None
        assert stored.name == "Updated"

    def test_update_case_warns_when_participant_has_not_accepted_embargo(
        self, monkeypatch, caplog
    ):
        """update_case logs WARNING per CM-10-004 when a participant has not accepted the active embargo."""
        import logging

        from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.case import UpdateCaseActivity
        from vultron.wire.as2.vocab.objects.case_participant import (
            CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.wire.as2.rehydration.get_datalayer",
            lambda **_: dl,
        )

        owner_id = "https://example.org/users/owner"
        actor_id = "https://example.org/users/alice"
        embargo = EmbargoEvent(id="https://example.org/embargoes/em1")
        dl.create(embargo)

        participant = CaseParticipant(
            id="https://example.org/participants/p1",
            attributed_to=actor_id,
            context="https://example.org/cases/uc4",
            accepted_embargo_ids=[],
        )
        dl.create(participant)

        case = VulnerabilityCase(
            id="https://example.org/cases/uc4",
            name="Original",
            attributed_to=owner_id,
            active_embargo=embargo.as_id,
        )
        case.actor_participant_index[actor_id] = participant.as_id
        dl.create(case)

        updated_case = VulnerabilityCase(
            id=case.as_id,
            name="Updated",
            attributed_to=owner_id,
        )
        activity = UpdateCaseActivity(actor=owner_id, object=updated_case)
        event = _make_payload(activity)

        with caplog.at_level(logging.WARNING):
            UpdateCaseReceivedUseCase(dl, event).execute()

        assert any(
            "has not accepted" in r.message and "CM-10-004" in r.message
            for r in caplog.records
        )

    def test_update_case_no_warning_when_all_participants_accepted_embargo(
        self, monkeypatch, caplog
    ):
        """update_case does NOT warn when all participants have accepted the active embargo (CM-10-004)."""
        import logging

        from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.case import UpdateCaseActivity
        from vultron.wire.as2.vocab.objects.case_participant import (
            CaseParticipant,
        )
        from vultron.wire.as2.vocab.objects.embargo_event import EmbargoEvent

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.wire.as2.rehydration.get_datalayer",
            lambda **_: dl,
        )

        owner_id = "https://example.org/users/owner"
        actor_id = "https://example.org/users/bob"
        embargo = EmbargoEvent(id="https://example.org/embargoes/em2")
        dl.create(embargo)

        participant = CaseParticipant(
            id="https://example.org/participants/p2",
            attributed_to=actor_id,
            context="https://example.org/cases/uc5",
            accepted_embargo_ids=[embargo.as_id],
        )
        dl.create(participant)

        case = VulnerabilityCase(
            id="https://example.org/cases/uc5",
            name="Original",
            attributed_to=owner_id,
            active_embargo=embargo.as_id,
        )
        case.actor_participant_index[actor_id] = participant.as_id
        dl.create(case)

        updated_case = VulnerabilityCase(
            id=case.as_id,
            name="Updated",
            attributed_to=owner_id,
        )
        activity = UpdateCaseActivity(actor=owner_id, object=updated_case)
        event = _make_payload(activity)

        with caplog.at_level(logging.WARNING):
            UpdateCaseReceivedUseCase(dl, event).execute()

        assert not any("has not accepted" in r.message for r in caplog.records)

    def test_update_case_no_warning_when_no_active_embargo(
        self, monkeypatch, caplog
    ):
        """update_case does NOT warn when there is no active embargo (CM-10-004)."""
        import logging

        from vultron.adapters.driven.datalayer_tinydb import TinyDbDataLayer
        from vultron.wire.as2.vocab.activities.case import UpdateCaseActivity
        from vultron.wire.as2.vocab.objects.case_participant import (
            CaseParticipant,
        )

        dl = TinyDbDataLayer(db_path=None)
        monkeypatch.setattr(
            "vultron.wire.as2.rehydration.get_datalayer",
            lambda **_: dl,
        )

        owner_id = "https://example.org/users/owner"
        actor_id = "https://example.org/users/carol"

        participant = CaseParticipant(
            id="https://example.org/participants/p3",
            attributed_to=actor_id,
            context="https://example.org/cases/uc6",
            accepted_embargo_ids=[],
        )
        dl.create(participant)

        case = VulnerabilityCase(
            id="https://example.org/cases/uc6",
            name="Original",
            attributed_to=owner_id,
            active_embargo=None,
        )
        case.actor_participant_index[actor_id] = participant.as_id
        dl.create(case)

        updated_case = VulnerabilityCase(
            id=case.as_id,
            name="Updated",
            attributed_to=owner_id,
        )
        activity = UpdateCaseActivity(actor=owner_id, object=updated_case)
        event = _make_payload(activity)

        with caplog.at_level(logging.WARNING):
            UpdateCaseReceivedUseCase(dl, event).execute()

        assert not any("has not accepted" in r.message for r in caplog.records)
