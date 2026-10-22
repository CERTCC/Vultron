#!/usr/bin/env python

#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
#  - see Contributors.md for a full list of Contributors
#  - see ContributionInstructions.md for information on how you can Contribute to this project
#  Vultron Multiparty Coordinated Vulnerability Disclosure Protocol Prototype is
#  licensed under a MIT (SEI)-style license, please see LICENSE.md distributed
#  with this Software or contact permission@sei.cmu.edu for full terms.
#  Created, in part, with funding and support from the United States Government
#  (see Acknowledgments file). This program may include and/or can use of
#  certain third party source code, object code, documentation and other files
#  ("Third Party Software"). See LICENSE.md for more details.
#  Carnegie Mellon®, CERT® and CERT Coordination Center® are registered in the
#  U.S. Patent and Trademark Office by Carnegie Mellon University

"""
Unit tests for SvcCreateCaseUseCase trigger use case.

Tests exercise the use case's execute() path against an in-memory DataLayer,
verifying state mutation, outbox effect, and error handling.
Spec: specs/triggerable-behaviors.yaml TRIG-09.
"""

import re

import pytest

from test.support.case_owner import CASE_OWNER_ID
from test.support.ledger import (
    assert_case_at_chain_tail,
    case_snapshot_position_violations,
    creation_entry_sequence,
    fail_commits,
    ledger_entries,
)
from test.support.ledger_rebuild import case_naming_its_records
from test.support.received import received_event
from test.support.trigger_results import activity_of
from vultron.adapters.driven.datalayer_sqlite import (
    SqliteDataLayer,
    reset_datalayer,
)
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.trigger_activity_adapter import (
    TriggerActivityAdapter,
)
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.models._helpers import _as_id
from vultron.core.models.base import CoreObject
from vultron.core.models.case import VulnerabilityCase
from vultron.core.models.case_ledger import ledger_entry_hash_intact
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.case_participant import CaseParticipant
from vultron.core.models.case_status import CaseStatus
from vultron.core.models.events.status import (
    AddParticipantStatusToParticipantReceivedEvent,
)
from vultron.core.models.ledger_position import LedgerPosition
from vultron.core.models.report import VulnerabilityReport
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.states.rm import RM
from vultron.core.use_cases.received.status import (
    AddParticipantStatusToParticipantReceivedUseCase,
)
from vultron.core.use_cases.triggers.case import SvcCreateCaseUseCase
from vultron.core.use_cases.triggers.case.add_participant_status import (
    SvcAddParticipantStatusUseCase,
)
from vultron.core.use_cases.triggers.requests import (
    AddParticipantStatusTriggerRequest,
    CreateCaseTriggerRequest,
)
from vultron.errors import (
    VultronBTInternalError,
    VultronNotFoundError,
    VultronValidationError,
)
from vultron.wire.as2.vocab.base.objects.activities.base import as_Activity
from vultron.wire.as2.vocab.base.objects.actors import as_Service
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)
from vultron.wire.as2.vocab.objects.vulnerability_report import (
    as_VulnerabilityReport,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_actor_dl(actor_name: str):
    """Create an as_Service actor and a matching per-actor SqliteDataLayer."""
    actor = as_Service(name=actor_name)
    actor_id = actor.id_
    reset_datalayer(actor_id)
    dl = SqliteDataLayer("sqlite:///:memory:", actor_id=actor_id)
    dl.clear_all()
    dl.create(actor)
    return actor, dl


def _activity_in_outbox(actor, dl: SqliteDataLayer) -> bool:
    """Check if actor's outbox has any items queued."""
    return len(dl.outbox_list()) > 0


#: A recipient for the ``Create``; without one nothing is queued (OX-08-001).
_RECIPIENT = "https://example.org/actors/finder"


def _use_case(
    dl: SqliteDataLayer, request: CreateCaseTriggerRequest
) -> SvcCreateCaseUseCase:
    """The use case with the ports the trigger dispatcher composes it with.

    Its tree commits the case's creation entries, which render through
    ``wire_render_port`` and fan out through ``sync_port`` (CLP-07-013).
    """
    return SvcCreateCaseUseCase(
        dl,
        request,
        trigger_activity=TriggerActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
        sync_port=SyncActivityAdapter(dl),
    )


def _get_outbox_activity_id(actor, dl: SqliteDataLayer) -> str | None:
    """Return the first activity ID in actor's outbox."""
    items = dl.outbox_list()
    return items[0] if items else None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSvcCreateCaseUseCase:
    """SvcCreateCaseUseCase creates a as_VulnerabilityCase and queues activity."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up actor and in-memory DataLayer."""
        self.actor, self.dl = _make_actor_dl("Vendor Co")
        yield
        self.dl.clear_all()
        reset_datalayer(self.actor.id_)

    @pytest.mark.spec("CLP-08-002")
    def test_create_case_trigger_anchors_the_genesis_hash_to_the_owner(self):
        """The owner's own creation path hashes on the owner (ADR-0117).

        The proposal path is pinned to the same formula in
        ``TestCLP08002GenesisHashAnchoredToTheOwner``; this is the other half,
        run through the real trigger rather than a hand-built case.
        """
        from vultron.core.models.case import VulnerabilityCase
        from vultron.core.models.case_ledger import compute_genesis_hash

        request = CreateCaseTriggerRequest(
            actor_id=self.actor.id_, name="Genesis Case", content="c"
        )
        _use_case(self.dl, request).execute()

        (case,) = [
            obj
            for obj in self.dl.list_objects("VulnerabilityCase")
            if getattr(obj, "name", "") == "Genesis Case"
        ]
        assert isinstance(case, VulnerabilityCase)
        assert case.published is not None
        assert case.genesis_hash == compute_genesis_hash(
            case_id=case.id_,
            created_at=case.published,
            owner_actor_id=self.actor.id_,
        )

    def test_create_case_happy_path_without_report(self):
        """SvcCreateCaseUseCase creates a case and queues CreateCaseActivity."""
        request = CreateCaseTriggerRequest(
            actor_id=self.actor.id_,
            name="Test Vulnerability Case",
            content="A test case for a vulnerability",
            to=[_RECIPIENT],
        )
        result = _use_case(self.dl, request).execute()

        # Verify case was persisted
        case_id = None
        for obj in self.dl.list_objects("VulnerabilityCase"):
            if getattr(obj, "name", "") == "Test Vulnerability Case":
                case_id = obj.id_
                break

        assert case_id is not None, "Case should have been created"

        # Verify case attributes
        case = self.dl.read(case_id)
        assert case is not None
        assert getattr(case, "name", "") == "Test Vulnerability Case"
        assert (
            getattr(case, "content", "") == "A test case for a vulnerability"
        )
        assert getattr(case, "attributed_to", "") == self.actor.id_

        # Verify activity was queued in outbox
        assert _activity_in_outbox(self.actor, self.dl), (
            "Activity should be queued in actor's outbox"
        )

        # Verify result contains activity
        activity_dict = activity_of(result)
        assert activity_dict.get("type") == "Create"

    def test_create_case_with_linked_report(self):
        """SvcCreateCaseUseCase links a report to the new case."""
        # Create a report first
        report = as_VulnerabilityReport(
            name="Test Vulnerability Report",
            content="A test report",
        )
        self.dl.create(report)

        request = CreateCaseTriggerRequest(
            actor_id=self.actor.id_,
            name="Test Case With Report",
            content="Case linked to report",
            report_id=report.id_,
            to=[_RECIPIENT],
        )
        result = _use_case(self.dl, request).execute()

        # Verify case was created
        case_id = None
        for obj in self.dl.list_objects("VulnerabilityCase"):
            if getattr(obj, "name", "") == "Test Case With Report":
                case_id = obj.id_
                break

        assert case_id is not None, "Case should have been created"

        # Verify report is linked
        case = self.dl.read(case_id)
        vul_reports = getattr(case, "vulnerability_reports", [])
        assert report.id_ in vul_reports, (
            f"Report {report.id_} should be linked to case"
        )

        # Verify activity queued
        assert _activity_in_outbox(self.actor, self.dl)
        assert result.activity is not None

    def test_create_case_raises_when_actor_not_found(self):
        """SvcCreateCaseUseCase raises VultronNotFoundError when actor not found."""
        request = CreateCaseTriggerRequest(
            actor_id="https://example.org/nonexistent",
            name="Test Case",
            content="Test content",
        )
        with pytest.raises(VultronNotFoundError, match="Actor"):
            _use_case(self.dl, request).execute()

    def test_create_case_raises_when_report_not_found(self):
        """SvcCreateCaseUseCase raises VultronNotFoundError when report_id not found."""
        request = CreateCaseTriggerRequest(
            actor_id=self.actor.id_,
            name="Test Case",
            content="Test content",
            report_id="https://example.org/nonexistent",
        )
        with pytest.raises(VultronNotFoundError, match="VulnerabilityReport"):
            _use_case(self.dl, request).execute()

    def test_create_case_raises_when_report_wrong_type(self):
        """SvcCreateCaseUseCase raises VultronValidationError when report_id is
        not a VulnerabilityReport."""
        # Create a wrong type object (as_VulnerabilityCase instead)
        case = as_VulnerabilityCase(
            attributed_to=CASE_OWNER_ID, name="Not a Report"
        )
        self.dl.create(case)

        request = CreateCaseTriggerRequest(
            actor_id=self.actor.id_,
            name="Test Case",
            content="Test content",
            report_id=case.id_,
        )
        with pytest.raises(
            VultronValidationError, match="not a VulnerabilityReport"
        ):
            _use_case(self.dl, request).execute()

    def test_create_case_outbox_activity_addressed_to_case_actor(self):
        """Activity is addressed to the Case Actor only when ``to`` is set (PCR-08-001)."""
        case_actor = as_Service(name="Case Actor")
        self.dl.create(case_actor)
        request = CreateCaseTriggerRequest(
            actor_id=self.actor.id_,
            name="Test Case PCR",
            content="Test content",
            to=[case_actor.id_],
        )
        before = set(self.dl.outbox_list())
        _use_case(self.dl, request).execute()
        after = set(self.dl.outbox_list())
        new_ids = after - before
        assert new_ids, "CreateCase must queue at least one outbox activity"
        activity_id = next(iter(new_ids))
        activity = self.dl.read(activity_id)
        assert activity is not None
        to = getattr(activity, "to", None)
        to_ids = (
            [
                (
                    item
                    if isinstance(item, str)
                    else getattr(item, "id_", str(item))
                )
                for item in to
            ]
            if isinstance(to, list)
            else ([to] if isinstance(to, str) else [])
        )
        assert case_actor.id_ in to_ids, (
            f"PCR-08-001: activity must be addressed to CaseActor; to={to_ids!r}"
        )
        assert len(to_ids) == 1, (
            f"PCR-08-001: exactly one recipient expected, got {to_ids!r}"
        )

    @pytest.mark.spec("CM-02-014")
    @pytest.mark.spec("CM-02-015")
    @pytest.mark.spec("CM-24-006")
    def test_create_case_trigger_registers_owner_and_manager(self):
        """SvcCreateCaseUseCase registers CASE_OWNER+CASE_MANAGER participant (CM-02-014, CM-02-015)."""
        from vultron.core.participants.authority import resolve_case_manager_id
        from vultron.enums.roles import CVDRole

        request = CreateCaseTriggerRequest(
            actor_id=self.actor.id_,
            name="Test Case Participant Roles",
            content="A test case for participant role registration",
        )
        _use_case(self.dl, request).execute()

        raw_case_id = None
        for obj in self.dl.list_objects("VulnerabilityCase"):
            if getattr(obj, "name", "") == "Test Case Participant Roles":
                raw_case_id = getattr(obj, "id_", None)
                break
        assert raw_case_id is not None, "Case should have been created"

        case_obj = self.dl.read_case(raw_case_id)
        assert case_obj is not None, (
            "Case must be readable as VulnerabilityCase"
        )

        manager_id = resolve_case_manager_id(case_obj, self.dl)
        assert manager_id is not None, (
            "CASE_MANAGER must be registered at case creation (CM-02-014, CM-02-015)"
        )
        assert manager_id == self.actor.id_, (
            "CASE_MANAGER must be the creating actor"
        )

        all_roles: set[CVDRole] = set()
        for pid in case_obj.actor_participant_index.values():
            p = self.dl.read(pid)
            if p is not None:
                all_roles.update(getattr(p, "case_roles", []))
        assert CVDRole.CASE_OWNER in all_roles, (
            "CASE_OWNER must be registered (CM-02-014)"
        )
        assert CVDRole.CASE_MANAGER in all_roles, (
            "CASE_MANAGER must be registered (CM-02-014)"
        )

    @pytest.mark.spec("HP-08-008")
    def test_create_case_owner_status_add_is_applied(self):
        """The creator's CASE_OWNER+CASE_MANAGER record names its case, so
        its own Add(ParticipantStatus), received on its own store, acts on
        that case and the status is appended (HP-08-008, #4961)."""
        created = _use_case(
            self.dl,
            CreateCaseTriggerRequest(
                actor_id=self.actor.id_,
                name="Test Case Owner Status",
                content="A test case for the owner's own status update",
            ),
        ).execute()
        assert created.case_id is not None
        case_obj = self.dl.read_case(created.case_id)
        assert case_obj is not None
        record = self.dl.read(case_obj.actor_participant_index[self.actor.id_])
        assert isinstance(record, CaseParticipant)
        assert _as_id(record.context) == case_obj.id_

        sent = SvcAddParticipantStatusUseCase(
            self.dl,
            AddParticipantStatusTriggerRequest(
                actor_id=self.actor.id_,
                case_id=case_obj.id_,
                rm_state=RM.RECEIVED,
            ),
            trigger_activity=TriggerActivityAdapter(self.dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(self.dl),
        ).execute()
        assert sent.activity_id is not None
        sent_activity = self.dl.read(sent.activity_id)
        assert isinstance(sent_activity, as_Activity)
        event = received_event(sent_activity).model_copy(
            update={"receiving_actor_id": self.actor.id_}
        )
        assert isinstance(
            event, AddParticipantStatusToParticipantReceivedEvent
        )

        result = AddParticipantStatusToParticipantReceivedUseCase(
            self.dl,
            event,
            trigger_activity=TriggerActivityAdapter(self.dl),
            wire_render_port=As2WireRenderAdapter(),
            sync_port=SyncActivityAdapter(self.dl),
        ).execute()

        assert result.disposition != HandlerDisposition.REFUSED, result.reason
        stored = self.dl.read(record.id_)
        assert isinstance(stored, CaseParticipant)
        assert [s.rm.state for s in stored.participant_statuses if s.rm] == [
            RM.START,
            RM.RECEIVED,
        ]

    def test_create_case_activity_queued_in_delivery_queue(self):
        """SvcCreateCaseUseCase queues activity in delivery queue for outbox_handler."""
        request = CreateCaseTriggerRequest(
            actor_id=self.actor.id_,
            name="Test Case",
            content="Test content",
            to=[_RECIPIENT],
        )
        result = _use_case(self.dl, request).execute()

        # Verify activity ID is in result
        activity_dict = activity_of(result)
        activity_id = activity_dict.get("id")
        assert activity_id is not None

        # Verify activity was queued in outbox
        outbox_activity_id = _get_outbox_activity_id(self.actor, self.dl)
        assert outbox_activity_id == activity_id, (
            "Activity ID in outbox should match returned activity ID"
        )

    @pytest.mark.spec("OX-08-001")
    @pytest.mark.parametrize("to", [None, []], ids=["absent", "empty"])
    def test_create_case_with_no_recipient_queues_nothing(self, to):
        """With no ``to`` the case is created but no ``Create`` is queued.

        The outbox refuses an activity addressed to no one (OX-08-001), so a
        queued row could only ever be dead-lettered (OX-13-013).
        """
        request = CreateCaseTriggerRequest(
            actor_id=self.actor.id_,
            name="Local Case",
            content="Test content",
            to=to,
        )
        result = _use_case(self.dl, request).execute()

        assert result.case_id is not None
        assert self.dl.read(result.case_id) is not None
        assert activity_of(result).get("type") == "Create"
        assert self.dl.outbox_list() == []


# ---------------------------------------------------------------------------
# Creation ledger entries (CLP-07-013, #4440)
# ---------------------------------------------------------------------------

#: The record class each creation entry carries, and where in the snapshot.
#: A participant record is created whole; a later status entry's ``target``
#: carries the record with that status added (CLP-07-013).
_CARRIED: dict[str, tuple[str, type[CoreObject]]] = {
    "create_case": ("object", VulnerabilityCase),
    "add_report_to_case": ("object", VulnerabilityReport),
    "create_case_participant": ("object", CaseParticipant),
    "add_participant_status_to_participant": ("target", CaseParticipant),
    "add_case_status_to_case": ("object", CaseStatus),
}


def _rebuild_case_file(
    entries: list[CaseLedgerEntry],
) -> dict[str, CoreObject]:
    """Each record the ledger carries, by id, read from the entries alone.

    A copy, as a replica's apply is (ADR-0124): every record comes from an
    entry's snapshot and nothing is read from the store that wrote it.  A
    later entry carrying the same record replaces the earlier copy.  Applying
    an entry moves the case's position to it, as a replica's store does
    (SYNC-16-005).
    """
    records: dict[str, CoreObject] = {}
    for entry in entries:
        key, cls = _CARRIED[entry.semantic_type]
        record = cls.model_validate(entry.payload_snapshot[key])
        if isinstance(record, VulnerabilityCase):
            # The genesis Create carries its records inline; each is copied
            # from its own entry (ADR-0157).
            record = case_naming_its_records(record)
        records[record.id_] = record
        case = records.get(entry.case_id)
        if isinstance(case, VulnerabilityCase):
            case.ledger_position = LedgerPosition(
                log_index=entry.log_index, entry_hash=entry.entry_hash
            )
    return records


class TestCreateCaseTriggerLedger:
    """The trigger commits the case's creation entries (CLP-07-013, #4440)."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.actor, self.dl = _make_actor_dl("Vendor Co")
        self.report = as_VulnerabilityReport(name="Report", content="r")
        self.dl.create(self.report)
        yield
        self.dl.clear_all()
        reset_datalayer(self.actor.id_)

    def _create(
        self, *, report: bool = True, to: list[str] | None = None
    ) -> VulnerabilityCase:
        request = CreateCaseTriggerRequest(
            actor_id=self.actor.id_,
            name="Ledgered Case",
            content="c",
            report_id=self.report.id_ if report else None,
            to=to,
        )
        result = _use_case(self.dl, request).execute()
        assert result.case_id is not None
        case = self.dl.read_case(result.case_id)
        assert isinstance(case, VulnerabilityCase)
        return case

    @pytest.mark.spec("CLP-07-013")
    @pytest.mark.spec("CM-22-003")
    @pytest.mark.parametrize("to", [None, [_RECIPIENT]], ids=["local", "sent"])
    def test_commits_genesis_then_an_entry_per_record(self, to):
        """The creator's record is created whole, with its one status.

        The owner holds one status, so its record is one
        ``create_case_participant`` entry and no status entry follows it
        (CLP-07-013).
        """
        case = self._create(to=to)

        entries = ledger_entries(self.dl, case.id_)

        assert [e.semantic_type for e in entries] == [
            "create_case",
            "add_report_to_case",
            "create_case_participant",
            "add_case_status_to_case",
        ]
        assert [
            (e.semantic_type, e.log_object_id) for e in entries
        ] == creation_entry_sequence(self.dl, case)

    @pytest.mark.spec("CLP-07-013")
    def test_a_case_with_no_report_commits_no_report_entry(self):
        case = self._create(report=False)

        assert [
            e.semantic_type for e in ledger_entries(self.dl, case.id_)
        ] == [
            "create_case",
            "create_case_participant",
            "add_case_status_to_case",
        ]

    @pytest.mark.spec("CLP-07-013")
    def test_every_entry_is_authored_by_the_case_manager(self):
        from vultron.core.participants.authority import (
            resolve_case_manager_id,
        )

        case = self._create()
        manager_id = resolve_case_manager_id(case, self.dl)

        assert manager_id == self.actor.id_
        assert {
            e.payload_snapshot["actor"]
            for e in ledger_entries(self.dl, case.id_)
        } == {manager_id}

    @pytest.mark.spec("CLP-07-013")
    def test_the_case_rebuilt_from_its_ledger_is_the_managers_case_file(
        self,
    ):
        case = self._create(to=[_RECIPIENT])

        rebuilt = _rebuild_case_file(ledger_entries(self.dl, case.id_))

        assert rebuilt[case.id_] == case
        file_ids = [
            *(str(_as_id(p)) for p in case.case_participants),
            *(str(_as_id(r)) for r in case.vulnerability_reports),
        ]
        for record_id in file_ids:
            assert rebuilt[record_id] == self.dl.read(record_id), record_id
        for status in case.case_statuses:
            assert isinstance(status, CaseStatus)
            assert rebuilt[status.id_] == status

    @pytest.mark.spec("CLP-07-011")
    @pytest.mark.spec("CLP-02-013")
    def test_the_sent_create_is_the_genesis_entry(self):
        """One activity, delivered and ledgered (ADR-0157): the ``Create`` the
        outbox delivers is the genesis entry's snapshot, byte for byte."""
        from vultron.adapters.outbox_sealed_body import read_sealed_body_dict

        case = self._create(to=[_RECIPIENT])

        genesis = ledger_entries(self.dl, case.id_)[0]
        (sent,) = [
            item
            for item in self.dl.outbox_list()
            if getattr(self.dl.read(item), "type_", None) == "Create"
        ]
        assert genesis.semantic_type == "create_case"
        assert read_sealed_body_dict(self.dl, sent) == genesis.payload_snapshot

    @pytest.mark.spec("SYNC-16-005")
    def test_the_case_names_the_tail_its_creation_entries_left(self):
        """After the creation commits, the stored case names its chain tail."""
        case = self._create(to=[_RECIPIENT])

        entries = ledger_entries(self.dl, case.id_)
        assert len(entries) > 1
        assert case.ledger_position == LedgerPosition(
            log_index=entries[-1].log_index, entry_hash=entries[-1].entry_hash
        )
        assert_case_at_chain_tail(self.dl, case.id_)

    @pytest.mark.spec("SYNC-16-005")
    def test_the_genesis_entry_carries_the_case_before_it(self):
        """No entry's hash depends on itself (AC-3 of #5091).

        The genesis ``Create`` carries the case at the empty ledger, though the
        case has since moved past it, and every entry still reproduces its
        hash.
        """
        case = self._create(to=[_RECIPIENT])

        entries = ledger_entries(self.dl, case.id_)
        genesis = entries[0]
        assert genesis.payload_snapshot["object"]["ledgerPosition"] == {
            "logIndex": -1,
            "entryHash": case.genesis_hash,
        }
        assert case.ledger_position == LedgerPosition(
            log_index=entries[-1].log_index,
            entry_hash=entries[-1].entry_hash,
        )
        assert all(ledger_entry_hash_intact(e) for e in entries)
        assert case_snapshot_position_violations(entries, self.actor.id_) == []

    @pytest.mark.spec("CLP-07-013")
    def test_the_create_is_the_only_outbox_item(self):
        """The creator is the case's only participant, so no entry is sent.

        The entries fan out to the case's other participants, of which a new
        case has none; the ``Create`` is the one item queued.
        """
        self._create(to=[_RECIPIENT])

        (activity_id,) = self.dl.outbox_list()
        activity = self.dl.read(activity_id)
        assert getattr(activity, "type_", None) == "Create"

    @pytest.mark.spec("CLP-07-013")
    @pytest.mark.parametrize(
        "missing", ["wire_render_port", "sync_port"], ids=lambda m: m
    )
    def test_a_missing_port_refuses_before_anything_is_written(self, missing):
        """A trigger that could not commit the entries writes no case.

        The ports are a composition fault, so the tree refuses before its
        first write rather than leaving a case its ledger never records.
        """
        ports: dict[str, object] = {
            "wire_render_port": As2WireRenderAdapter(),
            "sync_port": SyncActivityAdapter(self.dl),
        }
        del ports[missing]
        request = CreateCaseTriggerRequest(
            actor_id=self.actor.id_,
            name="Unwired Case",
            content="c",
            to=[_RECIPIENT],
        )

        # A composition fault is ours, not the client's: never a 422
        # validation error (ARCH-20-001).
        with pytest.raises(VultronBTInternalError, match=missing):
            SvcCreateCaseUseCase(
                self.dl,
                request,
                trigger_activity=TriggerActivityAdapter(self.dl),
                **ports,  # type: ignore[arg-type]
            ).execute()

        assert self.dl.list_objects("VulnerabilityCase") == []
        assert self.dl.list_objects("CaseLedgerEntry") == []
        assert self.dl.outbox_list() == []

    def _assert_nothing_of_the_case_is_kept(self) -> None:
        """The store holds nothing the failed creation wrote (CLP-07-013).

        The report the case was created from was not the creation's write,
        so it stays.
        """
        assert self.dl.list_objects("VulnerabilityCase") == []
        assert self.dl.list_objects("CaseParticipant") == []
        assert self.dl.list_objects("ParticipantStatus") == []
        assert self.dl.list_objects("CaseStatus") == []
        assert self.dl.list_objects("CaseLedgerEntry") == []
        assert self.dl.outbox_list() == []
        assert self.dl.list_objects("Create") == [], "the unsent Create too"
        assert self.dl.read(self.report.id_) is not None

    @pytest.mark.spec("CLP-07-013")
    @pytest.mark.parametrize(
        ("allowed", "failing"),
        [
            (0, "create_case"),
            (1, "add_report_to_case"),
            (2, "create_case_participant"),
            (3, "add_case_status_to_case"),
        ],
        ids=lambda v: v if isinstance(v, str) else None,
    )
    def test_a_creation_entry_that_fails_keeps_nothing_of_the_case(
        self, monkeypatch, allowed, failing
    ):
        """AC-1, AC-3: no record of the case outlives a failed entry (#4442).

        The creation is one act (ADR-0146): the case, the creator's record,
        the queued ``Create`` and every entry already committed, genesis
        included, are rolled back with the entry that failed, and the
        trigger raises with that entry's reason.
        """
        from vultron.core.behaviors.case.nodes import proposal_ledger

        fail_commits(monkeypatch, proposal_ledger, allowed=allowed)

        with pytest.raises(VultronValidationError, match=failing) as raised:
            self._create(to=[_RECIPIENT])

        assert re.search(r"on case '[^']+'", str(raised.value)), (
            "the error names the case"
        )
        self._assert_nothing_of_the_case_is_kept()

    @pytest.mark.spec("DL-02-004")
    @pytest.mark.spec("CLP-07-013")
    def test_delivery_is_never_told_of_a_rolled_back_create(self, monkeypatch):
        """A ``Create`` whose case is rolled back is never offered for delivery.

        The outbox monitor learns of a queued item only after the block
        commits (DL-02-004), so a failed genesis cannot race delivery into
        sending a case the CASE_MANAGER then does not hold (#4653).
        """
        from vultron.core.behaviors.case.nodes import proposal_ledger

        woken: list[str] = []
        self.dl.set_enqueue_callback(woken.append)
        fail_commits(monkeypatch, proposal_ledger)

        with pytest.raises(VultronValidationError):
            self._create(to=[_RECIPIENT])

        assert woken == []
        self._assert_nothing_of_the_case_is_kept()

        # Positive control: the same callback is woken once a creation
        # commits, so the empty list above is not a callback never wired.
        monkeypatch.undo()
        self._create(to=[_RECIPIENT])
        assert woken, "a committed creation wakes delivery"

    @pytest.mark.spec("SYNC-09-002")
    @pytest.mark.spec("CP-09-009")
    def test_the_create_is_queued_before_the_creation_entries(
        self, monkeypatch
    ):
        """The entries record a case whose creation was sent (ADR-0119)."""
        from test.support.ledger import record_sends_and_commits
        from vultron.core.models.activity_ids import derived_activity_id
        from vultron.core.use_cases.triggers.case.create import (
            CREATE_CASE_ID_KIND,
        )

        events = record_sends_and_commits(monkeypatch, self.actor.id_)

        case = self._create(to=[_RECIPIENT])

        create_id = derived_activity_id(
            CREATE_CASE_ID_KIND, self.actor.id_, case.id_
        )
        assert events[0] == ("queued", create_id)
        assert [kind for kind, _ in events[1:]] == [
            "create_case",
            "add_report_to_case",
            "create_case_participant",
            "add_case_status_to_case",
        ]

    @pytest.mark.spec("CLP-07-013")
    def test_a_create_the_outbox_cannot_take_keeps_nothing_of_the_case(
        self, monkeypatch
    ):
        """A failed outbox write rolls the creation back.

        The ``Create`` is queued before the creation entries (ADR-0119), so
        when the queue write fails no entry is committed, and the case
        written ahead of it is rolled back with it (ADR-0146).
        """
        from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer

        def _refuse(_self, _activity_id):
            raise RuntimeError("outbox unavailable")

        monkeypatch.setattr(SqliteDataLayer, "outbox_append", _refuse)
        with pytest.raises(VultronValidationError, match="UpdateActorOutbox"):
            self._create(to=[_RECIPIENT])

        self._assert_nothing_of_the_case_is_kept()


@pytest.mark.spec("CLP-07-013")
def test_the_trigger_and_proposal_trees_share_one_creation_commit():
    """Both creation paths compose the same commit node (#4440 AC-2).

    One node commits a new case's entries, so the two paths cannot drift
    into different sequences for the same resulting case.
    """
    from vultron.core.behaviors.case.case_proposal_received_tree import (
        create_case_proposal_received_tree,
    )
    from vultron.core.behaviors.case.create_case_trigger_tree import (
        create_case_trigger_bt,
    )
    from vultron.core.behaviors.case.nodes import (
        CommitNativeLedgerEntriesNode,
    )
    from vultron.core.use_cases.received.case_proposal import (
        CreateCaseProposalReceivedUseCase,
    )

    trigger = create_case_trigger_bt(
        actor_id="https://example.org/actors/vendor",
        case_name="n",
        case_content="c",
        report_id=None,
        result_out={},
        activity_builder=lambda case_id: (case_id, "{}"),
        queue_for_delivery=True,
    )
    proposal = create_case_proposal_received_tree(
        report_id=None,
        proposal_id="https://example.org/proposals/p",
        proposer_uri="https://example.org/actors/vendor",
        sender_rule=CreateCaseProposalReceivedUseCase.sender_entitlement,
    )

    for tree in (trigger, proposal):
        commits = [
            node
            for node in tree.iterate()
            if isinstance(node, CommitNativeLedgerEntriesNode)
        ]
        assert len(commits) == 1, tree.name
