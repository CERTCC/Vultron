#  Copyright (c) 2026 Carnegie Mellon University and Contributors.
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
"""Dispositions of AddReportToCaseReceivedUseCase (HP-01-003, #2255)."""

from types import SimpleNamespace
from typing import cast
from unittest.mock import MagicMock

import pytest
from py_trees.common import Status

from test.core.use_cases.received.conftest import (
    seed_case_manager_participant,
    seed_case_owner_participant,
)
from vultron.adapters.driven.datalayer_sqlite import SqliteDataLayer
from vultron.adapters.driven.sync_activity_adapter import SyncActivityAdapter
from vultron.adapters.driven.wire_render.as2 import As2WireRenderAdapter
from vultron.core.behaviors.bridge import BTBridge
from vultron.core.behaviors.case.nodes.invite_ledger_backfill import (
    BackfillCanonicalLedgerToInviteeNode,
)
from vultron.core.behaviors.sync.nodes.offer_report_effect import (
    ApplyOfferReportFromLedgerNode,
)
from vultron.core.models._helpers import _as_id
from vultron.core.models.case_ledger_entry import CaseLedgerEntry
from vultron.core.models.events.case import AddReportToCaseReceivedEvent
from vultron.core.models.use_case_result import HandlerDisposition
from vultron.core.ports.sync_activity import SyncActivityPort
from vultron.core.use_cases.received.case.lifecycle import (
    AddReportToCaseReceivedUseCase,
)
from vultron.semantic_registry import extract_event
from vultron.wire.as2.factories import add_report_to_case_activity
from vultron.wire.as2.vocab.examples._base import gen_report
from vultron.wire.as2.vocab.objects.vulnerability_case import (
    as_VulnerabilityCase,
)

_CASE_ID = "https://example.org/cases/lifecycle-001"
_MANAGER_ID = "https://example.org/actors/cm"
_OWNER_ID = "https://example.org/actors/owner"
_OTHER_ID = "https://example.org/actors/other"


@pytest.fixture()
def dl():
    return SqliteDataLayer("sqlite:///:memory:", actor_id=_MANAGER_ID)


def _managed_case(dl) -> as_VulnerabilityCase:
    """A case the store's actor manages, owned by ``_OWNER_ID``."""
    case = as_VulnerabilityCase(
        id_=_CASE_ID, name="Lifecycle", attributed_to=_OWNER_ID
    )
    seed_case_manager_participant(dl, case, _MANAGER_ID)
    seed_case_owner_participant(dl, case, _OWNER_ID)
    return case


def _add(dl, report, *, sender=_OWNER_ID):
    event = extract_event(
        add_report_to_case_activity(report, target=_CASE_ID, actor=sender)
    )
    return AddReportToCaseReceivedUseCase(
        dl,
        cast(AddReportToCaseReceivedEvent, event),
        sync_port=SyncActivityAdapter(dl),
        wire_render_port=As2WireRenderAdapter(),
    ).execute()


def _report_ids(case: as_VulnerabilityCase) -> list[str]:
    return [cast(str, _as_id(r)) for r in case.vulnerability_reports]


def _reports(dl) -> list[str]:
    return _report_ids(cast(as_VulnerabilityCase, dl.read(_CASE_ID)))


def _entries(dl) -> list[CaseLedgerEntry]:
    return [
        cast(CaseLedgerEntry, o)
        for o in dl.list_objects("CaseLedgerEntry")
        if isinstance(o, CaseLedgerEntry)
    ]


@pytest.mark.spec("HP-01-003")
@pytest.mark.spec("CLP-10-005")
def test_adding_new_report_is_applied_and_committed(dl):
    report = gen_report()
    dl.create(_managed_case(dl))

    result = _add(dl, report)

    assert result.disposition == HandlerDisposition.APPLIED
    assert _reports(dl) == [report.id_]
    assert [e.event_type for e in _entries(dl)] == ["add_report_to_case"]


@pytest.mark.spec("HP-01-003")
def test_report_already_in_case_is_skipped_and_commits_nothing(dl):
    report = gen_report()
    case = _managed_case(dl)
    case.vulnerability_reports.append(report.id_)
    dl.create(case)

    result = _add(dl, report)

    assert result.disposition == HandlerDisposition.SKIPPED
    assert _entries(dl) == []


@pytest.mark.spec("HP-01-005")
def test_report_at_non_manager_is_refused(dl):
    """A receiver that is not the CASE_MANAGER neither attaches nor commits."""
    case = as_VulnerabilityCase(
        id_=_CASE_ID, name="Lifecycle", attributed_to=_OWNER_ID
    )
    seed_case_manager_participant(dl, case, _OTHER_ID)
    dl.create(case)

    result = _add(dl, gen_report(), sender=_OTHER_ID)

    assert result.disposition == HandlerDisposition.REFUSED
    assert _reports(dl) == []
    assert _entries(dl) == []


@pytest.mark.spec("CM-30-002")
def test_report_from_non_owner_is_refused_and_commits_nothing(dl):
    dl.create(_managed_case(dl))

    result = _add(dl, gen_report(), sender=_OTHER_ID)

    assert result.disposition == HandlerDisposition.REFUSED
    assert _reports(dl) == []
    assert _entries(dl) == []


@pytest.mark.spec("HP-01-003")
def test_unknown_case_is_refused(dl):
    result = _add(dl, gen_report())

    assert result.disposition == HandlerDisposition.REFUSED
    assert result.reason is not None and _CASE_ID in result.reason


@pytest.mark.spec("HP-01-003")
@pytest.mark.parametrize("missing", ["report_id", "case_id"])
def test_missing_id_is_refused(dl, missing):
    request = cast(
        AddReportToCaseReceivedEvent,
        SimpleNamespace(
            report_id=None if missing == "report_id" else "r",
            case_id=None if missing == "case_id" else _CASE_ID,
        ),
    )

    result = AddReportToCaseReceivedUseCase(dl, request).execute()

    assert result.disposition == HandlerDisposition.REFUSED


@pytest.mark.spec("SYNC-02-002")
@pytest.mark.spec("RSH-08-004")
def test_late_joiner_receives_the_added_report_through_backfill(dl):
    """A participant invited after the report was added converges on it.

    The join-time backfill replays the committed ``add_report_to_case`` entry
    and the replica apply node lists the report on the joiner's case.
    """
    invitee_id = "https://example.org/actors/late-joiner"
    report = gen_report()
    dl.create(_managed_case(dl))
    assert _add(dl, report).disposition == HandlerDisposition.APPLIED

    sync_port = MagicMock(spec=SyncActivityPort)
    bridge = BTBridge(
        datalayer=dl,
        wire_render_port=As2WireRenderAdapter(),
        sync_port=sync_port,
    )
    result = bridge.execute_with_setup(
        tree=BackfillCanonicalLedgerToInviteeNode(
            case_id=_CASE_ID, invitee_id=invitee_id
        ),
        actor_id=_MANAGER_ID,
    )
    assert result.status == Status.SUCCESS
    sent = [
        call.kwargs["entry"]
        for call in sync_port.send_announce_log_entry.call_args_list
    ]
    report_entries = [e for e in sent if e.event_type == "add_report_to_case"]
    assert len(report_entries) == 1

    replica = SqliteDataLayer("sqlite:///:memory:", actor_id=invitee_id)
    replica.create(
        as_VulnerabilityCase(id_=_CASE_ID, name="Lifecycle replica")
    )
    activity = SimpleNamespace(
        log_entry=report_entries[0], actor_id=_MANAGER_ID
    )
    applied = BTBridge(
        datalayer=replica, wire_render_port=As2WireRenderAdapter()
    ).execute_with_setup(
        tree=ApplyOfferReportFromLedgerNode(name="ApplyReport"),
        actor_id=invitee_id,
        activity=activity,
    )
    assert applied.status == Status.SUCCESS
    joined = cast(as_VulnerabilityCase, replica.read(_CASE_ID))
    assert _report_ids(joined) == [report.id_]


@pytest.mark.spec("CM-30-002")
def test_report_at_replica_from_non_manager_is_refused(dl):
    """At a replica only the CASE_MANAGER is an entitled sender."""
    case = as_VulnerabilityCase(
        id_=_CASE_ID, name="Lifecycle", attributed_to=_OWNER_ID
    )
    seed_case_manager_participant(dl, case, _OTHER_ID)
    dl.create(case)

    result = _add(dl, gen_report(), sender=_OWNER_ID)

    assert result.disposition == HandlerDisposition.REFUSED
    assert _reports(dl) == []
    assert _entries(dl) == []


@pytest.mark.spec("SYNC-12-003")
def test_apply_report_entry_is_idempotent_and_tolerates_a_missing_case(dl):
    """The replica apply node lists a report once and skips an unseeded case."""
    report_id = "https://example.org/reports/replay"
    entry = CaseLedgerEntry(
        case_id=_CASE_ID,
        log_index=0,
        log_object_id="https://example.org/activities/add-report",
        event_type="add_report_to_case",
        payload_snapshot={"object": report_id},
        prev_log_hash="0" * 64,
        entry_hash="1" * 64,
    )
    activity = SimpleNamespace(log_entry=entry, actor_id=_MANAGER_ID)

    def apply() -> Status:
        return (
            BTBridge(datalayer=dl, wire_render_port=As2WireRenderAdapter())
            .execute_with_setup(
                tree=ApplyOfferReportFromLedgerNode(name="ApplyReport"),
                actor_id=_MANAGER_ID,
                activity=activity,
            )
            .status
        )

    assert apply() == Status.SUCCESS  # no case replica yet: a no-op
    dl.create(as_VulnerabilityCase(id_=_CASE_ID, name="Replica"))
    assert apply() == Status.SUCCESS
    assert apply() == Status.SUCCESS
    assert _reports(dl) == [report_id]
