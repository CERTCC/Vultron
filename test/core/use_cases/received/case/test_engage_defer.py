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
"""Tests for case-related use-case engage/defer handlers."""

import logging

import pytest

from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.core.models.base import VultronObject
from vultron.core.models.case import VultronCase
from vultron.core.models.events import MessageSemantics
from vultron.core.models.events.case import (
    DeferCaseReceivedEvent,
    EngageCaseReceivedEvent,
)
from vultron.core.models.participant import VultronParticipant
from vultron.core.use_cases.received.case.engage_defer import (
    DeferCaseReceivedUseCase,
    EngageCaseReceivedUseCase,
)


class TestEngageDeferCaseBTFailureReason:
    """Regression tests for BUG-471.6.

    When EngageCaseBT or DeferCaseBT fails (e.g., no participant record
    exists for the given actor), the WARNING log must include a non-empty
    failure reason — not a trailing colon with nothing after it.
    """

    @pytest.fixture
    def dl(self):
        return SqliteDataLayer("sqlite:///:memory:")

    @pytest.fixture
    def actor_id(self):
        return "https://example.org/actors/vendor"

    @pytest.fixture
    def case_id(self):
        return "urn:uuid:338a1bc3-0000-0000-0000-000000000001"

    def _engage_event(
        self, actor_id: str, case_id: str
    ) -> EngageCaseReceivedEvent:
        return EngageCaseReceivedEvent(
            activity_id="https://example.org/activities/engage-001",
            actor_id=actor_id,
            object_=VultronObject(id_=case_id),
            semantic_type=MessageSemantics.ENGAGE_CASE,
        )

    def _defer_event(
        self, actor_id: str, case_id: str
    ) -> DeferCaseReceivedEvent:
        return DeferCaseReceivedEvent(
            activity_id="https://example.org/activities/defer-001",
            actor_id=actor_id,
            object_=VultronObject(id_=case_id),
            semantic_type=MessageSemantics.DEFER_CASE,
        )

    def test_engage_case_failure_reason_is_nonempty(
        self, dl, actor_id, case_id, caplog
    ):
        """EngageCaseBT WARNING includes a non-empty failure reason.

        When CheckParticipantExists fails (no participant record),
        the warning must name the failing node, not end with a bare colon.
        """
        event = self._engage_event(actor_id, case_id)

        with caplog.at_level(logging.WARNING):
            EngageCaseReceivedUseCase(dl, event).execute()

        records = [
            r
            for r in caplog.records
            if "EngageCaseBT did not succeed" in r.message
        ]
        assert records, "Expected EngageCaseBT warning to be emitted"
        reason = records[0].message.rsplit(":", 1)[-1].strip()
        assert reason, (
            "EngageCaseBT warning must include a non-empty failure reason; "
            f"got: {records[0].message!r}"
        )

    def test_defer_case_failure_reason_is_nonempty(
        self, dl, actor_id, case_id, caplog
    ):
        """DeferCaseBT WARNING includes a non-empty failure reason.

        When CheckParticipantExists fails (no participant record),
        the warning must name the failing node, not end with a bare colon.
        """
        event = self._defer_event(actor_id, case_id)

        with caplog.at_level(logging.WARNING):
            DeferCaseReceivedUseCase(dl, event).execute()

        records = [
            r
            for r in caplog.records
            if "DeferCaseBT did not succeed" in r.message
        ]
        assert records, "Expected DeferCaseBT warning to be emitted"
        reason = records[0].message.rsplit(":", 1)[-1].strip()
        assert reason, (
            "DeferCaseBT warning must include a non-empty failure reason; "
            f"got: {records[0].message!r}"
        )


class TestEngageCaseStoresEmbeddedParticipants:
    """EngageCaseReceivedUseCase must call _store_embedded_participants (#573).

    Regression tests: when Join(VulnerabilityCase) arrives with inline
    participant objects, those objects must be persisted as independent
    DataLayer records before the BT runs — matching the pattern already
    established for Create (#564) and Announce (#566) paths.
    """

    _ACTOR_ID = "https://vendor.example.org/actors/vendor"
    _CASE_ID = "https://example.org/cases/case-573-001"
    _PARTICIPANT_ID = f"{_CASE_ID}/participants/vendor"

    @pytest.fixture
    def dl(self):
        return SqliteDataLayer("sqlite:///:memory:")

    @pytest.fixture
    def case_with_inline_participant(self):
        """VultronCase carrying a fully inline VultronParticipant."""
        participant = VultronParticipant(
            id_=self._PARTICIPANT_ID,
            attributed_to=self._ACTOR_ID,
            context=self._CASE_ID,
        )
        case = VultronCase(id_=self._CASE_ID)
        case.case_participants = [participant]
        return case

    @pytest.fixture
    def engage_event_with_inline_case(self, case_with_inline_participant):
        return EngageCaseReceivedEvent(
            activity_id="https://example.org/activities/engage-573",
            actor_id=self._ACTOR_ID,
            object_=case_with_inline_participant,
            semantic_type=MessageSemantics.ENGAGE_CASE,
        )

    def test_inline_participant_stored_even_when_bt_fails(
        self, dl, engage_event_with_inline_case
    ):
        """Embedded CaseParticipant is persisted before EngageCaseBT runs.

        Even when the BT fails (no pre-registered participant in the DataLayer),
        _store_embedded_participants must run first and persist the inline
        participant object (#573 regression).
        """
        EngageCaseReceivedUseCase(dl, engage_event_with_inline_case).execute()

        stored = dl.read(self._PARTICIPANT_ID)
        assert stored is not None, (
            "CaseParticipant embedded in Join(VulnerabilityCase) must be "
            "stored as an independent DataLayer record before the BT runs "
            "(EngageCaseReceivedUseCase regression #573)"
        )

    def test_bare_string_participant_is_not_stored(self, dl):
        """When case_participants contains bare strings, nothing is stored.

        _store_embedded_participants is idempotent on strings; no error and
        no false record is created (#573 does not regress bare-string path).
        """
        case_str_participants = VultronCase(id_=self._CASE_ID)
        case_str_participants.case_participants = [
            self._PARTICIPANT_ID
        ]  # bare string
        event = EngageCaseReceivedEvent(
            activity_id="https://example.org/activities/engage-573-str",
            actor_id=self._ACTOR_ID,
            object_=case_str_participants,
            semantic_type=MessageSemantics.ENGAGE_CASE,
        )
        EngageCaseReceivedUseCase(dl, event).execute()

        stored = dl.read(self._PARTICIPANT_ID)
        assert stored is None, (
            "_store_embedded_participants must skip bare string participant "
            "refs — no VultronParticipant record should be created for a bare "
            "string"
        )
