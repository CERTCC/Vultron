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
from vultron.core.models.activity import VultronActivity
from vultron.core.models.base import CoreObject
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.dimensions import RmDimension
from vultron.core.models.events import MessageSemantics
from vultron.core.models.events.case import (
    DeferCaseReceivedEvent,
    EngageCaseReceivedEvent,
)
from vultron.core.models.participant import VultronParticipant
from vultron.core.models.participant_status import ParticipantStatus
from vultron.core.states.rm import RM
from vultron.core.use_cases.received.case.engage_defer import (
    DeferCaseReceivedUseCase,
    EngageCaseReceivedUseCase,
)
from vultron.enums.roles import CVDRole
from vultron.wire.as2.vocab.base.objects.activities.transitive import (
    as_Announce,
)


class TestEngageDeferCaseBTFailureReason:
    """Regression tests for BUG-471.6.

    When EngageCaseBT or DeferCaseBT fails (e.g., no participant record
    exists for the given actor), the WARNING log must include a non-empty
    failure reason — not a trailing colon with nothing after it.
    """

    # The received-side tree executes under the case manager
    # (BT-17-005), so this names the store it runs in.
    _CASE_MANAGER_ID = "https://example.org/actors/coordinator-failreason"

    @pytest.fixture
    def dl(self):
        return SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=self._CASE_MANAGER_ID,
        )

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
            object_=CoreObject(id_=case_id),
            semantic_type=MessageSemantics.ENGAGE_CASE,
        )

    def _defer_event(
        self, actor_id: str, case_id: str
    ) -> DeferCaseReceivedEvent:
        return DeferCaseReceivedEvent(
            activity_id="https://example.org/activities/defer-001",
            actor_id=actor_id,
            object_=CoreObject(id_=case_id),
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

    # The received-side tree executes under the case manager
    # (BT-17-005), so this names the store it runs in.
    _CASE_MANAGER_ID = "https://example.org/actors/coordinator-embedded"

    _ACTOR_ID = "https://vendor.example.org/actors/vendor"
    _CASE_ID = "https://example.org/cases/case-573-001"
    _PARTICIPANT_ID = f"{_CASE_ID}/participants/vendor"

    @pytest.fixture
    def dl(self):
        return SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=self._CASE_MANAGER_ID,
        )

    @pytest.fixture
    def case_with_inline_participant(self):
        """VulnerabilityCase carrying a fully inline VultronParticipant."""
        participant = VultronParticipant(
            id_=self._PARTICIPANT_ID,
            attributed_to=self._ACTOR_ID,
            context=self._CASE_ID,
        )
        case = VulnerabilityCase(id_=self._CASE_ID)
        object.__setattr__(case, "case_participants", [participant])
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
        case_str_participants = VulnerabilityCase(id_=self._CASE_ID)
        object.__setattr__(
            case_str_participants, "case_participants", [self._PARTICIPANT_ID]
        )  # bare string
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


class TestEngageCaseLedgerCommit:
    """EngageCaseReceivedUseCase must commit an engage_case ledger entry.

    Regression for #2300: the blackboard actor_id was set to the sender's ID
    (request.actor_id) instead of the receiving CaseActor's ID
    (request.receiving_actor_id).  CheckIsCaseManagerNode compared the sender
    against the case's CASE_MANAGER, found a mismatch, and skipped the commit
    via the "not a case manager" guard path.  No ledger entry was ever written.
    """

    _SENDER_ID = "https://example.org/actors/vendor-2300"
    _CASE_MANAGER_ID = "https://example.org/actors/coordinator-2300"
    _CASE_ID = "https://example.org/cases/case-2300"
    _VENDOR_PARTICIPANT_ID = f"{_CASE_ID}/participants/vendor"
    _CM_PARTICIPANT_ID = f"{_CASE_ID}/participants/coordinator"

    @pytest.fixture
    def dl(self):
        return SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=self._CASE_MANAGER_ID,
        )

    @pytest.fixture
    def seeded_dl(self, dl):
        return self._seed(dl)

    @classmethod
    def _seed(cls, dl: SqliteDataLayer) -> SqliteDataLayer:
        """*dl*'s replica of the case: vendor participant plus the CM."""
        from vultron.core.models.vultron_types import VultronCaseActor

        dl.create(VultronCaseActor(id_=cls._SENDER_ID, name="Vendor"))

        vendor_p = VultronParticipant(
            id_=cls._VENDOR_PARTICIPANT_ID,
            attributed_to=cls._SENDER_ID,
            context=cls._CASE_ID,
            participant_statuses=[
                ParticipantStatus(
                    attributed_to=cls._SENDER_ID,
                    context=cls._CASE_ID,
                    rm=RmDimension(state=RM.RECEIVED),
                ),
                ParticipantStatus(
                    attributed_to=cls._SENDER_ID,
                    context=cls._CASE_ID,
                    rm=RmDimension(state=RM.VALID),
                ),
            ],
        )
        dl.create(vendor_p)

        dl.create(
            VultronCaseActor(id_=cls._CASE_MANAGER_ID, name="Coordinator")
        )

        cm_p = VultronParticipant(
            id_=cls._CM_PARTICIPANT_ID,
            attributed_to=cls._CASE_MANAGER_ID,
            context=cls._CASE_ID,
            case_roles=[CVDRole.CASE_MANAGER, CVDRole.COORDINATOR],
        )
        dl.create(cm_p)

        # attributed_to triggers genesis_hash computation (CLP-08-001/002).
        case = VulnerabilityCase(
            id_=cls._CASE_ID,
            name="Ledger Commit Regression Case #2300",
            attributed_to=cls._CASE_MANAGER_ID,
            case_participants=[
                cls._VENDOR_PARTICIPANT_ID,
                cls._CM_PARTICIPANT_ID,
            ],
            actor_participant_index={
                cls._SENDER_ID: cls._VENDOR_PARTICIPANT_ID,
                cls._CASE_MANAGER_ID: cls._CM_PARTICIPANT_ID,
            },
        )
        dl.create(case)
        return dl

    def _engage_event(self) -> EngageCaseReceivedEvent:
        # object_ must be a VulnerabilityCase so the canonical-entry validator
        # sees type="VulnerabilityCase" and recognises the ("Join","VulnerabilityCase")
        # pair as canonical (CLP-canonical-pairs / _CANONICAL_PAIRS check).
        return EngageCaseReceivedEvent(
            activity_id=f"{self._CASE_ID}/activities/engage-2300",
            actor_id=self._SENDER_ID,
            receiving_actor_id=self._CASE_MANAGER_ID,
            object_=CoreObject(id_=self._CASE_ID),
            semantic_type=MessageSemantics.ENGAGE_CASE,
            activity=VultronActivity(
                type_="Join",
                actor=self._SENDER_ID,
                object_=VulnerabilityCase(id_=self._CASE_ID),
                context=self._CASE_ID,
            ),
        )

    def test_engage_case_commits_ledger_entry_when_receiving_actor_is_case_manager(
        self, seeded_dl
    ):
        """EngageCaseReceivedUseCase commits an engage_case ledger entry.

        The receiving actor (CaseManager) must be the executing actor so
        GuardedCommitCaseLedgerEntryBT commits the entry instead of skipping
        it via the "not a case manager" guard.  Regression for #2300.
        """
        from vultron.core.models.case_ledger_entry import (
            CaseLedgerEntry,
        )

        EngageCaseReceivedUseCase(seeded_dl, self._engage_event()).execute()

        entries = seeded_dl.list_objects("CaseLedgerEntry")
        engage_entries = [
            e
            for e in entries
            if isinstance(e, CaseLedgerEntry) and e.event_type == "engage_case"
        ]
        assert len(engage_entries) == 1, (
            "Expected exactly one 'engage_case' ledger entry when "
            "receiving_actor_id is the CaseManager — regression for #2300"
        )

    @staticmethod
    def _queued_announces(dl: SqliteDataLayer) -> list[as_Announce]:
        queued = [dl.read(activity_id) for activity_id in dl.outbox_list()]
        return [a for a in queued if isinstance(a, as_Announce)]

    def test_engage_received_by_case_manager_broadcasts(self, seeded_dl):
        """Control: the CASE_MANAGER announces the updated case (CM-06-001)."""
        EngageCaseReceivedUseCase(seeded_dl, self._engage_event()).execute()

        announces = self._queued_announces(seeded_dl)
        assert len(announces) == 1
        assert announces[0].actor == self._CASE_MANAGER_ID

    def test_engage_received_by_non_case_manager_does_not_broadcast(self):
        """A participant that is not the CASE_MANAGER announces nothing.

        ``BroadcastCaseUpdateNode`` authors the ``Announce`` as the executing
        actor, so without a role gate every replica that received the Join
        re-broadcast canonical case state under its own name.
        """
        finder_id = "https://example.org/actors/finder-2300"
        dl = self._seed(
            SqliteDataLayer("sqlite:///:memory:", actor_id=finder_id)
        )
        event = self._engage_event().model_copy(
            update={"receiving_actor_id": finder_id}
        )

        EngageCaseReceivedUseCase(dl, event).execute()

        assert self._queued_announces(dl) == []

    def test_engage_without_receiving_actor_executes_as_store_owner(
        self, seeded_dl
    ):
        """No ``receiving_actor_id`` → the store's owner, never the sender.

        The fallback used to be ``request.actor_id``, so the CASE_MANAGER's own
        replica ran the tree as the vendor and skipped its commit (BT-17-006).
        """
        event = self._engage_event().model_copy(
            update={"receiving_actor_id": None}
        )

        EngageCaseReceivedUseCase(seeded_dl, event).execute()

        assert [
            e.event_type for e in seeded_dl.list_objects("CaseLedgerEntry")
        ] == ["engage_case"]

    def test_engage_case_transitions_vendor_rm_to_accepted(self, seeded_dl):
        """EngageCaseReceivedUseCase still transitions the engaging actor's RM to ACCEPTED.

        Verifies that fixing the receiving_actor_id does not break the RM
        transition for the sending actor (the actor who engaged the case).
        """
        EngageCaseReceivedUseCase(seeded_dl, self._engage_event()).execute()

        updated = seeded_dl.read(self._VENDOR_PARTICIPANT_ID)
        assert isinstance(updated, VultronParticipant)
        latest_status = updated.participant_statuses[-1]
        assert latest_status.rm.state == RM.ACCEPTED


class TestDeferCaseLedgerCommit:
    """DeferCaseReceivedUseCase must commit a defer_case ledger entry.

    Symmetric regression for #2300 on the defer path.
    """

    _SENDER_ID = "https://example.org/actors/vendor-2300-defer"
    _CASE_MANAGER_ID = "https://example.org/actors/coordinator-2300-defer"
    _CASE_ID = "https://example.org/cases/case-2300-defer"
    _VENDOR_PARTICIPANT_ID = f"{_CASE_ID}/participants/vendor"
    _CM_PARTICIPANT_ID = f"{_CASE_ID}/participants/coordinator"

    @pytest.fixture
    def dl(self):
        return SqliteDataLayer(
            "sqlite:///:memory:",
            actor_id=self._CASE_MANAGER_ID,
        )

    @pytest.fixture
    def seeded_dl(self, dl):
        from vultron.core.models.vultron_types import VultronCaseActor

        dl.create(VultronCaseActor(id_=self._SENDER_ID, name="Vendor"))
        vendor_p = VultronParticipant(
            id_=self._VENDOR_PARTICIPANT_ID,
            attributed_to=self._SENDER_ID,
            context=self._CASE_ID,
            participant_statuses=[
                ParticipantStatus(
                    attributed_to=self._SENDER_ID,
                    context=self._CASE_ID,
                    rm=RmDimension(state=RM.RECEIVED),
                ),
                ParticipantStatus(
                    attributed_to=self._SENDER_ID,
                    context=self._CASE_ID,
                    rm=RmDimension(state=RM.VALID),
                ),
            ],
        )
        dl.create(vendor_p)
        dl.create(
            VultronCaseActor(id_=self._CASE_MANAGER_ID, name="Coordinator")
        )
        cm_p = VultronParticipant(
            id_=self._CM_PARTICIPANT_ID,
            attributed_to=self._CASE_MANAGER_ID,
            context=self._CASE_ID,
            case_roles=[CVDRole.CASE_MANAGER, CVDRole.COORDINATOR],
        )
        dl.create(cm_p)
        case = VulnerabilityCase(
            id_=self._CASE_ID,
            name="Defer Ledger Commit Regression #2300",
            attributed_to=self._CASE_MANAGER_ID,
            case_participants=[
                self._VENDOR_PARTICIPANT_ID,
                self._CM_PARTICIPANT_ID,
            ],
            actor_participant_index={
                self._SENDER_ID: self._VENDOR_PARTICIPANT_ID,
                self._CASE_MANAGER_ID: self._CM_PARTICIPANT_ID,
            },
        )
        dl.create(case)
        return dl

    def _defer_event(self) -> DeferCaseReceivedEvent:
        return DeferCaseReceivedEvent(
            activity_id=f"{self._CASE_ID}/activities/defer-2300",
            actor_id=self._SENDER_ID,
            receiving_actor_id=self._CASE_MANAGER_ID,
            object_=CoreObject(id_=self._CASE_ID),
            semantic_type=MessageSemantics.DEFER_CASE,
            activity=VultronActivity(
                type_="Ignore",
                actor=self._SENDER_ID,
                object_=VulnerabilityCase(id_=self._CASE_ID),
                context=self._CASE_ID,
            ),
        )

    def test_defer_without_receiving_actor_executes_as_store_owner(
        self, seeded_dl
    ):
        """No ``receiving_actor_id`` → the store's owner, never the sender."""
        event = self._defer_event().model_copy(
            update={"receiving_actor_id": None}
        )

        DeferCaseReceivedUseCase(seeded_dl, event).execute()

        assert [
            e.event_type for e in seeded_dl.list_objects("CaseLedgerEntry")
        ] == ["defer_case"]

    def test_defer_case_commits_ledger_entry_when_receiving_actor_is_case_manager(
        self, seeded_dl
    ):
        """DeferCaseReceivedUseCase commits a defer_case ledger entry.

        Symmetric regression test to TestEngageCaseLedgerCommit for the
        defer path. Regression for #2300.
        """
        from vultron.core.models.case_ledger_entry import (
            CaseLedgerEntry,
        )

        DeferCaseReceivedUseCase(seeded_dl, self._defer_event()).execute()

        entries = seeded_dl.list_objects("CaseLedgerEntry")
        defer_entries = [
            e
            for e in entries
            if isinstance(e, CaseLedgerEntry) and e.event_type == "defer_case"
        ]
        assert len(defer_entries) == 1, (
            "Expected exactly one 'defer_case' ledger entry when "
            "receiving_actor_id is the CaseManager — regression for #2300"
        )

    def test_defer_case_transitions_vendor_rm_to_deferred(self, seeded_dl):
        """DeferCaseReceivedUseCase still transitions the deferring actor's RM to DEFERRED."""
        DeferCaseReceivedUseCase(seeded_dl, self._defer_event()).execute()

        updated = seeded_dl.read(self._VENDOR_PARTICIPANT_ID)
        assert isinstance(updated, VultronParticipant)
        latest_status = updated.participant_statuses[-1]
        assert latest_status.rm.state == RM.DEFERRED


class TestRegistrySuppliesTheTriggeringActivity:
    """The registry must populate ``event.activity`` for engage *and* defer.

    ``DEFER_CASE`` lacked ``include_activity=True`` while its ``ENGAGE_CASE``
    sibling had it, so a received ``Ignore(VulnerabilityCase)`` produced an event
    with no activity. The ledger snapshot was then dumped from the
    ``VultronEvent`` itself — which has neither ``type`` nor ``published`` — and
    the commit aborted at the canonical-signature check, taking the RM→DEFERRED
    transition with it when the receiving actor held CASE_MANAGER.

    The other tests in this file construct ``activity=VultronActivity(...)`` by
    hand, so they passed either way: they supplied exactly the thing the registry
    was failing to supply. These go through ``extract_event`` instead, which is
    the path production uses.
    """

    _CASE_ID = "https://example.org/cases/registry-activity-1"
    _SENDER_ID = "https://example.org/actors/vendor"

    def _wire_case(self):
        from vultron.wire.as2.vocab.objects.vulnerability_case import (
            as_VulnerabilityCase,
        )

        return as_VulnerabilityCase(id_=self._CASE_ID)

    @pytest.mark.parametrize(
        ("factory_name", "expected_semantics"),
        [
            ("rm_defer_case_activity", MessageSemantics.DEFER_CASE),
            ("rm_engage_case_activity", MessageSemantics.ENGAGE_CASE),
        ],
    )
    def test_extract_event_populates_activity(
        self, factory_name, expected_semantics
    ):
        from vultron.semantic_registry import extract_event
        from vultron.wire.as2 import factories

        activity = getattr(factories, factory_name)(
            self._wire_case(), actor=self._SENDER_ID
        )
        event = extract_event(activity)

        assert event.semantic_type == expected_semantics
        assert (
            event.activity is not None
        ), f"{factory_name}: registry did not carry the triggering activity"
        # The snapshot built from it needs both of these; the event itself has
        # neither, which is why the missing activity aborted the commit.
        assert event.activity.type_
        assert event.activity.published is not None
